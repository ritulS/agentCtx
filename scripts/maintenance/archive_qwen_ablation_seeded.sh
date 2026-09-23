#!/usr/bin/env bash
# Archive the 476 audited Qwen SWE-bench ablation copies of affected main runs.
# Default: read-only dry run. Pass --execute to move runs and update indexes.
# Stop experiment AND reevaluation workers before --execute; keep them stopped
# until completion. The underlying archiver detects experiment runners, but
# does not detect every reevaluation entry point.
# Changed/missing audited files cause an error: do not bypass that check.
set -euo pipefail

case "${1:-}" in
    ""|--dry-run) mode=() ;;
    --execute) mode=(--execute) ;;
    -h|--help)
        echo "Usage: bash scripts/maintenance/archive_qwen_ablation_seeded.sh [--dry-run|--execute]"
        exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac
if (( $# > 1 )); then
    echo "Expected at most one argument." >&2
    exit 2
fi

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$WS"
PY="${PYTHON:-$WS/venv/bin/python3}"
AUDIT="$WS/archives/summary-bug-audit-20260907_185802_CDT/rerun-list"
ARCHIVER="$WS/archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/archive_swebench_rerun_targets.py"

# Refuse a changed cohort instead of silently expanding the requested scope.
"$PY" - "$AUDIT/rerun_runs_ablation_seeded.csv" <<'PY'
import csv
import sys

with open(sys.argv[1], newline="") as stream:
    rows = list(csv.DictReader(stream))
reasons = {
    "agentlog_summary_failure", "agentlog_uncorroborated",
    "agentlog_unverifiable", "summary_failure_accounting",
    "summary_related_response",
}
if len(rows) != 476 or any(
    row["benchmark"] != "swebench"
    or row["section"] != "ablation"
    or row["cohort_model_path"] != "qwen35b"
    or row["rerun_reason"] not in reasons
    or row["cell"].split("__")[:2] not in [
        [depth, budget] for depth in ("d05", "di")
        for budget in ("b10k", "b20k")
    ]
    for row in rows
):
    raise SystemExit("Audit cohort differs from the expected 476 Qwen ablation runs; aborting.")
PY

exec "$PY" "$ARCHIVER" \
    --root "$WS" \
    --rerun-csv "$AUDIT/rerun_runs_ablation_seeded.csv" \
    --source-stats "$AUDIT/source_file_stats_ablation_seeded.json" \
    --section ablation --cohort-model-path qwen35b \
    --rerun-reason agentlog_summary_failure \
    --rerun-reason agentlog_uncorroborated \
    --rerun-reason agentlog_unverifiable \
    --rerun-reason summary_failure_accounting \
    --rerun-reason summary_related_response \
    --archive-name "swebench_summary_bug_ablation_seeded_$(date +%Y%m%d_%H%M%S_%N)" \
    "${mode[@]}"
