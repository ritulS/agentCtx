#!/usr/bin/env python3
"""Build a task x primitive outcome CSV from Terminal-Bench results.

By default, the P-40 main and ABL-15 ablation result cells below
``ICLR_results/terminalbench`` are aggregated into
``analysis/outcomes/terminalbench_outcomes.csv``.  The recursive search also
supports namespaced result trees such as ``main/p80_rootless/<model>/<cell>``.

Usage:
    python3 analysis/aggregate_terminalbench_results.py
    python3 analysis/aggregate_terminalbench_results.py --source-root /path/to/results
    python3 analysis/aggregate_terminalbench_results.py --output /tmp/tb.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_ROOT = ROOT / "ICLR_results" / "terminalbench"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "outcomes" / "terminalbench_outcomes.csv"
DEFAULT_P40_TASKS = ROOT / "task_lists" / "tbench_p40.json"
DEFAULT_ABL15_TASKS = ROOT / "task_lists" / "tbench_abl15.json"
RUNS_PER_TASK = 3

MODEL_BUDGETS = {
    "qwen35b": ("b2k", "b3k", "b4k"),
    "devstral24b": ("b3k", "b4k", "b7k"),
    "glm47flash": ("b2k", "b3k", "b5k"),
}
SINGLE_PRIMITIVES = {"tr", "su-full", "su-partial", "ss", "ss-partial"}
INVARIANT_PRIMITIVES = {"trc", "trc-su", "trc-ss", "otrc-tr", "otrc-su-partial", "otrc-ss-partial"}
BASELINE_CELLS = {"di__binf__fc", "di__binf__otrc"}

# Short primitive labels used in the ICLR result cell names.
CONDITION_TO_PRIMITIVE = {
    "full-context": "fc",
    "truncation": "tr",
    "summarization": "su-full",
    "summarization-partial": "su-partial",
    "structured-summarize": "ss",
    "structured-summarize-partial": "ss-partial",
    "tool-result-clear": "trc",
    "trc-su": "trc-su",
    "trc-ss": "trc-ss",
    "online-trc": "otrc",
    "otrc-tr": "otrc-tr",
    "otrc-su-partial": "otrc-su-partial",
    "otrc-ss-partial": "otrc-ss-partial",
}

FIELDNAMES = [
    "benchmark", "benchmark_version", "dataset", "experiment_section",
    "model_key", "model", "cell", "source_file", "task_name", "condition",
    "primitive", "raw_primitive", "token_budget", "depth", "run_num",
    "resolved", "reward", "failure_mode", "execution_state", "agent_started",
    "pre_agent_failure", "returncode", "exit_status", "submission_generated",
    "step_count", "total_tokens", "total_prompt_tokens",
    "total_completion_tokens", "latency_e2e_s", "latency_agent_s",
    "latency_llm_s", "compression_events", "trc_fallback_events",
    "online_trc_clears", "total_tokens_saved", "online_trc_tokens_saved",
    "summarization_prompt_tokens", "summarization_latency_s",
]


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load a bare result list or a wrapper containing a ``results`` list."""
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        payload = payload.get("results", [])
    if not isinstance(payload, list):
        raise ValueError("expected a list or an object containing a results list")
    return [row for row in payload if isinstance(row, dict)]


def load_task_names(path: Path) -> set[str]:
    payload = json.loads(path.read_text())
    tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(tasks, list) or not all(isinstance(task, str) for task in tasks):
        raise SystemExit(f"task list must contain a string list: {path}")
    return set(tasks)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def execution_state(row: dict[str, Any]) -> str:
    """Distinguish attempted runs from failures before the agent started."""
    calls = _number(row.get("n_calls")) or 0
    tokens = _number(row.get("total_tokens")) or 0
    if calls > 0 or tokens > 0:
        return "agent_started"
    if row.get("returncode") not in (None, 0):
        return "pre_agent_failure"
    return "zero_step_unknown"


def failure_mode(row: dict[str, Any], state: str) -> str:
    """Return a Terminal-Bench-aware, compact outcome classification."""
    reward = _number(row.get("reward"))
    if row.get("resolved") is True or (reward is not None and reward > 0):
        return "resolved"
    if state == "pre_agent_failure":
        return "pre_agent_failure"
    status = str(row.get("exit_status") or "")
    if status.startswith("LimitsExceeded"):
        return "limits_exceeded"
    if status == "Submitted" or row.get("submission_generated"):
        return "submitted_unresolved"
    if status in {"ValueError", "BadRequestError", "ContextWindowExceededError"}:
        return "agent_error"
    if not status or status == "missing_exit_info":
        return "incomplete"
    return "other"


def path_metadata(path: Path, source_root: Path) -> tuple[str, str, str]:
    """Extract section/model/cell from the variable-depth TB result tree."""
    parts = path.relative_to(source_root).parts[:-1]
    if len(parts) < 3:
        return "", "", ""
    return "/".join(parts[:-2]), parts[-2], parts[-1]


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalized_row(
    row: dict[str, Any], source_root: Path, source: Path
) -> dict[str, Any]:
    section, model_key, cell = path_metadata(source, source_root)
    condition = str(row.get("condition") or "")
    state = execution_state(row)
    return {
        "benchmark": "terminalbench",
        "benchmark_version": row.get("benchmark_version"),
        "dataset": row.get("dataset") or "",
        "experiment_section": section,
        "model_key": model_key,
        "model": row.get("model") or row.get("agent_model") or model_key,
        "cell": cell,
        "source_file": display_path(source),
        "task_name": row.get("instance_id") or row.get("task_name") or "",
        "condition": condition,
        "primitive": CONDITION_TO_PRIMITIVE.get(condition, row.get("primitive") or ""),
        "raw_primitive": row.get("primitive") or "",
        "token_budget": row.get("budget"),
        "depth": row.get("compression_ratio", 0.5),
        "run_num": row.get("run_num"),
        "resolved": row.get("resolved"),
        "reward": row.get("reward"),
        "failure_mode": failure_mode(row, state),
        "execution_state": state,
        "agent_started": state == "agent_started",
        "pre_agent_failure": state == "pre_agent_failure",
        "returncode": row.get("returncode"),
        "exit_status": row.get("exit_status") or "",
        "submission_generated": row.get("submission_generated"),
        "step_count": row.get("n_calls"),
        "total_tokens": row.get("total_tokens"),
        "total_prompt_tokens": row.get("total_prompt_tokens"),
        "total_completion_tokens": row.get("total_completion_tokens"),
        "latency_e2e_s": row.get("e2e_latency_s"),
        "latency_agent_s": row.get("agent_latency_s"),
        "latency_llm_s": row.get("llm_latency_s"),
        "compression_events": row.get("compression_events", 0),
        "trc_fallback_events": row.get("trc_truncation_fallback_events", 0),
        "online_trc_clears": row.get("online_trc_clears", 0),
        "total_tokens_saved": row.get("total_tokens_saved", 0),
        "online_trc_tokens_saved": row.get("online_trc_total_tokens_saved", 0),
        "summarization_prompt_tokens": row.get("summarization_prompt_tokens", 0),
        "summarization_latency_s": row.get("summarization_latency_s", 0),
    }


def expected_cells(section: str, model: str) -> set[str]:
    """Mirror the P-40/ABL-15 grid in run_agent_models_expansion_tb.sh."""
    if model not in MODEL_BUDGETS:
        return set()
    budget_a, budget_p, budget_b = MODEL_BUDGETS[model]
    if section == "main":
        cells = {f"d05__{budget_p}__{primitive}" for primitive in SINGLE_PRIMITIVES}
        cells |= {f"di__{budget_p}__{primitive}" for primitive in INVARIANT_PRIMITIVES}
        return cells | BASELINE_CELLS

    cells = {
        f"d05__{budget}__{primitive}"
        for budget in (budget_a, budget_b)
        for primitive in SINGLE_PRIMITIVES
    }
    cells |= {
        f"{depth}__{budget}__{primitive}"
        for depth in ("d03", "d07")
        for budget in (budget_a, budget_p, budget_b)
        for primitive in SINGLE_PRIMITIVES
    }
    cells |= {
        f"di__{budget}__{primitive}"
        for budget in (budget_a, budget_b)
        for primitive in INVARIANT_PRIMITIVES
    }
    return cells


def result_files(source_root: Path) -> Iterable[Path]:
    """Yield only direct P-40 main and ABL-15 ablation grid cells."""
    for section in ("main", "ablation"):
        for path in sorted((source_root / section).glob("*/*/experiment_results.json")):
            model, cell = path.parts[-3:-1]
            if cell in expected_cells(section, model):
                yield path


def build(
    source_root: Path, output: Path, p40_tasks_path: Path, abl15_tasks_path: Path
) -> int:
    if not source_root.is_dir():
        raise SystemExit(f"input directory does not exist: {source_root}")

    task_names = {
        "main": load_task_names(p40_tasks_path),
        "ablation": load_task_names(abl15_tasks_path),
    }
    sources = list(result_files(source_root))
    rows: list[dict[str, Any]] = []
    bad_sources: list[str] = []
    for source in sources:
        try:
            section = source.relative_to(source_root).parts[0]
            selected = (
                row for row in load_records(source)
                if (row.get("instance_id") or row.get("task_name")) in task_names[section]
                and isinstance(row.get("run_num"), int)
                and 1 <= row["run_num"] <= RUNS_PER_TASK
            )
            rows.extend(normalized_row(row, source_root, source) for row in selected)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            bad_sources.append(f"{source}: {exc}")

    rows.sort(key=lambda row: (
        row["experiment_section"], row["model_key"], row["cell"],
        row["task_name"], str(row["run_num"]), row["source_file"],
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"terminalbench: wrote {len(rows):,} runs from {len(sources):,} files to {output}")
    for message in bad_sources:
        print(f"WARNING: skipped {message}")
    return len(bad_sources)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--p40-tasks", type=Path, default=DEFAULT_P40_TASKS)
    parser.add_argument("--abl15-tasks", type=Path, default=DEFAULT_ABL15_TASKS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if build(
        args.source_root.resolve(), args.output.resolve(),
        args.p40_tasks.resolve(), args.abl15_tasks.resolve(),
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
