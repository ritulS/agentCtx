"""Harbor trial artifacts, normalized metrics, and FC calibration aggregation."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .results import run_key

INF = 999_999_999
DATASET = "terminal-bench-core@0.1.1"


def trial_result_paths(job_dir: Path) -> list[Path]:
    """Find trial results in current and older Harbor job layouts."""
    for root in (job_dir / "trials", job_dir):
        for filename in ("result.json", "results.json"):
            paths = sorted(root.glob(f"*/{filename}"))
            if paths:
                return paths
    return []


def reward_value(result: dict[str, Any]) -> float | None:
    rewards = (result.get("verifier_result") or {}).get("rewards")
    if not isinstance(rewards, dict) or not rewards:
        return None
    value = rewards.get("reward")
    if value is None and len(rewards) == 1:
        value = next(iter(rewards.values()))
    return float(value) if isinstance(value, (int, float)) else None


def seconds_between(start: str | None, finish: str | None) -> float | None:
    if not start or not finish:
        return None
    try:
        return round((datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds(), 2)
    except ValueError:
        return None


def normalize_trial(
    trial_dir: Path,
    destination: Path,
    label: str,
    run_num: int,
    *,
    condition: dict[str, Any],
    compression_ratio: float,
    benchmark: str = "terminal-bench",
    benchmark_version: str = "1.0",
    dataset: str = DATASET,
    fill_missing_timestamp: bool = False,
) -> dict[str, Any]:
    """Copy a Harbor trial's artifacts and convert its metrics to a result row.

    Calibration preserves a missing start time; the experiment adapter requests
    a current-time fallback through fill_missing_timestamp.
    """
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        result_path = trial_dir / "results.json"
    result = json.loads(result_path.read_text())
    task = result["task_name"]
    condition_name = condition["condition"]
    output = destination / task / condition_name / f"run_{run_num}"
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
    reward = reward_value(result)
    timing = result.get("agent_execution") or {}
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
        "is_baseline": condition["budget"] == INF,
        "run_num": run_num,
        "model": label,
        "agent_model": label,
        "timestamp": result.get("started_at"),
        "returncode": 0 if result.get("exception_info") is None else -1,
        "e2e_latency_s": seconds_between(result.get("started_at"), result.get("finished_at")),
        "agent_latency_s": seconds_between(timing.get("started_at"), timing.get("finished_at")),
        "resolved": bool(reward is not None and reward > 0),
        "reward": reward,
        "exit_status": exit_info.get("exit_status", "missing_exit_info"),
        "n_calls": exit_info.get("n_calls"),
        "submission_generated": exit_info.get("exit_status") == "Submitted",
        "patch_generated": exit_info.get("exit_status") == "Submitted",
    }
    if fill_missing_timestamp and not row["timestamp"]:
        row["timestamp"] = datetime.now().isoformat()
    row.update(token_log)
    row["llm_latency_s"] = token_log.get("total_latency_s", 0.0)
    return row


def collect_results(
    job_dir: Path, destination: Path, label: str, run_num: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect full-context calibration trials and merge by (task, run_num).

    Preserve earlier infrastructure phases and repetitions, replacing only
    rows collected for the current task and run number.
    """
    current_rows = [
        normalize_trial(
            path.parent, destination, label, run_num,
            condition={"condition": "full-context", "primitive": "truncation", "budget": INF},
            compression_ratio=0.5,
        )
        for path in trial_result_paths(job_dir)
    ]
    current_rows.sort(key=lambda row: row["instance_id"])

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
