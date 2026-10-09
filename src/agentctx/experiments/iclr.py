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
    # Length-free summaries (depth-invariant: no word target, so ``di__`` cells).
    "summarization-free": "su-free",
    "structured-summarize-free": "ss-free",
}
INFINITE_BUDGET_CONDITIONS = {"full-context", "online-trc"}


def canonical_cell(
    benchmark: str, section: str, model: str, cell: str,
    roots: dict[str, Path] = ICLR_ROOTS, option_prefix: str = "iclr",
) -> Path:
    """``<roots[benchmark]>/<section>/<model>/<cell>`` after validating each part.

    ``roots`` selects the results tree (the ICLR tree by default; the r2
    extension tree lives under ``data/r2/`` and passes its own roots).
    ``option_prefix`` only names the launcher's options in error messages.
    """
    if not MODEL_RE.fullmatch(model):
        raise SystemExit(f"invalid --{option_prefix}-model; use lowercase letters, digits, and hyphens")
    if not CELL_RE.fullmatch(cell):
        raise SystemExit(
            f"invalid --{option_prefix}-cell; expected {{d03|d05|d07|di}}__"
            "{b10k|bA|bP|bB|binf}__{primitive}"
        )
    destination = (roots[benchmark] / section / model / cell).resolve()
    expected_parent = (roots[benchmark] / section / model).resolve()
    if destination.parent != expected_parent:
        raise SystemExit(f"refusing non-canonical {option_prefix} destination: {destination}")
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


def _conditions_option(runner_args: list[str]) -> list[str]:
    """The values given to ``--conditions`` (the runner takes ``nargs="+"``)."""
    try:
        conditions_index = runner_args.index("--conditions")
    except ValueError:
        raise SystemExit("--conditions is required by the ICLR runner") from None
    condition_values = []
    for value in runner_args[conditions_index + 1:]:
        if value.startswith("--"):
            break
        condition_values.append(value)
    return condition_values


def validate_cell_semantics(cell: str, runner_args: list[str], destination: Path) -> None:
    depth_tag, budget_tag, primitive = cell.split("__")
    condition_values = _conditions_option(runner_args)
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


ADAPTIVE_CELL_RE = re.compile(r"^adaptive-[a-z0-9+-]+$")


def validate_adaptive_cell_semantics(cell: str, runner_args: list[str], destination: Path) -> None:
    """Cells whose primitive tag is ``adaptive-<tag>`` (r2 tree only).

    Such a cell holds the runner's dedicated ``adaptive`` condition driven by a
    JSON schedule (``--adaptive-schedule``; see
    src/agentctx/compression/ADAPTIVE.md). The schedule decides which primitive
    fires at each compression event, so the cell name cannot carry a single
    primitive; ``<tag>`` is the launcher's label for the schedule and the
    snapshot in ``<cell>/_adaptive/<sha256>.json`` is authoritative. What the
    cell name still promises is the budget and depth, so every schedule entry
    must carry the cell's ``b<N>k`` budget and ``d03|d05|d07`` depth. ``di``
    and symbolic/unlimited budgets have no meaning for a schedule and are
    rejected, as are ``--budget`` / ``--depth`` (they only configure fixed
    conditions) and Python policies (their settings are not readable from a
    file, so they cannot be checked against the cell name).
    """
    depth_tag, budget_tag, primitive = cell.split("__")
    if not ADAPTIVE_CELL_RE.fullmatch(primitive):
        raise SystemExit(f"cell primitive {primitive!r} is not an adaptive-<tag> cell")
    if _conditions_option(runner_args) != ["adaptive"]:
        raise SystemExit("adaptive cells require exactly `--conditions adaptive`")
    for option in ("--budget", "--depth"):
        if any(arg == option or arg.startswith(option + "=") for arg in runner_args):
            raise SystemExit(f"{option} does not apply to adaptive cells; "
                             "budget and depth come from the schedule entries")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--adaptive-schedule", default=None)
    parser.add_argument("--adaptive-policy", default=None)
    selected = parser.parse_known_args(runner_args)[0]
    if selected.adaptive_policy is not None or selected.adaptive_schedule is None:
        raise SystemExit("adaptive cells require --adaptive-schedule (no --adaptive-policy)")
    schedule_path = Path(selected.adaptive_schedule)
    if not schedule_path.is_file():
        raise SystemExit(f"--adaptive-schedule not found: {schedule_path}")
    entries = json.loads(schedule_path.read_text())
    if not isinstance(entries, list) or not entries:
        raise SystemExit("--adaptive-schedule must be a nonempty JSON array")

    expected_depth = {"d03": 0.3, "d05": 0.5, "d07": 0.7}.get(depth_tag)
    if expected_depth is None:
        raise SystemExit("adaptive cells need an explicit depth tag (d03|d05|d07)")
    numeric_match = re.fullmatch(r"b([1-9][0-9]*)k", budget_tag)
    if numeric_match is None:
        raise SystemExit("adaptive cells need a numeric b<N>k budget tag")
    expected_budget = int(numeric_match.group(1)) * 1000
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SystemExit(f"schedule entry {index} is not an object")
        if entry.get("budget") != expected_budget:
            raise SystemExit(f"schedule entry {index} budget {entry.get('budget')!r} "
                             f"does not match cell budget {budget_tag}")
        if round(float(entry.get("depth", 0.5)), 3) != expected_depth:
            raise SystemExit(f"schedule entry {index} depth {entry.get('depth', 0.5)!r} "
                             f"does not match cell depth {depth_tag}")

    # The runner's own resume check (agentctx.compression.selection.prepare_run)
    # rejects a different schedule in the same cell; here only make sure the
    # cell never mixes fixed-condition rows with adaptive ones.
    results_file = destination / "experiment_results.json"
    if results_file.exists():
        payload = json.loads(results_file.read_text())
        rows = payload.get("results", []) if isinstance(payload, dict) else payload
        if any(row.get("condition") != "adaptive" for row in rows):
            raise SystemExit(
                f"existing cell holds non-adaptive rows, refusing to mix: {destination}"
            )
