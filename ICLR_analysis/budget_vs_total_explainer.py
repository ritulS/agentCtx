#!/usr/bin/env python3
"""Compatibility entry point for the appendix plot in Iclr_plot_bank.py.

Defaults to the paper figure directory; accepts --outcomes and --output-dir.
"""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
try:
    from .Iclr_plot_bank import budget_vs_total_inputs, fig_budget_vs_total
    from .plot_style import PAPER_STYLE, save_figure
except ImportError:
    from Iclr_plot_bank import budget_vs_total_inputs, fig_budget_vs_total
    from plot_style import PAPER_STYLE, save_figure

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "paper_sections_ICLR/figures")
    args = parser.parse_args()
    series = budget_vs_total_inputs(args.outcomes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(PAPER_STYLE):
        fig = fig_budget_vs_total(series)
        try:
            save_figure(fig, args.output_dir, "budget_vs_total_explainer", dpi=300)
        finally:
            plt.close(fig)


if __name__ == "__main__":
    main()
