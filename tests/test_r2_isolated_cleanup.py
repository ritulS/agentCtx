"""Failure-path checks for run isolation, without a GPU or container daemon."""

import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

from test_r2_adaptive_launch import ISOLATED, _isolated_sandbox


class IsolatedCleanupTests(unittest.TestCase):
    def test_normal_exit_stops_orphaned_agent_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, env = _isolated_sandbox(Path(tmp))
            runner = Path(env["PYTHON"])
            original = runner.read_text()
            runner.write_text('''#!/usr/bin/env python3
import os, subprocess, sys
from pathlib import Path
if "--eval-only" not in sys.argv:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(os.environ["CHILD_PID"]).write_text(str(child.pid))
''' + original)
            marker = Path(tmp) / "orphan-pid"
            try:
                subprocess.run(["bash", str(ISOLATED)],
                               env={**env, "CHILD_PID": str(marker), "RUNS_PER_TASK": "1", "N_TASKS": "1"},
                               stdout=subprocess.DEVNULL, check=True, timeout=30)
                pid = int(marker.read_text())
                state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                       capture_output=True, text=True).stdout.strip()
                self.assertTrue(not state or state.startswith("Z"), (pid, state))
            finally:
                if marker.exists():
                    try:
                        os.kill(int(marker.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_stop_failure_still_purges_and_prevents_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            Path(env["VLLM_STOP_SCRIPT"]).write_text('echo stop-failed >> "$EVENTS"\nexit 1\n')
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "RUNS_PER_TASK": "2"},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            lines = events.read_text().splitlines()
            self.assertEqual(lines.count("start"), 1)
            self.assertEqual(lines[lines.index("stop-failed") + 1], "docker ps -a")
            self.assertIn("cleanup failed", result.stdout)
            self.assertTrue(capture.exists())

    def test_server_still_answering_after_stop_prevents_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, events, env = _isolated_sandbox(Path(tmp))
            # A broken stop script claims success but leaves the server up.
            Path(env["VLLM_STOP_SCRIPT"]).write_text('echo stop-noop >> "$EVENTS"\n')
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "RUNS_PER_TASK": "2"},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(events.read_text().splitlines().count("start"), 1)
            self.assertIn("server still answers", result.stdout)

    def test_final_container_listing_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, env = _isolated_sandbox(Path(tmp))
            docker = Path(tmp) / "docker"
            docker.write_text('''#!/bin/sh
echo "docker $1 $2" >> "$EVENTS"
case "$1" in
  ps)
    count=0
    [ ! -f "$STATE.count" ] || count=$(cat "$STATE.count")
    count=$((count + 1))
    echo "$count" > "$STATE.count"
    [ "$count" -lt 4 ] || exit 1
    cat "$STATE" ;;
  rm) : > "$STATE" ;;
esac
''')
            result = subprocess.run(["bash", str(ISOLATED)],
                                    env={**env, "RUNS_PER_TASK": "1", "N_TASKS": "1"},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("final cleanup failed", result.stdout)
            self.assertFalse(Path(env["VLLM_PID_FILE"]).exists())

    def test_term_stops_children_and_concurrent_driver_cannot_clean_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, events, env = _isolated_sandbox(Path(tmp))
            marker = Path(tmp) / "child-pids"
            runner = Path(env["PYTHON"])
            runner.write_text('''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
Path(os.environ["CHILD_PIDS"]).write_text(f"{os.getpgrp()} {os.getpid()} {child.pid}")
time.sleep(300)
''')
            env.update(CHILD_PIDS=str(marker), RUNS_PER_TASK="2")
            # Use a real file so the launcher's tee cannot keep a PIPE open.
            with (Path(tmp) / "output.log").open("w+") as output:
                process = subprocess.Popen(["bash", str(ISOLATED)], env=env, stdout=output,
                                           stderr=subprocess.STDOUT)
                pgid = None
                try:
                    deadline = time.monotonic() + 15
                    while not marker.exists() and time.monotonic() < deadline:
                        self.assertIsNone(process.poll())
                        time.sleep(0.05)
                    self.assertTrue(marker.exists())
                    pgid, *pids = map(int, marker.read_text().split())
                    before = events.read_text()
                    other = subprocess.run(["bash", str(ISOLATED)], env=env,
                                           capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(other.returncode, 0)
                    self.assertIn("another isolated driver", other.stdout)
                    self.assertEqual(events.read_text(), before)
                    process.send_signal(signal.SIGTERM)
                    self.assertEqual(process.wait(timeout=20), 143)
                    for pid in pids:
                        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                               capture_output=True, text=True).stdout.strip()
                        self.assertTrue(not state or state.startswith("Z"), (pid, state))
                    self.assertFalse(Path(env["VLLM_PID_FILE"]).exists())
                    self.assertEqual(Path(env["STATE"]).read_text(), "")
                    self.assertEqual(events.read_text().splitlines().count("start"), 1)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    if pgid is not None:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_sigkill_of_the_driver_is_cleaned_up_by_the_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, events, env = _isolated_sandbox(Path(tmp))
            marker = Path(tmp) / "child-pids"
            runner = Path(env["PYTHON"])
            runner.write_text('''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
Path(os.environ["CHILD_PIDS"]).write_text(f"{os.getpgrp()} {os.getpid()} {child.pid}")
time.sleep(300)
''')
            env.update(CHILD_PIDS=str(marker), RUNS_PER_TASK="2")
            output_log = Path(tmp) / "output.log"
            with output_log.open("w+") as output:
                process = subprocess.Popen(["bash", str(ISOLATED)], env=env, stdout=output,
                                           stderr=subprocess.STDOUT)
                pgid = None
                try:
                    deadline = time.monotonic() + 15
                    while not marker.exists() and time.monotonic() < deadline:
                        self.assertIsNone(process.poll())
                        time.sleep(0.05)
                    self.assertTrue(marker.exists())
                    pgid, *pids = map(int, marker.read_text().split())
                    process.send_signal(signal.SIGKILL)
                    self.assertEqual(process.wait(timeout=10), -9)
                    # The watchdog notices within a few seconds and cleans up on its own.
                    deadline = time.monotonic() + 40
                    while time.monotonic() < deadline and "watchdog: clean" not in output_log.read_text():
                        time.sleep(0.2)
                    text = output_log.read_text()
                    self.assertIn("watchdog: the driver", text)
                    self.assertIn("watchdog: clean", text)
                    for pid in pids:
                        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                               capture_output=True, text=True).stdout.strip()
                        self.assertTrue(not state or state.startswith("Z"), (pid, state))
                    self.assertFalse(Path(env["VLLM_PID_FILE"]).exists())
                    self.assertEqual(Path(env["STATE"]).read_text(), "")
                    lines = events.read_text().splitlines()
                    self.assertEqual((lines.count("start"), lines.count("stop")), (1, 1))
                    self.assertFalse((Path(tmp) / "logs/experiments/r2_sb_sandbox_isolated.pilot_pgid").exists())
                    # The lock is released once the watchdog is done: a new driver can start.
                    result = subprocess.run(["bash", str(ISOLATED)], env={**env, "DRY_RUN": "1"},
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stdout)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    if pgid is not None:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass


if __name__ == "__main__":
    unittest.main()
