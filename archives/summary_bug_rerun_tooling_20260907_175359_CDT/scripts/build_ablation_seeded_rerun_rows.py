#!/usr/bin/env python3
"""Build rerun rows for ablation cells that were seeded from archived main runs.

scripts/reuse_qwen_main_for_ablation.py copied ABL-30 runs from Qwen's legacy main
10K/20K cells into ICLR_results/swebench/ablation/qwen35b/.  The summary-bug audit
covered only the main-side paths, so the copies of runs that were later archived from
main are still recorded as complete in the ablation indexes and would be skipped by a
resume.

This script takes rerun_runs.csv (main-side rows), finds every ablation index row with
the same cell/task/condition/run, and keeps it only when the ablation copy is
byte-identical (trajectory.json and token_log.json) to the run archived from main and
its index row equals the archived main index row.  Rows whose ablation copy differs are
fresh reruns and are written to the excluded CSV instead.

Outputs (in --output-dir):
  rerun_runs_ablation_seeded.csv           rows in rerun_runs.csv format, section=ablation,
                                           trajectory pointing at the ablation copy, plus
                                           seed_* provenance columns
  rerun_runs_ablation_seeded_excluded.csv  candidates not selected, with a reason
  source_file_stats_ablation_seeded.json   size/mtime_ns of the selected copies, for
                                           archive_swebench_rerun_targets.py --source-stats
  rerun_ablation_seeded_README.txt         counts and the archive command

Read-only with respect to ICLR_results; nothing is moved.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

EXTRA_FIELDS = ['seed_source_section', 'seed_source_trajectory', 'seed_archive']
CHECKED_FILES = ('trajectory.json', 'token_log.json')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_number(run):
    return int(run.removeprefix('run_'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--rerun-csv', type=Path, required=True)
    parser.add_argument('--archive-root', type=Path, action='append', required=True,
                        help='Archive directory holding the runs moved out of main (repeatable)')
    parser.add_argument('--model', default='qwen35b', help='cohort_model_path (default qwen35b)')
    parser.add_argument('--tasks-file', type=Path, default=Path('task_lists/ablation_30tasks.json'),
                        help='ABL-30 task list, used only to split the not-in-index count')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    abl_tasks = {t['instance_id'] if isinstance(t, dict) else t
                 for t in json.loads((root / args.tasks_file).read_text())}
    archives = [a.resolve(strict=True) for a in args.archive_root]
    main_base = Path('ICLR_results/swebench/main') / args.model
    abl_base = Path('ICLR_results/swebench/ablation') / args.model

    with args.rerun_csv.resolve(strict=True).open() as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames)
        main_rows = [r for r in reader if r['benchmark'] == 'swebench' and r['section'] == 'main'
                     and r['cohort_model_path'] == args.model]
    by_key = {}
    for r in main_rows:
        key = (r['cell'], r['task'], r['condition'], run_number(r['run']))
        assert key not in by_key, f'duplicate main row: {key}'
        by_key[key] = r

    cells = sorted(c for c in {r['cell'] for r in main_rows} if (root / abl_base / c).is_dir())
    selected, excluded, stats = [], [], {}
    missing_from_index = Counter()
    for cell in cells:
        index_path = root / abl_base / cell / 'experiment_results.json'
        abl_index = {r['key']: r for r in json.loads(index_path.read_text())}
        archived_index = {}
        for archive in archives:
            p = archive / main_base / cell / 'experiment_results.json'
            if p.is_file():
                for r in json.loads(p.read_text()):
                    archived_index.setdefault(r['key'], (archive.name, r))
        for key, row in by_key.items():
            if key[0] != cell:
                continue
            index_key = f"{row['task']}__{row['condition']}__r{key[3]}"
            if index_key not in abl_index:
                missing_from_index['ABL-30' if row['task'] in abl_tasks else 'not ABL-30'] += 1
                continue
            relative = abl_base / cell / row['task'] / row['condition'] / row['run']
            run_dir = root / relative
            candidate = dict(row, section='ablation', trajectory=str(run_dir / 'trajectory.json'),
                             seed_source_section='main', seed_source_trajectory=row['trajectory'], seed_archive='')

            def exclude(reason):
                excluded.append(dict(candidate, exclusion_reason=reason))

            if not all((run_dir / f).is_file() for f in CHECKED_FILES):
                exclude('ablation_copy_missing_files')
                continue
            match = None
            for archive in archives:
                archived_run = archive / main_base / cell / row['task'] / row['condition'] / row['run']
                if all((archived_run / f).is_file() for f in CHECKED_FILES) and \
                        all(sha256(archived_run / f) == sha256(run_dir / f) for f in CHECKED_FILES):
                    match = archive
                    break
            if match is None:
                exclude('ablation_copy_differs_from_archived_main')
                continue
            archived_row = archived_index.get(index_key)
            if archived_row is None or archived_row[1] != abl_index[index_key]:
                exclude('index_row_differs_from_archived_main')
                continue
            candidate['seed_archive'] = match.name
            selected.append(candidate)
            for f in CHECKED_FILES:
                st = (run_dir / f).stat()
                stats[str(relative / f)] = [st.st_size, st.st_mtime_ns]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    out_fields = fields + EXTRA_FIELDS
    with (out / 'rerun_runs_ablation_seeded.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(selected)
    with (out / 'rerun_runs_ablation_seeded_excluded.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=out_fields + ['exclusion_reason'])
        writer.writeheader()
        writer.writerows(excluded)
    (out / 'source_file_stats_ablation_seeded.json').write_text(json.dumps(stats, indent=1, sort_keys=True) + '\n')

    reasons = Counter(r['rerun_reason'] for r in selected)
    priorities = Counter(r['rerun_priority'] for r in selected)
    per_cell = Counter(r['cell'] for r in selected)
    lines = [
        'Ablation-side rerun rows for seeded copies of archived main runs',
        f'Generated: {datetime.now().astimezone().isoformat(timespec="seconds")}',
        f'Input: {args.rerun_csv}',
        f'Archive roots: {", ".join(str(a) for a in archives)}',
        f'Model: {args.model}; ablation cells with a main counterpart: {len(cells)}',
        '',
        f'Main rerun rows in those cells: {sum(1 for k in by_key if k[0] in cells)}',
        f'  ABL-30 task, not in ablation index (ablation resume runs them): {missing_from_index["ABL-30"]}',
        f'  NEW-70 task (no ablation counterpart; not rerun by the launcher): {missing_from_index["not ABL-30"]}',
        f'  selected (identical to archived main run):      {len(selected)}',
        f'  excluded:                                       {len(excluded)}',
    ]
    for reason, n in sorted(Counter(r['exclusion_reason'] for r in excluded).items()):
        lines.append(f'    {reason}: {n}')
    lines += ['', 'Selected by rerun_reason:'] + [f'  {k}: {v}' for k, v in sorted(reasons.items())]
    lines += ['Selected by rerun_priority:'] + [f'  {k}: {v}' for k, v in sorted(priorities.items())]
    lines += ['Selected by cell:'] + [f'  {k}: {v}' for k, v in sorted(per_cell.items())]
    lines += ['', 'Archive command (dry run; add --execute after stopping launchers):',
              '  venv/bin/python archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/archive_swebench_rerun_targets.py \\',
              f'    --rerun-csv {out / "rerun_runs_ablation_seeded.csv"} \\',
              f'    --source-stats {out / "source_file_stats_ablation_seeded.json"} \\',
              f'    --section ablation --cohort-model-path {args.model} \\']
    lines += [f'    --rerun-reason {k} \\' for k in sorted(reasons)]
    lines += ['    --archive-name swebench_summary_bug_ablation_seeded_<YYYYMMDD_HHMMSS>_CDT', '']
    (out / 'rerun_ablation_seeded_README.txt').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
