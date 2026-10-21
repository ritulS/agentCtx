"""Offline checks for adaptive r2 cells: the never7 shell launcher
(scripts/expansions/run_r2_swe_never7_adaptive.sh), the chains and sandbox
drivers built on it (majority uniform, capped pilot, sandbox chain, isolated
serial driver) and the cell validation it relies on
(agentctx.experiments.iclr.validate_adaptive_cell_semantics).

Run with: uvx --with pyyaml pytest tests/test_r2_adaptive_launch.py
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
LAUNCHER = ROOT / "scripts/expansions/run_r2_swe_never7_adaptive.sh"
CHAIN = ROOT / "scripts/expansions/run_r2_swe_majority_uniform.sh"
CAPPED = ROOT / "scripts/expansions/run_r2_swe_majority_capped_pilot.sh"
SANDBOX_CHAIN = ROOT / "scripts/expansions/run_r2_swe_sandbox_chain.sh"
ISOLATED = ROOT / "scripts/expansions/run_r2_swe_sandbox_isolated.sh"


def _sandbox_pilot_files(tmp: Path) -> Path:
    """The extra files the capped pilot and the sandbox chain require; returns the 4k summary config."""
    for name in ["configs/config-qwen-vllm-cap4k.yaml", "configs/config-qwen-vllm-cap4k-nothink.yaml",
                 "task_lists/swe_verified/sandbox_su_free_compressing4.json"]:
        (tmp / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp / name).write_text('model:\n  api_base: "http://localhost:8000/v1"\n')
    for name in ["config-summary-qwen35-35b-nothink.yaml", "config-summary-qwen35-35b-nothink-4k.yaml"]:
        (tmp / "configs" / name).write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-35B-A3B\n")
    return tmp / "configs/config-summary-qwen35-35b-nothink-4k.yaml"
SCHEDULES = ROOT / "configs/adaptive/never7_prefix3"
PATTERNS = ["tts", "tst", "tss", "stt", "sts", "sst"]
UNIFORM = ["ttt", "sss"]   # only in the default chain of p100_fc_only4
ALL_ORDERS = ["ttt", *PATTERNS, "sss"]   # the p100_fc_only4 section's eight prefix-3 orders

from agentctx.experiments.iclr import validate_adaptive_cell_semantics  # noqa: E402


def _sandbox(tmp: Path) -> tuple[Path, dict]:
    for name in ["scripts/run_experiment_r2.py",
                 "task_lists/swe_verified/p30s_qwen35b_never_resolved.json",
                 "task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json",
                 "task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json",
                 "task_lists/swe_verified/p100_qwen35b_su-free_majority_resolved.json",
                 "task_lists/swe_verified/p100_qwen35b_tr_majority_resolved.json",
                 "configs/config-qwen-vllm.yaml", "configs/config-online-trc.yaml"]:
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    (tmp / "configs/config-qwen-vllm.yaml").write_text('model:\n  api_base: "http://localhost:8000/v1"\n')
    sched = tmp / "configs/adaptive/never7_prefix3"
    sched.mkdir(parents=True)
    for pat in PATTERNS + UNIFORM:
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
    def test_prefix3_schedules_at_15k_depth_05(self):
        names = {"truncation": "t", "summarization_free": "s"}
        found = sorted(p.stem for p in SCHEDULES.glob("*.json"))
        self.assertEqual(found, sorted(PATTERNS + UNIFORM))
        for pat in PATTERNS + UNIFORM:
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
            self.assertNotIn("--step-limit", c)      # runner defaults
            self.assertNotIn("--agent-timeout", c)
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

    def test_fc_only4_section_runs_all_eight_orders_ten_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            env.update(R2_SECTION="p100_fc_only4")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
        runs = [c for c in calls if "--eval-only" not in c]
        self.assertEqual(len(calls), 2 * len(runs))
        self.assertEqual([_opt(c, "--r2-cell") for c in runs],
                         [f"d05__b15k__adaptive-prefix3-{p}" for p in ["ttt", *PATTERNS, "sss"]])
        for c in calls:
            self.assertEqual(_opt(c, "--r2-section"), "p100_fc_only4")
            self.assertEqual(Path(_opt(c, "--tasks-file")).name, "p100_qwen35b_fc_not_tr_su-free.json")
            self.assertEqual(_opt(c, "--runs-per-task"), "10")
            self.assertEqual(_opt(c, "--step-limit"), "400")
            self.assertEqual(_opt(c, "--agent-timeout"), "7200")
            self.assertEqual(_opt(c, "--conditions"), "adaptive")

    def test_majority_sections_run_one_uniform_order_on_first_five_tasks(self):
        expected = {"p100_su_free_majority": ("sss", "p100_qwen35b_su-free_majority_resolved.json"),
                    "p100_tr_majority": ("ttt", "p100_qwen35b_tr_majority_resolved.json")}
        for section, (pat, tasks) in expected.items():
            with self.subTest(section), tempfile.TemporaryDirectory() as tmp:
                capture, env = _sandbox(Path(tmp))
                env.update(R2_SECTION=section)
                subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
                calls = [json.loads(line) for line in capture.read_text().splitlines()]
                self.assertEqual([("--eval-only" in c) for c in calls], [False, True])
                for c in calls:
                    self.assertEqual(_opt(c, "--r2-section"), section)
                    self.assertEqual(_opt(c, "--r2-cell"), f"d05__b15k__adaptive-prefix3-{pat}")
                    self.assertEqual(Path(_opt(c, "--adaptive-schedule")).name, f"{pat}.json")
                    self.assertEqual(Path(_opt(c, "--tasks-file")).name, tasks)
                    self.assertEqual(_opt(c, "--n-tasks"), "5")
                    self.assertEqual(_opt(c, "--runs-per-task"), "15")
                    self.assertEqual(_opt(c, "--conditions"), "adaptive")
                    self.assertNotIn("--step-limit", c)
                    self.assertNotIn("--agent-timeout", c)
                # N_TASKS=all lifts the section's 5-task default.
                capture.write_text("")
                env.update(N_TASKS="all", RUN_EVAL="0")
                subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
                calls = [json.loads(line) for line in capture.read_text().splitlines()]
                self.assertEqual(len(calls), 1)
                self.assertNotIn("--n-tasks", calls[0])

    def test_summary_config_passes_through_as_summary_config_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            env.update(PATTERNS="sss", RUN_EVAL="0", R2_SECTION="p100_su_free_majority")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertNotIn("--summary-config", calls[0])          # default: the agent summarizes
            summary = Path(tmp) / "configs/config-summary-qwen35-35b-nothink.yaml"
            summary.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-35B-A3B\n")
            capture.write_text("")
            env.update(SUMMARY_CONFIG=str(summary))
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--summary-config"), str(summary))
            # A missing file is refused before anything runs.
            capture.write_text("")
            result = subprocess.run(["bash", str(LAUNCHER)], env={**env, "SUMMARY_CONFIG": str(summary) + ".missing"},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(capture.read_text(), "")

    def test_capped_pilot_summarizer_nothink_routes_only_summaries_through_the_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            summary4k = _sandbox_pilot_files(Path(tmp))
            summary = Path(tmp) / "configs/config-summary-qwen35-35b-nothink.yaml"
            env.update(RUN_EVAL="0")
            subprocess.run(["bash", str(CAPPED)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-cap4k")
            self.assertEqual(Path(_opt(calls[0], "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")
            self.assertNotIn("--summary-config", calls[0])

            capture.write_text("")
            env.update(SUMMARIZER="nothink")
            subprocess.run(["bash", str(CAPPED)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-cap4k-sumnothink")
            self.assertEqual(Path(_opt(calls[0], "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")  # agent: thinking ON
            self.assertEqual(_opt(calls[0], "--summary-config"), str(summary))
            self.assertEqual(Path(_opt(calls[0], "--tasks-file")).name, "sandbox_su_free_compressing4.json")

            # nothink4k: the 4096-cap file, the primitive's default attempts, its own model dir.
            capture.write_text("")
            subprocess.run(["bash", str(CAPPED)], env={**env, "SUMMARIZER": "nothink4k"}, check=True,
                           stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-cap4k-sumnothink4k")
            self.assertEqual(_opt(calls[0], "--summary-config"), str(summary4k))
            self.assertEqual(Path(_opt(calls[0], "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")

            # An explicit R2_MODEL is kept; NOTHINK=1 with SUMMARIZER=nothink is refused.
            capture.write_text("")
            subprocess.run(["bash", str(CAPPED)], env={**env, "R2_MODEL": "qwen35b-smoke"}, check=True,
                           stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--r2-model"), "qwen35b-smoke")
            capture.write_text("")
            result = subprocess.run(["bash", str(CAPPED)], env={**env, "NOTHINK": "1"}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("redundant", result.stderr)
            self.assertEqual(capture.read_text(), "")

    def test_capped_pilot_fc_only4_section_keeps_its_own_list_and_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            summary4k = _sandbox_pilot_files(Path(tmp))
            env.update(RUN_EVAL="0", SUMMARIZER="nothink4k", SECTIONS="p100_fc_only4", N_TASKS="2", RUNS_PER_TASK="15")
            subprocess.run(["bash", str(CAPPED)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual([_opt(c, "--r2-cell").rsplit("-", 1)[1] for c in calls], ALL_ORDERS)
            for c in calls:
                self.assertEqual(_opt(c, "--r2-section"), "p100_fc_only4")
                self.assertEqual(_opt(c, "--r2-model"), "qwen35b-cap4k-sumnothink4k")
                self.assertEqual(Path(_opt(c, "--tasks-file")).name, "p100_qwen35b_fc_not_tr_su-free.json")
                self.assertEqual(_opt(c, "--n-tasks"), "2")
                self.assertEqual(_opt(c, "--runs-per-task"), "15")
                self.assertEqual(_opt(c, "--step-limit"), "400")        # the section's own limits
                self.assertEqual(_opt(c, "--agent-timeout"), "7200")
                self.assertEqual(_opt(c, "--max-workers"), "3")
                self.assertEqual(Path(_opt(c, "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")
                self.assertEqual(_opt(c, "--summary-config"), str(summary4k))
            # The majority sections still get the sandbox 4-task list by default.
            capture.write_text("")
            env.update(SECTIONS="p100_su_free_majority", N_TASKS="all")
            subprocess.run(["bash", str(CAPPED)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(Path(_opt(calls[0], "--tasks-file")).name, "sandbox_su_free_compressing4.json")
            self.assertNotIn("--n-tasks", calls[0])
            self.assertNotIn("--step-limit", calls[0])

    def test_sandbox_chain_runs_nothink4k_majority_then_fc_only2_eight_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            summary4k = _sandbox_pilot_files(Path(tmp))
            env.update(RUN_EVAL="0", WAIT_FOR_PATTERN="")
            subprocess.run(["bash", str(SANDBOX_CHAIN)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1 + len(ALL_ORDERS))
            step1, step2 = calls[0], calls[1:]
            self.assertEqual((_opt(step1, "--r2-section"), _opt(step1, "--r2-cell"), _opt(step1, "--runs-per-task")),
                             ("p100_su_free_majority", "d05__b15k__adaptive-prefix3-sss", "15"))
            self.assertEqual(Path(_opt(step1, "--tasks-file")).name, "sandbox_su_free_compressing4.json")
            self.assertEqual([_opt(c, "--r2-cell").rsplit("-", 1)[1] for c in step2], ALL_ORDERS)
            for c in step2:
                self.assertEqual(_opt(c, "--r2-section"), "p100_fc_only4")
                self.assertEqual(Path(_opt(c, "--tasks-file")).name, "p100_qwen35b_fc_not_tr_su-free.json")
                self.assertEqual((_opt(c, "--n-tasks"), _opt(c, "--runs-per-task")), ("2", "15"))
            for c in calls:
                self.assertEqual(_opt(c, "--r2-model"), "qwen35b-cap4k-sumnothink4k")
                self.assertEqual(_opt(c, "--summary-config"), str(summary4k))
                self.assertEqual(Path(_opt(c, "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")
            # SKIP_STEP1 and the step-2 overrides.
            capture.write_text("")
            env.update(SKIP_STEP1="1", PATTERNS_STEP2="tts sst", RUNS_PER_TASK_STEP2="3", N_TASKS_STEP2="1")
            subprocess.run(["bash", str(SANDBOX_CHAIN)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual([_opt(c, "--r2-cell").rsplit("-", 1)[1] for c in calls], ["tts", "sst"])
            self.assertEqual([(_opt(c, "--n-tasks"), _opt(c, "--runs-per-task")) for c in calls], [("1", "3")] * 2)
            # SECTIONS / PATTERNS belong to the chain.
            capture.write_text("")
            result = subprocess.run(["bash", str(SANDBOX_CHAIN)], env={**env, "PATTERNS": "sss"}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(capture.read_text(), "")

    def test_majority_uniform_chain_runs_su_free_section_then_tr_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            subprocess.run(["bash", str(CHAIN)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual([(_opt(c, "--r2-section"), _opt(c, "--r2-cell"), "--eval-only" in c) for c in calls], [
                ("p100_su_free_majority", "d05__b15k__adaptive-prefix3-sss", False),
                ("p100_su_free_majority", "d05__b15k__adaptive-prefix3-sss", True),
                ("p100_tr_majority", "d05__b15k__adaptive-prefix3-ttt", False),
                ("p100_tr_majority", "d05__b15k__adaptive-prefix3-ttt", True),
            ])
            for c in calls:
                self.assertEqual(_opt(c, "--r2-model"), "qwen35b")
                self.assertEqual(_opt(c, "--n-tasks"), "5")
                self.assertEqual(_opt(c, "--runs-per-task"), "15")
            # One log, owned by the chain, holding both sections' output.
            logs = sorted((Path(tmp) / "logs/experiments").glob("r2_sb_majority_uniform_qwen35b_*.log"))
            self.assertEqual(len(logs), 1)
            text = logs[0].read_text()
            self.assertIn("section p100_su_free_majority", text)
            self.assertIn("section p100_tr_majority", text)
            self.assertIn("p100_tr_majority/qwen35b/d05__b15k__adaptive-prefix3-ttt", text)
            self.assertFalse(list((Path(tmp) / "logs/experiments").glob("r2_sb_p100_*_majority_qwen35b_*.log")))

            # Overrides pass through; the per-section settings are refused.
            capture.write_text("")
            env.update(N_TASKS="2", RUNS_PER_TASK="1", RUN_EVAL="0", R2_MODEL="qwen35b-smoke",
                       SECTIONS="p100_tr_majority")
            subprocess.run(["bash", str(CHAIN)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual((_opt(calls[0], "--r2-section"), _opt(calls[0], "--r2-model"),
                              _opt(calls[0], "--n-tasks"), _opt(calls[0], "--runs-per-task")),
                             ("p100_tr_majority", "qwen35b-smoke", "2", "1"))
            for bad in ({"PATTERNS": "sss"}, {"SECTIONS": "p30s_never7"}):
                capture.write_text("")
                result = subprocess.run(["bash", str(CHAIN)], env={**env, **bad}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, bad)
                self.assertEqual(capture.read_text(), "")

    def test_albus_swe_profile_defaults_to_eight_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, env = _sandbox(Path(tmp))
            env.update(PATTERNS="sts", RUN_EVAL="0")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--max-workers"), "16")      # Dobby default

            capture.write_text("")
            env.update(AGENTCTX_PROFILE="albus-swe")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--max-workers"), "8")

            capture.write_text("")
            env.update(MAX_WORKERS="3")                                   # explicit value wins
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual(_opt(calls[0], "--max-workers"), "3")
            del env["MAX_WORKERS"]

            capture.write_text("")
            env.update(AGENTCTX_PROFILE="albus")                          # unknown profile
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown AGENTCTX_PROFILE", result.stderr)
            self.assertEqual(capture.read_text(), "")

            # The chain passes the profile through to both sections.
            capture.write_text("")
            env.update(AGENTCTX_PROFILE="albus-swe")
            del env["PATTERNS"]
            subprocess.run(["bash", str(CHAIN)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual([_opt(c, "--max-workers") for c in calls], ["8", "8"])

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
            env.update(PATTERNS="sts", STEP_LIMIT="350", AGENT_TIMEOUT="6000")
            subprocess.run(["bash", str(LAUNCHER)], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertEqual((_opt(calls[0], "--step-limit"), _opt(calls[0], "--agent-timeout")),
                             ("350", "6000"))
            env.update(AGENT_TIMEOUT="2h")
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("AGENT_TIMEOUT", result.stderr)
            del env["STEP_LIMIT"], env["AGENT_TIMEOUT"]

            capture.write_text("")
            env.update(PATTERNS="tts ttx")   # no such schedule
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ttx.json", result.stderr)
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


ISO_TASKS = ["django__django-11299", "scikit-learn__scikit-learn-25102"]


def _isolated_sandbox(tmp: Path) -> tuple[Path, Path, dict]:
    """Fakes for the isolated driver: a runner that records result rows, a server
    start/stop pair keyed on the pid file, a docker CLI over a state file and a
    curl that answers only while the pid file exists; all log to EVENTS."""
    capture, env = _sandbox(tmp)
    _sandbox_pilot_files(tmp)
    (tmp / "task_lists/swe_verified/sandbox_su_free_compressing4.json").write_text(json.dumps(
        [{"instance_id": instance, "repo": instance.split("__")[0]} for instance in ISO_TASKS]))
    events, state = tmp / "events.log", tmp / "containers.txt"
    runner = tmp / "fake-runner"
    runner.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import json, os, sys
        argv = sys.argv[1:]
        with open(os.environ["CAPTURE"], "a") as f:
            f.write(json.dumps(argv + ["--fake-summary-attempts", os.environ.get("MSWEA_SUMMARY_MAX_ATTEMPTS", "")]) + "\\n")
        opt = lambda name: argv[argv.index(name) + 1]
        tasks = [t["instance_id"] for t in json.load(open(opt("--tasks-file")))]
        with open(os.environ["EVENTS"], "a") as f:
            f.write(("eval " if "--eval-only" in argv else "run ") + " ".join(tasks) + " r" + opt("--runs-per-task") + "\\n")
        if "--eval-only" in argv:
            sys.exit(0)
        cell = os.path.join(os.environ["AGENTCTX_WS"], "data/r2/swebench", opt("--r2-section"), opt("--r2-model"), opt("--r2-cell"))
        os.makedirs(cell, exist_ok=True)
        path = os.path.join(cell, "experiment_results.json")
        rows = json.load(open(path)) if os.path.exists(path) else []
        keys = {r["key"] for r in rows}
        cond = opt("--conditions")   # adaptive (capped pilot) or the plain condition (run_r2_swe_p30s.sh)
        for t in tasks:
            for r in range(1, int(opt("--runs-per-task")) + 1):
                if f"{t}__{cond}__r{r}" not in keys:
                    rows.append({"key": f"{t}__{cond}__r{r}", "instance_id": t, "run_num": r})
        json.dump(rows, open(path, "w"))
        """))
    start, stop, docker, curl = tmp / "fake-vllm-start.sh", tmp / "fake-vllm-stop.sh", tmp / "docker", tmp / "curl"
    start.write_text('#!/bin/sh\nmkdir -p "$(dirname "$VLLM_PID_FILE")"\n'
                     '[ ! -f "$VLLM_PID_FILE" ] || { echo "server already running" >&2; exit 1; }\n'
                     'echo $PPID > "$VLLM_PID_FILE"\necho start >> "$EVENTS"\n')
    stop.write_text('#!/bin/sh\nrm -f "$1"\necho stop >> "$EVENTS"\n')
    docker.write_text('#!/bin/sh\necho "docker $1 $2" >> "$EVENTS"\n'
                      'case "$1" in\n  ps) cat "$STATE" 2>/dev/null ;;\n  rm) : > "$STATE" ;;\nesac\n')
    curl.write_text('#!/bin/sh\nfor a; do last=$a; done\n'
                    'case " $* " in *" -X POST "*) echo "curl POST $last" >> "$EVENTS" ;; esac\n'
                    '[ "${CURL_ALWAYS_OK:-0}" = 1 ] && exit 0\n[ -f "$VLLM_PID_FILE" ] && exit 0\nexit 7\n')
    for p in (runner, start, stop, docker, curl):
        p.chmod(0o755)
    state.write_text("abc minisweagent-dead Exited (137) 2 days ago\ndef buildx_buildkit_default Created\n")
    env.update(PYTHON=str(runner), EVENTS=str(events), STATE=str(state),
               VLLM_PID_FILE=str(tmp / "logs/servers/vllm_qwen35_a3b_noprefixcache.pid"),
               VLLM_START_SCRIPT=str(start), VLLM_STOP_SCRIPT=str(stop), BUSY_PATTERN="", SUMMARIZER="nothink4k")
    return capture, events, env


class SandboxIsolatedTests(unittest.TestCase):
    def test_one_fresh_server_and_container_purge_per_pending_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            model = "qwen35b-cap4k-sumnothink4k-iso"
            cell = Path(tmp) / "data/r2/swebench/p100_su_free_majority" / model / "d05__b15k__adaptive-prefix3-sss"
            cell.mkdir(parents=True)
            (cell / "experiment_results.json").write_text(json.dumps([{"key": f"{ISO_TASKS[0]}__adaptive__r1"}]))
            env.update(RUNS_PER_TASK="2")
            # DRY_RUN: the plan only; nothing started, listed or removed.
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "DRY_RUN": "1"}, check=True,
                                    capture_output=True, text=True)
            self.assertIn(f"recorded  p100_su_free_majority sss {ISO_TASKS[0]} r1", result.stdout)
            self.assertEqual(result.stdout.count("pending   "), 3)
            self.assertFalse(events.exists())
            self.assertFalse(capture.exists())

            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            lines = events.read_text().splitlines()
            # Initial clean-up removes the leftovers; afterwards every purge finds nothing.
            self.assertEqual(lines[:3], ["docker ps -a", "docker rm -f", "docker ps -a"])
            self.assertEqual(lines.count("docker rm -f"), 1)
            self.assertEqual(lines.count("docker ps -a"), 2 + 3 + 1)   # initial, one per cycle, final (exit trap)
            self.assertEqual(Path(env["STATE"]).read_text(), "")
            expected = []
            for instance, r in [(ISO_TASKS[0], 2), (ISO_TASKS[1], 1), (ISO_TASKS[1], 2)]:
                expected += ["start", f"run {instance} r{r}", f"eval {instance} r{r}", "stop", "docker ps -a"]
            self.assertEqual(lines[3:], expected + ["docker ps -a"])
            self.assertFalse(Path(env["VLLM_PID_FILE"]).exists())
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            runs = [c for c in calls if "--eval-only" not in c]
            self.assertEqual(len(calls), 6)
            self.assertEqual([_opt(c, "--runs-per-task") for c in runs], ["2", "1", "2"])
            for c in calls:
                self.assertEqual((_opt(c, "--max-workers"), _opt(c, "--r2-model"), _opt(c, "--r2-section")),
                                 ("1", model, "p100_su_free_majority"))
                self.assertEqual(_opt(c, "--r2-cell"), "d05__b15k__adaptive-prefix3-sss")
                self.assertEqual(Path(_opt(c, "--agent-config")).name, "config-qwen-vllm-cap4k.yaml")
                self.assertEqual(Path(_opt(c, "--summary-config")).name, "config-summary-qwen35-35b-nothink-4k.yaml")
                self.assertEqual(len(json.loads(Path(_opt(c, "--tasks-file")).read_text())), 1)
            rows = json.loads((cell / "experiment_results.json").read_text())
            self.assertEqual(sorted(r["key"] for r in rows),
                             sorted(f"{t}__adaptive__r{r}" for t in ISO_TASKS for r in (1, 2)))
            # A second launch finds everything recorded: clean-up only, no server.
            events.unlink()
            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(events.read_text().splitlines(), ["docker ps -a", "docker ps -a"])

    def test_refusals_leave_the_machine_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            for extra in [{"MAX_WORKERS": "3"}, {"PURGE_CONTAINERS": "some"}, {"SECTIONS": "p30s_never7"},
                          {"CURL_ALWAYS_OK": "1"},   # a server answers but no sandbox pid file: not ours to stop
                          {"QWEN_AGENT_CONFIG": str(Path(tmp) / "configs/config-qwen-vllm-cap4k.yaml")}]:
                result = subprocess.run(["bash", str(ISOLATED)], env={**env, **extra}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, (extra, result.stderr))
                self.assertFalse(events.exists(), extra)
                self.assertFalse(capture.exists(), extra)
            # Explicit R2_MODEL and an empty suffix are kept verbatim / resume the pilot's own dir.
            env.pop("SUMMARIZER")   # the driver's own default is the 2048-cap nothink recipe
            for extra, model, summary, attempts in [
                    ({}, "qwen35b-cap4k-sumnothink-iso", "config-summary-qwen35-35b-nothink.yaml", "5"),
                    ({"SUMMARY_MAX_ATTEMPTS": "2"}, "qwen35b-cap4k-sumnothink-iso", "config-summary-qwen35-35b-nothink.yaml", "2"),
                    ({"SUMMARIZER": "nothink4k"}, "qwen35b-cap4k-sumnothink4k-iso", "config-summary-qwen35-35b-nothink-4k.yaml", "5"),
                    ({"R2_MODEL": "qwen35b-iso-check"}, "qwen35b-iso-check", "config-summary-qwen35-35b-nothink.yaml", "5"),
                    ({"ISO_SUFFIX": ""}, "qwen35b-cap4k-sumnothink", "config-summary-qwen35-35b-nothink.yaml", "5"),
                    ({"SUMMARIZER": "agent"}, "qwen35b-cap4k-iso", None, "")]:
                result = subprocess.run(["bash", str(ISOLATED)], env={**env, **extra, "DRY_RUN": "1"},
                                        check=True, capture_output=True, text=True)
                self.assertIn(f"R2_MODEL={model} ", result.stdout, extra)
                self.assertIn(f"SUMMARIZER={extra.get('SUMMARIZER', 'nothink')} ", result.stdout, extra)
                # The recipe reaches the runner: one real cycle with the single-run plan (fresh data tree each time).
                if capture.exists():
                    capture.unlink()
                shutil.rmtree(Path(tmp) / "data", ignore_errors=True)
                subprocess.run(["bash", str(ISOLATED)], env={**env, **extra, "RUNS_PER_TASK": "1", "N_TASKS": "1"},
                               check=True, stdout=subprocess.DEVNULL)
                call = json.loads(capture.read_text().splitlines()[0])
                self.assertEqual(_opt(call, "--r2-model"), model)
                self.assertEqual(Path(_opt(call, "--summary-config")).name if "--summary-config" in call else None, summary)
                self.assertEqual(_opt(call, "--fake-summary-attempts"), attempts, extra)

    def test_inner_p30s_runs_plain_cells_one_run_per_server(self):
        """INNER=p30s: the plan is (section, cell spec, task, run) over run_r2_swe_p30s.sh,
        keys use the condition name, run-major order, and every pending run gets its
        own server start/stop and container purge."""
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            env.pop("SUMMARIZER")
            (Path(tmp) / "configs/config-devstral-check.yaml").write_text('model:\n  api_base: "http://localhost:8000/v1"\n')
            cells = "di__b15k__su-free:summarization-free:0.5 d05__b15k__tr:truncation:0.5"
            env.update(INNER="p30s", SECTIONS="p30s", CELLS=cells, R2_MODEL="devstral-iso-check",
                       TASKS_FILE=str(Path(tmp) / "task_lists/swe_verified/sandbox_su_free_compressing4.json"),
                       RUNS_PER_TASK="2", CYCLE_ORDER="run-major", QWEN_TAG="devstral-check",
                       QWEN_AGENT_CONFIG=str(Path(tmp) / "configs/config-devstral-check.yaml"),
                       VLLM_PID_FILE=str(Path(tmp) / "logs/servers/vllm_devstral_check.pid"))
            # Capped-pilot settings and malformed cells are refused before anything starts.
            for extra in [{"SUMMARIZER": "agent"}, {"PATTERNS": "sss"}, {"SECTIONS": "p100_fc_only4"},
                          {"CELLS": "di__b15k__su-free:summarization-free"}, {"CELLS": "di__bX__su-free:summarization-free:0.5"},
                          {"R2_MODEL": ""}, {"CYCLE_ORDER": "sideways"}]:
                result = subprocess.run(["bash", str(ISOLATED)], env={**env, **extra}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, (extra, result.stderr))
                self.assertFalse(events.exists(), extra)
            cell = Path(tmp) / "data/r2/swebench/p30s/devstral-iso-check/di__b15k__su-free"
            cell.mkdir(parents=True)
            (cell / "experiment_results.json").write_text(json.dumps([{"key": f"{ISO_TASKS[0]}__summarization-free__r1"}]))
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "DRY_RUN": "1"}, check=True,
                                    capture_output=True, text=True)
            plan = [line.split() for line in result.stdout.splitlines() if line.startswith(("  recorded", "  pending"))]
            su, tr = cells.split()
            self.assertEqual(plan, [
                ["recorded", "p30s", su, ISO_TASKS[0], "r1"], ["pending", "p30s", su, ISO_TASKS[1], "r1"],
                ["pending", "p30s", su, ISO_TASKS[0], "r2"], ["pending", "p30s", su, ISO_TASKS[1], "r2"],
                ["pending", "p30s", tr, ISO_TASKS[0], "r1"], ["pending", "p30s", tr, ISO_TASKS[1], "r1"],
                ["pending", "p30s", tr, ISO_TASKS[0], "r2"], ["pending", "p30s", tr, ISO_TASKS[1], "r2"]])
            self.assertIn("inner: p30s | server: per-run | order: run-major", result.stdout)
            self.assertFalse(events.exists())
            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            log = events.read_text().splitlines()
            self.assertEqual(log.count("start"), 7)
            self.assertEqual(log.count("stop"), 7)
            self.assertEqual([l for l in log if l.startswith("run ")],
                             [f"run {ISO_TASKS[1]} r1", f"run {ISO_TASKS[0]} r2", f"run {ISO_TASKS[1]} r2",
                              f"run {ISO_TASKS[0]} r1", f"run {ISO_TASKS[1]} r1", f"run {ISO_TASKS[0]} r2", f"run {ISO_TASKS[1]} r2"])
            self.assertEqual(len([l for l in log if l.startswith("eval ")]), 7)
            # Every run is a server start followed by the run, its eval, a stop and a purge listing.
            first = log.index("start")
            self.assertEqual(log[first:first + 5], ["start", f"run {ISO_TASKS[1]} r1", f"eval {ISO_TASKS[1]} r1", "stop", "docker ps -a"])
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            runs = [c for c in calls if "--eval-only" not in c]
            self.assertEqual(len(runs), 7)
            for c in runs:
                self.assertEqual(_opt(c, "--r2-section"), "p30s")
                self.assertEqual(_opt(c, "--r2-model"), "devstral-iso-check")
                self.assertEqual(_opt(c, "--model-tag"), "devstral-check")
                self.assertEqual(Path(_opt(c, "--agent-config")).name, "config-devstral-check.yaml")
                self.assertEqual(_opt(c, "--max-workers"), "1")
                self.assertNotIn("--n-tasks", c)
                self.assertNotIn("--summary-config", c)
            self.assertEqual([(_opt(c, "--r2-cell"), _opt(c, "--conditions"), _opt(c, "--runs-per-task")) for c in runs],
                             [("di__b15k__su-free", "summarization-free", "1"), ("di__b15k__su-free", "summarization-free", "2"),
                              ("di__b15k__su-free", "summarization-free", "2"), ("d05__b15k__tr", "truncation", "1"),
                              ("d05__b15k__tr", "truncation", "1"), ("d05__b15k__tr", "truncation", "2"),
                              ("d05__b15k__tr", "truncation", "2")])
            for name, cond in [("di__b15k__su-free", "summarization-free"), ("d05__b15k__tr", "truncation")]:
                rows = json.loads((cell.parent / name / "experiment_results.json").read_text())
                self.assertEqual(sorted(r["key"] for r in rows), sorted(f"{t}__{cond}__r{r}" for t in ISO_TASKS for r in (1, 2)))
            # Resume: everything recorded, so clean-up only and no server.
            events.unlink()
            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(events.read_text().splitlines(), ["docker ps -a", "docker ps -a"])

    def test_persistent_server_is_started_once_and_runs_stay_serial(self):
        """SERVER_LIFECYCLE=persistent: one server start before the first cycle and one
        stop on exit; every cycle still runs one key with MAX_WORKERS=1 and purges the
        containers; a server that died between cycles stops the driver."""
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            env.update(RUNS_PER_TASK="2", SERVER_LIFECYCLE="persistent")
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "SERVER_LIFECYCLE": "forever"},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(events.exists())
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "DRY_RUN": "1"}, check=True,
                                    capture_output=True, text=True)
            self.assertIn("server: persistent", result.stdout)
            self.assertFalse(events.exists())
            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            log = events.read_text().splitlines()
            self.assertEqual(log.count("start"), 1)
            self.assertEqual(log.count("stop"), 1)
            runs = [l for l in log if l.startswith("run ")]
            self.assertEqual(len(runs), 4)
            self.assertEqual(len([l for l in log if l.startswith("eval ")]), 4)
            self.assertLess(log.index("start"), log.index(runs[0]))
            self.assertGreater(log.index("stop"), log.index(runs[-1]))
            # Between two runs: eval, then a purge listing, then the next run - no server event.
            i, j = log.index(runs[0]), log.index(runs[1])
            self.assertEqual(log[i + 1:j], [runs[0].replace("run ", "eval "), "docker ps -a"])
            self.assertFalse(Path(env["VLLM_PID_FILE"]).exists())
            calls = [json.loads(line) for line in capture.read_text().splitlines() if "--eval-only" not in json.loads(line)]
            self.assertEqual({_opt(c, "--max-workers") for c in calls}, {"1"})
            self.assertEqual([len(json.load(open(_opt(c, "--tasks-file")))) for c in calls], [1, 1, 1, 1])
            # A server that disappears between cycles: the driver stops instead of restarting it.
            shutil.rmtree(Path(tmp) / "data", ignore_errors=True)
            events.unlink()
            stop = Path(env["VLLM_STOP_SCRIPT"])
            stop.write_text('#!/bin/sh\nrm -f "$1"\necho stop >> "$EVENTS"\n')
            runner = Path(env["PYTHON"])
            runner.write_text(runner.read_text().replace("import json, os, sys\n",
                              "import json, os, sys\n"
                              "if os.path.exists(os.environ['VLLM_PID_FILE']): os.remove(os.environ['VLLM_PID_FILE'])  # the server dies during the run\n"))
            result = subprocess.run(["bash", str(ISOLATED)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            # The driver owns its log here (no AGENTCTX_LOG_FILE), so stderr is folded into stdout.
            self.assertIn("never restarted mid-plan", result.stdout + result.stderr)
            log = events.read_text().splitlines()
            self.assertEqual(log.count("start"), 1)
            self.assertEqual(len([l for l in log if l.startswith("run ")]), 1)

    def test_prefix_cache_flush_after_every_cycle_on_the_persistent_server(self):
        """KV_FLUSH=prefix-cache: refused without the persistent server; with it, one
        POST /reset_prefix_cache after every cycle's purge, on the same single server."""
        with tempfile.TemporaryDirectory() as tmp:
            capture, events, env = _isolated_sandbox(Path(tmp))
            env.update(RUNS_PER_TASK="2", N_TASKS="1", KV_FLUSH="prefix-cache")
            for extra in [{}, {"SERVER_LIFECYCLE": "per-run"}, {"SERVER_LIFECYCLE": "persistent", "KV_FLUSH": "all"}]:
                result = subprocess.run(["bash", str(ISOLATED)], env={**env, **extra}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, (extra, result.stderr))
                self.assertFalse(events.exists(), extra)
            env.update(SERVER_LIFECYCLE="persistent")
            result = subprocess.run(["bash", str(ISOLATED)], env={**env, "DRY_RUN": "1"}, check=True,
                                    capture_output=True, text=True)
            self.assertIn("server: persistent (flush: prefix-cache)", result.stdout)
            subprocess.run(["bash", str(ISOLATED)], env=env, check=True, stdout=subprocess.DEVNULL)
            log = events.read_text().splitlines()
            self.assertEqual(log.count("start"), 1)
            self.assertEqual(log.count("stop"), 1)
            runs = [l for l in log if l.startswith("run ")]
            self.assertEqual(len(runs), 2)
            flushes = [l for l in log if l.startswith("curl POST ")]
            self.assertEqual(flushes, ["curl POST http://localhost:8000/reset_prefix_cache"] * 2)
            # Each cycle: run, eval, purge listing, flush; the server is not touched.
            i = log.index(runs[0])
            self.assertEqual(log[i:i + 5], [runs[0], runs[0].replace("run ", "eval "), "docker ps -a",
                                            "curl POST http://localhost:8000/reset_prefix_cache", runs[1]])
            # A failing reset stops the driver before the next run.
            shutil.rmtree(Path(tmp) / "data", ignore_errors=True)
            events.unlink()
            curl = Path(tmp) / "curl"
            curl.write_text(curl.read_text().replace('echo "curl POST $last" >> "$EVENTS" ;;', 'echo "curl POST $last" >> "$EVENTS"; exit 22 ;;'))
            result = subprocess.run(["bash", str(ISOLATED)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("reset_prefix_cache failed", result.stdout + result.stderr)
            log = events.read_text().splitlines()
            self.assertEqual(len([l for l in log if l.startswith("run ")]), 1)
            self.assertEqual(log.count("stop"), 1)


if __name__ == "__main__":
    unittest.main()
