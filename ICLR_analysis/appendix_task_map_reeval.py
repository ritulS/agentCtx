"""Appendix: the Figure 4 task-coverage map at every depth and trigger
threshold, from the re-evaluated verdicts, drawn by paper_figures_reeval.py.

One figure per trigger threshold (tight / primary / loose), Qwen on
SWE-bench, with the three depths stacked as bands headed "D = 0.3" etc. on
the left and the Solved / Lost / Neither legend once at the top. Each band
shows per policy which tasks it solves among those FC missed and those FC
solved, with the totals, gains and losses relative to FC, plus the Oracle
row of Figure 4 (a task counts as solved when any of the thirteen policies
solves it). Definitions follow appendix_task_map.py: three attempts per
task and policy, solved = at least two resolved attempts, attempts at or
beyond the 1500 s harness cap count as unresolved.

Settings, cells and cohorts are those of appendix_knob_overview.py: the
primary setting (D = 0.5, primary threshold) comes from the main track,
every other setting from the ablation track; depth-invariant policies repeat
their D = 0.5 cell at D = 0.3 and 0.7. By default every setting, including
the primary one, is restricted to ABL-25 so the maps share a cohort
(`--primary-cohort full` draws the primary setting on P100, i.e. Figure 4).
`resolved` is taken from --outcomes, by default the table carrying the
2026-09-23/24 Qwen re-evaluation.

The drawing is paper_figures_reeval.draw_task_map, so the layout, colours
(purple OTRC family, teal Oracle), FC square and legend are exactly those
of Figure 4.

Outputs go to ICLR_analysis/plots/appendix/task_specificity/ as
qwen35b_swe_task_map_<threshold>.png plus qwen35b_swe_task_map_counts.csv.

Usage (from the repository root):
    venv/bin/python ICLR_analysis/appendix_task_map_reeval.py
    venv/bin/python ICLR_analysis/appendix_task_map_reeval.py --thresholds tight
"""
from pathlib import Path
import argparse

import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from .appendix_knob_overview import (MODEL_NAMES, DEPTHS, LEVELS, load_runs, budget_levels,
                                         read_tasks, panel_runs)
    from .appendix_task_map import solved_table, order_tasks, ROWS
    from .paper_figures_reeval import (draw_task_map, task_map_legend, ORACLE, TASK_MAP_ROWS,
                                       PAPER_STYLE, REEVAL_OUTCOMES)
except ImportError:
    from appendix_knob_overview import (MODEL_NAMES, DEPTHS, LEVELS, load_runs, budget_levels,
                                        read_tasks, panel_runs)
    from appendix_task_map import solved_table, order_tasks, ROWS
    from paper_figures_reeval import (draw_task_map, task_map_legend, ORACLE, TASK_MAP_ROWS,
                                      PAPER_STYLE, REEVAL_OUTCOMES)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "ICLR_analysis/plots/appendix/task_specificity"
LEGEND_IN = 0.3       # legend band at the top, inches
MAP_IN = 2.25         # one map band = the Figure 4 figure height, inches


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="qwen35b", choices=list(MODEL_NAMES))
    parser.add_argument("--outcomes", type=Path, default=REEVAL_OUTCOMES,
                        help="SWE-bench outcomes table (default: the re-evaluated copy)")
    parser.add_argument("--thresholds", nargs="+", choices=LEVELS, default=LEVELS)
    parser.add_argument("--primary-cohort", choices=["ablation", "full"], default="ablation",
                        help="cohort for the (0.5, primary) setting; 'full' is Figure 4's")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
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


if __name__ == "__main__":
    main()
