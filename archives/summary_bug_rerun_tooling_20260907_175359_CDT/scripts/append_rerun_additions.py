"""Append an additions file (rerun_runs.csv schema) to a rerun list, keeping a dated backup.

This is the 'update' step that follows attribute_tb_erasure.py (or attribute_agentlog.py):

    python append_rerun_additions.py --rerun-list rerun_list/rerun_runs.csv \
        --additions erasure-terminalbench/rerun_runs_tb_additions.csv --label tb-erasure

* Refuses to run if the two headers differ or if any addition's trajectory is already listed.
* Copies the current list to rerun_runs.before-<label>-update-<YYYYmmdd-HHMM>.csv first.
* Appends an 'Update history' line to rerun_README.txt next to the list, when that file exists.
* --dry-run prints what would happen and writes nothing.
"""
from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rerun-list", type=Path, required=True)
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--label", required=True, help="short tag used in the backup file name and README line")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    fields, rows = read_csv(args.rerun_list)
    add_fields, additions = read_csv(args.additions)
    if fields != add_fields:
        raise SystemExit(f"header mismatch:\n  list:      {fields}\n  additions: {add_fields}")
    listed = {r["trajectory"] for r in rows}
    dup = [a["trajectory"] for a in additions if a["trajectory"] in listed]
    if dup:
        raise SystemExit(f"{len(dup)} additions are already listed, e.g. {dup[0]}")
    inner = [t for t, n in Counter(a["trajectory"] for a in additions).items() if n > 1]
    if inner:
        raise SystemExit(f"{len(inner)} trajectories repeated inside the additions file, e.g. {inner[0]}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    backup = args.rerun_list.with_name(f"{args.rerun_list.stem}.before-{args.label}-update-{stamp}.csv")
    by_reason = Counter((a["rerun_priority"], a["rerun_reason"]) for a in additions)
    note = (f"- {stamp}: appended {len(additions)} rows from {args.additions.name} ({args.label}): "
            + ", ".join(f"{p}/{r}={n}" for (p, r), n in sorted(by_reason.items()))
            + f". {len(rows)} rows -> {len(rows) + len(additions)} rows. Previous file saved as {backup.name}.")
    print(note)
    if args.dry_run:
        print("dry run: nothing written")
        return

    shutil.copy2(args.rerun_list, backup)
    with args.rerun_list.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writerows(additions)
    readme = args.rerun_list.with_name("rerun_README.txt")
    if readme.exists():
        text = readme.read_text()
        if "Update history:" not in text:
            text = text.rstrip("\n") + "\n\nUpdate history:\n"
        readme.write_text(text.rstrip("\n") + "\n" + note + "\n")
    print(f"appended {len(additions)} rows to {args.rerun_list}; backup: {backup}")


if __name__ == "__main__":
    main()
