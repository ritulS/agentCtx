"""Offline checks for adaptive r2 cells: the never7 shell launcher
(scripts/expansions/run_r2_swe_never7_adaptive.sh) and the cell validation it
relies on (agentctx.experiments.iclr.validate_adaptive_cell_semantics).

Run with: uvx --with pyyaml pytest tests/test_r2_adaptive_launch.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
LAUNCHER = ROOT / "scripts/expansions/run_r2_swe_never7_adaptive.sh"
SCHEDULES = ROOT / "configs/adaptive/never7_prefix3"
PATTERNS = ["tts", "tst", "tss", "stt", "sts", "sst"]

from agentctx.experiments.iclr import validate_adaptive_cell_semantics  # noqa: E402


def _sandbox(tmp: Path) -> tuple[Path, dict]:
    for name in ["scripts/run_experiment_r2.py",
                 "task_lists/swe_verified/p30s_qwen35b_never_resolved.json",
                 "task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json",
                 "configs/config-qwen-vllm.yaml", "configs/config-online-trc.yaml"]:
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    (tmp / "configs/config-qwen-vllm.yaml").write_text('model:\n  api_base: "http://localhost:8000/v1"\n')
    sched = tmp / "configs/adaptive/never7_prefix3"
    sched.mkdir(parents=True)
    for pat in PATTERNS:
        (sched / f"{pat}.json").write_text((SCHEDULES / f"{pat}.json").read_text())
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


class Never7SchedulesTests(unittest.TestCase):
    def test_six_mixed_prefix3_schedules_at_15k_depth_05(self):
        names = {"truncation": "t", "summarization_free": "s"}
        found = sorted(p.stem for p in SCHEDULES.glob("*.json"))
        self.assertEqual(found, sorted(PATTERNS))
        for pat in PATTERNS:
            entries = json.loads((SCHEDULES / f"{pat}.json").read_text())
            self.assertEqual("".join(names[e["primitive"]] for e in entries), pat)
            for e in entries:
                self.assertEqual((e["budget"], e["depth"]), (15000, 0.5))


class Never7LaunchTests(unittest.TestCase):
    def test_default_chain_runs_every_pattern_then_evaluates_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(len(calls), 2 * len(PATTERNS))
        self.assertEqual([("--eval-only" in c) for c in calls], [False, True] * len(PATTERNS))
        for c in calls:
            self.assertEqual(_opt(c, "--r2-section"), "p30s_never7")
            self.assertEqual(_opt(c, "--r2-model"), "qwen35b")
            self.assertEqual(Path(_opt(c, "--tasks-file")).name, "p30s_qwen35b_never_resolved.json")
            self.assertEqual(_opt(c, "--runs-per-task"), "3")
            self.assertEqual(_opt(c, "--conditions"), "adaptive")
            self.assertNotIn("--budget", c)
            self.assertNotIn("--depth", c)
            cell = _opt(c, "--r2-cell")
            self.assertEqual(_opt(c, "--ablation"), f"r2-qwen35b-p30s_never7-{cell}")
            pat = cell.rsplit("-", 1)[1]
            self.assertEqual(cell, f"d05__b15k__adaptive-prefix3-{pat}")
            self.assertEqual(Path(_opt(c, "--adaptive-schedule")).name, f"{pat}.json")
        self.assertEqual([_opt(c, "--r2-cell").rsplit("-", 1)[1] for c in calls if "--eval-only" not in c],
                         PATTERNS)

    def test_overrides_and_bad_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            env.update(PATTERNS="sts", N_TASKS="1", RUNS_PER_TASK="1", RUN_EVAL="0",
                       R2_MODEL="qwen35b-smoke")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(_opt(calls[0], "--r2-cell"), "d05__b15k__adaptive-prefix3-sts")
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-smoke")
            self.assertEqual(_opt(calls[0], "--n-tasks"), "1")
            self.assertEqual(_opt(calls[0], "--runs-per-task"), "1")

            capture.write_text("")
            env.update(PATTERNS="sts", R2_SECTION="p100_minus_p30s_never13")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(_opt(calls[0], "--r2-section"), "p100_minus_p30s_never13")
            self.assertEqual(Path(_opt(calls[0], "--tasks-file")).name,
                             "p100_minus_p30s_qwen35b_never_resolved.json")
            self.assertEqual(_opt(calls[0], "--ablation"),
                             "r2-qwen35b-smoke-p100_minus_p30s_never13-d05__b15k__adaptive-prefix3-sts")
            self.assertTrue((Path(tmp) / "logs/experiments/r2_sb_p100_minus_p30s_never13_qwen35b-smoke.lock").exists())

            capture.write_text("")
            env.update(R2_SECTION="p100_never")   # not a known section
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown R2_SECTION", result.stderr)
            self.assertEqual(capture.read_text(), "")
            env.update(R2_SECTION="p30s_never7")

            capture.write_text("")
            env.update(PATTERNS="tts ttt")   # ttt has no schedule (it is the fixed TR cell)
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ttt.json", result.stderr)
            self.assertEqual(capture.read_text(), "")   # validated before the first run


class AdaptiveCellValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.schedule = self.root / "tts.json"
        self.schedule.write_text((SCHEDULES / "tts.json").read_text())
        self.cell = "d05__b15k__adaptive-prefix3-tts"
        self.args = ["--conditions", "adaptive", "--adaptive-schedule", str(self.schedule),
                     "--tasks-file", "x.json"]

    def test_accepts_matching_schedule(self):
        validate_adaptive_cell_semantics(self.cell, self.args, self.root / "cell")

    def test_rejections(self):
        cases = {
            "not an adaptive-<tag> cell": ("d05__b15k__tr", self.args),
            "exactly `--conditions adaptive`": (self.cell, ["--conditions", "truncation",
                                                            "--adaptive-schedule", str(self.schedule)]),
            "--budget does not apply": (self.cell, [*self.args, "--budget", "15000"]),
            "--depth does not apply": (self.cell, [*self.args, "--depth=0.5"]),
            "require --adaptive-schedule": (self.cell, ["--conditions", "adaptive",
                                                        "--adaptive-policy", "m:f"]),
            "explicit depth tag": ("di__b15k__adaptive-prefix3-tts", self.args),
            "numeric b<N>k budget tag": ("d05__binf__adaptive-prefix3-tts", self.args),
            "does not match cell budget b20k": ("d05__b20k__adaptive-prefix3-tts", self.args),
            "does not match cell depth d03": ("d03__b15k__adaptive-prefix3-tts", self.args),
        }
        for message, (cell, args) in cases.items():
            with self.subTest(message), self.assertRaisesRegex(SystemExit, message):
                validate_adaptive_cell_semantics(cell, args, self.root / "cell")

    def test_refuses_cell_holding_fixed_condition_rows(self):
        cell_dir = self.root / "cell"
        cell_dir.mkdir()
        (cell_dir / "experiment_results.json").write_text(json.dumps(
            [{"condition": "truncation", "budget": 15000}]))
        with self.assertRaisesRegex(SystemExit, "non-adaptive rows"):
            validate_adaptive_cell_semantics(self.cell, self.args, cell_dir)
        (cell_dir / "experiment_results.json").write_text(json.dumps(
            [{"condition": "adaptive", "budget": 15000}]))
        validate_adaptive_cell_semantics(self.cell, self.args, cell_dir)


if __name__ == "__main__":
    unittest.main()
