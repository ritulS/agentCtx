"""Selected ICLR plot bank: five maintained figure renderers and their inputs.

Run `venv/bin/python ICLR_analysis/Iclr_plot_bank.py` to generate all figures.
Every data figure is computed from the tracked outcomes tables
(analysis/outcomes/, which carry the 2026-09-24 Qwen verdict re-evaluation)
and the audited Q3 exports in plots/q3/; the computed inputs are written as
CSVs next to each figure. Use --list or --help for selection and
input/output options. Shared visual conventions live in plot_style.py; data
definitions and usage are documented in Iclr_plot_bank.md. No files are
written on import.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba, LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle, Ellipse, FancyBboxPatch
try:
    from .plot_style import (PAPER_STYLE, KNOB_STYLE, ORDER, MK, PSTYLE, PDARK, RESOLVE_HIGHLIGHT, COST_HIGHLIGHT,
                             PLIGHT, pcol, pmark, prim_handles, save_figure)
    from .paper_figures import load_q2_runs
    from .appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                         raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                         SWE_TIMEOUT)
    from .intro_fig import make_wrap_figure as fig_intro_policy_axes
except ImportError:
    from plot_style import (PAPER_STYLE, KNOB_STYLE, ORDER, MK, PSTYLE, PDARK, RESOLVE_HIGHLIGHT, COST_HIGHLIGHT,
                            PLIGHT, pcol, pmark, prim_handles, save_figure)
    from paper_figures import load_q2_runs
    from appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                        raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                        SWE_TIMEOUT)
    from intro_fig import make_wrap_figure as fig_intro_policy_axes

ROOT = Path(__file__).resolve().parent.parent
ROWS = ORDER + ["FC"]
DT = dict(zip(["tr", "su-full", "su-partial", "ss", "ss-partial"], ["TR", "SU", "SU-p", "SS", "SS-p"]))
MARK = {p: MK["qwen35b"] for p in DT.values()}
FIGURES = {
    "intro_01_policy_axes_wrap": "setup",
    "q1_24_qwen_overview": "q1",
    "q1_26_knob_execution": "q1",
    "q2_qwen_task_map_only": "q1",
    "q3_policy_preferences_and_design": "q3",
}

# ------------------------------------------------------------ inputs
# Every figure input is computed here from the tracked outcomes tables (the
# SWE-bench table carries the 2026-09-24 Qwen verdict re-evaluation) with the
# definitions of q1_frontier.py / token_cost_ledger.py / q1_knob_execution.py
# and the Q3 exports, validated to reproduce those exports to floating-point
# precision (2026-09-24). Only the audited Q3 exports in plots/q3/ are read:
# their Devstral, GLM and Terminal-Bench rows are reused; the Qwen SWE-bench
# rows are recomputed.
SWE_OUTCOMES = ROOT / "analysis/outcomes/swebench_outcomes.csv"
TB_OUTCOMES = ROOT / "analysis/outcomes/terminalbench_outcomes_0924.csv"
Q3_DATA_DIR = ROOT / "ICLR_analysis/plots/q3"
# q1_frontier.py iterates policies in this order with one bootstrap stream.
Q1_ORDER = ["FC", "OTRC", "TR", "SU", "SU-p", "SS", "SS-p", "TRC", "TRC+SU", "TRC+SS",
            "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p"]
Q3_MODELS = ["qwen35b", "devstral24b", "glm47flash"]
Q3_PAIRS = [("SS-p", "SS"), ("TRC+SS", "SS"), ("OTRC", "TRC"), ("OTRC+SS-p", "OTRC")]
Q3_METRICS = [("resolve", "resolve", False), ("latency_ratio", "time", True),
              ("billed_input_ratio", "bill", True)]


# ------------------------------------------------------------ Figure 2 inputs
def q1_frontier(df, B=5000, seed=0, resolve_resamples=10000, resolve_seed=210926):
    """q1_frontier.py statistics from one setting's attempts (panel_runs frame),
    plus load_qwen_overview's absolute resolve-rate intervals."""
    rng = np.random.default_rng(seed)
    R = per_task(df, "res", False)          # resolve uses all attempts
    U = per_task(df, "usage", True)
    C = per_task(df, "bill", True)
    L = per_task(df, "e2e", True)
    rows = []
    for p in Q1_ORDER:
        rr = diff_ci(R, p, B, rng) if p != "FC" else (0.0, 0.0, 0.0, int(R["FC"].notna().sum()))
        u = ratio_ci(U, p, B, rng); c = ratio_ci(C, p, B, rng); l = ratio_ci(L, p, B, rng)
        values = R[p].dropna().to_numpy()
        brng = np.random.default_rng(resolve_seed)
        idx = brng.integers(0, len(values), (resolve_resamples, len(values)))
        lo, hi = np.percentile(values[idx].mean(axis=1) * 100, [2.5, 97.5])
        rows.append(dict(policy=p, resolve=values.mean() * 100,
                         dres=rr[0], dres_lo=rr[1], dres_hi=rr[2],
                         usage=u[0], usage_lo=u[1], usage_hi=u[2],
                         bill=c[0], bill_lo=c[1], bill_hi=c[2],
                         time=l[0], time_lo=l[1], time_hi=l[2], n_shared=l[3],
                         resolve_lo=lo, resolve_hi=hi, n_success_tasks=len(values),
                         n_attempts=int(df.policy.eq(p).sum())))
    frame = pd.DataFrame(rows).set_index("policy")
    for metric in ("dres", "bill", "time", "usage", "resolve"):
        if not ((frame[metric + "_lo"] <= frame[metric] + 1e-12) &
                (frame[metric] <= frame[metric + "_hi"] + 1e-12)).all():
            raise ValueError(f"{metric}: interval does not enclose estimate")
    return frame.loc[["FC"] + ORDER]


def primary_setting(benchmark, model, outcomes_path):
    """All attempts of the primary setting (depth 0.5, primary threshold) on the
    full cohort: main-track cells, FC and OTRC as references."""
    runs, dropped = load_runs(benchmark, model, outcomes_path)
    budgets = budget_levels(runs)
    tasks, label = read_tasks(benchmark, "full")
    df = panel_runs(runs, tasks, 0.5, "primary", budgets)
    print(f"{benchmark}/{model}: {label}, primary budget {budgets['primary']}, "
          f"{len(df)} attempts ({dropped} dropped with <2 model calls)")
    return df


# ------------------------------------------------------------ Figure 3 inputs
def removed_tokens(P):
    """q1_knob_execution.removed: context removed by detected compressions."""
    tot = 0.0
    for t in range(1, len(P)):
        drop = P[t - 1] - P[t]
        if drop >= max(1000, 0.15 * P[t - 1]):
            tot += drop
    return tot


def knob_settings():
    """(track, cell, policy, sweep, x) in q1_knob_execution.load order, then the
    45-cell grid in load_resolve_grid order."""
    sweep = [("main", "di__binf__fc", "FC", "primary", 0.0)]
    for prim, pol in DT.items():
        for b in (10, 15, 20):
            sweep.append(("main" if b == 15 else "ablation", f"d05__b{b}k__{prim}", pol,
                          "primary" if b == 15 else "threshold", float(b)))
        for keep in (7, 3):
            sweep.append(("ablation", f"d{keep:02d}__b15k__{prim}", pol, "depth", (10 - keep) / 10))
    grid = [(pol, budget, depth, "main" if (budget, depth) == (15, .5) else "ablation",
             f"d{int(round(10 * (1 - depth))):02d}__b{budget}k__{prim}")
            for prim, pol in DT.items() for budget in (10, 15, 20) for depth in (.3, .5, .7)]
    grid.append(("FC", None, None, "main", "di__binf__fc"))
    return sweep, grid


def knob_cell(outcomes, raw, track, cell, tasks):
    """Per-attempt quantities of token_cost_ledger.per_run for one cell on
    ABL-25, runs 1-3, with `resolved` taken from the outcomes table."""
    g = outcomes[outcomes.experiment_section.eq(track) & outcomes.cell.eq(cell)]
    if len(g) != len(tasks) * 3 or not g.groupby("task_name").size().eq(3).all():
        raise ValueError(f"{track}/{cell}: expected {len(tasks) * 3} attempts, found {len(g)}")
    if g.duplicated(["task_name", "run_num"]).any():
        raise ValueError(f"{track}/{cell}: duplicate attempts")
    verdict = g.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError(f"{cell}: resolved must be True, False, or missing")
    rows = []
    for r, res in zip(g.itertuples(index=False), verdict.eq("true").fillna(False)):
        P = json.loads(r.step_prompt_tokens) if isinstance(r.step_prompt_tokens, str) else []
        if len(P) < 2:
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: fewer than two model calls")
        C = json.loads(r.step_completion_tokens) if isinstance(r.step_completion_tokens, str) else []
        totP, totC = float(r.total_prompt_tokens), float(r.total_completion_tokens)
        flagged, summP = raw[(r.source_file, r.task_name, int(r.run_num))]
        sumP = float(sum(P))
        if abs(totP - sumP - summP) > 1:
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: prompt accounting mismatch")
        Cbar = (float(sum(C)) if C else totC) / len(P)
        e2e = float(r.latency_e2e_s)
        if not np.isfinite(e2e):
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: missing latency")
        rows.append(dict(task=r.task_name, run=int(r.run_num), resolved=bool(res),
                         n_calls=len(P), sumP=sumP, summP=summP,
                         compression_events=int(r.compression_events), e2e=e2e,
                         capped=e2e >= SWE_TIMEOUT, R_hi=fresh_cached(P, flagged, Cbar),
                         removed=removed_tokens(P)))
    df = pd.DataFrame(rows)
    df["bill"] = df.R_hi + 0.1 * (df.sumP - df.R_hi) + df.summP
    return df


def knob_inputs(outcomes_path, B=2000, seed=0):
    """q1_knob_execution.csv and q1_knob_execution_resolve_grid.csv."""
    tasks, label = read_tasks("swebench", "ablation")
    d = pd.read_csv(outcomes_path, low_memory=False)
    d = d[d.benchmark.eq("swebench") & d.model_key.eq("qwen35b") & d.task_name.isin(tasks) &
          d.run_num.isin([1, 2, 3])].copy()
    sweep, grid = knob_settings()
    cells = {(track, cell) for track, cell, *_ in sweep} | {(track, cell) for _, _, _, track, cell in grid}
    d = d[[(t, c) in cells for t, c in zip(d.experiment_section, d.cell)]]
    raw = raw_fields(sorted(d.source_file.unique()))
    per_cell = {(track, cell): knob_cell(d, raw, track, cell, tasks) for track, cell in sorted(cells)}
    if not per_cell[("main", "di__binf__fc")].removed.eq(0).all():
        raise ValueError("compression detector fires on FC attempts")

    rng = np.random.default_rng(seed)

    def ci(v, task):
        m = pd.DataFrame({"v": v, "t": task}).groupby("t").v.mean().values
        bs = m[rng.integers(0, len(m), (B, len(m)))].mean(1)
        return np.percentile(bs, 2.5), np.percentile(bs, 97.5)

    rows = []
    for track, cell, pol, sweep_name, x in sweep:
        g = per_cell[(track, cell)]
        c = g[~g.capped]
        lo, hi = ci(g.n_calls.values, g.task.values)
        rlo, rhi = ci(g.resolved.values.astype(float), g.task.values)
        rows.append(dict(policy=pol, sweep=sweep_name, x=x, n=len(g),
                         events=g.compression_events.mean(), removed=g.removed.mean(),
                         calls=g.n_calls.mean(), calls_lo=lo, calls_hi=hi,
                         resolve_lo=rlo, resolve_hi=rhi,
                         bill=c.bill.mean(), e2e=c.e2e.mean(), n_completed=len(c),
                         capped=g.capped.mean(), stepcap=g.n_calls.ge(125).mean(),
                         resolve=g.resolved.mean()))
    S = pd.DataFrame(rows)

    records = []
    for pol, budget, depth, track, cell in grid:
        runs = per_cell[(track, cell)]
        success = runs.resolved
        completed = ~runs.capped
        records.append(dict(policy=pol, threshold_k=budget, depth_removed=depth, track=track, cell=cell,
                            n_attempts=len(runs), n_success=int(success.sum()), resolve=success.mean(),
                            events=runs.compression_events.mean(), n_completed=int(completed.sum()),
                            resolve_excl_time_caps=success[completed].mean(),
                            bill_all=runs.bill.mean(), bill_completed=runs.bill[completed].mean(),
                            latency_all=runs.e2e.mean(), latency_completed=runs.e2e[completed].mean()))
    resolve_grid = pd.DataFrame(records)
    fc_bill = resolve_grid.loc[resolve_grid.policy.eq("FC"), "bill_all"].iloc[0]
    resolve_grid["bill_vs_fc"] = resolve_grid.bill_all / fc_bill
    if len(resolve_grid) != 46 or resolve_grid.duplicated(["policy", "threshold_k", "depth_removed"]).any():
        raise ValueError("Knob grid must contain 45 distinct settings plus FC")
    print(f"tuning: {label}, {len(S)} sweep cells, {len(resolve_grid)} grid rows, "
          f"FC resolve {100 * S.loc[S.policy.eq('FC'), 'resolve'].iloc[0]:.1f}%")
    return S, resolve_grid


# ------------------------------------------------------------ Figure 5 inputs
def q3_inputs(frame, df, baseline_dir, model="qwen35b", B=2000, seed=0):
    """Qwen SWE-bench policy values and design contrasts recomputed from the
    outcomes table (the only Q3 rows the re-evaluation touches); every other
    row (Devstral, GLM, Terminal-Bench) copied from the audited exports."""
    values = pd.read_csv(baseline_dir / "q3_combined_policy_values.csv")
    contrasts = pd.read_csv(baseline_dir / "q3_combined_design_contrasts.csv")
    for name, table, keys in [("policy values", values, ["benchmark", "model_key", "policy", "metric"]),
                              ("design contrasts", contrasts, ["benchmark", "model_key", "p", "q"])]:
        if table.duplicated(keys).any():
            raise ValueError(f"Duplicate Q3 {name} in {baseline_dir}")
        if set(table.model_key) != set(Q3_MODELS) or set(table.benchmark) != {"SWE-bench", "Terminal-Bench"}:
            raise ValueError(f"Q3 {name} in {baseline_dir}: expected three models on both benchmarks")
    pol = ["FC"] + ORDER
    value_rows, contrast_rows = [], []
    for metric, col, ascending in Q3_METRICS:
        v = frame.loc[pol, col]
        rank = v.round(6).rank(ascending=ascending, method="average")
        for p in pol:
            # Resolve counts every task; the paired ratios count uncapped shared tasks.
            n_tasks = int(frame.loc[p, "n_success_tasks" if metric == "resolve" else "n_shared"])
            value_rows.append(dict(benchmark="SWE-bench", model_key=model, policy=p, metric=metric,
                                   value=float(v[p]), rank=float(rank[p]), n_tasks=n_tasks))
    R = per_task(df, "res", False)
    for p, q in Q3_PAIRS:
        m = R[[p, q]].dropna()
        d = ((m[p] - m[q]) * 100).to_numpy()
        rng = np.random.default_rng(seed)        # one fresh stream per pair
        boots = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
        contrast_rows.append(dict(benchmark="SWE-bench", model_key=model, p=p, q=q,
                                  estimate=d.mean(), lo=np.percentile(boots, 2.5),
                                  hi=np.percentile(boots, 97.5), n_tasks=len(d),
                                  p_attempts=int(df.policy.eq(p).sum()),
                                  q_attempts=int(df.policy.eq(q).sum())))
    keep = lambda t: ~(t.benchmark.eq("SWE-bench") & t.model_key.eq(model))
    values = pd.concat([pd.DataFrame(value_rows), values[keep(values)]], ignore_index=True)
    contrasts = pd.concat([pd.DataFrame(contrast_rows), contrasts[keep(contrasts)]], ignore_index=True)
    return values, contrasts


# ------------------------------------------------------------ Figure 2
# Reviewer revisions of Iclr_plot_bank.fig_qwen_overview (wide 2x5 layout):
# no "Qwen" heading, larger fonts and markers, black arrows marking the
# better direction of each axis, both axes start at 0, no y=x guide in the
# third column, one benchmark heading per row (no panel titles), FC is a black
# square instead of a star.
FC_MARKER = "s"


def overview_handles():
    handles = [Line2D([], [], marker=FC_MARKER, ls="", color="black", ms=10, label="FC")]
    for policy in ORDER:
        c, open_ = pcol(policy), PSTYLE[policy][2]
        handles.append(Line2D([], [], marker="o", ls="", ms=10,
                              mfc="white" if open_ else c, mec=c, mew=1.0 if open_ else 0.3,
                              label=policy))
    return handles


def better_arrows(ax, x_better, y_better, label=None, occupied=()):
    """One thick light-grey block arrow pointing toward the corner the panel
    favours, optionally labelled. It sits in the favoured corner when that
    corner is free of data; otherwise in the diagonally opposite corner (the
    direction never changes). `occupied` lists (x, y) in axes fractions covered by
    markers and their intervals."""
    dx = -1 if x_better == "left" else 1
    dy = -1 if y_better == "down" else 1
    span, pad = 0.19, 0.06
    label_h = 0.14 if label else 0.0      # room for the word beside the tail

    def footprint(cx, cy):
        # cx, cy = the corner the arrow occupies (True = right / top)
        x_edge = 0.94 if cx else 0.06
        y_edge = 0.94 if cy else 0.06
        xa, xb = sorted([x_edge, x_edge - span if cx else x_edge + span])
        ya, yb = sorted([y_edge, y_edge - span if cy else y_edge + span])
        # the arrow shaft is half as wide as it is long: pad the box modestly
        return (xa - pad, xb + pad, ya - pad - (label_h if not cy else 0), yb + pad + (label_h if cy else 0))

    # The favoured corner when it is free of data, otherwise the opposite
    # corner (the arrow then points across the panel toward the favoured one).
    preferred = (x_better == "right", y_better == "up")
    xa, xb, ya, yb = footprint(*preferred)
    free = not any(xa <= x <= xb and ya <= y <= yb for (x, y) in occupied)
    cx, cy = preferred if free else (not preferred[0], not preferred[1])
    # Arrow centred in that corner box, pointing (dx, dy).
    x_edge = 0.94 if cx else 0.06
    y_edge = 0.94 if cy else 0.06
    xmid = x_edge - span / 2 if cx else x_edge + span / 2
    ymid = y_edge - span / 2 if cy else y_edge + span / 2
    head = (xmid + dx * span / 2, ymid + dy * span / 2)
    tail = (xmid - dx * span / 2, ymid - dy * span / 2)
    ax.annotate("", xy=head, xytext=tail, xycoords="axes fraction",
                textcoords="axes fraction", zorder=6,
                arrowprops=dict(arrowstyle="simple,head_length=1.0,head_width=1.6,tail_width=0.8",
                                color=BETTER_ARROW, lw=0, shrinkA=0, shrinkB=0))
    if label:
        # Just outside the arrow box on the side away from the panel edge
        # vertically, aligned with the corner's edge horizontally.
        ax.text(x_edge, (y_edge - span - 0.02) if cy else (y_edge + span + 0.02), label,
                transform=ax.transAxes, fontsize=9, color="#8a8a8a", style="italic",
                ha="right" if cx else "left", va="top" if cy else "bottom", zorder=6)


OVERVIEW_PANELS = [  # (x metric, y metric, x label, y label, better x, better y)
    ("usage", "dres", "token usage / FC", "\u0394 resolve rate (pp)", "left", "up"),
    ("usage", "time", "token usage / FC", "wall-clock / FC", "left", "down"),
    ("usage", "bill", "token usage / FC", "billed input cost / FC", "left", "down"),
    ("resolve", "bill", "resolve rate (%)", "billed input cost / FC", "right", "down"),
    ("resolve", "time", "resolve rate (%)", "wall-clock / FC", "right", "down"),
]
BETTER_ARROW = "#b5b5b5"     # arrow toward the better corner


def draw_overview_rows(axes, rows):
    """Fill an (n, 5) axes array with the Figure 2 panels, one row per
    (heading, frontier frame). Shared by Figure 2 and the appendix depth /
    trigger figures so they keep the same layout."""
    last = len(rows) - 1
    for row, (label, frame) in enumerate(rows):
        fc = frame.loc["FC"]
        # Shared metric limits within each row: every displayed CI, the FC
        # reference, and 0 on both axes.
        bounds = {}
        for metric, reference in [("dres", 0), ("time", 1), ("bill", 1), ("resolve", fc.resolve)]:
            low = min(frame[metric + "_lo"].min(), reference, 0)
            high = max(frame[metric + "_hi"].max(), reference, 0)
            margin = max((high - low) * 0.075, 0.04 if metric in ["time", "bill"] else 0.5)
            bounds[metric] = (low - margin if low < 0 else 0, high + margin)
        usage_bounds = (0, 1.06)
        for position, (xmetric, ymetric, xlabel, ylabel, xbest, ybest) in enumerate(OVERVIEW_PANELS):
            ax = axes[row, position]
            ylim = bounds[ymetric]
            xlim = usage_bounds if xmetric == "usage" else bounds["resolve"]
            ax.axhline(fc[ymetric], color="#999999", lw=0.6, ls="--", zorder=0)
            ax.axvline(fc[xmetric], color="#999999", lw=0.6, ls="--", zorder=0)
            for policy in ORDER:
                r = frame.loc[policy]
                errors = {"yerr": [[r[ymetric] - r[ymetric + "_lo"]], [r[ymetric + "_hi"] - r[ymetric]]]}
                ax.errorbar(r[xmetric], r[ymetric], **errors,
                            fmt="none", ecolor="#c8c8c8", elinewidth=0.8, capsize=0, zorder=1)
                pmark(ax, r[xmetric], r[ymetric], policy, "o", s=64)
            ax.scatter(fc[xmetric], fc[ymetric], marker=FC_MARKER, color="black", s=80, zorder=5)
            ax.set_xlim(xlim); ax.set_ylim(ylim)
            # Marker centres and interval ends in axes fractions, for arrow placement.
            fx = lambda v: (v - xlim[0]) / (xlim[1] - xlim[0])
            fy = lambda v: (v - ylim[0]) / (ylim[1] - ylim[0])
            occupied = [(fx(fc[xmetric]), fy(fc[ymetric]))]
            for policy in ORDER:
                r = frame.loc[policy]
                occupied += [(fx(r[xmetric]), fy(v)) for v in (r[ymetric], r[ymetric + "_lo"], r[ymetric + "_hi"])]
            better_arrows(ax, xbest, ybest, occupied=occupied)
            if position == 0:
                # One row heading, rotated in the left margin, centred on the row,
                # with a thin rule between it and the y-axis label.
                # Anchored to the figure edge so the y-label width does not matter.
                pos = ax.get_position()
                fig = ax.figure
                fig.text(0.014, (pos.y0 + pos.y1) / 2, label, fontsize=15, rotation=90,
                         ha="center", va="center", weight="bold")
                fig.add_artist(Line2D([0.032, 0.032], [pos.y0 - 0.01, pos.y1 + 0.01],
                                      transform=fig.transFigure, color="#555555", lw=0.8))
            if row == last:
                ax.set_xlabel(xlabel, labelpad=3, fontsize=13)
            ax.set_ylabel(ylabel, labelpad=3, fontsize=11.5)   # longest label must fit the panel height
            ax.tick_params(axis="both", labelsize=12)
            ax.grid(alpha=0.2, lw=0.5)
            ax.locator_params(axis="both", nbins=3)


def overview_legend(fig, y=1.005):
    handles = overview_handles()
    # Two legend rows: 13 entries at this font size overflow an 11-inch line.
    # Matplotlib fills legend columns first; interleave so the key reads by row.
    top, bottom = handles[:7], handles[7:]
    handles = [h for pair in zip(top, bottom + [None]) for h in pair if h is not None]
    fig.legend(handles=handles, loc="upper center", ncol=7, frameon=False,
               handletextpad=0.3, columnspacing=1.0, fontsize=12, bbox_to_anchor=(0.52, y))


def overview_figure(n_rows):
    """Figure and (n_rows, 5) axes with the Figure 2 proportions: 11 in wide,
    1.75 in per row plus the legend band; 2 rows = 11.0 x 4.7 in (2200 x 940
    px at 200 dpi)."""
    height = 1.2 + 1.75 * n_rows
    fig, axes = plt.subplots(n_rows, 5, figsize=(11.0, height), squeeze=False)
    # Left margin holds the rotated row heading; rows need less vertical
    # room without the floating heading above each.
    fig.subplots_adjust(left=0.10, right=0.992, bottom=0.60 / height, top=1 - 0.66 / height,
                        wspace=0.42, hspace=0.36)
    return fig, axes


def fig_qwen_overview(frames):
    fig, axes = overview_figure(2)
    draw_overview_rows(axes, [("SWE-bench", frames["swebench"]),
                              ("Terminal-Bench", frames["terminalbench"])])
    overview_legend(fig)
    return fig


# ------------------------------------------------------------ Figure 3
def sweep_series(S, sweep, pol, col):
    """Sweep line including the shared primary point at its slot."""
    xs = [.3, .5, .7] if sweep == "depth" else [10., 15., 20.]
    prim_x = .5 if sweep == "depth" else 15.
    g = S[S.policy.eq(pol)]
    return xs, [g.loc[g.sweep.eq("primary") if v == prim_x
                      else g.sweep.eq(sweep) & g.x.eq(v), col].iloc[0] for v in xs]


def fig_knob_execution(S, resolve_grid):
    """Ritul's 2026-09-24 local revision of the plot-bank renderer (larger
    KNOB_STYLE fonts, yellow highest-resolve and green lowest-cost cells,
    oval lowest-latency, winner legend, FC summary line), with the sweep
    x-axis labels shortened to "D" and "Threshold", compressions starting
    at 0, and billed input and latency plotted as ratios to FC on a range
    around 1. Not yet committed to the
    plot bank, so it is carried here.
    """
    fc = S[S.policy.eq("FC")].iloc[0]
    with plt.rc_context(KNOB_STYLE):
        fig = plt.figure(figsize=(12.8, 5.4))
        grid = fig.add_gridspec(3, 3, width_ratios=[1, 1, 3.1],
                                left=.052, right=.995, bottom=.085, top=.84,
                                wspace=.16, hspace=.32)
        # Cost and latency are shown relative to FC (FC = 1.0 dotted line).
        metrics = [("events", "Compressions/run", None),
                   ("bill", "Billed input / FC", 1 / fc.bill),
                   ("e2e", "Latency / FC", 1 / fc.e2e)]
        handles = []
        for row, (col_name, ylab, scale) in enumerate(metrics):
            row_axes = []
            for col, sweep in enumerate(("depth", "threshold")):
                ax = fig.add_subplot(grid[row, col])
                row_axes.append(ax)
                for pol in DT.values():
                    xs, ys = sweep_series(S, sweep, pol, col_name)
                    ys = np.array(ys) * (scale or 1)
                    partial = pol.endswith("-p")
                    line, = ax.plot(range(3), ys, color=pcol(pol), marker=MARK[pol],
                                    ms=6, lw=1.6, ls="--" if partial else "-",
                                    mfc="white" if partial else pcol(pol), label=pol)
                    if row == 0 and col == 0:
                        handles.append(line)
                if col_name != "events":
                    # FC reference line; the legend names it, no inline label.
                    ax.axhline(fc[col_name] * (scale or 1), color=".4", ls=":", lw=.9)
                ax.set_xticks(range(3), ["0.3", "0.5", "0.7"] if sweep == "depth"
                              else ["10K", "15K", "20K"])
                ax.set_xlim(-.2, 2.2)
                if row == 0:
                    ax.set_ylim(0, 7.2)
                    ax.set_title("(a) Depth sweep" if col == 0 else "(b) Trigger sweep",
                                 loc="left", pad=8)
                if col == 0:
                    ax.set_ylabel(ylab)
                if row == 2:
                    ax.set_xlabel("D" if sweep == "depth" else "Threshold")
                ax.grid(axis="y", color="#ececec", lw=.5)
                ax.set_axisbelow(True)
                ax.spines[["top", "right"]].set_visible(False)
            # Compressions start at 0; the FC-ratio rows share a range around
            # FC = 1 with a small margin so the differences stay readable.
            lims = [a.get_ylim() for a in row_axes]
            lo, hi = min(l for l, _ in lims), max(h for _, h in lims)
            if row == 0:
                lo = 0
            else:
                lo, hi = min(lo, 1) - .03, max(hi, 1) + .03
            for a in row_axes:
                a.set_ylim(lo, hi)

        ax = fig.add_subplot(grid[:, 2])
        # The table has no x-axis labels, so let it run down to the figure edge
        # and use the taller rows for larger text.
        pos = ax.get_position()
        ax.set_position([pos.x0, .02, pos.width, pos.y1 - .02])
        ax.set_axis_off()
        ax.set_title("(c) Resolve, cost, and latency", loc="left", pad=8)
        ax.set_xlim(0, 11.3)
        ax.set_ylim(.25, 19.35)
        left = 2.2
        ax.text(.02, 17.92, "Primitive", fontsize=11, va="center")
        ax.text(1.30, 17.92, "Trigger", fontsize=11, va="center")
        for j, (depth, label) in enumerate(((.3, "Shallow (0.3)"), (.5, "Depth 0.5"), (.7, "Deep (0.7)"))):
            center = left + 3*j + 1.5
            ax.text(center, 18.93, label, ha="center", va="center", fontsize=14, fontweight="bold")
            ax.plot([left + 3*j + .08, left + 3*j + 2.92], [18.45, 18.45], color=".65", lw=.5)
            for k, label in enumerate(("RR (%)", "Cost/FC", "Lat. (s)")):
                ax.text(left + 3*j + k + .5, 17.92, label, ha="center", va="center", fontsize=10.5)
        ax.plot([0, 11.2], [17.36, 17.36], color=".35", lw=.65)
        for i, pol in enumerate(DT.values()):
            ytop = 16.66 - 3.4*i
            ax.text(.02, ytop-1, pol, color="black", fontweight="bold", fontsize=14, va="center")
            for k, budget in enumerate((10, 15, 20)):
                y = ytop-k
                g = resolve_grid[resolve_grid.policy.eq(pol) & resolve_grid.threshold_k.eq(budget)]
                assert len(g) == 3
                best, cheapest, fastest = g.resolve.max(), g.bill_vs_fc.min(), g.latency_all.min()
                ax.text(1.35, y, f"{budget}K", ha="center", fontsize=12.5, va="center")
                for j, depth in enumerate((.3, .5, .7)):
                    r = g[g.depth_removed.eq(depth)].iloc[0]
                    # One bounded triplet = one primitive/trigger/depth setting.
                    ax.add_patch(Rectangle((left + 3*j + .025, y-.43), 2.95, .86,
                                           facecolor="#f3f4f6", edgecolor="#c9cdd2",
                                           linewidth=.45, zorder=0))
                    xresolve, xcost, xlatency = [left + 3*j + t + .5 for t in range(3)]
                    if np.isclose(r.resolve, best):
                        ax.add_patch(Rectangle((xresolve-.42, y-.35), .84, .70,
                                               facecolor=RESOLVE_HIGHLIGHT, edgecolor="none", zorder=1))
                    if np.isclose(r.bill_vs_fc, cheapest):
                        ax.add_patch(Rectangle((xcost-.42, y-.35), .84, .70,
                                               facecolor=COST_HIGHLIGHT, edgecolor="none", zorder=1))
                    if np.isclose(r.latency_all, fastest):
                        ax.add_patch(Ellipse((xlatency, y), .94, .76, fill=False,
                                             edgecolor=".15", linewidth=.9, zorder=4))
                    ax.text(xlatency, y, f"{r.latency_all:.0f}", ha="center", va="center", fontsize=13.5,
                            fontweight="bold" if np.isclose(r.latency_all, fastest) else "normal")
                    ax.text(xresolve, y, f"{100*r.resolve:.1f}", ha="center", va="center", fontsize=13.5,
                            fontweight="bold" if np.isclose(r.resolve, best) else "normal")
                    ax.text(xcost, y, f"{r.bill_vs_fc:.2f}", ha="center", va="center", fontsize=13.5,
                            fontweight="bold" if np.isclose(r.bill_vs_fc, cheapest) else "normal")
            if i < 4:
                ax.plot([0, 11.2], [ytop-2.7, ytop-2.7], color=".60", lw=.65)
        ax.plot([0, 11.2], [.48, .48], color=".35", lw=.65)
        # Legend placement follows the centers of the two plot blocks.
        left_center = (grid[0, 0].get_position(fig).x0 + grid[0, 1].get_position(fig).x1) / 2
        right_center = (grid[0, 2].get_position(fig).x0 + grid[0, 2].get_position(fig).x1) / 2
        fc_handle = Line2D([], [], color=".45", ls=":", lw=.9, label="FC")
        fig.legend(handles=handles + [fc_handle], loc="upper center", ncol=6, frameon=False,
                   bbox_to_anchor=(left_center, .985), handlelength=1.1, columnspacing=.55, handletextpad=.3)
        winners = [Patch(facecolor=RESOLVE_HIGHLIGHT, edgecolor="none",
                         label="Highest resolve"),
                   Patch(facecolor=COST_HIGHLIGHT, edgecolor="none",
                         label="Lowest cost"),
                   Line2D([], [], linestyle="none", marker="o", markerfacecolor="none",
                          markeredgecolor=".15", markersize=8, label="Lowest latency"),
                   ]
        fig.legend(handles=winners, loc="upper center", ncol=3, frameon=False,
                   bbox_to_anchor=(right_center, .985), handlelength=1.4,
                   columnspacing=.9, handletextpad=.3, fontsize=12)
        fig.text(.993, .911,
                 f"FC: {100*fc.resolve:.1f}% / 1.00× / "
                 f"{resolve_grid.loc[resolve_grid.policy.eq('FC'), 'latency_all'].iloc[0]:.0f}s",
                 ha="right", va="center", fontsize=12)
        return fig


# Figure 4 rows: the plot-bank rows plus an oracle row directly above FC. The
# oracle counts a task as solved when any of the thirteen policies (the twelve
# compression policies or FC) solves it (per-policy majority of 3 runs, as in
# every other row), i.e. the resolve reachable if the right policy were known
# for each task. Its Lost column is therefore always 0.
ORACLE = "Oracle"
TASK_MAP_ROWS = ORDER + [ORACLE, "FC"]
ORACLE_COLOR = "#1b9e77"


# ------------------------------------------------------------ Figure 4
def row_color(p):
    return ORACLE_COLOR if p == ORACLE else pcol(p)


def task_map_legend(fig, y=.995):
    handles = [Line2D([], [], marker='s', ls='', mfc='#525252', mec='none', ms=3.5, label='Solved'),
               Line2D([], [], marker='x', ls='', color='#666666', ms=3.5, mew=.6, label='Lost'),
               Patch(facecolor='#f4f4f4', edgecolor='#cccccc', lw=.3, label='Neither')]
    fig.legend(handles=handles, ncol=3, loc='upper center', bbox_to_anchor=(.5, y),
               frameon=False, fontsize=6.8, handlelength=1, handletextpad=.3,
               columnspacing=.9, borderaxespad=0)


def draw_task_map(fig, solved, missed, shared, rows=TASK_MAP_ROWS, band=(0.0, 1.0)):
    """Draw one task map into the vertical band (bottom, height) of `fig`, in
    figure fractions, with the geometry of a 5.5 x 2.25 in figure scaled to
    the band. Shared by Figure 4 (one band) and the appendix stacks.
    """
    y0, yh = band
    n_tasks = len(solved)
    bottom, height = y0 + .17 * yh, .58 * yh
    # Narrow number columns and small gaps leave the width to the maps
    # (reviewer note: the cells were cramped while the columns had slack).
    totals = fig.add_axes([.130, bottom, .030, height])
    cell_width = .324 / n_tasks
    missed_width, solved_width = len(missed) * cell_width, len(shared) * cell_width
    miss_ax = fig.add_axes([.165, bottom, missed_width, height], sharey=totals)
    # Gained sits right next to the FC-missed map, Lost right next to the
    # FC-solved map; the wider gap separates the two map halves.
    gain_left = .165 + missed_width + .003
    gain_ax = fig.add_axes([gain_left, bottom, .021, height], sharey=totals)
    shared_left = gain_left + .021 + .018   # a visible gap between the two halves
    shared_ax = fig.add_axes([shared_left, bottom, solved_width, height], sharey=totals)
    loss_ax = fig.add_axes([shared_left + solved_width + .003, bottom, .021, height], sharey=totals)
    map_axes = [totals, miss_ax, gain_ax, shared_ax, loss_ax]

    for ax, tasks, is_missed in [(miss_ax, missed, True), (shared_ax, shared, False)]:
        pixels = np.ones((len(rows), len(tasks), 4))
        for j, p in enumerate(rows):
            for i, t in enumerate(tasks):
                if solved.loc[t, p]:
                    pixels[j, i] = to_rgba(row_color(p))
                elif is_missed:
                    pixels[j, i] = to_rgba('#f4f4f4')
        ax.imshow(pixels, interpolation='nearest', aspect='auto',
                  extent=[-.5, len(tasks) - .5, len(rows) - .5, -.5])
        for x in np.arange(-.5, len(tasks)):
            ax.axvline(x, color='white', alpha=.45, lw=.18, zorder=2)
        for y in np.arange(.5, len(rows)):
            ax.axhline(y, color='white', lw=.55, zorder=3)
        ax.set_xlim(-.5, len(tasks) - .5)
    fc_total = int(solved.FC.sum())
    for j, p in enumerate(rows):
        lost = [i for i, t in enumerate(shared) if not solved.loc[t, p]]
        shared_ax.scatter(lost, [j] * len(lost), marker='x', s=4, color='#666666', linewidths=.4, zorder=4)
        if p == 'FC':
            totals.scatter(-.95, j, s=11, marker=FC_MARKER, color='black', clip_on=False,
                           transform=totals.get_yaxis_transform(), zorder=5)
        count = int(solved[p].sum())
        if count > fc_total:
            totals.axhspan(j - .44, j + .44, xmin=.02, xmax=.98, facecolor='#eaf2e5', edgecolor='none')
        totals.text(.5, j, str(count), ha='center', va='center', fontsize=6.8,
                    fontweight='bold' if count > fc_total else 'normal', color='#333333')
        gain = int((~solved.FC & solved[p]).sum())
        loss = int((solved.FC & ~solved[p]).sum())
        gain_ax.text(.5, j, f'+{gain}', ha='center', va='center', fontsize=6.8, color='#333333')
        loss_ax.text(.5, j, f'−{loss}' if loss else '0', ha='center', va='center', fontsize=6.8, color='#333333')
    for ax in map_axes:
        ax.set_xticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    boundaries = [rows.index(p) + .5 for p in ('TRC', 'SS-p', 'TRC+SS', 'OTRC+SS-p', 'OTRC', ORACLE)
                  if p in rows]
    for ax in map_axes:
        if ax is not totals:
            ax.tick_params(axis='y', left=False, labelleft=False)
        if ax in [miss_ax, shared_ax]:
            for boundary in boundaries:
                ax.axhline(boundary, color='white', lw=1.4, zorder=3)
    totals.set_ylim(len(rows) - .4, -.6)
    totals.set_yticks(np.arange(len(rows)), rows)
    totals.tick_params(axis='y', length=0, pad=4, labelsize=6.8)
    for ax in [totals, gain_ax, loss_ax]:
        ax.set_xlim(0, 1)
    headers = [(totals, 'Solved'), (miss_ax, f'FC missed {len(missed)} tasks'),
               (gain_ax, 'Gained'), (shared_ax, f'FC solved {len(shared)} tasks'), (loss_ax, 'Lost')]
    for ax, header in headers:
        ax.text(.5, 1.025, header, transform=ax.transAxes, ha='center', va='bottom', fontsize=6.4)
    for ax in map_axes:
        pos = ax.get_position()
        ax.set_position([.15 + (pos.x0 - .144) * 2.02, y0 + .035 * yh, pos.width * 2.02, .80 * yh])
    return map_axes


def fig_task_map(solved, missed, shared, rows=TASK_MAP_ROWS):
    """Iclr_plot_bank.fig_task_map with the row list as a parameter.

    Identical drawing to the plot bank for the policy rows; `rows` may add
    the oracle row (ORACLE), drawn in its own colour. Reviewer revisions: no
    heading (goes in the caption), centred legend closer to the map, slightly
    larger fonts, one-line column headers, and no row markers except FC's,
    a black square as in Figure 2. Family separators are placed after TRC, SS-p, TRC+SS, OTRC+SS-p,
    OTRC and (when present) the oracle row.
    """
    fig = plt.figure(figsize=(5.5, 2.25))
    task_map_legend(fig)
    draw_task_map(fig, solved, missed, shared, rows)
    return fig


# ------------------------------------------------------------ Figure 5
def fig_policy_preferences(l, d):
    """Policy values and paired design contrasts from the Q3 exports.

    Panel (a) uses the Figure 3(c) table encoding: grey boxed triplets per
    model, highest resolve as a yellow cell, lowest billed cost as a green
    cell, lowest latency ratio as an oval, winners in bold, a winner legend
    above; no rank shading or rank colour bar, policy labels in black. The
    panel titles are reduced to "(a)" and "(b)" centred under each panel.
    """
    RESOLVE_HIGHLIGHT, COST_HIGHLIGHT = '#ffe680', '#d9edcf'   # as in Figure 3's table
    pol = ['FC'] + ORDER
    models = ['qwen35b', 'devstral24b', 'glm47flash']
    names = ['Qwen', 'Devstral', 'GLM']
    pairs = [('SS-p', 'SS'), ('TRC+SS', 'SS'), ('OTRC', 'TRC'), ('OTRC+SS-p', 'OTRC')]
    diffmap = LinearSegmentedColormap.from_list(
        'diff', [PDARK['llm'], PLIGHT['llm'], '#fafafa', PLIGHT['rule'], PDARK['rule']])
    dn = Normalize(-20, 20)

    def clean(a, nr, nc, grid='white', labelsize=5.5):
        a.set_xticks(np.arange(-.5, nc, 1), minor=True)
        a.set_yticks(np.arange(-.5, nr, 1), minor=True)
        a.grid(which='minor', color=grid, lw=.6)
        a.tick_params(which='both', length=0, pad=2, labelsize=labelsize)
        for sp in a.spines.values():
            sp.set_visible(False)

    with plt.rc_context(PAPER_STYLE):
        fig = plt.figure(figsize=(6.75, 2.25))
        # (a) policy table
        # Wider table than the plot bank (panel (b) narrowed) for larger fonts.
        ax = fig.add_axes([.105, .075, .455, .655])
        vals = np.empty((13, 9))
        for j, m in enumerate(models):
            for k, metric in enumerate(['resolve', 'latency_ratio', 'billed_input_ratio']):
                a = l[(l.benchmark == 'SWE-bench') & (l.model_key == m) & (l.metric == metric)]
                vals[:, 3 * j + k] = a.set_index('policy').loc[pol].value
        ax.set_xlim(-.5, 8.5)
        ax.set_ylim(12.5, -.5)
        for row in range(13):
            for j in range(3):
                ax.add_patch(Rectangle((3 * j - .47, row - .41), 2.94, .82, facecolor='#f3f4f6',
                                       edgecolor='#c9cdd2', linewidth=.45, zorder=0))
        for col in range(9):
            v = vals[:, col]
            kind = col % 3  # 0 resolve, 1 latency, 2 bill
            best = np.isclose(v, v.max() if kind == 0 else v.min(), atol=1e-10, rtol=0)
            for row in range(13):
                if best[row] and kind == 0:
                    ax.add_patch(Rectangle((col - .42, row - .33), .84, .66, facecolor=RESOLVE_HIGHLIGHT,
                                           edgecolor='none', zorder=1))
                elif best[row] and kind == 2:
                    ax.add_patch(Rectangle((col - .42, row - .33), .84, .66, facecolor=COST_HIGHLIGHT,
                                           edgecolor='none', zorder=1))
                elif best[row]:
                    # Pill rather than ellipse: the cells are too narrow for an
                    # ellipse to clear the corners of the number.
                    ax.add_patch(FancyBboxPatch((col - .48, row - .39), .96, .78, fill=False,
                                                boxstyle='round,pad=0,rounding_size=0.3',
                                                edgecolor='.15', linewidth=.7, zorder=4))
                label = f'{v[row]:.1f}' if kind == 0 else f'{v[row]:.2f}'
                ax.text(col, row, label, ha='center', va='center', fontsize=7.3, color='#222222',
                        fontweight='bold' if best[row] else 'normal', zorder=5)
        ax.set_yticks(range(13), pol)
        ax.set_xticks(range(9), ['Res. \u2191\n(%)', 'Lat. \u2193\n/ FC', 'Bill \u2193\n/ FC'] * 3)
        ax.xaxis.tick_top()
        for j, (name, bud) in enumerate(zip(names, ['15K', '21K', '13K'])):
            ax.text((j + .5) / 3, 1.19, f'{name} ({bud})', transform=ax.transAxes,
                    ha='center', fontsize=8)
        clean(ax, 13, 9, grid='none', labelsize=7.3)
        ax.tick_params(axis='x', labelsize=6.4)  # metric headers must not touch
        winners = [Patch(facecolor=RESOLVE_HIGHLIGHT, edgecolor='none', label='Highest resolve'),
                   Patch(facecolor=COST_HIGHLIGHT, edgecolor='none', label='Lowest cost'),
                   Line2D([], [], ls='none', marker='o', mfc='none', mec='.15', ms=4.5,
                          label='Lowest latency')]
        fig.legend(handles=winners, loc='upper center', ncol=3, frameon=False, fontsize=6,
                   bbox_to_anchor=(.3325, .995), handlelength=1.2, columnspacing=1.0,
                   handletextpad=.4, borderaxespad=0)
        fig.text(.3325, .015, '(a)', ha='center', fontsize=7)

        # (b) design contrasts
        decisions = ['Preserve\nrecent history', 'Clear before\nrewriting',
                     'Clear every\nstep', 'Add partial\nrewriting']
        comparisons = ['(SS-p vs SS)', '(TRC+SS vs SS)', '(OTRC vs TRC)', '(OTRC+SS-p\nvs OTRC)']
        for bi, bench in enumerate(['SWE-bench', 'Terminal-Bench']):
            bottom = [.50, .205][bi]
            ar = fig.add_axes([.66, bottom, .33, .22])
            v = np.empty((3, 4))
            sig = np.zeros((3, 4), bool)
            for j, (pp, q) in enumerate(pairs):
                for i, m in enumerate(models):
                    r = d[(d.benchmark == bench) & (d.model_key == m) & (d.p == pp) & (d.q == q)].iloc[0]
                    v[i, j] = r.estimate
                    sig[i, j] = r.lo > 0 or r.hi < 0
            dm = ar.imshow(v, cmap=diffmap, norm=dn, aspect='auto')
            for i in range(3):
                for j in range(4):
                    lum = np.dot(diffmap(dn(v[i, j]))[:3], [.2126, .7152, .0722])
                    val = 0 if abs(v[i, j]) < 1e-9 else v[i, j]
                    ar.text(j, i, f'{val:+.1f}' + ('*' if sig[i, j] else ''), ha='center', va='center',
                            fontsize=6, color='white' if lum < .50 else '#222222')
            ar.set_yticks(range(3), names)
            ar.set_xticks([])
            clean(ar, 3, 4)
            if bi == 0:
                for j, (decision, comparison) in enumerate(zip(decisions, comparisons)):
                    ar.text(j, 1.80, decision, transform=ar.get_xaxis_transform(), ha='center',
                            va='top', fontsize=5.2, fontweight='bold', linespacing=1.05)
                    ar.text(j, 1.46, comparison, transform=ar.get_xaxis_transform(), ha='center',
                            va='top', fontsize=5.2, linespacing=1.05)
            fig.text(.66, bottom + .228, bench, fontsize=5.8, fontweight='bold')
        c = fig.colorbar(dm, cax=fig.add_axes([.66, .165, .33, .016]), orientation='horizontal')
        c.set_ticks([-20, -10, 0, 10, 20])
        c.outline.set_visible(False)
        c.ax.tick_params(length=2, pad=1, labelsize=5)
        c.set_label('Resolve-rate change (pp)', fontsize=5.5, labelpad=1)
        fig.text(.825, .015, '(b)', ha='center', fontsize=7)
    return fig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", nargs="+", choices=["all", *FIGURES], default=["all"])
    parser.add_argument("--list", action="store_true", help="List the selected figure names")
    parser.add_argument("--outcomes", type=Path, default=SWE_OUTCOMES,
                        help="SWE-bench outcomes table (main + ablation tracks)")
    parser.add_argument("--tb-outcomes", type=Path, default=TB_OUTCOMES,
                        help="Terminal-Bench outcomes table")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--q3-data-dir", type=Path, default=Q3_DATA_DIR,
                        help="audited Q3 exports; Devstral, GLM and Terminal-Bench rows are reused")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots",
                        help="Output root; preserves setup/, q1/ and q3/ subdirectories")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(FIGURES))
        return
    selected = list(FIGURES) if "all" in args.figure else list(dict.fromkeys(args.figure))
    for path in (args.outcomes, args.tb_outcomes):
        if not path.is_file():
            parser.error(f"missing {path}")

    cache = {}

    def qwen_primary():
        """Primary-setting attempts and q1_frontier statistics, Qwen SWE-bench on P100."""
        if "qwen" not in cache:
            df = primary_setting("swebench", "qwen35b", args.outcomes)
            cache["qwen"] = (df, q1_frontier(df))
        return cache["qwen"]

    def write(frame, sub, name, **kw):
        path = sub / name
        if path.resolve() != (args.q3_data_dir / name).resolve():   # never overwrite the audited inputs
            frame.to_csv(path, **kw)

    for name in selected:
        sub = args.output_dir / FIGURES[name]
        sub.mkdir(parents=True, exist_ok=True)
        with plt.rc_context(PAPER_STYLE):
            if name == "intro_01_policy_axes_wrap":
                fig = fig_intro_policy_axes()
            elif name == "q1_24_qwen_overview":
                _, swe = qwen_primary()
                tb = q1_frontier(primary_setting("terminalbench", "qwen35b", args.tb_outcomes))
                write(swe, sub, "q1_frontier_qwen35b.csv")
                write(tb, sub, "q1_frontier_tb_qwen35b.csv")
                fig = fig_qwen_overview({"swebench": swe, "terminalbench": tb})
            elif name == "q1_26_knob_execution":
                summary, grid = knob_inputs(args.outcomes)
                if len(grid) != 46 or grid.duplicated(["policy", "threshold_k", "depth_removed"]).any():
                    raise ValueError("Knob grid must contain 45 distinct settings plus FC")
                write(summary, sub, "q1_knob_execution.csv", index=False)
                write(grid, sub, "q1_knob_execution_resolve_grid.csv", index=False)
                fig = fig_knob_execution(summary, grid)
            elif name == "q2_qwen_task_map_only":
                runs = load_q2_runs(args.outcomes, args.tasks)
                solved = runs.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].ge(2)
                solved[ORACLE] = solved[ROWS].any(axis=1)
                solved = solved.loc[:, TASK_MAP_ROWS]
                missed = sorted(solved.index[~solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                shared = sorted(solved.index[solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                counts = pd.DataFrame({"solved": solved.sum(),
                                       "gained": (~solved.FC.to_numpy()[:, None] & solved).sum(),
                                       "lost": (solved.FC.to_numpy()[:, None] & ~solved).sum()}).loc[TASK_MAP_ROWS]
                counts.index.name = "policy"
                write(counts, sub, "q2_task_map_counts.csv")
                print(f"task map: FC solved {int(solved.FC.sum())}/{len(solved)}; "
                      f"oracle solves {int(solved[ORACLE].sum())}", flush=True)
                fig = fig_task_map(solved, missed, shared)
            else:
                df, swe = qwen_primary()
                values, contrasts = q3_inputs(swe, df, args.q3_data_dir)
                if values.duplicated(["benchmark", "model_key", "policy", "metric"]).any():
                    raise ValueError("Duplicate Q3 policy values")
                if contrasts.duplicated(["benchmark", "model_key", "p", "q"]).any():
                    raise ValueError("Duplicate Q3 design contrasts")
                write(values, sub, "q3_combined_policy_values.csv", index=False)
                write(contrasts, sub, "q3_combined_design_contrasts.csv", index=False)
                fig = fig_policy_preferences(values, contrasts)
            try:
                save_figure(fig, sub, name, dpi=300 if name.startswith(("intro", "q3")) else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {sub / name}.{{pdf,png}}", flush=True)


if __name__ == "__main__":
    main()
