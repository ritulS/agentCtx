"""Offline checks for the r2 P30S shell launcher (scripts/expansions/run_r2_swe_p30s.sh).

Run with: uvx --with pyyaml pytest tests/test_r2_launch.py
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts/expansions/run_r2_swe_p30s.sh"
INF = "999999999"


def _sandbox(tmp: Path) -> tuple[Path, dict]:
    for name in ["scripts/run_experiment_r2.py", "task_lists/swe_verified/p30_stratified.json",
                 "configs/config-qwen-vllm.yaml", "configs/config-online-trc.yaml"]:
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    (tmp / "configs/config-qwen-vllm.yaml").write_text('model:\n  api_base: "http://localhost:8000/v1"\n')
    fake = tmp / "fake-python"
    fake.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                    'with open(os.environ["CAPTURE"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
    fake.chmod(0o755)
    curl = tmp / "curl"
    curl.write_text("#!/bin/sh\nexit 0\n")
    curl.chmod(0o755)
    capture = tmp / "calls.jsonl"
    env = dict(os.environ, AGENTCTX_WS=str(tmp), PYTHON=str(fake), CAPTURE=str(capture),
               PATH=f"{tmp}:{os.environ['PATH']}")
    env.pop("AGENTCTX_LOG_FILE", None)
    return capture, env


def _opt(argv: list[str], option: str) -> str:
    return argv[argv.index(option) + 1]


class R2P30sLaunchTests(unittest.TestCase):
    def test_default_cells_are_length_free_summaries_on_p30s(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(len(calls), 2 * 2)
        self.assertEqual(sum("--eval-only" in c for c in calls), 2)
        for c in calls:
            self.assertEqual(_opt(c, "--r2-section"), "p30s")
            self.assertEqual(_opt(c, "--r2-model"), "qwen35b")
            self.assertEqual(Path(_opt(c, "--tasks-file")).name, "p30_stratified.json")
            self.assertEqual(_opt(c, "--runs-per-task"), "3")
            self.assertEqual(_opt(c, "--budget"), "15000")
            self.assertEqual(_opt(c, "--depth"), "0.5")
            cell = _opt(c, "--r2-cell")
            self.assertEqual(_opt(c, "--ablation"), f"r2-qwen35b-p30s-{cell}")
        self.assertEqual(
            [(_opt(c, "--r2-cell"), _opt(c, "--conditions")) for c in calls if "--eval-only" not in c],
            [("di__b15k__su-free", "summarization-free"),
             ("di__b15k__ss-free", "structured-summarize-free")],
        )

    def test_presets(self):
        expected = {
            "fc": [("di__binf__fc", "full-context", INF)],
            "otrc": [("di__binf__otrc", "online-trc", INF)],
            "su-free": [("di__b15k__su-free", "summarization-free", "15000")],
            "baselines": [("di__binf__fc", "full-context", INF), ("di__binf__otrc", "online-trc", INF)],
        }
        for preset, cells in expected.items():
            with self.subTest(preset=preset), tempfile.TemporaryDirectory() as tmp:
                capture, env = _sandbox(Path(tmp))
                env["RUN_EVAL"] = "0"
                subprocess.run(["bash", str(LAUNCHER), preset], env=env, check=True, stdout=subprocess.DEVNULL)
                calls = [json.loads(line) for line in capture.read_text().splitlines()]
                self.assertEqual([(_opt(c, "--r2-cell"), _opt(c, "--conditions"), _opt(c, "--budget")) for c in calls], cells)
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            result = subprocess.run(["bash", str(LAUNCHER), "bogus"], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown preset", result.stderr)
            # CELLS wins over the preset.
            env.update(CELLS="di__b15k__trc:tool-result-clear:0.5", RUN_EVAL="0")
            subprocess.run(["bash", str(LAUNCHER), "fc"], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual([_opt(c, "--r2-cell") for c in calls], ["di__b15k__trc"])

    def test_overrides_and_bad_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            env.update(CELLS="di__b20k__trc:tool-result-clear:0.5 di__binf__fc:full-context:0.5",
                       N_TASKS="2", RUNS_PER_TASK="5", RUN_EVAL="0", R2_MODEL="qwen35b-smoke")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            self.assertEqual([_opt(c, "--budget") for c in calls], ["20000", INF])
            self.assertEqual([_opt(c, "--runs-per-task") for c in calls], ["5", "5"])
            self.assertEqual(_opt(calls[0], "--n-tasks"), "2")
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-smoke")

            capture.write_text("")
            env.update(CELLS="d05__b15k__tr:truncation:0.5 d05__bogus__tr:truncation:0.5")
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no b<N>k / binf budget tag", result.stderr)
            self.assertEqual(capture.read_text(), "")   # validated before the first run


if __name__ == "__main__":
    unittest.main()
