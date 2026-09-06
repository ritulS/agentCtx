"""Canonical ICLR result paths and experiment-cell validation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from agentctx import WORKSPACE_ROOT


ICLR_ROOTS = {
    "swe-bench": WORKSPACE_ROOT / "ICLR_results" / "swebench",
    "terminal-bench": WORKSPACE_ROOT / "ICLR_results" / "terminalbench",
}
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


def canonical_cell(args: argparse.Namespace) -> Path:
    if not MODEL_RE.fullmatch(args.iclr_model):
        raise SystemExit("invalid --iclr-model; use lowercase letters, digits, and hyphens")
    if not CELL_RE.fullmatch(args.iclr_cell):
        raise SystemExit(
            "invalid --iclr-cell; expected {d03|d05|d07|di}__"
            "{b10k|bA|bP|bB|binf}__{primitive}"
        )
    destination = (
        ICLR_ROOTS[args.iclr_benchmark]
        / args.iclr_section / args.iclr_model / args.iclr_cell
    ).resolve()
    expected_parent = (
        ICLR_ROOTS[args.iclr_benchmark] / args.iclr_section / args.iclr_model
    ).resolve()
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
