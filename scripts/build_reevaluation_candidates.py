#!/usr/bin/env python3
"""Build a SWE-bench re-evaluation candidate list for one model (read-only scan).

Scans ICLR_results/swebench/<section>/<model>/*/experiment_results.json and the
harness artifacts next to them, and writes an evaluate_only CSV compatible with
scripts/reevaluate_swebench_candidates.py.

Included by default:
  stale_report_different_patch     eval cache patch.diff differs from the current submission
  evaluation_error_recorded_as_false
                                   resolved=False but the harness top-level report lists
                                   the instance under error_ids and the log shows no
                                   "Patch Apply Failed" (timeout / 409 / build error)
Optional (--include-unevaluated): resolved=None with a saved patch.
Counted but never included: resolved=False rows with no harness report at all
(provenance unknown), and genuine patch-apply failures.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
DEFAULT_TAG = {"devstral24b": "devstral-2", "qwen35b": "qwen35-a3b", "glm47flash": "glm47-flash"}
FIELDS = ["cell", "key", "task", "run_num", "action", "reason", "result_file",
          "timestamp", "resolved", "model_tag"]


def toplevel_report(eval_dir: Path, key: str) -> Path | None:
    """Exact-name match of <anything>.<key>.json (keys contain no dots)."""
    suffix = f".{key}.json"
    hits = sorted(p for p in eval_dir.glob("*.json") if p.name.endswith(suffix)
                  and p.name[:-len(suffix)].count(".") == 0)
    return hits[0] if hits else None


def instance_dir(eval_dir: Path, key: str, tag: str, instance_id: str) -> Path | None:
    base = eval_dir / "logs" / "run_evaluation" / key
    preferred = base / tag / instance_id
    if preferred.exists():
        return preferred
    if base.exists():
        for tag_dir in sorted(base.iterdir()):
            if (tag_dir / instance_id).exists():
                return tag_dir / instance_id
    return None


def classify(row: dict, cell_dir: Path, tag: str) -> str | None:
    eval_dir = cell_dir / "eval"
    inst = instance_dir(eval_dir, row["key"], tag, row["instance_id"])
    patch = inst / "patch.diff" if inst else None
    if patch and patch.exists() and patch.read_text() != row["submission"]:
        return "stale_report_different_patch"
    if row.get("resolved") is None:
        return "unevaluated"
    if row.get("resolved") is False:
        report = toplevel_report(eval_dir, row["key"])
        if report is None:
            return "no_toplevel_report"
        data = json.loads(report.read_text())
        if row["instance_id"] in data.get("error_ids", []):
            log = inst / "run_instance.log" if inst else None
            if log and log.exists() and APPLY_PATCH_FAIL in log.read_text(errors="replace"):
                return "genuine_patch_apply_failure"
            return "evaluation_error_recorded_as_false"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=sorted(DEFAULT_TAG))
    ap.add_argument("--model-tag", default=None)
    ap.add_argument("--section", default="main", choices=("main", "ablation"))
    ap.add_argument("--include-unevaluated", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    tag = args.model_tag or DEFAULT_TAG[args.model]
    base = ROOT / "ICLR_results" / "swebench" / args.section / args.model
    out = args.out or (ROOT / "ICLR_results" / "issue" /
                       f"reeval_candidates_{args.model}_{args.section}_{dt.date.today():%Y%m%d}" / "candidates.csv")
    include = {"stale_report_different_patch", "evaluation_error_recorded_as_false"}
    if args.include_unevaluated:
        include.add("unevaluated")

    rows, counts = [], collections.Counter()
    per_cell = collections.defaultdict(collections.Counter)
    for cell_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        index = cell_dir / "experiment_results.json"
        if not index.exists():
            continue
        for row in json.loads(index.read_text()):
            if "seeded_from" in row or not row.get("patch_generated") or not (row.get("submission") or "").strip():
                continue
            reason = classify(row, cell_dir, tag)
            if reason is None:
                continue
            counts[reason] += 1
            if reason in include:
                per_cell[cell_dir.name][reason] += 1
                rows.append({"cell": cell_dir.name, "key": row["key"], "task": row["instance_id"],
                             "run_num": row["run_num"], "action": "evaluate_only", "reason": reason,
                             "result_file": str(index.relative_to(ROOT)), "timestamp": row.get("timestamp", ""),
                             "resolved": row.get("resolved"), "model_tag": tag})

    print(f"{args.model}/{args.section} (tag {tag}): scanned classifications: {dict(counts)}")
    for cell in sorted(per_cell):
        print(f"  {cell}: {dict(per_cell[cell])}")
    if not rows:
        print("No candidates; nothing written.")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} evaluate_only candidates to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
