#!/usr/bin/env python3
"""Tag every run of one or more result cells with its infrastructure failure classes.

A run's outcome mixes two things: whether the agent could solve the task and
whether the serving stack let it try. This script separates them after the fact
from files every SWE-bench run already has (``experiment_results.json`` rows,
``token_log.json`` ``model_call_records`` / ``summary_outcomes``, and the
``model_kwargs`` recorded in ``trajectory.json``):

  runaway          an agent reply reached the run's ``max_tokens`` (a thinking
                   loop; completion_tokens >= max_tokens, default 32768)
  summary_runaway  a summarizer reply ended with finish_reason "length"
  hung             an agent call took at least the client timeout (``timeout``
                   in model_kwargs, default litellm 600 s): the request never
                   returned and was retried; the recorded latency includes the
                   lost attempt(s)
  timeout          the run hit the agent wall-clock limit (exit_status Timeout)
  limits_exceeded  the run hit the step limit (exit_status LimitsExceeded)

``class`` summarizes a run: ``resolved``; ``unevaluated`` (no verdict);
``infra_failure`` (not resolved and runaway / hung / timeout); ``model_failure``
(not resolved, none of those). ``limits_exceeded`` alone is a model failure.
Resolved runs keep their tags so "affected but still resolved" stays visible.

Writes ``<cell>/failure_tags.csv`` (one row per run) unless --no-write, and
prints a per-task summary per cell plus a cell total.

Usage:
  python scripts/maintenance/tag_run_failures.py data/r2/swebench/p100_su_free_majority/qwen35b/*
  python scripts/maintenance/tag_run_failures.py <cell> --no-write
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_MAX_TOKENS = 32768     # configs/config-qwen-vllm.yaml before the cap
DEFAULT_TIMEOUT_S = 600.0      # litellm default request timeout
HUNG_TOLERANCE = 0.98          # latency >= 0.98 * timeout counts as a lost attempt
FIELDS = [
    "cell", "instance_id", "condition", "run_num", "resolved", "exit_status",
    "class", "runaway", "summary_runaway", "hung", "timeout", "limits_exceeded",
    "n_runaway_calls", "n_hung_calls", "n_calls", "max_tokens", "timeout_s",
    "e2e_latency_s", "wasted_s",
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def run_limits(run_dir: Path) -> tuple[int, float]:
    """(max_tokens, timeout_s) the run was launched with, from its trajectory."""
    traj = load_json(run_dir / "trajectory.json") or {}
    kwargs = (((traj.get("info") or {}).get("config") or {}).get("model") or {}).get("model_kwargs") or {}
    max_tokens = kwargs.get("max_tokens")
    timeout = kwargs.get("timeout")
    return (
        int(max_tokens) if isinstance(max_tokens, int) and max_tokens > 0 else DEFAULT_MAX_TOKENS,
        float(timeout) if isinstance(timeout, (int, float)) and timeout > 0 else DEFAULT_TIMEOUT_S,
    )


def tag_run(cell: Path, row: dict) -> dict:
    run_dir = cell / row["instance_id"] / row["condition"] / f"run_{row['run_num']}"
    max_tokens, timeout_s = run_limits(run_dir)
    token_log = load_json(run_dir / "token_log.json") or {}
    records = token_log.get("model_call_records") or []
    n_runaway = n_hung = 0
    wasted = 0.0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        completion = rec.get("completion_tokens") or 0
        latency = rec.get("latency_s") or 0.0
        if completion >= max_tokens:
            n_runaway += 1
            wasted += latency
        elif latency >= HUNG_TOLERANCE * timeout_s:
            n_hung += 1
            wasted += timeout_s * int(latency // timeout_s or 1)
    summary_runaway = any(
        ((outcome.get("flags") or {}).get("finish_reason") == "length")
        for outcome in (token_log.get("summary_outcomes") or []) if isinstance(outcome, dict)
    )
    exit_status = row.get("exit_status") or ""
    timeout = bool(row.get("timed_out")) or exit_status == "Timeout"
    limits = exit_status == "LimitsExceeded"
    resolved = row.get("resolved")
    infra = n_runaway > 0 or n_hung > 0 or timeout or summary_runaway
    if resolved is True:
        cls = "resolved"
    elif resolved is None:
        cls = "unevaluated"
    elif infra:
        cls = "infra_failure"
    else:
        cls = "model_failure"
    return {
        "cell": str(cell), "instance_id": row["instance_id"], "condition": row["condition"],
        "run_num": row["run_num"], "resolved": resolved, "exit_status": exit_status,
        "class": cls, "runaway": n_runaway > 0, "summary_runaway": summary_runaway,
        "hung": n_hung > 0, "timeout": timeout, "limits_exceeded": limits,
        "n_runaway_calls": n_runaway, "n_hung_calls": n_hung, "n_calls": len(records),
        "max_tokens": max_tokens, "timeout_s": timeout_s,
        "e2e_latency_s": row.get("e2e_latency_s"), "wasted_s": round(wasted),
    }


def summarize(cell: Path, tags: list[dict]) -> None:
    by_task: dict[str, list[dict]] = defaultdict(list)
    for tag in tags:
        by_task[tag["instance_id"]].append(tag)
    print(f"\n== {cell}")
    print(f"{'task':42s} {'runs':>4s} {'resolved':>8s} {'infra':>5s} {'model':>5s} {'uneval':>6s} "
          f"{'affected':>8s} {'timeout':>7s} {'wasted_h':>8s}")
    totals = defaultdict(int)
    wasted_total = 0.0
    for task, rows in by_task.items():
        counts = defaultdict(int)
        for r in rows:
            counts[r["class"]] += 1
            counts["affected"] += r["runaway"] or r["hung"] or r["timeout"] or r["summary_runaway"]
            counts["timeout"] += r["timeout"]
        wasted = sum(r["wasted_s"] for r in rows)
        wasted_total += wasted
        for k, v in counts.items():
            totals[k] += v
        print(f"{task[-42:]:42s} {len(rows):4d} {counts['resolved']:8d} {counts['infra_failure']:5d} "
              f"{counts['model_failure']:5d} {counts['unevaluated']:6d} {counts['affected']:8d} "
              f"{counts['timeout']:7d} {wasted/3600:8.1f}")
    print(f"{'TOTAL':42s} {len(tags):4d} {totals['resolved']:8d} {totals['infra_failure']:5d} "
          f"{totals['model_failure']:5d} {totals['unevaluated']:6d} {totals['affected']:8d} "
          f"{totals['timeout']:7d} {wasted_total/3600:8.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cells", nargs="+", type=Path, help="result cell dirs (each holds experiment_results.json)")
    parser.add_argument("--no-write", action="store_true", help="print the summary only; do not write failure_tags.csv")
    args = parser.parse_args()
    status = 0
    for cell in args.cells:
        rows = load_json(cell / "experiment_results.json")
        if not isinstance(rows, list):
            print(f"!! {cell}: no experiment_results.json", file=sys.stderr)
            status = 1
            continue
        tags = [tag_run(cell, row) for row in rows if isinstance(row, dict) and "instance_id" in row]
        summarize(cell, tags)
        if not args.no_write:
            out = cell / "failure_tags.csv"
            with out.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(tags)
            print(f"   wrote {out} ({len(tags)} rows)")
    return status


if __name__ == "__main__":
    sys.exit(main())
