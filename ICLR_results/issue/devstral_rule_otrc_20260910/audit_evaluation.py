"""Read-only evaluation provenance checks for the six cells in summary.json.

Run after audit_generation.py and before classify_evaluation.py. Writes only
diagnostic CSV/JSON files in this audit directory, never benchmark results.
"""
import csv
import datetime as dt
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
summary = json.loads((OUT / 'summary.json').read_text())
rows = []
issues = []
for cell in summary['cells']:
    base = ROOT / 'ICLR_results/swebench/main/devstral24b' / cell['cell']
    for result in json.loads((base / 'experiment_results.json').read_text()):
        if not result['patch_generated']:
            continue
        row = {k: result[k] for k in ['key', 'resolved', 'timestamp']}
        row = {'cell': cell['cell'], **row}
        prediction = base / 'preds' / f"preds_{result['key']}.json"
        tag = 'devstral-2'
        row['pred_matches'] = False
        if prediction.exists():
            pred = json.loads(prediction.read_text())[result['instance_id']]
            tag = pred['model_name_or_path']
            row['pred_matches'] = pred['model_patch'] == result['submission']
        directory = base / 'eval/logs/run_evaluation' / result['key'] / tag.replace('/', '__') / result['instance_id']
        patch = directory / 'patch.diff'
        report = directory / 'report.json'
        row['report_exists'] = report.exists()
        row['patch_matches'] = patch.exists() and patch.read_text() == result['submission']
        row['report_time'] = dt.datetime.fromtimestamp(report.stat().st_mtime).isoformat() if report.exists() else ''
        row['report_after_attempt'] = row['report_time'] >= result['timestamp'] if report.exists() else False
        row['report_resolved'] = json.loads(report.read_text()).get(result['instance_id'], {}).get('resolved') if report.exists() else None
        rows.append(row)
        if not all(row[k] for k in ['pred_matches', 'report_exists', 'patch_matches', 'report_after_attempt']) or row['resolved'] != row['report_resolved']:
            issues.append(row)
with (OUT / 'evaluation_checks.csv').open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
(OUT / 'evaluation_issues.json').write_text(json.dumps(issues, indent=2))
print(f'Checked {len(rows)} submitted patches; {len(issues)} need classification.')
