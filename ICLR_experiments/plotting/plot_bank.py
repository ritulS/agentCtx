"""ICLR plot bank: every figure renderer of the paper in one file.

Run `python3 ICLR_experiments/plotting/plot_bank.py` from the repository root to
generate the nine maintained figures (Figures 2-5 and the appendix
companions). Every data figure is computed from the tracked outcomes tables
(analysis/outcomes/, which carry the 2026-09-24 Qwen verdict re-evaluation)
and the audited Q3 exports in ICLR_experiments/plotting/; the computed inputs are written
as CSVs next to each figure. Use --list or --help for selection and
input/output options. Data definitions and usage are documented in the
docstrings of each section below (the *_DOC constants, shown by `<tool>
--help`). No files are written on import.

The former companion scripts live here as sub-tools, selected by a first
positional word (each keeps its own options; `<tool> --help` lists them):

    python3 ICLR_experiments/plotting/plot_bank.py [--figure ...]        # the nine figures (default)
    python3 ICLR_experiments/plotting/plot_bank.py intro-fig             # intro_fig.py
    python3 ICLR_experiments/plotting/plot_bank.py paper-figures ...     # paper_figures.py
    python3 ICLR_experiments/plotting/plot_bank.py knob-overview ...     # appendix_knob_overview.py
    python3 ICLR_experiments/plotting/plot_bank.py task-map ...          # appendix_task_map.py
    python3 ICLR_experiments/plotting/plot_bank.py task-map-reeval ...   # appendix_task_map_reeval.py
    python3 ICLR_experiments/plotting/plot_bank.py depth-trigger-reeval  # appendix_depth_trigger_ablation_reeval.py
    python3 ICLR_experiments/plotting/plot_bank.py budget-vs-total ...   # budget_vs_total_explainer.py

File layout (one section per former module, in dependency order):
  1. shared style (plot_style.py)
  2. Figure 1 schematic (intro_fig.py)
  3. outcomes loading, statistics and the per-setting overview figures
     (appendix_knob_overview.py)
  4. termination rates, agent-call comparison, summarizer ablation
     (limit_rates.py, step_comparison.py, summarizer_ablation.py)
  5. the original paper figures and the Q2 loader (paper_figures.py)
  6. the plot bank proper: inputs, Figures 2-5, appendix explainer
  7. appendix task maps and the re-evaluation companions
     (appendix_task_map.py, appendix_task_map_reeval.py,
     appendix_depth_trigger_ablation_reeval.py, budget_vs_total_explainer.py)
  8. the command-line dispatcher
Names that collided across modules were renamed: LIMIT_MODELS and
SUMMARIZER_MODELS / SUMMARIZER_CELLS (formerly MODELS / CELLS in
limit_rates.py and summarizer_ablation.py), fig_appendix_task_map (formerly
appendix_task_map.fig_task_map), draw_setting (formerly
appendix_knob_overview.draw), read_required_csv (formerly
paper_figures.read_csv), INTRO_OUT (formerly intro_fig.OUT), and the
per-tool *_main functions.
"""
from pathlib import Path
import argparse
import ast
import json
import sys

import numpy as np
import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba, LinearSegmentedColormap, Normalize
from matplotlib.ticker import FuncFormatter, MultipleLocator
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle, Ellipse, FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# Shared figure style (formerly plot_style.py)
# ============================================================================
# Shared ICLR figure style. Encoding conventions: hue = policy family (blue
# rule, orange LLM, green stacked, purple/grey step-triggered), shade =
# primitive, hollow marker = partial rewrite, OTRC hollow black, FC black;
# model marker: Qwen circle, Devstral triangle, GLM diamond.
# Nothing here mutates matplotlib rcParams on import.
PAPER_STYLE = {
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8,
    "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.6, "pdf.fonttype": 42,
    "savefig.facecolor": "white",
}
Q2_STYLE = {**PAPER_STYLE, "font.size": 6}
MODELS = [("qwen35b", "Qwen", "o"), ("devstral24b", "Devstral", "^"), ("glm47flash", "GLM", "D")]
MK = {m: k for m, _, k in MODELS}
ORDER = ["TR", "TRC", "SU", "SU-p", "SS", "SS-p", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p", "OTRC"]
# Hue = policy family; shade = primitive; hollow = partial rewrite.
PDARK = {"rule": "#2171b5", "llm": "#d94801", "stack": "#238b45", "step": "#525252"}
PLIGHT = {"rule": "#6baed6", "llm": "#fd8d3c", "stack": "#74c476", "step": "#969696"}
PSTYLE = {"TR": ("rule", "d", False), "TRC": ("rule", "l", False),
          "SU": ("llm", "d", False), "SU-p": ("llm", "d", True), "SS": ("llm", "l", False), "SS-p": ("llm", "l", True),
          "TRC+SU": ("stack", "d", False), "TRC+SS": ("stack", "l", False),
          "OTRC+TR": ("step", "d", False), "OTRC+SU-p": ("step", "d", True), "OTRC+SS-p": ("step", "l", True),
          "OTRC": ("otrc", "d", True)}
# Per-policy overrides of the family palette: the OTRC-stacked family gets
# distinct purples (blue-leaning for OTRC+TR, red-leaning for OTRC+SU-p, light
# for OTRC+SS-p) instead of greys, so its members are not confused with each
# other or with hollow-black OTRC (2026-09-24 reviewer round).
POLICY_COLORS = {"OTRC+TR": "#8a4fd3", "OTRC+SU-p": "#c41cad", "OTRC+SS-p": "#7f6bd0"}


def pcol(p):
    """Policy color shared by all figures (FC is black)."""
    if p == "FC":
        return "#000000"
    if p in POLICY_COLORS:
        return POLICY_COLORS[p]
    g, shade, _ = PSTYLE[p]
    if g == "otrc":
        return "#000000"
    return PDARK[g] if shade == "d" else PLIGHT[g]


def pmark(ax, x, y, p, marker, s=22, force_hollow=False):
    """Draw a policy marker; marker shape encodes the model."""
    c = pcol(p)
    hollow = PSTYLE[p][2] or force_hollow
    if hollow:
        ax.scatter(x, y, marker=marker, s=s, facecolors="white", edgecolors=c,
                   linewidths=1.0, zorder=3)
    else:
        ax.scatter(x, y, marker=marker, s=s, color=c, edgecolors="#444444",
                   linewidths=0.3, zorder=3)


def prim_handles():
    h = []
    for p in ORDER:
        c = pcol(p); hollow = PSTYLE[p][2]
        h.append(Line2D([], [], marker="o", ls="", ms=4.5, mfc="white" if hollow else c, mec=c, mew=1.0 if hollow else 0.3, label=p))
    return h

def model_handles():
    return [Line2D([], [], marker=k, ls="", color="#555555", ms=5, label=n) for _, n, k in MODELS]


def save_figure(fig, output_dir, name, dpi=200):
    """Write a fixed-size PNG; preserve the selected layout margins."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{name}.png", dpi=dpi)


KNOB_STYLE = {**PAPER_STYLE, "font.size": 14, "axes.titlesize": 15,
              "axes.labelsize": 12.5, "xtick.labelsize": 13,
              "ytick.labelsize": 13, "legend.fontsize": 13}
RESOLVE_HIGHLIGHT = "#ffe680"  # highest resolve in a primitive/trigger triplet
COST_HIGHLIGHT = "#d9edcf"     # lowest billed cost in the triplet


# ============================================================================
# Figure 1 schematic (formerly intro_fig.py)
# ============================================================================
INTRO_FIG_DOC = """Figure 1 schematic of context growth and repeated policy execution.

The illustrated policy uses a threshold trigger and a depth-tunable rewrite.
Hatching denotes the shorter history retained after compression, not removed
text. Depth is measured on the compressible history above the fixed prompt.
The policy definitions intentionally omit the experiment grid from Sec2.
"""
INTRO_OUT = ROOT / "ICLR_experiments/plotting/plots"
INK = "#222222"
GREY = "#bdbdbd"
BLUE = PLIGHT["rule"]
THRESHOLD = 6.0
BAR_WIDTH = 0.72


def block(ax, x, bottom, height, *, compressed=False, prompt=False):
    ax.add_patch(Rectangle(
        (x - BAR_WIDTH / 2, bottom), BAR_WIDTH, height,
        facecolor=GREY if prompt else ("white" if compressed else BLUE),
        edgecolor=PDARK["rule"] if compressed else "white",
        hatch="////" if compressed else None, linewidth=0.55, zorder=3,
    ))


def bar(ax, x, fresh, history=0):
    """Fixed prompt, optional compressed history, then new interaction blocks."""
    block(ax, x, 0, 1, prompt=True)
    bottom = 1
    if history:
        block(ax, x, bottom, history, compressed=True)
        bottom += history
    for _ in range(fresh):
        block(ax, x, bottom, 1)
        bottom += 1
    return bottom


def rewrite_arrow(ax, start, end):
    arrow = FancyArrowPatch(
        start, end, connectionstyle="arc3,rad=-0.28", arrowstyle="-|>",
        mutation_scale=7, linewidth=1, color=PDARK["rule"], zorder=4,
    )
    ax.add_patch(arrow)
    return arrow


def left_panel(ax):
    # Compression is an event between agent steps, not an extra numbered step.
    for step in range(5):
        bar(ax, step, fresh=step + 1)
    bar(ax, 6.2, fresh=0, history=2)
    for x, fresh in [(7.3, 1), (8.4, 2), (9.5, 3)]:
        bar(ax, x, fresh=fresh, history=2)
    bar(ax, 11.2, fresh=0, history=2)

    ax.axhline(THRESHOLD, color=PDARK["stack"], linewidth=0.8,
               linestyle=(0, (3, 2)), zorder=1)
    ax.text(-0.35, 6.18, r"Trigger threshold $\mathbf{(T)}$", fontsize=6.5,
            color=PDARK["stack"], va="bottom")
    ax.text(6.1, 7.52, r"Primitive $\mathbf{(P)}$", fontsize=7.5,
            color=PDARK["rule"], ha="center", va="center")
    first_rewrite = rewrite_arrow(ax, (4.05, 6.65), (6.18, 3.18))
    first_rewrite.set_gid("primitive-rewrite")
    rewrite_arrow(ax, (9.53, 6.30), (11.18, 3.18))

    ax.annotate("", (5.25, 3), (5.25, 6), arrowprops=dict(
        arrowstyle="<->", color=PDARK["llm"], lw=0.85,
        shrinkA=0, shrinkB=0, mutation_scale=7,
    ))
    ax.text(6.0, 5.38, r"Depth $\mathbf{(D)}$", fontsize=6.5,
            color=PDARK["llm"], va="center")
    ax.text(12.0, 1.5, "…", fontsize=9, ha="center", va="center")

    ax.set_xlim(-0.55, 12.5)
    ax.set_ylim(0, 10.6)
    ax.set_xticks([0, 1, 2, 3, 4, 7.3, 8.4, 9.5])
    ax.set_xticklabels(range(1, 9), fontsize=6.5)
    ax.set_yticks([])
    ax.set_xlabel("Agent step", fontsize=7, labelpad=2)
    ax.set_ylabel("Context tokens", fontsize=7, labelpad=3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_bounds(0, 6)
    ax.spines["bottom"].set_color("#737373")
    ax.spines["left"].set_color("#737373")
    ax.tick_params(length=2, pad=2)


def figure_legend(fig, *, anchor=(0.375, 0.96)):
    """One compact row, ordered from fixed context to rewritten history."""
    handles = [
        Rectangle((0, 0), 1, 1, fc=GREY, ec="white"),
        Rectangle((0, 0), 1, 1, fc=BLUE, ec="white"),
        Rectangle((0, 0), 1, 1, fc="white", ec=PDARK["rule"], hatch="////", lw=0.55),
    ]
    labels = ["Fixed prompt", "New history", "Compressed history"]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=anchor,
               ncol=3, frameon=False, fontsize=6.5, handlelength=1.2,
               handleheight=1.0, handletextpad=0.4, columnspacing=0.8,
               borderaxespad=0, borderpad=0)


def connect_primitive_label(fig):
    """End the leader on the rendered curve after the panel geometry is set."""
    fig.canvas.draw()
    ax = fig.axes[0]
    arrow = next(p for p in ax.patches if p.get_gid() == "primitive-rewrite")
    start, control, end = arrow.get_path().vertices[:3]
    t = 0.18
    target = (1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end
    ax.plot([6.1, target[0]], [7.13, target[1]],
            color=PDARK["rule"], lw=0.6, zorder=5)


def make_wrap_figure():
    """Native-size inset for wrapping intro prose on a 5.5 inch text block."""
    fig = plt.figure(figsize=(3.2, 1.9))
    # Preserve the plot and definition sizes while removing the heading space.
    vertical_scale = 2.2 / 1.9
    # Left margin matched to the right one: the y-label starts ~1.8% in.
    plot_left, plot_right = 0.052, 0.98
    plot_center = (plot_left + plot_right) / 2
    ax = fig.add_axes([plot_left, 0.28 * vertical_scale,
                       plot_right - plot_left, 0.51 * vertical_scale])
    left_panel(ax)
    ax.set_ylim(0, 8.05)
    ax.yaxis.labelpad = 1
    figure_legend(fig, anchor=(plot_center, 0.99))

    # Trigger and depth share the upper row; primitive spans the lower row.
    # Keep all copy at its native print size in the compact inset.
    group_width = 0.88
    group_left = plot_center - group_width / 2
    gap = 0.014
    trigger_width = 0.51
    points_per_width = fig.get_figwidth() * 72

    def definition_box(x, y, width, height, color):
        fig.add_artist(Rectangle(
            (x, y * vertical_scale), width, height * vertical_scale,
            transform=fig.transFigure,
            facecolor="#f5f5f5", edgecolor="#d9d9d9", linewidth=0.45,
            zorder=0,
        ))
        fig.add_artist(Rectangle(
            (x, y * vertical_scale), 0.008, height * vertical_scale,
            transform=fig.transFigure,
            facecolor=color, edgecolor="none", zorder=1,
        ))

    for x, width, name, definition, label_width, color in [
        (group_left, trigger_width, r"Trigger $\mathbf{(T)}$",
         "When primitive fires", 43, PDARK["stack"]),
        (group_left + trigger_width + gap, group_width - trigger_width - gap,
         r"Depth $\mathbf{(D)}$", "How much", 40, PDARK["llm"]),
    ]:
        definition_box(x, 0.080, width, 0.064, color)
        fig.text(x + 3 / points_per_width, 0.112 * vertical_scale, name,
                 fontsize=7.5, color=color, va="center")
        fig.text(x + (label_width + 6) / points_per_width, 0.112 * vertical_scale,
                 definition, fontsize=6.5, va="center")

    definition_box(group_left, 0.008, group_width, 0.064, PDARK["rule"])
    name = fig.text(0, 0.040 * vertical_scale, r"Primitive $\mathbf{(P)}$",
                    fontsize=7.5, color=PDARK["rule"], va="center")
    definition = fig.text(0, 0.040 * vertical_scale, "How context is changed",
                          fontsize=6.5, va="center")
    connect_primitive_label(fig)
    renderer = fig.canvas.get_renderer()
    name_width = name.get_window_extent(renderer).width / fig.bbox.width
    definition_width = definition.get_window_extent(renderer).width / fig.bbox.width
    text_gap = 6 / points_per_width
    text_left = plot_center - (name_width + text_gap + definition_width) / 2
    name.set_x(text_left)
    definition.set_x(text_left + name_width + text_gap)
    return fig


def intro_fig_main(argv=None):
    """Write the intro_01_policy_axes_wrap inset (no options); the same figure
    as `--figure intro_01_policy_axes_wrap`."""
    with plt.rc_context(PAPER_STYLE):
        inset = make_wrap_figure()
        save_figure(inset, INTRO_OUT, "intro_01_policy_axes_wrap", dpi=300)
        plt.close(inset)


# The plot bank's name for the wrap inset renderer.
fig_intro_policy_axes = make_wrap_figure


# ============================================================================
# Outcomes loading, statistics and per-setting overviews (formerly appendix_knob_overview.py)
# ============================================================================
KNOB_OVERVIEW_DOC = """Appendix: the Figure 1 overview (q1_24_qwen_overview) at every depth and
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

Metrics follow q1_frontier.py and token_cost_ledger.py
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
analysis/outcomes/terminalbench_outcomes.csv (schema of
analysis/aggregate_benchmark_results.py), plus the raw
experiment_results.json named in their source_file column for the online
TRC clear flags, and the pinned task lists in task_lists/.

Run from the repository root:
    venv/bin/python ICLR_experiments/plotting/plot_bank.py knob-overview
    venv/bin/python ICLR_experiments/plotting/plot_bank.py knob-overview --model devstral24b \
        --benchmarks swebench --grid-settings all      # per-model grid, nine settings
    venv/bin/python ICLR_experiments/plotting/plot_bank.py knob-overview --settings 0.3:tight 0.7:loose
Outputs (PNG + CSV) go to ICLR_experiments/plotting/plots/ by default:
`<model>_{swe,tb}_depth_trigger_ablation_{tight,primary,loose}.png`, one
figure per threshold group and benchmark with that group's D settings as
rows (D = depth) and the five Figure 1 panels as columns. Optional extras,
off by default: `--grid` (page-wide grid, all settings as columns),
`--per-setting` (one Figure 1-style figure per setting) and `--stack`
(single-column stack of the eight non-primary settings).
"""
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
    """One Figure 1 panel (plot_bank.fig_qwen_overview, wide layout);
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


def draw_setting(frames, heading):
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


def knob_overview_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py knob-overview", description=KNOB_OVERVIEW_DOC,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tb-outcomes", type=Path,
                        default=ROOT / "analysis/outcomes/terminalbench_outcomes.csv")
    parser.add_argument("--settings", nargs="+", default=[f"{d}:{l}" for d in DEPTHS for l in LEVELS],
                        help="depth:level pairs, depth = fraction removed")
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' reproduces Figure 1")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_experiments/plotting/plots")
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
                fig = draw_setting(frames, f"{MODEL_NAMES[args.model]} · {setting}")
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


# ============================================================================
# Termination rates (formerly limit_rates.py)
# ============================================================================
LIMIT_RATES_DOC = """Main-setting termination rates, without resource/log availability filtering.

Time category reproduces the main resource exclusion rule. TB fallback is
shown separately because cancellation/missing status does not prove timeout.
Step-only excludes attempts already classified as time-capped/inferred.
"""
POLICIES=['FC']+ORDER
NAMES=dict(zip(['fc','tr','trc','su-full','su-partial','ss','ss-partial','trc-su','trc-ss','otrc-tr','otrc-su-partial','otrc-ss-partial','otrc'],['FC','TR','TRC','SU','SU-p','SS','SS-p','TRC+SU','TRC+SS','OTRC+TR','OTRC+SU-p','OTRC+SS-p','OTRC']))
LIMIT_MODELS=[('qwen35b','Qwen'),('devstral24b','Devstral'),('glm47flash','GLM')]

def limit_inputs(swe,tb):
    parts=[]
    for benchmark,path,thresholds,taskfile,n in [
        ('SWE-bench',swe,[15000,21000,13000],'p100_all_100_tasks.json',100),
        ('Terminal-Bench',tb,[3000,4000,3000],'tbench_p40.json',40)]:
        tasks=json.loads((ROOT/'task_lists'/taskfile).read_text())
        if isinstance(tasks,dict):
            tasks=tasks.get('tasks',tasks.get('task_ids',tasks))
        tasks={x['instance_id'] if isinstance(x,dict) else x for x in tasks}
        assert len(tasks)==n
        d=pd.read_csv(path,low_memory=False)
        for (model,label),threshold in zip(LIMIT_MODELS,thresholds):
            g=d[d.experiment_section.eq('main')&d.model_key.eq(model)&d.task_name.isin(tasks)&d.run_num.isin([1,2,3])].copy()
            g['policy']=g.cell.str.split('__').str[-1].map(NAMES)
            g=g[g.token_budget.eq(threshold)|g.policy.isin(['FC','OTRC'])].copy()
            assert set(g.policy)==set(POLICIES)
            assert not g.duplicated(['policy','task_name','run_num']).any()
            assert g.groupby('policy').size().eq(n*3).all()
            assert g.groupby(['policy','task_name']).size().eq(3).all()
            if benchmark=='SWE-bench':
                g['time']=pd.to_numeric(g.latency_e2e_s).ge(1500)
                g['inferred']=False
                step_limit=125
            else:
                g['time']=g.harbor_exception.eq('AgentTimeoutError')
                g['inferred']=g.harbor_exception.isna()&(g.exit_status.isna()|g.exit_status.eq('CancelledError'))
                step_limit=100
            step=g.exit_status.eq('LimitsExceeded')
            assert pd.to_numeric(g.loc[step,'step_count']).eq(step_limit).all()
            g['step_recorded']=step
            g['step']=step&~(g.time|g.inferred)
            g['submitted_failed']=g.exit_status.eq('Submitted') & g.resolved.astype('string').str.lower().eq('false').fillna(False) & ~(g.time|g.inferred|g.step)
            g['benchmark']=benchmark;g['model']=label
            parts.append(g)
    runs=pd.concat(parts,ignore_index=True)
    runs['success']=runs.resolved.astype('string').str.lower().eq('true').fillna(False)
    runs['outcome']=np.select([runs.success, runs.time|runs.inferred, runs.step,
                               runs.submitted_failed],
                              ['resolved','timeout','step_limit','submitted_failure'],default='other')
    kinds=['resolved','timeout','step_limit','submitted_failure','other']
    groups=['benchmark','model','policy']
    counts=runs.groupby(groups+['outcome']).size().unstack(fill_value=0).reindex(columns=kinds,fill_value=0)
    summary=counts.reset_index()
    summary['attempts']=summary[kinds].sum(axis=1)
    for kind in kinds: summary[kind+'_pct']=100*summary[kind]/summary.attempts
    assert np.allclose(summary[[k+'_pct' for k in kinds]].sum(axis=1),100)
    # Keep resource-exclusion rates separate: successful runs can also be capped.
    audit=runs.assign(resource_excluded=runs.time|runs.inferred)
    extra=audit.groupby(groups).agg(resource_excluded_count=('resource_excluded','sum'),
                                   successful_excluded_count=('success',lambda v: int((v & audit.loc[v.index,'resource_excluded']).sum())),
                                   inferred_count=('inferred','sum')).reset_index()
    summary=summary.merge(extra,on=groups,validate='one_to_one')
    return summary,audit[['benchmark','model','policy','task_name','run_num','source_file','exit_status','step_count','latency_e2e_s','time','inferred','step_recorded','resolved','outcome','resource_excluded']]

def fig_limit_rates(summary):
    """Directly labeled, exhaustive outcome stacked bars on a shared scale."""
    fig,axes=plt.subplots(2,3,figsize=(8.0,6.3),sharex=True,sharey=True)
    categories=[('resolved','Resolved','#39836b'),('timeout','Unresolved: time limit*','#d97932'),
                ('step_limit','Unresolved: step limit','#397eaf'),
                ('submitted_failure','Submitted, failed evaluation','#99618b'),('other','Other / missing outcome','#c5c5c5')]
    for row,benchmark in enumerate(['SWE-bench','Terminal-Bench']):
        for col,(_,model) in enumerate(LIMIT_MODELS):
            ax=axes[row,col]
            g=summary[summary.benchmark.eq(benchmark)&summary.model.eq(model)].set_index('policy').loc[POLICIES]
            y=np.arange(len(g));left=np.zeros(len(g))
            for key,label,color in categories:
                values=g[key+'_pct'].to_numpy()
                ax.barh(y,values,left=left,height=.73,color=color)
                for i,v in enumerate(values):
                    if v>=9 or key=='resolved':
                        ax.text(left[i]+v/2,i,f'{v:.0f}',ha='center',va='center',fontsize=6.5,
                                color='0.2' if key=='other' else 'white')
                left+=values
            ax.set_title(model,fontsize=10,fontweight='bold',pad=8)
            ax.set_yticks(y,POLICIES,fontsize=8)
            ax.set_xlim(0,100);ax.set_xticks([0,25,50,75,100])
            ax.tick_params(axis='y',length=0)
            ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
            ax.spines[['top','right','left']].set_visible(False)
            if row==1:ax.set_xlabel('Share of all attempts (%)',fontsize=8)
    axes[0,0].invert_yaxis()
    fig.subplots_adjust(left=.145,right=.98,top=.86,bottom=.13,hspace=.31,wspace=.18)
    fig.text(.145,.92,'SWE-bench · 300 attempts per policy and model',fontsize=10)
    fig.text(.145,.50,'Terminal-Bench · 120 attempts per policy and model',fontsize=10)
    fig.legend(handles=[Patch(facecolor=color,label=label) for _,label,color in categories],
               loc='upper center',bbox_to_anchor=(.55,1.005),ncol=3,frameon=False,fontsize=7.5)
    fig.text(.55,.025,'Each bar sums to 100%. Successful verdicts take priority over exit status.\n'
             '* Includes inferred Terminal-Bench timeouts. Segment labels are percentages.',
             ha='center',fontsize=7,color='0.25')
    return fig


# ============================================================================
# Agent-call comparison (formerly step_comparison.py)
# ============================================================================
STEP_COMPARISON_DOC = """Agent-call changes on tasks solved by both policies (>=2/3 successes).
Successful attempts only, task means, paired bootstrap B=10,000 seed=210926.
"""
def step_inputs(swe,tb):
    _,runs=limit_inputs(swe,tb)
    runs['success']=runs.resolved.astype('string').str.lower().eq('true').fillna(False)
    runs['calls']=pd.to_numeric(runs.step_count,errors='coerce')
    assert runs.loc[runs.success,'calls'].notna().all()
    assert runs.loc[runs.success,'calls'].gt(0).all()
    rng=np.random.default_rng(210926)
    rows=[];paired=[]
    for (bench,model),g in runs.groupby(['benchmark','model'],sort=False):
        solved=g.groupby(['policy','task_name']).success.sum().ge(2).unstack('policy')
        means=g[g.success].groupby(['task_name','policy']).calls.mean().unstack('policy')
        for policy in ORDER:
            tasks=solved.index[solved[policy]&solved.FC]
            if len(tasks)==0:
                rows.append(dict(benchmark=bench,model=model,policy=policy,n_tasks=0,change=np.nan,lo=np.nan,hi=np.nan))
                continue
            v=means.loc[tasks,policy].to_numpy();base=means.loc[tasks,'FC'].to_numpy()
            idx=rng.integers(0,len(tasks),(10000,len(tasks)))
            boot=(v[idx].mean(axis=1)/base[idx].mean(axis=1)-1)*100
            lo,hi=np.percentile(boot,[2.5,97.5])
            rows.append(dict(benchmark=bench,model=model,policy=policy,n_tasks=len(tasks),
                             policy_calls=v.mean(),fc_calls=base.mean(),change=(v.mean()/base.mean()-1)*100,lo=lo,hi=hi))
            paired.extend(dict(benchmark=bench,model=model,policy=policy,task=task,policy_calls=a,fc_calls=b)
                          for task,a,b in zip(tasks,v,base))
    return pd.DataFrame(rows),pd.DataFrame(paired)


def fig_step_comparison(summary):
    fig,axes=plt.subplots(2,3,figsize=(8,6.1),sharex="row",sharey=True)
    low=min(-10,np.floor(summary.lo.min()/25)*25)
    high=max(25,np.ceil(summary.hi.max()/25)*25)
    for row,bench in enumerate(['SWE-bench','Terminal-Bench']):
        subset=summary[summary.benchmark.eq(bench)]
        low=min(-10,np.floor(subset.lo.min()/10)*10)
        high=max(25,np.ceil(subset.hi.max()/10)*10)
        for col,(_,model) in enumerate(LIMIT_MODELS):
            ax=axes[row,col]
            g=summary[summary.benchmark.eq(bench)&summary.model.eq(model)].set_index('policy').loc[ORDER]
            for i,(policy,r) in enumerate(g.iterrows()):
                if r.n_tasks:
                    ax.plot([r.lo,r.hi],[i,i],color=pcol(policy),lw=1.2)
                    ax.plot(r.change,i,'o',color=pcol(policy),ms=4)
                ax.text(1.02,i,str(int(r.n_tasks)),transform=ax.get_yaxis_transform(),va='center',fontsize=7,color='0.4')
            ax.text(1.02,1.015,'n',transform=ax.transAxes,fontsize=7,color='0.4')
            ax.axvline(0,color='0.4',ls='--',lw=.8)
            ax.set_yticks(range(len(ORDER)),ORDER,fontsize=8)
            ax.set_xlim(low,high)
            ax.set_title(model,fontweight='bold',fontsize=10,pad=8)
            ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
            ax.spines[['top','right','left']].set_visible(False)
            ax.tick_params(axis='y',length=0)
            if row == 1:
                ax.set_xlabel('Change in agent calls vs. FC (%)',fontsize=8)
    axes[0,0].invert_yaxis()
    fig.subplots_adjust(left=.145,right=.95,top=.88,bottom=.13,hspace=.38,wspace=.25)
    fig.text(.145,.95,'SWE-bench',fontsize=11)
    fig.text(.145,.51,'Terminal-Bench',fontsize=11)
    fig.text(.55,.025,'Left of zero: fewer calls. Right of zero: more calls. Bars: 95% paired task-bootstrap intervals.\n'
             'Successful attempts on tasks solved in ≥2/3 runs by both policies; n = shared tasks.',ha='center',fontsize=7,color='0.25')
    return fig


# ============================================================================
# Summarizer ablation (formerly summarizer_ablation.py)
# ============================================================================
SUMMARIZER_ABLATION_DOC = """Summarizer sensitivity on pinned ABL-25; invoked by plot_bank.py.

Success uses all attempts. Resource ratios use uncapped runs with >=2
prompt counts, task means, and tasks shared by all three summarizers.
Intervals: 5,000 task bootstrap samples, seed 0; paired for ratios/deltas.
"""
SUMMARIZER_MODELS = [('qwen35b', 'Self'), ('qwen35b-sum-qwen35-9b', 'Qwen3.5-9B'),
          ('qwen35b-sum-gemma4-12b', 'Gemma-4-12B')]
SUMMARIZER_CELLS = {'d05__b15k__su-full': 'SU', 'di__b15k__trc-su': 'TRC+SU'}


def summarizer_inputs(outcomes):
    d = pd.read_csv(outcomes, low_memory=False)
    tasks = sorted(x['instance_id'] for x in json.loads((ROOT / 'task_lists/ablation_25tasks.json').read_text()))
    parts = []
    for model, label in SUMMARIZER_MODELS:
        track = 'main' if label == 'Self' else 'model_ablation'
        g = d[d.model_key.eq(model) & d.experiment_section.eq(track) &
              d.task_name.isin(tasks) & d.cell.isin(SUMMARIZER_CELLS) & d.run_num.isin([1, 2, 3])].copy()
        assert not g.duplicated(['cell', 'task_name', 'run_num']).any()
        for cell in SUMMARIZER_CELLS:
            c = g[g.cell.eq(cell)]
            assert len(c) == 75 and set(c.task_name) == set(tasks)
            assert c.groupby('task_name').size().eq(3).all()
        g['summarizer'] = label
        parts.append(g)
    d = pd.concat(parts, ignore_index=True)
    d['policy'] = d.cell.map(SUMMARIZER_CELLS)
    verdict = d.resolved.astype('string').str.lower()
    assert (verdict.isna() | verdict.isin(['true', 'false'])).all()
    d['success'] = verdict.eq('true').fillna(False).astype(float)
    d['usage'] = pd.to_numeric(d.total_prompt_tokens) + pd.to_numeric(d.total_completion_tokens)
    d['latency'] = pd.to_numeric(d.latency_e2e_s)
    d['prompt_calls'] = d.step_prompt_tokens.map(lambda x: len(json.loads(x)) if isinstance(x, str) else 0)
    d['eligible'] = d.latency.lt(1500) & d.latency.ge(0) & d.usage.ge(0) & d.prompt_calls.ge(2)
    rng = np.random.default_rng(0)
    rows = []
    for policy in SUMMARIZER_CELLS.values():
        g = d[d.policy.eq(policy)]
        success = g.groupby(['task_name', 'summarizer']).success.mean().unstack().loc[tasks]
        eligible = g[g.eligible]
        common = sorted(set.intersection(*(set(eligible[eligible.summarizer.eq(label)].task_name) for _, label in SUMMARIZER_MODELS)))
        assert common
        ix = rng.integers(0, len(tasks), (5000, len(tasks)))
        jx = rng.integers(0, len(common), (5000, len(common)))
        for _, label in SUMMARIZER_MODELS:
            values = success[label].to_numpy()
            boots = values[ix].mean(axis=1) * 100
            diff = (values - success.Self.to_numpy())[ix].mean(axis=1) * 100
            row = dict(policy=policy, summarizer=label, attempts=75, tasks=25,
                       success=values.mean()*100, success_lo=np.percentile(boots, 2.5),
                       success_hi=np.percentile(boots, 97.5),
                       success_delta=(values-success.Self.to_numpy()).mean()*100,
                       delta_lo=np.percentile(diff,2.5), delta_hi=np.percentile(diff,97.5),
                       resource_tasks=len(common), eligible_runs=int((eligible.summarizer.eq(label)&eligible.task_name.isin(common)).sum()))
            for metric in ['usage', 'latency']:
                means = eligible.groupby(['task_name', 'summarizer'])[metric].mean().unstack().loc[common]
                v, base = means[label].to_numpy(), means.Self.to_numpy()
                ratios = v[jx].mean(axis=1)/base[jx].mean(axis=1)
                row[metric] = v.mean()/base.mean()
                row[metric+'_lo'],row[metric+'_hi'] = np.percentile(ratios,[2.5,97.5])
                row[metric+'_absolute'] = v.mean()
            rows.append(row)
    audit_cols=['policy','summarizer','task_name','run_num','source_file','success','usage','latency','prompt_calls','eligible']
    return pd.DataFrame(rows), d[audit_cols]


def fig_summarizer_ablation(summary):
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.65))
    labels = [label for _, label in SUMMARIZER_MODELS]
    for ax, metric, title, ylabel in zip(axes, ['success','usage','latency'],
            ['(a) Task success','(b) Token consumption','(c) End-to-end latency'],
            ['Resolve rate (%)','Tokens / self','Latency / self']):
        for policy, offset, marker in [('SU',-.1,'o'),('TRC+SU',.1,'s')]:
            g=summary[summary.policy.eq(policy)].set_index('summarizer').loc[labels]
            v=g[metric].to_numpy()
            ax.errorbar(np.arange(3)+offset,v,yerr=np.vstack([v-g[metric+'_lo'],g[metric+'_hi']-v]),
                        fmt=marker, color=pcol(policy), capsize=3, markersize=4, label=policy)
        ax.set_xticks(range(3),['Self','Qwen3.5\n9B','Gemma-4\n12B'])
        ax.set_xlim(-.4,2.4)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.18)
        if metric=='success': ax.set_ylim(0,100)
        else: ax.axhline(1,color='0.5',ls='--',lw=.8)
    axes[0].legend(frameon=False,loc='upper left',ncol=2,handletextpad=.3,columnspacing=.7)
    fig.subplots_adjust(left=.075,right=.99,bottom=.23,top=.88,wspace=.48)
    return fig


# ============================================================================
# Original paper figures and the Q2 loader (formerly paper_figures.py)
# ============================================================================
PAPER_FIGURES_DOC = """The three main paper figures and their shared style, in one source file.

Run from the repo root (Python with numpy, pandas, matplotlib):
    venv/bin/python ICLR_experiments/plotting/plot_bank.py paper-figures
    venv/bin/python ICLR_experiments/plotting/plot_bank.py paper-figures --figure q2 --output-dir /tmp/figs
    venv/bin/python ICLR_experiments/plotting/plot_bank.py paper-figures --figure q1-qwen-overview
    venv/bin/python ICLR_experiments/plotting/plot_bank.py paper-figures --help

Outputs (PNG, default ICLR_experiments/plotting/plots):
    q1_20_o1_frontier, q1_21_o2_bill_latency,
    q2_qwen_task_map_and_endings
The optional q1-qwen-overview target exports a wide 2x5 Qwen overview and
two 5.5-inch companion figures (token comparisons and success comparisons).
It also requires resolve, time_lo, time_hi in the Qwen frontier exports and
token_cost_ledger[_tb]_qwen35b.csv (policy, task, resolved) to bootstrap
absolute resolve-rate intervals. Paired difference intervals are not reused
as absolute resolve-rate intervals.

Data are read only and are NOT bundled in this plotting source. Supply the
following existing analysis exports locally, or via the CLI paths:
* --data-dir: q1_frontier[_tb]_<model>.csv for qwen35b, devstral24b,
  glm47flash. Required columns: policy, usage, time, dres, dres_lo,
  dres_hi, bill, bill_lo, bill_hi. FC plus all 12 policies are required.
* --data-dir: q1_step_factor.csv. Required columns: benchmark, model,
  policy, leg, steps, per_step, per_step_lo, per_step_hi. Uses SWE e2e rows.
* --outcomes: analysis/outcomes/swebench_outcomes.csv, exported by
  analysis/aggregate_benchmark_results.py. --tasks: the pinned P100 JSON,
  a list of objects with instance_id. See load_q2_runs for the CSV schema.
* --tb-outcomes: analysis/outcomes/terminalbench_outcomes.csv; --tb-tasks:
  task_lists/tbench_p40.json. Terminal-Bench censoring reads Harbor results
  beneath --run-root, falling back to CancelledError/empty exit status.
The Q1 exports come from q1_frontier.py and q1_step_factor.py; neither is
imported or run here. Q2 is computed directly, with no scratch-file inputs.
--figure q2 needs both benchmarks' outcomes and pinned task lists, plus Harbor
records where available; Q1 needs only its exports.
--audit-dir optionally exports Q2 task order and all displayed numerical values.

Conventions:
* Q1 preserves the supplied task-bootstrap intervals. Success includes capped
  runs as unresolved; resource ratios use uncapped runs paired by task with FC.
  The billing metric is estimated billed INPUT cost, as in the selected plot.
* Q2 uses Qwen main-track SWE 15K and Terminal-Bench 3K, depth 0.5;
  FC/OTRC are budget-free references.
  Each policy must have exactly runs 1,2,3 on every pinned task (100 SWE, 40 TB).
  Success requires >=2/3 resolved attempts; >=1500 s or missing verdict means
  unresolved. Both FC blocks show EVERY task, ordered by policy coverage then ID.
  Terminal-Bench uses TB-40 runs 1--3 and Harbor per-task timeout flags.
* Steps: successful attempts on tasks both policies solve, averaged within each
  task, then across paired tasks. Ratio of means, marginal 95% paired-task
  bootstrap (10,000 resamples, seed 210926 independently for each policy).
  The two step panels have different axis ranges. Each policy/benchmark uses
  its own shared-solved tasks; n reports their count. These selected subsets
  do not identify a causal effect of extra steps on failures.

Reuse the style without producing files or changing global rcParams on import:
    from pathlib import Path
    import matplotlib.pyplot as plt
    from plot_bank import PAPER_STYLE, pcol, pmark, save_figure
    with plt.rc_context(PAPER_STYLE):
        fig, ax = plt.subplots(figsize=(5.5, 2.3))
        pmark(ax, 1.0, 0.8, "SU-p", "o")
        save_figure(fig, Path("my_plots"), "new_figure")

Style: 5.5 inch ICLR width; DejaVu Sans; embedded TrueType PDF fonts;
ColorBrewer blue=rule, orange=LLM, green=stacked, gray=step-triggered.
Shade distinguishes primitives; hollow markers denote partial rewrite;
OTRC is black/hollow. Model shapes: Qwen circle, Devstral triangle, GLM diamond.
The task map uses policy colors plus explicit symbols; consult labels as well
as colors. Its existing output filename is retained for paper references.
"""
def read_required_csv(path, required):
    """Fail explicitly on missing inputs/columns rather than drawing partial plots."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Missing input: {path}. See this script's data requirements.")
    frame = pd.read_csv(path, low_memory=False)
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return frame


def load_q1(data_dir, need_steps):
    columns = ["policy", "usage", "time", "dres", "dres_lo", "dres_hi",
               "bill", "bill_lo", "bill_hi"]
    frontiers = {}
    for benchmark, tag in [("swebench", ""), ("terminalbench", "tb_")]:
        for model, _, _ in MODELS:
            path = data_dir / f"q1_frontier_{tag}{model}.csv"
            frame = read_required_csv(path, columns).set_index("policy", verify_integrity=True)
            if set(ORDER + ["FC"]) - set(frame.index):
                raise ValueError(f"{path}: expected FC and all 12 policies")
            frame = frame.loc[["FC"] + ORDER]
            if not np.isfinite(frame[columns[1:]].to_numpy(float)).all():
                raise ValueError(f"{path}: non-finite plotted values")
            for metric in ("dres", "bill"):
                if not ((frame[metric + "_lo"] <= frame[metric]) &
                        (frame[metric] <= frame[metric + "_hi"])).all():
                    raise ValueError(f"{path}: {metric} interval does not enclose estimate")
            frontiers[benchmark, model] = frame
    factors = None
    if need_steps:
        factors = read_required_csv(data_dir / "q1_step_factor.csv", [
            "benchmark", "model", "policy", "leg", "steps", "per_step",
            "per_step_lo", "per_step_hi"])
        factors = factors[factors.benchmark.eq("swebench") & factors.leg.eq("e2e")]
        factors = factors.set_index(["model", "policy"], verify_integrity=True)
        expected = pd.MultiIndex.from_product([[m for m, _, _ in MODELS], ORDER])
        if len(expected.difference(factors.index)):
            raise ValueError("q1_step_factor.csv: missing SWE e2e model/policy rows")
        factors = factors.loc[expected]
        cols = ["steps", "per_step", "per_step_lo", "per_step_hi"]
        if not np.isfinite(factors[cols].to_numpy(float)).all():
            raise ValueError("q1_step_factor.csv: non-finite plotted values")
        if not ((factors.per_step_lo <= factors.per_step) &
                (factors.per_step <= factors.per_step_hi)).all():
            raise ValueError("q1_step_factor.csv: interval does not enclose estimate")
    return frontiers, factors


# Q1: preserve the two selected figures' layouts, annotations, and encodings.
def fig_o1(frontiers):
    """Return the resolve-rate / resource-use figure from indexed summary tables."""
    fig, ax = plt.subplots(2, 2, figsize=(5.5, 3.5))
    for r, (bench, bname) in enumerate([("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]):
        F = {m: frontiers[bench, m] for m, _, _ in MODELS}
        for c, (leg, xlab) in enumerate([("usage", "token usage / full context"), ("time", "wall-clock / full context")]):
            a = ax[r, c]
            a.axhline(0, color="#999999", lw=0.6, ls="--", zorder=0)
            a.axvline(1, color="#999999", lw=0.6, ls="--", zorder=0)
            for m, _, _ in MODELS:
                f = F[m]
                for p in ORDER:
                    if p not in f.index: continue
                    q = f.loc[p]
                    a.errorbar(q[leg], q.dres, yerr=[[q.dres - q.dres_lo], [q.dres_hi - q.dres]],
                               fmt="none", ecolor="#dedede", elinewidth=0.5, capsize=0, zorder=1)
                    pmark(a, q[leg], q.dres, p, MK[m])
            a.scatter(1, 0, marker="*", s=90, color="black", zorder=5)
            a.set_title(f"{bname}, {'token usage' if leg == 'usage' else 'latency'}", loc="left", pad=3)
            if r == 1: a.set_xlabel(xlab)
            a.grid(alpha=0.2, lw=0.5)
            if c == 0: a.set_ylabel("success vs FC (pp)")
        # the two diagnostic pairs named in the prose (SWE row)
        if bench == "swebench":
            f = F["qwen35b"]; a = ax[0, 0]
            ys = [f.loc[p].dres for p in ["TRC", "TRC+SU", "SU"]]; xs = [f.loc[p].usage for p in ["TRC", "TRC+SU", "SU"]]
            xb = max(xs) + 0.03
            a.plot([xb, xb], [min(ys), max(ys)], color="#333333", lw=0.7)
            a.plot([xb - 0.008, xb], [min(ys)] * 2, color="#333333", lw=0.7); a.plot([xb - 0.008, xb], [max(ys)] * 2, color="#333333", lw=0.7)
            a.annotate("same tokens\nQwen TRC, TRC+SU, SU", xy=(xb, np.mean(ys)), xytext=(0.70, -21), fontsize=6.5,
                       ha="left", va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=2))
            f = F["devstral24b"]; a = ax[0, 1]
            xs = [f.loc[p].time for p in ["TR", "SS-p"]]; ys = [f.loc[p].dres for p in ["TR", "SS-p"]]
            yb = max(ys) + 4
            a.plot([min(xs), max(xs)], [yb, yb], color="#333333", lw=0.7)
            a.plot([min(xs)] * 2, [yb - 1, yb], color="#333333", lw=0.7); a.plot([max(xs)] * 2, [yb - 1, yb], color="#333333", lw=0.7)
            a.text(max(xs) + 0.03, yb, "Devstral TR, SS-p\nsame success", va="center", ha="left", fontsize=6.5)
    ax[0, 0].set_xlim(0.3, 1.06); ax[0, 1].set_xlim(0.72, 1.58)
    ax[1, 0].set_xlim(0.05, 1.06); ax[1, 1].set_xlim(0.9, 2.6)
    for r in range(2):
        lo = min(a.get_ylim()[0] for a in ax[r]); hi = max(a.get_ylim()[1] for a in ax[r])
        for a in ax[r]: a.set_ylim(lo, hi)
    # one legend, two rows of eight: models and FC first, then the primitives (matplotlib fills column-major)
    allh = model_handles() + [Line2D([], [], marker="*", ls="", color="black", ms=8, label="full context")] + prim_handles()
    row1, row2 = allh[:8], allh[8:]
    fig.legend(handles=[h for pair in zip(row1, row2) for h in pair], loc="upper center", ncol=8, frameon=False,
               handletextpad=0.2, columnspacing=0.8, fontsize=6, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.925), h_pad=0.6)
    return fig


def fig_o2_bill(frontiers, step_factors):
    """Compact 1x3: SWE and TB billing, then the original SWE latency factor panel.

    Reuses O1's primitive colors, model markers, and two-row shared legend.
    Billing panels share limits; gray shading denotes bills above full context.
    """
    S = step_factors
    fig = plt.figure(figsize=(5.5, 2.3))
    # The two billing panels share a y label and ticks, leaving more room for
    # the third panel's distinct y label without increasing the figure height.
    ax = [fig.add_axes([0.090, 0.185, 0.255, 0.575]),
          fig.add_axes([0.375, 0.185, 0.255, 0.575]),
          fig.add_axes([0.725, 0.185, 0.265, 0.575])]

    for i, (bench, bname) in enumerate([("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]):
        a = ax[i]
        a.axhspan(1, 1.6, color="#f1f1f1", zorder=-1)
        a.plot([0, 1.1], [0, 1.1], color="#999999", lw=0.6, ls=":", zorder=0)
        a.axhline(1, color="#999999", lw=0.6, ls="--", zorder=0)
        for m, _, k in MODELS:
            f = frontiers[bench, m]
            for p in ORDER:
                if p not in f.index: continue
                q = f.loc[p]
                a.errorbar(q.usage, q.bill, yerr=[[q.bill - q.bill_lo], [q.bill_hi - q.bill]],
                           fmt="none", ecolor="#e4e4e4", elinewidth=0.5, capsize=0, zorder=1)
                pmark(a, q.usage, q.bill, p, k, s=18)
        a.scatter(1, 1, marker="*", s=60, color="black", zorder=5)
        a.set_xlim(0.05, 1.08); a.set_ylim(0.3, 1.6); a.grid(alpha=0.2, lw=0.5)
        a.set_xticks([0.2, 0.6, 1.0]); a.set_yticks([0.5, 1.0, 1.5])
        a.set_xlabel("token usage / FC", labelpad=2)
        a.set_title(f"({chr(97 + i)}) {bname}", loc="left", pad=3)
        a.text(1.04, 1.565, "higher bill", fontsize=6, color="#777777", style="italic", ha="right", va="top")
    ax[0].set_ylabel("billed input cost / FC", labelpad=3)
    ax[1].tick_params(axis="y", labelleft=False)

    # Highlight the Qwen inversion, keeping the callout in the
    # empty shaded area and connecting the two actual plotted coordinates.
    a = ax[0]; f = frontiers["swebench", "qwen35b"]
    before, after = f.loc["TRC"], f.loc["OTRC+TR"]
    for p, q in [("TRC", before), ("OTRC+TR", after)]:
        a.scatter(q.usage, q.bill, marker=MK["qwen35b"], s=25, color=pcol(p),
                  edgecolors="#333333", linewidths=0.65, zorder=5)
    a.annotate("", xy=(after.usage, after.bill), xytext=(before.usage, before.bill),
               arrowprops=dict(arrowstyle="->", color="#333333", lw=0.85,
                               shrinkA=3, shrinkB=3), zorder=6)
    a.annotate("Qwen: TRC → OTRC+TR\nfewer tokens, higher bill",
               xy=(after.usage, after.bill), xytext=(0.105, 1.36), fontsize=6,
               ha="left", va="center", linespacing=1.4,
               arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))

    a = ax[2]
    xx = np.linspace(0.55, 1.45, 200); a.plot(xx, 1 / xx, color="#999999", lw=0.6, ls=":", zorder=0)
    a.axhline(1, color="#dddddd", lw=0.5, zorder=0); a.axvline(1, color="#dddddd", lw=0.5, zorder=0)
    for m, _, k in MODELS:
        for p in ORDER:
            if (m, p) not in S.index: continue
            q = S.loc[(m, p)]
            a.errorbar(q.steps, q.per_step, yerr=[[q.per_step - q.per_step_lo], [q.per_step_hi - q.per_step]],
                       fmt="none", ecolor="#e4e4e4", elinewidth=0.5, capsize=0, zorder=1)
            pmark(a, q.steps, q.per_step, p, k, s=18, force_hollow=(m == "glm47flash" and p in {"SU", "SS"}))
    a.scatter(1, 1, marker="*", s=60, color="black", zorder=5)
    a.set_xlim(0.62, 1.38); a.set_ylim(0.6, 1.9); a.grid(alpha=0.2, lw=0.5)
    a.set_xticks([0.8, 1.0, 1.2]); a.set_yticks([0.6, 1.0, 1.4, 1.8])
    a.set_xlabel("model calls / FC", labelpad=2); a.set_ylabel("seconds per call / FC", labelpad=3)
    a.set_title("(c) SWE-bench latency", loc="left", pad=3)
    a.text(0.78, 1 / 0.78 + 0.03, "same latency\nas FC", fontsize=5.5, color="#666666", ha="left", va="bottom")
    a.text(1.37, 1.86, "slower", fontsize=6, color="#666666", style="italic", ha="right", va="top")
    a.text(1.37, 0.62, "faster", fontsize=6, color="#666666", style="italic", ha="right", va="bottom")
    q = S.loc[("qwen35b", "OTRC+TR")]
    a.annotate("Qwen\nstep-triggered", xy=(q.steps, q.per_step), xytext=(0.80, 0.78), fontsize=5.5, ha="center",
               va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))
    q = S.loc[("devstral24b", "OTRC+TR")]
    a.annotate("Devstral\nstep-triggered", xy=(q.steps, q.per_step), xytext=(1.20, 1.55), fontsize=5.5, ha="center",
               va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))
    # Exactly the legend order, primitive encoding, and typography used by O1.
    allh = model_handles() + [Line2D([], [], marker="*", ls="", color="black", ms=8, label="full context")] + prim_handles()
    row1, row2 = allh[:8], allh[8:]
    fig.legend(handles=[h for pair in zip(row1, row2) for h in pair], loc="upper center", ncol=8, frameon=False,
               handletextpad=0.2, columnspacing=0.8, fontsize=6, bbox_to_anchor=(0.5, 1.0))
    return fig


def load_qwen_overview(data_dir, resamples=10000, seed=210926):
    """Preserve Q1 estimates and add genuine absolute-success intervals."""
    frames = {}
    columns = ["policy", "resolve", "dres", "dres_lo", "dres_hi", "usage",
               "bill", "bill_lo", "bill_hi", "time", "time_lo", "time_hi"]
    for benchmark, tag in [("swebench", ""), ("terminalbench", "tb_")]:
        path = data_dir / f"q1_frontier_{tag}qwen35b.csv"
        frame = read_required_csv(path, columns).set_index("policy", verify_integrity=True)
        missing = set(["FC"] + ORDER) - set(frame.index)
        if missing:
            raise ValueError(f"{path}: missing policies {sorted(missing)}")
        frame = frame.loc[["FC"] + ORDER].copy()
        if not np.isfinite(frame[columns[1:]].to_numpy(float)).all():
            raise ValueError(f"{path}: non-finite plotted values")
        for metric in ["dres", "bill", "time"]:
            if not ((frame[metric + "_lo"] <= frame[metric]) &
                    (frame[metric] <= frame[metric + "_hi"])).all():
                raise ValueError(f"{path}: invalid {metric} intervals")

        ledger_path = data_dir / f"token_cost_ledger_{tag}qwen35b.csv"
        ledger = read_required_csv(ledger_path, ["policy", "task", "resolved"])
        if ledger.resolved.isna().any() or not ledger.resolved.isin([True, False, 0, 1]).all():
            raise ValueError(f"{ledger_path}: resolved must contain nonmissing boolean values")
        ledger["success"] = ledger.resolved.astype(float)
        for policy in frame.index:
            values = ledger[ledger.policy.eq(policy)].groupby("task").success.mean().to_numpy()
            if not len(values) or not np.isclose(values.mean() * 100, frame.loc[policy, "resolve"], atol=1e-6):
                raise ValueError(f"{ledger_path}: {policy} success differs from {path.name}; use matched exports")
            # All runs, including capped runs as unresolved, as in q1_frontier.
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, len(values), (resamples, len(values)))
            lo, hi = np.percentile(values[idx].mean(axis=1) * 100, [2.5, 97.5])
            frame.loc[policy, "resolve_lo"] = lo
            frame.loc[policy, "resolve_hi"] = hi
            frame.loc[policy, "n_success_tasks"] = len(values)
        frames[benchmark] = frame
    return frames


# Q2: reconstruct memberships and successful-run steps on shared solved tasks.
QWEN_CELLS = {
    "d05__b15k__tr": "TR", "di__b15k__trc": "TRC",
    "d05__b15k__su-full": "SU", "d05__b15k__su-partial": "SU-p",
    "d05__b15k__ss": "SS", "d05__b15k__ss-partial": "SS-p",
    "di__b15k__trc-su": "TRC+SU", "di__b15k__trc-ss": "TRC+SS",
    "di__b15k__otrc-tr": "OTRC+TR", "di__b15k__otrc-su-partial": "OTRC+SU-p",
    "di__b15k__otrc-ss-partial": "OTRC+SS-p",
    "di__binf__otrc": "OTRC", "di__binf__fc": "FC",
}


def load_q2_runs(outcomes_path, tasks_path, benchmark="swebench", run_root=ROOT):
    """Load the fixed main-track cohort, retaining missing verdicts as unresolved."""
    required = ["benchmark", "experiment_section", "model_key", "cell", "task_name",
                "run_num", "resolved", "exit_status", "step_count", "latency_e2e_s"]
    is_tb = benchmark == "terminalbench"
    if is_tb:
        required += ["source_file", "condition"]
    d = read_required_csv(outcomes_path, required)
    manifest = json.loads(tasks_path.read_text())
    pinned = manifest["tasks"] if is_tb else [row["instance_id"] for row in manifest]
    n_tasks = 40 if is_tb else 100
    if len(pinned) != n_tasks or len(set(pinned)) != n_tasks:
        raise ValueError(f"Q2 expects the pinned {n_tasks}-task {benchmark} cohort")
    cells = {cell.replace("b15k", "b3k") if is_tb else cell: policy
             for cell, policy in QWEN_CELLS.items()}
    d = d[d.benchmark.eq(benchmark) & d.experiment_section.eq("main") &
          d.model_key.eq("qwen35b") & d.cell.isin(cells) &
          d.task_name.isin(pinned) & d.run_num.isin([1, 2, 3])].copy()
    d = d.rename(columns={"task_name": "task", "run_num": "run"})
    d["policy"] = d.cell.map(cells)
    expected = pd.MultiIndex.from_product([sorted(pinned), ROWS, [1, 2, 3]],
                                          names=["task", "policy", "run"])
    actual = pd.MultiIndex.from_frame(d[["task", "policy", "run"]])
    if actual.has_duplicates or len(expected.difference(actual)):
        raise ValueError(f"Q2 requires exactly three unique runs per task/policy ({n_tasks*39} rows)")
    verdict = d.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError("Q2 resolved values must be True, False, or missing")
    if is_tb:
        caps = []
        for row in d.itertuples():
            path = (run_root / Path(row.source_file).parent / row.task /
                    row.condition / f"run_{int(row.run)}" / "harbor_result.json")
            info = {}
            if path.is_file():
                info = json.loads(path.read_text()).get("exception_info") or {}
            status = "" if pd.isna(row.exit_status) else row.exit_status
            caps.append(info.get("exception_type") == "AgentTimeoutError" if info
                        else status in ("CancelledError", ""))
        d["capped"] = caps
    else:
        if not np.isfinite(d.latency_e2e_s.to_numpy(float)).all():
            raise ValueError("Q2 latency is missing/non-finite; cannot determine timeout flags")
        d["capped"] = d.latency_e2e_s.ge(1500)
    d["res"] = verdict.eq("true").fillna(False) & ~d.capped
    successful_steps = d.loc[d.res, "step_count"].to_numpy(float)
    if not (np.isfinite(successful_steps) & (successful_steps > 0)).all():
        raise ValueError("Q2 successful attempts require positive, finite step counts")
    return d


def summarize_q2(d, resamples=10000, seed=210926):
    """Return task membership and paired statistics; resample tasks, not runs."""
    k = d.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].astype(int)
    solved = k.ge(2)
    means = d[d.res].groupby(["task", "policy"]).step_count.mean().unstack()
    rows = []
    for policy in ORDER:
        common = solved.FC & solved[policy]
        gained = ~solved.FC & solved[policy]
        lost = solved.FC & ~solved[policy]
        pairs = means.loc[common, [policy, "FC"]]
        if pairs.empty or pairs.isna().any().any():
            raise ValueError(f"{policy}: no complete successful-run step pairs")
        a, f = pairs[policy].to_numpy(), pairs.FC.to_numpy()
        # Reset per policy so adding another plot/policy never changes existing CIs.
        rng = np.random.default_rng(seed)
        ix = rng.integers(0, len(pairs), (resamples, len(pairs)))
        boots = a[ix].mean(axis=1) / f[ix].mean(axis=1)
        lo, hi = np.quantile(boots, [.025, .975])
        if int(solved[policy].sum()) != int(solved.FC.sum() + gained.sum() - lost.sum()):
            raise ValueError(f"{policy}: inconsistent task partition")
        rows.append(dict(policy=policy, cohort_tasks=len(k), fc_solved=int(solved.FC.sum()),
                         solved=int(solved[policy].sum()), gained=int(gained.sum()), lost=int(lost.sum()),
                         n_tasks=int(common.sum()), policy_steps=a.mean(), fc_steps=f.mean(),
                         policy_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq(policy)).sum()),
                         fc_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq("FC")).sum()),
                         ratio=a.mean()/f.mean(), ratio_lo=lo, ratio_hi=hi))
    summary = pd.DataFrame(rows).set_index("policy")
    coverage = solved[ORDER].sum(axis=1)
    meta = pd.DataFrame({"fc": solved.FC, "coverage": coverage,
                         "task": solved.index}, index=solved.index).rename_axis("task_index")
    missed = meta[~meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    shared = meta[meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    return solved, summary, missed, shared


def fig_q2(solved, summary, missed, shared, tb_summary):
    """Qwen SWE task map, then paired successful steps on SWE and Terminal-Bench."""
    n_tasks = len(solved)
    fig = plt.figure(figsize=(5.5,2.25))
    bottom, height = .17, .58
    totals = fig.add_axes([.144,bottom,.044,height])
    cell_width = .217 / n_tasks
    missed_width, solved_width = len(missed)*cell_width, len(shared)*cell_width
    miss_ax = fig.add_axes([.208,bottom,missed_width,height],sharey=totals)
    gain_left = .208 + missed_width + .016
    gain_ax = fig.add_axes([gain_left,bottom,.042,height],sharey=totals)
    shared_ax = fig.add_axes([gain_left+.061,bottom,solved_width,height],sharey=totals)
    loss_ax = fig.add_axes([.518,bottom,.037,height],sharey=totals)
    n_ax = fig.add_axes([.580,bottom,.031,height],sharey=totals)
    step_ax = fig.add_axes([.630,bottom,.145,height],sharey=totals)
    tb_n_ax = fig.add_axes([.801,bottom,.031,height],sharey=totals)
    tb_step_ax = fig.add_axes([.849,bottom,.139,height],sharey=totals)
    map_axes = [totals,miss_ax,gain_ax,shared_ax,loss_ax]
    all_axes = map_axes+[n_ax,step_ax,tb_n_ax,tb_step_ax]

    fig.text(.144,.95,'(a) Qwen · SWE-bench',fontsize=7.2)
    fig.text(.580,.95,'(b) Steps to solve · Qwen',fontsize=7.2)
    map_handles = [Line2D([],[],marker='s',ls='',mfc='#525252',mec='none',ms=3.5,label='Solved'),
                   Line2D([],[],marker='x',ls='',color='#666666',ms=3.5,mew=.6,label='Lost'),
                   Patch(facecolor='#f4f4f4',edgecolor='#cccccc',lw=.3,label='Neither')]
    map_legend = fig.legend(handles=map_handles,ncol=3,loc='upper left',bbox_to_anchor=(.144,.923),
                           frameon=False,fontsize=5.9,handlelength=1.0,handletextpad=.3,columnspacing=.7,borderaxespad=0)
    right_handles = [Line2D([],[],marker='o',ms=2.5,color='#666666',lw=.7,
                            label='95% CI; n = shared solved tasks')]
    right_legend = fig.legend(handles=right_handles,ncol=1,loc='upper left',bbox_to_anchor=(.580,.923),
                             frameon=False,fontsize=5.25,handlelength=1.5,handletextpad=.4,borderaxespad=0)

    for ax,tasks,is_missed in [(miss_ax,missed,True),(shared_ax,shared,False)]:
        pixels = np.ones((len(ROWS),len(tasks),4))
        for j,p in enumerate(ROWS):
            for i,t in enumerate(tasks):
                if solved.loc[t,p]:pixels[j,i] = to_rgba(pcol(p))
                elif is_missed:pixels[j,i] = to_rgba('#f4f4f4')
        ax.imshow(pixels,interpolation='nearest',aspect='auto',extent=[-.5,len(tasks)-.5,len(ROWS)-.5,-.5])
        for x in np.arange(-.5,len(tasks)):ax.axvline(x,color='white',alpha=.45,lw=.18,zorder=2)
        for y in np.arange(.5,len(ROWS)):ax.axhline(y,color='white',lw=.55,zorder=3)
        ax.set_xlim(-.5,len(tasks)-.5)
    for j,p in enumerate(ROWS):
        lost = [i for i,t in enumerate(shared) if not solved.loc[t,p]]
        shared_ax.scatter(lost,[j]*len(lost),marker='x',s=4,color='#666666',linewidths=.4,zorder=4)
        hollow = p!='FC' and PSTYLE[p][2]
        totals.scatter(-.15,j,s=15 if p=='FC' else 10,marker='*' if p=='FC' else 'o',
                       facecolors='white' if hollow else pcol(p),edgecolors=pcol(p),linewidths=.8,
                       clip_on=False,transform=totals.get_yaxis_transform(),zorder=5)
        count = int(solved[p].sum())
        if count>solved.FC.sum():totals.axhspan(j-.44,j+.44,xmin=.02,xmax=.98,facecolor='#eaf2e5',edgecolor='none')
        totals.text(.5,j,str(count),ha='center',va='center',fontsize=6.2,
                    fontweight='bold' if count>solved.FC.sum() else 'normal',color='#333333')
        gain = int((~solved.FC&solved[p]).sum())
        loss = int((solved.FC&~solved[p]).sum())
        gain_ax.text(.5,j,f'+{gain}',ha='center',va='center',fontsize=6.2,color='#333333')
        loss_ax.text(.5,j,f'−{loss}' if loss else '0',ha='center',va='center',fontsize=6.2,color='#333333')
    for ax in map_axes+[n_ax,tb_n_ax]:
        ax.set_xticks([])
        for spine in ax.spines.values():spine.set_visible(False)
    for ax in all_axes:
        if ax is not totals:ax.tick_params(axis='y',left=False,labelleft=False)
        for boundary in [1.5,5.5,7.5,10.5,11.5]:
            ax.axhline(boundary,color='white' if ax in [miss_ax,shared_ax] else '#e5e5e5',
                       lw=1.4 if ax in [miss_ax,shared_ax] else .35,zorder=3 if ax in [miss_ax,shared_ax] else 0)
    totals.set_ylim(len(ROWS)-.4,-.6)
    totals.set_yticks(np.arange(len(ROWS)),ROWS)
    totals.tick_params(axis='y',length=0,pad=11,labelsize=6.1)
    for ax in [totals,gain_ax,loss_ax,n_ax,tb_n_ax]:ax.set_xlim(0,1)
    headers = [(totals,'Solved'),(miss_ax,f'FC missed\n{len(missed)} tasks'),
               (gain_ax,'Gained'),(shared_ax,f'FC solved\n{len(shared)} tasks'),(loss_ax,'Lost'),
               (n_ax,'n'),(step_ax,'SWE-bench'),(tb_n_ax,'n'),(tb_step_ax,'Terminal-Bench')]
    for ax,header in headers:
        ax.text(.5,1.025,header,transform=ax.transAxes,ha='center',va='bottom',fontsize=5.65)

    for ax,counts,table in [(step_ax,n_ax,summary),(tb_step_ax,tb_n_ax,tb_summary)]:
        for j,p in enumerate(ORDER):
            r = table.loc[p]
            mean,lo,hi = [(r[c]-1)*100 for c in ['ratio','ratio_lo','ratio_hi']]
            hollow = PSTYLE[p][2]
            ax.errorbar(mean,j,xerr=[[mean-lo],[hi-mean]],fmt='o',ms=3.1,color=pcol(p),
                        mfc='white' if hollow else pcol(p),mec=pcol(p),mew=.7,lw=.75,capsize=1.4,zorder=4)
            counts.text(.5,j,str(int(r.n_tasks)),ha='center',va='center',fontsize=5.9,color='#555555')
        counts.text(.5,len(ORDER),'—',ha='center',va='center',fontsize=6,color='#777777')
        ax.scatter(0,len(ORDER),marker='*',s=17,color='black',zorder=5)
        ax.axvline(0,color='#777777',ls='--',lw=.6,zorder=1)
        ax.set_xlabel('Change from FC (%)',fontsize=5.0,labelpad=2)
    step_ax.set_xlim(-23,36)
    step_ax.set_xticks([-20,0,20],['−20','0','+20'])
    tb_step_ax.set_xlim(-40,360)
    tb_step_ax.set_xticks([0,150,300],['0','+150','+300'])
    for ax in [step_ax,tb_step_ax]:
        ax.spines[['top','right','left']].set_visible(False)
        ax.tick_params(axis='x',labelsize=5.4,length=2,pad=2)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [legend.get_window_extent(renderer) for legend in [map_legend,right_legend]]
    for b in boxes:assert b.x0>=0 and b.x1<=fig.bbox.width and b.y1<=fig.bbox.height
    assert boxes[0].x1<boxes[1].x0
    for ax in [step_ax,tb_step_ax]:
        assert ax.xaxis.label.get_window_extent(renderer).y0>=0
    for row in range(len(ROWS)):
        assert np.ptp([ax.transData.transform((0,row))[1] for ax in all_axes])<1e-6
    return fig


def paper_figures_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py paper-figures", description=PAPER_FIGURES_DOC,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", choices=["all", "q1-o1", "q1-o2", "q1-qwen-overview", "q2"], default="all")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "ICLR_experiments/plotting")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--tb-outcomes", type=Path, default=ROOT / "analysis/outcomes/terminalbench_outcomes.csv")
    parser.add_argument("--tb-tasks", type=Path, default=ROOT / "task_lists/tbench_p40.json")
    parser.add_argument("--run-root", type=Path, default=ROOT, help="Root for outcome source_file paths and Harbor records")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_experiments/plotting/plots")
    parser.add_argument("--audit-dir", type=Path, help="Optional directory for Q2 values and task-order CSVs")
    parser.add_argument("--resamples", type=int, default=10000, help="Q2 and Qwen overview task-bootstrap resamples")
    parser.add_argument("--seed", type=int, default=210926, help="Bootstrap seed, reset for each policy")
    args = parser.parse_args(argv)
    if args.resamples < 1000 or args.seed < 0:
        parser.error("Use at least 1000 bootstrap resamples and a non-negative seed")
    try:
        # Read/validate requested inputs before creating any figures.
        if args.figure in ["all", "q1-o1", "q1-o2"]:
            frontiers, factors = load_q1(args.data_dir, args.figure in ["all", "q1-o2"])
        if args.figure == "q1-qwen-overview":
            overview = load_qwen_overview(args.data_dir, args.resamples, args.seed)
        if args.figure in ["all", "q2"]:
            d = load_q2_runs(args.outcomes, args.tasks)
            solved, summary, missed, shared = summarize_q2(d, args.resamples, args.seed)
            tb = load_q2_runs(args.tb_outcomes, args.tb_tasks, "terminalbench", args.run_root)
            _, tb_summary, _, _ = summarize_q2(tb, args.resamples, args.seed)
        with plt.rc_context(PAPER_STYLE):
            if args.figure == "q1-qwen-overview":
                # The plot-bank renderer draws the full 2x5 overview only; the
                # former _tokens / _success column subsets are not produced.
                fig = fig_qwen_overview(overview)
                save_figure(fig, args.output_dir, "q1_24_qwen_overview")
                plt.close(fig)
                if args.audit_dir:
                    args.audit_dir.mkdir(parents=True, exist_ok=True)
                    pd.concat(overview, names=["benchmark", "policy"]).to_csv(args.audit_dir / "q1_24_qwen_overview_values.csv")
            if args.figure in ["all", "q1-o1"]:
                fig = fig_o1(frontiers)
                save_figure(fig, args.output_dir, "q1_20_o1_frontier")
                plt.close(fig)
            if args.figure in ["all", "q1-o2"]:
                fig = fig_o2_bill(frontiers, factors)
                save_figure(fig, args.output_dir, "q1_21_o2_bill_latency")
                plt.close(fig)
        if args.figure in ["all", "q2"]:
            with plt.rc_context(Q2_STYLE):
                fig = fig_q2(solved, summary, missed, shared, tb_summary)
                save_figure(fig, args.output_dir, "q2_qwen_task_map_and_endings", dpi=300)
                plt.close(fig)
            if args.audit_dir:
                args.audit_dir.mkdir(parents=True, exist_ok=True)
                summary.to_csv(args.audit_dir / "q2_plotted_values.csv")
                tb_summary.to_csv(args.audit_dir / "q2_tb_plotted_values.csv")
                task_order = pd.DataFrame({"task": missed + shared,
                                           "block": ["FC missed"]*len(missed) + ["FC solved"]*len(shared)})
                task_order.to_csv(args.audit_dir / "q2_task_order.csv", index=False)
            print(f"Q2: {len(missed)} FC-missed + {len(shared)} FC-solved task columns; "
                  "majority >=2/3, capped and missing verdicts unresolved.")
        print(f"Wrote {args.figure} figures (PNG) to {args.output_dir}")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Input/plot error: {exc}\n")


# ============================================================================
# Plot bank: figure inputs, Figures 2-5 and the appendix explainer
# ============================================================================
ROWS = ORDER + ["FC"]
DT = dict(zip(["tr", "su-full", "su-partial", "ss", "ss-partial"], ["TR", "SU", "SU-p", "SS", "SS-p"]))
MARK = {p: MK["qwen35b"] for p in DT.values()}
FIGURES = [          # all written flat into --output-dir, PNG plus their input CSVs
    "intro_01_policy_axes_wrap",
    "q1_24_qwen_overview",
    "q1_26_knob_execution",
    "q2_qwen_task_map_only",
    "q3_policy_preferences_and_design",
    "budget_vs_total_explainer",
    "summarizer_ablation",
    "limit_rates",
    "step_comparison",
]

# ------------------------------------------------------------ inputs
# Every figure input is computed here from the tracked outcomes tables (the
# SWE-bench table carries the 2026-09-24 Qwen verdict re-evaluation) with the
# definitions of q1_frontier.py / token_cost_ledger.py / q1_knob_execution.py
# and the Q3 exports, validated to reproduce those exports to floating-point
# precision (2026-09-24). Only the audited Q3 exports in ICLR_experiments/plotting/ are read:
# their Devstral, GLM and Terminal-Bench rows are reused; the Qwen SWE-bench
# rows are recomputed.
SWE_OUTCOMES = ROOT / "analysis/outcomes/swebench_outcomes.csv"
TB_OUTCOMES = ROOT / "analysis/outcomes/terminalbench_outcomes.csv"
Q3_DATA_DIR = ROOT / "ICLR_experiments/plotting"
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
# Reviewer revisions of plot_bank.fig_qwen_overview (wide 2x5 layout):
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
    ("usage", "bill", "token usage / FC", "billed cost / FC", "left", "down"),
    ("resolve", "bill", "resolve rate (%)", "billed cost / FC", "right", "down"),
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
            if ymetric == "bill":
                ax.axhspan(1, ylim[1], color="#f1f1f1", zorder=-1)   # costlier than FC
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
            ax.set_ylabel(ylabel, labelpad=3, fontsize=12.5)
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
                                left=.052, right=.995, bottom=.085, top=.87,
                                wspace=.16, hspace=.32)
        # Cost and latency are shown relative to FC (FC = 1.0 dotted line).
        metrics = [("events", "Compressions", None),
                   ("bill", "Billed cost / FC", 1 / fc.bill),
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
        ax.set_position([pos.x0, .005, pos.width, pos.y1 - .005])
        ax.set_axis_off()
        ax.set_title("(c) Resolve, cost, and latency", loc="left", pad=8)
        ax.set_xlim(0, 11.3)
        ax.set_ylim(.3, 19.25)   # tight to the bottom rule and the depth headings
        left = 2.2
        ax.text(.02, 17.92, "Primitive", fontsize=10, va="center")
        ax.text(1.52, 17.92, "Trigger", fontsize=10, ha="center", va="center")
        for j, (depth, label) in enumerate(((.3, "Shallow (0.3)"), (.5, "Depth 0.5"), (.7, "Deep (0.7)"))):
            center = left + 3*j + 1.5
            ax.text(center, 18.93, label, ha="center", va="center", fontsize=16, fontweight="bold")
            ax.plot([left + 3*j + .08, left + 3*j + 2.92], [18.45, 18.45], color=".65", lw=.5)
            for k, label in enumerate(("RR (%)", "Cost/FC", "Lat. (s)")):
                ax.text(left + 3*j + k + .5, 17.92, label, ha="center", va="center", fontsize=10.5)
        ax.plot([0, 11.2], [17.36, 17.36], color=".35", lw=.65)
        for i, pol in enumerate(DT.values()):
            ytop = 16.66 - 3.4*i
            ax.text(.02, ytop-1, pol, color="black", fontweight="bold", fontsize=15, va="center")
            for k, budget in enumerate((10, 15, 20)):
                y = ytop-k
                g = resolve_grid[resolve_grid.policy.eq(pol) & resolve_grid.threshold_k.eq(budget)]
                assert len(g) == 3
                best, cheapest, fastest = g.resolve.max(), g.bill_vs_fc.min(), g.latency_all.min()
                ax.text(1.45, y, f"{budget}K", ha="center", fontsize=14.5, va="center")
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
                    ax.text(xlatency, y, f"{r.latency_all:.0f}", ha="center", va="center", fontsize=15.5,
                            fontweight="bold" if np.isclose(r.latency_all, fastest) else "normal")
                    ax.text(xresolve, y, f"{100*r.resolve:.1f}", ha="center", va="center", fontsize=15.5,
                            fontweight="bold" if np.isclose(r.resolve, best) else "normal")
                    ax.text(xcost, y, f"{r.bill_vs_fc:.2f}", ha="center", va="center", fontsize=15.5,
                            fontweight="bold" if np.isclose(r.bill_vs_fc, cheapest) else "normal")
            if i < 4:
                ax.plot([0, 11.2], [ytop-2.7, ytop-2.7], color=".60", lw=.65)
        ax.plot([0, 11.2], [.48, .48], color=".35", lw=.65)
        # Legend placement follows the centers of the two plot blocks.
        left_center = (grid[0, 0].get_position(fig).x0 + grid[0, 1].get_position(fig).x1) / 2
        right_center = (grid[0, 2].get_position(fig).x0 + grid[0, 2].get_position(fig).x1) / 2
        fc_handle = Line2D([], [], color=".45", ls=":", lw=.9, label="FC")
        fig.legend(handles=handles + [fc_handle], loc="upper center", ncol=6, frameon=False,
                   bbox_to_anchor=(left_center, 1.0), handlelength=1.1, columnspacing=.55, handletextpad=.3)
        winners = [Patch(facecolor=RESOLVE_HIGHLIGHT, edgecolor="none",
                         label="Highest resolve"),
                   Patch(facecolor=COST_HIGHLIGHT, edgecolor="none",
                         label="Lowest cost"),
                   Line2D([], [], linestyle="none", marker="o", markerfacecolor="none",
                          markeredgecolor=".15", markersize=9, label="Lowest latency"),
                   ]
        fig.legend(handles=winners, loc="upper center", ncol=3, frameon=False,
                   bbox_to_anchor=(right_center, 1.0), handlelength=1.4,
                   columnspacing=.9, handletextpad=.3, fontsize=13)
        # FC reference on the (c) title line, right-aligned.
        fig.text(.993, .905,
                 f"FC: {100*fc.resolve:.1f}% / 1.00× / "
                 f"{resolve_grid.loc[resolve_grid.policy.eq('FC'), 'latency_all'].iloc[0]:.0f}s",
                 ha="right", va="center", fontsize=13)
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
        totals.text(.5, j, str(count), ha='center', va='center', fontsize=6.2,
                    fontweight='bold' if count > fc_total else 'normal', color='#333333')
        gain = int((~solved.FC & solved[p]).sum())
        loss = int((solved.FC & ~solved[p]).sum())
        gain_ax.text(.5, j, f'+{gain}', ha='center', va='center', fontsize=6.2, color='#333333')
        loss_ax.text(.5, j, f'−{loss}' if loss else '0', ha='center', va='center', fontsize=6.2, color='#333333')
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
    totals.tick_params(axis='y', length=0, pad=4, labelsize=6.2)
    for ax in [totals, gain_ax, loss_ax]:
        ax.set_xlim(0, 1)
    headers = [(totals, 'Solved'), (miss_ax, f'FC missed {len(missed)} tasks'),
               (gain_ax, 'Gained'), (shared_ax, f'FC solved {len(shared)} tasks'), (loss_ax, 'Lost')]
    for ax, header in headers:
        ax.text(.5, 1.025, header, transform=ax.transAxes, ha='center', va='bottom', fontsize=6.0)
    for ax in map_axes:
        pos = ax.get_position()
        ax.set_position([.15 + (pos.x0 - .144) * 2.02, y0 + .005 * yh, pos.width * 2.02, .80 * yh])
    return map_axes


def fig_task_map(solved, missed, shared, rows=TASK_MAP_ROWS):
    """plot_bank.fig_task_map with the row list as a parameter.

    Identical drawing to the plot bank for the policy rows; `rows` may add
    the oracle row (ORACLE), drawn in its own colour. Reviewer revisions: no
    heading (goes in the caption), centred legend closer to the map, slightly
    larger fonts, one-line column headers, and no row markers except FC's,
    a black square as in Figure 2. Family separators are placed after TRC, SS-p, TRC+SS, OTRC+SS-p,
    OTRC and (when present) the oracle row.
    """
    fig = plt.figure(figsize=(5.5, 1.55))   # 1100 x 310 px at 200 dpi
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


# ------------------------------------------------------------ Appendix figures
# Per-call prompt sizes and cumulative prompt consumption, fixed paired runs.
def budget_vs_total_inputs(outcomes):
    """Read the two observed trajectories used in the appendix illustration."""
    data = pd.read_csv(outcomes, low_memory=False)
    data = data[(data.model_key == 'qwen35b') & (data.experiment_section == 'main')
                & (data.task_name == 'scikit-learn__scikit-learn-13142') & (data.run_num == 1)]
    series = []
    for cell, title, color in [('di__binf__fc', 'Full context', '#777777'),
                               ('d05__b15k__tr', 'Truncation', '#0072B2')]:
        rows = data[data.cell == cell]
        if len(rows) != 1:
            raise ValueError(f'Expected exactly one trajectory for {cell}, got {len(rows)}')
        row = rows.iloc[0]
        values = np.asarray(ast.literal_eval(row.step_prompt_tokens), dtype=float)
        if not len(values) or not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f'Invalid prompt counts for {cell}')
        if str(row.resolved).lower() != 'true':
            raise ValueError(f'The illustrated trajectory is no longer marked solved: {cell}')
        series.append((values, title, color))
        print(f'{title}: {len(values)} calls; peak {max(values):,.0f}; total {sum(values):,.0f} prompt tokens')

    return series


def fig_budget_vs_total(series):
    """Draw per-call bars, with panel labels below and statistics inside."""
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 4.5), sharex=True, sharey=True)
    max_calls = max(len(v) for v, _, _ in series)
    for i, (ax, (values, title, color)) in enumerate(zip(axes, series)):
        calls = np.arange(1, len(values) + 1)
        ax.barh(calls, values, height=.78, color=color, linewidth=0)
        ax.text(.5, -.20, f'({chr(97+i)}) {title}',
                transform=ax.transAxes, fontsize=10, ha='center', va='top')
        ax.text(.97, .97,
                f'{len(values)} calls\nPeak: {max(values)/1000:.1f}K\n'
                f'Total prompt tokens: {sum(values)/1e6:.2f}M',
                transform=ax.transAxes, fontsize=8.5, linespacing=1.5,
                ha='right', va='top',
                bbox=dict(facecolor='white', edgecolor='none', alpha=.95, pad=3))
        ax.set_xlim(0, 30000)
        ax.set_ylim(max_calls + 1, 0)
        ax.set_yticks([1, 10, 20, 30, 40, 50, max_calls])
        ax.xaxis.set_major_locator(MultipleLocator(10000))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x/1000:g}K' if x else '0'))
        ax.set_xlabel('Prompt tokens per call')
        ax.grid(axis='x', color='#e5e5e5', linewidth=.6)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
        ax.spines[['left', 'bottom']].set_color('#aaaaaa')
        ax.tick_params(length=3, color='#aaaaaa')
        if i == 1:
            ax.axvline(15000, color='#333333', linestyle=(0, (4, 3)), linewidth=.9)
            ax.text(15800, 53, '15K trigger\nthreshold', fontsize=8, va='center')
    axes[0].set_ylabel('Model call')
    fig.subplots_adjust(left=.09, right=.98, top=.97, bottom=.23, wspace=.16)
    return fig


def plot_bank_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py", description=__doc__,
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
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_experiments/plotting/plots",
                        help="Output directory; every figure (PNG) and its CSVs are written flat into it")
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
        sub = args.output_dir
        sub.mkdir(parents=True, exist_ok=True)
        with plt.rc_context(PAPER_STYLE):
            if name == "intro_01_policy_axes_wrap":
                fig = fig_intro_policy_axes()
            elif name == "step_comparison":
                summary, pairs = step_inputs(args.outcomes, args.tb_outcomes)
                write(summary, sub, "step_comparison_summary.csv", index=False)
                write(pairs, sub, "step_comparison_pairs.csv", index=False)
                fig = fig_step_comparison(summary)
            elif name == "limit_rates":
                summary, audit = limit_inputs(args.outcomes, args.tb_outcomes)
                write(summary, sub, "limit_rates_summary.csv", index=False)
                write(audit, sub, "limit_rates_runs.csv", index=False)
                fig = fig_limit_rates(summary)
            elif name == "summarizer_ablation":
                summary, audit = summarizer_inputs(args.outcomes)
                write(summary, sub, "summarizer_ablation_summary.csv", index=False)
                write(audit, sub, "summarizer_ablation_runs.csv", index=False)
                fig = fig_summarizer_ablation(summary)
            elif name == "budget_vs_total_explainer":
                series = budget_vs_total_inputs(args.outcomes)
                calls = pd.DataFrame([
                    {"policy": title, "call": call, "prompt_tokens": int(tokens)}
                    for values, title, _ in series
                    for call, tokens in enumerate(values, 1)
                ])
                write(calls, sub, "budget_vs_total_explainer_calls.csv", index=False)
                fig = fig_budget_vs_total(series)
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
                save_figure(fig, sub, name, dpi=300 if name.startswith(("intro", "q3", "budget_vs_total")) else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {sub / name}.png", flush=True)


# ============================================================================
# Appendix task maps (formerly appendix_task_map.py)
# ============================================================================
TASK_MAP_DOC = """Appendix: the task-coverage map (plot_bank.fig_task_map, "Figure 4")
at every depth and trigger threshold, Qwen on SWE-bench.

For each (threshold, depth) setting the figure shows, per policy, the tasks
it solves among those FC missed and those FC solved, with the totals,
gains and losses relative to FC. Definitions follow paper_figures.load_q2_runs:
three attempts per task and policy, a task counts as solved when at least
two attempts are resolved, and attempts at or beyond the 1500 s harness cap
are unresolved.

Settings, cells and cohorts are those of the knob-overview tool (formerly appendix_knob_overview.py): the
primary setting (D=0.5, primary threshold) comes from the main track, every
other setting from the ablation track on ABL-25; depth-invariant policies
repeat their D=0.5 cell at D=0.3 and 0.7. By default the primary setting is
also restricted to ABL-25 so the nine maps share a cohort; `--primary-cohort
full` draws it on P100 instead, which is the paper's Figure 4.

Layout changes from the paper figure: no title and no policy markers next
to the row labels, no family rules in the count columns; the "FC missed"
map sits next to "Gained" and, after a wider gap, the "FC solved" map next
to "Lost".

Run from the repository root:
    venv/bin/python ICLR_experiments/plotting/plot_bank.py task-map
    venv/bin/python ICLR_experiments/plotting/plot_bank.py task-map --settings 0.5:primary --primary-cohort full
Outputs go to ICLR_experiments/plotting/plots/ as
qwen35b_swe_task_map_<threshold>_D<depth>.png plus a CSV of the counts.
"""
FAMILY_BOUNDARIES = [1.5, 5.5, 7.5, 10.5, 11.5]     # between rule / LLM / stacked / step / OTRC / FC


def solved_table(df):
    """Task x policy booleans: at least two of three uncapped resolved attempts."""
    counts = df.groupby(["task", "policy"]).size().unstack()
    if not counts.eq(3).all().all():
        bad = counts[counts.ne(3).any(axis=1)].index.tolist()[:5]
        raise ValueError(f"expected exactly three attempts per task and policy; see {bad}")
    d = df.assign(ok=df.res.gt(0) & ~df.capped)
    return d.groupby(["task", "policy"]).ok.sum().unstack().loc[:, ROWS].ge(2)


def order_tasks(solved):
    """FC-missed and FC-solved task columns, by descending policy coverage then ID."""
    coverage = solved[ORDER].sum(axis=1)
    key = lambda t: (-coverage[t], t)
    missed = sorted(solved.index[~solved.FC], key=key)
    shared = sorted(solved.index[solved.FC], key=key)
    return missed, shared


def fig_appendix_task_map(solved, missed, shared, heading=None):
    """Port of plot_bank.fig_task_map without title, row markers or
    family rules in the count columns, and with the FC-missed/Gained and
    FC-solved/Lost pairs grouped. `heading` is accepted but not drawn."""
    fig = plt.figure(figsize=(5.5, 2.25))
    bottom, height = .035, .80
    left, right = .15, .98
    w_totals, w_gain, w_loss = .09, .07, .065
    gap, gap_small, gap_big = .02, .003, .05
    w_maps = right - left - (w_totals + w_gain + w_loss + gap + 2 * gap_small + gap_big)
    n_cols = max(len(missed) + len(shared), 1)
    w_missed = w_maps * len(missed) / n_cols
    w_shared = w_maps * len(shared) / n_cols
    x = left
    totals = fig.add_axes([x, bottom, w_totals, height]); x += w_totals + gap
    miss_ax = fig.add_axes([x, bottom, w_missed, height], sharey=totals); x += w_missed + gap_small
    gain_ax = fig.add_axes([x, bottom, w_gain, height], sharey=totals); x += w_gain + gap_big
    shared_ax = fig.add_axes([x, bottom, w_shared, height], sharey=totals); x += w_shared + gap_small
    loss_ax = fig.add_axes([x, bottom, w_loss, height], sharey=totals)
    map_axes = [totals, miss_ax, gain_ax, shared_ax, loss_ax]

    # No title: the file name carries model, benchmark, threshold and depth.
    handles = [Line2D([], [], marker='s', ls='', mfc='#525252', mec='none', ms=3.5, label='Solved'),
               Line2D([], [], marker='x', ls='', color='#666666', ms=3.5, mew=.6, label='Lost'),
               Patch(facecolor='#f4f4f4', edgecolor='#cccccc', lw=.3, label='Neither')]
    fig.legend(handles=handles, ncol=3, loc='upper left', bbox_to_anchor=(left, .993),
               frameon=False, fontsize=5.9, handlelength=1, handletextpad=.3,
               columnspacing=.7, borderaxespad=0)

    for ax, tasks, is_missed in [(miss_ax, missed, True), (shared_ax, shared, False)]:
        pixels = np.ones((len(ROWS), max(len(tasks), 1), 4))
        for j, p in enumerate(ROWS):
            for i, t in enumerate(tasks):
                if solved.loc[t, p]:
                    pixels[j, i] = to_rgba(pcol(p))
                elif is_missed:
                    pixels[j, i] = to_rgba('#f4f4f4')
        if tasks:
            ax.imshow(pixels, interpolation='nearest', aspect='auto',
                      extent=[-.5, len(tasks) - .5, len(ROWS) - .5, -.5])
            for xx in np.arange(-.5, len(tasks)):
                ax.axvline(xx, color='white', alpha=.45, lw=.18, zorder=2)
            for yy in np.arange(.5, len(ROWS)):
                ax.axhline(yy, color='white', lw=.55, zorder=3)
        ax.set_xlim(-.5, max(len(tasks), 1) - .5)
    fc_count = int(solved.FC.sum())
    for j, p in enumerate(ROWS):
        lost = [i for i, t in enumerate(shared) if not solved.loc[t, p]]
        shared_ax.scatter(lost, [j] * len(lost), marker='x', s=4, color='#666666', linewidths=.4, zorder=4)
        count = int(solved[p].sum())
        if count > fc_count:
            totals.axhspan(j - .44, j + .44, xmin=.02, xmax=.98, facecolor='#eaf2e5', edgecolor='none')
        totals.text(.5, j, str(count), ha='center', va='center', fontsize=6.2,
                    fontweight='bold' if count > fc_count else 'normal', color='#333333')
        gain = int((~solved.FC & solved[p]).sum())
        loss = int((solved.FC & ~solved[p]).sum())
        gain_ax.text(.5, j, f'+{gain}', ha='center', va='center', fontsize=6.2, color='#333333')
        loss_ax.text(.5, j, f'−{loss}' if loss else '0', ha='center', va='center', fontsize=6.2, color='#333333')
    for ax in map_axes:
        ax.set_xticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        if ax is not totals:
            ax.tick_params(axis='y', left=False, labelleft=False)
        if ax in [miss_ax, shared_ax]:      # family separators only inside the maps
            for boundary in FAMILY_BOUNDARIES:
                ax.axhline(boundary, color='white', lw=1.4, zorder=3)
    totals.set_ylim(len(ROWS) - .4, -.6)
    totals.set_yticks(np.arange(len(ROWS)), ROWS)
    totals.tick_params(axis='y', length=0, pad=4, labelsize=6.1)
    for ax in [totals, gain_ax, loss_ax]:
        ax.set_xlim(0, 1)
    headers = [(totals, 'Solved'), (miss_ax, f'FC missed\n{len(missed)} tasks'), (gain_ax, 'Gained'),
               (shared_ax, f'FC solved\n{len(shared)} tasks'), (loss_ax, 'Lost')]
    for ax, header in headers:
        ax.text(.5, 1.025, header, transform=ax.transAxes, ha='center', va='bottom', fontsize=5.65)
    return fig


def appendix_task_map_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py task-map", description=TASK_MAP_DOC,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--settings", nargs="+", default=[f"{d}:{l}" for l in LEVELS for d in DEPTHS],
                        help="depth:level pairs, depth = fraction removed")
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' reproduces Figure 4")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "ICLR_experiments/plotting/plots")
    args = parser.parse_args(argv)
    settings = parse_settings(args.settings)
    runs, _ = load_runs("swebench", args.model, args.outcomes)
    budgets = budget_levels(runs)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for depth, level in settings:
        primary = (depth == 0.5 and level == "primary")
        cohort = args.primary_cohort if primary else "ablation"
        tasks, cohort_label = read_tasks("swebench", cohort)
        df = panel_runs(runs, tasks, depth, level, budgets)
        solved = solved_table(df)
        missed, shared = order_tasks(solved)
        budget_k = budgets[level] // 1000
        heading = f"{MODEL_NAMES[args.model]} · SWE-bench · {level} threshold ({budget_k}K) · D={depth}"
        name = f"{args.model}_swe_task_map_{level}_D{depth}" + ("_fullcohort" if cohort == "full" else "")
        with plt.rc_context(PAPER_STYLE):
            fig = fig_appendix_task_map(solved, missed, shared, heading)
            try:
                fig.savefig(args.output_dir / f"{name}.png", dpi=300)
            finally:
                plt.close(fig)
        for p in ROWS:
            records.append(dict(model=args.model, threshold=level, budget=budgets[level], depth_removed=depth,
                                cohort=cohort_label, policy=p, solved=int(solved[p].sum()),
                                gained=int((~solved.FC & solved[p]).sum()),
                                lost=int((solved.FC & ~solved[p]).sum()),
                                fc_solved=int(solved.FC.sum()), n_tasks=len(solved)))
        print(f"Wrote {args.output_dir / name}.png  ({cohort_label}: FC solved {int(solved.FC.sum())}/{len(solved)})")
    table = pd.DataFrame(records)
    out = args.output_dir / f"{args.model}_swe_task_map_counts.csv"
    table.to_csv(out, index=False)
    print(f"Wrote {out}")


# ============================================================================
# Appendix task maps, re-evaluated (formerly appendix_task_map_reeval.py)
# ============================================================================
TASK_MAP_REEVAL_DOC = """Appendix: the Figure 4 task-coverage map at every depth and trigger
threshold, from the re-evaluated verdicts, drawn by the plot bank.

One figure per trigger threshold (tight / primary / loose), Qwen on
SWE-bench, with the three depths stacked as bands headed "D = 0.3" etc. on
the left and the Solved / Lost / Neither legend once at the top. Each band
shows per policy which tasks it solves among those FC missed and those FC
solved, with the totals, gains and losses relative to FC, plus the Oracle
row of Figure 4 (a task counts as solved when any of the thirteen policies
solves it). Definitions follow the task-map tool (formerly appendix_task_map.py): three attempts per
task and policy, solved = at least two resolved attempts, attempts at or
beyond the 1500 s harness cap count as unresolved.

Settings, cells and cohorts are those of the knob-overview tool (formerly appendix_knob_overview.py): the
primary setting (D = 0.5, primary threshold) comes from the main track,
every other setting from the ablation track; depth-invariant policies repeat
their D = 0.5 cell at D = 0.3 and 0.7. By default every setting, including
the primary one, is restricted to ABL-25 so the maps share a cohort
(`--primary-cohort full` draws the primary setting on P100, i.e. Figure 4).
`resolved` is taken from --outcomes, by default the table carrying the
2026-09-23/24 Qwen re-evaluation.

The drawing is plot_bank.draw_task_map, so the layout, colours
(purple OTRC family, teal Oracle), FC square and legend are exactly those
of Figure 4.

Outputs go to ICLR_experiments/plotting/plots/ as
qwen35b_swe_task_map_<threshold>.png plus qwen35b_swe_task_map_counts.csv.

Usage (from the repository root):
    venv/bin/python ICLR_experiments/plotting/plot_bank.py task-map-reeval
    venv/bin/python ICLR_experiments/plotting/plot_bank.py task-map-reeval --thresholds tight
"""
TASK_MAP_REEVAL_DIR = ROOT / "ICLR_experiments/plotting/plots"
LEGEND_IN = 0.3       # legend band at the top, inches
MAP_IN = 1.55         # one map band = the Figure 4 figure height, inches


def fig_task_map_stack(blocks):
    """`blocks` = [(depth, solved, missed, shared)] top to bottom: one Figure 4
    map per band, "D = <depth>" at the left of each band, legend on top."""
    height = LEGEND_IN + MAP_IN * len(blocks)
    fig = plt.figure(figsize=(5.5, height))
    task_map_legend(fig, y=.995)
    band_h = MAP_IN / height
    for i, (depth, solved, missed, shared) in enumerate(blocks):
        y0 = 1 - LEGEND_IN / height - band_h * (i + 1)
        draw_task_map(fig, solved, missed, shared, band=(y0, band_h))
        fig.text(.012, y0 + band_h * (.035 + .40), f"D = {depth}", rotation=90,
                 ha="center", va="center", fontsize=8)
    return fig


def appendix_task_map_reeval_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py task-map-reeval", description=TASK_MAP_REEVAL_DOC,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=SWE_OUTCOMES,
                        help="SWE-bench outcomes table (carries the re-evaluation)")
    parser.add_argument("--thresholds", nargs="+", choices=LEVELS, default=LEVELS)
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' is Figure 4's")
    parser.add_argument("--output-dir", type=Path, default=TASK_MAP_REEVAL_DIR)
    args = parser.parse_args(argv)
    if not args.outcomes.is_file():
        parser.error(f"missing {args.outcomes}")
    runs, _ = load_runs("swebench", args.model, args.outcomes)
    budgets = budget_levels(runs)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for level in args.thresholds:
        blocks = []
        for depth in DEPTHS:
            primary = (depth == 0.5 and level == "primary")
            cohort = args.primary_cohort if primary else "ablation"
            tasks, cohort_label = read_tasks("swebench", cohort)
            df = panel_runs(runs, tasks, depth, level, budgets)
            solved = solved_table(df)
            solved[ORACLE] = solved[ROWS].any(axis=1)
            solved = solved.loc[:, TASK_MAP_ROWS]
            missed, shared = order_tasks(solved)
            blocks.append((depth, solved, missed, shared))
            for p in TASK_MAP_ROWS:
                records.append(dict(model=args.model, threshold=level, budget=budgets[level],
                                    depth_removed=depth, cohort=cohort_label, policy=p,
                                    solved=int(solved[p].sum()),
                                    gained=int((~solved.FC & solved[p]).sum()),
                                    lost=int((solved.FC & ~solved[p]).sum()),
                                    fc_solved=int(solved.FC.sum()), n_tasks=len(solved)))
            print(f"  {level} ({budgets[level] // 1000}K) D={depth}: {cohort_label}, FC solved "
                  f"{int(solved.FC.sum())}/{len(solved)}, oracle {int(solved[ORACLE].sum())}", flush=True)
        name = f"{args.model}_swe_task_map_{level}"
        with plt.rc_context(PAPER_STYLE):
            fig = fig_task_map_stack(blocks)
            try:
                fig.savefig(args.output_dir / f"{name}.png", dpi=300)
            finally:
                plt.close(fig)
        print(f"Wrote {args.output_dir / name}.png", flush=True)
    out = args.output_dir / f"{args.model}_swe_task_map_counts.csv"
    pd.DataFrame(records).to_csv(out, index=False)
    print(f"Wrote {out}")


# ============================================================================
# Appendix depth / trigger overviews, re-evaluated (formerly appendix_depth_trigger_ablation_reeval.py)
# ============================================================================
DEPTH_TRIGGER_REEVAL_DOC = """Appendix: Figure 2 at every depth and trigger threshold, from the
re-evaluated verdicts, in the Figure 2 layout of the plot bank.

Figure 2 (q1_24_qwen_overview) fixes depth 0.5 and the primary trigger
threshold. This script draws the same five panels (success, latency and
billed cost against token usage, then billed cost and latency against
resolve rate) for the other (depth, threshold) settings, one figure per
model, benchmark and threshold with that threshold's depths as rows:

    <model>_<swe|tb>_<tight|primary|loose>.png

The rows are headed "D = 0.3" etc. (D = fraction removed at each
compression event). For Qwen the primary threshold figure has the D = 0.3
and D = 0.7 rows only (Figure 2 shows 0.5); Devstral and GLM, which have no
main figure, get all three rows. Terminal-Bench is drawn for Qwen only.

Data and definitions follow plot_bank.py: attempts come from
appendix_knob_overview.load_runs / panel_runs (primary setting from the main
track, every other setting from the ablation track; depth-invariant
policies repeat their depth-0.5 cell at 0.3 / 0.7; FC and OTRC are the
budget-free references), all restricted to the ablation cohort (ABL-25 on
SWE-bench, TB-15 on Terminal-Bench) so the settings are comparable, and the
statistics are plot_bank.q1_frontier (q1_frontier.py's paired
task bootstrap, seed 0, B=5000). `resolved` is taken from --outcomes, by
default the table carrying the 2026-09-23/24 Qwen re-evaluation. The drawing
is plot_bank.draw_overview_rows, so the panels, arrows, markers
and colours are exactly those of Figure 2.

Outputs go to ICLR_experiments/plotting/plots/ with
reeval_<model>_values[_swebench].csv holding every plotted number.

Usage (from the repository root):
    venv/bin/python ICLR_experiments/plotting/plot_bank.py depth-trigger-reeval
    venv/bin/python ICLR_experiments/plotting/plot_bank.py depth-trigger-reeval --models qwen35b
"""
DEPTH_TRIGGER_REEVAL_DIR = ROOT / "ICLR_experiments/plotting/plots"
SHORT = {"swebench": "swe", "terminalbench": "tb"}
# Per model: benchmarks drawn, and whether the (0.5, primary) setting (Figure 2
# for Qwen) is included in the primary-threshold figure.
MODEL_SETUP = {
    "qwen35b": dict(benchmarks=["swebench", "terminalbench"], include_primary=False),
    "devstral24b": dict(benchmarks=["swebench"], include_primary=True),
    "glm47flash": dict(benchmarks=["swebench"], include_primary=True),
}


def threshold_figure(blocks):
    """One threshold: its (depth, frame) rows in the Figure 2 layout."""
    fig, axes = overview_figure(len(blocks))
    draw_overview_rows(axes, [(f"D = {depth}", frame) for depth, frame in blocks])
    overview_legend(fig)
    return fig


def appendix_depth_trigger_reeval_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py depth-trigger-reeval", description=DEPTH_TRIGGER_REEVAL_DOC,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outcomes", type=Path, default=SWE_OUTCOMES,
                        help="SWE-bench outcomes table (carries the re-evaluation)")
    parser.add_argument("--tb-outcomes", type=Path, default=TB_OUTCOMES)
    parser.add_argument("--output-dir", type=Path, default=DEPTH_TRIGGER_REEVAL_DIR)
    parser.add_argument("--models", nargs="+", choices=list(MODEL_SETUP), default=list(MODEL_SETUP))
    parser.add_argument("--B", type=int, default=5000, help="paired bootstrap resamples")
    args = parser.parse_args(argv)
    if not args.outcomes.is_file():
        parser.error(f"missing {args.outcomes}")
    paths = {"swebench": args.outcomes, "terminalbench": args.tb_outcomes}
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for model in args.models:
        setup = MODEL_SETUP[model]
        benchmarks = [b for b, _ in BENCHMARKS if b in setup["benchmarks"]]
        runs, budgets, exports = {}, {}, []
        for benchmark in benchmarks:
            runs[benchmark], dropped = load_runs(benchmark, model, paths[benchmark])
            budgets[benchmark] = budget_levels(runs[benchmark])
            print(f"{model}/{benchmark}: {len(runs[benchmark])} attempts, {dropped} dropped "
                  f"(<2 model calls); budgets {budgets[benchmark]}", flush=True)
        for benchmark in benchmarks:
            tasks, cohort = read_tasks(benchmark, "ablation")
            for level in LEVELS:
                blocks = []
                for depth in DEPTHS:
                    if (depth, level) == (0.5, "primary") and not setup["include_primary"]:
                        continue
                    df = panel_runs(runs[benchmark], tasks, depth, level, budgets[benchmark])
                    frame = q1_frontier(df, B=args.B)
                    blocks.append((depth, frame))
                    export = frame.reset_index()
                    export.insert(0, "benchmark", benchmark)
                    export.insert(1, "depth_removed", depth)
                    export.insert(2, "threshold", level)
                    export.insert(3, "budget", budgets[benchmark][level])
                    export.insert(4, "cohort", cohort)
                    exports.append(export)
                    print(f"  {benchmark} {level} ({budgets[benchmark][level] // 1000}K) D={depth}: "
                          f"FC resolve {frame.loc['FC', 'resolve']:.1f}% on {cohort}", flush=True)
                name = f"{model}_{SHORT[benchmark]}_{level}"
                with plt.rc_context(PAPER_STYLE):
                    fig = threshold_figure(blocks)
                    try:
                        fig.savefig(args.output_dir / f"{name}.png", dpi=200)
                    finally:
                        plt.close(fig)
                print(f"Wrote {args.output_dir / name}.png", flush=True)
        out = args.output_dir / f"reeval_{model}_values.csv"
        if len(benchmarks) < 2:
            out = out.with_name(out.stem + "_" + "_".join(benchmarks) + ".csv")
        pd.concat(exports, ignore_index=True).to_csv(out, index=False)
        print(f"Wrote {out}", flush=True)


# ============================================================================
# Budget-vs-total explainer entry point (formerly budget_vs_total_explainer.py)
# ============================================================================
BUDGET_VS_TOTAL_DOC = """Compatibility entry point for the appendix plot in plot_bank.py.

Defaults to ICLR_experiments/plotting/plots/; accepts --outcomes and --output-dir.
"""
def budget_vs_total_main(argv=None):
    parser = argparse.ArgumentParser(prog="plot_bank.py budget-vs-total", description=BUDGET_VS_TOTAL_DOC)
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_experiments/plotting/plots")
    args = parser.parse_args(argv)
    series = budget_vs_total_inputs(args.outcomes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(PAPER_STYLE):
        fig = fig_budget_vs_total(series)
        try:
            save_figure(fig, args.output_dir, "budget_vs_total_explainer", dpi=300)
        finally:
            plt.close(fig)


# ============================================================================
# Command-line dispatcher
# ============================================================================
TOOLS = {
    "intro-fig": intro_fig_main,
    "paper-figures": paper_figures_main,
    "knob-overview": knob_overview_main,
    "task-map": appendix_task_map_main,
    "task-map-reeval": appendix_task_map_reeval_main,
    "depth-trigger-reeval": appendix_depth_trigger_reeval_main,
    "budget-vs-total": budget_vs_total_main,
}


def main(argv=None):
    """`<tool> [options]` runs a former companion script; anything else is
    the plot bank's own command line (see plot_bank_main)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in TOOLS:
        return TOOLS[argv[0]](argv[1:])
    return plot_bank_main(argv)


if __name__ == "__main__":
    main()
