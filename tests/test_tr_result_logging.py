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
