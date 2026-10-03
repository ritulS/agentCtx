# Local SWE-bench summary-bug audit

Source: `/home/ak58925/agentCtx/ICLR_results` on local `akiho-expansion`.
Selection follows `archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md`.
Experiment files are read only; no runs were moved, no indexes were rewritten,
and no reruns were started.

## Outputs

- `archive_targets.csv`: **2,359** runs with `rerun_reason=summary_marker_error`.
  Includes the original rerun columns plus `result_index_status` (`recorded` or `missing`).
- `archive_target_summary.csv`: the same selection grouped by benchmark/section/model.
- `rerun-list/rerun_runs.csv`: **5,119** candidates: 2,359 marker cases,
  2,498 accounting cases, and 262 inferred response-content cases.
- `rerun-list/rerun_condition_summary.csv`: per-condition candidate counts.
- `audit-swebench/`: full error scan, metadata sources, rejected-response details,
  warnings, and counts. Scanned 22,979 trajectories, including 14,208 with recorded query errors.
- `review-swebench/`: classification of 8,239 unmarked summary-condition runs.
- `manual_review_inconsistent_counters.csv`: **55** unmarked runs with inconsistent
  success/call counters, conservatively classified as `not_established` and excluded
  from the rerun candidates. No accounting lower bound is asserted for these runs.
- `unindexed_archive_candidates.json`: the one marker candidate not present in its
  cell's `experiment_results.json` (GLM, main, `d05__bP__ss`,
  `sympy__sympy-16450`, `structured-summarize`, `run_2`). Its trajectory exists.
- `verification.json`: count, path, source-file stability, and existing-work checks.

| Model | main | ablation | total |
|---|---:|---:|---:|
| devstral24b | 256 | 511 | 767 |
| glm47flash | 29 | 0 | 29 |
| qwen35b | 1,133 | 430 | 1,563 |
| Total | 1,418 | 941 | 2,359 |

## Rebuild

Run from the repository root. Choose a fresh output directory for every scan/review.
The scripts require only Python's standard library.

```bash
tooling=archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts
audit_out="archives/summary-bug-audit-$(date +%Y%m%d_%H%M%S_%Z)"
venv/bin/python "$tooling/export_query_errors.py" \
  --source-root ICLR_results --output-dir "$audit_out/audit-swebench"
venv/bin/python "$tooling/review_unmarked_summary_errors.py" \
  --audit-dir "$audit_out/audit-swebench" --output-dir "$audit_out/review-swebench"
venv/bin/python "$tooling/build_rerun_runs.py" \
  --audit-dir "$audit_out/audit-swebench" --review-dir "$audit_out/review-swebench" \
  --output-dir "$audit_out/rerun-list"
venv/bin/python - "$audit_out" <<'PYCSV'
import csv, json, sys
from pathlib import Path
base = Path(sys.argv[1])
with (base / 'rerun-list/rerun_runs.csv').open() as stream:
    reader = csv.DictReader(stream)
    fields = reader.fieldnames + ['result_index_status']
    rows = [row for row in reader if row['rerun_reason'] == 'summary_marker_error']
indexes = {}
for row in rows:
    cell = Path(row['trajectory']).parents[3]
    if cell not in indexes:
        indexes[cell] = {r['key'] for r in json.loads((cell / 'experiment_results.json').read_text())}
    key = f"{row['task']}__{row['condition']}__r{int(row['run'].split('_')[1])}"
    row['result_index_status'] = 'recorded' if key in indexes[cell] else 'missing'
with (base / 'archive_targets.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
PYCSV
```

## Interpretation

A marker means a rejected response contains `[CONTEXT SUMMARY]` or
`[COMPRESSED HISTORY SUMMARY]` within a summary condition. This matches the
historical archive selection; it does not prove the origin of every individual call.
Unmarked accounting and content candidates are kept in the full rerun list,
not in `archive_targets.csv`.

SWE-bench metadata is read from the matching result-index row when `exit_info.json`
is absent. Legacy rows without primitive use the condition directory name.
There are no missing primitive values in the final error index. Scan warnings
comprise 13,200 missing `run_info.json` files (path fallback) and 404 incomplete
metadata cases (missing depth for non-summary conditions). No JSON read failures
were reported.

The archived `archive_rerun_targets.py` is a Terminal-Bench mover that requires
Harbor trial files. For SWE-bench use
`archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/archive_swebench_rerun_targets.py`.
See the tooling directory's `ARCHIVE_LOG.md` for preview and execution commands.
The SWE-bench script defaults to dry run and selects only `summary_marker_error`.
Generated files are under the repository's `archives/` directory.
