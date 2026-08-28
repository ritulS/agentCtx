#!/usr/bin/env python3
"""Archive raw results and build the ICLR Qwen3.5-35B SWE-bench trees.

The raw experiment layout is split across ABL-30 and NEW-70 directories.  This
script copies complete P100 cells into ``main/qwen35b``, depth-ablation ABL-30
cells into ``ablation/qwen35b``, and rebuilds experiment_results.json.  Source
data is never removed or modified.

Typical use after run_run3_expansion.sh has completed:

  python scripts/archive_and_organize_qwen35b_swebench.py \
      --backup-root /path/on/another/disk/run3-complete-2026-09-01

Inspect without writing anything:

  python scripts/archive_and_organize_qwen35b_swebench.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "swebench" / "ablations"
ICLR_SWEBENCH = ROOT / "ICLR_results" / "swebench"
P100_TASKS_FILE = ROOT / "task_lists" / "p100_all_100_tasks.json"
ABL30_TASKS_FILE = ROOT / "task_lists" / "ablation_30tasks.json"
INF = 999_999_999

CONDITION_TO_PRIMITIVE = {
    "truncation": "tr",
    "summarization": "su-full",
    "summarization-partial": "su-partial",
    "structured-summarize": "ss",
    "structured-summarize-partial": "ss-partial",
    "tool-result-clear": "trc",
    "trc-su": "trc-su",
    "trc-ss": "trc-ss",
    "otrc-tr": "otrc-tr",
    "otrc-su-partial": "otrc-su-partial",
    "otrc-ss-partial": "otrc-ss-partial",
    "full-context": "fc",
    "online-trc": "otrc",
}

SINGLES = tuple(list(CONDITION_TO_PRIMITIVE)[:5])
TRC = ("tool-result-clear", "trc-su", "trc-ss")
OTRC = ("otrc-tr", "otrc-su-partial", "otrc-ss-partial")


@dataclass(frozen=True)
class Cell:
    section: str
    cohort: str
    depth: str
    budget: str
    condition: str
    sources: tuple[str, ...]

    @property
    def name(self) -> str:
        return f"{self.depth}__{self.budget}__{CONDITION_TO_PRIMITIVE[self.condition]}"

    @property
    def destination(self) -> Path:
        return ICLR_SWEBENCH / self.section / "qwen35b" / self.name

    @property
    def tasks_file(self) -> Path:
        return P100_TASKS_FILE if self.cohort == "P100" else ABL30_TASKS_FILE


def unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def cells() -> list[Cell]:
    out: list[Cell] = []
    for depth, tag, source_depth in (("0.3", "d03", "30"), ("0.5", "d05", "50"), ("0.7", "d07", "70")):
        for budget in (10_000, 15_000, 20_000):
            btag = f"b{budget // 1000}k"
            for cond in SINGLES:
                sources = [f"p100-depth{source_depth}-singles-{budget}"] if depth != "0.5" else [f"p100-singles-{budget}"]
                # Canonical-depth ABL-30 sources.  The p100 directory is kept
                # first because some historical runs were seeded into it.
                if depth == "0.5":
                    if budget in (10_000, 20_000) and cond in ("truncation", "summarization"):
                        sources.append(f"timing-{budget // 1000}k")
                    if cond in ("summarization-partial", "structured-summarize-partial"):
                        sources.append(f"partial-{budget}")
                    if cond == "structured-summarize" and budget in (10_000, 20_000):
                        sources.append(f"partial-{budget}")
                    if budget == 15_000 and cond in ("truncation", "summarization", "structured-summarize"):
                        sources.append("qwen3.5-35B-A3B_15k_Fullrun")
                # Tail depths are the ABL-30 depth ablation.  Canonical depth
                # cells are fully P100 and belong to main.
                section, cohort = ("main", "P100") if depth == "0.5" else ("ablation", "ABL-30")
                out.append(Cell(section, cohort, tag, btag, cond, unique(sources)))

    for budget in (10_000, 15_000, 20_000):
        btag = f"b{budget // 1000}k"
        for cond in TRC:
            sources = [f"p100-trc-{budget}"]
            if cond == "tool-result-clear":
                sources.append("qwen3.5-35B-A3B_15k_Fullrun" if budget == 15_000 else f"timing-{budget // 1000}k")
            else:
                sources.append(f"stacked-{budget}")
            out.append(Cell("main", "P100", "di", btag, cond, unique(sources)))
        for cond in OTRC:
            out.append(Cell("main", "P100", "di", btag, cond, (f"p100-otrc-{budget}", f"otrc-stacked-{budget}")))

    out.append(Cell("main", "P100", "di", "binf", "full-context", ("p100-inf", "qwen3.5-35B-A3B_15k_Fullrun")))
    out.append(Cell("main", "P100", "di", "binf", "online-trc", ("p100-inf", "qwen35-a3b_online-trc")))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backup-root", type=Path, help="new directory in which data/ and results/ are snapshotted")
    p.add_argument("--dry-run", action="store_true", help="validate and report only; write nothing")
    p.add_argument("--skip-backup", action="store_true", help="organize without first making a raw-data snapshot")
    p.add_argument("--allow-incomplete", action="store_true", help="copy incomplete cells too (marked in manifest; not recommended)")
    p.add_argument("--overwrite", action="store_true", help="replace existing canonical cell directories")
    return p.parse_args()


def task_ids(tasks_file: Path, expected: int) -> list[str]:
    payload = json.loads(tasks_file.read_text())
    ids = [row["instance_id"] for row in payload]
    if len(ids) != expected or len(set(ids)) != expected:
        raise SystemExit(f"expected {expected} unique tasks in {tasks_file}, found {len(set(ids))}")
    return ids


def source_run(cell: Cell, task: str, run: int) -> tuple[Path | None, str | None]:
    hits: list[tuple[Path, str]] = []
    for source in cell.sources:
        path = RAW / source / task / cell.condition / f"run_{run}"
        if (path / "trajectory.json").is_file():
            hits.append((path, source))
    if not hits:
        return None, None
    # Identical duplicate/seed paths are common. Prefer the first declared source.
    return hits[0]


def load_result(source: str, key: str) -> dict | None:
    path = RAW / source / "experiment_results.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list):
        return None
    return next(
        (
            row
            for row in payload
            if isinstance(row, dict) and row.get("key") == key
        ),
        None,
    )


def best_result(sources: tuple[str, ...], key: str) -> dict | None:
    """Prefer a full result row over the minimal rows used by seeded cells."""
    rows = [row for source in sources if (row := load_result(source, key)) is not None]
    return max(rows, key=lambda row: len(row), default=None)


def find_in_sources(sources: tuple[str, ...], subdir: str, patterns: tuple[str, ...]) -> Path | None:
    for source in sources:
        if found := find_named_file(source, subdir, patterns):
            return found
    return None


def find_named_file(source: str, subdir: str, patterns: tuple[str, ...]) -> Path | None:
    base = RAW / source / subdir
    if not base.is_dir():
        return None
    for pattern in patterns:
        found = sorted(base.glob(pattern))
        if found:
            return found[0]
    return None


def copy_run(src: Path, dst: Path) -> None:
    # Dereference compatibility symlinks so ICLR_results is self-contained.
    shutil.copytree(src, dst, symlinks=False, copy_function=shutil.copy2)


def backup(backup_root: Path, dry_run: bool) -> None:
    target = backup_root.expanduser().resolve()
    if target.exists():
        raise SystemExit(f"backup destination already exists: {target}")
    if ROOT == target or ROOT in target.parents:
        raise SystemExit("backup destination must be outside the workspace (avoids recursive backup)")
    print(f"Backup: {ROOT / 'data'} -> {target / 'data'}")
    print(f"Backup: {ROOT / 'results'} -> {target / 'results'}")
    if dry_run:
        return
    target.mkdir(parents=True)
    # Keep results' relative links; alongside the copied data/ they still resolve.
    shutil.copytree(ROOT / "data", target / "data", symlinks=True, copy_function=shutil.copy2)
    shutil.copytree(ROOT / "results", target / "results", symlinks=True, copy_function=shutil.copy2)
    metadata = {
        "created_at": datetime.now().astimezone().isoformat(),
        "workspace": str(ROOT),
        "contents": ["data", "results"],
    }
    (target / "SNAPSHOT.json").write_text(json.dumps(metadata, indent=2) + "\n")


def organize(args: argparse.Namespace) -> int:
    cohorts = {
        "P100": task_ids(P100_TASKS_FILE, 100),
        "ABL-30": task_ids(ABL30_TASKS_FILE, 30),
    }
    manifest: list[dict] = []
    incomplete = 0
    complete = 0

    for cell in cells():
        ids = cohorts[cell.cohort]
        expected_runs = len(ids) * 3
        resolved: list[tuple[str, int, Path, str]] = []
        missing: list[str] = []
        for task in ids:
            for run in (1, 2, 3):
                src, source = source_run(cell, task, run)
                if src is None or source is None:
                    missing.append(f"{task}__{cell.condition}__r{run}")
                else:
                    resolved.append((task, run, src, source))

        is_complete = not missing
        complete += int(is_complete)
        incomplete += int(not is_complete)
        status = "COMPLETE" if is_complete else f"INCOMPLETE missing={len(missing)}"
        label = f"{cell.section}/{cell.name}"
        print(f"{label:<44} {len(resolved):>3}/{expected_runs:<3}  {status}")
        record = {
            "section": cell.section,
            "cohort": cell.cohort,
            "cell": cell.name,
            "condition": cell.condition,
            "sources": list(cell.sources),
            "runs_found": len(resolved),
            "runs_expected": expected_runs,
            "complete": is_complete,
            "missing": missing,
        }
        manifest.append(record)
        if args.dry_run or (missing and not args.allow_incomplete):
            continue

        final = cell.destination
        stage = final.parent / f".{cell.name}.tmp-{os.getpid()}"
        if final.exists() and not args.overwrite:
            raise SystemExit(f"destination exists (use --overwrite): {final}")
        if stage.exists():
            raise SystemExit(f"staging directory already exists: {stage}")
        stage.mkdir(parents=True)
        rows: list[dict] = []
        provenance: list[dict] = []
        try:
            for task, run, src, source in resolved:
                key = f"{task}__{cell.condition}__r{run}"
                copy_run(src, stage / task / cell.condition / f"run_{run}")
                row = best_result(cell.sources, key) or {
                    "key": key, "instance_id": task,
                    "condition": cell.condition, "run_num": run,
                }
                rows.append(row)
                provenance.append({"key": key, "source": source})

                pred = find_in_sources(cell.sources, "preds", (f"preds_{key}.json", f"*{key}*.json"))
                if pred:
                    (stage / "preds").mkdir(exist_ok=True)
                    shutil.copy2(pred, stage / "preds" / f"preds_{key}.json")
                ev = find_in_sources(cell.sources, "eval", (f"qwen35-a3b.{key}.json", f"*{key}*.json"))
                if ev:
                    (stage / "eval").mkdir(exist_ok=True)
                    shutil.copy2(ev, stage / "eval" / f"qwen35-a3b.{key}.json")

            rows.sort(key=lambda row: row["key"])
            (stage / "experiment_results.json").write_text(json.dumps(rows, indent=2) + "\n")
            cell_info = {**record, "created_at": datetime.now().astimezone().isoformat(), "provenance": provenance}
            (stage / "ICLR_CELL_MANIFEST.json").write_text(json.dumps(cell_info, indent=2) + "\n")
            if final.exists():
                old = final.parent / f".{cell.name}.old-{os.getpid()}"
                final.rename(old)
                stage.rename(final)
                shutil.rmtree(old)
            else:
                stage.rename(final)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    print(f"\nComplete cells: {complete}; incomplete cells: {incomplete}")
    if not args.dry_run:
        summary = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "runs_per_task": 3,
            "task_lists": {
                "P100": {
                    "path": str(P100_TASKS_FILE.relative_to(ROOT)),
                    "sha256": hashlib.sha256(P100_TASKS_FILE.read_bytes()).hexdigest(),
                },
                "ABL-30": {
                    "path": str(ABL30_TASKS_FILE.relative_to(ROOT)),
                    "sha256": hashlib.sha256(ABL30_TASKS_FILE.read_bytes()).hexdigest(),
                },
            },
            "cells": manifest,
        }
        for section in ("main", "ablation"):
            destination = ICLR_SWEBENCH / section / "qwen35b"
            destination.mkdir(parents=True, exist_ok=True)
            section_summary = {**summary, "section": section,
                               "cells": [row for row in manifest if row["section"] == section]}
            (destination / "MANIFEST.json").write_text(json.dumps(section_summary, indent=2) + "\n")
    return 1 if incomplete and not args.allow_incomplete else 0


def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.skip_backup and args.backup_root is None:
        raise SystemExit("--backup-root is required unless --skip-backup or --dry-run is used")
    if args.backup_root is not None and not args.skip_backup:
        backup(args.backup_root, args.dry_run)
    code = organize(args)
    if code:
        print("\nIncomplete cells were not copied.", file=sys.stderr)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
