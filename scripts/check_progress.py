#!/usr/bin/env python3
"""
E1 Experiment — progress monitor.
Run at any time:
  python scripts/check_progress.py
  watch -n 60 python scripts/check_progress.py
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
RESULTS_FILE   = WORKSPACE_ROOT / "results" / "experiment_results.json"

PRIMITIVES         = ["truncation", "summarization"]
BUDGET_PERCENTAGES = [1.00, 0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.25]
RUNS_PER_TASK      = 3
N_TASKS            = 30   # 10 per repo × 3 repos
TOTAL_RUNS         = N_TASKS * len(PRIMITIVES) * len(BUDGET_PERCENTAGES) * RUNS_PER_TASK


def fmt_dur(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds + td.days * 86400, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def _pct_tag(pct: float) -> str:
    return f"p{int(round(pct * 100)):03d}"


def main() -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*66}")
    print(f"  E1 EXPERIMENT PROGRESS   [{now_str}]")
    print(f"{'='*66}")

    if not RESULTS_FILE.exists():
        print("\n  No results yet.  Run: python scripts/run_experiment.py\n")
        return

    results = json.loads(RESULTS_FILE.read_text())
    n_done  = len(results)
    pct_done = 100 * n_done / TOTAL_RUNS if TOTAL_RUNS else 0

    bar_w  = 44
    filled = int(pct_done / 100 * bar_w)
    bar    = "█" * filled + "░" * (bar_w - filled)
    print(f"\n  [{bar}] {n_done}/{TOTAL_RUNS}  ({pct_done:.0f}%)")

    # Phase labels
    n_baseline   = sum(1 for r in results if r.get("is_baseline"))
    n_compressed = n_done - n_baseline
    total_base   = N_TASKS * len(PRIMITIVES) * RUNS_PER_TASK
    total_comp   = TOTAL_RUNS - total_base
    print(f"  Phase 0 (baseline):   {n_baseline:4d}/{total_base}")
    print(f"  Phase 2 (compressed): {n_compressed:4d}/{total_comp}")

    # ETA
    if n_done > 1:
        times = []
        for r in results:
            try:
                times.append(datetime.fromisoformat(r["timestamp"]))
            except Exception:
                pass
        if times:
            elapsed   = (max(times) - min(times)).total_seconds()
            rate      = (n_done - 1) / elapsed if elapsed > 0 else 0
            remaining = TOTAL_RUNS - n_done
            eta_s     = remaining / rate if rate > 0 else 0
            print(f"  Elapsed : {fmt_dur(elapsed)}   "
                  f"Rate: {3600*rate:.0f} runs/hr   "
                  f"ETA: {fmt_dur(eta_s)}")

    # ── Completion grid: budget_pct × primitive ───────────────────────────────
    done_set = {
        (r.get("budget_pct"), r["primitive"], r["run_num"])
        for r in results
    }
    print(f"\n  Grid  (✓=all {RUNS_PER_TASK} runs done  ·=0  digit=partial)")
    print(f"  {'Budget':>7}  ", end="")
    for p in PRIMITIVES:
        print(f"  {p[0].upper()}", end="")
    print()
    print(f"  {'─'*7}  {'─'*5*len(PRIMITIVES)}")
    for pct in BUDGET_PERCENTAGES:
        label = "100%(base)" if pct == 1.0 else f"{int(pct*100):>3}%"
        print(f"  {label:>10}", end="")
        for p in PRIMITIVES:
            done = sum(1 for rn in range(1, RUNS_PER_TASK + 1)
                       if (pct, p, rn) in done_set)
            cell = "✓" if done == RUNS_PER_TASK else (str(done) if done else "·")
            print(f"  {cell}", end="")
        print()

    # ── Per-task summary ──────────────────────────────────────────────────────
    by_task: dict[str, list] = defaultdict(list)
    for r in results:
        by_task[r["instance_id"]].append(r)

    per_config = len(PRIMITIVES) * len(BUDGET_PERCENTAGES) * RUNS_PER_TASK
    print(f"\n  Per-task  (done / {per_config} per task)")
    print(f"  {'─'*62}")
    for task_id in sorted(by_task):
        rows     = by_task[task_id]
        patches  = sum(1 for r in rows if r.get("patch_generated"))
        resolved = sum(1 for r in rows if r.get("resolved") is True)
        calls    = [r["n_calls"] for r in rows if r.get("n_calls", 0) > 0]
        avg_c    = f"{sum(calls)/len(calls):.1f}" if calls else "—"
        short    = task_id.split("__")[-1][:20]
        print(f"  {short:<22} {len(rows):>3}/{per_config}"
              f"  patch={patches:<3}  res={resolved:<3}  avg_calls={avg_c}")

    # ── Quick stats ───────────────────────────────────────────────────────────
    if results:
        patches  = sum(1 for r in results if r.get("patch_generated"))
        resolved = sum(1 for r in results if r.get("resolved") is True)
        latencies = [r["e2e_latency_s"] for r in results]
        timeouts  = sum(1 for r in results if r.get("returncode") == -1)
        calls     = [r["n_calls"] for r in results if r.get("n_calls", 0) > 0]
        comp_runs = sum(1 for r in results if r.get("compression_events", 0) > 0)

        print(f"\n  Aggregate ({n_done} runs):")
        print(f"  {'─'*44}")
        print(f"  Patch generated  : {patches}/{n_done}  ({100*patches/n_done:.0f}%)")
        if any(r.get("resolved") is not None for r in results):
            evaled = sum(1 for r in results if r.get("resolved") is not None)
            print(f"  Resolved (eval)  : {resolved}/{evaled}")
        if latencies:
            print(f"  Avg e2e latency  : {sum(latencies)/len(latencies):.0f}s"
                  f"  max={max(latencies):.0f}s")
        if calls:
            print(f"  Avg tool calls   : {sum(calls)/len(calls):.1f}"
                  f"  max={max(calls)}")
        print(f"  Compression fired: {comp_runs}/{n_done} runs")
        if timeouts:
            print(f"  Timeouts         : {timeouts}")

    # ── Last 5 completions ────────────────────────────────────────────────────
    if results:
        recent = sorted(results, key=lambda r: r.get("timestamp", ""), reverse=True)[:5]
        print(f"\n  Last {min(5, len(recent))} completions:")
        print(f"  {'─'*62}")
        for r in recent:
            icon = "P" if r.get("patch_generated") else "x"
            res  = ("R" if r.get("resolved") is True
                    else ("F" if r.get("resolved") is False else "?"))
            pct  = r.get("budget_pct", 0)
            short = r["instance_id"].split("__")[-1][:16]
            print(f"  [{icon}{res}] {r['primitive']:<14} "
                  f"{int(pct*100):>3}%  {short:<18}  "
                  f"calls={r['n_calls']:>3}  {r['e2e_latency_s']:.0f}s")

    print()


if __name__ == "__main__":
    main()
