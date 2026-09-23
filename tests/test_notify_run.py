"""Unit tests for scripts/notify_run.sh and dashboard/notify_slack.py.

notify_run.sh is executed for real against a throwaway workspace whose
``dashboard/notify_slack.py`` is a fake that records its argv instead of
posting to Slack, so the start/stop notices, exit statuses, log tee, lock,
PID file, signal forwarding and the --on-success hook are all checked without
a webhook.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness import REPO_ROOT

NOTIFY_RUN = REPO_ROOT / "scripts" / "notify_run.sh"

FAKE_NOTIFIER = """\
import json, os, sys
with open(os.environ["FAKE_NOTIFY_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("FAKE_NOTIFY_FAIL") == "1":
    raise SystemExit(1)
"""


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """A workspace root with a fake notifier; notify_run.sh cds into it."""
    (tmp_path / "dashboard").mkdir()
    (tmp_path / "dashboard" / "notify_slack.py").write_text(FAKE_NOTIFIER)
    return tmp_path


def env_for(ws: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"ALLOW_NO_SLACK", "SLACK_WEBHOOK_URL"}}
    env.update({
        "AGENTCTX_WS": str(ws),
        "FAKE_NOTIFY_LOG": str(ws / "notices.jsonl"),
        "NOTIFY_PYTHON": sys.executable,
        "SLACK_WEBHOOK_URL": "https://hooks.slack.invalid/test",
    })
    env.update(extra)
    return env


def notices(ws: Path) -> list[list[str]]:
    path = ws / "notices.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run(ws: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(NOTIFY_RUN), *args], cwd=ws, env=env or env_for(ws),
                          capture_output=True, text=True, timeout=60)


def test_success_posts_start_and_completion(ws: Path) -> None:
    proc = run(ws, "--unit", "exp/unit-a", "--", "bash", "-c", "echo hello from the run; exit 0")
    assert proc.returncode == 0, proc.stderr
    log = ws / "logs" / "exp_unit-a.log"   # default log: "/" in the unit becomes "_"
    assert notices(ws) == [["start", "exp/unit-a"],
                           ["stop", "exp/unit-a", "success", "0", "logs/exp_unit-a.log"]]
    assert "hello from the run" in log.read_text()
    assert "hello from the run" in proc.stdout   # the tee keeps the nohup log too


def test_failure_reports_exit_status(ws: Path) -> None:
    proc = run(ws, "--unit", "u", "--log", "logs/custom.log", "--", "bash", "-c", "echo boom >&2; exit 3")
    assert proc.returncode == 3
    assert notices(ws)[-1] == ["stop", "u", "failed", "3", "logs/custom.log"]
    assert "boom" in (ws / "logs" / "custom.log").read_text()   # stderr is captured as well


def test_missing_webhook_refuses_before_starting(ws: Path) -> None:
    env = env_for(ws)
    del env["SLACK_WEBHOOK_URL"]
    marker = ws / "ran"
    proc = run(ws, "--unit", "u", "--", "touch", str(marker), env=env)
    assert proc.returncode == 2
    assert "SLACK_WEBHOOK_URL" in proc.stderr
    assert not marker.exists()
    assert notices(ws) == []


def test_allow_no_slack_runs_silently(ws: Path) -> None:
    env = env_for(ws, ALLOW_NO_SLACK="1")
    del env["SLACK_WEBHOOK_URL"]
    proc = run(ws, "--unit", "u", "--", "true", env=env)
    assert proc.returncode == 0, proc.stderr
    assert notices(ws) == []


def test_notifier_failure_does_not_change_exit_status(ws: Path) -> None:
    proc = run(ws, "--unit", "u", "--", "true", env=env_for(ws, FAKE_NOTIFY_FAIL="1"))
    assert proc.returncode == 0
    assert "Slack notification failed" in proc.stderr


def test_lock_refuses_second_launcher(ws: Path) -> None:
    (ws / "logs").mkdir()
    with open(ws / "logs" / "job.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = ws / "ran"
        proc = run(ws, "--unit", "u", "--lock", "job", "--", "touch", str(marker))
    assert proc.returncode == 1
    assert "already running" in proc.stderr
    assert not marker.exists()
    assert notices(ws) == []
    # ... and runs once the lock is free.
    proc = run(ws, "--unit", "u", "--lock", "job", "--", "touch", str(marker))
    assert proc.returncode == 0, proc.stderr
    assert marker.exists()


def test_on_success_hook_runs_only_after_a_clean_exit(ws: Path) -> None:
    hook = "echo unit=$UNIT log=$LOG_FILE > hook.out"
    proc = run(ws, "--unit", "u", "--on-success", hook, "--", "false")
    assert proc.returncode == 1
    assert not (ws / "hook.out").exists()

    proc = run(ws, "--unit", "u", "--log", "logs/x.log", "--on-success", hook, "--", "true")
    assert proc.returncode == 0, proc.stderr
    assert (ws / "hook.out").read_text().strip() == "unit=u log=logs/x.log"
    # the hook runs after the completion notice
    assert notices(ws)[-1][0] == "stop"


def test_hook_failure_is_reported_but_not_fatal(ws: Path) -> None:
    proc = run(ws, "--unit", "u", "--on-success", "exit 7", "--", "true")
    assert proc.returncode == 0
    assert "--on-success command failed (exit 7)" in proc.stderr


def wait_for(predicate, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met in time")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.parametrize("sig,status,name", [(signal.SIGTERM, 143, "TERM"), (signal.SIGINT, 130, "INT"),
                                              (signal.SIGHUP, 129, "HUP")])
def test_signal_stops_the_command_group_then_notifies(ws: Path, sig: signal.Signals, status: int, name: str) -> None:
    pid_file = ws / "child.pid"
    # The command spawns a grandchild; both must be gone before the stop notice.
    cmd = "sleep 300 & echo $! > grandchild.pid; wait"
    proc = subprocess.Popen(["bash", str(NOTIFY_RUN), "--unit", "u", "--pid-file", str(pid_file),
                             "--", "bash", "-c", cmd],
                            cwd=ws, env=env_for(ws), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_for(lambda: pid_file.exists() and (ws / "grandchild.pid").exists())
        child = int(pid_file.read_text())
        grandchild = int((ws / "grandchild.pid").read_text())
        assert os.getpgid(child) == child   # its own process group (setsid)
        proc.send_signal(sig)
        _, err = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == status, err
    wait_for(lambda: not alive(child) and not alive(grandchild), timeout=5)
    assert not pid_file.exists()
    assert notices(ws) == [["start", "u"], ["stop", "u", "killed", str(status), "logs/u.log"]]


def test_usage_errors(ws: Path) -> None:
    assert run(ws, "--", "true").returncode == 2                 # no --unit
    assert run(ws, "--unit", "u").returncode == 2                # no command
    assert run(ws, "--unit", "u", "--bogus", "--", "true").returncode == 2


# ── dashboard/notify_slack.py ──────────────────────────────────────────────────

def _notify_slack():
    sys.path.insert(0, str(REPO_ROOT / "dashboard"))
    import notify_slack
    return notify_slack


def test_notify_slack_stop_success_is_a_completion() -> None:
    text = _notify_slack().format_message(["stop", "unit-A", "success", "0", "logs/a.log"])
    assert text.startswith("✅")
    assert "• exit status: `0`" in text and "• log: `logs/a.log`" in text


@pytest.mark.parametrize("argv", [["stop", "u", "failed", "3", "l"], ["stop", "u", "killed", "143", "l"],
                                  ["stop", "u", "success", "1", "l"]])
def test_notify_slack_stop_non_success_is_a_termination(argv: list[str]) -> None:
    assert _notify_slack().format_message(argv).startswith("🚨")


def test_notify_slack_rejects_the_old_six_argument_stop() -> None:
    # The former *_notified.sh wrappers passed "exited"/"killed" as a 4th value,
    # which shifted the status into the log slot and made every success a 🚨.
    with pytest.raises(ValueError):
        _notify_slack().format_message(["stop", "u", "success", "exited", "0", "l"])
    with pytest.raises(ValueError):
        _notify_slack().format_message(["start"])


def test_glm_split_script_dispatches_to_notify_run(ws: Path) -> None:
    """run_glm_tb_ablation_split.sh keeps the GPU-group logic and delegates the rest."""
    scripts = ws / "scripts"
    (scripts / "expansions").mkdir(parents=True)
    shutil.copy(NOTIFY_RUN, scripts / "notify_run.sh")
    shutil.copy(REPO_ROOT / "scripts" / "expansions" / "run_glm_tb_ablation_split.sh", scripts / "expansions")
    fake = scripts / "expansions" / "run_agent_models_expansion_tb.sh"
    fake.write_text('#!/usr/bin/env bash\necho "args=$* parts=$ABLATION_PARTS health=$GLM_HEALTH_URL suffix=$TB_LOG_SUFFIX"\n')
    proc = subprocess.run(["bash", str(scripts / "expansions" / "run_glm_tb_ablation_split.sh"), "gpu4-7"],
                          cwd=ws, env=env_for(ws), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "args=glm ablation parts=di d05 health=http://localhost:8004/v1/models suffix=ablation_gpu4-7" in proc.stdout
    assert notices(ws) == [["start", "glm-terminal-bench-ablation-gpu4-7"],
                           ["stop", "glm-terminal-bench-ablation-gpu4-7", "success", "0",
                            "logs/followup_tb_glm_ablation_gpu4-7.nohup.log"]]
    assert (ws / "logs" / "glm_tb_ablation_gpu4-7.lock").exists()
    proc = subprocess.run(["bash", str(scripts / "expansions" / "run_glm_tb_ablation_split.sh"), "gpu9"],
                          cwd=ws, env=env_for(ws), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2
