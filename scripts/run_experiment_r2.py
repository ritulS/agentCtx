#!/usr/bin/env python3
"""Run one experiment cell in the r2 (post-ICLR extension) results tree.

Same thin adapter as ``run_experiment_iclr.py`` — it only overrides the
runner's result directory — but writes to
``data/r2/<swebench|terminalbench>/<section>/<model>/<cell>/`` instead of
``ICLR_experiments/``. Cell naming and validation are shared with the ICLR
launcher (``agentctx.experiments.iclr``); the roots live in
``agentctx.experiments.r2``. All remaining command-line arguments are handled
by the shared runner.

Unlike the ICLR launcher, an r2 cell may also be an ``adaptive-<tag>`` cell
(``--r2-cell d05__b15k__adaptive-prefix3-tts``): the runner's dedicated
``adaptive`` condition driven by ``--adaptive-schedule``, whose entries must
all carry the cell's budget and depth.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTCTX_SRC = ROOT / "src"
if str(AGENTCTX_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTCTX_SRC))

from agentctx.experiments import runner  # noqa: E402
from agentctx.experiments.iclr import (  # noqa: E402
    canonical_cell,
    option_value,
    validate_adaptive_cell_semantics,
    validate_cell_semantics,
    validate_summarizer,
)
from agentctx.experiments.r2 import R2_ROOTS, R2_SECTIONS  # noqa: E402


def parse_adapter_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--r2-benchmark",
        choices=tuple(R2_ROOTS),
        default="swe-bench",
    )
    parser.add_argument(
        "--r2-section", required=True,
        choices=R2_SECTIONS,
        help="result section below data/r2/<benchmark>/; same meaning as the "
             "ICLR sections (model_ablation = summarizer differs from the agent, "
             "prefix_cache_ablation = vLLM prefix caching flipped)",
    )
    parser.add_argument("--r2-model", required=True)
    parser.add_argument("--r2-cell", required=True,
                        help="{d03|d05|d07|di}__{b15k|bA|bP|bB|binf}__{primitive}")
    return parser.parse_known_args()


def main() -> None:
    adapter_args, runner_args = parse_adapter_args()
    runner_benchmark = (
        option_value(runner_args, "--benchmark")
        if "--benchmark" in runner_args
        else "swe-bench"
    )
    if runner_benchmark != adapter_args.r2_benchmark:
        raise SystemExit(
            "--r2-benchmark and --benchmark must select the same benchmark"
        )
    destination = canonical_cell(
        adapter_args.r2_benchmark, adapter_args.r2_section,
        adapter_args.r2_model, adapter_args.r2_cell,
        roots=R2_ROOTS, option_prefix="r2",
    )
    # ``adaptive-<tag>`` cells (r2 only) hold the runner's dedicated adaptive
    # condition; their budget/depth are checked against the schedule entries.
    if adapter_args.r2_cell.split("__")[2].startswith("adaptive-"):
        validate_adaptive_cell_semantics(adapter_args.r2_cell, runner_args, destination)
    else:
        validate_cell_semantics(adapter_args.r2_cell, runner_args, destination)
    validate_summarizer(adapter_args.r2_section, runner_args, destination)

    # A non-empty ablation name makes the original runner honor the explicit
    # task file without changing its source. model_results_dir is the only
    # output-routing behavior replaced by this adapter.
    if runner_benchmark == "swe-bench" and "--ablation" not in runner_args:
        runner_args = ["--ablation", f"r2-{adapter_args.r2_cell}", *runner_args]
    runner.model_results_dir = lambda: destination
    sys.argv = [sys.argv[0], *runner_args]
    runner.main()


if __name__ == "__main__":
    main()
