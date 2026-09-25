"""Paper Figures 2-5 from the re-evaluated verdicts.

Re-renders the four data figures of the selected plot bank
(Iclr_plot_bank.py: q1_24_qwen_overview, q1_26_knob_execution,
q2_qwen_task_map_only, q3_policy_preferences_and_design) with every input
recomputed from an outcomes table, by default the one carrying the
2026-09-23 Qwen main-track re-evaluation
(ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv, written by
analysis/apply_reeval_outcomes.py). Figure 1 (the introduction's policy-axes
sketch, intro_01_policy_axes) draws no data and is unaffected.

The plot bank itself reads existing analysis exports (q1_frontier_*.csv,
q1_knob_execution*.csv, plots/q3/q3_combined_*.csv) that were computed from
the raw records, whose `resolved` flags predate the re-evaluation. This
script recomputes those exports with the same definitions, taking `resolved`
from the outcomes table, and passes them to the unchanged drawing
functions:

  * Figure 2 (overview): q1_frontier.py statistics (paired task bootstrap vs
    FC, seed 0, B=5000, policies in q1_frontier order so the intervals
    reproduce the export bit for bit) plus the absolute resolve-rate
    intervals of paper_figures.load_qwen_overview (seed 210926, 10,000
    resamples). Per-run quantities come from appendix_knob_overview.load_runs
    (the token_cost_ledger port). SWE-bench on P100, Terminal-Bench on TB-40
    from --tb-outcomes (unchanged by the re-evaluation). Drawn by a revised
    copy of fig_qwen_overview: no "Qwen" heading, larger fonts and
    markers, black arrows marking the better direction of each axis, both
    axes include 0, no y=x guide in the third column, one benchmark heading
    per row instead of panel titles, and FC drawn as a black square instead
    of a star. In every figure this script draws, the OTRC family gets
    purple hues instead of greys (OTRC+TR blue-leaning purple, filled;
    OTRC+SU-p red-leaning purple and OTRC+SS-p light blue-leaning purple,
    hollow) so the members are not confused with each other or with
    hollow-black OTRC.
  * Figure 3 (tuning): q1_knob_execution.py cell statistics and the 45-cell
    resolve grid on ABL-25 (compression detector at 15% drop, seed 0, B=2000,
    completed-run cost/latency on the left, all-attempt table on the right).
    Drawn by Ritul's 2026-09-24 local revision of fig_knob_execution (larger
    fonts, yellow/green winner cells, oval lowest latency), carried here until
    it is committed, with the sweep x-axis labels shortened to "D" and
    "Threshold", compressions starting at 0, and billed input and latency
    shown as ratios to FC on a range around 1.
  * Figure 4 (task map): Iclr_plot_bank's own loader on the outcomes table,
    plus an 'Oracle' row directly above FC: a task counts as solved when
    any of the thirteen policies (twelve compression policies or FC)
    solves it (per-policy majority of three runs), i.e. the resolve
    reachable if the best policy were known per task. Gained is relative
    to FC like every other row; Lost is 0 by construction. The renderer is a copy of fig_task_map that takes
    the row list as a parameter.
  * Figure 5 (policy preferences): the Qwen SWE-bench policy values
    (resolve, latency and billed-input ratios = the Figure 2 statistics,
    ranks by average method) and the four Qwen SWE-bench design contrasts
    (paired task resolve-rate differences, one fresh stream per pair, seed
    0, B=2000) are recomputed; every other row (Devstral, GLM,
    Terminal-Bench) is copied unchanged from the audited exports in
    --q3-data-dir, which the re-evaluation does not touch. Drawn by the
    plot bank's fig_policy_preferences: panel (a) uses the Figure 3(c)
    table encoding (grey boxed triplets, yellow highest resolve, green lowest
    cost, oval lowest latency, bold winners) with black policy labels and no
    rank shading or rank colour bar, and the panel titles are "(a)" and
    "(b)" centred under each panel.

With --outcomes analysis/outcomes/swebench_outcomes.csv the recomputed
exports reproduce Ritul's q1_frontier_*.csv, q1_knob_execution*.csv and
q3_combined_*.csv to floating-point precision (validated 2026-09-24).

Outputs (default ICLR_analysis/plots/reeval/): the four figures as PNG
under the plot-bank filenames, plus every recomputed input:
q1_frontier_qwen35b.csv, q1_frontier_tb_qwen35b.csv,
q1_24_qwen_overview_values.csv, q1_knob_execution.csv,
q1_knob_execution_resolve_grid.csv, q2_task_map_counts.csv,
q3_combined_policy_values.csv, q3_combined_design_contrasts.csv.

Usage (from the repository root):
    venv/bin/python ICLR_analysis/paper_figures_reeval.py
    venv/bin/python ICLR_analysis/paper_figures_reeval.py --figure overview tuning
    venv/bin/python ICLR_analysis/paper_figures_reeval.py --outcomes analysis/outcomes/swebench_outcomes.csv \
        --output-dir /tmp/canonical      # reproduces the canonical exports
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
    from . import plot_style, Iclr_plot_bank as plot_bank
    from .plot_style import PAPER_STYLE, ORDER, PSTYLE, PDARK, PLIGHT
    from .Iclr_plot_bank import fig_policy_preferences, ROWS, DT, MARK
    from .paper_figures import load_q2_runs
    from .appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                         raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                         SWE_TIMEOUT, MODEL_NAMES)
except ImportError:
    import plot_style
    import Iclr_plot_bank as plot_bank
    from plot_style import PAPER_STYLE, ORDER, PSTYLE, PDARK, PLIGHT
    from Iclr_plot_bank import fig_policy_preferences, ROWS, DT, MARK
    from paper_figures import load_q2_runs
    from appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                        raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                        SWE_TIMEOUT, MODEL_NAMES)

ROOT = Path(__file__).resolve().parent.parent
# The re-evaluated table: the local copy written by analysis/apply_reeval_outcomes.py
# when present, otherwise the canonical table, which carries the same
# re-evaluation since commit 397c232 (2026-09-24) and is tracked in git.
_REEVAL_COPY = ROOT / "ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv"
CANONICAL_OUTCOMES = ROOT / "analysis/outcomes/swebench_outcomes.csv"
REEVAL_OUTCOMES = _REEVAL_COPY if _REEVAL_COPY.is_file() else CANONICAL_OUTCOMES
TB_OUTCOMES = ROOT / "analysis/outcomes/terminalbench_outcomes_0924.csv"
Q3_DATA_DIR = ROOT / "ICLR_analysis/plots/q3"
OUTPUT_DIR = ROOT / "ICLR_analysis/plots/reeval"
FIGURES = {"overview": "q1_24_qwen_overview", "tuning": "q1_26_knob_execution",
           "task_map": "q2_qwen_task_map_only", "preferences": "q3_policy_preferences_and_design"}
# Figure 4 rows: the plot-bank rows plus an oracle row directly above FC. The
# oracle counts a task as solved when any of the thirteen policies (the twelve
# compression policies or FC) solves it (per-policy majority of 3 runs, as in
# every other row), i.e. the resolve reachable if the right policy were known
# for each task. Its Lost column is therefore always 0.
ORACLE = "Oracle"
TASK_MAP_ROWS = ORDER + [ORACLE, "FC"]
ORACLE_COLOR = "#1b9e77"

# The plot bank draws the OTRC family in greys next to hollow-black OTRC,
# which is hard to tell apart. Here each member gets its own clearly distinct
# hue (hollow markers keep their meaning) in every figure this script draws;
# the plot-bank renderers pick it up through their module-level pcol name.
# Blue-leaning purple for the TR-based member, red-leaning purple for the
# partial-rewrite members (light for SS-p); OTRC stays hollow black.
STEP_COLORS = {"OTRC+TR": "#8a4fd3", "OTRC+SU-p": "#c41cad", "OTRC+SS-p": "#7f6bd0"}


def pcol(p):
    return STEP_COLORS.get(p) or plot_style.pcol(p)


def hollow(p):
    """Hollow marker for partial rewrites and OTRC, as in the plot bank."""
    return p != "FC" and PSTYLE[p][2]


def pmark(ax, x, y, p, marker, s=22, force_hollow=False):
    """plot_style.pmark with the recoloured OTRC family."""
    c = pcol(p)
    if hollow(p) or force_hollow:
        ax.scatter(x, y, marker=marker, s=s, facecolors="white", edgecolors=c,
                   linewidths=1.0, zorder=3)
    else:
        ax.scatter(x, y, marker=marker, s=s, color=c, edgecolors="#444444",
                   linewidths=0.3, zorder=3)


plot_bank.pcol = pcol
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


# ------------------------------------------------------------ Figure 3 renderer
# Reviewer note: larger type and markers everywhere.
KNOB_STYLE = {**PAPER_STYLE, "font.size": 13, "axes.titlesize": 14,
              "axes.labelsize": 12.5, "xtick.labelsize": 12,
              "ytick.labelsize": 12, "legend.fontsize": 12}
RESOLVE_HIGHLIGHT = "#ffe680"  # highest resolve in a primitive/trigger triplet
COST_HIGHLIGHT = "#d9edcf"     # lowest billed cost in the triplet


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


# ------------------------------------------------------------ Figure 2 renderer
# Reviewer revisions of Iclr_plot_bank.fig_qwen_overview (wide 2x5 layout):
# no "Qwen" heading, larger fonts and markers, black arrows marking the
# better direction of each axis, both axes start at 0, no y=x guide in the
# third column, one benchmark heading per row (no panel titles), FC is a black
# square instead of a star.
FC_MARKER = "s"


def overview_handles():
    handles = [Line2D([], [], marker=FC_MARKER, ls="", color="black", ms=8, label="FC")]
    for policy in ORDER:
        c, open_ = pcol(policy), hollow(policy)
        handles.append(Line2D([], [], marker="o", ls="", ms=8,
                              mfc="white" if open_ else c, mec=c, mew=1.0 if open_ else 0.3,
                              label=policy))
    return handles


def better_arrows(ax, x_better, y_better):
    """Two black arrows in the corner the panel favours, in axes fractions."""
    x0 = 0.05 if x_better == "left" else 0.95
    y0 = 0.05 if y_better == "down" else 0.95
    span = 0.22
    xs = x0 + span if x_better == "left" else x0 - span
    ys = y0 + span if y_better == "down" else y0 - span
    style = dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color="black",
                 lw=1.3, shrinkA=0, shrinkB=0)
    ax.annotate("", xy=(x0, y0), xytext=(xs, y0), xycoords="axes fraction",
                textcoords="axes fraction", arrowprops=style, zorder=6)
    ax.annotate("", xy=(x0, y0), xytext=(x0, ys), xycoords="axes fraction",
                textcoords="axes fraction", arrowprops=style, zorder=6)


OVERVIEW_PANELS = [  # (x metric, y metric, x label, y label, better x, better y)
    ("usage", "dres", "token usage / FC", "success vs FC (pp)", "left", "up"),
    ("usage", "time", "token usage / FC", "wall-clock / FC", "left", "down"),
    ("usage", "bill", "token usage / FC", "billed input cost / FC", "left", "down"),
    ("resolve", "bill", "resolve rate (%)", "billed input cost / FC", "right", "down"),
    ("resolve", "time", "resolve rate (%)", "wall-clock / FC", "right", "down"),
]


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
            if ymetric == "bill":
                ax.axhspan(1, ylim[1], color="#f1f1f1", zorder=-1)
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
            better_arrows(ax, xbest, ybest)
            if position == 0:
                # One row heading, floated above and left of the first panel.
                ax.text(-0.36, 1.06, label, transform=ax.transAxes, fontsize=13,
                        ha="left", va="bottom")
            if row == last:
                ax.set_xlabel(xlabel, labelpad=4, fontsize=11)
            ax.set_ylabel(ylabel, labelpad=4, fontsize=11)
            ax.tick_params(axis="both", labelsize=10)
            ax.grid(alpha=0.2, lw=0.5)
            ax.locator_params(axis="both", nbins=4)


def overview_legend(fig, y=1.005):
    handles = overview_handles()
    # Two legend rows: 13 entries at this font size overflow an 11-inch line.
    # Matplotlib fills legend columns first; interleave so the key reads by row.
    top, bottom = handles[:7], handles[7:]
    handles = [h for pair in zip(top, bottom + [None]) for h in pair if h is not None]
    fig.legend(handles=handles, loc="upper center", ncol=7, frameon=False,
               handletextpad=0.3, columnspacing=1.2, fontsize=10, bbox_to_anchor=(0.52, y))


def overview_figure(n_rows):
    """Figure and (n_rows, 5) axes with the Figure 2 proportions: 11 in wide,
    1.75 in per row plus the legend band; 2 rows = 11.0 x 4.7 in (2200 x 940
    px at 200 dpi)."""
    height = 1.2 + 1.75 * n_rows
    fig, axes = plt.subplots(n_rows, 5, figsize=(11.0, height), squeeze=False)
    fig.subplots_adjust(left=0.062, right=0.992, bottom=0.54 / height, top=1 - 0.66 / height,
                        wspace=0.42, hspace=0.44)
    return fig, axes


def fig_qwen_overview(frames):
    fig, axes = overview_figure(2)
    draw_overview_rows(axes, [("SWE-bench", frames["swebench"]),
                              ("Terminal-Bench", frames["terminalbench"])])
    overview_legend(fig)
    return fig


# ------------------------------------------------------------ Figure 4 renderer
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
    totals = fig.add_axes([.144, bottom, .044, height])
    cell_width = .236 / n_tasks  # maps widened to reclaim the tightened gaps
    missed_width, solved_width = len(missed) * cell_width, len(shared) * cell_width
    miss_ax = fig.add_axes([.208, bottom, missed_width, height], sharey=totals)
    # Gained sits right next to the FC-missed map, Lost right next to the
    # FC-solved map; the wider gap separates the two map halves.
    gain_left = .208 + missed_width + .004
    gain_ax = fig.add_axes([gain_left, bottom, .042, height], sharey=totals)
    shared_left = gain_left + .042 + .024
    shared_ax = fig.add_axes([shared_left, bottom, solved_width, height], sharey=totals)
    loss_ax = fig.add_axes([shared_left + solved_width + .004, bottom, .037, height], sharey=totals)
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
            totals.scatter(-.52, j, s=11, marker=FC_MARKER, color='black', clip_on=False,
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


# ------------------------------------------------------------ driver
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", nargs="+", choices=["all", *FIGURES], default=["all"])
    parser.add_argument("--outcomes", type=Path, default=REEVAL_OUTCOMES,
                        help="SWE-bench outcomes table (default: the re-evaluated copy)")
    parser.add_argument("--tb-outcomes", type=Path, default=TB_OUTCOMES)
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--q3-data-dir", type=Path, default=Q3_DATA_DIR,
                        help="audited Q3 exports; their Terminal-Bench rows are reused")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not args.outcomes.is_file():
        parser.error(f"missing {args.outcomes}")
    selected = list(FIGURES) if "all" in args.figure else list(dict.fromkeys(args.figure))
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    frames, settings = {}, {}
    if "overview" in selected or "preferences" in selected:
        settings["qwen35b"] = primary_setting("swebench", "qwen35b", args.outcomes)
        frames["qwen35b"] = q1_frontier(settings["qwen35b"])
        frames["qwen35b"].to_csv(out / "q1_frontier_qwen35b.csv")
    for name in selected:
        with plt.rc_context(PAPER_STYLE):
            if name == "overview":
                tb = q1_frontier(primary_setting("terminalbench", "qwen35b", args.tb_outcomes))
                tb.to_csv(out / "q1_frontier_tb_qwen35b.csv")
                overview = {"swebench": frames["qwen35b"], "terminalbench": tb}
                pd.concat(overview, names=["benchmark", "policy"]).to_csv(out / "q1_24_qwen_overview_values.csv")
                fig = fig_qwen_overview(overview)
            elif name == "tuning":
                S, grid = knob_inputs(args.outcomes)
                S.to_csv(out / "q1_knob_execution.csv", index=False)
                grid.to_csv(out / "q1_knob_execution_resolve_grid.csv", index=False)
                fig = fig_knob_execution(S, grid)
            elif name == "task_map":
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
                counts.to_csv(out / "q2_task_map_counts.csv")
                print(f"task map: FC solved {int(solved.FC.sum())}/{len(solved)}; "
                      f"oracle over {len(ROWS)} policies solves {int(solved[ORACLE].sum())}; "
                      f"{len(missed)} FC-missed + {len(shared)} FC-solved columns")
                fig = fig_task_map(solved, missed, shared)
            else:
                values, contrasts = q3_inputs(frames["qwen35b"], settings["qwen35b"], args.q3_data_dir)
                values.to_csv(out / "q3_combined_policy_values.csv", index=False)
                contrasts.to_csv(out / "q3_combined_design_contrasts.csv", index=False)
                fig = fig_policy_preferences(values, contrasts)
            try:
                fig.savefig(out / f"{FIGURES[name]}.png", dpi=300 if name == "preferences" else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {out / FIGURES[name]}.png", flush=True)


if __name__ == "__main__":
    main()
