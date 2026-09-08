"""Regression checks for Qwen's shared P100/ABL-30 experiment scope."""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_coverage as coverage
import build_dashboard as dashboard


class QwenCoverageTest(unittest.TestCase):
    def test_legacy_main_cohort_and_copied_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'task_lists').mkdir()
            tasks = [{'instance_id': f'task{i}'} for i in range(100)]
            for name, cohort in [('ablation_30tasks.json', tasks[:30]),
                                 ('p100_all_100_tasks.json', tasks),
                                 ('tbench_tasks.json', [])]:
                (root / 'task_lists' / name).write_text(json.dumps(cohort))

            examples = [('d05__b10k__tr', 'truncation', 10000, 0.5),
                        ('di__b20k__trc', 'tool-result-clear', 20000, 0.5),
                        ('d03__b15k__ss', 'structured-summarize', 15000, 0.3)]
            for cell, condition, budget, depth in examples:
                rows = [dict(instance_id=t['instance_id'], condition=condition,
                             budget=budget, compression_ratio=depth, run_num=rn)
                        for i, t in enumerate(tasks)
                        for rn in range(1, 4 if i < 30 else 3)]
                source = root / 'ICLR_results/swebench/main/qwen35b' / cell
                source.mkdir(parents=True)
                (source / 'experiment_results.json').write_text(json.dumps(rows))

            def build():
                with patch.object(coverage, 'ROOT', root), \
                     patch.object(coverage, 'ICLR_RESULTS', root / 'ICLR_results'), \
                     patch('sys.argv', ['build_coverage.py', '--output', str(root / 'COVERAGE.csv'),
                                        '--tb-output', str(root / 'COVERAGE_TB.csv')]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    coverage.main()
                with (root / 'COVERAGE.csv').open() as stream:
                    return list(csv.DictReader(stream))

            before = build()
            for cell, _, _, _ in examples:
                source = root / 'ICLR_results/swebench/main/qwen35b' / cell
                destination = root / 'ICLR_results/swebench/ablation/qwen35b' / cell
                destination.mkdir(parents=True)
                rows = json.loads((source / 'experiment_results.json').read_text())
                (destination / 'experiment_results.json').write_text(json.dumps(rows[:90]))
            after = build()
            for old, new in zip(before, after):
                self.assertEqual(new['required_cohort'], 'ABL-30')
                self.assertEqual(new['status'], 'COMPLETE')
                self.assertEqual(new['runs_capped_3_abl30'], '90')
                self.assertEqual(new['runs_capped_3_p100'], '230')
                self.assertEqual(new['runs_on_disk'], '230')
                self.assertEqual({k: v for k, v in old.items() if k != 'source_dirs'},
                                 {k: v for k, v in new.items() if k != 'source_dirs'})
            cell = after[0]
            done, actual, target = dashboard.coverage_progress(
                {(dashboard.MAIN, cell['primitive'], cell['budget'], cell['depth']): cell},
                dashboard.MAIN, [cell['primitive']], cell['budget'], cell['depth'],
                30, 3, baseline_runs=2)
            self.assertEqual((done, actual, target), (True, 30, 30))

    def test_p1_display_targets_and_history_scope(self):
        captured = {}
        original = dashboard.progress_bar

        def capture(rows, key, *args):
            captured[key] = rows
            return original(rows, key, *args)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(dashboard, 'ROOT', root), \
                 patch.object(dashboard, 'OUT', root / 'DASHBOARD.html'), \
                 patch.object(dashboard, 'load_cells', return_value=({}, {})), \
                 patch.object(dashboard, 'load_progress_history', return_value=[]), \
                 patch.object(dashboard, 'progress_bar', side_effect=capture), \
                 patch('sys.argv', ['build_dashboard.py']), \
                 contextlib.redirect_stdout(io.StringIO()):
                dashboard.main()
            rows = captured['p1_abl30_v2']
            self.assertNotIn('p1', captured)
            self.assertEqual(sum(r[6][2] for r in rows), 2860)
            self.assertEqual(sum(r[6][2] for r in rows if r[4] == 'SB:P-100'), 1300)
            self.assertEqual(sum(r[6][2] for r in rows if r[4] == 'SB:ABL-30'), 1560)
            for row in rows:
                expected = 'SB:P-100' if row[3] == '∞' or (
                    row[3] == '15K' and row[2] in ('0.5', 'DI')) else 'SB:ABL-30'
                self.assertEqual(row[4], expected)
            html = (root / 'DASHBOARD.html').read_text()
            self.assertIn('0 / 2,860 runs', html)
            self.assertNotIn('4,400', html)


if __name__ == '__main__':
    unittest.main()
