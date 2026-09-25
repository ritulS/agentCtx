"""Selected ICLR plot bank: five maintained figure renderers.

Run `venv/bin/python ICLR_analysis/Iclr_plot_bank.py` to generate all figures.
Use --list or --help for selection and input/output options.
Shared visual conventions live in plot_style.py; data definitions and usage
are documented in Iclr_plot_bank.md. No files are written on import.
"""
from pathlib import Path
import argparse
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
    from .paper_figures import load_qwen_overview, load_q2_runs
    from .intro_fig import make_wrap_figure as fig_intro_policy_axes
except ImportError:
    from plot_style import (PAPER_STYLE, KNOB_STYLE, ORDER, MK, PSTYLE, PDARK, RESOLVE_HIGHLIGHT, COST_HIGHLIGHT,
                            PLIGHT, pcol, pmark, prim_handles, save_figure)
    from paper_figures import load_qwen_overview, load_q2_runs
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

# ------------------------------------------------------------ Figure 2
# Reviewer revisions of Iclr_plot_bank.fig_qwen_overview (wide 2x5 layout):
# no "Qwen" heading, larger fonts and markers, black arrows marking the
# better direction of each axis, both axes start at 0, no y=x guide in the
# third column, one benchmark heading per row (no panel titles), FC is a black
# square instead of a star.
FC_MARKER = "s"


def overview_handles():
    handles = [Line2D([], [], marker=FC_MARKER, ls="", color="black", ms=8, label="FC")]
    for policy in ORDER:
        c, open_ = pcol(policy), PSTYLE[policy][2]
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", nargs="+", choices=["all", *FIGURES], default=["all"])
    parser.add_argument("--list", action="store_true", help="List the selected figure names")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "ICLR_analysis")
    parser.add_argument("--q3-data-dir", type=Path, default=ROOT / "ICLR_analysis/plots/q3")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots",
                        help="Output root; preserves setup/, q1/ and q3/ subdirectories")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(FIGURES))
        return
    selected = list(FIGURES) if "all" in args.figure else list(dict.fromkeys(args.figure))
    for name in selected:
        with plt.rc_context(PAPER_STYLE):
            if name == "intro_01_policy_axes_wrap":
                fig = fig_intro_policy_axes()
            elif name == "q1_24_qwen_overview":
                fig = fig_qwen_overview(load_qwen_overview(args.data_dir))
            elif name == "q1_26_knob_execution":
                summary = pd.read_csv(args.data_dir / "q1_knob_execution.csv")
                grid = pd.read_csv(args.data_dir / "q1_knob_execution_resolve_grid.csv")
                if len(grid) != 46 or grid.duplicated(["policy", "threshold_k", "depth_removed"]).any():
                    raise ValueError("Knob grid must contain 45 distinct settings plus FC")
                fig = fig_knob_execution(summary, grid)
            elif name == "q2_qwen_task_map_only":
                runs = load_q2_runs(args.outcomes, args.tasks)
                solved = runs.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].ge(2)
                solved[ORACLE] = solved[ROWS].any(axis=1)
                solved = solved.loc[:, TASK_MAP_ROWS]
                missed = sorted(solved.index[~solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                shared = sorted(solved.index[solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                fig = fig_task_map(solved, missed, shared)
            else:
                values = pd.read_csv(args.q3_data_dir / "q3_combined_policy_values.csv")
                contrasts = pd.read_csv(args.q3_data_dir / "q3_combined_design_contrasts.csv")
                if values.duplicated(["benchmark", "model_key", "policy", "metric"]).any():
                    raise ValueError("Duplicate Q3 policy values")
                if contrasts.duplicated(["benchmark", "model_key", "p", "q"]).any():
                    raise ValueError("Duplicate Q3 design contrasts")
                fig = fig_policy_preferences(values, contrasts)
            try:
                save_figure(fig, args.output_dir / FIGURES[name], name,
                            dpi=300 if name.startswith(("intro", "q3")) else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {args.output_dir / FIGURES[name] / name}.{{pdf,png}}", flush=True)


if __name__ == "__main__":
    main()
