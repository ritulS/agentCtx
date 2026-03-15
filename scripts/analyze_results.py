#!/usr/bin/env python3
"""
Analyze WAF experiment results.

Metrics reported
----------------
WAF (Work Amplification Factor)
  For task i and configuration c = (primitive, budget):
    WAF_i(c) = mean_calls_c(i) / min_calls(i)
  where min_calls(i) = min over all configs c of mean_calls_c(i)

  Aggregate WAF(c) = (1 / |T|) * sum_i WAF_i(c)

Other aggregates per configuration (mean over tasks × runs):
  - e2e latency (s)
  - total LLM tokens (prompt + completion)
  - compression events per run
  - patch_generated rate
  - resolved rate (SWE-bench evaluation)

Usage
-----
python scripts/analyze_results.py [--results path/to/experiment_results.json]
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
RESULTS_DIR    = WORKSPACE_ROOT / "results"

PRIMITIVES    = ["truncation", "summarization"]
TOKEN_BUDGETS = [0, 1_000, 1_500, 2_500, 4_000]


# ─── Loading ──────────────────────────────────────────────────────────────────

def load_results(path: Path | None) -> list[dict]:
    if path is None:
        path = RESULTS_DIR / "experiment_results.json"
    if not path.exists():
        print(f"ERROR: results file not found at {path}")
        raise SystemExit(1)
    data = json.loads(path.read_text())
    print(f"Loaded {len(data)} run records from {path}\n")
    return data


# ─── Budget-pct derivation ────────────────────────────────────────────────────

def add_budget_pct(results: list[dict]) -> list[dict]:
    """
    Attach budget_pct to every record.

    budget_pct = budget / baseline_total_prompt_tokens
                 where the baseline is the is_baseline==True (budget==0) run
                 for the same (instance_id, primitive).

    Records whose baseline is missing get budget_pct = None.
    The baseline record itself gets budget_pct = 0.0.
    """
    baseline_tokens: dict[tuple, int] = {}
    for r in results:
        if r.get("is_baseline") or r.get("budget") == 0:
            key = (r["instance_id"], r["primitive"])
            t = r.get("total_prompt_tokens", 0)
            if t > 0:
                baseline_tokens[key] = t

    for r in results:
        key = (r["instance_id"], r["primitive"])
        bt  = baseline_tokens.get(key)
        if r.get("is_baseline") or r.get("budget") == 0:
            r["budget_pct"] = 0.0
        elif bt and bt > 0:
            r["budget_pct"] = round(r["budget"] / bt, 4)
        else:
            r["budget_pct"] = None

    return results


# ─── WAF computation ──────────────────────────────────────────────────────────

def compute_waf(results: list[dict]) -> dict[tuple, float]:
    """
    Returns dict mapping (primitive, budget) -> aggregate WAF over all tasks.

    Algorithm
    ---------
    1. For each (task, primitive, budget) compute mean n_calls over runs.
    2. For each task, find the reference: min mean_calls over all configs.
    3. WAF_i(c) = mean_calls_c(i) / ref_i     (if ref_i > 0 else 1.0)
    4. WAF(c) = mean over tasks of WAF_i(c)
    """
    # Group: (instance_id, primitive, budget) -> [n_calls]
    cell: dict[tuple, list[int]] = defaultdict(list)
    for r in results:
        cell[(r["instance_id"], r["primitive"], r["budget"])].append(r["n_calls"])

    tasks = list({r["instance_id"] for r in results})

    # Mean calls per (task, config)
    mean_calls: dict[tuple, float] = {
        k: statistics.mean(v) for k, v in cell.items()
    }

    # Reference per task = min mean_calls across all configs for that task
    ref: dict[str, float] = {}
    for task in tasks:
        vals = [
            mean_calls[k]
            for k in mean_calls
            if k[0] == task and mean_calls[k] > 0
        ]
        ref[task] = min(vals) if vals else 1.0

    # WAF per (config, task)
    waf_by_config: dict[tuple, list[float]] = defaultdict(list)
    for task in tasks:
        for primitive in PRIMITIVES:
            for budget in TOKEN_BUDGETS:
                key = (task, primitive, budget)
                mc  = mean_calls.get(key, 0.0)
                r   = ref.get(task, 1.0)
                waf = mc / r if r > 0 and mc > 0 else 1.0
                waf_by_config[(primitive, budget)].append(waf)

    # Aggregate WAF per config
    return {
        cfg: statistics.mean(waf_vals)
        for cfg, waf_vals in waf_by_config.items()
    }


# ─── Generic aggregation helpers ──────────────────────────────────────────────

def _mean(lst: list) -> float:
    return statistics.mean(lst) if lst else 0.0


def _rate(lst: list) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def config_stats(results: list[dict], primitive: str, budget: int) -> dict:
    """Aggregate metrics for one (primitive, budget) configuration."""
    rows = [r for r in results if r["primitive"] == primitive and r["budget"] == budget]
    if not rows:
        return {}
    return {
        "n":                  len(rows),
        "mean_e2e_s":         _mean([r["e2e_latency_s"] for r in rows]),
        "mean_llm_s":         _mean([r.get("llm_latency_s", 0.0) for r in rows]),
        "mean_n_calls":       _mean([r["n_calls"] for r in rows]),
        "mean_total_tokens":  _mean([r["total_tokens"] for r in rows]),
        "mean_tokens_saved":  _mean([r["total_tokens_saved"] for r in rows]),
        "mean_comp_events":   _mean([r["compression_events"] for r in rows]),
        "mean_comp_ratio":    _mean([r["mean_compression_ratio"] for r in rows]),
        "patch_rate":         _rate([r["patch_generated"] for r in rows]),
        "resolve_rate":       _rate([r.get("resolved") is True for r in rows]),
    }


# ─── Display ──────────────────────────────────────────────────────────────────

def print_aggregate_table(results: list[dict], waf: dict[tuple, float]) -> None:
    primitives = [p for p in PRIMITIVES if any(r["primitive"] == p for r in results)]
    budgets    = sorted({r["budget"] for r in results})

    # ── WAF x budget heatmap ──────────────────────────────────────────────────
    print("WAF  (Work Amplification Factor)  — lower is better")
    print("  WAF_i(c) = mean_calls_c(i) / min_calls(i),  aggregated over tasks\n")

    bw = 8
    hdr = f"{'Primitive':<16}"
    sep = f"{'─'*16}"
    for b in budgets:
        hdr += f"{'b='+str(b):>{bw}}"
        sep += f"{'─'*bw}"
    print(hdr)
    print(sep)
    for p in primitives:
        row = f"{p:<16}"
        for b in budgets:
            val = waf.get((p, b), float("nan"))
            cell = f"{val:.3f}" if val == val else "  nan"
            row += f"{cell:>{bw}}"
        print(row)
    print()

    # ── Full aggregate table ──────────────────────────────────────────────────
    print("─" * 110)
    print(f"{'Config':<28} {'WAF':>6} {'Calls':>6} {'e2e(s)':>7} {'Tokens':>8} "
          f"{'Comp/run':>9} {'Saved':>8} {'Patch%':>7} {'Resolve%':>9}")
    print("─" * 110)

    for p in primitives:
        for b in budgets:
            s   = config_stats(results, p, b)
            cfg = f"{p}/{b}"
            if not s:
                print(f"{cfg:<28}  (no data)")
                continue
            w = waf.get((p, b), float("nan"))
            print(
                f"{cfg:<28} "
                f"{w:>6.3f} "
                f"{s['mean_n_calls']:>6.1f} "
                f"{s['mean_e2e_s']:>7.1f} "
                f"{s['mean_total_tokens']:>8.0f} "
                f"{s['mean_comp_events']:>9.1f} "
                f"{s['mean_tokens_saved']:>8.0f} "
                f"{100*s['patch_rate']:>6.1f}% "
                f"{100*s['resolve_rate']:>8.1f}%"
            )
        print()

    print("─" * 110)


def print_per_task_waf(results: list[dict]) -> None:
    """Show WAF broken down per task for inspection."""
    tasks = sorted({r["instance_id"] for r in results})
    cell: dict[tuple, list[int]] = defaultdict(list)
    for r in results:
        cell[(r["instance_id"], r["primitive"], r["budget"])].append(r["n_calls"])

    mean_calls = {k: _mean(v) for k, v in cell.items()}
    ref = {}
    for t in tasks:
        vals = [mean_calls[k] for k in mean_calls if k[0] == t and mean_calls[k] > 0]
        ref[t] = min(vals) if vals else 1.0

    primitives = [p for p in PRIMITIVES if any(r["primitive"] == p for r in results)]
    budgets    = sorted({r["budget"] for r in results})

    print("Per-task WAF breakdown")
    print("─" * 90)
    short_tasks = [t.split("__")[-1][:14] for t in tasks]
    header = f"{'Config':<28}" + "".join(f" {s:>14}" for s in short_tasks) + f" {'mean':>8}"
    print(header)
    print("─" * 90)

    for p in primitives:
        for b in budgets:
            cfg  = f"{p}/{b}"
            row  = f"{cfg:<28}"
            wafs = []
            for t in tasks:
                mc = mean_calls.get((t, p, b), 0.0)
                r  = ref.get(t, 1.0)
                if r > 0 and mc > 0:
                    w = mc / r
                    wafs.append(w)
                    row += f" {w:>14.3f}"
                else:
                    row += f" {'—':>14}"
            mean_w = _mean(wafs) if wafs else float("nan")
            row += f" {mean_w:>8.3f}" if wafs else f" {'—':>8}"
            print(row)
        print()
    print()


def print_primitive_summary(results: list[dict]) -> None:
    """Aggregate over budgets: show each primitive's mean metrics."""
    waf_all = compute_waf(results)
    budgets = sorted({r["budget"] for r in results})
    primitives = [p for p in PRIMITIVES if any(r["primitive"] == p for r in results)]

    print("Per-primitive summary  (aggregated over all budgets and tasks)\n")
    print(f"{'Primitive':<16} {'WAF':>6} {'Calls':>6} {'e2e(s)':>7} {'Tokens':>8} "
          f"{'Patch%':>7} {'Resolve%':>9}")
    print("─" * 68)

    for p in primitives:
        rows = [r for r in results if r["primitive"] == p]
        if not rows:
            continue
        w = _mean([waf_all.get((p, b), 1.0) for b in budgets])
        print(
            f"{p:<16} "
            f"{w:>6.3f} "
            f"{_mean([r['n_calls']           for r in rows]):>6.1f} "
            f"{_mean([r['e2e_latency_s']     for r in rows]):>7.1f} "
            f"{_mean([r['total_tokens']      for r in rows]):>8.0f} "
            f"{100*_rate([r['patch_generated']       for r in rows]):>6.1f}% "
            f"{100*_rate([r.get('resolved') is True  for r in rows]):>8.1f}%"
        )
    print()


def print_budget_summary(results: list[dict]) -> None:
    """Aggregate over primitives: show each budget's mean metrics."""
    waf_all    = compute_waf(results)
    budgets    = sorted({r["budget"] for r in results})
    primitives = [p for p in PRIMITIVES if any(r["primitive"] == p for r in results)]

    print("Per-budget summary  (aggregated over all primitives and tasks)\n")
    print(f"{'Budget':>8} {'WAF':>6} {'Calls':>6} {'e2e(s)':>7} {'Tokens':>8} "
          f"{'Comp/run':>9} {'Saved':>8} {'Patch%':>7} {'Resolve%':>9}")
    print("─" * 80)

    for b in budgets:
        rows = [r for r in results if r["budget"] == b]
        if not rows:
            continue
        w = _mean([waf_all.get((p, b), 1.0) for p in primitives])
        print(
            f"{b:>8} "
            f"{w:>6.3f} "
            f"{_mean([r['n_calls']            for r in rows]):>6.1f} "
            f"{_mean([r['e2e_latency_s']      for r in rows]):>7.1f} "
            f"{_mean([r['total_tokens']       for r in rows]):>8.0f} "
            f"{_mean([r['compression_events'] for r in rows]):>9.1f} "
            f"{_mean([r['total_tokens_saved'] for r in rows]):>8.0f} "
            f"{100*_rate([r['patch_generated']       for r in rows]):>6.1f}% "
            f"{100*_rate([r.get('resolved') is True  for r in rows]):>8.1f}%"
        )
    print()


def print_run_consistency(results: list[dict]) -> None:
    """Show variance across the 3 runs per config to assess stability."""
    cell: dict[tuple, list[int]] = defaultdict(list)
    for r in results:
        cell[(r["instance_id"], r["primitive"], r["budget"])].append(r["n_calls"])

    stddevs = [statistics.stdev(v) for v in cell.values() if len(v) > 1]

    print("Run-consistency: std-dev of n_calls across runs (same task+config)\n")
    if stddevs:
        print(f"  Mean std-dev : {_mean(stddevs):.2f} calls")
        print(f"  Max  std-dev : {max(stddevs):.2f} calls")
        print(f"  Min  std-dev : {min(stddevs):.2f} calls")
    else:
        print("  (not enough data for std-dev)")
    print()


# ─── CSV export ───────────────────────────────────────────────────────────────

def export_csv(results: list[dict], waf_map: dict[tuple, float]) -> None:
    csv_path = RESULTS_DIR / "experiment_results.csv"
    fieldnames = [
        "key", "instance_id", "primitive", "budget", "is_baseline", "budget_type",
        "budget_pct", "run_num",
        "n_calls", "e2e_latency_s", "llm_latency_s",
        "total_prompt_tokens", "total_completion_tokens", "total_tokens",
        "compression_events", "total_tokens_saved", "mean_compression_ratio",
        "patch_generated", "resolved",
        "waf_config_aggregate",
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in results:
            row = dict(r)
            row.pop("submission", None)   # omit the raw patch text
            row["waf_config_aggregate"] = waf_map.get((r["primitive"], r["budget"]), "")
            w.writerow(row)
    print(f"CSV exported -> {csv_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results", type=Path, default=None,
        help="Path to experiment_results.json (default: results/experiment_results.json)"
    )
    args = parser.parse_args()

    results = load_results(args.results)
    if not results:
        print("No results to analyze.")
        raise SystemExit(0)

    results = add_budget_pct(results)

    has_eval      = any(r.get("resolved") is not None for r in results)
    n_pending     = sum(1 for r in results if r.get("patch_generated") and r.get("resolved") is None)

    print("=" * 72)
    print("WAF EXPERIMENT — RESULTS ANALYSIS")
    print("=" * 72)
    print(f"  Total runs       : {len(results)}")
    print(f"  Patches generated: {sum(1 for r in results if r['patch_generated'])}/{len(results)}")
    if has_eval:
        print(f"  Resolved         : {sum(1 for r in results if r.get('resolved') is True)}/{len(results)}")
    if n_pending:
        print(f"  Pending SWE eval : {n_pending}  (run with --with-eval or --eval-only)")
    print()

    waf_map = compute_waf(results)

    print_aggregate_table(results, waf_map)
    print_per_task_waf(results)
    print_primitive_summary(results)
    print_budget_summary(results)
    print_run_consistency(results)
    export_csv(results, waf_map)

    print("=" * 72)
    print("Analysis complete.")
    print("=" * 72)


if __name__ == "__main__":
    main()
