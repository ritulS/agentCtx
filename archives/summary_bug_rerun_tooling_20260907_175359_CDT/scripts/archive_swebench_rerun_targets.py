#!/usr/bin/env python3
"""Archive SWE-bench summary-marker runs and remove their result-index rows.

Dry run by default. Stop experiment launchers/workers before --execute, and keep
them stopped until completion. Originals of every affected result index, the
selected CSV, and a move journal are retained in the archive.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_runners():
    names = {"run_experiment.py", "run_experiment_iclr.py",
             "run_agent_models_expansion.sh", "run_agent_models_expansion_notified.sh"}
    found = []
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if process.stat().st_uid != os.getuid():
                continue
            args = (process / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            if any(Path(arg).name in names for arg in args if '\n' not in arg):
                found.append(process.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--rerun-csv', type=Path, required=True)
    parser.add_argument('--archive-name', required=True, help='New directory name under archives/')
    parser.add_argument('--cohort-model-path', help='Optional model filter')
    parser.add_argument('--section', choices=['main', 'ablation'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    require(Path(args.archive_name).name == args.archive_name and args.archive_name not in {'.', '..'},
            'archive-name must be a single directory name')
    archive = root / 'archives' / args.archive_name
    require(not archive.exists(), f'Archive already exists: {archive}')
    csv_path = args.rerun_csv.resolve(strict=True)
    with csv_path.open() as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        selected = [r for r in reader if r['benchmark'] == 'swebench'
                    and r['rerun_reason'] == 'summary_marker_error'
                    and (not args.cohort_model_path or r['cohort_model_path'] == args.cohort_model_path)
                    and (not args.section or r['section'] == args.section)]
    require(selected, 'No SWE-bench summary_marker_error rows matched')
    cells, moves, manifest, hashes = {}, [], [], {}
    for row in selected:
        relative = Path('ICLR_results/swebench') / row['section'] / row['cohort_model_path'] / row['cell'] / row['task'] / row['condition'] / row['run']
        run = root / relative
        require(run.resolve().is_relative_to(root / 'ICLR_results/swebench'), f'Outside source tree: {run}')
        require(run.resolve() == run and run.is_dir(), f'Missing or symlinked run: {run}')
        require((run / 'trajectory.json') == Path(row['trajectory']), f'CSV path mismatch: {run}')
        require(run not in moves, f'Duplicate run: {run}')
        trajectory = json.loads((run / 'trajectory.json').read_text())
        markers = 0
        for message in trajectory.get('messages', []):
            extra = message.get('extra') or {}
            if extra.get('interrupt_type') != 'FormatError' and 'model_response' not in extra:
                continue
            response = extra.get('model_response', '')
            if not isinstance(response, str):
                response = json.dumps(response, ensure_ascii=False)
            markers += any(m in response for m in ('[CONTEXT SUMMARY]', '[COMPRESSED HISTORY SUMMARY]'))
        require(markers > 0 and markers == int(row['summary_marker_errors']), f'Stale marker evidence: {run}')
        cell = run.parents[2]
        index = cell / 'experiment_results.json'
        if cell not in cells:
            raw = index.read_bytes()
            records = json.loads(raw)
            require(isinstance(records, list), f'Invalid index: {index}')
            by_key = {r['key']: r for r in records}
            require(len(by_key) == len(records), f'Duplicate index keys: {index}')
            cells[cell] = dict(index=index, raw=raw, records=records, by_key=by_key, selected=set())
        info = cells[cell]
        key = f"{row['task']}__{row['condition']}__r{int(row['run'].removeprefix('run_'))}"
        info['selected'].add(key)
        # Missing result rows still have run artifacts to preserve.
        manifest.append(dict(row, result_index_status='recorded' if key in info['by_key'] else 'missing',
                             source_run_dir=str(relative), key=key))
        moves.append(run)
        for path in run.rglob('*'):
            require(not path.is_symlink(), f'Symlink in run: {path}')
            if path.is_file():
                hashes[str(path.relative_to(root))] = digest(path)
    removed = sum(len(c['selected'] & c['by_key'].keys()) for c in cells.values())
    counts = Counter((r['cohort_model_path'], r['section']) for r in manifest)
    print(f'Archive: {archive}')
    print(f'Runs: {len(moves)}; cells: {len(cells)}; index rows to remove: {removed}; unindexed runs: {len(moves)-removed}')
    for (model, section), count in sorted(counts.items()):
        print(f'  {model} / {section}: {count}')
    live = active_runners()
    if live:
        print('Stop SWE-bench launchers/workers before executing. Detected PIDs: ' + ', '.join(live))
    if not args.execute:
        print('Dry run only; no files changed. Add --execute to apply.')
        return
    require(not live, 'Active experiment processes detected; stop them before --execute')
    for c in cells.values():
        require(c['index'].read_bytes() == c['raw'], f"Index changed: {c['index']}")
    for name, expected in hashes.items():
        require(digest(root / name) == expected, f'Run file changed: {name}')

    archive.mkdir(parents=True, exist_ok=False)
    (archive / 'rerun_source').mkdir()
    shutil.copy2(csv_path, archive / 'rerun_source' / 'input.csv')
    with (archive / 'rerun_source' / 'selected_rows.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    for c in cells.values():
        relative = c['index'].relative_to(root)
        backup = archive / 'before' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(c['raw'])
        archived_index = archive / relative
        archived_index.parent.mkdir(parents=True, exist_ok=True)
        archived_index.write_text(json.dumps([r for r in c['records'] if r['key'] in c['selected']], indent=2) + '\n')
    (archive / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (archive / 'source_sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    shutil.copy2(__file__, archive / 'archive_operation.py')
    (archive / 'README.md').write_text(
        f'# SWE-bench summary-marker archive\n\nCreated: {datetime.now().astimezone().isoformat()}\n\n'
        f'Selected {len(moves)} runs; {removed} result-index rows will be removed.\n'
        'See status.json for completion status and moves_completed.jsonl for completed moves.\n'
        'Original indexes are in before/. Run directories retain workspace-relative paths.\n'
        'To restore before any reruns: stop workers, move archived run directories back without\n'
        'overwriting existing paths, and restore original indexes from before/.\n'
        'If new runs have since completed, reconcile indexes instead of overwriting them.\n')
    (archive / 'status.json').write_text(json.dumps({'status': 'in_progress'}) + '\n')
    with (archive / 'moves_completed.jsonl').open('w') as journal:
        for run in moves:
            destination = archive / run.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            require(not destination.exists(), f'Destination exists: {destination}')
            run.rename(destination)
            journal.write(json.dumps({'source': str(run), 'destination': str(destination)}) + '\n')
            journal.flush()
            os.fsync(journal.fileno())
    for c in cells.values():
        require(c['index'].read_bytes() == c['raw'], f"Index changed; backups retained: {c['index']}")
        kept = [r for r in c['records'] if r['key'] not in c['selected']]
        temp = c['index'].with_suffix('.json.archive-tmp')
        with temp.open('x') as stream:
            stream.write(json.dumps(kept, indent=2) + '\n')
        temp.replace(c['index'])
    for name, expected in hashes.items():
        require(digest(archive / name) == expected, f'Archive checksum mismatch: {name}')
    require(all(not run.exists() for run in moves), 'Some source runs remain')
    remaining = sum(len(json.loads(c['index'].read_text())) for c in cells.values())
    require(remaining == sum(len(c['records']) for c in cells.values()) - removed, 'Index count mismatch')
    (archive / 'status.json').write_text(json.dumps({'status': 'complete', 'runs': len(moves), 'removed_index_rows': removed}, indent=2) + '\n')
    print(f'Archived {len(moves)} runs; removed {removed} index rows. Backups: {archive}')


if __name__ == '__main__':
    main()
