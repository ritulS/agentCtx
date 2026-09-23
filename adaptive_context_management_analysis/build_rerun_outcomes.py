#!/usr/bin/env python3
"""Overlay raised-limit re-run results onto ``swebench_outcomes.csv``.

The canonical outcome table (``analysis/outcomes/swebench_outcomes.csv``) is
built only from ``ICLR_experiments/``.  Re-runs made by
``rerun_limit_failures.py`` live outside that tree, under
``results/adaptive_context_management/swebench/reruns/<name>/``, so they never
leak into the canonical cells.  This script produces a *second* table in which
every canonical row that was re-run is replaced by its re-run result, and the
provenance of the replacement (which re-run directory, which step / time
limits, what the original row looked like) is recorded in extra columns.

Rows that were not re-run are copied through unchanged, with
``rerun=False`` and the runner's default limits in ``step_limit`` /
``agent_timeout_s``.

Output (default):
    results/adaptive_context_management/swebench/swebench_outcomes_rerun.csv
    results/adaptive_context_management/swebench/swebench_outcomes_rerun.meta.json

Selection rule when the same run was re-run more than once (e.g. phase 1 at
200 steps / 3600 s, then again at 300 steps / 5400 s): the attempt with the
highest ``(step_limit, agent_timeout_s)`` wins; ties go to the latest
timestamp.  Every attempt is still listed in ``rerun_history``.

Re-run rows without an evaluation result (``resolved`` missing, i.e. the
re-run directory has not been evaluated yet) are skipped with a warning
unless ``--include-unevaluated`` is given, so an evaluated ``resolved=False``
is never overwritten by an unevaluated blank.

Usage:
    python3 adaptive_context_management_analysis/build_rerun_outcomes.py
    python3 adaptive_context_management_analysis/build_rerun_outcomes.py \
        --rerun-dir results/adaptive_context_management/swebench/reruns/<name> ...
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from aggregate_benchmark_results import FIELDNAMES, normalized_row, records  # noqa: E402

BENCHMARK = "swebench"
DEFAULT_BASE = ROOT / "analysis" / "outcomes" / "swebench_outcomes.csv"
DEFAULT_RERUNS_ROOT = ROOT / "results" / "adaptive_context_management" / "swebench" / "reruns"
DEFAULT_OUTPUT = ROOT / "results" / "adaptive_context_management" / "swebench" / "swebench_outcomes_rerun.csv"

# Limits used by scripts/run_experiment.py for every canonical run
# (STEP_LIMIT / AGENT_TIMEOUT).  Cross-checked against rerun_info.json.
DEFAULT_STEP_LIMIT = 125
DEFAULT_AGENT_TIMEOUT_S = 1500

EXTRA_FIELDS = [
    "rerun",                    # True if this row is a re-run result
    "step_limit",               # harness step limit that applied to this row
    "agent_timeout_s",          # harness wall-clock limit that applied to this row
    "rerun_name",               # re-run directory name (encodes causes / limits / filter)
    "rerun_source_file",        # experiment_results.json the re-run row came from
    "rerun_original_cause",     # why the original run was selected (timeout / step_limit)
    "rerun_attempts",           # number of re-run attempts found for this run
    "rerun_history",            # all attempts: step<N>/t<M>:<failure_mode>; ...
    "original_source_file",     # canonical experiment_results.json of the replaced row
    "original_resolved",
    "original_failure_mode",
    "original_exit_status",
    "original_returncode",
    "original_step_count",
    "original_latency_e2e_s",
]
OUT_FIELDNAMES = FIELDNAMES + EXTRA_FIELDS

RERUN_OF_RE = re.compile(
    r"^ICLR_experiments/swebench/(?P<section>.+)/(?P<model>[^/]+)/(?P<cell>[^/]+)/"
    r"(?P<task>[^/]+)/(?P<condition>[^/]+)/run_(?P<run>\d+)/?$"
)

Key = tuple[str, str, str, str, str, str]


def base_key(row: dict[str, Any]) -> Key:
    return (row["experiment_section"], row["model_key"], row["cell"],
            row["task_name"], row["condition"], str(row["run_num"]))


def parse_rerun_of(value: str) -> tuple[Key, dict[str, str]] | None:
    m = RERUN_OF_RE.match(value.strip())
    if not m:
        return None
    d = m.groupdict()
    return (d["section"], d["model"], d["cell"], d["task"], d["condition"], d["run"]), d


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def records_retry(path: Path, attempts: int = 5, delay_s: float = 1.0) -> list[dict[str, Any]]:
    """Like ``records`` but tolerant of a runner rewriting the file mid-read.

    ``scripts/run_experiment.py`` rewrites experiment_results.json in place
    (truncate + write) after every finished run, so a read that lands in that
    window sees a truncated file.  Retry a few times before giving up.
    """
    for i in range(attempts):
        try:
            return records(path)
        except (json.JSONDecodeError, ValueError):
            if i == attempts - 1:
                raise
            time.sleep(delay_s)
    return []


def load_rerun_dir(rerun_dir: Path, include_unevaluated: bool, warnings: list[str]
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (normalized rerun rows with provenance, summary dict)."""
    results = rerun_dir / "experiment_results.json"
    info_path = rerun_dir / "rerun_info.json"
    info = json.loads(info_path.read_text()) if info_path.is_file() else {}
    for key, default in (("original_step_limit", DEFAULT_STEP_LIMIT),
                         ("original_agent_timeout_s", DEFAULT_AGENT_TIMEOUT_S)):
        if key in info and info[key] != default:
            warnings.append(f"{rerun_dir.name}: rerun_info {key}={info[key]} differs from "
                            f"the default {default} used for non-rerun rows")

    rows: list[dict[str, Any]] = []
    n_unevaluated = 0
    n_bad_ref = 0
    for raw in records_retry(results):
        if raw.get("resolved") is None and not include_unevaluated:
            n_unevaluated += 1
            continue
        parsed = parse_rerun_of(str(raw.get("rerun_of") or ""))
        if parsed is None:
            n_bad_ref += 1
            warnings.append(f"{rerun_dir.name}: cannot parse rerun_of={raw.get('rerun_of')!r} "
                            f"for key {raw.get('key')}; skipped")
            continue
        key, parts = parsed
        norm = normalized_row(raw, BENCHMARK, rerun_dir.parent, results)
        norm["experiment_section"] = parts["section"]
        norm["model_key"] = parts["model"]
        norm["model"] = raw.get("model") or parts["model"]
        norm["cell"] = parts["cell"]
        norm["_key"] = key
        norm["_raw"] = raw
        norm["_step_limit"] = raw.get("step_limit", info.get("step_limit"))
        norm["_timeout"] = raw.get("agent_timeout_s", info.get("agent_timeout_s"))
        norm["_rerun_name"] = rerun_dir.name
        norm["_original_cause"] = raw.get("original_cause", "")
        rows.append(norm)
    if n_unevaluated:
        warnings.append(f"{rerun_dir.name}: {n_unevaluated} row(s) have no evaluation result "
                        f"(resolved missing) and were skipped; run the eval or pass --include-unevaluated")
    summary = {
        "rerun_dir": str(rerun_dir.relative_to(ROOT)) if rerun_dir.is_relative_to(ROOT) else str(rerun_dir),
        "step_limit": info.get("step_limit"),
        "agent_timeout_s": info.get("agent_timeout_s"),
        "causes": info.get("causes"),
        "filters": info.get("filters"),
        "created": info.get("created"),
        "planned_runs": info.get("n_runs"),
        "recorded_rows": len(rows) + n_unevaluated + n_bad_ref,
        "rows_used": len(rows),
        "rows_unevaluated_skipped": n_unevaluated,
        "rows_unparseable_skipped": n_bad_ref,
    }
    return rows, summary


def attempt_rank(row: dict[str, Any]) -> tuple[float, float, str]:
    def num(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return -1.0
    return (num(row["_step_limit"]), num(row["_timeout"]), str(row["_raw"].get("timestamp") or ""))


def history_entry(row: dict[str, Any]) -> str:
    return f"{row['_rerun_name']}@step{row['_step_limit']}/t{row['_timeout']}:{row['failure_mode']}"


def build(base_csv: Path, rerun_dirs: list[Path], output: Path, include_unevaluated: bool) -> None:
    warnings: list[str] = []
    with base_csv.open(newline="") as handle:
        base_rows = list(csv.DictReader(handle))
    base_index: dict[Key, int] = {}
    for i, row in enumerate(base_rows):
        base_index.setdefault(base_key(row), i)

    attempts: dict[Key, list[dict[str, Any]]] = {}
    dir_summaries: list[dict[str, Any]] = []
    for rerun_dir in rerun_dirs:
        rows, summary = load_rerun_dir(rerun_dir, include_unevaluated, warnings)
        dir_summaries.append(summary)
        for row in rows:
            attempts.setdefault(row["_key"], []).append(row)

    out_rows: list[dict[str, Any]] = []
    for row in base_rows:
        out = dict(row)
        out.update({
            "rerun": False,
            "step_limit": DEFAULT_STEP_LIMIT,
            "agent_timeout_s": DEFAULT_AGENT_TIMEOUT_S,
            "rerun_name": "", "rerun_source_file": "", "rerun_original_cause": "",
            "rerun_attempts": 0, "rerun_history": "",
            "original_source_file": "", "original_resolved": "", "original_failure_mode": "",
            "original_exit_status": "", "original_returncode": "", "original_step_count": "",
            "original_latency_e2e_s": "",
        })
        out_rows.append(out)

    transitions: Counter[tuple[str, str]] = Counter()
    n_replaced = 0
    n_appended = 0
    for key, rows in sorted(attempts.items()):
        rows.sort(key=attempt_rank)
        chosen = rows[-1]
        history = "; ".join(history_entry(r) for r in rows)
        idx = base_index.get(key)
        if idx is None:
            warnings.append(f"re-run {chosen['_rerun_name']} refers to {'/'.join(key)} which is "
                            f"not in {base_csv.name}; appended without original_* columns")
            original: dict[str, Any] = {}
            n_appended += 1
        else:
            original = base_rows[idx]
            n_replaced += 1
        new = {k: chosen[k] for k in FIELDNAMES}
        new.update({
            "rerun": True,
            "step_limit": chosen["_step_limit"],
            "agent_timeout_s": chosen["_timeout"],
            "rerun_name": chosen["_rerun_name"],
            "rerun_source_file": chosen["source_file"],
            "rerun_original_cause": chosen["_original_cause"],
            "rerun_attempts": len(rows),
            "rerun_history": history,
            "original_source_file": original.get("source_file", ""),
            "original_resolved": original.get("resolved", ""),
            "original_failure_mode": original.get("failure_mode", ""),
            "original_exit_status": original.get("exit_status", ""),
            "original_returncode": original.get("returncode", ""),
            "original_step_count": original.get("step_count", ""),
            "original_latency_e2e_s": original.get("latency_e2e_s", ""),
        })
        transitions[(original.get("failure_mode", "<new>"), new["failure_mode"])] += 1
        if idx is None:
            out_rows.append(new)
        else:
            out_rows[idx] = new

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(out_rows)

    meta = {
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "base_csv": str(base_csv.relative_to(ROOT)) if base_csv.is_relative_to(ROOT) else str(base_csv),
        "base_csv_mtime": datetime.fromtimestamp(base_csv.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "base_rows": len(base_rows),
        "default_step_limit": DEFAULT_STEP_LIMIT,
        "default_agent_timeout_s": DEFAULT_AGENT_TIMEOUT_S,
        "selection_rule": "highest (step_limit, agent_timeout_s), then latest timestamp",
        "include_unevaluated": include_unevaluated,
        "rerun_dirs": dir_summaries,
        "rows_replaced": n_replaced,
        "rows_appended": n_appended,
        "runs_with_multiple_attempts": sum(1 for r in attempts.values() if len(r) > 1),
        "transitions": [
            {"original_failure_mode": a, "rerun_failure_mode": b, "n": n}
            for (a, b), n in sorted(transitions.items())
        ],
        "warnings": warnings,
    }
    meta_path = output.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"wrote {len(out_rows):,} rows to {output}")
    print(f"  base rows: {len(base_rows):,}   replaced by re-run: {n_replaced}   appended: {n_appended}"
          f"   multi-attempt runs: {meta['runs_with_multiple_attempts']}")
    for s in dir_summaries:
        print(f"  {Path(s['rerun_dir']).name}: step {s['step_limit']} / {s['agent_timeout_s']} s, "
              f"planned {s['planned_runs']}, recorded {s['recorded_rows']}, used {s['rows_used']}"
              + (f", unevaluated skipped {s['rows_unevaluated_skipped']}" if s['rows_unevaluated_skipped'] else ""))
    if transitions:
        print("  transitions (original failure_mode -> re-run failure_mode):")
        for (a, b), n in sorted(transitions.items(), key=lambda kv: -kv[1]):
            print(f"    {a:>22} -> {b:<22} {n}")
    for w in warnings:
        print(f"WARNING: {w}")
    print(f"metadata: {meta_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, default=DEFAULT_BASE,
                   help=f"canonical outcomes CSV to overlay on (default: {DEFAULT_BASE.relative_to(ROOT)})")
    p.add_argument("--reruns-root", type=Path, default=DEFAULT_RERUNS_ROOT,
                   help="directory whose immediate children are re-run directories "
                        "(default: results/adaptive_context_management/swebench/reruns)")
    p.add_argument("--rerun-dir", type=Path, action="append",
                   help="use only these re-run directories (repeatable); default: every "
                        "<reruns-root>/*/experiment_results.json")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--include-unevaluated", action="store_true",
                   help="also overlay re-run rows whose 'resolved' is missing (eval not run yet)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.rerun_dir:
        rerun_dirs = [d.resolve() for d in args.rerun_dir]
    else:
        rerun_dirs = sorted(p.parent for p in args.reruns_root.glob("*/experiment_results.json"))
    missing = [d for d in rerun_dirs if not (d / "experiment_results.json").is_file()]
    if missing:
        raise SystemExit("no experiment_results.json in: " + ", ".join(map(str, missing)))
    if not rerun_dirs:
        raise SystemExit(f"no re-run directories found under {args.reruns_root}")
    if not args.base.is_file():
        raise SystemExit(f"base CSV not found: {args.base}")
    build(args.base, rerun_dirs, args.output, args.include_unevaluated)


if __name__ == "__main__":
    main()
