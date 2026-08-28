#!/usr/bin/env python3
"""Run one experiment cell directly in the canonical ICLR results tree.

This is a deliberately thin adapter around ``run_experiment.py``.  It keeps
the actively used runner unchanged and only overrides its result directory.
All remaining command-line arguments are handled by the original runner.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import run_experiment as runner


ROOT = Path(__file__).resolve().parent.parent
ICLR_SWEBENCH = ROOT / "ICLR_results" / "swebench"
CELL_RE = re.compile(r"^(d03|d05|d07|di)__(b(?:[1-9][0-9]*k|A|P|B|inf))__[a-z0-9+-]+$")
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CONDITION_TO_PRIMITIVE = {
    "truncation": "tr",
    "summarization": "su-full",
    "summarization-partial": "su-partial",
    "structured-summarize": "ss",
    "structured-summarize-partial": "ss-partial",
    "tool-result-clear": "trc",
    "trc-su": "trc-su",
    "trc-ss": "trc-ss",
    "otrc-tr": "otrc-tr",
    "otrc-su-partial": "otrc-su-partial",
    "otrc-ss-partial": "otrc-ss-partial",
    "full-context": "fc",
    "online-trc": "otrc",
}
INFINITE_BUDGET_CONDITIONS = {"full-context", "online-trc"}


def parse_adapter_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--iclr-section", required=True, choices=("main", "ablation"))
    parser.add_argument("--iclr-model", required=True)
    parser.add_argument("--iclr-cell", required=True)
    return parser.parse_known_args()


def canonical_cell(args: argparse.Namespace) -> Path:
    if not MODEL_RE.fullmatch(args.iclr_model):
        raise SystemExit("invalid --iclr-model; use lowercase letters, digits, and hyphens")
    if not CELL_RE.fullmatch(args.iclr_cell):
        raise SystemExit(
            "invalid --iclr-cell; expected {d03|d05|d07|di}__"
            "{b10k|bA|bP|bB|binf}__{primitive}"
        )
    destination = (
        ICLR_SWEBENCH / args.iclr_section / args.iclr_model / args.iclr_cell
    ).resolve()
    expected_parent = (ICLR_SWEBENCH / args.iclr_section / args.iclr_model).resolve()
    if destination.parent != expected_parent:
        raise SystemExit(f"refusing non-canonical ICLR destination: {destination}")
    return destination


def option_value(argv: list[str], option: str) -> str:
    try:
        return argv[argv.index(option) + 1]
    except (ValueError, IndexError):
        raise SystemExit(f"{option} is required by the ICLR runner") from None


def validate_cell_semantics(cell: str, runner_args: list[str], destination: Path) -> None:
    depth_tag, budget_tag, primitive = cell.split("__")
    try:
        conditions_index = runner_args.index("--conditions")
    except ValueError:
        raise SystemExit("--conditions is required by the ICLR runner") from None
    condition_values = []
    for value in runner_args[conditions_index + 1:]:
        if value.startswith("--"):
            break
        condition_values.append(value)
    if len(condition_values) != 1:
        raise SystemExit("ICLR cells require exactly one --conditions value")
    condition = condition_values[0]
    expected_primitive = CONDITION_TO_PRIMITIVE.get(condition)
    if expected_primitive is None:
        raise SystemExit(f"condition {condition!r} has no canonical ICLR primitive")
    if primitive != expected_primitive:
        raise SystemExit(
            f"cell primitive {primitive!r} does not match condition {condition!r}"
        )
    depth_tunable = {
        "truncation", "summarization", "summarization-partial",
        "structured-summarize", "structured-summarize-partial",
    }
    if (condition in depth_tunable) != (depth_tag != "di"):
        raise SystemExit(f"cell depth tag {depth_tag} is invalid for condition {condition!r}")

    budget = int(option_value(runner_args, "--budget"))
    depth = float(option_value(runner_args, "--depth"))
    expected_depth = {"d03": 0.3, "d05": 0.5, "d07": 0.7}.get(depth_tag)
    if expected_depth is not None and depth != expected_depth:
        raise SystemExit(f"cell depth {depth_tag} does not match --depth {depth}")
    if depth_tag == "di" and depth != 0.5:
        raise SystemExit("depth-invariant cells require the canonical --depth 0.5")
    if condition in INFINITE_BUDGET_CONDITIONS and budget_tag != "binf":
        raise SystemExit(f"condition {condition!r} requires a binf cell")
    if condition not in INFINITE_BUDGET_CONDITIONS and budget_tag == "binf":
        raise SystemExit(f"condition {condition!r} requires a finite-budget cell")
    if budget_tag == "binf" and budget != 999_999_999:
        raise SystemExit("binf cells require --budget 999999999")
    numeric_match = re.fullmatch(r"b([1-9][0-9]*)k", budget_tag)
    if numeric_match and budget != int(numeric_match.group(1)) * 1000:
        raise SystemExit(f"cell budget {budget_tag} does not match --budget {budget}")

    # Symbolic GLM cells keep the same path after calibration. Never silently
    # mix runs made with different calibrated values in one bA/bP/bB cell.
    results_file = destination / "experiment_results.json"
    if results_file.exists():
        payload = json.loads(results_file.read_text())
        rows = payload.get("results", []) if isinstance(payload, dict) else payload
        conflicts = [
            row for row in rows
            if row.get("budget") != budget
            or round(float(row.get("compression_ratio", 0.5) or 0.5), 3) != round(depth, 3)
            or row.get("condition") != condition
        ]
        if conflicts:
            raise SystemExit(
                f"existing cell metadata conflicts with this launch: {destination}"
            )


def main() -> None:
    adapter_args, runner_args = parse_adapter_args()
    if "--benchmark" in runner_args and option_value(runner_args, "--benchmark") != "swe-bench":
        raise SystemExit("run_experiment_iclr.py only writes SWE-Bench cells")
    destination = canonical_cell(adapter_args)
    validate_cell_semantics(adapter_args.iclr_cell, runner_args, destination)

    # A non-empty ablation name makes the original runner honor the explicit
    # task file without changing its source. model_results_dir is the only
    # output-routing behavior replaced by this adapter.
    if "--ablation" not in runner_args:
        runner_args = ["--ablation", f"iclr-{adapter_args.iclr_cell}", *runner_args]
    runner.model_results_dir = lambda: destination
    sys.argv = [sys.argv[0], *runner_args]
    runner.main()


if __name__ == "__main__":
    main()
