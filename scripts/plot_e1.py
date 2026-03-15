#!/usr/bin/env python3
"""
E1 Experiment — Generate publication figures.

Figure 1: Metric Divergence Plot
  Dual-axis chart showing how resolve rate and WAF diverge from baseline
  as the token budget shrinks, with bootstrap 95% CI bands.

Figure 2: Success vs Tool Calls Scatter
  Two subplots (100% budget / 40% budget) showing per-task resolve status
  vs tool-call count, sorted by full-context tool-call count.

Usage:
    python scripts/plot_e1.py                   # reads results/experiment_results.json
    python scripts/plot_e1.py --results PATH    # custom results file
    python scripts/plot_e1.py --show            # also display interactively
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
FIGURES_DIR  = REPO_ROOT / "figures" / "e1"
RESULTS_FILE = REPO_ROOT / "results" / "experiment_results.json"

# ── constants matching run_experiment.py ───────────────────────────────────────
BUDGET_PERCENTAGES = [1.00, 0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.25]
PRIMITIVES         = ["truncation", "summarization"]
RUNS_PER_TASK      = 3
N_BOOTSTRAP        = 2_000
RANDOM_SEED        = 42

# ── colour palette ─────────────────────────────────────────────────────────────
COLOURS = {
    "truncation":    "#2196F3",   # blue
    "summarization": "#FF9800",   # orange
}

# ── helpers ────────────────────────────────────────────────────────────────────

def load_results(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def group_by(results: list[dict], *keys) -> dict:
    """Return a defaultdict(list) keyed by tuple of field values."""
    d: dict = defaultdict(list)
    for r in results:
        key = tuple(r.get(k) for k in keys)
        d[key].append(r)
    return d


def resolve_rate(runs: list[dict]) -> float:
    evaled = [r for r in runs if r.get("resolved") is not None]
    if not evaled:
        return float("nan")
    return sum(1 for r in evaled if r["resolved"] is True) / len(evaled)


def mean_calls(runs: list[dict]) -> float:
    calls = [r["n_calls"] for r in runs if r.get("n_calls", 0) > 0]
    return sum(calls) / len(calls) if calls else float("nan")


def bootstrap_ci(values: list[float], n: int = N_BOOTSTRAP, seed: int = RANDOM_SEED,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Return (lower, upper) bootstrap percentile CI for the mean."""
    if not values or all(np.isnan(values)):
        return float("nan"), float("nan")
    rng    = random.Random(seed)
    arr    = [v for v in values if not np.isnan(v)]
    if not arr:
        return float("nan"), float("nan")
    means  = [sum(rng.choices(arr, k=len(arr))) / len(arr) for _ in range(n)]
    lo     = np.percentile(means, 100 * alpha / 2)
    hi     = np.percentile(means, 100 * (1 - alpha / 2))
    return float(lo), float(hi)


# ── Figure 1 ───────────────────────────────────────────────────────────────────

def compute_divergence(results: list[dict]) -> dict:
    """
    Returns dict keyed by primitive with lists aligned to BUDGET_PERCENTAGES:
      rr_mean, rr_lo, rr_hi : resolve-rate (fraction)
      waf_mean, waf_lo, waf_hi : WAF values
    """
    by_prim_pct_task: dict = defaultdict(lambda: defaultdict(list))
    for r in results:
        prim = r.get("primitive")
        pct  = r.get("budget_pct")
        iid  = r.get("instance_id")
        if prim and pct is not None and iid:
            by_prim_pct_task[(prim, pct)][iid].append(r)

    # Baseline WAF denominator: mean calls per task at pct=1.0
    baseline_calls: dict[tuple, float] = {}  # (prim, iid) -> float
    for prim in PRIMITIVES:
        for iid, runs in by_prim_pct_task[(prim, 1.0)].items():
            mc = mean_calls(runs)
            if not np.isnan(mc):
                baseline_calls[(prim, iid)] = mc

    out: dict = {}
    for prim in PRIMITIVES:
        rr_means, rr_los, rr_his = [], [], []
        waf_means, waf_los, waf_his = [], [], []

        for pct in BUDGET_PERCENTAGES:
            task_dict = by_prim_pct_task[(prim, pct)]

            # per-task resolve rates and WAF values
            rr_vals:  list[float] = []
            waf_vals: list[float] = []
            for iid, runs in task_dict.items():
                rr = resolve_rate(runs)
                rr_vals.append(rr)

                mc  = mean_calls(runs)
                denom = baseline_calls.get((prim, iid), float("nan"))
                if not (np.isnan(mc) or np.isnan(denom) or denom == 0):
                    waf_vals.append(mc / denom)

            # aggregate
            valid_rr  = [v for v in rr_vals  if not np.isnan(v)]
            valid_waf = [v for v in waf_vals  if not np.isnan(v)]

            rr_mean = sum(valid_rr)  / len(valid_rr)  if valid_rr  else float("nan")
            waf_mean = sum(valid_waf) / len(valid_waf) if valid_waf else float("nan")

            rr_lo,  rr_hi  = bootstrap_ci(valid_rr)
            waf_lo, waf_hi = bootstrap_ci(valid_waf)

            rr_means.append(rr_mean);  rr_los.append(rr_lo);  rr_his.append(rr_hi)
            waf_means.append(waf_mean); waf_los.append(waf_lo); waf_his.append(waf_hi)

        out[prim] = dict(
            rr_mean=rr_means,  rr_lo=rr_los,   rr_hi=rr_his,
            waf_mean=waf_means, waf_lo=waf_los, waf_hi=waf_his,
        )
    return out


def plot_figure1(results: list[dict], save_path: Path) -> None:
    """Dual-axis Metric Divergence Plot."""
    div = compute_divergence(results)
    xs  = [int(p * 100) for p in BUDGET_PERCENTAGES]  # e.g. [100, 90, 75, …]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax2 = ax1.twinx()

    # CIR onset annotation (first budget where any primitive RR drops below baseline)
    cir_onset: int | None = None
    baseline_rr = {prim: div[prim]["rr_mean"][0] for prim in PRIMITIVES
                   if not np.isnan(div[prim]["rr_mean"][0])}
    for i, (pct, x) in enumerate(zip(BUDGET_PERCENTAGES[1:], xs[1:]), start=1):
        for prim in PRIMITIVES:
            rr_b = baseline_rr.get(prim, float("nan"))
            rr_c = div[prim]["rr_mean"][i]
            if not (np.isnan(rr_b) or np.isnan(rr_c)):
                if rr_c < rr_b * 0.95:
                    if cir_onset is None:
                        cir_onset = x
                    break
        if cir_onset is not None:
            break

    for prim in PRIMITIVES:
        c   = COLOURS[prim]
        d   = div[prim]
        x_a = np.array(xs, dtype=float)

        # Resolve rate on ax1 (left)
        rr  = np.array(d["rr_mean"], dtype=float)
        rlo = np.array(d["rr_lo"],   dtype=float)
        rhi = np.array(d["rr_hi"],   dtype=float)
        mask = ~np.isnan(rr)
        if mask.any():
            ax1.plot(x_a[mask], rr[mask],  color=c, linewidth=2,
                     label=f"{prim} RR", zorder=3)
            ax1.fill_between(x_a[mask], rlo[mask], rhi[mask],
                             color=c, alpha=0.15, zorder=2)

        # WAF on ax2 (right)
        waf = np.array(d["waf_mean"], dtype=float)
        wlo = np.array(d["waf_lo"],   dtype=float)
        whi = np.array(d["waf_hi"],   dtype=float)
        mask2 = ~np.isnan(waf)
        if mask2.any():
            ax2.plot(x_a[mask2], waf[mask2], color=c, linewidth=2,
                     linestyle="--", label=f"{prim} WAF", zorder=3)
            ax2.fill_between(x_a[mask2], wlo[mask2], whi[mask2],
                             color=c, alpha=0.10, zorder=2)

    # CIR onset vertical line
    if cir_onset is not None:
        ax1.axvline(cir_onset, color="gray", linestyle=":", linewidth=1.5, zorder=1)
        ax1.text(cir_onset + 0.5, ax1.get_ylim()[1] * 0.97,
                 f"CIR onset\n({cir_onset}%)",
                 fontsize=8, va="top", color="gray")

    ax1.set_xlabel("Token Budget  (% of full context)", fontsize=11)
    ax1.set_ylabel("Resolve Rate", fontsize=11, color="black")
    ax2.set_ylabel("WAF  (relative to baseline)", fontsize=11, color="dimgray")
    ax1.set_title("E1 — Metric Divergence as Token Budget Shrinks", fontsize=12, fontweight="bold")

    ax1.set_xlim(max(xs) + 2, min(xs) - 2)   # right→left (full budget on left)
    ax1.set_xticks(xs)
    ax1.tick_params(axis="x", labelsize=9)
    ax2.axhline(1.0, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)

    # Combined legend
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2,
               loc="upper right", fontsize=8, framealpha=0.85)

    plt.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved Figure 1 → {save_path}")


# ── Figure 2 ───────────────────────────────────────────────────────────────────

def plot_figure2(results: list[dict], save_path: Path) -> None:
    """Success vs Tool Calls scatter, sorted by baseline calls."""
    FOCUS_BUDGETS = [1.00, 0.40]
    SUBPLOT_TITLES = {1.00: "100% Budget (Baseline)", 0.40: "40% Budget"}

    # Gather per (primitive, pct, task) stats
    by_ppt: dict = defaultdict(list)  # (prim, pct, iid) -> runs
    for r in results:
        prim = r.get("primitive")
        pct  = r.get("budget_pct")
        iid  = r.get("instance_id")
        if prim and pct is not None and iid:
            by_ppt[(prim, pct, iid)].append(r)

    # Sort tasks by mean baseline calls (truncation baseline used as canonical sort)
    tasks_sorted = sorted(
        {r["instance_id"] for r in results},
        key=lambda iid: (
            mean_calls(by_ppt.get(("truncation", 1.0, iid), [])) or 0
        )
    )
    task_idx = {iid: i for i, iid in enumerate(tasks_sorted)}
    short_labels = [iid.split("__")[-1][:14] for iid in tasks_sorted]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)

    for ax, pct in zip(axes, FOCUS_BUDGETS):
        for prim in PRIMITIVES:
            c = COLOURS[prim]
            xs_res, ys_res = [], []
            xs_fail, ys_fail = [], []

            for iid in tasks_sorted:
                runs = by_ppt.get((prim, pct, iid), [])
                if not runs:
                    continue
                xi = task_idx[iid]
                mc = mean_calls(runs)
                rr = resolve_rate(runs)
                if np.isnan(mc):
                    continue
                if not np.isnan(rr) and rr > 0.5:
                    xs_res.append(xi); ys_res.append(mc)
                else:
                    xs_fail.append(xi); ys_fail.append(mc)

            # Resolved (filled circle), failed (open circle)
            ax.scatter(xs_res,  ys_res,  c=c, s=55, zorder=3,
                       label=f"{prim} resolved")
            ax.scatter(xs_fail, ys_fail, c="none", edgecolors=c, s=55,
                       linewidths=1.4, zorder=3,
                       label=f"{prim} failed")

        ax.set_title(SUBPLOT_TITLES[pct], fontsize=11, fontweight="bold")
        ax.set_xlabel("Task (sorted by baseline calls)", fontsize=10)
        ax.set_ylabel("Mean Tool Calls", fontsize=10)
        ax.set_xticks(range(len(tasks_sorted)))
        ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=7)
        ax.legend(fontsize=8, loc="upper left", framealpha=0.85)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("E1 — Success vs Tool Calls per Task", fontsize=12, fontweight="bold")
    plt.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved Figure 2 → {save_path}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate E1 figures.")
    parser.add_argument("--results", default=str(RESULTS_FILE),
                        help="Path to experiment_results.json")
    parser.add_argument("--out", default=str(FIGURES_DIR),
                        help="Output directory for figures")
    parser.add_argument("--show", action="store_true",
                        help="Display figures interactively after saving")
    args = parser.parse_args()

    results_path = Path(args.results)
    out_dir      = Path(args.out)

    if not results_path.exists():
        print(f"Results file not found: {results_path}")
        print("Run: python scripts/run_experiment.py")
        return

    print(f"Loading results from {results_path} …")
    results = load_results(results_path)
    print(f"  {len(results)} run records loaded.")

    out_dir.mkdir(parents=True, exist_ok=True)

    print("\nGenerating Figure 1 (Metric Divergence) …")
    plot_figure1(results, out_dir / "fig1_metric_divergence.png")

    print("Generating Figure 2 (Success vs Tool Calls) …")
    plot_figure2(results, out_dir / "fig2_success_vs_calls.png")

    if args.show:
        plt.show()

    print("\nDone.")


if __name__ == "__main__":
    main()
