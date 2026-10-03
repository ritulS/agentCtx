#!/usr/bin/env python3
"""List the tasks a model never resolved in a set of r2 (or ICLR-layout) cells.

Reads every ``<cell>/experiment_results.json`` below one model directory, e.g.
``data/r2/swebench/p100_minus_p30s/qwen35b`` (cells ``di__binf__fc``,
``d05__b15k__tr``, ``di__b15k__su-free``, ``di__b15k__trc``), and prints the
tasks whose every evaluated run is unresolved. A task is only listed when every
cell holds at least ``--min-runs`` evaluated runs for it (default 3) and no run
is still unevaluated (``resolved`` null), so a half-finished chain cannot make a
task look never-resolved.

The output follows the ``task_lists/swe_verified/`` schema
(``instance_id``, ``repo``, ``difficulty``); the difficulty comes from the
locally cached SWE-bench Verified dataset (``--no-difficulty`` to skip it).

    venv/bin/python scripts/maintenance/never_resolved_tasks.py \\
        data/r2/swebench/p100_minus_p30s/qwen35b \\
        --cells di__binf__fc d05__b15k__tr di__b15k__su-free di__b15k__trc \\
        -o task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json

This is how ``p100_minus_p30s_qwen35b_never_resolved.json`` was produced
(2026-10-02); ``p30s_qwen35b_never_resolved.json`` has the same definition.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys


def load_rows(cell_dir: Path) -> list[dict]:
    path = cell_dir / "experiment_results.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    data = json.loads(path.read_text())
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return [r for r in rows if r.get("instance_id")]


def never_resolved(model_dir: Path, cells: list[str], min_runs: int) -> tuple[list[str], dict]:
    """Return (sorted never-resolved instance ids, per-task per-cell verdict lists)."""
    verdicts: dict[str, dict[str, list]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for cell in cells:
        for row in load_rows(model_dir / cell):
            verdicts[row["instance_id"]][cell].append(row.get("resolved"))
    never = []
    for task, per_cell in sorted(verdicts.items()):
        complete = all(len(per_cell[c]) >= min_runs for c in cells)
        evaluated = all(v is not None for vs in per_cell.values() for v in vs)
        resolved = any(bool(v) for vs in per_cell.values() for v in vs)
        if complete and evaluated and not resolved:
            never.append(task)
    return never, verdicts


def difficulties(instance_ids: list[str]) -> dict[str, str]:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("[warn] `datasets` not installed; difficulty omitted", file=sys.stderr)
        return {}
    try:
        ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    except Exception as exc:  # noqa: BLE001 - offline cache miss, network, ...
        print(f"[warn] SWE-bench Verified not loadable ({exc}); difficulty omitted", file=sys.stderr)
        return {}
    wanted = set(instance_ids)
    return {r["instance_id"]: r["difficulty"] for r in ds if r["instance_id"] in wanted}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_dir", type=Path, help="e.g. data/r2/swebench/p100_minus_p30s/qwen35b")
    ap.add_argument("--cells", nargs="+", default=["di__binf__fc", "d05__b15k__tr", "di__b15k__su-free", "di__b15k__trc"])
    ap.add_argument("--min-runs", type=int, default=3, help="evaluated runs required per cell per task")
    ap.add_argument("--no-difficulty", action="store_true", help="do not look up difficulty in SWE-bench Verified")
    ap.add_argument("-o", "--output", type=Path, help="write the task list JSON here (stdout otherwise)")
    args = ap.parse_args()

    never, verdicts = never_resolved(args.model_dir, args.cells, args.min_runs)
    diff = {} if args.no_difficulty else difficulties(never)
    entries = []
    for task in never:
        entry = {"instance_id": task, "repo": task.split("__")[0]}
        if task in diff:
            entry["difficulty"] = diff[task]
        entries.append(entry)

    n_runs = {t: sum(len(v) for v in verdicts[t].values()) for t in never}
    print(f"{len(verdicts)} tasks in {args.model_dir} across {len(args.cells)} cells; "
          f"{len(never)} never resolved "
          f"({min(n_runs.values(), default=0)}-{max(n_runs.values(), default=0)} evaluated runs each)",
          file=sys.stderr)
    text = json.dumps(entries, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
