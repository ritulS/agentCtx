"""Appendix: the task-coverage map (Iclr_plot_bank.fig_task_map, "Figure 4")
at every depth and trigger threshold, Qwen on SWE-bench.

For each (threshold, depth) setting the figure shows, per policy, the tasks
it solves among those FC missed and those FC solved, with the totals,
gains and losses relative to FC. Definitions follow paper_figures.load_q2_runs:
three attempts per task and policy, a task counts as solved when at least
two attempts are resolved, and attempts at or beyond the 1500 s harness cap
are unresolved.

Settings, cells and cohorts are those of appendix_knob_overview.py: the
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
    venv/bin/python ICLR_analysis/appendix_task_map.py
    venv/bin/python ICLR_analysis/appendix_task_map.py --settings 0.5:primary --primary-cohort full
Outputs go to ICLR_analysis/plots/appendix/task_specificity/ as
qwen35b_swe_task_map_<threshold>_D<depth>.png plus a CSV of the counts.
"""
from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

try:
    from .plot_style import PAPER_STYLE, ORDER, pcol
    from .appendix_knob_overview import (MODEL_NAMES, DEPTHS, LEVELS, load_runs, budget_levels,
                                         read_tasks, panel_runs, parse_settings)
except ImportError:
    from plot_style import PAPER_STYLE, ORDER, pcol
    from appendix_knob_overview import (MODEL_NAMES, DEPTHS, LEVELS, load_runs, budget_levels,
                                        read_tasks, panel_runs, parse_settings)

ROOT = Path(__file__).resolve().parent.parent
ROWS = ORDER + ["FC"]
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


def fig_task_map(solved, missed, shared, heading=None):
    """Port of Iclr_plot_bank.fig_task_map without title, row markers or
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--settings", nargs="+", default=[f"{d}:{l}" for l in LEVELS for d in DEPTHS],
                        help="depth:level pairs, depth = fraction removed")
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' reproduces Figure 4")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "ICLR_analysis/plots/appendix/task_specificity")
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
            fig = fig_task_map(solved, missed, shared, heading)
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


if __name__ == "__main__":
    main()
