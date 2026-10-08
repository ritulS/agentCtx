#!/usr/bin/env python3
"""List the tasks a model resolved in at least ``--min-resolved`` runs of one cell.

The complement of ``never_resolved_tasks.py``: reads ``<cell>/experiment_results.json``
below one or more model directories (so a P100 list can be built from the r2
``p30s`` and ``p100_minus_p30s`` sections together) and prints the tasks whose
evaluated runs in that cell resolved at least ``--min-resolved`` times (default
2, i.e. a 2-of-3 majority). A task is only considered when it has at least
``--min-runs`` runs (default 3) and none is still unevaluated (``resolved`` null).

The output follows the ``task_lists/swe_verified/`` schema (``instance_id``,
``repo``, ``difficulty``), in the order of ``--order`` (default: P100 order)
and falls back to sorted ids for tasks outside that list.

    venv/bin/python scripts/maintenance/majority_resolved_tasks.py \\
        data/r2/swebench/p30s/qwen35b data/r2/swebench/p100_minus_p30s/qwen35b \\
        --cell d05__b15k__tr \\
        -o task_lists/swe_verified/p100_qwen35b_tr_majority_resolved.json

This is how ``p100_qwen35b_tr_majority_resolved.json`` (cell ``d05__b15k__tr``)
and ``p100_qwen35b_su-free_majority_resolved.json`` (cell ``di__b15k__su-free``)
were produced (2026-10-08).
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from never_resolved_tasks import difficulties, load_rows  # noqa: E402

P100 = Path(__file__).resolve().parents[2] / "task_lists" / "swe_verified" / "p100_all_100_tasks.json"


def majority_resolved(model_dirs: list[Path], cell: str, min_runs: int, min_resolved: int) -> tuple[list[str], dict]:
    """Return (instance ids resolved >= min_resolved times, per-task verdict lists)."""
    verdicts: dict[str, list] = collections.defaultdict(list)
    for model_dir in model_dirs:
        for row in load_rows(model_dir / cell):
            verdicts[row["instance_id"]].append(row.get("resolved"))
    hits = []
    for task, vs in verdicts.items():
        if len(vs) >= min_runs and all(v is not None for v in vs) and sum(bool(v) for v in vs) >= min_resolved:
            hits.append(task)
    return hits, verdicts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_dirs", nargs="+", type=Path, help="e.g. data/r2/swebench/p30s/qwen35b data/r2/swebench/p100_minus_p30s/qwen35b")
    ap.add_argument("--cell", required=True, help="cell directory name, e.g. d05__b15k__tr")
    ap.add_argument("--min-runs", type=int, default=3, help="evaluated runs required per task")
    ap.add_argument("--min-resolved", type=int, default=2, help="resolved runs required per task")
    ap.add_argument("--order", type=Path, default=P100, help="task list giving the output order (default: P100)")
    ap.add_argument("--no-difficulty", action="store_true", help="do not look up difficulty in SWE-bench Verified")
    ap.add_argument("-o", "--output", type=Path, help="write the task list JSON here (stdout otherwise)")
    args = ap.parse_args()

    hits, verdicts = majority_resolved(args.model_dirs, args.cell, args.min_runs, args.min_resolved)
    order = [e["instance_id"] for e in json.loads(args.order.read_text())] if args.order else []
    rank = {t: i for i, t in enumerate(order)}
    hits.sort(key=lambda t: (rank.get(t, len(rank)), t))

    diff = {} if args.no_difficulty else difficulties(hits)
    entries = []
    for task in hits:
        entry = {"instance_id": task, "repo": task.split("__")[0]}
        if task in diff:
            entry["difficulty"] = diff[task]
        entries.append(entry)

    n_runs = [len(verdicts[t]) for t in hits]
    print(f"{len(verdicts)} tasks in cell {args.cell} across {len(args.model_dirs)} model dirs; "
          f"{len(hits)} resolved >= {args.min_resolved} times "
          f"({min(n_runs, default=0)}-{max(n_runs, default=0)} evaluated runs each)",
          file=sys.stderr)
    text = json.dumps(entries, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
