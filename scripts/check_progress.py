#!/usr/bin/env python3
"""
Quick progress check for the WAF experiment.
Run at any time during or after the experiment:
  python scripts/check_progress.py
  watch -n 30 python scripts/check_progress.py
"""

import json
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE_ROOT = Path(__file__).parent.parent
RESULTS_FILE   = WORKSPACE_ROOT / "results" / "experiment_results.json"

PRIMITIVES    = ["truncation", "summarization"]
TOKEN_BUDGETS = [10_000, 20_000, 30_000, 40_000]
RUNS_PER_TASK = 1
N_TASKS       = 3
TOTAL_RUNS    = N_TASKS * len(PRIMITIVES) * len(TOKEN_BUDGETS) * RUNS_PER_TASK


def fmt_dur(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds + td.days * 86400, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*62}")
    print(f"  WAF EXPERIMENT PROGRESS   [{now_str}]")
    print(f"{'='*62}")

    if not RESULTS_FILE.exists():
        print(f"\n  No results yet. Experiment has not started.")
        print(f"  Run: bash scripts/run_full_experiment.sh")
        print()
        return

    results = json.loads(RESULTS_FILE.read_text())
    n_done  = len(results)

    # ── Overall progress ──────────────────────────────────────
    pct = 100 * n_done / TOTAL_RUNS if TOTAL_RUNS else 0
    bar_w = 40
    filled = int(pct / 100 * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)

    print(f"\n  [{bar}] {n_done}/{TOTAL_RUNS}  ({pct:.0f}%)")

    # ETA from timestamps
    if n_done > 1:
        times = []
        for r in results:
            try:
                times.append(datetime.fromisoformat(r["timestamp"]))
            except Exception:
                pass
        if times:
            elapsed = (max(times) - min(times)).total_seconds()
            rate_per_s = (n_done - 1) / elapsed if elapsed > 0 else 0
            remaining  = TOTAL_RUNS - n_done
            eta_s      = remaining / rate_per_s if rate_per_s > 0 else 0
            print(f"  Elapsed : {fmt_dur(elapsed)}   "
                  f"Rate: {60*rate_per_s:.1f} runs/hr   "
                  f"ETA: {fmt_dur(eta_s)}")

    # ── Grid: primitive × budget ──────────────────────────────
    done_set = {(r["primitive"], r["budget"], r["run_num"]) for r in results}

    print(f"\n  Completion grid  (T=truncation  S=summarization)")
    print(f"  {'Budget':>8}", end="")
    for p in PRIMITIVES:
        label = p[0].upper()
        print(f"  {label}", end="")
    print()
    print(f"  {'─'*8}{'─'*5*len(PRIMITIVES)}")

    for b in TOKEN_BUDGETS:
        print(f"  {b:>8}", end="")
        for p in PRIMITIVES:
            done = sum(1 for run in range(1, RUNS_PER_TASK + 1)
                       if (p, b, run) in done_set)
            cell = "✓" if done == RUNS_PER_TASK else (str(done) if done else "·")
            print(f"  {cell}", end="")
        print()

    # ── Per-task breakdown ────────────────────────────────────
    by_task = defaultdict(list)
    for r in results:
        by_task[r["instance_id"]].append(r)

    print(f"\n  Per-task  (done / {len(PRIMITIVES)*len(TOKEN_BUDGETS)*RUNS_PER_TASK})")
    print(f"  {'─'*58}")
    for task_id in sorted(by_task):
        rows    = by_task[task_id]
        n       = len(rows)
        patches = sum(1 for r in rows if r.get("patch_generated"))
        resolved= sum(1 for r in rows if r.get("resolved") is True)
        calls   = [r["n_calls"] for r in rows if r["n_calls"] > 0]
        avg_c   = f"{sum(calls)/len(calls):.1f}" if calls else "—"
        short   = task_id.split("__")[-1][:18]
        print(f"  {short:<20} {n:>3}/{len(PRIMITIVES)*len(TOKEN_BUDGETS)*RUNS_PER_TASK}"
              f"   patch={patches}  resolved={resolved}  avg_calls={avg_c}")

    # ── Quick stats on completed runs ─────────────────────────
    if results:
        patches  = sum(1 for r in results if r.get("patch_generated"))
        resolved = sum(1 for r in results if r.get("resolved") is True)
        latencies= [r["e2e_latency_s"] for r in results]
        timeouts = sum(1 for r in results if r.get("returncode") == -1)
        calls    = [r["n_calls"] for r in results if r["n_calls"] > 0]

        print(f"\n  Aggregate over {n_done} completed runs:")
        print(f"  {'─'*40}")
        print(f"  Patch generated : {patches}/{n_done}  ({100*patches/n_done:.0f}%)")
        if any(r.get("resolved") is not None for r in results):
            evaled = sum(1 for r in results if r.get("resolved") is not None)
            print(f"  Resolved        : {resolved}/{evaled} evaluated  ({100*resolved/evaled:.0f}% of eval'd)")
        if latencies:
            print(f"  Avg e2e latency : {sum(latencies)/len(latencies):.0f}s  "
                  f"(min={min(latencies):.0f}s  max={max(latencies):.0f}s)")
        if calls:
            print(f"  Avg tool calls  : {sum(calls)/len(calls):.1f}  "
                  f"(min={min(calls)}  max={max(calls)})")
        if timeouts:
            print(f"  Timeouts        : {timeouts}")

    # ── Last 5 completions ────────────────────────────────────
    if results:
        recent = sorted(results, key=lambda r: r.get("timestamp",""), reverse=True)[:5]
        print(f"\n  Last {min(5,len(recent))} completions:")
        print(f"  {'─'*58}")
        for r in recent:
            icon = "P" if r.get("patch_generated") else "x"
            res  = ("R" if r.get("resolved") is True
                    else ("F" if r.get("resolved") is False else "?"))
            short = r["instance_id"].split("__")[-1][:14]
            print(f"  [{icon}{res}] {r['primitive']:<14} b={r['budget']:>5}  "
                  f"{short:<16}  calls={r['n_calls']:>3}  {r['e2e_latency_s']:.0f}s")

    print()


if __name__ == "__main__":
    main()
