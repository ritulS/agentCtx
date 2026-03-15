#!/usr/bin/env python3
"""
Generate experiment graphs from WAF experiment results.

Saves figures to graphs/ directory.

Usage:
    python scripts/plot_results.py [--results path/to/experiment_results.json]
"""

import argparse
import json
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

warnings.filterwarnings("ignore")

WORKSPACE_ROOT = Path(__file__).parent.parent
GRAPHS_DIR     = WORKSPACE_ROOT / "graphs"
RESULTS_FILE   = WORKSPACE_ROOT / "results" / "experiment_results.json"

PRIMITIVES    = ["truncation", "summarization"]
TOKEN_BUDGETS = [1_000, 1_500, 2_500, 4_000]

COLORS = {
    "truncation":   "#2196F3",   # blue
    "summarization":"#FF5722",   # deep orange
}
HATCHES = {
    "truncation":   "",
    "summarization":"///",
}

BUDGET_LABELS = {1000: "1k", 1500: "1.5k", 2500: "2.5k", 4000: "4k"}

TASK_SHORT = {
    "pallets__flask-4045":    "flask-4045",
    "django__django-13447":   "django-13447",
    "pytest-dev__pytest-5221":"pytest-5221",
}

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size":  11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})


# ─── Data helpers ─────────────────────────────────────────────────────────────

def load(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def by_config(results, primitive, budget):
    return [r for r in results if r["primitive"] == primitive and r["budget"] == budget]


def mean(lst):
    return sum(lst) / len(lst) if lst else 0.0


def rate(lst):
    return sum(bool(x) for x in lst) / len(lst) if lst else 0.0


def compute_waf(results):
    """(primitive, budget) -> aggregate WAF."""
    cell: dict[tuple, list] = defaultdict(list)
    for r in results:
        cell[(r["instance_id"], r["primitive"], r["budget"])].append(r["n_calls"])

    tasks = list({r["instance_id"] for r in results})
    mean_calls = {k: mean(v) for k, v in cell.items()}

    ref = {}
    for t in tasks:
        vals = [mean_calls[k] for k in mean_calls if k[0] == t and mean_calls[k] > 0]
        ref[t] = min(vals) if vals else 1.0

    waf_cfg: dict[tuple, list] = defaultdict(list)
    for t in tasks:
        for p in PRIMITIVES:
            for b in TOKEN_BUDGETS:
                mc = mean_calls.get((t, p, b), 0.0)
                r  = ref.get(t, 1.0)
                w  = mc / r if r > 0 and mc > 0 else None
                if w is not None:
                    waf_cfg[(p, b)].append(w)

    return {k: mean(v) for k, v in waf_cfg.items()}


# ─── Figure 1 — WAF vs Budget ─────────────────────────────────────────────────

def fig_waf(results, waf):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(TOKEN_BUDGETS))
    width = 0.35

    for i, prim in enumerate(PRIMITIVES):
        vals = [waf.get((prim, b), np.nan) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width,
               label=prim, color=COLORS[prim], hatch=HATCHES[prim],
               edgecolor="white", linewidth=0.5, alpha=0.9)
        for xi, v in zip(x + offset, vals):
            if not np.isnan(v):
                ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=9)

    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--", label="ideal (WAF=1)")
    ax.set_xlabel("Token Budget")
    ax.set_ylabel("WAF  (lower = better)")
    ax.set_title("Work Amplification Factor by Budget & Primitive")
    ax.set_xticks(x)
    ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out = GRAPHS_DIR / "waf_vs_budget.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 2 — Total Tokens Used ────────────────────────────────────────────

def fig_tokens(results):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(TOKEN_BUDGETS))
    width = 0.35

    for i, prim in enumerate(PRIMITIVES):
        vals = [mean([r["total_tokens"] for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width,
               label=prim, color=COLORS[prim], hatch=HATCHES[prim],
               edgecolor="white", linewidth=0.5, alpha=0.9)
        for xi, v in zip(x + offset, vals):
            if v > 0:
                ax.text(xi, v + 50, f"{int(v)}", ha="center", va="bottom", fontsize=8, rotation=45)

    ax.set_xlabel("Token Budget")
    ax.set_ylabel("Mean Total Tokens (prompt + completion)")
    ax.set_title("Token Usage by Budget & Primitive")
    ax.set_xticks(x)
    ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
    ax.legend()
    fig.tight_layout()
    out = GRAPHS_DIR / "tokens_used.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 3 — E2E Latency ──────────────────────────────────────────────────

def fig_latency(results):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(TOKEN_BUDGETS))
    width = 0.35

    for i, prim in enumerate(PRIMITIVES):
        vals = [mean([r["e2e_latency_s"] for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width,
               label=prim, color=COLORS[prim], hatch=HATCHES[prim],
               edgecolor="white", linewidth=0.5, alpha=0.9)
        for xi, v in zip(x + offset, vals):
            if v > 0:
                ax.text(xi, v + 0.5, f"{v:.0f}s", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Token Budget")
    ax.set_ylabel("Mean E2E Latency (seconds)")
    ax.set_title("End-to-End Latency by Budget & Primitive")
    ax.set_xticks(x)
    ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
    ax.legend()
    fig.tight_layout()
    out = GRAPHS_DIR / "e2e_latency.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 4 — Patch Generation Rate ────────────────────────────────────────

def fig_patch_rate(results):
    has_eval = any(r.get("resolved") is not None for r in results)

    n_metrics = 2 if has_eval else 1
    fig, axes = plt.subplots(1, n_metrics, figsize=(7 * n_metrics, 4.5), squeeze=False)

    x = np.arange(len(TOKEN_BUDGETS))
    width = 0.35

    for ax_idx, (metric, title, col_suffix) in enumerate([
        ("patch_generated", "Patch Generation Rate", "patch_rate.png"),
        ("resolved",        "Success Rate (SWE-bench Resolved)", "resolve_rate.png"),
    ][:n_metrics]):
        ax = axes[0][ax_idx]
        for i, prim in enumerate(PRIMITIVES):
            if metric == "patch_generated":
                vals = [rate([r["patch_generated"] for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
            else:
                vals = [rate([r.get("resolved") is True for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
            offset = (i - 0.5) * width
            bars = ax.bar(x + offset, [v * 100 for v in vals], width,
                          label=prim, color=COLORS[prim], hatch=HATCHES[prim],
                          edgecolor="white", linewidth=0.5, alpha=0.9)
            for xi, v in zip(x + offset, vals):
                ax.text(xi, v * 100 + 1, f"{v*100:.0f}%", ha="center", va="bottom", fontsize=9)

        ax.set_xlabel("Token Budget")
        ax.set_ylabel("Rate (%)")
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
        ax.set_ylim(0, 115)
        ax.legend()

    fig.tight_layout()
    out = GRAPHS_DIR / "patch_and_resolve_rate.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 5 — Per-task breakdown ───────────────────────────────────────────

def fig_per_task(results):
    tasks   = sorted({r["instance_id"] for r in results})
    n_tasks = len(tasks)

    fig, axes = plt.subplots(n_tasks, 2, figsize=(13, 3.5 * n_tasks))
    if n_tasks == 1:
        axes = [axes]

    x     = np.arange(len(TOKEN_BUDGETS))
    width = 0.35

    for row, task in enumerate(tasks):
        task_rows = [r for r in results if r["instance_id"] == task]
        short = TASK_SHORT.get(task, task.split("__")[-1])

        # Left: n_calls
        ax = axes[row][0]
        for i, prim in enumerate(PRIMITIVES):
            vals = [mean([r["n_calls"] for r in task_rows if r["primitive"] == prim and r["budget"] == b]) for b in TOKEN_BUDGETS]
            offset = (i - 0.5) * width
            ax.bar(x + offset, vals, width,
                   label=prim, color=COLORS[prim], hatch=HATCHES[prim],
                   edgecolor="white", linewidth=0.5, alpha=0.9)
        ax.set_title(f"{short} — LLM calls (n_calls)")
        ax.set_xticks(x)
        ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
        ax.set_ylabel("Calls")
        if row == 0:
            ax.legend()

        # Right: patch generated (bool as bar height)
        ax = axes[row][1]
        for i, prim in enumerate(PRIMITIVES):
            vals = [rate([r["patch_generated"] for r in task_rows if r["primitive"] == prim and r["budget"] == b]) for b in TOKEN_BUDGETS]
            offset = (i - 0.5) * width
            bars = ax.bar(x + offset, [v * 100 for v in vals], width,
                          label=prim, color=COLORS[prim], hatch=HATCHES[prim],
                          edgecolor="white", linewidth=0.5, alpha=0.9)
            for xi, v in zip(x + offset, vals):
                ax.text(xi, v * 100 + 1, "Y" if v == 1 else ("" if v == 0 else f"{v*100:.0f}%"),
                        ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.set_title(f"{short} — Patch Generated")
        ax.set_xticks(x)
        ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
        ax.set_ylabel("Patch rate (%)")
        ax.set_ylim(0, 115)
        if row == 0:
            ax.legend()

    fig.suptitle("Per-Task Breakdown", fontsize=14, y=1.01)
    fig.tight_layout()
    out = GRAPHS_DIR / "per_task_breakdown.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 6 — Compression Events vs N_calls (scatter) ──────────────────────

def fig_scatter(results):
    fig, ax = plt.subplots(figsize=(7, 5))

    markers = {"truncation": "o", "summarization": "s"}
    for prim in PRIMITIVES:
        rows = [r for r in results if r["primitive"] == prim]
        x_vals = [r["compression_events"] for r in rows]
        y_vals = [r["n_calls"]            for r in rows]
        colors = ["#4CAF50" if r["patch_generated"] else "#F44336" for r in rows]
        ax.scatter(x_vals, y_vals, c=colors, marker=markers[prim], s=80,
                   edgecolors="black", linewidths=0.5, alpha=0.85, label=prim)

    # legend for prim
    prim_handles = [mpatches.Patch(color=COLORS[p], label=p) for p in PRIMITIVES]
    # legend for patch outcome
    patch_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#4CAF50",
                   markersize=9, markeredgecolor="black", label="patch generated"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#F44336",
                   markersize=9, markeredgecolor="black", label="no patch"),
    ]
    ax.legend(handles=prim_handles + patch_handles, loc="upper left", fontsize=9)

    ax.set_xlabel("Compression Events")
    ax.set_ylabel("LLM Calls (n_calls)")
    ax.set_title("Compression Events vs LLM Calls\n(color = patch outcome)")
    fig.tight_layout()
    out = GRAPHS_DIR / "scatter_comp_vs_calls.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 7 — N_calls heatmap (task × config) ──────────────────────────────

def fig_heatmap(results):
    tasks   = sorted({r["instance_id"] for r in results})
    configs = [(p, b) for p in PRIMITIVES for b in TOKEN_BUDGETS]
    labels_x = [f"{p[:5]}\n{BUDGET_LABELS[b]}" for p, b in configs]
    labels_y = [TASK_SHORT.get(t, t.split("__")[-1]) for t in tasks]

    data = np.zeros((len(tasks), len(configs)))
    for ti, task in enumerate(tasks):
        for ci, (prim, budget) in enumerate(configs):
            rows = [r for r in results if r["instance_id"] == task
                    and r["primitive"] == prim and r["budget"] == budget]
            data[ti, ci] = mean([r["n_calls"] for r in rows]) if rows else 0

    fig, ax = plt.subplots(figsize=(12, 3.5))
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
    fig.colorbar(im, ax=ax, label="Mean n_calls")

    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels(labels_x, fontsize=9)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(labels_y)
    ax.set_title("LLM Calls Heatmap  (task × config)")

    # Annotate cells
    for ti in range(len(tasks)):
        for ci in range(len(configs)):
            v = data[ti, ci]
            ax.text(ci, ti, f"{v:.0f}", ha="center", va="center",
                    fontsize=9, color="black" if v < data.max() * 0.7 else "white")

    fig.tight_layout()
    out = GRAPHS_DIR / "heatmap_calls.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 8 — WAF line plot ─────────────────────────────────────────────────

def fig_waf_line(results, waf):
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for prim in PRIMITIVES:
        x_vals = TOKEN_BUDGETS
        y_vals = [waf.get((prim, b), np.nan) for b in TOKEN_BUDGETS]
        ax.plot(x_vals, y_vals, marker="o", linewidth=2, markersize=7,
                color=COLORS[prim], label=prim)
        for x, y in zip(x_vals, y_vals):
            if not np.isnan(y):
                ax.text(x, y + 0.05, f"{y:.2f}", ha="center", va="bottom", fontsize=9,
                        color=COLORS[prim])

    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--", label="ideal (WAF=1)")
    ax.set_xlabel("Token Budget")
    ax.set_ylabel("WAF")
    ax.set_title("WAF vs Token Budget (line plot)")
    ax.set_xscale("log")
    ax.set_xticks(TOKEN_BUDGETS)
    ax.set_xticklabels([BUDGET_LABELS[b] for b in TOKEN_BUDGETS])
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out = GRAPHS_DIR / "waf_line.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Figure 9 — Summary dashboard ────────────────────────────────────────────

def fig_dashboard(results, waf):
    """2×2 summary dashboard."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    x     = np.arange(len(TOKEN_BUDGETS))
    width = 0.35
    blabels = [BUDGET_LABELS[b] for b in TOKEN_BUDGETS]

    # ── Top-left: WAF ──────────────────────────────────────────────────────────
    ax = axes[0][0]
    for i, prim in enumerate(PRIMITIVES):
        vals = [waf.get((prim, b), 0) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width, label=prim, color=COLORS[prim],
               hatch=HATCHES[prim], edgecolor="white", alpha=0.9)
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--")
    ax.set_title("WAF  (lower = better)")
    ax.set_xticks(x); ax.set_xticklabels(blabels)
    ax.set_ylabel("WAF"); ax.legend()

    # ── Top-right: Tokens ──────────────────────────────────────────────────────
    ax = axes[0][1]
    for i, prim in enumerate(PRIMITIVES):
        vals = [mean([r["total_tokens"] for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width, label=prim, color=COLORS[prim],
               hatch=HATCHES[prim], edgecolor="white", alpha=0.9)
    ax.set_title("Mean Token Usage")
    ax.set_xticks(x); ax.set_xticklabels(blabels)
    ax.set_ylabel("Tokens"); ax.legend()

    # ── Bottom-left: Latency ───────────────────────────────────────────────────
    ax = axes[1][0]
    for i, prim in enumerate(PRIMITIVES):
        vals = [mean([r["e2e_latency_s"] for r in by_config(results, prim, b)]) for b in TOKEN_BUDGETS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, vals, width, label=prim, color=COLORS[prim],
               hatch=HATCHES[prim], edgecolor="white", alpha=0.9)
    ax.set_title("Mean E2E Latency (s)")
    ax.set_xticks(x); ax.set_xticklabels(blabels)
    ax.set_ylabel("Seconds"); ax.legend()

    # ── Bottom-right: Patch rate ───────────────────────────────────────────────
    ax = axes[1][1]
    has_eval = any(r.get("resolved") is not None for r in results)
    for i, prim in enumerate(PRIMITIVES):
        patch_vals   = [rate([r["patch_generated"]        for r in by_config(results, prim, b)]) * 100 for b in TOKEN_BUDGETS]
        resolve_vals = [rate([r.get("resolved") is True   for r in by_config(results, prim, b)]) * 100 for b in TOKEN_BUDGETS] if has_eval else None
        offset = (i - 0.5) * width
        ax.bar(x + offset, patch_vals, width, label=f"{prim} (patch)", color=COLORS[prim],
               hatch=HATCHES[prim], edgecolor="white", alpha=0.6)
        if resolve_vals:
            ax.bar(x + offset, resolve_vals, width, label=f"{prim} (resolved)", color=COLORS[prim],
                   edgecolor="white", alpha=1.0)
    ax.set_title("Patch Rate%  (resolved darker if available)")
    ax.set_xticks(x); ax.set_xticklabels(blabels)
    ax.set_ylabel("Rate (%)"); ax.set_ylim(0, 115); ax.legend(fontsize=8)

    fig.suptitle("WAF Experiment Dashboard", fontsize=15, fontweight="bold")
    fig.tight_layout()
    out = GRAPHS_DIR / "dashboard.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=RESULTS_FILE)
    args = parser.parse_args()

    results = load(args.results)
    print(f"Loaded {len(results)} runs from {args.results}\n")

    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    # Quick summary
    patched  = sum(1 for r in results if r["patch_generated"])
    resolved = sum(1 for r in results if r.get("resolved") is True)
    has_eval = any(r.get("resolved") is not None for r in results)
    print(f"Patches generated : {patched}/{len(results)}")
    print(f"Resolved (eval)   : {resolved}/{len(results)}"
          + ("  (eval not run yet)" if not has_eval else ""))
    print()

    waf = compute_waf(results)

    print("Generating figures...")
    fig_waf(results, waf)
    fig_waf_line(results, waf)
    fig_tokens(results)
    fig_latency(results)
    fig_patch_rate(results)
    fig_per_task(results)
    fig_scatter(results)
    fig_heatmap(results)
    fig_dashboard(results, waf)

    print(f"\nAll figures saved to {GRAPHS_DIR}/")

    # Print WAF table
    print("\nWAF summary:")
    print(f"  {'Config':<24}  {'WAF':>6}")
    for p in PRIMITIVES:
        for b in TOKEN_BUDGETS:
            w = waf.get((p, b), float("nan"))
            print(f"  {p}/{BUDGET_LABELS[b]:<20}  {w:>6.3f}")


if __name__ == "__main__":
    main()
