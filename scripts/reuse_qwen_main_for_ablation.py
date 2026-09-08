#!/usr/bin/env python3
"""Copy ABL-30 runs from Qwen's legacy main 10K/20K cells into ablation.

Dry run by default; add --execute to copy. Stop experiment writers before
execution. Sources are preserved. Existing destination cells are never replaced.
Result rows (including evaluation results) and complete run directories are
copied together; missing runs and summary-marker failures remain pending.
"""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


CONDITIONS = {
    'truncation': 'tr',
    'summarization': 'su-full',
    'summarization-partial': 'su-partial',
    'structured-summarize': 'ss',
    'structured-summarize-partial': 'ss-partial',
    'tool-result-clear': 'trc',
    'trc-su': 'trc-su',
    'trc-ss': 'trc-ss',
    'otrc-tr': 'otrc-tr',
    'otrc-su-partial': 'otrc-su-partial',
    'otrc-ss-partial': 'otrc-ss-partial',
}
SINGLES = set(list(CONDITIONS)[:5])


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def file_hashes(directory):
    require(directory.resolve() == directory, f'Symlinked source: {directory}')
    hashes = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), f'Symlink in run: {path}')
        if path.is_file():
            hashes[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def has_summary_marker_error(path):
    trajectory = json.loads(path.read_text())
    for message in trajectory.get('messages', []):
        extra = message.get('extra') or {}
        if extra.get('interrupt_type') != 'FormatError' and 'model_response' not in extra:
            continue
        response = extra.get('model_response', '')
        if not isinstance(response, str):
            response = json.dumps(response, ensure_ascii=False)
        if any(marker in response for marker in ('[CONTEXT SUMMARY]', '[COMPRESSED HISTORY SUMMARY]')):
            return True
    return False


def build_plan(root):
    tasks_file = root / 'task_lists/ablation_30tasks.json'
    tasks_raw = tasks_file.read_bytes()
    tasks = [r['instance_id'] for r in json.loads(tasks_raw)]
    require(len(tasks) == len(set(tasks)) == 30, 'Expected 30 unique ABL-30 tasks')
    require(all(Path(t).name == t and t not in {'.', '..'} for t in tasks), 'Invalid task ID')
    base = root / 'ICLR_results/swebench'
    plan = []
    for budget in (10000, 20000):
        for condition, primitive in CONDITIONS.items():
            depth = 'd05' if condition in SINGLES else 'di'
            cell = f'{depth}__b{budget // 1000}k__{primitive}'
            source = base / 'main/qwen35b' / cell
            destination = base / 'ablation/qwen35b' / cell
            require(not destination.exists() and not destination.is_symlink(), f'Destination already exists: {destination}')
            require(destination.resolve() == destination, f'Symlinked destination: {destination}')
            index = source / 'experiment_results.json'
            raw = index.read_bytes()
            rows = json.loads(raw)
            require(isinstance(rows, list), f'Expected list: {index}')
            by_key = {r['key']: r for r in rows}
            require(len(by_key) == len(rows), f'Duplicate keys: {index}')
            selected, runs, excluded = [], [], []
            for task in tasks:
                for number in (1, 2, 3):
                    key = f'{task}__{condition}__r{number}'
                    row = by_key.get(key)
                    relative = Path(task) / condition / f'run_{number}'
                    run = source / relative
                    if row is None or not (run / 'trajectory.json').is_file():
                        excluded.append({'key': key, 'reason': 'missing result row or trajectory'})
                        continue
                    require(row['instance_id'] == task and row['condition'] == condition
                            and row['run_num'] == number and row['budget'] == budget
                            and float(row.get('compression_ratio') or 0.5) == 0.5,
                            f'Conflicting metadata: {index}: {key}')
                    if has_summary_marker_error(run / 'trajectory.json'):
                        excluded.append({'key': key, 'reason': 'summary_marker_error'})
                        continue
                    selected.append(row)
                    runs.append((relative, file_hashes(run)))
            plan.append(dict(source=source, destination=destination, index_raw=raw,
                             rows=selected, runs=runs, excluded=excluded))
    return tasks_file, tasks_raw, plan


def execute(root, tasks_file, tasks_raw, plan):
    require(tasks_file.read_bytes() == tasks_raw, 'Task list changed; rerun dry-run')
    for cell in plan:
        require(not cell['destination'].exists(), f"Destination appeared: {cell['destination']}")
        require((cell['source'] / 'experiment_results.json').read_bytes() == cell['index_raw'],
                f"Source index changed: {cell['source']}")
    # Each cell is published only after its complete copy has been verified.
    for cell in plan:
        source, destination = cell['source'], cell['destination']
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.qwen-reuse-', dir=destination.parent) as tmp:
            staged = Path(tmp) / destination.name
            staged.mkdir()
            for relative, expected in cell['runs']:
                shutil.copytree(source / relative, staged / relative)
                require(file_hashes(staged / relative) == expected, f'Copy changed: {relative}')
                require(file_hashes(source / relative) == expected, f'Source changed: {relative}')
            require((source / 'experiment_results.json').read_bytes() == cell['index_raw'],
                    f'Source index changed: {source}')
            (staged / 'experiment_results.json').write_text(json.dumps(cell['rows'], indent=2) + '\n')
            manifest = dict(source_cell=str(source.relative_to(root)), cohort='ABL-30',
                            tasks_file=str(tasks_file.relative_to(root)),
                            tasks_sha256=hashlib.sha256(tasks_raw).hexdigest(),
                            source_index_sha256=hashlib.sha256(cell['index_raw']).hexdigest(),
                            copied_runs=len(cell['runs']), pending_runs=cell['excluded'],
                            run_sha256={str(relative): hashes for relative, hashes in cell['runs']})
            (staged / 'REUSE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
            require(not destination.exists() and not destination.is_symlink(), f'Destination appeared: {destination}')
            staged.rename(destination)
        print(f'Copied {len(cell["runs"]):2d} runs: {destination.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    tasks_file, tasks_raw, plan = build_plan(root)
    copied = sum(len(cell['runs']) for cell in plan)
    print(f'Cells: {len(plan)}; reusable runs: {copied}; pending runs: {len(plan) * 90 - copied}')
    if args.execute:
        execute(root, tasks_file, tasks_raw, plan)
        print('Complete. Source main cells preserved.')
    else:
        print('Dry run only; no files changed. Add --execute to copy.')


if __name__ == '__main__':
    main()
