#!/usr/bin/env python3
"""
Repair the token_log.json -> experiment_results.json transcription.

`run_experiment.run_agent` copies the per-run token log into the result row at
the moment the run finishes.  Three things break that copy after the fact:

  1. A run directory is overwritten by a *later* execution (an interrupted
     sweep that was resumed, or a timed-out subprocess that kept writing after
     `proc.kill()`).  The row still describes the original execution, so the
     token log on disk no longer belongs to it.  These rows are left alone and
     marked `token_log_stale: true`.

  2. `seeded_from` stub rows carry no token fields at all even though a real
     token log sits in the run directory.  Those get backfilled and marked
     `token_log_backfilled: true`.

  3. Fields added to the harness after a sweep ran (`step_completion_tokens`,
     `online_trc_*`, `trc_truncation_fallback_events`) are simply absent from
     older rows.  Those get filled in from the log.

A row is only touched when the log is *verified* to belong to it: the three
cumulative token totals must match exactly.  Existing values are never
overwritten -- the script only fills fields that are missing.

Usage:
    python scripts/repair_token_log_transcription.py                 # dry run
    python scripts/repair_token_log_transcription.py --apply
    python scripts/repair_token_log_transcription.py --root data/swebench --apply
    python scripts/repair_token_log_transcription.py --report-csv /tmp/stale.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# token_log.json key -> experiment_results.json key, mirroring the result dict
# built in scripts/run_experiment.py::run_agent.  Order matters: new fields are
# appended to a row in this order.
FIELD_MAP: list[tuple[str, str, object]] = [
    # (token_log key, row key, harness default)
    ("total_prompt_tokens",              "total_prompt_tokens",              0),
    ("total_completion_tokens",          "total_completion_tokens",          0),
    ("total_tokens",                     "total_tokens",                     0),
    ("total_latency_s",                  "llm_latency_s",                    0.0),
    ("mean_latency_s",                   "mean_latency_s",                   0.0),
    ("step_prompt_tokens",               "step_prompt_tokens",               []),
    ("step_completion_tokens",           "step_completion_tokens",           None),
    ("compression_events",               "compression_events",               0),
    ("compression_event_steps",          "compression_event_steps",          []),
    ("context_tokens_at_compression",    "context_tokens_at_compression",    []),
    ("context_tokens_after_compression", "context_tokens_after_compression", []),
    ("total_tokens_saved",               "total_tokens_saved",               0),
    ("mean_compression_ratio",           "mean_compression_ratio",           1.0),
    ("summarization_prompt_tokens",      "summarization_prompt_tokens",      0),
    ("summarization_latency_s",          "summarization_latency_s",          0.0),
    ("trc_truncation_fallback_events",   "trc_truncation_fallback_events",   0),
    ("online_trc_total_tokens_saved",    "online_trc_total_tokens_saved",    0),
    ("online_trc_clears",                "online_trc_clears",                0),
    ("online_trc_flags",                 "online_trc_flags",                 []),
]

# The three cumulative totals that identify which execution a log belongs to.
IDENTITY_KEYS = ["total_prompt_tokens", "total_completion_tokens", "total_tokens"]

STALE_FLAG      = "token_log_stale"
BACKFILL_FLAG   = "token_log_backfilled"


def values_equal(a, b) -> bool:
    """Compare a token-log value with a recorded value, tolerating float noise."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-6)
    return a == b


def run_dir_for(cell: Path, row: dict) -> Path | None:
    task = row.get("instance_id") or row.get("task_name")
    cond = row.get("condition")
    run_num = row.get("run_num")
    if not task or not cond or run_num is None:
        return None
    return cell / str(task) / str(cond) / f"run_{run_num}"


def classify(row: dict, tok: dict | None) -> str:
    """verified | stale | stub | no_log | no_identity"""
    if tok is None:
        return "no_log"
    has_identity = all(k in row for k in IDENTITY_KEYS)
    if not has_identity:
        # No totals recorded at all.  A seeded stub, or a row written before
        # the token log existed; either way there is nothing to contradict.
        return "stub"
    for k in IDENTITY_KEYS:
        if not values_equal(tok.get(k, 0), row.get(k, 0)):
            return "stale"
    return "verified"


def repair_row(row: dict, tok: dict, kind: str) -> list[str]:
    """Fill missing token fields in `row` in place.  Returns the field names added."""
    added: list[str] = []
    if kind == "stale":
        if row.get(STALE_FLAG) is not True:
            row[STALE_FLAG] = True
            added.append(STALE_FLAG)
        return added

    for tok_key, row_key, default in FIELD_MAP:
        if row_key in row:
            continue
        row[row_key] = tok.get(tok_key, default)
        added.append(row_key)

    if kind == "stub" and added and row.get(BACKFILL_FLAG) is not True:
        row[BACKFILL_FLAG] = True
        added.append(BACKFILL_FLAG)
    return added


def write_json_atomic(path: Path, payload, backup: bool) -> None:
    if backup:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_bytes(path.read_bytes())
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, path)


def process_cell(cell: Path, apply: bool, backup: bool, stale_rows: list[dict]) -> Counter:
    stats = Counter()
    results_path = cell / "experiment_results.json"
    try:
        rows = json.loads(results_path.read_text())
    except (OSError, ValueError) as exc:
        print(f"WARNING: cannot read {results_path}: {exc}", file=sys.stderr)
        stats["unreadable_cell"] += 1
        return stats
    if not isinstance(rows, list):
        print(f"WARNING: {results_path} is not a list of rows", file=sys.stderr)
        stats["unreadable_cell"] += 1
        return stats

    changed = False
    seen_dirs: set[Path] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        stats["rows"] += 1
        rd = run_dir_for(cell, row)
        tok = None
        if rd is not None:
            seen_dirs.add(rd)
            log_path = rd / "token_log.json"
            if log_path.exists():
                try:
                    loaded = json.loads(log_path.read_text())
                    tok = loaded if isinstance(loaded, dict) else None
                    if tok is None:
                        print(f"WARNING: {log_path} is not an object", file=sys.stderr)
                except (OSError, ValueError) as exc:
                    print(f"WARNING: cannot read {log_path}: {exc}", file=sys.stderr)

        kind = classify(row, tok)
        stats[kind] += 1
        if tok is None:
            continue

        if kind == "stale":
            stale_rows.append({
                "cell": str(cell),
                "key": row.get("key", ""),
                "instance_id": row.get("instance_id", ""),
                "condition": row.get("condition", ""),
                "run_num": row.get("run_num", ""),
                "row_total_tokens": row.get("total_tokens"),
                "log_total_tokens": tok.get("total_tokens"),
                "row_steps": len(row.get("step_prompt_tokens") or []),
                "log_steps": len(tok.get("step_prompt_tokens") or []),
                "row_compression_events": row.get("compression_events"),
                "log_compression_events": tok.get("compression_events"),
                "exit_status": row.get("exit_status", ""),
                "returncode": row.get("returncode", ""),
            })

        added = repair_row(row, tok, kind)
        if added:
            changed = True
            stats[f"filled:{kind}"] += 1
            for f in added:
                stats[f"field:{f}"] += 1

    # Run directories with a token log that no row claims.
    for log_path in cell.rglob("token_log.json"):
        rd = log_path.parent
        if rd.parent.parent.parent == cell and rd not in seen_dirs:
            stats["orphan_log"] += 1

    if changed and apply:
        write_json_atomic(results_path, rows, backup)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", default=None,
                    help="Directory to scan for experiment_results.json "
                         "(repeatable; default: ICLR_results)")
    ap.add_argument("--apply", action="store_true",
                    help="Write the repairs. Without this the script only reports.")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip writing experiment_results.json.bak next to each edited file.")
    ap.add_argument("--report-csv", type=Path, default=None,
                    help="Write the list of stale (row/token_log mismatched) runs here.")
    args = ap.parse_args()

    roots = [Path(r) for r in (args.root or ["ICLR_results"])]
    roots = [r if r.is_absolute() else WORKSPACE_ROOT / r for r in roots]

    cells: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"WARNING: {root} does not exist, skipping", file=sys.stderr)
            continue
        cells.extend(sorted(p.parent for p in root.rglob("experiment_results.json")))
    if not cells:
        print("No experiment_results.json found.", file=sys.stderr)
        return 1

    total = Counter()
    per_cell: dict[str, Counter] = {}
    stale_rows: list[dict] = []
    for cell in cells:
        stats = process_cell(cell, args.apply, not args.no_backup, stale_rows)
        total.update(stats)
        # Every cell gets `verified` fills, so listing them all is noise.  Only
        # the cells needing attention are worth printing.
        if stats["stale"] or stats["stub"] or stats["no_log"] or stats["orphan_log"]:
            per_cell[str(cell)] = stats

    mode = "APPLIED" if args.apply else "DRY RUN (re-run with --apply to write)"
    print(f"\n=== token_log -> experiment_results transcription repair [{mode}] ===")
    print(f"cells scanned : {len(cells)}")
    print(f"rows scanned  : {total['rows']}")
    print()
    print("row classification")
    print(f"  verified (log matches row)      : {total['verified']}")
    print(f"  stale    (log is another run)   : {total['stale']}")
    print(f"  stub     (no totals recorded)   : {total['stub']}")
    print(f"  no_log   (no token_log on disk) : {total['no_log']}")
    if total["orphan_log"]:
        print(f"  token logs claimed by no row    : {total['orphan_log']}")

    filled = {k[len('filled:'):]: v for k, v in total.items() if k.startswith("filled:")}
    print("\nrows modified")
    if filled:
        for kind, n in sorted(filled.items(), key=lambda kv: -kv[1]):
            what = {"verified": "missing fields filled from log",
                    "stub":     "backfilled from log",
                    "stale":    f"marked {STALE_FLAG}"}.get(kind, kind)
            print(f"  {n:6d}  {kind:9s} — {what}")
    else:
        print("  (none — nothing to repair)")

    fields = {k[len('field:'):]: v for k, v in total.items() if k.startswith("field:")}
    if fields:
        print("\nfields written (row count)")
        for f, n in sorted(fields.items(), key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {f}")

    if per_cell:
        print("\ncells needing attention (stale / stub / missing logs)")
        for name, stats in sorted(per_cell.items()):
            bits = ", ".join(f"{k}={stats[k]}"
                             for k in ("stale", "stub", "no_log", "orphan_log") if stats[k])
            rel = Path(name)
            try:
                rel = rel.relative_to(WORKSPACE_ROOT)
            except ValueError:
                pass
            print(f"  {rel}: {bits}")

    if args.report_csv and stale_rows:
        args.report_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(stale_rows[0].keys()))
            w.writeheader()
            w.writerows(stale_rows)
        print(f"\nstale-run report: {args.report_csv} ({len(stale_rows)} rows)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
