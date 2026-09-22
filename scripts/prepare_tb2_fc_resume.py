#!/usr/bin/env python3
"""Preserve completed TB2 FC trials and list only unfinished tasks for resume."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import run_budget_calibration_tb as runner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--job-dir",
        type=Path,
        default=ROOT / "logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc/tb2-qwen35b-fc-run1",
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=ROOT / "data/tb2-harbor-prebuilt-2.0",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "task_lists/tbench2_qwen_fc_run1_remaining.json",
    )
    parser.add_argument("--model-label", default="Qwen3.5-35B-A3B")
    args = parser.parse_args()

    job_dir = args.job_dir.resolve()
    dataset = args.dataset_path.resolve()
    if not job_dir.is_dir():
        raise SystemExit(f"job directory not found: {job_dir}")

    dataset_tasks = sorted(
        path.name for path in dataset.iterdir()
        if path.is_dir() and (path / "task.toml").is_file()
    )
    if len(dataset_tasks) != 89:
        raise SystemExit(f"expected 89 TB2 tasks, found {len(dataset_tasks)}")

    completed = set()
    preserved = set()
    rerun_reasons: dict[str, str] = {}
    for trial_dir in job_dir.iterdir():
        if not trial_dir.is_dir():
            continue
        result_path = next(
            (path for path in (trial_dir / "result.json", trial_dir / "results.json") if path.exists()),
            None,
        )
        if result_path is None:
            continue
        result = json.loads(result_path.read_text())
        task = str(result["task_name"]).removeprefix("terminal-bench/")
        completed.add(task)
        exception_type = (result.get("exception_info") or {}).get("exception_type")
        if exception_type == "AgentTimeoutError":
            preserved.add(task)
            continue
        if exception_type:
            rerun_reasons[task] = f"exception={exception_type}"
            continue

        timing = result.get("agent_execution") or {}
        try:
            duration = (
                datetime.fromisoformat(timing["finished_at"])
                - datetime.fromisoformat(timing["started_at"])
            ).total_seconds()
        except (KeyError, TypeError, ValueError):
            rerun_reasons[task] = "missing agent timing"
            continue
        task_config = tomllib.loads((dataset / task / "task.toml").read_text())
        official_timeout = float((task_config.get("agent") or {})["timeout_sec"])
        if duration > official_timeout + 5.0:
            rerun_reasons[task] = (
                f"duration={duration:.1f}s exceeds official timeout={official_timeout:.1f}s"
            )
        else:
            preserved.add(task)

    unknown = sorted(completed - set(dataset_tasks))
    if unknown:
        raise SystemExit("job contains unknown tasks: " + ", ".join(unknown))
    remaining = sorted(set(dataset_tasks) - preserved)

    destination = ROOT / "ICLR_results/terminalbench2/main/qwen35b/di__binf__fc"
    runner.BENCHMARK_VERSION = "2.0"
    runner.DATASET = "terminal-bench@2.0"
    current_rows, aggregate_rows = runner.collect_results(
        job_dir, destination, args.model_label, 1
    )
    if len(current_rows) != len(completed):
        raise SystemExit(
            f"collected {len(current_rows)} trials but found {len(completed)} completed tasks"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"dataset": "terminal-bench@2.0", "tasks": remaining}, indent=2) + "\n"
    )
    print(f"Completed trials found: {len(completed)}")
    print(f"Preserved trials: {len(preserved)}")
    print(f"Tasks to run at multiplier 1.0: {len(remaining)}")
    for task in sorted(rerun_reasons):
        print(f"  rerun {task}: {rerun_reasons[task]}")
    print(f"Aggregate: {destination / 'experiment_results.json'}")
    print(f"Task list: {args.output.resolve()}")


if __name__ == "__main__":
    main()
