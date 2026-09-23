"""Harbor trial artifacts, normalized metrics, and FC calibration aggregation.

Shared by the Terminal-Bench experiment adapter (``terminal_bench.py``) and the
FC calibration launcher (``scripts/calibration/run_budget_calibration_tb.py``)
so both write result rows with the same fields and verdict semantics
(see ``tb_verdict.py``).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agentctx import INFINITE_BUDGET, WORKSPACE_ROOT

from . import tb_verdict
from .results import run_key
from .tb_verdict import select_trials, task_name, trial_verdict

DATASET = "terminal-bench-core@0.1.1"
BENCHMARK_VERSION = "1.0"
FULL_CONTEXT_CONDITION = {
    "condition": "full-context",
    "primitive": "truncation",
    "budget": INFINITE_BUDGET,
}


def seconds_between(start: str | None, finish: str | None) -> float | None:
    if not start or not finish:
        return None
    try:
        return round((datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds(), 2)
    except ValueError:
        return None


def relative_to_workspace(path: Path, workspace_root: Path = WORKSPACE_ROOT) -> str:
    try:
        return str(path.relative_to(workspace_root))
    except ValueError:
        return str(path)


def supersede_previous_output(output: Path, harbor_result: dict) -> str | None:
    """Move an earlier attempt's run directory aside instead of overwriting it.

    Returns the relative name of the archived directory, or None when the
    directory did not exist or already holds this very trial.
    """
    previous = output / "harbor_result.json"
    if not previous.exists():
        return None
    try:
        if json.loads(previous.read_text()).get("id") == harbor_result.get("id"):
            return None
    except (OSError, ValueError):
        pass
    index = 1
    while (archived := output.with_name(f"{output.name}.superseded.{index}")).exists():
        index += 1
    output.rename(archived)
    return archived.name


def normalize_trial(
    trial_dir: Path,
    destination: Path,
    label: str,
    run_num: int,
    *,
    condition: dict[str, Any],
    compression_ratio: float,
    benchmark: str = "terminal-bench",
    benchmark_version: str = BENCHMARK_VERSION,
    dataset: str = DATASET,
    workspace_root: Path = WORKSPACE_ROOT,
    verifier_timeout_multiplier: float | None = None,
    fill_missing_timestamp: bool = False,
    supersede: bool = False,
) -> dict[str, Any]:
    """Copy a Harbor trial's artifacts and convert its metrics to a result row.

    ``reward`` / ``resolved`` / ``verdict_source`` / ``harbor_exception(_message)``
    (+ ``reward_file`` when recovered) come from ``tb_verdict.trial_verdict``:
    ``resolved`` is None when the verifier produced no reward.

    Calibration preserves a missing start time; the experiment adapter requests
    a current-time fallback through ``fill_missing_timestamp`` and, through
    ``supersede``, keeps an earlier attempt's run directory as
    ``run_<n>.superseded.<k>`` and stamps ``attempts`` / ``superseded_dir``.
    """
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        result_path = trial_dir / "results.json"
    harbor_result = json.loads(result_path.read_text())
    task = task_name(harbor_result)
    condition_name = condition["condition"]
    output = destination / task / condition_name / f"run_{run_num}"
    superseded_dir = supersede_previous_output(output, harbor_result) if supersede else None
    output.mkdir(parents=True, exist_ok=True)

    for source, target in (
        (trial_dir / "agent" / "trajectory.json", output / "trajectory.json"),
        (trial_dir / "agent" / "token_log.json", output / "token_log.json"),
        (trial_dir / "agent" / "exit_info.json", output / "exit_info.json"),
        (trial_dir / "trial.log", output / "agent.log"),
        (result_path, output / "harbor_result.json"),
    ):
        if source.exists():
            shutil.copy2(source, target)

    token_log_path = trial_dir / "agent" / "token_log.json"
    token_log = json.loads(token_log_path.read_text()) if token_log_path.exists() else {}
    exit_path = trial_dir / "agent" / "exit_info.json"
    exit_info = json.loads(exit_path.read_text()) if exit_path.exists() else {}
    verdict = trial_verdict(harbor_result, trial_dir)
    timing = harbor_result.get("agent_execution") or {}
    row = {
        "key": run_key(task, condition_name, run_num),
        "benchmark": benchmark,
        "benchmark_version": benchmark_version,
        "dataset": dataset,
        "instance_id": task,
        "condition": condition_name,
        "primitive": condition["primitive"],
        "budget": condition["budget"],
        "compression_ratio": compression_ratio,
        "is_baseline": condition["budget"] == INFINITE_BUDGET,
        "run_num": run_num,
        "model": label,
        "agent_model": label,
        "timestamp": harbor_result.get("started_at"),
        "returncode": 0 if harbor_result.get("exception_info") is None else -1,
        "e2e_latency_s": seconds_between(harbor_result.get("started_at"), harbor_result.get("finished_at")),
        "agent_latency_s": seconds_between(timing.get("started_at"), timing.get("finished_at")),
        **verdict,
        "verifier_timeout_multiplier": tb_verdict.verifier_timeout_multiplier(verifier_timeout_multiplier),
        "harbor_trial_dir": relative_to_workspace(trial_dir, workspace_root),
    }
    if supersede:
        row["attempts"] = 1
        row["superseded_dir"] = superseded_dir
    row.update({
        "exit_status": exit_info.get("exit_status", "missing_exit_info"),
        "n_calls": exit_info.get("n_calls"),
        "submission_generated": exit_info.get("exit_status") == "Submitted",
        "patch_generated": exit_info.get("exit_status") == "Submitted",
    })
    if fill_missing_timestamp and not row["timestamp"]:
        row["timestamp"] = datetime.now().isoformat()
    row.update(token_log)
    row["llm_latency_s"] = token_log.get("total_latency_s", 0.0)
    return row


def collect_results(
    job_dir: Path,
    destination: Path,
    label: str,
    run_num: int,
    *,
    benchmark_version: str = BENCHMARK_VERSION,
    dataset: str = DATASET,
    workspace_root: Path = WORKSPACE_ROOT,
    verifier_timeout_multiplier: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect full-context calibration trials and merge by (task, run_num).

    Preserve earlier infrastructure phases and repetitions, replacing only
    rows collected for the current task and run number.
    """
    # One trial per task. A relaunched job can hold several trials for the
    # same task; the one with a verifier verdict wins, then the latest finish.
    selected, duplicates = select_trials(job_dir)
    for task, rejected in sorted(duplicates.items()):
        print(
            f"    ! {task}: {len(rejected)} duplicate trial(s) in {job_dir.name}; "
            "keeping the one with a verdict / latest finish"
        )
    current_rows = [
        normalize_trial(
            path.parent, destination, label, run_num,
            condition=FULL_CONTEXT_CONDITION,
            compression_ratio=0.5,
            benchmark_version=benchmark_version,
            dataset=dataset,
            workspace_root=workspace_root,
            verifier_timeout_multiplier=verifier_timeout_multiplier,
        )
        for path in selected.values()
    ]
    current_rows.sort(key=lambda row: row["instance_id"])
    unverified = [row["instance_id"] for row in current_rows if row["resolved"] is None]
    if unverified:
        print(
            f"    ! {len(unverified)} trial(s) without a verifier verdict (resolved=None): "
            + ", ".join(unverified)
        )

    # A canonical run may be collected in multiple infrastructure phases (for
    # example, tasks whose images are already available followed by images
    # built later). Preserve prior runs and replace only the matching
    # (task, run_num) rows.
    aggregate_path = destination / "experiment_results.json"
    previous_rows: list[dict[str, Any]] = []
    if aggregate_path.exists():
        payload = json.loads(aggregate_path.read_text())
        if not isinstance(payload, list):
            raise SystemExit(f"expected a JSON list in {aggregate_path}")
        previous_rows = payload
    merged = {
        (str(row["instance_id"]), int(row.get("run_num", 1))): row
        for row in previous_rows
    }
    merged.update({(str(row["instance_id"]), run_num): row for row in current_rows})
    aggregate_rows = sorted(
        merged.values(), key=lambda row: (int(row.get("run_num", 1)), row["instance_id"])
    )
    aggregate_path.write_text(json.dumps(aggregate_rows, indent=2))
    return current_rows, aggregate_rows
