#!/usr/bin/env python3
"""Build a SWE-bench re-evaluation candidate list for one model (read-only scan).

Scans ICLR_experiments/swebench/<section>/<model>/*/experiment_results.json and the
harness artifacts next to them, and writes an evaluate_only CSV compatible with
scripts/maintenance/reevaluate_swebench_candidates.py.

Machines that keep SWE-bench cells in the pre-ICLR layout
(results/ablations/<cell>/experiment_results.json, i.e. data/swebench/ablations)
pass the cell directory's parent instead:

    python3 scripts/maintenance/build_reevaluation_candidates.py \\
        --results-root results/ablations --model-tag qwen35-a3b --cell 'p100-*'

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
import fnmatch
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
DEFAULT_TAG = {"devstral24b": "devstral-2", "qwen35b": "qwen35-a3b", "glm47flash": "glm47-flash"}
FIELDS = ["cell", "key", "task", "run_num", "action", "reason", "result_file",
          "timestamp", "resolved", "model_tag"]


def display_path(path: Path) -> str:
    """Repo-relative when possible (what reevaluate_swebench_candidates expects)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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
    ap.add_argument("--model", default=None, choices=sorted(DEFAULT_TAG),
                    help="model directory under ICLR_experiments/swebench/<section>/ (ICLR layout)")
    ap.add_argument("--model-tag", default=None,
                    help="harness model_name_or_path; required with --results-root")
    ap.add_argument("--section", default="main", choices=("main", "ablation"))
    ap.add_argument("--results-root", type=Path, default=None,
                    help="directory whose subdirectories are cells with experiment_results.json "
                         "(e.g. results/ablations); replaces the ICLR_experiments/swebench layout")
    ap.add_argument("--cell", action="append", default=[], metavar="GLOB",
                    help="only scan cells whose directory name matches (repeatable)")
    ap.add_argument("--include-unevaluated", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    today = f"{dt.date.today():%Y%m%d}"
    if args.results_root is not None:
        if not args.model_tag:
            ap.error("--model-tag is required with --results-root")
        tag = args.model_tag
        base = args.results_root if args.results_root.is_absolute() else ROOT / args.results_root
        label = args.model or base.name
        out = args.out or (ROOT / "results" / "reeval" / f"candidates_{tag}_{today}" / "candidates.csv")
    else:
        if not args.model:
            ap.error("--model is required unless --results-root is given")
        tag = args.model_tag or DEFAULT_TAG[args.model]
        base = ROOT / "ICLR_experiments" / "swebench" / args.section / args.model
        label = f"{args.model}/{args.section}"
        out = args.out or (ROOT / "ICLR_experiments" / "issue" /
                           f"reeval_candidates_{args.model}_{args.section}_{today}" / "candidates.csv")
    if not base.is_dir():
        raise SystemExit(f"results directory not found: {base}")
    include = {"stale_report_different_patch", "evaluation_error_recorded_as_false"}
    if args.include_unevaluated:
        include.add("unevaluated")

    rows, counts = [], collections.Counter()
    per_cell = collections.defaultdict(collections.Counter)
    for cell_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if args.cell and not any(fnmatch.fnmatch(cell_dir.name, pattern) for pattern in args.cell):
            continue
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
                             "result_file": display_path(index), "timestamp": row.get("timestamp", ""),
                             "resolved": row.get("resolved"), "model_tag": tag})

    print(f"{label} (tag {tag}): scanned classifications: {dict(counts)}")
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
