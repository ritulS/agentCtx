"""TR diagnostics survive benchmark result conversion, including legacy logs."""
import json
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
