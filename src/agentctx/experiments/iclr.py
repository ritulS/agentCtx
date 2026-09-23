"""Canonical ICLR result paths and experiment-cell validation."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from agentctx import INFINITE_BUDGET, WORKSPACE_ROOT
from agentctx.summary_config import summary_model_info


ICLR_ROOTS = {
    "swe-bench": WORKSPACE_ROOT / "ICLR_experiments" / "swebench",
    "terminal-bench": WORKSPACE_ROOT / "ICLR_experiments" / "terminalbench",
}
# Result sections below ICLR_experiments/<benchmark>/. model_ablation holds runs
# whose summarizer differs from the agent (FOLLOWUP_EXPERIMENTS.md §4);
# prefix_cache_ablation holds self-summarized runs served with vLLM prefix
# caching flipped relative to the benchmark's production runs.
ICLR_SECTIONS = ("main", "ablation", "model_ablation", "prefix_cache_ablation")
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
    """Value of ``option`` in ``--opt value`` or ``--opt=value`` form (last wins)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(option, default=None)
    value = getattr(parser.parse_known_args(argv)[0], option.lstrip("-").replace("-", "_"))
    if value is None:
        raise SystemExit(f"{option} is required by the ICLR runner")
    return value


def validate_summarizer(section: str, runner_args: list[str], destination: Path) -> None:
    """The summarizer is part of a cell's identity, like budget and depth.

    ``model_ablation`` cells hold runs whose summarizer differs from the agent,
    so they require ``--summary-config``; ``main``/``ablation``/
    ``prefix_cache_ablation`` cells are self-summarized and must not get one.
    Within a cell, every existing run
    that recorded its summarizer must match this launch's, so changing
    SUMMARY_CONFIG without changing the destination is refused instead of
    silently filling the remaining keys with a different summarizer.
    """
    # Resolve the *effective* summarizer the agents will see: the CLI option
    # (either ``--summary-config x`` or ``--summary-config=x``, parsed like the
    # runner does) exported to the environment, or, without it, whatever
    # MSWEA_SUMMARY_MODEL_CONFIG / _NAME / _API_BASE are already set to.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--summary-config", default=None)
    config_arg = parser.parse_known_args(runner_args)[0].summary_config
    if config_arg is not None:
        config_path = Path(config_arg).resolve()
        if not config_path.is_file():
            raise SystemExit(f"--summary-config not found: {config_path}")
        os.environ["MSWEA_SUMMARY_MODEL_CONFIG"] = str(config_path)
    launch = summary_model_info()
    launch_identity = (launch["source"], launch.get("model_name"))
    overridden = launch["source"] == "override"
    origin = (f"--summary-config {config_arg}" if config_arg is not None
              else "MSWEA_SUMMARY_MODEL_CONFIG/_NAME/_API_BASE in the environment")
    if section == "model_ablation" and not overridden:
        raise SystemExit("model_ablation cells require a summarizer override "
                         "(--summary-config); none is in effect")
    if section != "model_ablation" and overridden:
        raise SystemExit(f"a summarizer override is in effect ({origin}: {launch.get('model_name')}) "
                         f"but section {section!r} holds self-summarized cells; use model_ablation")

    results_file = destination / "experiment_results.json"
    if not results_file.exists():
        return
    payload = json.loads(results_file.read_text())
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    recorded = {
        (row["summarization_model"].get("source"), row["summarization_model"].get("model_name"))
        for row in rows
        if isinstance(row.get("summarization_model"), dict)
        and row["summarization_model"].get("source")
    }
    if recorded - {launch_identity}:
        raise SystemExit(
            f"existing runs in {destination} recorded summarizer(s) "
            f"{sorted(recorded - {launch_identity})}, but this launch uses {launch_identity}; "
            "use a different --iclr-model (<agent>-sum-<summarizer>) for a different summarizer"
        )


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
    if budget_tag == "binf" and budget != INFINITE_BUDGET:
        raise SystemExit(f"binf cells require --budget {INFINITE_BUDGET}")
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
