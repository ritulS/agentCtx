"""Appendix: Figure 2 at every depth and trigger threshold, from the
re-evaluated verdicts, in the Figure 2 layout of paper_figures_reeval.py.

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

Data and definitions follow paper_figures_reeval.py: attempts come from
appendix_knob_overview.load_runs / panel_runs (primary setting from the main
track, every other setting from the ablation track; depth-invariant
policies repeat their depth-0.5 cell at 0.3 / 0.7; FC and OTRC are the
budget-free references), all restricted to the ablation cohort (ABL-25 on
SWE-bench, TB-15 on Terminal-Bench) so the settings are comparable, and the
statistics are paper_figures_reeval.q1_frontier (q1_frontier.py's paired
task bootstrap, seed 0, B=5000). `resolved` is taken from --outcomes, by
default the table carrying the 2026-09-23/24 Qwen re-evaluation. The drawing
is paper_figures_reeval.draw_overview_rows, so the panels, arrows, markers
and colours are exactly those of Figure 2.

Outputs go to ICLR_analysis/plots/appendix/depth_trigger_ablation/ with
reeval_<model>_values[_swebench].csv holding every plotted number.

Usage (from the repository root):
    venv/bin/python ICLR_analysis/appendix_depth_trigger_ablation_reeval.py
    venv/bin/python ICLR_analysis/appendix_depth_trigger_ablation_reeval.py --models qwen35b
"""
from pathlib import Path
import argparse

import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from .appendix_knob_overview import (load_runs, budget_levels, read_tasks, panel_runs,
                                         MODEL_NAMES, LEVELS, DEPTHS, BENCHMARKS)
    from .paper_figures_reeval import (q1_frontier, draw_overview_rows, overview_legend,
                                       overview_figure, PAPER_STYLE, REEVAL_OUTCOMES, TB_OUTCOMES)
except ImportError:
    from appendix_knob_overview import (load_runs, budget_levels, read_tasks, panel_runs,
                                        MODEL_NAMES, LEVELS, DEPTHS, BENCHMARKS)
    from paper_figures_reeval import (q1_frontier, draw_overview_rows, overview_legend,
                                      overview_figure, PAPER_STYLE, REEVAL_OUTCOMES, TB_OUTCOMES)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "ICLR_analysis/plots/appendix/depth_trigger_ablation"
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outcomes", type=Path, default=REEVAL_OUTCOMES,
                        help="SWE-bench outcomes table (default: the re-evaluated copy)")
    parser.add_argument("--tb-outcomes", type=Path, default=TB_OUTCOMES)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
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


if __name__ == "__main__":
    main()
