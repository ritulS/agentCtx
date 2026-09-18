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

    def test_summarizer_ablation_cells_are_tracked_separately(self):
        # model_ablation/<agent>-sum-<summarizer> runs must form their own
        # cell (non-empty ``summarizer`` column) instead of merging into the
        # self-summarized main cell of the same primitive/budget/depth, and
        # "-smoke" directories must never be counted.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'task_lists').mkdir()
            tasks = [{'instance_id': f'task{i}'} for i in range(100)]
            for name, cohort in [('ablation_25tasks.json', tasks[:25]),
                                 ('p100_all_100_tasks.json', tasks),
                                 ('tbench_tasks.json', [])]:
                (root / 'task_lists' / name).write_text(json.dumps(cohort))

            def write_cell(section, model_dir, n_tasks, runs, run_info=None):
                rows = [dict(instance_id=t['instance_id'], condition='summarization',
                             budget=15000, compression_ratio=0.5, run_num=rn)
                        for t in tasks[:n_tasks] for rn in range(1, runs + 1)]
                cell = root / 'ICLR_results/swebench' / section / model_dir / 'd05__b15k__su-full'
                cell.mkdir(parents=True)
                (cell / 'experiment_results.json').write_text(json.dumps(rows))
                if run_info is not None:
                    (cell / 'run_info.json').write_text(json.dumps(run_info))

            write_cell('main', 'qwen35b', 100, 3)
            write_cell('model_ablation', 'qwen35b-sum-qwen35-9b', 25, 3, run_info={
                'model': 'hosted_vllm/Qwen/Qwen3.5-35B-A3B',
                'summary_model': 'hosted_vllm/Qwen/Qwen3.5-9B',
                'summarization_model': {'source': 'override',
                                        'model_name': 'hosted_vllm/Qwen/Qwen3.5-9B'},
            })
            write_cell('model_ablation', 'qwen35b-sum-qwen35-9b-smoke', 1, 1)

            with patch.object(coverage, 'ROOT', root), \
                 patch.object(coverage, 'ICLR_RESULTS', root / 'ICLR_results'), \
                 patch('sys.argv', ['build_coverage.py', '--output', str(root / 'COVERAGE.csv'),
                                    '--tb-output', str(root / 'COVERAGE_TB.csv')]), \
                 contextlib.redirect_stdout(io.StringIO()):
                coverage.main()
            with (root / 'COVERAGE.csv').open() as stream:
                rows = list(csv.DictReader(stream))

            by_summarizer = {r['summarizer']: r for r in rows}
            self.assertEqual(sorted(by_summarizer), ['', 'Qwen3.5-9B'])
            self.assertEqual(len(rows), 2)   # the -smoke directory adds no cell
            main_cell, abl_cell = by_summarizer[''], by_summarizer['Qwen3.5-9B']
            self.assertEqual(main_cell['runs_on_disk'], '300')
            self.assertEqual((main_cell['required_cohort'], main_cell['status']),
                             ('P100', 'COMPLETE'))
            self.assertEqual(abl_cell['model'], coverage.MAIN_MODEL)
            self.assertEqual(abl_cell['runs_on_disk'], '75')
            self.assertEqual((abl_cell['scope'], abl_cell['required_cohort'], abl_cell['status']),
                             ('in-scope', 'ABL-25', 'COMPLETE'))
            self.assertIn('model_ablation/qwen35b-sum-qwen35-9b/', abl_cell['source_dirs'])

            # The dashboard keeps the two apart and reads P4 progress from the
            # summarizer view only.
            with patch.object(dashboard, 'ROOT', root):
                swe_cells, tb_cells, summarizer_cells, _ = dashboard.load_cells()
            self.assertEqual(list(swe_cells), [(dashboard.MAIN, 'SU-full', '15k', '0.5')])
            self.assertEqual(list(summarizer_cells),
                             [('swebench', 'Qwen3.5-9B', dashboard.MAIN, 'SU-full', '15k', '0.5')])
            view = dashboard.summarizer_view(summarizer_cells, 'swebench', 'Qwen3.5-9B')
            self.assertEqual(
                dashboard.coverage_progress(view, dashboard.MAIN, ['SU-full'], '15k', '0.5', 25, 3),
                (True, 75, 75))
            self.assertEqual(
                dashboard.coverage_progress(view, dashboard.MAIN, ['TRC+SU'], '15k', '0.5', 25, 3),
                (False, 0, 75))

    def test_prefix_cache_ablation_cells_are_tracked_separately(self):
        # prefix_cache_ablation/<model> runs must form their own cells
        # (non-empty ``prefix_cache`` column) instead of merging into, or being
        # deduplicated against, the production cell of the same
        # primitive/budget/depth; "-smoke" directories must never be counted.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'task_lists').mkdir()
            tasks = [{'instance_id': f'task{i}'} for i in range(100)]
            for name, cohort in [('ablation_25tasks.json', tasks[:25]),
                                 ('p100_all_100_tasks.json', tasks),
                                 ('tbench_tasks.json', [])]:
                (root / 'task_lists' / name).write_text(json.dumps(cohort))

            def write_cell(benchmark_dir, section, model_dir, cell_name, condition,
                           budget, n_tasks, runs):
                rows = [dict(instance_id=t['instance_id'], condition=condition,
                             budget=budget, compression_ratio=0.5, run_num=rn)
                        for t in tasks[:n_tasks] for rn in range(1, runs + 1)]
                cell = root / 'ICLR_results' / benchmark_dir / section / model_dir / cell_name
                cell.mkdir(parents=True)
                (cell / 'experiment_results.json').write_text(json.dumps(rows))

            write_cell('swebench', 'main', 'qwen35b', 'd05__b15k__tr', 'truncation', 15000, 100, 3)
            write_cell('swebench', 'prefix_cache_ablation', 'qwen35b-prefixcache',
                       'd05__b15k__tr', 'truncation', 15000, 25, 3)
            write_cell('swebench', 'prefix_cache_ablation', 'qwen35b-prefixcache',
                       'di__binf__fc', 'full-context', 999_999_999, 25, 2)
            write_cell('swebench', 'prefix_cache_ablation', 'qwen35b-prefixcache-smoke',
                       'd05__b15k__tr', 'truncation', 15000, 1, 1)
            write_cell('terminalbench', 'prefix_cache_ablation', 'qwen35b-noprefixcache',
                       'di__b3k__trc', 'tool-result-clear', 3000, 15, 3)

            with patch.object(coverage, 'ROOT', root), \
                 patch.object(coverage, 'ICLR_RESULTS', root / 'ICLR_results'), \
                 patch('sys.argv', ['build_coverage.py', '--output', str(root / 'COVERAGE.csv'),
                                    '--tb-output', str(root / 'COVERAGE_TB.csv')]), \
                 contextlib.redirect_stdout(io.StringIO()):
                coverage.main()
            with (root / 'COVERAGE.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            with (root / 'COVERAGE_TB.csv').open() as stream:
                tb_rows = list(csv.DictReader(stream))

            self.assertEqual(len(rows), 3)   # the -smoke directory adds no cell
            by_key = {(r['prefix_cache'], r['primitive']): r for r in rows}
            main_cell = by_key[('', 'TR')]
            self.assertEqual(main_cell['runs_on_disk'], '300')   # not deduplicated away
            self.assertEqual((main_cell['required_cohort'], main_cell['status']),
                             ('P100', 'COMPLETE'))
            self.assertNotIn('prefix_cache_ablation', main_cell['source_dirs'])
            on_cell = by_key[('ON', 'TR')]
            self.assertEqual(on_cell['model'], coverage.MAIN_MODEL)
            self.assertEqual(on_cell['runs_on_disk'], '75')
            self.assertEqual((on_cell['scope'], on_cell['required_cohort'], on_cell['status']),
                             ('in-scope', 'ABL-25', 'COMPLETE'))
            self.assertIn('prefix_cache_ablation/qwen35b-prefixcache/', on_cell['source_dirs'])
            fc_cell = by_key[('ON', 'FC')]
            self.assertEqual((fc_cell['budget'], fc_cell['required_cohort'], fc_cell['status']),
                             ('inf', 'ABL-25', 'PARTIAL'))
            self.assertEqual(len(tb_rows), 1)
            self.assertEqual((tb_rows[0]['prefix_cache'], tb_rows[0]['model'],
                              tb_rows[0]['required_cohort'], tb_rows[0]['status']),
                             ('OFF', coverage.MAIN_MODEL, 'TB-15', 'COMPLETE'))

            # The dashboard keeps them apart and reads P5 progress from the
            # prefix-cache view only.
            with patch.object(dashboard, 'ROOT', root):
                swe_cells, tb_cells, summarizer_cells, prefix_cache_cells = dashboard.load_cells()
            self.assertEqual(list(swe_cells), [(dashboard.MAIN, 'TR', '15k', '0.5')])
            self.assertEqual((tb_cells, summarizer_cells), ({}, {}))
            view = dashboard.prefix_cache_view(prefix_cache_cells, 'swebench', 'ON')
            self.assertEqual(
                dashboard.coverage_progress(view, dashboard.MAIN, ['TR'], '15k', '0.5', 25, 3),
                (True, 75, 75))
            self.assertEqual(
                dashboard.coverage_progress(view, dashboard.MAIN, ['FC', 'OTRC'], 'inf', '0.5', 25, 3),
                (False, 50, 150))
            self.assertEqual(dashboard.prefix_cache_view(prefix_cache_cells, 'swebench', 'OFF'), {})
            tb_view = dashboard.prefix_cache_view(prefix_cache_cells, 'terminal-bench', 'OFF')
            self.assertEqual(
                dashboard.coverage_progress(tb_view, dashboard.MAIN, ['TRC'], '3k', 'DI', 15, 3),
                (True, 45, 45))

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
                 patch.object(dashboard, 'load_cells', return_value=({}, {}, {}, {})), \
                 patch.object(dashboard, 'load_progress_history', return_value=[]), \
                 patch.object(dashboard, 'progress_bar', side_effect=capture), \
                 patch('sys.argv', ['build_dashboard.py']), \
                 contextlib.redirect_stdout(io.StringIO()):
                dashboard.main()
            rows = captured['p1a_all_runs_v3'] + captured['p1b_abl25_v4']
            self.assertNotIn('p1_all_runs_v3', captured)
            self.assertNotIn('p1', captured)
            self.assertNotIn('p1_abl25_v2', captured)
            for old_key in ('p1b_all_runs_v3', 'p2c', 'p2d', 'p2', 'p4', 'p4_abl25_v2'):
                self.assertNotIn(old_key, captured)
            self.assertEqual(sum(r[6][2] for r in captured['p2_abl25_v2']), 15600)
            p4_rows = captured['p4_abl25_tbabl15_v3']
            self.assertEqual(sum(r[6][2] for r in p4_rows), 480)
            self.assertEqual(dashboard.P4_TOTAL_RUNS, 480)
            tb_p4_rows = [r for r in p4_rows if r[4].startswith('TB:')]
            self.assertEqual(len(tb_p4_rows), 2)
            for row in tb_p4_rows:
                self.assertEqual(row[4], 'TB:ABL-15')
                self.assertEqual(row[6][2], 90)
            p5_rows = captured['p5_prefix_cache_v1']
            self.assertEqual(dashboard.P5_TOTAL_RUNS, 1560)
            self.assertEqual(sum(r[6][2] for r in p5_rows), 1560)
            self.assertEqual(sum(r[6][2] for r in p5_rows if r[4] == 'SB:ABL-25'), 975)
            self.assertEqual(sum(r[6][2] for r in p5_rows if r[4] == 'TB:ABL-15'), 585)
            self.assertEqual([(r[2], r[3]) for r in p5_rows],
                             [('0.5', '15K'), ('DI', '15K'), ('DI', '∞'),
                              ('0.5', '3K'), ('DI', '3K'), ('DI', '∞')])
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
            self.assertIn('5. [Priority] Prefix Cache Ablation', html)
            self.assertIn('0 / 1,560 runs', html)


if __name__ == '__main__':
    unittest.main()
