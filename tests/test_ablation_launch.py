"""Offline checks for selective evaluation preserving excluded result rows.

Run with: uvx --with pyyaml pytest tests/test_ablation_launch.py
"""
import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agentctx.experiments import runner  # noqa: E402


class AblationLaunchTests(unittest.TestCase):
    def test_evaluation_preserves_excluded_rows(self):
        for mode in ['--eval-only', '--with-eval']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                rows = [dict(key='keep__r1', instance_id='keep', resolved=None),
                        dict(key='legacy__r1', instance_id='legacy', resolved=None)]
                saved = []
                class Benchmark:
                    name = 'swe-bench'
                    def run_experiments(self, **kwargs):
                        return kwargs['existing_results']
                    def evaluate_results(self, selected, save):
                        self_test.assertEqual([r['instance_id'] for r in selected], ['keep'])
                        updated = [dict(selected[0], resolved=True)]
                        save(updated)
                        return updated
                self_test = self
                with patch.object(sys, 'argv', ['runner', '--ablation', 'test', '--tasks-file', 'test.json', mode]), \
                     patch.object(runner, 'model_results_dir', return_value=Path(tmp)), \
                     patch.object(runner, 'create_benchmark', return_value=Benchmark()), \
                     patch.object(runner, 'load_tasks', return_value=[dict(instance_id='keep')]), \
                     patch.object(runner, '_write_run_info'), \
                     patch.object(runner, 'load_existing_results', return_value=rows), \
                     patch.object(runner, 'save_results', side_effect=lambda r: saved.append(copy.deepcopy(r))), \
                     contextlib.redirect_stdout(io.StringIO()):
                    runner.main()
                self.assertTrue(saved)
                for snapshot in saved:
                    self.assertEqual(len(snapshot), 2)
                    self.assertTrue(snapshot[0]['resolved'])
                    self.assertEqual(snapshot[1], dict(key='legacy__r1', instance_id='legacy', resolved=None))


if __name__ == '__main__':
    unittest.main()
