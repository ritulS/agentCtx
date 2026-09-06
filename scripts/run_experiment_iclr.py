#!/usr/bin/env python3
"""Run one experiment cell directly in the canonical ICLR results tree.

This is a deliberately thin adapter around ``agentctx.experiments.runner``.  It keeps
the actively used runner unchanged and only overrides its result directory.
Path construction and cell validation live in ``agentctx.experiments.iclr``.
All remaining command-line arguments are handled by the shared runner.
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
    ICLR_ROOTS,
    canonical_cell,
    option_value,
    validate_cell_semantics,
)


def parse_adapter_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--iclr-benchmark",
        choices=tuple(ICLR_ROOTS),
        default="swe-bench",
    )
    parser.add_argument("--iclr-section", required=True, choices=("main", "ablation"))
    parser.add_argument("--iclr-model", required=True)
    parser.add_argument("--iclr-cell", required=True)
    return parser.parse_known_args()


def main() -> None:
    adapter_args, runner_args = parse_adapter_args()
    runner_benchmark = (
        option_value(runner_args, "--benchmark")
        if "--benchmark" in runner_args
        else "swe-bench"
    )
    if runner_benchmark != adapter_args.iclr_benchmark:
        raise SystemExit(
            "--iclr-benchmark and --benchmark must select the same benchmark"
        )
    destination = canonical_cell(adapter_args)
    validate_cell_semantics(adapter_args.iclr_cell, runner_args, destination)

    # A non-empty ablation name makes the original runner honor the explicit
    # task file without changing its source. model_results_dir is the only
    # output-routing behavior replaced by this adapter.
    if runner_benchmark == "swe-bench" and "--ablation" not in runner_args:
        runner_args = ["--ablation", f"iclr-{adapter_args.iclr_cell}", *runner_args]
    runner.model_results_dir = lambda: destination
    sys.argv = [sys.argv[0], *runner_args]
    runner.main()


if __name__ == "__main__":
    main()
