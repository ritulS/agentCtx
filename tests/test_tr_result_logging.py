"""TR diagnostics survive benchmark result conversion, including legacy logs."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agentctx.benchmarks.harbor_results import normalize_trial
from agentctx.benchmarks.swe_bench import SweBench


DIAGNOSTICS = {
    'tr_events': [{'policy': 'budget_ratio_complete_turns_v1', 'step': 4,
                   'primitive': 'truncation', 'budget_tokens': 100, 'target_tokens': 50,
                   'tokens_before': 200, 'tokens_after': 80, 'tokens_saved': 120,
                   'target_not_met': True, 'budget_exceeded': False, 'zero_reduction': False}],
    'tr_target_not_met_events': 1,
    'tr_budget_exceeded_events': 0,
    'tr_zero_reduction_events': 0,
}


class TrResultLoggingTests(unittest.TestCase):
    def assert_diagnostics(self, row, payload):
        for key in DIAGNOSTICS:
            if key in payload:
                self.assertEqual(row[key], payload[key])
            else:
                self.assertNotIn(key, row)

    def test_swe_result_retains_diagnostics_without_inventing_historical_values(self):
        for payload in (DIAGNOSTICS, {}):
            with self.subTest(legacy=not payload), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                results = root / 'results'
                output = results / 'task' / 'truncation' / 'run_1'
                output.mkdir(parents=True)
                (output / 'token_log.json').write_text(json.dumps(payload))
                benchmark = SweBench(root, 'test', results)
                process = Mock(pid=123, returncode=0)
                with patch('agentctx.benchmarks.swe_bench.subprocess.Popen', return_value=process), patch(
                    'agentctx.benchmarks.swe_bench.resource_monitor.start_for_process', return_value=None
                ):
                    row = benchmark._run_agent(instance_id='task', condition='truncation',
                                               primitive='truncation', budget=100, run_num=1,
                                               agent_config=root / 'config.yaml', step_limit=2, agent_timeout=1)
                self.assert_diagnostics(row, payload)

    def test_swe_result_names_timeout_and_keeps_last_flushed_trajectory(self):
        # The harness SIGKILLs the agent on timeout, so the agent never writes
        # an exit status. The row must still say why the run ended, whether or
        # not a trajectory had been flushed before the kill.
        for trajectory in (None, {'info': {'exit_status': '', 'submission': '',
                                           'model_stats': {'api_calls': 7}}}):
            with self.subTest(trajectory=trajectory is not None), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                results = root / 'results'
                output = results / 'task' / 'truncation' / 'run_1'
                output.mkdir(parents=True)
                if trajectory is not None:
                    (output / 'trajectory.json').write_text(json.dumps(trajectory))
                (output / 'token_log.json').write_text(json.dumps(
                    {'net_tokens_saved': -5, 'growth_events': 1, 'summary_fallback_events': 2}))
                benchmark = SweBench(root, 'test', results)
                process = Mock(pid=123, returncode=None)
                process.wait.side_effect = [subprocess.TimeoutExpired('agent', 1), None]
                with patch('agentctx.benchmarks.swe_bench.subprocess.Popen', return_value=process), patch(
                    'agentctx.benchmarks.swe_bench.resource_monitor.start_for_process', return_value=None
                ):
                    row = benchmark._run_agent(instance_id='task', condition='truncation',
                                               primitive='truncation', budget=100, run_num=1,
                                               agent_config=root / 'config.yaml', step_limit=2, agent_timeout=1)
                process.kill.assert_called_once()
                self.assertTrue(row['timed_out'])
                self.assertEqual(row['exit_status'], 'Timeout')
                self.assertEqual(row['returncode'], -1)
                self.assertEqual(row['n_calls'], 7 if trajectory is not None else 0)
                self.assertFalse(row['patch_generated'])
                self.assertEqual((row['net_tokens_saved'], row['growth_events'], row['summary_fallback_events']),
                                 (-5, 1, 2))

    def test_swe_recovers_calls_from_missing_corrupt_and_oversized_trajectories(self):
        for status in ('missing', 'unreadable', 'oversized'):
            for field in ('model_call_records', 'step_prompt_tokens'):
                with self.subTest(status=status, field=field), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    trajectory = root / 'trajectory.json'
                    benchmark = SweBench(root, 'test', root)
                    if status == 'unreadable':
                        trajectory.write_text('{"info":')
                    elif status == 'oversized':
                        with trajectory.open('wb') as stream:
                            stream.truncate(benchmark.MAX_TRAJECTORY_BYTES + 1)
                    token_log = {field: [{}] * 134 if field == 'model_call_records' else [10] * 134}
                    row = benchmark.read_run_outcome(trajectory, token_log)
                    self.assertEqual(row['trajectory_status'], status)
                    self.assertEqual(row['n_calls'], 134)
                    self.assertEqual(row['n_calls_source'], 'token_log.' + field)
                    self.assertFalse(row['patch_generated'])
                    self.assertEqual(row['submission'], '')
                    self.assertEqual(row['exit_status'], '')
                    self.assertIsNone(row['resolved'])

    def test_swe_call_recovery_preserves_valid_submission_and_inflight_count(self):
        for trajectory_calls in (2, 3, 4):
            with self.subTest(calls=trajectory_calls), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                trajectory = root / 'trajectory.json'
                trajectory.write_text(json.dumps({'info': {
                    'model_stats': {'api_calls': trajectory_calls},
                    'submission': 'diff --git a/file b/file', 'exit_status': 'Submitted',
                }}))
                benchmark = SweBench(root, 'test', root)
                row = benchmark.read_run_outcome(trajectory, {'model_call_records': [{}, {}, {}]})
                self.assertEqual(row['n_calls'], max(3, trajectory_calls))
                self.assertEqual(row['n_calls_source'],
                                 'token_log.model_call_records' if trajectory_calls < 3 else 'trajectory')
                self.assertEqual(row['exit_status'], 'Submitted')
                self.assertTrue(row['patch_generated'])
                self.assertEqual(row['submission'], 'diff --git a/file b/file')

    def test_swe_timeout_with_broken_trajectory_recovers_completed_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'results' / 'task' / 'truncation' / 'run_1'
            output.mkdir(parents=True)
            (output / 'trajectory.json').write_text('{"info":')
            (output / 'token_log.json').write_text(json.dumps({
                'model_call_records': [{'step': i, 'status': 'ok'} for i in range(1, 135)],
                'step_prompt_tokens': [10] * 134, 'total_prompt_tokens': 1340,
            }))
            benchmark = SweBench(root, 'test', root / 'results')
            process = Mock(pid=123, returncode=None)
            process.wait.side_effect = [subprocess.TimeoutExpired('agent', 1), None]
            with patch('agentctx.benchmarks.swe_bench.subprocess.Popen', return_value=process), patch(
                'agentctx.benchmarks.swe_bench.resource_monitor.start_for_process', return_value=None
            ):
                row = benchmark._run_agent(instance_id='task', condition='truncation',
                                           primitive='truncation', budget=100, run_num=1,
                                           agent_config=root / 'config.yaml', step_limit=300, agent_timeout=1)
            self.assertEqual(row['n_calls'], 134)
            self.assertEqual(row['n_calls_source'], 'token_log.model_call_records')
            self.assertEqual(row['trajectory_status'], 'unreadable')
            self.assertEqual(row['total_prompt_tokens'], 1340)
            self.assertEqual(row['exit_status'], 'Timeout')
            self.assertFalse(row['patch_generated'])

    def test_swe_no_patch_rows_are_failures_regardless_of_trajectory_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            benchmark = SweBench(root, 'test', root)
            rows = [
                {'patch_generated': False, 'resolved': None, 'trajectory_status': status}
                for status in ('missing', 'unreadable', 'oversized', 'ok')
            ]
            rows.append({'patch_generated': False, 'resolved': None,
                         'trajectory_status': 'unreadable', 'timed_out': True})
            saved = Mock()
            benchmark.evaluate_results(rows, saved)
            # The status column carries the read problem; the verdict does not change.
            self.assertEqual([r['resolved'] for r in rows], [False] * 5)
            self.assertEqual([r['trajectory_status'] for r in rows],
                             ['missing', 'unreadable', 'oversized', 'ok', 'unreadable'])
            saved.assert_called_once()

    def test_swe_invalid_call_count_recovers_from_token_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trajectory = root / 'trajectory.json'
            trajectory.write_text(json.dumps({'info': {'model_stats': {'api_calls': None}}}))
            row = SweBench(root, 'test', root).read_run_outcome(trajectory, {'step_prompt_tokens': [1, 2]})
            self.assertEqual(row['trajectory_status'], 'unreadable')
            self.assertEqual(row['n_calls'], 2)

    def test_swe_result_without_timeout_has_no_timeout_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / 'results'
            output = results / 'task' / 'truncation' / 'run_1'
            output.mkdir(parents=True)
            (output / 'trajectory.json').write_text(json.dumps(
                {'info': {'exit_status': 'Submitted', 'submission': 'diff', 'model_stats': {'api_calls': 3}}}))
            (output / 'token_log.json').write_text(json.dumps({}))
            benchmark = SweBench(root, 'test', results)
            process = Mock(pid=123, returncode=0)
            with patch('agentctx.benchmarks.swe_bench.subprocess.Popen', return_value=process), patch(
                'agentctx.benchmarks.swe_bench.resource_monitor.start_for_process', return_value=None
            ):
                row = benchmark._run_agent(instance_id='task', condition='truncation',
                                           primitive='truncation', budget=100, run_num=1,
                                           agent_config=root / 'config.yaml', step_limit=2, agent_timeout=1)
            self.assertEqual(row['exit_status'], 'Submitted')
            self.assertNotIn('timed_out', row)
            for key in ('net_tokens_saved', 'growth_events', 'summary_fallback_events'):
                self.assertNotIn(key, row)  # legacy token logs stay legacy-shaped

    def test_harbor_result_retains_diagnostics_without_inventing_historical_values(self):
        for payload in (DIAGNOSTICS, {}):
            with self.subTest(legacy=not payload), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                trial = root / 'trial'
                (trial / 'agent').mkdir(parents=True)
                (trial / 'result.json').write_text(json.dumps({
                    'task_name': 'task', 'exception_info': None,
                    'verifier_result': {'rewards': {'reward': 1}},
                }))
                (trial / 'agent' / 'token_log.json').write_text(json.dumps(payload))
                row = normalize_trial(trial, root / 'results', 'test', 1,
                                      condition={'condition': 'truncation', 'primitive': 'truncation', 'budget': 100},
                                      compression_ratio=0.5, workspace_root=root)
                self.assert_diagnostics(row, payload)


if __name__ == '__main__':
    unittest.main()
