#!/usr/bin/env python3
"""Move selected rerun targets out of the canonical ICLR results tree.

Reads rerun_runs.csv from the query-error audit, selects rows by rerun reason
and cohort, and moves each selected run so that the normal launcher
(scripts/run_agent_models_expansion_tb.sh) treats it as not yet executed.

The Terminal-Bench runner decides what to run only from the keys recorded in
each cell's experiment_results.json (see TerminalBenchAdapter.run_experiments).
So for every selected run this script:

1. removes its row from <cell>/experiment_results.json (atomic rewrite),
2. moves <cell>/<task>/<condition>/run_<n>/ into the archive,
3. moves the raw Harbor trial directory <job>/<trial_name>/ into the archive.

Everything is moved with the same path relative to --root, exactly like the
earlier archives/devstral_since_20260905_145630_CDT operation. The archive
also stores the untouched experiment_results.json files (before/), a manifest,
a move journal, and a README. Nothing is deleted.

Default mode is a dry run. Pass --execute to apply.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
RUN_FILES = ("trajectory.json", "token_log.json", "exit_info.json", "agent.log", "harbor_result.json")


def parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, value
    return parsed


LAUNCHER_KEYS = {"qwen35b": "qwen", "devstral24b": "devstral", "glm47flash": "glm"}


def runner_processes(model_key: str) -> list[str]:
    """Return command lines of live runners for this cohort (must be none)."""
    try:
        out = subprocess.run(["pgrep", "-af", "run_experiment_iclr.py|run_agent_models_expansion_tb.sh"],
                             capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return []
    launcher = LAUNCHER_KEYS.get(model_key, model_key)
    return [line for line in out.splitlines()
            if f"--iclr-model {model_key} " in line
            or f"expansion_tb.sh {launcher}" in line or "expansion_tb.sh all" in line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rerun-csv", type=Path,
                        default=Path(__file__).resolve().parent.parent / "results/query-error-audit-20260907/rerun_runs.csv")
    parser.add_argument("--root", type=Path, default=Path("/home/ak58925/agentCtx"),
                        help="Workspace that owns ICLR_results/ and logs/ (the runtime tree)")
    parser.add_argument("--cohort-model-path", default="devstral24b",
                        help="Value of the cohort_model_path column to select (ICLR_results/<benchmark>/<section>/<this>)")
    parser.add_argument("--rerun-reason", nargs="+", default=["summary_marker_error"],
                        help="rerun_reason values to select")
    parser.add_argument("--section", nargs="+", default=None, help="Optional section filter (main/ablation)")
    parser.add_argument("--archive-name", default=None,
                        help="Directory name under <root>/archives (default: <cohort>_<reason>_<timestamp>_CDT)")
    parser.add_argument("--execute", action="store_true", help="Apply the moves (default: dry run)")
    parser.add_argument("--allow-running", action="store_true",
                        help="Do not abort when a runner for this cohort is alive")
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    results_root = root / "ICLR_results"
    now = datetime.now(TZ)
    name = args.archive_name or (
        f"{args.cohort_model_path}_{'-'.join(args.rerun_reason)}_{now:%Y%m%d_%H%M%S}_CDT"
    )
    archive = root / "archives" / name
    csv_path = args.rerun_csv.resolve(strict=True)

    live = runner_processes(args.cohort_model_path)
    if live and not args.allow_running:
        sys.exit("A runner for this cohort is alive; refusing to move its results:\n" + "\n".join(live))

    with csv_path.open() as stream:
        all_rows = list(csv.DictReader(stream))
    selected_rows = [
        r for r in all_rows
        if r["cohort_model_path"] == args.cohort_model_path
        and r["rerun_reason"] in set(args.rerun_reason)
        and (args.section is None or r["section"] in set(args.section))
    ]
    if not selected_rows:
        sys.exit("No rows matched the selection.")

    # ── Plan ────────────────────────────────────────────────────────────────
    cells: dict[Path, dict] = {}
    manifest = []
    moves: list[Path] = []
    for r in selected_rows:
        trajectory = Path(r["trajectory"])
        run_dir = trajectory.parent
        assert run_dir.is_relative_to(results_root), f"outside ICLR_results: {run_dir}"
        assert run_dir.is_dir(), f"missing run dir: {run_dir}"
        assert run_dir.name == r["run"] and run_dir.parent.name == r["condition"], run_dir
        cell_dir = run_dir.parents[2]
        assert cell_dir.name == r["cell"], (cell_dir, r["cell"])
        assert run_dir.parent.parent.relative_to(cell_dir) == Path(r["task"]), run_dir
        run_num = int(r["run"].split("_")[1])
        key = f"{r['task']}__{r['condition']}__r{run_num}"

        cell = cells.get(cell_dir)
        if cell is None:
            path = cell_dir / "experiment_results.json"
            rows = json.loads(path.read_text())
            assert isinstance(rows, list), path
            cell = cells[cell_dir] = {"path": path, "rows": rows,
                                      "by_key": {x["key"]: x for x in rows}, "selected_keys": set()}
            assert len(cell["by_key"]) == len(rows), f"duplicate keys in {path}"
        row = cell["by_key"].get(key)
        assert row is not None, f"{key} not recorded in {cell['path']}; nothing to un-record"
        assert key not in cell["selected_keys"], f"duplicate CSV row for {key}"
        cell["selected_keys"].add(key)

        harbor = json.loads((run_dir / "harbor_result.json").read_text())
        trial_dir = Path(harbor["config"]["trials_dir"]) / harbor["trial_name"]
        assert trial_dir.is_relative_to(root / "logs"), trial_dir
        assert trial_dir.is_dir(), f"missing Harbor trial dir: {trial_dir}"
        assert harbor["task_name"] == r["task"], (harbor["task_name"], r["task"])
        assert parse_ts(row["timestamp"]) == parse_ts(harbor["started_at"]), key

        moves.extend((run_dir, trial_dir))
        manifest.append({
            "benchmark": r["benchmark"], "section": r["section"],
            "cohort_model_path": r["cohort_model_path"], "cell": r["cell"], "key": key,
            "task": r["task"], "condition": r["condition"], "run": run_num,
            "primitive": r["primitive"], "budget_tokens": r["budget_tokens"], "depth": r["depth"],
            "rerun_reason": r["rerun_reason"], "rerun_priority": r["rerun_priority"],
            "summary_marker_errors": r["summary_marker_errors"],
            "exit_status": row.get("exit_status", ""), "resolved": row.get("resolved"),
            "started_at_CDT": parse_ts(row["timestamp"]).astimezone(TZ).isoformat(),
            "source_run_dir": str(run_dir.relative_to(root)),
            "source_trial_dir": str(trial_dir.relative_to(root)),
            "harbor_job": trial_dir.parent.name,
        })
    assert len(set(moves)) == len(moves), "duplicate move sources"

    before_total = sum(len(c["rows"]) for c in cells.values())
    after_total = before_total - len(manifest)
    counts = Counter((m["cell"], m["condition"], m["run"]) for m in manifest)

    print(f"Archive: {archive}")
    print(f"Selected {len(manifest)} runs from {len(selected_rows)} CSV rows "
          f"(reason={args.rerun_reason}, cohort={args.cohort_model_path})")
    print(f"Cells affected: {len(cells)}; recorded rows {before_total} -> {after_total}")
    for (cell, condition, run), n in sorted(counts.items()):
        print(f"  {cell}\t{condition}\trun_{run}\t{n}")
    print(f"Directories to move: {len(moves)} ({len(manifest)} run dirs + {len(manifest)} Harbor trial dirs)")
    if not args.execute:
        print("Dry run only. Re-run with --execute to apply.")
        return

    # ── Execute ─────────────────────────────────────────────────────────────
    assert not archive.exists(), archive
    archive.mkdir(parents=True)
    (archive / "rerun_source").mkdir()
    shutil.copy2(csv_path, archive / "rerun_source" / csv_path.name)
    with (archive / "rerun_source" / "selected_rows.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected_rows[0]))
        writer.writeheader()
        writer.writerows(selected_rows)
    for cell_dir, cell in cells.items():
        backup = archive / "before" / cell["path"].relative_to(root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cell["path"], backup)
        dest = archive / cell["path"].relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        archived_rows = [x for x in cell["rows"] if x["key"] in cell["selected_keys"]]
        dest.write_text(json.dumps(archived_rows, indent=2) + "\n")
        for extra in ("run_info.json", "run_info.md"):
            if (cell_dir / extra).exists():
                shutil.copy2(cell_dir / extra, dest.parent / extra)
    (archive / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    (archive / "move_plan.json").write_text(json.dumps([str(p.relative_to(root)) for p in moves], indent=2) + "\n")
    shutil.copy2(__file__, archive / "archive_operation.py")
    with (archive / "tasks.tsv").open("w") as stream:
        columns = list(manifest[0])
        stream.write("\t".join(columns) + "\n")
        for m in sorted(manifest, key=lambda m: (m["cell"], m["run"], m["task"])):
            stream.write("\t".join(str(m[c]) for c in columns) + "\n")

    with (archive / "moves_completed.jsonl").open("a") as journal:
        for src in moves:
            dest = archive / src.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            assert not dest.exists(), dest
            src.rename(dest)
            journal.write(json.dumps({"source": str(src), "destination": str(dest)}) + "\n")
            journal.flush()

    for cell in cells.values():
        # Refuse to clobber an index that changed underneath us.
        assert json.loads(cell["path"].read_text()) == cell["rows"], cell["path"]
        kept = [x for x in cell["rows"] if x["key"] not in cell["selected_keys"]]
        temp = cell["path"].with_suffix(".json.archive-tmp")
        temp.write_text(json.dumps(kept, indent=2) + "\n")
        temp.replace(cell["path"])
        assert {x["key"] for x in json.loads(cell["path"].read_text())} | cell["selected_keys"] == set(cell["by_key"])

    remaining = sum(len(json.loads(c["path"].read_text())) for c in cells.values())
    assert remaining == after_total, (remaining, after_total)
    assert all(not p.exists() and (archive / p.relative_to(root)).is_dir() for p in moves)

    reason_text = ", ".join(args.rerun_reason)
    lines = [
        f"# {args.cohort_model_path}: rerun targets ({reason_text}) archived on {now:%Y-%m-%d %H:%M:%S} CDT",
        "",
        f"Source list: `{csv_path}` (copied to `rerun_source/`). Selected rows: `rerun_source/selected_rows.csv`.",
        f"Selection: cohort_model_path={args.cohort_model_path}, rerun_reason in [{reason_text}]"
        + (f", section in {args.section}" if args.section else "") + ".",
        "",
        "## Why",
        "",
        "These runs recorded FormatErrors on responses containing summary markers:",
        "the pre-fix memory.py passed summary prompts through the agent model's `_parse_actions`.",
        "This does not mean every summary call failed; some runs also recorded successful compression.",
        "The summary-response format check was fixed in commit cd1716f",
        "(`query_summary`). The runs are archived so that the same launcher re-executes them.",
        "",
        "## What was done",
        "",
        f"- {len(manifest)} runs across {len(cells)} cells; recorded rows {before_total} -> {after_total}.",
        "- Each run directory and its raw Harbor trial directory were moved here under the same",
        "  path relative to the workspace root. Other trials of the same Harbor job stayed in place.",
        "- Each `ICLR_results/.../experiment_results.json` here holds only the archived rows;",
        "  `before/` holds the complete pre-modification files. The archived keys were removed",
        "  from the canonical files, so the runner treats them as not yet executed.",
        "- `run_info.json`/`run_info.md` are historical copies; the launcher rewrites them on rerun.",
        "- Derived reports (COVERAGE*.csv) were not updated; regenerate after the rerun.",
        "",
        "## Rerun",
        "",
        "Before launching, make sure the runtime tree's `memory.py` contains the cd1716f fix",
        "(`query_summary`); the agent imports `memory` from the workspace root on PYTHONPATH.",
        "Then run the usual launcher, e.g. `bash scripts/run_agent_models_expansion_tb.sh devstral main`",
        "(or the Slack wrapper). Completed keys are skipped; only the archived keys are re-executed.",
        "",
        "## Counts (cell / condition / run / n)",
        "",
    ] + [f"- {cell}\t{condition}\trun_{run}\t{n}" for (cell, condition, run), n in sorted(counts.items())]
    lines += ["", "## Tasks", ""] + [f"- {t}" for t in sorted({m["task"] for m in manifest})]
    lines += ["", "Details: `tasks.tsv`, `manifest.json`, `move_plan.json`, `moves_completed.jsonl`.",
              f"Verification: {after_total} + {len(manifest)} = {before_total}; per-cell key sets preserved;",
              f"all {len(moves)} destinations exist and sources are gone."]
    (archive / "README.md").write_text("\n".join(lines) + "\n")
    print(f"Archived {len(manifest)} runs ({len(moves)} directories); {remaining} rows remain recorded.")
    print(archive)


if __name__ == "__main__":
    main()
