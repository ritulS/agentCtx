"""Unit tests for Terminal-Bench verdict handling.

Run with either interpreter:

    venv-harbor/bin/python -m unittest scripts.bench_adapters.test_tb_verdict
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bench_adapters import tb_verdict  # noqa: E402
from scripts.bench_adapters.terminal_bench import TerminalBench  # noqa: E402


def harbor_result(task, *, reward=None, exception=None, message=None, trial_id="t1",
                  finished="2026-09-11T00:00:00Z"):
    result = {
        "id": trial_id, "task_name": task, "trial_name": f"{task}__{trial_id}",
        "started_at": "2026-09-11T00:00:00Z", "finished_at": finished,
        "exception_info": None, "verifier_result": None,
        "agent_execution": {"started_at": "2026-09-11T00:00:00Z", "finished_at": finished},
    }
    if reward is not None:
        result["verifier_result"] = {"rewards": {"reward": reward}}
    if exception:
        result["exception_info"] = {"exception_type": exception, "exception_message": message or exception}
    return result


def write_trial(job_dir: Path, result: dict, name: str | None = None) -> Path:
    trial_dir = job_dir / (name or result["trial_name"])
    (trial_dir / "agent").mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(json.dumps(result))
    (trial_dir / "agent" / "exit_info.json").write_text(json.dumps({"exit_status": "Submitted", "n_calls": 3}))
    (trial_dir / "agent" / "token_log.json").write_text(json.dumps({"total_tokens": 10}))
    return trial_dir


class VerdictFieldsTest(unittest.TestCase):
    def test_reward_gives_boolean_resolved(self):
        self.assertEqual(tb_verdict.verdict_fields(harbor_result("a", reward=1.0))["resolved"], True)
        fields = tb_verdict.verdict_fields(harbor_result("a", reward=0.0))
        self.assertEqual(fields["resolved"], False)
        self.assertEqual(fields["verdict_source"], "verifier")

    def test_missing_reward_is_unverified_not_false(self):
        fields = tb_verdict.verdict_fields(
            harbor_result("a", exception="VerifierTimeoutError", message="Verifier execution timed out\nmore"))
        self.assertIsNone(fields["resolved"])
        self.assertIsNone(fields["reward"])
        self.assertEqual(fields["verdict_source"], "none")
        self.assertEqual(fields["harbor_exception"], "VerifierTimeoutError")
        self.assertEqual(fields["harbor_exception_message"], "Verifier execution timed out")

    def test_agent_timeout_with_reward_keeps_verdict(self):
        fields = tb_verdict.verdict_fields(harbor_result("a", reward=1.0, exception="AgentTimeoutError"))
        self.assertEqual(fields["resolved"], True)
        self.assertEqual(fields["harbor_exception"], "AgentTimeoutError")

    def test_namespaced_task_name(self):
        self.assertEqual(tb_verdict.task_name({"task_name": "terminal-bench/caffe-cifar-10"}), "caffe-cifar-10")


class RewardFileRecoveryTest(unittest.TestCase):
    def make_trial(self, tmp: Path, reward: str | None, stdout: str) -> Path:
        trial = tmp / "task__abc"
        (trial / "verifier").mkdir(parents=True)
        if reward is not None:
            (trial / "verifier" / "reward.txt").write_text(reward)
        (trial / "verifier" / "test-stdout.txt").write_text(stdout)
        return trial

    def test_verifier_timeout_with_complete_tests_is_graded(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial = self.make_trial(Path(tmp), "1\n", "PASSED a\n===== 6 passed in 83.07s (0:01:23) =====\n")
            result = harbor_result("task", exception="VerifierTimeoutError", message="Verifier execution timed out")
            fields = tb_verdict.trial_verdict(result, trial)
            self.assertEqual((fields["resolved"], fields["reward"], fields["verdict_source"]),
                             (True, 1.0, "verifier_reward_file"))
            self.assertEqual(fields["harbor_exception"], "VerifierTimeoutError")
            self.assertIn("6 passed", fields["reward_file"]["pytest_summary"])
            # trial_uri resolution works too
            result["trial_uri"] = trial.as_uri()
            self.assertEqual(tb_verdict.trial_verdict(result)["verdict_source"], "verifier_reward_file")

    def test_incomplete_or_missing_reward_stays_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = harbor_result("task", exception="VerifierTimeoutError")
            cut = self.make_trial(Path(tmp) / "a", "0", "Collecting torch\n")          # no summary line
            self.assertIsNone(tb_verdict.trial_verdict(result, cut)["resolved"])
            none = self.make_trial(Path(tmp) / "b", None, "===== 2 passed in 1.0s =====\n")
            self.assertIsNone(tb_verdict.trial_verdict(result, none)["resolved"])
            other = self.make_trial(Path(tmp) / "c", "1", "===== 2 passed in 1.0s =====\n")
            # Only verifier timeouts are recovered; other exceptions keep None.
            self.assertIsNone(tb_verdict.trial_verdict(harbor_result("task", exception="AddTestsDirError"), other)["resolved"])

    def test_verifier_timeout_multiplier_from_env(self):
        with mock.patch.dict(os.environ, {"TB_VERIFIER_TIMEOUT_MULTIPLIER": "5"}):
            self.assertEqual(tb_verdict.verifier_timeout_args(), ["--verifier-timeout-multiplier", "5.0"])
        self.assertEqual(tb_verdict.verifier_timeout_args(2.5), ["--verifier-timeout-multiplier", "2.5"])
        with self.assertRaises(ValueError):
            tb_verdict.verifier_timeout_multiplier(0)


class RetryPolicyTest(unittest.TestCase):
    def test_infrastructure_exceptions_are_retryable(self):
        self.assertTrue(tb_verdict.is_retryable("AddTestsDirError", None))
        self.assertTrue(tb_verdict.is_retryable("RuntimeError", "Docker compose command failed for environment x"))
        self.assertFalse(tb_verdict.is_retryable("RuntimeError", "ValueError: Encountered text corresponding to disallowed special token"))
        self.assertFalse(tb_verdict.is_retryable("VerifierTimeoutError", None))
        self.assertFalse(tb_verdict.is_retryable("AgentTimeoutError", None))
        self.assertFalse(tb_verdict.is_retryable(None, None))

    def test_needs_rerun_only_without_verdict(self):
        self.assertFalse(tb_verdict.needs_rerun({"resolved": False, "reward": 0.0, "harbor_exception": "AddTestsDirError"}))
        self.assertTrue(tb_verdict.needs_rerun({"resolved": None, "reward": None, "harbor_exception": "AddTestsDirError"}))
        self.assertFalse(tb_verdict.needs_rerun({"resolved": None, "reward": None, "harbor_exception": "VerifierTimeoutError"}))

    def test_env_override_adds_and_removes(self):
        with mock.patch.dict(os.environ, {"TB_RETRY_EXCEPTIONS": "VerifierTimeoutError, -CancelledError"}):
            names = tb_verdict.retry_exceptions_from_env()
        self.assertIn("VerifierTimeoutError", names)
        self.assertNotIn("CancelledError", names)
        self.assertIn("AddTestsDirError", names)

    def test_verifier_env_args(self):
        with mock.patch.dict(os.environ, {"TB_VERIFIER_THREADS": "4"}):
            args = tb_verdict.verifier_env_args()
        self.assertEqual(args[:2], ["--verifier-env", "OMP_NUM_THREADS=4"])
        self.assertEqual(len(args), 2 * len(tb_verdict.THREAD_ENV_KEYS))


class SelectTrialsTest(unittest.TestCase):
    def test_prefers_verdict_then_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            write_trial(job, harbor_result("a", exception="CancelledError", trial_id="z", finished="2026-09-11T09:00:00Z"))
            with_verdict = write_trial(job, harbor_result("a", reward=1.0, trial_id="m", finished="2026-09-11T08:00:00Z"))
            write_trial(job, harbor_result("b", reward=0.0, trial_id="b1", finished="2026-09-11T08:00:00Z"))
            later_b = write_trial(job, harbor_result("b", reward=0.0, trial_id="b2", finished="2026-09-11T09:00:00Z"))
            write_trial(job, harbor_result("c", reward=1.0, trial_id="c1"))
            selected, duplicates = tb_verdict.select_trials(job, ["a", "b"])
            self.assertEqual(selected["a"].parent, with_verdict)
            self.assertEqual(selected["b"].parent, later_b)
            self.assertNotIn("c", selected)
            self.assertEqual(sorted(duplicates), ["a", "b"])


class RunExperimentsTest(unittest.TestCase):
    """The attempt loop re-runs only retryable unverified rows and never drops rows."""

    def make_adapter(self, tmp: Path) -> TerminalBench:
        adapter = TerminalBench(tmp, "model", tmp / "results")
        adapter._validate_runtime = lambda config: None
        adapter._load_model_config = lambda path: ("m", "http://x")
        return adapter

    def test_attempt_loop(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"TB_MAX_BATCH_ATTEMPTS": "3"}):
            adapter = self.make_adapter(Path(tmp))
            calls = []
            outcomes = [
                # attempt 1: a unverified (infra), b never produced, c verified
                {"a": ("AddTestsDirError", None), "c": (None, 1.0)},
                # attempt 2: a verified, b unverified for a non-retryable reason
                {"a": (None, 0.0), "b": ("VerifierTimeoutError", None)},
            ]

            def fake_batch(*, task_names, condition, run_num, attempt=1, **kwargs):
                calls.append((attempt, sorted(task_names)))
                rows = []
                for task, (exception, reward) in outcomes[attempt - 1].items():
                    if task not in task_names:
                        continue
                    result = harbor_result(task, reward=reward, exception=exception, trial_id=f"{task}{attempt}")
                    row = {"key": adapter._run_key(task, condition["condition"], run_num), "instance_id": task,
                           "condition": condition["condition"], "run_num": run_num, "timestamp": "t",
                           "attempts": 1, "superseded_dir": None, **tb_verdict.verdict_fields(result)}
                    rows.append(row)
                return rows

            adapter._run_batch = fake_batch
            saves = []
            results = adapter.run_experiments(
                tasks=[{"instance_id": t} for t in ("a", "b", "c")],
                conditions=[{"condition": "truncation", "primitive": "truncation", "budget": 1000}],
                runs_per_task=1, existing_results=[], save=lambda rows: saves.append(len(rows)),
                agent_config=Path(tmp) / "cfg.yaml", step_limit=1, agent_timeout=1, max_workers=1,
                compression_ratio=0.5,
            )
            self.assertEqual(calls, [(1, ["a", "b", "c"]), (2, ["a", "b"])])
            by_task = {row["instance_id"]: row for row in results}
            self.assertEqual(by_task["a"]["resolved"], False)
            self.assertEqual(by_task["a"]["attempts"], 2)
            self.assertEqual(by_task["a"]["previous_attempts"][0]["harbor_exception"], "AddTestsDirError")
            self.assertIsNone(by_task["b"]["resolved"])          # kept, not turned into False
            self.assertEqual(by_task["b"]["harbor_exception"], "VerifierTimeoutError")
            self.assertEqual(by_task["c"]["resolved"], True)
            self.assertEqual(len(results), 3)
            self.assertEqual(saves, [2, 3])                        # saved after every batch

    def test_batch_collects_finished_trials_when_harbor_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            condition = {"condition": "truncation", "primitive": "truncation", "budget": 1000}

            def fake_run(command, **kwargs):
                job_dir = Path(command[command.index("--jobs-dir") + 1]) / command[command.index("--job-name") + 1]
                write_trial(job_dir, harbor_result("a", reward=1.0, trial_id="a1"))   # b never finished
                return SimpleNamespace(returncode=1)

            with mock.patch("scripts.bench_adapters.terminal_bench.subprocess.run", side_effect=fake_run), \
                    mock.patch.dict(os.environ, {"TB_REAP_FINISHED_HARBOR": "0"}):
                rows = adapter._run_batch(task_names=["a", "b"], condition=condition, run_num=1,
                                          agent_config=Path(tmp) / "cfg", model_name="m", api_base="http://x",
                                          n_concurrent=1, compression_ratio=0.5)
            self.assertEqual([r["instance_id"] for r in rows], ["a"])
            self.assertEqual(rows[0]["resolved"], True)

    def test_batch_raises_when_harbor_fails_before_any_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            condition = {"condition": "truncation", "primitive": "truncation", "budget": 1000}
            with mock.patch("scripts.bench_adapters.terminal_bench.subprocess.run",
                            return_value=SimpleNamespace(returncode=2)), \
                    mock.patch.dict(os.environ, {"TB_REAP_FINISHED_HARBOR": "0"}), \
                    self.assertRaises(subprocess.CalledProcessError):
                adapter._run_batch(task_names=["a"], condition=condition, run_num=1,
                                   agent_config=Path(tmp) / "cfg", model_name="m", api_base="http://x",
                                   n_concurrent=1, compression_ratio=0.5)

    def test_normalize_trial_recovers_reward_file_and_records_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"TB_VERIFIER_TIMEOUT_MULTIPLIER": "5"}):
            adapter = self.make_adapter(Path(tmp))
            condition = {"condition": "truncation", "primitive": "truncation", "budget": 1000}
            trial = write_trial(Path(tmp) / "job", harbor_result("a", exception="VerifierTimeoutError", trial_id="v1"))
            (trial / "verifier").mkdir()
            (trial / "verifier" / "reward.txt").write_text("0")
            (trial / "verifier" / "test-stdout.txt").write_text("FAILED x\n===== 1 failed, 5 passed in 83.86s =====\n")
            row = adapter._normalize_trial(trial, condition, 1, 0.5)
            self.assertEqual((row["resolved"], row["reward"], row["verdict_source"]), (False, 0.0, "verifier_reward_file"))
            self.assertEqual(row["verifier_timeout_multiplier"], 5.0)
            self.assertFalse(tb_verdict.needs_rerun(row))

    def test_normalize_trial_supersedes_previous_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self.make_adapter(Path(tmp))
            condition = {"condition": "truncation", "primitive": "truncation", "budget": 1000}
            first = write_trial(Path(tmp) / "job1", harbor_result("a", exception="AddTestsDirError", trial_id="one"))
            row1 = adapter._normalize_trial(first, condition, 1, 0.5)
            self.assertIsNone(row1["resolved"])
            self.assertIsNone(row1["superseded_dir"])
            second = write_trial(Path(tmp) / "job2", harbor_result("a", reward=1.0, trial_id="two"))
            row2 = adapter._normalize_trial(second, condition, 1, 0.5)
            self.assertEqual(row2["resolved"], True)
            self.assertEqual(row2["superseded_dir"], "run_1.superseded.1")
            run_dir = Path(tmp) / "results" / "a" / "truncation"
            self.assertEqual(json.loads((run_dir / "run_1.superseded.1" / "harbor_result.json").read_text())["id"], "one")
            self.assertEqual(json.loads((run_dir / "run_1" / "harbor_result.json").read_text())["id"], "two")
            # Re-normalizing the same trial does not archive again.
            row3 = adapter._normalize_trial(second, condition, 1, 0.5)
            self.assertIsNone(row3["superseded_dir"])


if __name__ == "__main__":
    unittest.main()
