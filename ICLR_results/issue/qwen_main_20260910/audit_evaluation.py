"""Read-only audit of canonical Qwen main evaluation provenance."""
import collections
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'ICLR_results/swebench/main/qwen35b'
rows = []
fingerprints = {}
cells = []
for index in sorted(BASE.glob('*/experiment_results.json')):
    fingerprints[index] = hashlib.sha256(index.read_bytes()).hexdigest()
    results = json.loads(index.read_text())
    cell = index.parent
    cells.append({'cell': cell.name, 'runs': len(results), 'unique_keys': len({r['key'] for r in results})})
    for r in results:
        key, task = r['key'], r['instance_id']
        predfile = cell / 'preds' / f'preds_{key}.json'
        pred = json.loads(predfile.read_text()).get(task, {}) if predfile.exists() else {}
        tag = pred.get('model_name_or_path', '').replace('/', '__')
        dirs = sorted((cell / 'eval/logs/run_evaluation' / key).glob(f'*/{task}'))
        directory = cell / 'eval/logs/run_evaluation' / key / tag / task if tag else (dirs[0] if len(dirs) == 1 else None)
        report = directory / 'report.json' if directory else None
        patch = directory / 'patch.diff' if directory else None
        log = directory / 'run_instance.log' if directory else None
        report_exists = bool(report and report.exists())
        matching = bool(patch and patch.exists() and patch.read_text() == r.get('submission'))
        logtext = log.read_text(errors='replace') if log and log.exists() else ''
        data = json.loads(report.read_text()).get(task, {}) if report_exists else {}
        topfiles = sorted((cell / 'eval').glob(f'*.{key}.json'))
        topdata = [json.loads(p.read_text()) for p in topfiles]
        topflags = sorted({name for d in topdata for name in ('resolved_ids', 'unresolved_ids', 'error_ids', 'empty_patch_ids') if task in d.get(name, [])})
        verdict = data.get('resolved')
        action, reason = 'keep', 'matching_report'
        if not r.get('patch_generated'):
            reason = 'no_generated_patch'
        elif report_exists and not matching:
            action, reason = 'evaluate_only', 'report_patch_mismatch_or_missing'
        elif report_exists and not isinstance(verdict, bool):
            action, reason = 'evaluate_only', 'report_verdict_missing'
        elif report_exists and verdict != r.get('resolved'):
            action, reason = 'sync_result', 'index_report_verdict_mismatch'
        elif not report_exists:
            if matching and 'Patch Apply Failed' in logtext:
                reason = 'current_patch_apply_failure'
            elif 'invalid state' in logtext and '409' in logtext:
                action, reason = 'evaluate_only', 'evaluation_container_image_conflict'
            elif 'timed out' in logtext.lower() or 'timeout' in logtext.lower():
                action, reason = 'evaluate_only', 'evaluation_timeout_log'
            elif r.get('resolved') is None:
                action, reason = 'evaluate_only', 'evaluation_incomplete_report_missing'
            elif pred.get('model_patch') != r.get('submission'):
                action, reason = 'review', 'prediction_patch_mismatch_missing_internal_report'
            elif 'error_ids' in topflags:
                action, reason = 'review', 'legacy_evaluation_error_missing_log'
            elif ('resolved_ids' in topflags and r.get('resolved') is False) or ('unresolved_ids' in topflags and r.get('resolved') is True):
                action, reason = 'review', 'legacy_top_report_verdict_mismatch'
            elif 'resolved_ids' in topflags or 'unresolved_ids' in topflags:
                action, reason = 'review', 'legacy_summary_only_provenance_unverified'
            else:
                action, reason = 'review', 'legacy_evaluation_reports_missing'
        rows.append(dict(cell=cell.name, key=key, task=task, run_num=r['run_num'], timestamp=r.get('timestamp', ''),
                         resolved=r.get('resolved'), patch_generated=r.get('patch_generated'), action=action, reason=reason,
                         pred_matches=pred.get('model_patch') == r.get('submission'), patch_matches=matching,
                         report_exists=report_exists, report_resolved=verdict, report_mtime=report.stat().st_mtime if report_exists else '',
                         result_file=str(index.relative_to(ROOT)), prediction_file=str(predfile.relative_to(ROOT)),
                         evaluation_log_dir=str(directory.relative_to(ROOT)) if directory else '', report_count=len(dirs), top_flags=';'.join(topflags)))
for index, digest in fingerprints.items():
    assert hashlib.sha256(index.read_bytes()).hexdigest() == digest, f'Index changed during audit: {index}'
for name, subset in [('evaluation_classification.csv', rows), ('reevaluation_candidates.csv', [r for r in rows if r['action'] == 'evaluate_only']),
                     ('review_candidates.csv', [r for r in rows if r['action'] == 'review']),
                     ('result_sync_candidates.csv', [r for r in rows if r['action'] == 'sync_result'])]:
    with (OUT / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(subset)
summary = dict(total=len(rows), cells=cells, reasons=dict(collections.Counter(r['reason'] for r in rows)),
               candidates_by_cell=dict(collections.Counter(r['cell'] for r in rows if r['action'] == 'evaluate_only')),
               index_sha256={str(p.relative_to(ROOT)): h for p,h in fingerprints.items()})
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('cells','index_sha256')}, indent=2))
