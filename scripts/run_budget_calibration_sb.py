#!/usr/bin/env python3
"""Collect SWE-Bench (SB) FC run_1 trajectories for budget calibration.

These are not calibration-only duplicate runs. They are written directly to
the canonical FC cell and count as run_1 of FOLLOWUP_EXPERIMENTS 2.a/2.b:

  ICLR_results/swebench/main/<model-key>/di__binf__fc/

After a successful run, COVERAGE.csv and DASHBOARD.html are rebuilt.  The
per-step ``step_prompt_tokens`` arrays, raw artifacts, and a machine-readable
context-length distribution are retained in that cell.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INF = 999_999_999
DEFAULT_TASKS = ROOT / "task_lists" / "p100_all_100_tasks.json"
MODEL_LABELS = {
    "qwen35b": "Qwen3.5-35B-A3B",
    "devstral24b": "Devstral-Small-2-24B",
    "glm47flash": "GLM-4.7-Flash",
}


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def write_calibration_report(model_key: str, destination: Path) -> None:
    cmd = [
        sys.executable, str(ROOT / "Review1" / "calibrate_budgets.py"),
        "--model-tag", model_key,
        "--results-file", str(destination / "experiment_results.json"),
        "--output", str(destination / "calibrated_budgets.sh"),
        "--distribution-output", str(destination / "fc_context_distribution.json"),
        "--run-num", "1",
    ]
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (destination / "calibration_report.txt").write_text(result.stdout)
    print(result.stdout, end="")
    if result.returncode:
        print("Calibration needs manual review; raw results and report were retained.")


def annotate_swebench_model(destination: Path, label: str) -> None:
    path = destination / "experiment_results.json"
    payload = json.loads(path.read_text())
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    for row in rows:
        row["model"] = label
        row["agent_model"] = label
    path.write_text(json.dumps(payload, indent=2))


def task_count(path: Path) -> int:
    payload = json.loads(path.read_text())
    tasks = payload.get("tasks", payload.get("instances", [])) if isinstance(payload, dict) else payload
    return len(tasks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True,
                        help="canonical directory key, e.g. devstral24b or glm47flash")
    parser.add_argument("--model-label", default=None,
                        help="COVERAGE/dashboard model label (known model keys are automatic)")
    parser.add_argument("--agent-config", type=Path, required=True,
                        help="agent/model YAML, including model_name and api_base")
    parser.add_argument("--tasks-file", type=Path, default=None)
    parser.add_argument("--n-tasks", type=int, default=None,
                        help="use only the first N tasks (main calibration normally uses all tasks)")
    parser.add_argument("--max-workers", type=int, default=16,
                        help="SWE-Bench concurrency")
    parser.add_argument("--skip-eval", action="store_true",
                        help="skip SWE-Bench patch evaluation (the FC runs remain reusable, but unresolved)")
    parser.add_argument("--skip-postprocess", action="store_true",
                        help="do not rebuild COVERAGE.csv and DASHBOARD.html")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = args.agent_config.resolve()
    tasks = (args.tasks_file or DEFAULT_TASKS).resolve()
    if not config.is_file():
        raise SystemExit(f"agent config not found: {config}")
    if not tasks.is_file():
        raise SystemExit(f"tasks file not found: {tasks}")
    if args.n_tasks is not None and not 1 <= args.n_tasks <= task_count(tasks):
        raise SystemExit("--n-tasks must be between 1 and the number of tasks in --tasks-file")

    label = args.model_label or MODEL_LABELS.get(args.model_key)
    if not label:
        raise SystemExit("unknown --model-key: provide --model-label explicitly")

    destination = (
        ROOT / "ICLR_results" / "swebench" / "main" /
        args.model_key / "di__binf__fc"
    )
    selected_count = args.n_tasks or task_count(tasks)
    print(f"FC calibration: SWE-Bench, {label}, {selected_count} tasks")
    if selected_count != 100:
        print("NOTE: this is a partial calibration run; it does not cover the full SB:P100 cell.")
    print(f"Output: {destination}")

    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_experiment_iclr.py"),
        "--iclr-section", "main",
        "--iclr-model", args.model_key,
        "--iclr-cell", "di__binf__fc",
        "--model-tag", args.model_key,
        "--agent-config", str(config),
        "--tasks-file", str(tasks),
        "--conditions", "full-context",
        "--budget", str(INF),
        "--depth", "0.5",
        "--runs-per-task", "1",
        "--max-workers", str(args.max_workers),
    ]
    if args.n_tasks is not None:
        cmd.extend(("--n-tasks", str(args.n_tasks)))
    if not args.skip_eval:
        cmd.append("--with-eval")
    run(cmd)
    annotate_swebench_model(destination, label)

    write_calibration_report(args.model_key, destination)

    if not args.skip_postprocess:
        run([sys.executable, str(ROOT / "scripts" / "build_coverage.py")])
        run([sys.executable, str(ROOT / "scripts" / "build_dashboard.py")])

    print(f"Raw distribution: {destination / 'experiment_results.json'}")
    print(f"Context summary: {destination / 'fc_context_distribution.json'}")
    print(f"Calibration report: {destination / 'calibration_report.txt'}")


if __name__ == "__main__":
    main()
