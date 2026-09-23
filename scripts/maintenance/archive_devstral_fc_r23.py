#!/usr/bin/env python3
"""Archive Devstral main FC@infinity run_2/3; dry run unless --execute.

Moves generation directories, predictions, top-level evaluation reports, and
internal per-run evaluation caches. Keeps run_1 and its calibration outputs.
Stop experiment/evaluation writers before executing. Does not start reruns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
CELL = Path("ICLR_experiments/swebench/main/devstral24b/di__binf__fc")


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n")
    tmp.replace(path)


def active_writers():
    names = {"run_experiment.py", "run_experiment_iclr.py",
             "run_agent_models_expansion.sh", "notify_run.sh",
             "reevaluate_swebench_candidates.py", "swebench.harness.run_evaluation",
             "minisweagent.run.benchmarks.swebench_single"}
    found = []
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            if proc.stat().st_uid != os.getuid() or int(proc.name) == os.getpid():
                continue
            args = (proc / "cmdline").read_bytes().decode(errors="replace").split("\0")
            if any("\n" not in arg and Path(arg).name in names for arg in args):
                found.append(proc.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return found


def fingerprint(path):
    """Hash files without following symlinks in evaluation log directories."""
    result = {}
    def visit(p):
        rel = str(p.relative_to(path.parent))
        if p.is_symlink():
            result[rel] = ["symlink", os.readlink(p)]
        elif p.is_file():
            result[rel] = ["file", hashlib.sha256(p.read_bytes()).hexdigest()]
        elif p.is_dir():
            result[rel] = ["directory"]
            for child in sorted(p.iterdir()):
                visit(child)
        else:
            raise RuntimeError(f"Unsupported or missing artifact: {p}")
    visit(path)
    return result


def build_plan(root, name):
    require(name not in {"", ".", ".."} and Path(name).name == name,
            "--archive-name must be a single directory name")
    archive = root / "archives" / name
    require(not archive.exists(), f"Archive already exists: {archive}")
    cell = root / CELL
    require(cell.resolve() == cell, "Refusing a symlinked source cell")
    index = cell / "experiment_results.json"
    raw = index.read_bytes()
    records = json.loads(raw)
    require(isinstance(records, list), "Expected a list result index")
    tasks = {r["instance_id"] for r in json.loads((root / "task_lists/p100_all_100_tasks.json").read_text())}
    require(tasks, "Empty task list")
    require(len({r["key"] for r in records}) == len(records), "Duplicate result keys")
    require(all(r["condition"] == "full-context" and r["budget"] == 999999999
                and r["key"] == f"{r['instance_id']}__full-context__r{r['run_num']}"
                for r in records), "Unexpected FC result metadata")
    require(len(records) == len(tasks) * 3 and
            {(r["instance_id"], r["run_num"]) for r in records} ==
            {(task, n) for task in tasks for n in (1, 2, 3)},
            "Expected complete run_1/2/3 coverage; refusing a partial or already-archived cell")
    selected = [r for r in records if r["run_num"] in (2, 3)]
    kept = [r for r in records if r["run_num"] == 1]
    moves = {}
    for row in selected:
        key = row["key"]
        directory = cell / row["instance_id"] / "full-context" / f"run_{row['run_num']}"
        require(directory.is_dir() and directory.resolve() == directory,
                f"Missing/symlinked run directory: {directory}")
        moves[directory] = "generation"
        pred = cell / "preds" / f"preds_{key}.json"
        if pred.exists():
            moves[pred] = "prediction"
        for report in (cell / "eval").glob("*.json"):
            if report.name == key + ".json" or report.name.endswith("." + key + ".json"):
                moves[report] = "evaluation_report"
        cache = cell / "eval/logs/run_evaluation" / key
        if cache.exists():
            moves[cache] = "evaluation_cache"
    for p in moves:
        require(not p.is_symlink() and p.resolve() == p, f"Symlinked move root: {p}")
    return {"root": root, "archive": archive, "index": index, "raw": raw,
            "selected": selected, "kept": kept, "moves": moves}


def execute(plan):
    root, archive, index = plan["root"], plan["archive"], plan["index"]
    live = active_writers()
    require(not live, f"Stop experiment/evaluation writers first. Detected PIDs: {', '.join(live)}")
    snapshots = {str(p.relative_to(root)): fingerprint(p) for p in plan["moves"]}
    require(index.read_bytes() == plan["raw"], "Result index changed while planning")
    require(not active_writers(), "An experiment/evaluation writer started while planning")
    archive.mkdir(parents=True, exist_ok=False)
    backup = archive / "before" / index.relative_to(root)
    backup.parent.mkdir(parents=True)
    backup.write_bytes(plan["raw"])
    write_json(archive / index.relative_to(root), plan["selected"])
    write_json(archive / "manifest.json", {
        "cell": str(CELL), "run_numbers": [2, 3], "selected_keys": [r["key"] for r in plan["selected"]],
        "index_rows_removed": len(plan["selected"]), "index_rows_kept": len(plan["kept"]),
        "moves": [{"path": str(p.relative_to(root)), "kind": kind} for p, kind in plan["moves"].items()]})
    write_json(archive / "source_fingerprints.json", snapshots)
    shutil.copy2(__file__, archive / "archive_operation.py")
    (archive / "README.md").write_text(
        "# Devstral FC run_2/3 archive\n\n"
        "Contains generation directories, predictions, evaluation reports and internal evaluation caches.\n"
        "The complete original result index is under before/; the selected-only index retains its canonical path.\n"
        "run_1 and run_1 calibration outputs were kept. Existing analysis CSVs were not updated.\n"
        "See manifest.json and status.json. To restore before any reruns, stop writers, move each manifest path\n"
        "back without overwriting a destination, then restore the index from before/. After reruns exist,\n"
        "reconcile rows individually instead of overwriting new results.\n")
    write_json(archive / "status.json", {"status": "in_progress"})
    moved = []
    new_index = (json.dumps(plan["kept"], indent=2) + "\n").encode()
    try:
        with (archive / "moves_completed.jsonl").open("w") as journal:
            for source in plan["moves"]:
                rel = str(source.relative_to(root))
                require(fingerprint(source) == snapshots[rel], f"Artifact changed: {source}")
                target = archive / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                require(not target.exists(), f"Archive destination exists: {target}")
                source.rename(target)
                moved.append((source, target))
                journal.write(json.dumps({"path": rel}) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
        for source, target in moved:
            require(fingerprint(target) == snapshots[str(source.relative_to(root))],
                    f"Archived artifact checksum mismatch: {target}")
        require(index.read_bytes() == plan["raw"], "Index changed; refusing to remove rows")
        write_json(index, plan["kept"])
        require(index.read_bytes() == new_index, "Index verification failed")
        write_json(archive / "status.json", {"status": "complete", "removed": len(plan["selected"]),
                                             "remaining": len(plan["kept"]), "moved_paths": len(moved)})
    except BaseException as exc:
        rollback_errors = []
        for source, target in reversed(moved):
            try:
                require(not source.exists(), f"Cannot overwrite new source: {source}")
                target.rename(source)
            except Exception as restore_error:
                rollback_errors.append(str(restore_error))
        if index.read_bytes() == new_index:
            tmp = index.with_name(index.name + ".rollback-tmp")
            tmp.write_bytes(plan["raw"])
            tmp.replace(index)
        write_json(archive / "status.json", {"status": "rollback_incomplete" if rollback_errors else "rolled_back",
                                             "error": str(exc), "rollback_errors": rollback_errors})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archive-name", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = build_plan(args.root.resolve(), args.archive_name)
    print(f"Archive: {plan['archive']}")
    print(f"Index rows: archive {len(plan['selected'])} (run_2/3); keep {len(plan['kept'])} (run_1)")
    from collections import Counter
    for kind, count in sorted(Counter(plan["moves"].values()).items()):
        print(f"  {kind}: {count}")
    if not args.execute:
        print("Dry run only. No files changed. Add --execute to archive.")
        return
    execute(plan)
    print("Archive complete. No reruns were launched; outcomes.csv was not changed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
