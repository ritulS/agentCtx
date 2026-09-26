"""Appendix: the Figure 1 overview (q1_24_qwen_overview) at every depth and
trigger threshold.

Figure 1 fixes depth 0.5 and the primary trigger threshold. This script
re-renders the same 2x5 layout (SWE-bench row, Terminal-Bench row; success,
latency and billed cost against token usage, then billed cost and latency
against resolve rate) for each (depth, threshold) setting in the ablation
grid, and exports the plotted numbers next to the figures.

    depth in {0.3, 0.5, 0.7}, expressed as the fraction REMOVED at each
        compression event (paper convention; result cells encode the
        fraction retained, so cell d07 is depth 0.3 here).
    threshold in {tight, primary, loose}: the three per-model trigger budgets
        (Qwen SWE-bench 10K/15K/20K, Terminal-Bench 2K/3K/4K, and so on),
        taken from the token_budget column of the outcomes tables.

Cells. The primary setting (depth 0.5, primary threshold) comes from the
main track. Every other setting comes from the ablation track; the depth-
invariant policies (TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-p, OTRC+SS-p) have
no depth knob, so at depth 0.3 or 0.7 their points repeat the depth 0.5
cell of the same threshold. FC and OTRC are budget-free references from the
main track. All cells are restricted to the panel's cohort, so every panel is
paired against FC on its own tasks.

Cohorts. The ablation track covers ABL-25 (SWE-bench) and TB-15
(Terminal-Bench). By default all nine settings use that cohort so the nine
figures are comparable; `--primary-cohort full` instead draws the primary
setting on P100 / TB-40, which reproduces Figure 1 exactly (validated
against Ritul's q1_frontier exports when available).

Metrics follow ICLR_analysis/q1_frontier.py and token_cost_ledger.py
(Ritul's clone; the fresh/cached reconstruction is ported below):
  * success vs FC (pp): all attempts, missing verdicts and capped runs count
    as unresolved, per-task means, paired task bootstrap.
  * token usage, wall-clock and billed input cost: ratio of means to FC on
    completed runs of shared tasks, paired task bootstrap. Capped = e2e >=
    1500 s on SWE-bench, Harbor AgentTimeoutError (or CancelledError/empty
    exit status) on Terminal-Bench.
  * billed input cost = fresh input + 0.1 * cached input + summarizer
    prompts (ideal prefix cache, block 16; an OTRC-cleared step is fresh from
    the cleared message). Output tokens are excluded, as in Figure 1.
  * resolve-rate intervals: task bootstrap of per-task success means.

Inputs: analysis/outcomes/swebench_outcomes.csv and
analysis/outcomes/terminalbench_outcomes_0924.csv (schema of
analysis/aggregate_benchmark_results.py), plus the raw
experiment_results.json named in their source_file column for the online
TRC clear flags, and the pinned task lists in task_lists/.

Run from the repository root:
    venv/bin/python ICLR_analysis/appendix_knob_overview.py
    venv/bin/python ICLR_analysis/appendix_knob_overview.py --model devstral24b \
        --benchmarks swebench --grid-settings all      # per-model grid, nine settings
    venv/bin/python ICLR_analysis/appendix_knob_overview.py --settings 0.3:tight 0.7:loose
Outputs (PNG + CSV) go to ICLR_analysis/plots/appendix/ by default:
`<model>_{swe,tb}_depth_trigger_ablation_{tight,primary,loose}.png`, one
figure per threshold group and benchmark with that group's D settings as
rows (D = depth) and the five Figure 1 panels as columns. Optional extras,
off by default: `--grid` (page-wide grid, all settings as columns),
`--per-setting` (one Figure 1-style figure per setting) and `--stack`
(single-column stack of the eight non-primary settings).
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

try:
    from .plot_style import PAPER_STYLE, ORDER, MK, pmark, prim_handles
except ImportError:
    from plot_style import PAPER_STYLE, ORDER, MK, pmark, prim_handles

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAMES = {"qwen35b": "Qwen3.5-35B-A3B", "devstral24b": "Devstral-Small-2-24B",
               "glm47flash": "GLM-4.7-Flash"}
NAME = {"tr": "TR", "su-full": "SU", "su-partial": "SU-p", "ss": "SS", "ss-partial": "SS-p",
        "trc": "TRC", "trc-su": "TRC+SU", "trc-ss": "TRC+SS", "otrc-tr": "OTRC+TR",
        "otrc-su-partial": "OTRC+SU-p", "otrc-ss-partial": "OTRC+SS-p", "fc": "FC", "otrc": "OTRC"}
DEPTH_TUNABLE = ["TR", "SU", "SU-p", "SS", "SS-p"]
DEPTH_INVARIANT = ["TRC", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p"]
LEVELS = ["tight", "primary", "loose"]
DEPTHS = [0.3, 0.5, 0.7]
BENCHMARKS = [("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]
SWE_TIMEOUT = 1500.0          # scripts/run_experiment.py AGENT_TIMEOUT
LAG = 5                       # token_cost_ledger.LAG (online TRC clears lag)
BLOCK = 16                    # prefix-cache block size
COHORTS = {"swebench": {"full": "p100_all_100_tasks.json", "ablation": "ablation_25tasks.json"},
           "terminalbench": {"full": "tbench_p40.json", "ablation": "tbench_abl15.json"}}
COHORT_LABELS = {"p100_all_100_tasks.json": "P100", "ablation_25tasks.json": "ABL-25",
                 "tbench_p40.json": "TB-40", "tbench_abl15.json": "TB-15"}


# ---------------------------------------------------------------- loading
def read_tasks(benchmark, cohort):
    path = ROOT / "task_lists" / COHORTS[benchmark][cohort]
    data = json.loads(path.read_text())
    tasks = data["tasks"] if isinstance(data, dict) else [row["instance_id"] for row in data]
    if len(set(tasks)) != len(tasks):
        raise ValueError(f"{path}: duplicate tasks")
    return set(tasks), COHORT_LABELS[path.name]


def fresh_cached(P, flagged, Cbar, block=BLOCK):
    """Ported from token_cost_ledger.fresh_cached (Ritul). R_hi bounds the
    fresh-token count from above: a prompt that shrinks by >= max(1000, 25%)
    is a compression event and everything after the stable system prefix is
    fresh; an OTRC-flagged step is fresh from the cleared message; minor
    drops count as fresh only in R_hi; otherwise only appended tokens are fresh."""
    rb = lambda x: (x // block) * block
    S = rb(P[0])
    R_hi = 0.0
    for t in range(1, len(P)):
        d = P[t] - P[t - 1]
        if d <= -max(1000, 0.25 * P[t - 1]):
            R_hi += max(P[t] - S, 0)
        elif t in flagged:
            shared = rb(P[t - LAG] + Cbar) if t - LAG >= 0 else S
            R_hi += max(P[t] - shared, 0)
        elif d < 0:
            R_hi += max(P[t] - S, 0)
        else:
            R_hi += d
    return R_hi


def raw_fields(source_files):
    """Online TRC clear flags and summarizer prompt tokens from the raw records
    (the outcomes tables carry neither as structured fields for every benchmark)."""
    lookup = {}
    for source in source_files:
        path = ROOT / source
        if not path.is_file():
            raise ValueError(f"Missing raw records: {path}")
        for r in json.loads(path.read_text()):
            key = (source, r["instance_id"], int(r["run_num"]))
            lookup[key] = ({int(f["step"]) for f in (r.get("online_trc_flags") or [])},
                           float(r.get("summarization_prompt_tokens") or 0.0))
    return lookup


def load_runs(benchmark, model, outcomes_path):
    """One row per attempt (runs 1-3) with the Figure 1 per-run quantities."""
    required = ["benchmark", "experiment_section", "model_key", "cell", "source_file",
                "task_name", "run_num", "resolved", "exit_status", "token_budget",
                "step_prompt_tokens", "step_completion_tokens", "total_prompt_tokens",
                "total_completion_tokens", "latency_e2e_s"]
    d = pd.read_csv(outcomes_path, low_memory=False)
    missing = set(required) - set(d.columns)
    if missing:
        raise ValueError(f"{outcomes_path}: missing columns {sorted(missing)}")
    d = d[d.benchmark.eq(benchmark) & d.model_key.eq(model) &
          d.experiment_section.isin(["main", "ablation"]) & d.run_num.isin([1, 2, 3])].copy()
    if d.empty:
        raise ValueError(f"{outcomes_path}: no {benchmark}/{model} main or ablation rows")
    if d.duplicated(["experiment_section", "cell", "task_name", "run_num"]).any():
        raise ValueError("duplicate attempts per track/cell/task/run")
    parts = d.cell.str.split("__", expand=True)
    d["depth_cell"], d["budget_cell"], d["prim"] = parts[0], parts[1], parts[2]
    d["policy"] = d.prim.map(NAME)
    if d.policy.isna().any():
        raise ValueError(f"unknown primitives: {sorted(d.prim[d.policy.isna()].unique())}")
    verdict = d.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError("resolved must be True, False, or missing")
    d["res"] = verdict.eq("true").fillna(False).astype(float)   # missing verdict = unresolved
    # Missing latency (silent crashes) is validated per panel, once cells are chosen.
    d["e2e"] = pd.to_numeric(d.latency_e2e_s, errors="coerce")
    if benchmark == "swebench":
        d["capped"] = d.e2e.ge(SWE_TIMEOUT)
    else:
        if "harbor_exception" not in d.columns:
            raise ValueError("Terminal-Bench outcomes need harbor_exception")
        has_exc = d.harbor_exception.notna()
        fallback = d.exit_status.isna() | d.exit_status.eq("CancelledError")
        d["capped"] = np.where(has_exc, d.harbor_exception.eq("AgentTimeoutError"), fallback)
    raw = raw_fields(sorted(d.source_file.unique()))
    rows = []
    for r in d.itertuples(index=False):
        P = json.loads(r.step_prompt_tokens) if isinstance(r.step_prompt_tokens, str) else []
        if len(P) < 2:      # token_cost_ledger.per_run drops these attempts
            continue
        C = json.loads(r.step_completion_tokens) if isinstance(r.step_completion_tokens, str) else []
        totP, totC = float(r.total_prompt_tokens), float(r.total_completion_tokens)
        flagged, summP = raw[(r.source_file, r.task_name, int(r.run_num))]
        sumP = float(sum(P))
        if abs(totP - sumP - summP) > 1:
            raise ValueError(f"{r.cell} {r.task_name} run {r.run_num}: prompt accounting mismatch")
        Cbar = (float(sum(C)) if C else totC) / len(P)
        R_hi = fresh_cached(P, flagged, Cbar)
        rows.append(dict(track=r.experiment_section, cell=r.cell, policy=r.policy,
                         depth_cell=r.depth_cell, budget=int(r.token_budget),
                         task=r.task_name, run=int(r.run_num), res=r.res,
                         capped=bool(r.capped), e2e=float(r.e2e), usage=totP + totC,
                         bill=R_hi + 0.1 * (sumP - R_hi) + summP))
    runs = pd.DataFrame(rows)
    dropped = len(d) - len(runs)
    return runs, dropped


def budget_levels(runs):
    """tight / primary / loose = the three budgets of the depth-tunable cells."""
    budgets = sorted(runs.loc[runs.policy.isin(DEPTH_TUNABLE), "budget"].unique())
    if len(budgets) != 3:
        raise ValueError(f"expected three trigger budgets, found {budgets}")
    return dict(zip(LEVELS, budgets))


# ---------------------------------------------------------------- statistics
def panel_runs(runs, tasks, depth, level, budgets):
    """Assemble FC, OTRC and the 11 budgeted policies for one setting."""
    budget = budgets[level]
    keep = f"d{int(round(10 * (1 - depth))):02d}"
    primary = (depth == 0.5 and level == "primary")
    parts = [runs[runs.track.eq("main") & runs.cell.isin(["di__binf__fc", "di__binf__otrc"])]]
    for policy in DEPTH_TUNABLE:
        track = "main" if primary else "ablation"
        parts.append(runs[runs.track.eq(track) & runs.policy.eq(policy) &
                          runs.depth_cell.eq(keep) & runs.budget.eq(budget)])
    for policy in DEPTH_INVARIANT:
        track = "main" if level == "primary" else "ablation"
        parts.append(runs[runs.track.eq(track) & runs.policy.eq(policy) &
                          runs.depth_cell.eq("di") & runs.budget.eq(budget)])
    df = pd.concat(parts, ignore_index=True)
    df = df[df.task.isin(tasks)]
    counts = df.groupby("policy").size()
    missing = set(["FC"] + ORDER) - set(counts.index)
    if missing:
        raise ValueError(f"depth {depth} {level}: no attempts for {sorted(missing)}")
    if df.duplicated(["policy", "task", "run"]).any():
        raise ValueError(f"depth {depth} {level}: duplicate attempts (cell selection is ambiguous)")
    if df.e2e.isna().any():
        bad = df[df.e2e.isna()].groupby("cell").size().to_dict()
        raise ValueError(f"depth {depth} {level}: attempts without latency in {bad}")
    return df


def per_task(df, col, completed_only):
    d = df[~df.capped] if completed_only else df
    return d.groupby(["policy", "task"])[col].mean().unstack(0)


def ratio_ci(mat, policy, B, rng):
    m = mat[[policy, "FC"]].dropna()
    a, b = m[policy].to_numpy(), m["FC"].to_numpy()
    if not len(a):
        raise ValueError(f"{policy}: no completed runs on tasks shared with FC")
    idx = rng.integers(0, len(a), (B, len(a)))
    boots = a[idx].mean(1) / b[idx].mean(1)
    return a.mean() / b.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5), len(a)


def diff_ci(mat, policy, B, rng):
    m = mat[[policy, "FC"]].dropna()
    d = (m[policy] - m["FC"]).to_numpy() * 100
    idx = rng.integers(0, len(d), (B, len(d)))
    boots = d[idx].mean(1)
    return d.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5), len(d)


def frontier(df, B=5000, seed=0, resolve_resamples=10000, resolve_seed=210926):
    """q1_frontier statistics plus absolute resolve-rate intervals
    (the load_qwen_overview bootstrap: per-task success means, all attempts)."""
    rng = np.random.default_rng(seed)
    R = per_task(df, "res", False)
    U = per_task(df, "usage", True)
    C = per_task(df, "bill", True)
    L = per_task(df, "e2e", True)
    rows = []
    for policy in ["FC"] + ORDER:
        rr = diff_ci(R, policy, B, rng) if policy != "FC" else (0.0, 0.0, 0.0, R["FC"].notna().sum())
        u, c, l = (ratio_ci(M, policy, B, rng) for M in (U, C, L))
        values = R[policy].dropna().to_numpy()
        brng = np.random.default_rng(resolve_seed)
        idx = brng.integers(0, len(values), (resolve_resamples, len(values)))
        lo, hi = np.percentile(values[idx].mean(axis=1) * 100, [2.5, 97.5])
        g = df[df.policy.eq(policy)]
        rows.append(dict(policy=policy, resolve=values.mean() * 100, resolve_lo=lo, resolve_hi=hi,
                         dres=rr[0], dres_lo=rr[1], dres_hi=rr[2], n_tasks=rr[3],
                         usage=u[0], usage_lo=u[1], usage_hi=u[2],
                         bill=c[0], bill_lo=c[1], bill_hi=c[2],
                         time=l[0], time_lo=l[1], time_hi=l[2], n_shared=l[3],
                         n_attempts=len(g), n_completed=int((~g.capped).sum()),
                         cell=g.cell.iloc[0], track=g.track.iloc[0]))
    frame = pd.DataFrame(rows).set_index("policy")
    for metric in ("dres", "bill", "time", "usage", "resolve"):
        if not ((frame[metric + "_lo"] <= frame[metric] + 1e-12) &
                (frame[metric] <= frame[metric + "_hi"] + 1e-12)).all():
            raise ValueError(f"{metric}: interval does not enclose estimate")
    return frame


# ---------------------------------------------------------------- figure
PANEL_TITLES = ["success", "latency", "billed cost", "billed cost", "latency"]
PANELS = [
    ("usage", "dres", "token usage / FC", "success vs FC (pp)"),
    ("usage", "time", "token usage / FC", "wall-clock / FC"),
    ("usage", "bill", "token usage / FC", "billed input cost / FC"),
    ("resolve", "bill", "resolve rate (%)", "billed input cost / FC"),
    ("resolve", "time", "resolve rate (%)", "wall-clock / FC"),
]
STACK_ORDER = [(0.3, "tight"), (0.5, "tight"), (0.7, "tight"), (0.3, "primary"), (0.7, "primary"),
               (0.3, "loose"), (0.5, "loose"), (0.7, "loose")]


def panel_bounds(frame):
    """Axis limits of the Figure 1 panels for one benchmark frame."""
    fc = frame.loc["FC"]
    bounds = {}
    for metric, reference in [("dres", 0), ("time", 1), ("bill", 1), ("resolve", fc.resolve)]:
        low = min(frame[metric + "_lo"].min(), reference)
        high = max(frame[metric + "_hi"].max(), reference)
        margin = max((high - low) * 0.075, 0.04 if metric in ["time", "bill"] else 0.5)
        bounds[metric] = (low - margin, high + margin)
    bounds["usage"] = (max(0, frame.usage.min() - 0.055), 1.045)
    return bounds


def draw_panel(ax, frame, index, bounds=None, scale=1.0, diagonal=True):
    """One Figure 1 panel (Iclr_plot_bank.fig_qwen_overview, wide layout);
    `scale` enlarges markers and tick labels for bigger layouts, `diagonal`
    draws the equal-savings line on the usage/bill panel."""
    xmetric, ymetric, _, _ = PANELS[index]
    bounds = bounds or panel_bounds(frame)
    fc = frame.loc["FC"]
    xlim, ylim = bounds[xmetric], bounds[ymetric]
    if ymetric == "bill":
        ax.axhspan(1, ylim[1], color="#f1f1f1", zorder=-1)
    ax.axhline(fc[ymetric], color="#999999", lw=0.6, ls="--", zorder=0)
    ax.axvline(fc[xmetric], color="#999999", lw=0.6, ls="--", zorder=0)
    if diagonal and (xmetric, ymetric) == ("usage", "bill"):
        xx = np.array(xlim)
        ax.plot(xx, xx, color="#999999", lw=0.6, ls=":", zorder=0)
    for policy in ORDER:
        r = frame.loc[policy]
        ax.errorbar(r[xmetric], r[ymetric],
                    yerr=[[r[ymetric] - r[ymetric + "_lo"]], [r[ymetric + "_hi"] - r[ymetric]]],
                    fmt="none", ecolor="#c8c8c8", elinewidth=0.7 * scale, capsize=0, zorder=1)
        pmark(ax, r[xmetric], r[ymetric], policy, MK["qwen35b"], s=36 * scale ** 2)
    ax.scatter(fc[xmetric], fc[ymetric], marker="*", color="black", s=110 * scale ** 2, zorder=5)
    ax.set_xlim(xlim); ax.set_ylim(ylim)
    ax.tick_params(axis="both", labelsize=8.5 * scale)
    ax.grid(alpha=0.2, lw=0.5)
    ax.locator_params(axis="both", nbins=4)


def draw_panels(axes, frames, benchmarks=BENCHMARKS, name_benchmark=True):
    """A len(benchmarks) x 5 block of Figure 1 panels; the benchmark is named
    only on the leftmost panel of each row (or not at all)."""
    for row, (benchmark, label) in enumerate(benchmarks):
        frame = frames[benchmark]
        bounds = panel_bounds(frame)
        for col, (ax, (_, _, xlabel, ylabel)) in enumerate(zip(axes[row], PANELS)):
            draw_panel(ax, frame, col, bounds)
            title = PANEL_TITLES[col]
            ax.set_title(f"{label}\n{title}" if col == 0 and name_benchmark else title,
                         loc="left", pad=4, fontsize=9.5)
            if row == len(benchmarks) - 1:
                ax.set_xlabel(xlabel, labelpad=4, fontsize=9)
            ax.set_ylabel(ylabel, labelpad=4, fontsize=9)


def draw_grid(title, blocks, benchmark):
    """Wide page layout for one benchmark: settings as columns (grouped by
    threshold, D within), the five Figure 1 panels as rows. Axis labels are
    shared: y labels on the leftmost column, x labels under the last row of
    each x-axis group (token usage rows 1-3, resolve rate rows 4-5)."""
    groups = threshold_groups(blocks)
    widths, col_of = [], []
    for gi, (level, start, count) in enumerate(groups):
        if gi:
            widths.append(0.12)         # spacer between threshold groups
        for _ in range(count):
            col_of.append(len(widths)); widths.append(1)
    heights = [1, 1, 1, 0.05, 1, 1]     # spacer row between the two x-axis groups
    row_of = [0, 1, 2, 4, 5]
    panel_in = 1.45
    width = 0.75 + sum(widths) * panel_in + (len(widths) - 1) * 0.4 * panel_in
    height = 1.2 + sum(heights) * panel_in + (len(heights) - 1) * 0.42 * panel_in + 0.55
    fig = plt.figure(figsize=(width, height))
    grid = fig.add_gridspec(len(heights), len(widths), width_ratios=widths, height_ratios=heights,
                            left=0.75 / width, right=1 - 0.1 / width, bottom=0.55 / height,
                            top=1 - 1.2 / height, wspace=0.4, hspace=0.42)
    short = {"swebench": "SWE", "terminalbench": "TB"}
    top_axes = []
    for j, (depth, level, frames) in enumerate(blocks):
        frame = frames[benchmark]
        bounds = panel_bounds(frame)
        for i, (_, _, xlabel, ylabel) in enumerate(PANELS):
            ax = fig.add_subplot(grid[row_of[i], col_of[j]])
            draw_panel(ax, frame, i, bounds)
            if i == 0:
                ax.set_title(f"D={depth}", loc="center", pad=4, fontsize=10)
                top_axes.append(ax)
            if j == 0:
                ax.set_ylabel(ylabel, labelpad=4, fontsize=9)
            if i in (2, 4):
                ax.set_xlabel(xlabel, labelpad=3, fontsize=9)
    fig.canvas.draw()
    for level, start, count in groups:
        left = top_axes[start].get_position().x0
        right = top_axes[start + count - 1].get_position().x1
        top = top_axes[start].get_position().y1
        budget = int(blocks[start][2][benchmark].budget.iloc[0]) // 1000
        fig.text((left + right) / 2, top + 0.42 / height,
                 f"{level} threshold ({short[benchmark]} {budget}K)",
                 ha="center", va="bottom", fontsize=10.5, weight="bold")
    fig.text(0.1 / width, 1 - 0.08 / height, title, fontsize=12, weight="bold", va="top")
    fig.legend(handles=legend_handles(), loc="upper right", ncol=13, frameon=False,
               handletextpad=0.2, columnspacing=0.85, fontsize=7.5,
               bbox_to_anchor=(1 - 0.1 / width, 1 - 0.32 / height))
    return fig


def threshold_groups(blocks):
    """Consecutive blocks with the same threshold: [level, first index, count]."""
    groups = []
    for _, level, _ in blocks:
        if groups and groups[-1][0] == level:
            groups[-1][2] += 1
        else:
            groups.append([level, sum(g[2] for g in groups), 1])
    return groups


def draw_group_vertical(title, blocks, benchmark, scale=1.35):
    """One threshold group for one benchmark: its settings as rows (D on the
    left), the five Figure 1 panels as columns with no gap, larger panels and
    type than the page-wide grid. Panel titles on the first row, x labels on
    the last."""
    rows = len(blocks)
    panel_in = 1.55 * scale
    fs = dict(header=11.5 * scale, label=10.5 * scale, tick=9.5 * scale, legend=9 * scale)
    left_in, top_in, bottom_in, right_in = 1.02 * scale, 0.6 * scale, 0.55 * scale, 0.1 * scale
    wspace, hspace = 0.48, 0.3
    width = left_in + 5 * panel_in + 4 * wspace * panel_in + right_in
    height = top_in + rows * panel_in + (rows - 1) * hspace * panel_in + bottom_in
    fig = plt.figure(figsize=(width, height))
    grid = fig.add_gridspec(rows, 5, left=left_in / width, right=1 - right_in / width,
                            bottom=bottom_in / height, top=1 - top_in / height,
                            wspace=wspace, hspace=hspace)
    for j, (depth, level, frames) in enumerate(blocks):
        frame = frames[benchmark]
        bounds = panel_bounds(frame)
        bounds["usage"] = (0, bounds["usage"][1])          # x axes start at zero
        bounds["resolve"] = (0, bounds["resolve"][1])
        for i, (_, _, xlabel, ylabel) in enumerate(PANELS):
            ax = fig.add_subplot(grid[j, i])
            draw_panel(ax, frame, i, bounds, scale, diagonal=False)
            ax.tick_params(axis="both", labelsize=fs["tick"])
            ax.set_ylabel(ylabel, labelpad=4, fontsize=fs["label"])
            if j == 0:
                ax.set_title(PANEL_TITLES[i], loc="left", pad=5, fontsize=fs["header"])
            if j == rows - 1:
                ax.set_xlabel(xlabel, labelpad=4, fontsize=fs["label"])
            if i == 0:
                ax.annotate(f"D={depth}", xy=(0, 0.5), xycoords="axes fraction",
                            xytext=(-0.84 * scale * 72, 0), textcoords="offset points",
                            rotation=90, ha="center", va="center", fontsize=fs["header"], weight="bold")
    # No title: the file name carries model/benchmark/threshold. One legend row on top.
    fig.legend(handles=legend_handles(), loc="upper center", ncol=13, frameon=False,
               handletextpad=0.2, columnspacing=0.9, fontsize=fs["legend"],
               bbox_to_anchor=((left_in + (width - right_in)) / 2 / width, 1 - 0.04 * scale / height))
    return fig


def legend_handles():
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="*", ls="", color="black", ms=10, label="full context")] + prim_handles()
    for handle in handles[1:]:
        handle.set_markersize(6)
    return handles


PANEL_COLUMNS = [0, 1, 2, 4, 5]          # column 3 is a spacer between the two x-axis groups
PANEL_WIDTHS = [1, 1, 1, 0.35, 1, 1]


def panel_axes(fig, grid, rows):
    """rows x 5 axes from a rows x 6 grid whose fourth column is a spacer."""
    return np.array([[fig.add_subplot(grid[r, c]) for c in PANEL_COLUMNS] for r in range(rows)])


def draw(frames, heading):
    """One setting: the Figure 1 layout (one row per benchmark present) with a
    heading line above the legend."""
    benchmarks = [(b, l) for b, l in BENCHMARKS if b in frames]
    rows = len(benchmarks)
    fig = plt.figure(figsize=(11.0, 4.7 if rows == 2 else 2.95))
    grid = fig.add_gridspec(rows, 6, width_ratios=PANEL_WIDTHS, left=0.064, right=0.987,
                            bottom=0.12 if rows == 2 else 0.19, top=0.815 if rows == 2 else 0.72,
                            wspace=0.62, hspace=0.5)
    axes = panel_axes(fig, grid, rows)
    draw_panels(axes, frames, benchmarks)
    fig.text(0.014, 0.99, heading, fontsize=10.5, weight="bold", va="top")
    fig.legend(handles=legend_handles(), loc="upper right", ncol=13, frameon=False,
               handletextpad=0.2, columnspacing=0.85, fontsize=7.5, bbox_to_anchor=(0.99, 0.95))
    return fig


def setting_heading(depth, level, frames, benchmarks=BENCHMARKS):
    """'tight threshold (SWE 10K, TB 2K) · D=0.3', naming only the budgets of
    the benchmarks shown (D = depth, fraction removed)."""
    short = {"swebench": "SWE", "terminalbench": "TB"}
    benchmarks = [(b, l) for b, l in benchmarks if b in frames]
    budgets = ", ".join(f"{short[b]} {int(frames[b].budget.iloc[0]) // 1000}K" for b, _ in benchmarks)
    return f"{level} threshold ({budgets}) · D={depth}"


def draw_stack(title, blocks, benchmarks=BENCHMARKS):
    """All settings stacked vertically: title and legend once at the top, one
    heading per setting, a larger gap between settings than between the
    SWE-bench and Terminal-Bench rows. `blocks` is a list of (depth, level, frames).
    With a single benchmark each block is one row and the benchmark is named
    only in the title."""
    from matplotlib.gridspec import GridSpecFromSubplotSpec
    n, rows = len(blocks), len(benchmarks)
    top_in, block_in, gap_in, bottom_in = 1.1, 1.5 * rows + 0.5, 1.1, 0.4
    height = top_in + n * block_in + (n - 1) * gap_in + bottom_in
    fig = plt.figure(figsize=(11.0, height))
    outer = fig.add_gridspec(n, 1, left=0.064, right=0.987, top=1 - top_in / height,
                             bottom=bottom_in / height, hspace=gap_in / block_in)
    for i, (depth, level, frames) in enumerate(blocks):
        heading = setting_heading(depth, level, frames, benchmarks)
        inner = GridSpecFromSubplotSpec(rows, 6, subplot_spec=outer[i], width_ratios=PANEL_WIDTHS,
                                        wspace=0.62, hspace=0.5)
        axes = panel_axes(fig, inner, rows)
        draw_panels(axes, frames, benchmarks, name_benchmark=rows > 1)
        y1 = outer[i].get_position(fig).y1
        fig.text(0.014, y1 + (0.4 if rows > 1 else 0.3) / height, heading,
                 fontsize=10.5, weight="bold", va="bottom")
    fig.text(0.014, 1 - 0.08 / height, title, fontsize=12, weight="bold", va="top")
    fig.legend(handles=legend_handles(), loc="upper right", ncol=13, frameon=False,
               handletextpad=0.2, columnspacing=0.85, fontsize=7.5,
               bbox_to_anchor=(0.99, 1 - 0.3 / height))
    return fig


def parse_settings(values):
    out = []
    for v in values:
        depth, level = v.split(":")
        depth = float(depth)
        if depth not in DEPTHS or level not in LEVELS:
            raise ValueError(f"bad setting {v!r}; use depth:level with depth in {DEPTHS} and level in {LEVELS}")
        out.append((depth, level))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tb-outcomes", type=Path,
                        default=ROOT / "analysis/outcomes/terminalbench_outcomes_0924.csv")
    parser.add_argument("--settings", nargs="+", default=[f"{d}:{l}" for d in DEPTHS for l in LEVELS],
                        help="depth:level pairs, depth = fraction removed")
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' reproduces Figure 1")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots/appendix")
    parser.add_argument("--B", type=int, default=5000, help="paired bootstrap resamples")
    parser.add_argument("--prefix", default="q1_appendix_overview")
    parser.add_argument("--per-setting", action="store_true",
                        help="also write one Figure 1-style figure per setting (q1_appendix_overview_*)")
    parser.add_argument("--stack", action="store_true",
                        help="also write the single-column stack of the eight non-primary settings")
    parser.add_argument("--grid", action="store_true",
                        help="also write the page-wide grid with all settings as columns")
    parser.add_argument("--name-tag", default="depth_trigger_ablation",
                        help="tag inserted into figure names (<model>_<bench>_<tag>_<threshold>.png); "
                             "empty for <model>_<bench>_<threshold>.png")
    parser.add_argument("--benchmarks", nargs="+", choices=[b for b, _ in BENCHMARKS],
                        default=[b for b, _ in BENCHMARKS], help="benchmarks to load and draw")
    parser.add_argument("--grid-settings", choices=["no-primary", "all"], default="no-primary",
                        help="grid columns/rows: the eight non-primary settings (Figure 1 covers "
                             "0.5/primary) or all nine, primary inserted between 0.3 and 0.7")
    args = parser.parse_args(argv)
    settings = parse_settings(args.settings)

    benchmarks = [(b, l) for b, l in BENCHMARKS if b in args.benchmarks]
    paths = {"swebench": args.outcomes, "terminalbench": args.tb_outcomes}
    grid_order = list(STACK_ORDER)
    if args.grid_settings == "all":
        grid_order.insert(grid_order.index((0.7, "primary")), (0.5, "primary"))
    runs, budgets = {}, {}
    for benchmark, _ in benchmarks:
        path = paths[benchmark]
        runs[benchmark], dropped = load_runs(benchmark, args.model, path)
        budgets[benchmark] = budget_levels(runs[benchmark])
        print(f"{benchmark}: {len(runs[benchmark])} attempts, {dropped} dropped (<2 model calls); "
              f"budgets {budgets[benchmark]}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    exports, blocks = [], {}
    for depth, level in settings:
        primary = (depth == 0.5 and level == "primary")
        cohort = args.primary_cohort if primary else "ablation"
        frames, labels = {}, {}
        for benchmark, _ in benchmarks:
            tasks, labels[benchmark] = read_tasks(benchmark, cohort)
            df = panel_runs(runs[benchmark], tasks, depth, level, budgets[benchmark])
            frame = frontier(df, B=args.B)
            frame.insert(0, "benchmark", benchmark)
            frame.insert(1, "depth_removed", depth)
            frame.insert(2, "threshold", level)
            frame.insert(3, "budget", budgets[benchmark][level])
            frame.insert(4, "cohort", labels[benchmark])
            frames[benchmark] = frame
            exports.append(frame.reset_index())
        setting = setting_heading(depth, level, frames)
        blocks[(depth, level)] = (depth, level, frames)
        fc = " / ".join(f"{l} {frames[b].loc['FC', 'resolve']:.1f}%" for b, l in benchmarks)
        print(f"{setting}: FC resolve {fc}")
        if args.per_setting:
            name = f"{args.prefix}_{args.model}_depth{depth}_{level}" + ("_fullcohort" if cohort == "full" else "")
            with plt.rc_context(PAPER_STYLE):
                fig = draw(frames, f"{MODEL_NAMES[args.model]} · {setting}")
                try:
                    fig.savefig(args.output_dir / f"{name}.png", dpi=200)
                finally:
                    plt.close(fig)
            print(f"Wrote {args.output_dir / name}.png")
    if all(key in blocks for key in grid_order):
        ordered = [blocks[key] for key in grid_order]
        if args.stack and len(benchmarks) == 2 and args.grid_settings == "no-primary":
            name = f"{args.prefix}_{args.model}_stack"
            with plt.rc_context(PAPER_STYLE):
                fig = draw_stack(MODEL_NAMES[args.model], ordered)
                try:
                    fig.savefig(args.output_dir / f"{name}.png", dpi=200)
                finally:
                    plt.close(fig)
            print(f"Wrote {args.output_dir / name}.png")
        for benchmark, label in benchmarks:
            stem = f"{args.model}_{'swe' if benchmark == 'swebench' else 'tb'}"
            if args.name_tag:
                stem += f"_{args.name_tag}"
            figures = []
            if args.grid:
                figures.append((stem, lambda: draw_grid(f"{MODEL_NAMES[args.model]} · {label}", ordered, benchmark)))
            for level, start, count in threshold_groups(ordered):
                group = ordered[start:start + count]
                budget = budgets[benchmark][level] // 1000
                heading = f"{MODEL_NAMES[args.model]} · {label} · {level} threshold ({budget}K)"
                figures.append((f"{stem}_{level}", lambda h=heading, g=group: draw_group_vertical(h, g, benchmark)))
            for name, make in figures:
                with plt.rc_context(PAPER_STYLE):
                    fig = make()
                    try:
                        fig.savefig(args.output_dir / f"{name}.png", dpi=200)
                    finally:
                        plt.close(fig)
                print(f"Wrote {args.output_dir / name}.png")
    table = pd.concat(exports, ignore_index=True)
    out = args.output_dir / f"{args.prefix}_{args.model}_values.csv"
    if len(benchmarks) < 2:
        out = out.with_name(out.stem + "_" + "_".join(b for b, _ in benchmarks) + ".csv")
    table.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
