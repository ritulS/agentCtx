#!/usr/bin/env python3
"""Build an outcome CSV from Terminal-Bench 2.0 results.

Recursively collect experiment_results.json files below
ICLR_results/terminalbench2 into analysis/outcomes/terminalbench2_outcomes.csv.
All tasks, models, cells, and run numbers are included; no TB 1.0 task lists
or experiment grids are applied. Result paths should follow
<section>[/<namespace>]/<model>/<cell>/experiment_results.json.

The CSV schema and outcome classifications match aggregate_terminalbench_results.
Benchmark version and dataset are preserved from each input record.

Usage:
    python3 analysis/aggregate_terminalbench2_results.py
    python3 analysis/aggregate_terminalbench2_results.py --source-root /path/to/results
    python3 analysis/aggregate_terminalbench2_results.py --output /tmp/tb2.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

if __package__:
    from .aggregate_terminalbench_results import FIELDNAMES, ROOT, load_records, normalized_row
else:
    from aggregate_terminalbench_results import FIELDNAMES, ROOT, load_records, normalized_row


DEFAULT_SOURCE_ROOT = ROOT / "ICLR_results" / "terminalbench2"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "outcomes" / "terminalbench2_outcomes.csv"


def build(source_root: Path, output: Path) -> int:
    """Write all available runs and return the number of unreadable sources."""
    if not source_root.is_dir():
        raise SystemExit(f"input directory does not exist: {source_root}")

    sources = sorted(source_root.rglob("experiment_results.json"))
    rows: list[dict[str, Any]] = []
    bad_sources: list[str] = []
    for source in sources:
        try:
            rows.extend(
                normalized_row(row, source_root, source)
                for row in load_records(source)
            )
        except (OSError, ValueError) as exc:
            bad_sources.append(f"{source}: {exc}")

    rows.sort(key=lambda row: (
        row["experiment_section"], row["model_key"], row["cell"],
        row["task_name"], str(row["run_num"]), row["source_file"],
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"terminalbench2: wrote {len(rows):,} runs from {len(sources):,} files to {output}")
    for message in bad_sources:
        print(f"WARNING: skipped {message}")
    return len(bad_sources)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if build(args.source_root.resolve(), args.output.resolve()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
