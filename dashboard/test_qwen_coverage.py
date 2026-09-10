"""Regression checks for Qwen's shared P100/ABL-25 experiment scope."""

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
    def test_pinned_ablation_is_25_task_subset(self):
        tasks = coverage.load_task_list(coverage.ROOT / 'task_lists/ablation_25tasks.json')
        legacy = coverage.load_task_list(coverage.ROOT / 'task_lists/ablation_30tasks.json')
        self.assertEqual(len(tasks), 25)
        self.assertLess(tasks, legacy)

    def test_excluded_tasks_cannot_complete_ablation(self):
        cell = {'tasks_on_disk': '30', 'runs_on_disk': '90',
                'runs_capped_3_abl25': '72', 'runs_capped_3_abl30': '90'}
        progress = dashboard.coverage_progress(
            {(dashboard.MAIN, 'TR', '10k', '0.5'): cell},
            dashboard.MAIN, ['TR'], '10k', '0.5', 25, 3)
        self.assertEqual(progress, (False, 72, 75))

    def test_legacy_csv_requires_rebuild(self):
        with self.assertRaisesRegex(ValueError, 'regenerate COVERAGE.csv'):
            dashboard.coverage_progress(
                {(dashboard.MAIN, 'TR', '10k', '0.5'):
                 {'tasks_on_disk': '30', 'runs_on_disk': '90'}},
                dashboard.MAIN, ['TR'], '10k', '0.5', 25, 3)

    def test_legacy_main_cohort_and_copied_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'task_lists').mkdir()
            tasks = [{'instance_id': f'task{i}'} for i in range(100)]
            for name, cohort in [('ablation_25tasks.json', tasks[:25]),
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
                        for rn in range(1, 4 if i < 25 else 3)]
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
                self.assertEqual(new['required_cohort'], 'ABL-25')
                self.assertEqual(new['status'], 'COMPLETE')
                self.assertEqual(new['runs_capped_3_abl25'], '75')
                self.assertEqual(new['runs_capped_3_p100'], '225')
                self.assertEqual(new['runs_on_disk'], '225')
                self.assertEqual({k: v for k, v in old.items() if k != 'source_dirs'},
                                 {k: v for k, v in new.items() if k != 'source_dirs'})
            cell = after[0]
            done, actual, target = dashboard.coverage_progress(
                {(dashboard.MAIN, cell['primitive'], cell['budget'], cell['depth']): cell},
                dashboard.MAIN, [cell['primitive']], cell['budget'], cell['depth'],
                25, 3)
            self.assertEqual((done, actual, target), (True, 75, 75))

    def test_partial_runs_count_toward_total(self):
        # One task with one run and one with two runs must contribute three,
        # even though neither task has a third run yet.
        cell = {'runs_capped_3_abl25': '3', 'runs_capped_2_abl25': '3'}
        progress = dashboard.coverage_progress(
            {(dashboard.MAIN, 'TR', '10k', '0.5'): cell},
            dashboard.MAIN, ['TR'], '10k', '0.5', 25, 3)
        self.assertEqual(progress, (False, 3, 75))

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
            rows = captured['p1a_all_runs_v3'] + captured['p1b_abl25_v4']
            self.assertNotIn('p1_all_runs_v3', captured)
            self.assertNotIn('p1', captured)
            self.assertNotIn('p1_abl25_v2', captured)
            for old_key in ('p1b_all_runs_v3', 'p2c', 'p2d', 'p2', 'p4'):
                self.assertNotIn(old_key, captured)
            self.assertEqual(sum(r[6][2] for r in captured['p2_abl25_v2']), 15600)
            self.assertEqual(sum(r[6][2] for r in captured['p4_abl25_v2']), 700)
            self.assertEqual(sum(r[6][2] for r in captured['p3']), 11700)
            self.assertEqual(sum(r[6][2] for r in rows), 7800)
            self.assertEqual(sum(r[6][2] for r in rows if r[4] == 'SB:P-100'), 3900)
            self.assertEqual(sum(r[6][2] for r in rows if r[4] == 'SB:ABL-25'), 3900)
            for row in rows:
                expected = 'SB:P-100' if row[3] == '∞' or (
                    row[3] == '15K' and row[2] in ('0.5', 'DI')) else 'SB:ABL-25'
                self.assertEqual(row[4], expected)
            html = (root / 'DASHBOARD.html').read_text()
            self.assertNotIn('ABL-30', html)
            self.assertIn('15,600', html)
            self.assertNotIn('0 / 8,580 runs', html)
            self.assertIn('0 / 3,900 runs', html)
            self.assertIn('0 / 3,900 runs', html)
            self.assertNotIn('4,400', html)


if __name__ == '__main__':
    unittest.main()
