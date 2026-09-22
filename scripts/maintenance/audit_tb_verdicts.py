#!/usr/bin/env python3
"""Audit Terminal-Bench result rows against the Harbor verdicts on disk.

Rows written before ``agentctx.benchmarks.tb_verdict`` recorded
``resolved=False`` whenever the verifier produced no reward, so trials that
were never graded (environment start failures, verifier timeouts, cancelled
jobs, tests-directory copy errors) look like task failures. This script
compares every row with the ``harbor_result.json`` saved next to its
trajectory and reports the discrepancies; with ``--write`` it rewrites those
rows to the current semantics (``resolved=None`` plus ``verdict_source``,
``harbor_exception`` and ``harbor_exception_message``) after backing up each
index file.

Read-only by default:

    python3 scripts/maintenance/audit_tb_verdicts.py
    python3 scripts/maintenance/audit_tb_verdicts.py --source-root ICLR_results/terminalbench2
    python3 scripts/maintenance/audit_tb_verdicts.py --write            # backs up, then rewrites
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agentctx.benchmarks.tb_verdict import VERDICT_FIELDS, trial_verdict  # noqa: E402

DEFAULT_ROOTS = (
    ROOT / "ICLR_results" / "terminalbench",
    ROOT / "ICLR_results" / "terminalbench2",
)
# Classifications that --write rewrites. Reward-file recoveries are listed
# but left to scripts/maintenance/replay_reverify_tb.py (plan/recover/apply), which keeps
# per-row evidence and backups for that change.
REWRITE = {"false_without_verdict", "verdict_missing_in_row"}


def run_dir(index: Path, row: dict) -> Path:
    return index.parent / str(row["instance_id"]) / str(row["condition"]) / f"run_{row.get('run_num', 1)}"


def classify(row: dict, harbor: dict | None) -> tuple[str, dict | None]:
    """Return (classification, verdict-fields-from-harbor)."""
    if harbor is None:
        return "no_harbor_result", None
    # Recovery-aware: a verifier timeout whose reward file exists counts as graded.
    verdict = trial_verdict(harbor)
    row_reward = row.get("reward")
    if verdict["reward"] is not None:
        if row_reward is not None and float(row_reward) == verdict["reward"] \
                and row.get("resolved") == verdict["resolved"]:
            return "verdict_ok", verdict
        if verdict.get("verdict_source") == "verifier_reward_file":
            return "reward_file_not_in_row", verdict
        return "verdict_missing_in_row", verdict
    # Harbor has no reward for this trial.
    if row_reward is not None:
        return "row_reward_without_harbor_reward", verdict
    if row.get("resolved") is False:
        return "false_without_verdict", verdict
    if row.get("resolved") is None:
        return "already_unverified", verdict
    return "true_without_verdict", verdict


def audit(index: Path) -> tuple[list[dict], list[tuple[int, str, dict]]]:
    rows = json.loads(index.read_text())
    if not isinstance(rows, list):
        raise SystemExit(f"expected a JSON list in {index}")
    findings = []
    for position, row in enumerate(rows):
        harbor_path = run_dir(index, row) / "harbor_result.json"
        harbor = None
        if harbor_path.exists():
            try:
                harbor = json.loads(harbor_path.read_text())
            except (OSError, ValueError):
                harbor = None
        kind, verdict = classify(row, harbor)
        findings.append((position, kind, verdict or {}))
    return rows, findings


def rewrite(rows: list[dict], findings, stamp: str) -> int:
    changed = 0
    for position, kind, verdict in findings:
        if kind not in REWRITE:
            continue
        row = rows[position]
        row.setdefault("verdict_audit", []).append({
            "audited_at": stamp,
            "reason": kind,
            "previous": {field: row.get(field) for field in VERDICT_FIELDS},
        })
        row.update(verdict)
        changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-root", type=Path, action="append", default=None,
                        help="result tree to scan (repeatable; default: ICLR_results/terminalbench and terminalbench2)")
    parser.add_argument("--write", action="store_true", help="rewrite discrepant rows after backing up each index file")
    parser.add_argument("--backup-dir", type=Path, default=None,
                        help="where index backups go (default: logs/tb_verdict_audit/<timestamp>)")
    parser.add_argument("--verbose", action="store_true", help="list every discrepant row")
    args = parser.parse_args()

    roots = [r if r.is_absolute() else ROOT / r for r in (args.source_root or list(DEFAULT_ROOTS))]
    roots = [r for r in roots if r.is_dir()]
    if not roots:
        raise SystemExit("no result tree found to audit")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = args.backup_dir or (ROOT / "logs" / "tb_verdict_audit" / stamp)

    totals = collections.Counter()
    by_exception = collections.Counter()
    per_file = {}
    for root in roots:
        for index in sorted(root.rglob("experiment_results.json")):
            rows, findings = audit(index)
            counts = collections.Counter(kind for _, kind, _ in findings)
            totals.update(counts)
            discrepant = [(p, k, v) for p, k, v in findings if k in REWRITE]
            for _, kind, verdict in discrepant:
                by_exception[(kind, verdict.get("harbor_exception") or "none")] += 1
            if discrepant:
                per_file[index] = counts
                if args.verbose:
                    for position, kind, verdict in discrepant:
                        row = rows[position]
                        print(f"  {index.relative_to(ROOT)} :: {row['key']}: {kind} "
                              f"({verdict.get('harbor_exception')}: {verdict.get('harbor_exception_message') or ''})")
            if args.write and discrepant:
                target = backup_dir / index.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(index.read_bytes())
                changed = rewrite(rows, findings, stamp)
                index.write_text(json.dumps(rows, indent=2))
                print(f"rewrote {changed} row(s): {index.relative_to(ROOT)} (backup: {target.relative_to(ROOT)})")

    print("\nRows by classification:")
    for kind, count in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {count:6d}  {kind}")
    if by_exception:
        print("\nDiscrepant rows by Harbor exception:")
        for (kind, exception), count in sorted(by_exception.items(), key=lambda kv: -kv[1]):
            print(f"  {count:6d}  {kind:26s} {exception}")
        print("\nFiles with discrepancies:")
        for index, counts in per_file.items():
            n = sum(counts[k] for k in REWRITE)
            print(f"  {n:4d}  {index.relative_to(ROOT)}")
    if not args.write and by_exception:
        print("\nRead-only audit. Re-run with --write to rewrite these rows (backups are kept).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
