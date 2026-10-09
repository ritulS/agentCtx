"""AGENTCTX_PROFILE=albus-swe (scripts/lib/profiles.sh) in the Qwen3.5-35B-A3B
serving launcher: all 8 GPUs and --tensor-parallel-size 8, otherwise the Dobby
production server (GPUs 0-3, TP=4). The launcher is run for real against a
throwaway workspace whose venv python records its argv and CUDA_VISIBLE_DEVICES.

Run with: uvx --with pyyaml pytest tests/test_serving_profile.py
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts/serving/start_vllm_qwen35_prefix_cache.sh"

FAKE_VLLM = """#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["CAPTURE"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cuda": os.environ.get("CUDA_VISIBLE_DEVICES")}) + "\\n")
time.sleep(4)   # outlive the launcher's startup check
"""


def _launch(tmp: Path, **env) -> tuple[subprocess.CompletedProcess, list[dict]]:
    venv = tmp / "venv/bin"
    venv.mkdir(parents=True)
    (venv / "python3").write_text(FAKE_VLLM)
    (venv / "python3").chmod(0o755)
    for tool in ("ss", "pgrep"):        # "nothing is running yet"
        (tmp / tool).write_text("#!/bin/sh\nexit 1\n")
        (tmp / tool).chmod(0o755)
    capture = tmp / "calls.jsonl"
    base = {k: v for k, v in os.environ.items()
            if k not in ("AGENTCTX_PROFILE", "AGENTCTX_KV_TRACE", "AGENTCTX_KV_TRACE_DIR")}
    base.update(AGENTCTX_WS=str(tmp), CAPTURE=str(capture), PATH=f"{tmp}:{os.environ['PATH']}", **env)
    result = subprocess.run(["bash", str(LAUNCHER)], env=base, capture_output=True, text=True)
    pid_file = tmp / "logs/servers/vllm_qwen35_a3b.pid"
    if pid_file.exists():
        subprocess.run(["kill", pid_file.read_text().strip()], stderr=subprocess.DEVNULL)
    calls = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
    return result, calls


def _opt(argv: list[str], option: str) -> str:
    return argv[argv.index(option) + 1]


class ServingProfileTests(unittest.TestCase):
    def test_default_is_dobby_gpus_0_3_tp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = _launch(Path(tmp))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["cuda"], "0,1,2,3")
        self.assertEqual(_opt(calls[0]["argv"], "--tensor-parallel-size"), "4")
        self.assertEqual(_opt(calls[0]["argv"], "--max-model-len"), "102400")
        self.assertIn("--enable-prefix-caching", calls[0]["argv"])
        self.assertIn("no profile", result.stdout)

    def test_albus_swe_profile_takes_all_eight_gpus_tp8(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = _launch(Path(tmp), AGENTCTX_PROFILE="albus-swe")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[0]["cuda"], "0,1,2,3,4,5,6,7")
        self.assertEqual(_opt(calls[0]["argv"], "--tensor-parallel-size"), "8")
        # Only the GPU set and TP change under the profile.
        self.assertEqual(_opt(calls[0]["argv"], "--max-model-len"), "102400")
        self.assertEqual(_opt(calls[0]["argv"], "--max-num-seqs"), "64")
        self.assertEqual(_opt(calls[0]["argv"], "--port"), "8000")
        self.assertIn("--enable-prefix-caching", calls[0]["argv"])
        self.assertIn("profile albus-swe", result.stdout)

    def test_unknown_profile_refuses_to_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = _launch(Path(tmp), AGENTCTX_PROFILE="albus")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown AGENTCTX_PROFILE", result.stderr)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
