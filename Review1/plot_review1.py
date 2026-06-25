"""Review1 figure suite — 8 figures generated from Review1/Review1.csv.

Outputs to Review1/figures/.

Usage:
  python3 Review1/plot_review1.py            # all 8 figures
  python3 Review1/plot_review1.py a b g      # only figures A, B, G
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).parent
CSV  = ROOT / "Review1.csv"
OUT  = Path(os.environ.get("REVIEW1_FIG_DIR", str(ROOT / "figures")))

# ── Ordering and styling ──────────────────────────────────────────────────────
PRIMITIVE_ORDER = [
    "TR", "SU-full", "SU-partial", "SS", "SS-partial", "TRC",
    "TRC+SU", "TRC+SS",
    "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial",
]
# OTRC is at budget=∞ — handled separately on budget-conditioned plots.
PRIMITIVE_ORDER_FULL = PRIMITIVE_ORDER + ["OTRC"]

COLORS = {
    "FC":               "#1F2937",  # baseline: near-black
    "TR":               "#6B7280",  # singles: gray/blue/red
    "SU-full":          "#93C5FD",
    "SU-partial":       "#3B82F6",
    "SS":               "#FCA5A5",
    "SS-partial":       "#EF4444",
    "TRC":              "#84CC16",  # TRC family: green
    "TRC+SU":           "#22C55E",
    "TRC+SS":           "#15803D",
    "OTRC":             "#F97316",  # OTRC family: orange/purple
    "OTRC+TR":          "#EA580C",
    "OTRC+SU-partial":  "#A855F7",
    "OTRC+SS-partial":  "#7E22CE",
}

# 3-bucket failure mapping for plots F and L
BUCKET_OF_FM = {
    "resolved":             "resolved",
    "submitted_unresolved": "submitted_wrong",
    "silent_crash":         "did_not_submit",
    "limits_exceeded":      "did_not_submit",
}
BUCKET_COLORS = {
    "resolved":        "#3FA34D",
    "submitted_wrong": "#E59500",
    "did_not_submit":  "#C0392B",
}
BUCKET_LABELS = {
    "resolved":        "Resolved",
    "submitted_wrong": "Submitted (wrong)",
    "did_not_submit":  "Did not submit",
}

OUTCOME_COLORS = {
    "resolved":             "#3FA34D",
    "submitted_unresolved": "#E59500",
    "silent_crash":         "#C0392B",
    "limits_exceeded":      "#9CA3AF",
}
OUTCOME_ORDER = ["resolved", "submitted_unresolved", "silent_crash", "limits_exceeded"]
OUTCOME_LABELS = {
    "resolved":             "Resolved",
    "submitted_unresolved": "Submitted (wrong)",
    "silent_crash":         "Silent crash",
    "limits_exceeded":      "LimitsExceeded",
}

plt.rcParams.update({"font.family": "sans-serif"})


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df = df[df.depth == 0.5].copy()  # scope to canonical depth — depth-grid lives in depth_analysis.py
    # Booleans come through as "True" / "False" strings (or empty)
    df["resolved_bool"] = df["resolved"].astype(str) == "True"
    df["patch_bool"]    = df["patch_generated"].astype(str) == "True"
    return df


# ── A: stacked outcome bars per primitive × budget ────────────────────────────

def fig_a_outcomes(df: pd.DataFrame) -> None:
    """3 budget panels (10k/15k/20k) + a 4th panel for FC and OTRC (no-threshold baselines)."""
    budgets = [10000, 15000, 20000]
    n_tasks = df.task_name.nunique()
    n_per_cell = n_tasks * 2  # 2 runs per task
    # 4th panel widths smaller (only 2 bars: FC + OTRC)
    fig, axes = plt.subplots(1, 4, figsize=(19, 5.2), sharey=True,
                             gridspec_kw={"width_ratios": [1, 1, 1, 0.35]})

    for ax, b in zip(axes[:3], budgets):
        sub = df[(df.token_budget == b) & (df.primitive.isin(PRIMITIVE_ORDER))]
        pv = (sub.groupby(["primitive", "failure_mode"]).size()
                 .unstack(fill_value=0)
                 .reindex(index=PRIMITIVE_ORDER, columns=OUTCOME_ORDER, fill_value=0))

        bottom = np.zeros(len(pv))
        for fm in OUTCOME_ORDER:
            ax.bar(pv.index, pv[fm], bottom=bottom,
                   color=OUTCOME_COLORS[fm], edgecolor="white", linewidth=0.6,
                   label=OUTCOME_LABELS[fm])
            bottom += pv[fm].values

        ax.set_title(f"{b // 1000}k budget", fontsize=11, fontweight="bold")
        ax.set_xticks(range(len(pv.index)))
        ax.set_xticklabels(pv.index, rotation=40, ha="right", fontsize=9)
        ax.set_ylim(0, n_per_cell)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
        ax.set_axisbelow(True)
        if ax is axes[0]:
            ax.set_ylabel(f"Number of runs (n={n_per_cell} = {n_tasks} tasks × 2 runs)", fontsize=10)

    # 4th panel: FC + OTRC (both at no-threshold)
    ax4 = axes[3]
    refs = ["FC", "OTRC"]
    pv4 = (df[df.primitive.isin(refs)]
              .groupby(["primitive", "failure_mode"]).size()
              .unstack(fill_value=0)
              .reindex(index=refs, columns=OUTCOME_ORDER, fill_value=0))
    bottom = np.zeros(len(pv4))
    for fm in OUTCOME_ORDER:
        ax4.bar(pv4.index, pv4[fm], bottom=bottom,
                color=OUTCOME_COLORS[fm], edgecolor="white", linewidth=0.6)
        bottom += pv4[fm].values
    ax4.set_title("No threshold", fontsize=11, fontweight="bold")
    ax4.set_xticks(range(len(refs)))
    ax4.set_xticklabels(refs, fontsize=9)
    ax4.set_ylim(0, n_per_cell)
    ax4.spines["top"].set_visible(False)
    ax4.spines["right"].set_visible(False)
    ax4.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
    ax4.set_axisbelow(True)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.03),
               ncol=4, frameon=False, fontsize=10)

    fig.suptitle("Outcome decomposition by primitive and budget  (FC = no compression baseline)",
                 fontsize=13, fontweight="bold", y=1.10)

    plt.tight_layout()
    out = OUT / "fig_A_outcomes.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── B: resolve rate vs budget, line plot ──────────────────────────────────────

def fig_b_resolve_vs_budget(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    budgets = [10000, 15000, 20000]

    for prim in PRIMITIVE_ORDER:
        rates = []
        for b in budgets:
            sub = df[(df.primitive == prim) & (df.token_budget == b)]
            rates.append(sub.resolved_bool.sum() / len(sub) * 100 if len(sub) else np.nan)
        ax.plot(budgets, rates, marker="o", linewidth=2, markersize=7,
                label=prim, color=COLORS[prim])

    # FC reference line (no compression at all)
    fc = df[df.primitive == "FC"]
    fc_rate = fc.resolved_bool.sum() / len(fc) * 100
    ax.axhline(fc_rate, color=COLORS["FC"], linestyle=":", linewidth=2,
               alpha=0.9, label=f"FC (no compression): {fc_rate:.1f}%")

    # OTRC reference line (no threshold)
    otrc = df[df.primitive == "OTRC"]
    otrc_rate = otrc.resolved_bool.sum() / len(otrc) * 100
    ax.axhline(otrc_rate, color=COLORS["OTRC"], linestyle="--", linewidth=1.5,
               alpha=0.8, label=f"OTRC (no threshold): {otrc_rate:.1f}%")

    ax.set_xlabel("Token budget", fontsize=11)
    ax.set_ylabel("Resolve rate (%)", fontsize=11)
    n_tasks = df.task_name.nunique()
    ax.set_title(f"Resolve rate vs budget — {n_tasks}-task ablation, {n_tasks * 2} runs per cell",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_xticks(budgets)
    ax.set_xticklabels([f"{b // 1000}k" for b in budgets])
    ax.set_ylim(0, 80)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = OUT / "fig_B_resolve_vs_budget.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── F: step-count box plot per primitive @ 15k, split by outcome ──────────────

def fig_f_step_box(df: pd.DataFrame) -> None:
    """3 boxes per primitive: resolved / submitted-wrong / did-not-submit. @ 15k (OTRC, FC at ∞)."""
    primitives = ["FC"] + PRIMITIVE_ORDER_FULL  # 13 — FC + 11 + OTRC
    fig, ax = plt.subplots(figsize=(15.5, 5.5))

    spacing = 4   # 3 boxes per primitive + 1 gap
    bucket_order = ["resolved", "submitted_wrong", "did_not_submit"]
    bucket_offset = {"resolved": 0, "submitted_wrong": 1, "did_not_submit": 2}

    for bucket in bucket_order:
        positions, data = [], []
        for i, prim in enumerate(primitives):
            if prim in ("OTRC", "FC"):
                sub = df[df.primitive == prim]
            else:
                sub = df[(df.primitive == prim) & (df.token_budget == 15000)]
            sub = sub.copy()
            sub["bucket"] = sub.failure_mode.map(BUCKET_OF_FM)
            vals = sub[sub.bucket == bucket].step_count.dropna().astype(float).values
            positions.append(i * spacing + bucket_offset[bucket])
            data.append(vals if len(vals) else np.array([np.nan]))
        bp = ax.boxplot(data, positions=positions, widths=0.85,
                        patch_artist=True, showfliers=False,
                        boxprops=dict(facecolor=BUCKET_COLORS[bucket], alpha=0.55,
                                      edgecolor=BUCKET_COLORS[bucket]),
                        medianprops=dict(color="black", linewidth=1.3),
                        whiskerprops=dict(color=BUCKET_COLORS[bucket]),
                        capprops=dict(color=BUCKET_COLORS[bucket]))

    ax.set_xticks([i * spacing + 1 for i in range(len(primitives))])
    ax.set_xticklabels(primitives, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Step count", fontsize=11)
    ax.set_title("Step-count distribution per primitive at 15k budget — split by outcome\n"
                 "(FC and OTRC shown at no-threshold)",
                 fontsize=12, fontweight="bold", pad=10)

    legend_handles = [Patch(facecolor=BUCKET_COLORS[b], alpha=0.55, label=BUCKET_LABELS[b])
                      for b in bucket_order]
    ax.legend(handles=legend_handles, loc="upper right", frameon=False, fontsize=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = OUT / "fig_F_step_box.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── G: cost-quality Pareto, mean tokens vs resolve rate, per budget ───────────

def fig_g_pareto(df: pd.DataFrame) -> None:
    """3 budget panels with FC as no-compression reference point on each panel."""
    budgets = [10000, 15000, 20000]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharey=True)

    # FC point (same on every panel — the "no compression" reference)
    fc = df[df.primitive == "FC"]
    fc_x  = fc.total_tokens_consumed.astype(float).mean() / 1000
    fc_y  = fc.resolved_bool.sum() / len(fc) * 100

    for ax, b in zip(axes, budgets):
        for prim in PRIMITIVE_ORDER:
            sub = df[(df.primitive == prim) & (df.token_budget == b)]
            if not len(sub):
                continue
            mean_tok = sub.total_tokens_consumed.astype(float).mean() / 1000
            res_pct  = sub.resolved_bool.sum() / len(sub) * 100
            ax.scatter(mean_tok, res_pct, s=140, color=COLORS[prim],
                       edgecolor="black", linewidth=0.5, zorder=3)
            ax.annotate(prim, (mean_tok, res_pct), fontsize=8.5,
                        xytext=(6, 6), textcoords="offset points")

        # FC reference (star marker, dashed lines to axes for visibility)
        ax.scatter(fc_x, fc_y, s=240, color=COLORS["FC"], marker="*",
                   edgecolor="white", linewidth=0.9, zorder=4)
        ax.annotate(f"FC", (fc_x, fc_y), fontsize=9, fontweight="bold",
                    xytext=(8, 6), textcoords="offset points", color=COLORS["FC"])
        ax.axhline(fc_y, color=COLORS["FC"], linestyle=":", linewidth=0.9, alpha=0.4)

        ax.set_title(f"{b // 1000}k budget", fontsize=11, fontweight="bold")
        ax.set_xlabel("Mean tokens per run (k)", fontsize=10)
        if ax is axes[0]:
            ax.set_ylabel("Resolve rate (%)", fontsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
        ax.set_axisbelow(True)

    fig.suptitle("Cost-quality Pareto: mean tokens per run vs resolve rate  (★ FC = no compression)",
                 fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    out = OUT / "fig_G_pareto.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── H: best single primitive vs stacked variants per budget ───────────────────

def fig_h_stacked_lift(df: pd.DataFrame) -> None:
    budgets = [10000, 15000, 20000]
    singles = ["TR", "SU-full", "SU-partial", "SS", "SS-partial", "TRC"]
    stacked = ["TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]

    fig, ax = plt.subplots(figsize=(12, 5.5))

    n_bars      = 1 + len(stacked)
    bar_width   = 0.13
    group_width = bar_width * n_bars
    x_centers   = np.arange(len(budgets))

    best_single_vals, best_single_names = [], []
    for b in budgets:
        best_v, best_n = 0, None
        for s in singles:
            sub = df[(df.primitive == s) & (df.token_budget == b)]
            if not len(sub):
                continue
            v = sub.resolved_bool.sum() / len(sub) * 100
            if v > best_v:
                best_v, best_n = v, s
        best_single_vals.append(best_v)
        best_single_names.append(best_n)

    bars_x = np.arange(n_bars) * bar_width - group_width / 2 + bar_width / 2

    ax.bar(x_centers + bars_x[0], best_single_vals, width=bar_width,
           color="#9CA3AF", edgecolor="white", linewidth=0.5,
           label="Best single primitive")
    for x, v, n in zip(x_centers + bars_x[0], best_single_vals, best_single_names):
        ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", va="bottom",
                fontsize=8.5, fontweight="bold")
        ax.text(x, -3, f"{n}", ha="center", va="top",
                fontsize=7, fontstyle="italic", color="#666")

    for i, st in enumerate(stacked, 1):
        vals = []
        for b in budgets:
            sub = df[(df.primitive == st) & (df.token_budget == b)]
            vals.append(sub.resolved_bool.sum() / len(sub) * 100 if len(sub) else 0)
        ax.bar(x_centers + bars_x[i], vals, width=bar_width,
               color=COLORS[st], edgecolor="white", linewidth=0.5,
               label=st)
        for x, v in zip(x_centers + bars_x[i], vals):
            ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", va="bottom",
                    fontsize=7.5, fontweight="bold")

    ax.set_xticks(x_centers)
    ax.set_xticklabels([f"{b // 1000}k" for b in budgets], fontsize=11)
    ax.set_xlabel("Budget", fontsize=11, labelpad=18)
    ax.set_ylabel("Resolve rate (%)", fontsize=11)
    ax.set_title("Stacking lift: best single primitive vs stacked variants",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_ylim(-7, 90)
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = OUT / "fig_H_stacked_lift.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── I: compression event distribution per primitive × budget ──────────────────

def fig_i_compression_events(df: pd.DataFrame) -> None:
    # Budget-triggered primitives only — OTRC at ∞ never triggers the budget gate.
    primitives = PRIMITIVE_ORDER  # 11
    budgets = [10000, 15000, 20000]

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), sharey=True)

    for ax, b in zip(axes, budgets):
        data, labels = [], []
        for prim in primitives:
            sub = df[(df.primitive == prim) & (df.token_budget == b)]
            if not len(sub):
                continue
            data.append(sub.compression_events.astype(float).values)
            labels.append(prim)

        bp = ax.boxplot(data, labels=labels, patch_artist=True, showfliers=True,
                        flierprops=dict(marker=".", markersize=4, markerfacecolor="black", alpha=0.5),
                        medianprops=dict(color="black", linewidth=1.4))
        for patch, prim in zip(bp["boxes"], labels):
            patch.set_facecolor(COLORS[prim])
            patch.set_alpha(0.7)
            patch.set_edgecolor(COLORS[prim])

        ax.set_title(f"{b // 1000}k budget", fontsize=11, fontweight="bold")
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        if ax is axes[0]:
            ax.set_ylabel("Compression events per run", fontsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
        ax.set_axisbelow(True)

    fig.suptitle("Budget-gate firings per run — how often each primitive's stage-2 fallback triggers",
                 fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    out = OUT / "fig_I_compression_events.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── K: TRC fallback rate (TRC standalone only — TRC+SU/SS use fallback=False) ─

def fig_k_trc_fallback(df: pd.DataFrame) -> None:
    budgets = [10000, 15000, 20000]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))

    rates, n_with_fb, n_with_comp = [], [], []
    for b in budgets:
        sub = df[(df.primitive == "TRC") & (df.token_budget == b)]
        ce  = sub.compression_events.astype(float)
        fb  = sub.trc_fallback_events.astype(float)
        rate = (fb.sum() / ce.sum() * 100) if ce.sum() else 0.0
        rates.append(rate)
        n_with_fb.append(int((fb > 0).sum()))
        n_with_comp.append(int((ce > 0).sum()))

    x = np.arange(len(budgets))
    ax.bar(x, rates, color=COLORS["TRC"], edgecolor="white", linewidth=0.5, width=0.55)
    for xi, r, fbn, cmpn in zip(x, rates, n_with_fb, n_with_comp):
        ax.text(xi, r + 1.5, f"{r:.0f}%\n({fbn}/{cmpn} runs)",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{b // 1000}k" for b in budgets], fontsize=11)
    ax.set_xlabel("Budget", fontsize=11)
    ax.set_ylabel("TR fallback rate  (% of compression events)", fontsize=10)
    ax.set_title("TRC standalone — fraction of compression events that hit the TR fallback",
                 fontsize=11, fontweight="bold", pad=12)
    ax.set_ylim(0, max(rates) * 1.35 + 5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = OUT / "fig_K_trc_fallback.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


# ── L: 30 tasks × 12 primitives heatmap, mean resolve rate ────────────────────

def fig_l_per_task_heatmap(df: pd.DataFrame) -> None:
    """30 tasks × 13 primitives, each cell split horizontally into run1 (left) / run2 (right).
    Color: green (resolved) / orange (submitted-wrong) / red (did-not-submit).
    """
    from matplotlib.patches import Rectangle

    primitives = ["FC"] + PRIMITIVE_ORDER_FULL  # 13: FC + 11 + OTRC
    tasks = sorted(df.task_name.unique())

    # outcome[task, prim, run_num] -> bucket
    # Score per task = sum of resolved across all primitives × runs (for ordering)
    score_matrix = np.zeros(len(tasks))
    cells = {}  # (i_task, j_prim) -> {1: bucket, 2: bucket}
    for i, t in enumerate(tasks):
        score = 0
        for j, prim in enumerate(primitives):
            if prim in ("OTRC", "FC"):
                sub = df[(df.primitive == prim) & (df.task_name == t)]
            else:
                sub = df[(df.primitive == prim) &
                         (df.token_budget == 15000) &
                         (df.task_name == t)]
            run_outcomes = {}
            for _, r in sub.iterrows():
                rn = int(r["run_num"])
                run_outcomes[rn] = BUCKET_OF_FM.get(r["failure_mode"], "did_not_submit")
                if r["resolved_bool"]:
                    score += 1
            cells[(i, j)] = run_outcomes
        score_matrix[i] = score

    # Order tasks easy → hard (high score → low score)
    order = np.argsort(-score_matrix)
    tasks_ordered = [tasks[i] for i in order]

    fig, ax = plt.subplots(figsize=(13, 12))
    n_rows = len(tasks_ordered)
    n_cols = len(primitives)

    # Draw each cell as 2 side-by-side rectangles
    for new_i, old_i in enumerate(order):
        for j in range(n_cols):
            outcomes = cells.get((old_i, j), {})
            for run_num, x_offset in ((1, 0.0), (2, 0.5)):
                bucket = outcomes.get(run_num, None)
                color  = BUCKET_COLORS[bucket] if bucket else "#FFFFFF"
                ax.add_patch(Rectangle(
                    (j - 0.5 + x_offset, new_i - 0.5), 0.5, 1.0,
                    facecolor=color, edgecolor="white", linewidth=0.4))

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)   # invert so easy tasks at top
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(primitives, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(tasks_ordered, fontsize=7.5)

    # Vertical separators: after FC (col 0), before OTRC (last col)
    ax.axvline(0.5, color="black", linewidth=1.2)
    ax.axvline(n_cols - 1.5, color="black", linewidth=1.2)

    # Legend
    legend_handles = [Patch(facecolor=BUCKET_COLORS[b], label=BUCKET_LABELS[b])
                      for b in ["resolved", "submitted_wrong", "did_not_submit"]]
    legend_handles.append(Patch(facecolor="white", edgecolor="#999",
                                label="left half = run 1, right half = run 2"))
    ax.legend(handles=legend_handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.05), ncol=4, frameon=False, fontsize=10)

    ax.set_title("Per-task per-run outcome by primitive  (15k budget; FC and OTRC at no-threshold)\n"
                 "Tasks ordered easy → hard by total resolved across all primitives × runs",
                 fontsize=11, fontweight="bold", pad=10)
    ax.set_aspect("auto")

    plt.tight_layout()
    out = OUT / "fig_L_per_task_heatmap.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def _per_task_value_heatmap(df: pd.DataFrame, value_col: str,
                            cmap_name: str, cbar_label: str, title: str,
                            out_name: str, log_scale: bool) -> None:
    """Shared layout: 30 tasks × 13 primitives, each cell split into run1/run2,
    colored by `value_col` from df. Same task ordering as fig_l (easy → hard by
    total resolved) so the three heatmaps line up row-for-row.
    """
    from matplotlib.patches import Rectangle
    from matplotlib.colors import LogNorm, Normalize

    primitives = ["FC"] + PRIMITIVE_ORDER_FULL
    tasks = sorted(df.task_name.unique())

    score_matrix = np.zeros(len(tasks))
    cells = {}  # (i_task, j_prim) -> {1: value, 2: value}
    for i, t in enumerate(tasks):
        score = 0
        for j, prim in enumerate(primitives):
            if prim in ("OTRC", "FC"):
                sub = df[(df.primitive == prim) & (df.task_name == t)]
            else:
                sub = df[(df.primitive == prim) &
                         (df.token_budget == 15000) &
                         (df.task_name == t)]
            run_vals = {}
            for _, r in sub.iterrows():
                rn = int(r["run_num"])
                v = r[value_col]
                run_vals[rn] = float(v) if pd.notna(v) else None
                if r["resolved_bool"]:
                    score += 1
            cells[(i, j)] = run_vals
        score_matrix[i] = score

    order = np.argsort(-score_matrix)
    tasks_ordered = [tasks[i] for i in order]

    all_vals = [v for c in cells.values() for v in c.values()
                if v is not None and v > 0]
    vmin, vmax = (min(all_vals), max(all_vals)) if all_vals else (1, 2)
    cmap = plt.get_cmap(cmap_name)
    norm = LogNorm(vmin=max(vmin, 1), vmax=vmax) if log_scale else \
           Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(13, 12))
    n_rows = len(tasks_ordered)
    n_cols = len(primitives)

    for new_i, old_i in enumerate(order):
        for j in range(n_cols):
            run_vals = cells.get((old_i, j), {})
            for run_num, x_offset in ((1, 0.0), (2, 0.5)):
                v = run_vals.get(run_num)
                color = cmap(norm(v)) if (v is not None and v > 0) else "#FFFFFF"
                ax.add_patch(Rectangle(
                    (j - 0.5 + x_offset, new_i - 0.5), 0.5, 1.0,
                    facecolor=color, edgecolor="white", linewidth=0.4))

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(primitives, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(tasks_ordered, fontsize=7.5)
    ax.axvline(0.5, color="black", linewidth=1.2)
    ax.axvline(n_cols - 1.5, color="black", linewidth=1.2)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.025, pad=0.04)
    cbar.set_label(cbar_label, fontsize=9)

    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    ax.set_aspect("auto")

    plt.tight_layout()
    out = OUT / out_name
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


def fig_l_tokens_heatmap(df: pd.DataFrame) -> None:
    _per_task_value_heatmap(
        df,
        value_col="total_tokens_consumed",
        cmap_name="Blues",
        cbar_label="Total tokens consumed (log scale)",
        title=("Per-task per-run total tokens consumed by primitive  "
               "(15k budget; FC and OTRC at ∞)\n"
               "Tasks ordered easy → hard by total resolved (same row order "
               "as outcome heatmap); white = no run / missing data"),
        out_name="fig_L_tokens_heatmap.png",
        log_scale=True,
    )


def fig_l_steps_heatmap(df: pd.DataFrame) -> None:
    _per_task_value_heatmap(
        df,
        value_col="step_count",
        cmap_name="Purples",
        cbar_label="Step count (linear)",
        title=("Per-task per-run step count by primitive  "
               "(15k budget; FC and OTRC at ∞)\n"
               "Tasks ordered easy → hard by total resolved (same row order "
               "as outcome heatmap); white = no run / missing data"),
        out_name="fig_L_steps_heatmap.png",
        log_scale=False,
    )


# ── Driver ────────────────────────────────────────────────────────────────────

PLOTS = {
    "a":  ("Outcome decomposition",       fig_a_outcomes),
    "b":  ("Resolve rate vs budget",      fig_b_resolve_vs_budget),
    "f":  ("Step-count box (split)",      fig_f_step_box),
    "g":  ("Cost-quality Pareto",         fig_g_pareto),
    "h":  ("Stacking lift",               fig_h_stacked_lift),
    "i":  ("Compression event dist",      fig_i_compression_events),
    "k":  ("TRC fallback rate",           fig_k_trc_fallback),
    "l":  ("Per-task outcome heatmap",    fig_l_per_task_heatmap),
    "lt": ("Per-task tokens heatmap",     fig_l_tokens_heatmap),
    "ls": ("Per-task steps heatmap",      fig_l_steps_heatmap),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plots", nargs="*", default=list(PLOTS.keys()),
                        help="Subset of plot keys to generate (default: all)")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    print(f"loaded {len(df)} rows from {CSV}")
    for k in args.plots:
        k = k.lower()
        if k not in PLOTS:
            print(f"  unknown plot '{k}', skipping (valid: {list(PLOTS)})")
            continue
        title, fn = PLOTS[k]
        print(f"\n[{k.upper()}] {title}")
        fn(df)


if __name__ == "__main__":
    main()
