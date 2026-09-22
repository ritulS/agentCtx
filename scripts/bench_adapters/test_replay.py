"""Unit tests for the replay re-verification tooling (no containers involved).

    venv-harbor/bin/python -m unittest scripts.bench_adapters.test_replay
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT, REPO_ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from scripts.bench_adapters import replay_agent  # noqa: E402

spec = importlib.util.spec_from_file_location("replay_reverify_tb", REPO_ROOT / "scripts" / "replay_reverify_tb.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def trajectory(commands, *, cleared=(), missing_turns=0):
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}]
    for i, command in enumerate(commands):
        messages.append({"role": "assistant", "content": f"```bash\n{command}\n```",
                         "extra": {"actions": [{"command": command}]}})
        observation = {"role": "user", "content": f"<returncode>0</returncode>\n<output>\nout {i}\n</output>"}
        if i not in cleared:
            observation["extra"] = {"raw_output": f"out {i}\n", "returncode": 0}
        messages.append(observation)
    messages.append({"role": "exit", "content": "", "extra": {"exit_status": "Submitted", "submission": ""}})
    if missing_turns:
        del messages[2:2 + 2 * missing_turns]
    return {"info": {"model_stats": {"api_calls": len(commands)}}, "messages": messages,
            "trajectory_format": "mini-swe-agent-1.1"}


class ExtractActionsTest(unittest.TestCase):
    def test_pairs_commands_with_observations(self):
        actions = replay_agent.extract_actions(trajectory(["ls", "pwd", "echo done"], cleared={1}))
        self.assertEqual([a["command"] for a in actions], ["ls", "pwd", "echo done"])
        self.assertEqual(actions[0]["original"], {"raw_output": "out 0\n", "returncode": 0})
        self.assertIsNone(actions[1]["original"])       # cleared by TRC: nothing to compare

    def test_compare(self):
        self.assertEqual(replay_agent.compare_with_original({"raw_output": "a \nb\n", "returncode": 0}, "a\nb", 0),
                         {"output_match": True, "returncode_match": True})
        self.assertEqual(replay_agent.compare_with_original(None, "x", 1),
                         {"output_match": None, "returncode_match": None})


class AnalyzeTrajectoryTest(unittest.TestCase):
    def test_no_compression_is_replayable_even_with_api_retries(self):
        t = trajectory(["ls", "pwd"])
        info = runner.analyze_trajectory(t, {"n_calls": 3, "compression_events": 0})
        self.assertTrue(info["replayable"])

    def test_compression_without_lost_turns(self):
        t = trajectory(["ls", "pwd"])
        info = runner.analyze_trajectory(t, {"n_calls": 2, "compression_events": 1})
        self.assertTrue(info["replayable"])
        self.assertEqual(info["n_uncomparable"], 0)

    def test_counts_commands_without_observation(self):
        t = trajectory(["ls", "touch x", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"], cleared={1, 2})
        info = runner.analyze_trajectory(t, {"n_calls": 3, "compression_events": 1})
        self.assertEqual(info["n_uncomparable"], 1)          # the submission echo is exempt

    def test_compression_with_lost_turns(self):
        t = trajectory(["ls", "pwd", "cat x"], missing_turns=1)
        info = runner.analyze_trajectory(t, {"n_calls": 3, "compression_events": 1})
        self.assertFalse(info["replayable"])
        self.assertIn("removed 1 of 3", info["reason"])

    def test_no_actions(self):
        info = runner.analyze_trajectory({"messages": []}, {"n_calls": 0, "compression_events": 0})
        self.assertFalse(info["replayable"])


class FakeEnvironment:
    def __init__(self, outputs, fail_at=None):
        self.outputs = outputs
        self.fail_at = fail_at
        self.calls = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.calls.append((command, env, timeout_sec))
        if self.fail_at is not None and len(self.calls) - 1 == self.fail_at:
            raise TimeoutError("command timed out")
        return SimpleNamespace(stdout=self.outputs[len(self.calls) - 1], stderr="", return_code=0)


class ReplayAgentTest(unittest.TestCase):
    def test_replays_all_commands_and_records_fidelity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.json"
            path.write_text(json.dumps(trajectory(["ls", "pwd", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"], cleared={2})))
            specs = Path(tmp) / "cfg.yaml"
            specs.write_text("environment:\n  timeout: 7\n  env:\n    PAGER: cat\n")
            with mock.patch.dict(os.environ, {"REPLAY_TRAJECTORY": str(path), "REPLAY_CONFIG_SPECS": str(specs)}):
                agent = replay_agent.ReplayAgent(logs_dir=Path(tmp) / "agent", model_name="replay/trajectory")
            env = FakeEnvironment(["out 0\n", "different\n", "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n"], fail_at=None)
            context = SimpleNamespace(n_input_tokens=None, n_output_tokens=None)
            asyncio.run(agent.run("instruction", env, context))
            self.assertEqual([c[0] for c in env.calls], ["ls", "pwd", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])
            self.assertEqual(env.calls[0][1], {"PAGER": "cat"})
            self.assertEqual(env.calls[0][2], 7)
            summary = json.loads((Path(tmp) / "agent" / "replay_summary.json").read_text())
            self.assertTrue(summary["complete"])
            self.assertEqual((summary["n_actions"], summary["n_executed"], summary["n_errors"]), (3, 3, 0))
            self.assertEqual((summary["n_compared"], summary["n_output_matched"]), (2, 1))
            log = json.loads((Path(tmp) / "agent" / "replay_log.json").read_text())
            self.assertEqual([e["output_match"] for e in log], [True, False, None])
            self.assertEqual(context.n_input_tokens, 0)

    def test_continues_after_command_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.json"
            path.write_text(json.dumps(trajectory(["a", "b"])))
            with mock.patch.dict(os.environ, {"REPLAY_TRAJECTORY": str(path)}):
                agent = replay_agent.ReplayAgent(logs_dir=Path(tmp) / "agent")
            env = FakeEnvironment(["out 0\n", "out 1\n"], fail_at=0)
            asyncio.run(agent.run("i", env, SimpleNamespace()))
            summary = json.loads((Path(tmp) / "agent" / "replay_summary.json").read_text())
            self.assertTrue(summary["complete"])
            self.assertEqual(summary["n_errors"], 1)
            log = json.loads((Path(tmp) / "agent" / "replay_log.json").read_text())
            self.assertTrue(log[0]["exception"].startswith("TimeoutError"))
            self.assertEqual(log[1]["output_match"], True)


class DivergenceGateTest(unittest.TestCase):
    """A graded replay is applicable only when it reproduced the original run."""

    def make_job(self, tmp: Path, log, *, reward=1.0):
        trial = tmp / "job" / "t1__abc"
        (trial / "agent").mkdir(parents=True)
        (trial / "result.json").write_text(json.dumps({"id": "x", "task_name": "t1", "exception_info": None,
                                                        "verifier_result": {"rewards": {"reward": reward}}}))
        (trial / "agent" / "replay_summary.json").write_text(json.dumps({
            "trajectory_sha256": "sha", "complete": True, "n_actions": len(log), "n_executed": len(log),
            "n_errors": sum(bool(s.get("exception")) for s in log), "n_compared": 0,
            "n_output_matched": 0, "n_returncode_matched": 0}))
        (trial / "agent" / "replay_log.json").write_text(json.dumps(log))
        return tmp / "job"

    def step(self, n, **kw):
        return {"step": n, "command": "c", "returncode": 0, "exception": "", "output_match": True,
                "returncode_match": True, **kw}

    def test_faithful_replay_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            submit = self.step(1, command="echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
                               output_match=None, returncode_match=None)
            job = self.make_job(Path(tmp), [self.step(0), submit])
            evidence = runner.collect_evidence({"task": "t1", "trajectory_sha256": "sha"}, job)
            self.assertEqual(evidence["resolved"], True)
            self.assertEqual(evidence["divergence"]["fatal"], [])
            self.assertEqual(evidence["divergence"]["uncomparable"], [])    # submission echo is exempt

    def test_uncomparable_step_is_divergent_unless_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            # e.g. a file-creating command whose observation was cleared; the replay
            # may have failed silently, so the verdict must not be applied by default.
            job = self.make_job(Path(tmp), [self.step(0, command="touch out.txt", output_match=None,
                                                      returncode_match=None), self.step(1)], reward=0.0)
            item = {"task": "t1", "trajectory_sha256": "sha"}
            with self.assertRaises(runner.Divergent) as ctx:
                runner.collect_evidence(item, job)
            self.assertIn("no original observation [0]", str(ctx.exception))
            evidence = runner.collect_evidence(item, job, accept_uncomparable=True)
            self.assertEqual(evidence["divergence"]["uncomparable"], [0])
            self.assertEqual(evidence["resolved"], False)

    def test_exec_error_or_exit_code_mismatch_is_divergent(self):
        for bad in ({"exception": "TimeoutError: x"}, {"returncode_match": False, "returncode": 1}):
            with tempfile.TemporaryDirectory() as tmp:
                job = self.make_job(Path(tmp), [self.step(0), self.step(1, **bad)])
                with self.assertRaises(runner.Divergent):
                    runner.collect_evidence({"task": "t1", "trajectory_sha256": "sha"}, job,
                                            accept_output_mismatch=True)

    def test_output_mismatch_is_divergent_unless_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(Path(tmp), [self.step(0, output_match=False)])
            item = {"task": "t1", "trajectory_sha256": "sha"}
            with self.assertRaises(runner.Divergent):
                runner.collect_evidence(item, job)
            evidence = runner.collect_evidence(item, job, accept_output_mismatch=True)
            self.assertEqual(evidence["divergence"]["output_mismatch"], [0])

    def test_apply_skips_divergent_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            (out / "manifest.json").write_text(json.dumps({"items": [{"key": "k", "cell": "c", "result_file": "r"}]}))
            (out / "results.json").write_text(json.dumps({"0": {"status": "divergent", "error": "e"}}))
            with mock.patch("sys.stdout"):
                code = runner.apply(SimpleNamespace(output_dir=out, write=False, allow_partial=False))
            self.assertEqual(code, 0)          # preview only; nothing to apply, nothing raised


class RunnerPlanAndDryRunTest(unittest.TestCase):
    def make_tree(self, tmp: Path):
        cell = tmp / "terminalbench" / "main" / "m" / "d05__b3k__tr"
        rows = []
        # t1 replayable; t2 lost turns but the verifier wrote a reward file; t3 not a verifier timeout
        for task, exception, missing, reward_file in (("t1", "VerifierTimeoutError", 0, None),
                                                      ("t2", "VerifierTimeoutError", 1, "1"),
                                                      ("t3", "AddTestsDirError", 0, None)):
            run_dir = cell / task / "truncation" / "run_1"
            run_dir.mkdir(parents=True)
            raw = tmp / "logs" / "harbor_jobs" / "job" / f"{task}__raw"
            (raw / "verifier").mkdir(parents=True)
            if reward_file is not None:
                (raw / "verifier" / "reward.txt").write_text(reward_file + "\n")
                (raw / "verifier" / "test-stdout.txt").write_text(
                    "PASSED tests/test_outputs.py::test_a\n=========== 2 passed in 1.34s ===========\n")
            (run_dir / "harbor_result.json").write_text(json.dumps({
                "id": task, "task_name": task, "trial_name": f"{task}__raw", "trial_uri": raw.as_uri(),
                "exception_info": {"exception_type": exception, "exception_message": exception},
                "verifier_result": None}))
            (run_dir / "trajectory.json").write_text(json.dumps(trajectory(["ls", "pwd"], missing_turns=missing)))
            rows.append({"key": f"{task}__truncation__r1", "instance_id": task, "condition": "truncation", "run_num": 1,
                         "reward": None, "resolved": False, "n_calls": 2, "compression_events": 1 if missing else 0,
                         "dataset": "terminal-bench-core@0.1.1", "benchmark_version": "1.0", "exit_status": "Submitted"})
        (cell / "experiment_results.json").write_text(json.dumps(rows))
        return tmp / "terminalbench"

    def test_reward_file_requires_pytest_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "trial"
            (raw / "verifier").mkdir(parents=True)
            (raw / "verifier" / "reward.txt").write_text("0")
            (raw / "verifier" / "test-stdout.txt").write_text("collecting ...\n")     # cut off: no summary
            harbor = {"trial_uri": raw.as_uri()}
            self.assertIsNone(runner.reward_file_evidence(harbor))
            (raw / "verifier" / "test-stdout.txt").write_text("FAILED x\n===== 1 failed, 5 passed in 83.86s (0:01:23) =====\n")
            evidence = runner.reward_file_evidence(harbor)
            self.assertEqual(evidence["reward"], 0.0)
            self.assertIn("1 failed, 5 passed", evidence["pytest_summary"])

    def test_recover_then_apply_writes_reward_file_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(Path(tmp))
            out = Path(tmp) / "candidates.json"
            with mock.patch.object(runner, "ROOT", Path(tmp)), mock.patch("sys.stdout"):
                runner.plan(SimpleNamespace(source_root=[root], exception=None, out=out))
                by_task = {c["task"]: c for c in json.loads(out.read_text())["candidates"]}
                self.assertIsNone(by_task["t1"]["reward_file"])
                self.assertEqual(by_task["t2"]["reward_file"]["reward"], 1.0)
                output = Path(tmp) / "logs" / "rec"
                code = runner.recover(SimpleNamespace(candidates=out, output_dir=output, limit=None, only=None, resume=False))
                self.assertEqual(code, 0)
                results = json.loads((output / "results.json").read_text())
                self.assertEqual(results["0"]["status"], "verified")
                self.assertEqual(results["0"]["method"], "reward_file")
                self.assertEqual(runner.apply(SimpleNamespace(output_dir=output, write=True, allow_partial=False)), 0)
                index = root / "main" / "m" / "d05__b3k__tr" / "experiment_results.json"
                row = {r["instance_id"]: r for r in json.loads(index.read_text())}["t2"]
            self.assertEqual((row["resolved"], row["reward"], row["verdict_source"]), (True, 1.0, "verifier_reward_file"))
            self.assertEqual(row["reevaluation"]["method"], "reward_file")
            self.assertEqual(row["reevaluation"]["previous"]["resolved"], False)
            self.assertTrue(any((output / "backups").rglob("experiment_results.json")))

    def test_plan_then_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(Path(tmp))
            out = Path(tmp) / "candidates.json"
            with mock.patch.object(runner, "ROOT", Path(tmp)):
                code = runner.plan(SimpleNamespace(source_root=[root], exception=None, out=out))
                self.assertEqual(code, 0)
                payload = json.loads(out.read_text())
                by_task = {c["task"]: c for c in payload["candidates"]}
                self.assertEqual(sorted(by_task), ["t1", "t2"])          # t3: not a verifier timeout
                self.assertTrue(by_task["t1"]["replayable"])
                self.assertFalse(by_task["t2"]["replayable"])
                args = SimpleNamespace(
                    candidates=out, output_dir=Path(tmp) / "logs" / "out", harbor_bin=Path("/bin/harbor"),
                    dataset_path=Path("/data/tb1"), config_specs="cfg.yaml", model_name="replay/trajectory",
                    verifier_timeout_multiplier=2.0, verifier_threads=8, n_parallel=1, limit=None, only=None,
                    resume=False, continue_on_error=False, dry_run=True, accept_output_mismatch=False,
                    accept_uncomparable=False, include_recoverable=False,
                )
                with mock.patch("sys.stdout") as stdout:
                    self.assertEqual(runner.run(args), 0)
                printed = "".join(str(c.args[0]) for c in stdout.write.call_args_list)
            self.assertIn("--include-task-name t1", printed)
            self.assertIn("--verifier-timeout-multiplier 2.0", printed)
            self.assertIn("--verifier-env OMP_NUM_THREADS=8", printed)
            self.assertIn("scripts.bench_adapters.replay_agent:ReplayAgent", printed)
            self.assertNotIn("--include-task-name t2", printed)              # not replayable: skipped
            self.assertFalse((Path(tmp) / "logs" / "out").exists())          # dry run writes nothing


if __name__ == "__main__":
    unittest.main()
