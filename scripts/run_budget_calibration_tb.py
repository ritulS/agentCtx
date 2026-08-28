#!/usr/bin/env python3
"""Collect Terminal-Bench 1.0 FC run_1 trajectories with rootless Podman.

The 80-task, one-attempt Harbor job is stored in the canonical ICLR cell:

  ICLR_results/terminalbench/main/<model-key>/di__binf__fc/

Harbor's raw job is retained under ``harbor_jobs`` and each trial's artifacts
are also normalized to ``<task>/full-context/run_1``.  The aggregate keeps the
same token fields as the SWE-Bench runner, including ``step_prompt_tokens``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
INF = 999_999_999
EXPECTED_TASKS = 80
DATASET = "terminal-bench-core@0.1.1"
DATASET_REPO = "harbor-framework/terminal-bench-1"
MODEL_LABELS = {
    "qwen35b": "Qwen3.5-35B-A3B",
    "devstral24b": "Devstral-Small-2-24B",
    "glm47flash": "GLM-4.7-Flash",
}


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def load_model_config(path: Path) -> tuple[str, str]:
    payload = yaml.safe_load(path.read_text()) or {}
    model = payload.get("model", {})
    name = model.get("model_name")
    base_url = model.get("model_kwargs", {}).get("api_base")
    if not name or not base_url:
        raise SystemExit("--agent-config must define model.model_name and model.model_kwargs.api_base")
    return str(name), str(base_url)


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


def normalize_trial(trial_dir: Path, destination: Path, label: str) -> dict[str, Any]:
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        result_path = trial_dir / "results.json"
    result = json.loads(result_path.read_text())
    task = result["task_name"]
    output = destination / task / "full-context" / "run_1"
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
        "key": f"{task}__full-context__r1",
        "benchmark": "terminal-bench",
        "benchmark_version": "1.0",
        "dataset": DATASET,
        "instance_id": task,
        "condition": "full-context",
        "primitive": "truncation",
        "budget": INF,
        "compression_ratio": 0.5,
        "is_baseline": True,
        "run_num": 1,
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
    row.update(token_log)
    row["llm_latency_s"] = token_log.get("total_latency_s", 0.0)
    return row


def collect_results(job_dir: Path, destination: Path, label: str) -> list[dict[str, Any]]:
    trial_results = sorted((job_dir / "trials").glob("*/result.json"))
    if not trial_results:
        trial_results = sorted((job_dir / "trials").glob("*/results.json"))
    rows = [normalize_trial(path.parent, destination, label) for path in trial_results]
    rows.sort(key=lambda row: row["instance_id"])
    (destination / "experiment_results.json").write_text(json.dumps(rows, indent=2))
    return rows


def write_calibration_report(model_key: str, destination: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "Review1" / "calibrate_budgets.py"),
        "--model-tag", model_key,
        "--results-file", str(destination / "experiment_results.json"),
        "--output", str(destination / "calibrated_budgets.sh"),
        "--distribution-output", str(destination / "fc_context_distribution.json"),
        "--run-num", "1",
    ]
    print("+", " ".join(cmd), flush=True)
    completed = subprocess.run(
        cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    (destination / "calibration_report.txt").write_text(completed.stdout)
    print(completed.stdout, end="")
    if completed.returncode:
        print("Calibration needs manual review; raw results and report were retained.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--model-label", default=None)
    parser.add_argument("--agent-config", type=Path, required=True)
    parser.add_argument("--harbor-bin", type=Path, default=ROOT / "venv-harbor/bin/harbor")
    parser.add_argument("--n-concurrent", type=int, default=4)
    parser.add_argument("--n-tasks", type=int, default=EXPECTED_TASKS,
                        help="debug-only prefix size; canonical run uses 80")
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--docker-host", default=None,
                        help="rootless Podman API socket (default: /run/user/<uid>/podman/podman.sock)")
    parser.add_argument("--skip-postprocess", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = args.agent_config.resolve()
    harbor = args.harbor_bin.resolve()
    if not config.is_file():
        raise SystemExit(f"agent config not found: {config}")
    if not harbor.is_file():
        raise SystemExit(f"Harbor executable not found: {harbor}")
    if not 1 <= args.n_tasks <= EXPECTED_TASKS:
        raise SystemExit("--n-tasks must be between 1 and 80")
    label = args.model_label or MODEL_LABELS.get(args.model_key)
    if not label:
        raise SystemExit("unknown --model-key: provide --model-label explicitly")

    model_name, api_base = load_model_config(config)
    destination = ROOT / "ICLR_results/terminalbench/main" / args.model_key / "di__binf__fc"
    destination.mkdir(parents=True, exist_ok=True)
    jobs_dir = destination / "harbor_jobs"
    job_name = args.job_name or f"tb1-{args.model_key}-fc-run1"
    job_dir = jobs_dir / job_name
    docker_host = args.docker_host or f"unix:///run/user/{os.getuid()}/podman/podman.sock"

    env = os.environ.copy()
    env.update({
        "DOCKER_HOST": docker_host,
        "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "mini-swe-agent/src"))),
        "MSWEA_PRIMITIVE": "truncation",
        "MSWEA_TOKEN_BUDGET": str(INF),
        "MSWEA_COMPRESSION_RATIO": "0.5",
        "MSWEA_COST_TRACKING": "ignore_errors",
        "MSWEA_TB_CONFIGS": os.pathsep.join((str(config), str(ROOT / "configs/config-tbench.yaml"))),
    })
    health = subprocess.run(
        ["docker", "info"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if health.returncode:
        raise SystemExit(
            f"rootless Podman API is not reachable through DOCKER_HOST={docker_host}; "
            "start `podman system service` first"
        )

    print(f"FC calibration: Terminal-Bench 1.0, {label}, {args.n_tasks} tasks")
    print(f"Output: {destination}")
    cmd = [
        str(harbor), "run",
        "--agent", "tbench.harbor_adapter:CompressionAgent",
        "--model", model_name,
        "--repo", DATASET_REPO,
        "--dataset", DATASET,
        "--n-attempts", "1",
        "--n-tasks", str(args.n_tasks),
        "--n-concurrent", str(args.n_concurrent),
        "--env", "docker",
        "--cpus", "ignore",
        "--jobs-dir", str(jobs_dir),
        "--job-name", job_name,
        "--yes",
    ]
    # Harbor requires a model argument for bookkeeping; the adapter reads the
    # exact model/base URL from --agent-config. Export both LiteLLM aliases.
    env.setdefault("MSWEA_API_KEY", "EMPTY")
    env["OPENAI_BASE_URL"] = api_base
    env["OPENAI_API_BASE"] = api_base
    run(cmd, env=env)

    rows = collect_results(job_dir, destination, label)
    if len(rows) != args.n_tasks:
        raise SystemExit(
            f"Harbor produced {len(rows)} trial results, expected {args.n_tasks}; "
            f"raw job retained at {job_dir}"
        )
    write_calibration_report(args.model_key, destination)
    if not args.skip_postprocess:
        run([sys.executable, str(ROOT / "scripts/build_coverage.py")])
        run([sys.executable, str(ROOT / "scripts/build_dashboard.py")])

    print(f"Aggregate: {destination / 'experiment_results.json'}")
    print(f"Context summary: {destination / 'fc_context_distribution.json'}")
    print(f"Raw Harbor job: {job_dir}")


if __name__ == "__main__":
    main()
