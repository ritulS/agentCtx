#!/usr/bin/env python3
"""
Experiment progress monitor.

Usage:
  python scripts/check_progress.py <run_tag>
  python scripts/check_progress.py qwen3.5-35B-A3B_15k_Fullrun
  python scripts/check_progress.py Llama3.3-70B-Instruct_15k_Generalizerun
  watch -n 30 python scripts/check_progress.py <run_tag>
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
CONDITIONS     = ["full-context", "truncation", "summarization", "structured-summarize", "tool-result-clear"]


def fmt_dur(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds + td.days * 86400, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def progress_bar(done: int, total: int, width: int = 40) -> str:
    if total == 0:
        return "░" * width
    filled = int(done / total * width)
    return "█" * filled + "░" * (width - filled)


def eta(n_done: int, total: int, results: list) -> str:
    if n_done < 2:
        return "—"
    timestamps = []
    for r in results:
        ts_str = r.get("timestamp", "")
        if ts_str:
            try:
                timestamps.append(datetime.fromisoformat(ts_str[:19]))
            except Exception:
                pass
    if len(timestamps) < 2:
        return "—"
    timestamps.sort()
    elapsed   = (timestamps[-1] - timestamps[0]).total_seconds()
    rate      = n_done / elapsed if elapsed > 0 else 0
    remaining = (total - n_done) / rate if rate > 0 else 0
    return f"{fmt_dur(remaining)}  ({rate * 3600:.0f} runs/hr)"


def load_run_info(run_dir: Path) -> dict:
    info_path = run_dir / "run_info.json"
    if info_path.exists():
        return json.loads(info_path.read_text())
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment progress monitor")
    parser.add_argument("run_tag", help="Run tag (directory name under results/)")
    args = parser.parse_args()

    run_dir      = WORKSPACE_ROOT / "results" / args.run_tag
    results_file = run_dir / "experiment_results.json"
    run_info     = load_run_info(run_dir)

    total_runs  = run_info.get("total_runs", "?")
    budget      = run_info.get("budget_tokens", "?")
    n_tasks     = run_info.get("n_tasks", "?")
    step_limit  = run_info.get("step_limit", "?")
    model       = run_info.get("model", args.run_tag)
    purpose     = run_info.get("purpose", "")

    W       = 72
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*W}")
    print(f"  {args.run_tag}")
    print(f"  {model}")
    if purpose:
        print(f"  {purpose}")
    print(f"  [{now_str}]")
    print(f"  {n_tasks} tasks × {len(CONDITIONS)} conditions × {run_info.get('runs_per_task', 2)} runs = {total_runs} total"
          f"   budget={budget:,}   steps={step_limit}" if isinstance(budget, int) else
          f"  {n_tasks} tasks × {len(CONDITIONS)} conditions  total={total_runs}   budget={budget}   steps={step_limit}")
    print(f"{'='*W}")

    if not run_dir.exists():
        print(f"\n  Results directory not found: {run_dir}\n")
        return

    if not results_file.exists():
        # Count partial results by scanning subdirs
        n_partial = sum(1 for p in run_dir.rglob("token_log.json"))
        print(f"\n  No experiment_results.json yet.  ({n_partial} token_log files found)\n")
        return

    results = json.loads(results_file.read_text())
    n_done  = len(results)
    total   = total_runs if isinstance(total_runs, int) else n_done

    # ── Overall progress ──────────────────────────────────────────────────────
    bar     = progress_bar(n_done, total)
    pct_str = f"{100*n_done//total}%" if (isinstance(total, int) and total > 0 and n_done < total) else ("✓ COMPLETE" if n_done >= total else f"{n_done}")
    print(f"\n  PROGRESS  [{pct_str}]")
    print(f"  [{bar}]  {n_done}/{total}")

    if n_done == 0:
        print()
        return

    n_patch   = sum(1 for r in results if r.get("patch_generated"))
    n_evaled  = sum(1 for r in results if r.get("resolved") is not None)
    n_res     = sum(1 for r in results if r.get("resolved") is True)
    n_limits  = sum(1 for r in results if r.get("exit_status") == "LimitsExceeded")
    n_timeout = sum(1 for r in results if r.get("returncode") == -1)
    n_comp    = sum(1 for r in results if r.get("compression_events", 0) > 0)
    latencies = [r["e2e_latency_s"] for r in results if r.get("e2e_latency_s")]
    calls_all = [r["n_calls"] for r in results if r.get("n_calls", 0) > 0]

    print(f"\n  Summary")
    print(f"  {'─'*W}")
    print(f"  Patches generated : {n_patch}/{n_done}  ({100*n_patch//n_done}%)")
    print(f"  Compression fired : {n_comp}/{n_done}  ({100*n_comp//n_done}%)")
    if calls_all:
        print(f"  Avg steps         : {sum(calls_all)/len(calls_all):.1f}  (max={max(calls_all)}, limit={step_limit})")
    if latencies:
        print(f"  Avg latency       : {sum(latencies)/len(latencies):.0f}s  (max={max(latencies):.0f}s)")
    exits = []
    if n_limits:  exits.append(f"LimitsExceeded={n_limits}")
    if n_timeout: exits.append(f"Timeout={n_timeout}")
    if exits:     print(f"  Failures          : {',  '.join(exits)}")
    eta_str = eta(n_done, total, results)
    if eta_str != "—":
        print(f"  ETA               : {eta_str}")

    # ── Per-condition breakdown ───────────────────────────────────────────────
    by_cond = defaultdict(list)
    for r in results:
        by_cond[r["condition"]].append(r)

    print(f"\n  By condition")
    print(f"  {'─'*W}")
    print(f"  {'Condition':<22}  {'Done':>6}  {'Patch%':>7}  {'Comp%':>6}  {'AvgSteps':>9}  {'AvgLat':>8}  {'TRCfall%':>9}")
    print(f"  {'─'*W}")
    for cond in CONDITIONS:
        rows = by_cond.get(cond, [])
        if not rows:
            print(f"  {cond:<22}  {'0':>6}")
            continue
        n      = len(rows)
        p      = 100 * sum(1 for r in rows if r["patch_generated"]) // n
        c      = 100 * sum(1 for r in rows if r.get("compression_events", 0) > 0) // n
        steps  = [r["n_calls"] for r in rows if r.get("n_calls", 0) > 0]
        lats   = [r["e2e_latency_s"] for r in rows if r.get("e2e_latency_s")]
        as_    = f"{sum(steps)/len(steps):.1f}" if steps else "—"
        al_    = f"{sum(lats)/len(lats):.0f}s"  if lats  else "—"
        trc_events    = sum(r.get("compression_events", 0) for r in rows)
        trc_fallbacks = sum(r.get("trc_truncation_fallback_events", 0) for r in rows)
        trc_str = f"{100*trc_fallbacks//trc_events}%" if trc_events > 0 else "—"
        print(f"  {cond:<22}  {n:>6}  {p:>6}%  {c:>5}%  {as_:>9}  {al_:>8}  {trc_str:>9}")

    # ── SWE-bench evaluation ──────────────────────────────────────────────────
    print(f"\n  SWE-bench evaluation")
    print(f"  {'─'*W}")
    if n_evaled == 0:
        print(f"  Not started  ({n_patch} patches ready to evaluate)")
    else:
        bar2 = progress_bar(n_evaled, n_patch)
        print(f"  [{bar2}]  {n_evaled}/{n_patch} evaluated")
        if n_evaled > 0:
            print(f"  Resolved : {n_res}/{n_evaled}  ({100*n_res//n_evaled}%)")
        if n_evaled < n_patch:
            print(f"  Pending  : {n_patch - n_evaled} patches")

        print(f"\n  Resolve rate by condition:")
        for cond in CONDITIONS:
            rows = [r for r in by_cond.get(cond, []) if r.get("resolved") is not None]
            if not rows: continue
            res = sum(1 for r in rows if r["resolved"] is True)
            print(f"    {cond:<22} {res}/{len(rows)}  ({100*res//len(rows)}%)")

    # ── Per-task table ────────────────────────────────────────────────────────
    by_task = defaultdict(list)
    for r in results:
        by_task[r["instance_id"]].append(r)

    print(f"\n  Per-task  ({len(by_task)} tasks touched)")
    print(f"  {'─'*W}")

    by_repo: dict[str, list] = defaultdict(list)
    for task_id, rows in sorted(by_task.items()):
        repo = task_id.split("__")[0]
        by_repo[repo].append((task_id, rows))

    for repo in sorted(by_repo):
        print(f"  [{repo}]")
        for task_id, rows in sorted(by_repo[repo]):
            n_runs  = len(rows)
            patches = sum(1 for r in rows if r.get("patch_generated"))
            ev      = [r for r in rows if r.get("resolved") is not None]
            res_str = f"res={sum(1 for r in ev if r['resolved'])}/{len(ev)}" if ev else "res=—"
            comp    = sum(r.get("compression_events", 0) for r in rows)
            short   = task_id.split("__", 1)[-1][:28]
            print(f"    {short:<30}  n={n_runs:>3}  patch={patches:<3}  {res_str:<12}  comp_events={comp}")

    # ── Last 5 completions ────────────────────────────────────────────────────
    recent = sorted(results, key=lambda r: r.get("timestamp", ""), reverse=True)[:5]
    print(f"\n  Last 5 completions:")
    print(f"  {'─'*W}")
    for r in recent:
        icon  = "[P]" if r.get("patch_generated") else "[x]"
        res   = "[✓]" if r.get("resolved") else ("   " if r.get("resolved") is None else "[✗]")
        cond  = r.get("condition", r.get("primitive", "?"))[:14]
        short = r["instance_id"].split("__", 1)[-1][:22]
        comp  = r.get("compression_events", 0)
        print(f"  {icon}{res} {cond:<14}  r{r['run_num']}  {short:<24}  steps={r['n_calls']:>3}  comp={comp}  {r.get('e2e_latency_s',0):.0f}s")

    print()


if __name__ == "__main__":
    main()
