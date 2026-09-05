#!/usr/bin/env python3
"""Collect Terminal-Bench 1.0 FC trajectories with rootless Podman.

The full 80-task, one-attempt Harbor job is stored in the canonical ICLR cell:

  ICLR_results/terminalbench/main/<model-key>/di__binf__fc/

Named subsets can be kept separate beneath the track directory, for example:

  ICLR_results/terminalbench/main/p80_rootless/<model-key>/di__binf__fc/
  ICLR_results/terminalbench/main/p80_subuid_required/<model-key>/di__binf__fc/

Harbor's raw job is retained outside ``ICLR_results`` under ``logs/harbor_jobs``.
Each trial's canonical artifacts are normalized to
``<task>/full-context/run_<N>``.  The aggregate keeps the same token fields as
the SWE-Bench runner, including ``step_prompt_tokens``.
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
BENCHMARK_VERSION = "1.0"
DEFAULT_DATASET_PATH = ROOT / "data" / "tb1-harbor-0.1.1"
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


def normalize_trial(
    trial_dir: Path, destination: Path, label: str, run_num: int
) -> dict[str, Any]:
    result_path = trial_dir / "result.json"
    if not result_path.exists():
        result_path = trial_dir / "results.json"
    result = json.loads(result_path.read_text())
    task = result["task_name"]
    output = destination / task / "full-context" / f"run_{run_num}"
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
        "key": f"{task}__full-context__r{run_num}",
        "benchmark": "terminal-bench",
        "benchmark_version": BENCHMARK_VERSION,
        "dataset": DATASET,
        "instance_id": task,
        "condition": "full-context",
        "primitive": "truncation",
        "budget": INF,
        "compression_ratio": 0.5,
        "is_baseline": True,
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
    row.update(token_log)
    row["llm_latency_s"] = token_log.get("total_latency_s", 0.0)
    return row


def collect_results(
    job_dir: Path, destination: Path, label: str, run_num: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trial_results = sorted((job_dir / "trials").glob("*/result.json"))
    if not trial_results:
        trial_results = sorted((job_dir / "trials").glob("*/results.json"))
    # Harbor 0.20 stores trial directories directly below the job directory;
    # older releases used a ``trials/`` intermediate directory.
    if not trial_results:
        trial_results = sorted(job_dir.glob("*/result.json"))
    if not trial_results:
        trial_results = sorted(job_dir.glob("*/results.json"))
    current_rows = [
        normalize_trial(path.parent, destination, label, run_num)
        for path in trial_results
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

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--run-num", type=int, default=1)
    parser.add_argument("--model-label", default=None)
    parser.add_argument("--agent-config", type=Path, required=True)
    parser.add_argument("--harbor-bin", type=Path, default=ROOT / "venv-harbor/bin/harbor")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="local Harbor-format Terminal-Bench 1.0.1 task directory",
    )
    parser.add_argument("--n-concurrent", type=int, default=4)
    parser.add_argument(
        "--agent-timeout-multiplier",
        type=float,
        default=1.0,
        help="multiply each task's agent timeout without changing verifier timeouts",
    )
    parser.add_argument(
        "--n-tasks",
        type=int,
        default=None,
        help="number of tasks (defaults to the task-list size, or 80 without a task list)",
    )
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=None,
        help="JSON task list: either an array of task names or an object with a 'tasks' array",
    )
    parser.add_argument(
        "--task-name",
        action="append",
        default=[],
        help="include a named task (repeatable; one name is useful for smoke testing)",
    )
    parser.add_argument(
        "--exclude-task-name",
        action="append",
        default=[],
        help="exclude a task from a provisional subset run (repeatable)",
    )
    parser.add_argument("--job-name", default=None)
    parser.add_argument(
        "--result-scope",
        choices=("p80_rootless", "p80_subuid_required"),
        default=None,
        help="optional result namespace beneath ICLR_results/terminalbench/main",
    )
    parser.add_argument("--docker-host", default=None,
                        help="rootless Podman API socket (default: /run/user/<uid>/podman/podman.sock)")
    parser.add_argument("--skip-postprocess", action="store_true")
    parser.add_argument("--expected-tasks", type=int, default=EXPECTED_TASKS)
    parser.add_argument("--benchmark-version", default=BENCHMARK_VERSION)
    parser.add_argument("--dataset-name", default=DATASET)
    parser.add_argument("--result-benchmark", default="terminalbench")
    parser.add_argument("--job-benchmark", default="terminalbench")
    parser.add_argument("--job-prefix", default="tb1")
    parser.add_argument("--display-name", default="Terminal-Bench 1.0")
    return parser.parse_args()


def main() -> None:
    global BENCHMARK_VERSION, DATASET
    args = parse_args()
    if args.expected_tasks < 1:
        raise SystemExit("--expected-tasks must be positive")
    BENCHMARK_VERSION = args.benchmark_version
    DATASET = args.dataset_name
    if not 1 <= args.run_num <= 5:
        raise SystemExit("--run-num must be between 1 and 5")
    if args.agent_timeout_multiplier <= 0:
        raise SystemExit("--agent-timeout-multiplier must be positive")
    config = args.agent_config.resolve()
    harbor = args.harbor_bin.resolve()
    dataset_path = args.dataset_path.resolve()
    if not config.is_file():
        raise SystemExit(f"agent config not found: {config}")
    if not harbor.is_file():
        raise SystemExit(f"Harbor executable not found: {harbor}")
    if not dataset_path.is_dir():
        raise SystemExit(
            f"Harbor-format Terminal-Bench dataset not found: {dataset_path}"
        )
    dataset_tasks = [
        path for path in dataset_path.iterdir()
        if path.is_dir() and (path / "task.toml").is_file()
    ]
    if len(dataset_tasks) != args.expected_tasks:
        raise SystemExit(
            f"Terminal-Bench dataset has {len(dataset_tasks)} tasks, "
            f"expected {args.expected_tasks}: {dataset_path}"
        )

    tasks_file = args.tasks_file.resolve() if args.tasks_file else None
    if tasks_file:
        if args.task_name or args.exclude_task_name:
            raise SystemExit(
                "--tasks-file cannot be combined with --task-name or --exclude-task-name"
            )
        if not tasks_file.is_file():
            raise SystemExit(f"task list not found: {tasks_file}")
        try:
            task_payload = json.loads(tasks_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"could not read task list {tasks_file}: {exc}") from exc
        task_names = task_payload.get("tasks") if isinstance(task_payload, dict) else task_payload
        if not isinstance(task_names, list) or not task_names:
            raise SystemExit("--tasks-file must contain a non-empty JSON 'tasks' array")
        if any(not isinstance(name, str) or not name for name in task_names):
            raise SystemExit("every entry in the task list must be a non-empty string")
        args.task_name = task_names

    selected_task_count = len(args.task_name) if args.task_name else args.expected_tasks
    if args.exclude_task_name:
        selected_task_count = args.expected_tasks - len(set(args.exclude_task_name))
    if args.n_tasks is None:
        args.n_tasks = selected_task_count
    if not 1 <= args.n_tasks <= args.expected_tasks:
        raise SystemExit(f"--n-tasks must be between 1 and {args.expected_tasks}")
    if args.task_name and args.exclude_task_name:
        raise SystemExit("--task-name and --exclude-task-name cannot be combined")
    if len(set(args.task_name)) != len(args.task_name):
        raise SystemExit("duplicate --task-name")
    if args.task_name and args.n_tasks != len(args.task_name):
        raise SystemExit("--n-tasks must equal the number of --task-name values")
    for task_name in args.task_name:
        if not (dataset_path / task_name).is_dir():
            raise SystemExit(f"task not found in dataset: {task_name}")
    for task_name in args.exclude_task_name:
        if not (dataset_path / task_name).is_dir():
            raise SystemExit(f"excluded task not found in dataset: {task_name}")
    expected_after_exclusions = args.expected_tasks - len(set(args.exclude_task_name))
    if args.exclude_task_name and args.n_tasks != expected_after_exclusions:
        raise SystemExit(
            "--n-tasks must equal the dataset size after exclusions: "
            f"expected {expected_after_exclusions}"
        )
    label = args.model_label or MODEL_LABELS.get(args.model_key)
    if not label:
        raise SystemExit("unknown --model-key: provide --model-label explicitly")

    model_name, api_base = load_model_config(config)
    result_root = ROOT / "ICLR_results" / args.result_benchmark / "main"
    if args.result_scope:
        result_root /= args.result_scope
    destination = result_root / args.model_key / "di__binf__fc"
    destination.mkdir(parents=True, exist_ok=True)
    # Keep infrastructure-specific Harbor state out of the canonical ICLR
    # results hierarchy documented in ICLR_results/README.md.
    jobs_dir = (
        ROOT / "logs" / "harbor_jobs" / args.job_benchmark / "main"
        / args.model_key / "di__binf__fc"
    )
    job_name = args.job_name or f"{args.job_prefix}-{args.model_key}-fc-run{args.run_num}"
    job_dir = jobs_dir / job_name
    docker_host = args.docker_host or f"unix:///run/user/{os.getuid()}/podman/podman.sock"

    env = os.environ.copy()
    env.update({
        "DOCKER_HOST": docker_host,
        # Docker Compose v5 otherwise delegates builds to a privileged buildx
        # container.  That container cannot create /sys/fs/cgroup/docker under
        # rootless Podman; use Podman's Docker-compatible build API directly.
        "COMPOSE_BAKE": "false",
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

    phase = "FC calibration" if args.run_num == 1 else "FC repetition"
    print(
        f"{phase}: {args.display_name}, {label}, "
        f"run_{args.run_num}, {args.n_tasks} tasks"
    )
    print(f"Output: {destination}")
    cmd = [
        str(harbor), "run",
        "--agent", "tbench.harbor_adapter:CompressionAgent",
        "--model", model_name,
        "--path", str(dataset_path),
        "--n-attempts", "1",
        "--n-tasks", str(args.n_tasks),
        "--n-concurrent", str(args.n_concurrent),
        "--agent-timeout-multiplier", str(args.agent_timeout_multiplier),
        "--env", "docker",
        "--cpus", "ignore",
        "--jobs-dir", str(jobs_dir),
        "--job-name", job_name,
        "--yes",
    ]
    for task_name in args.task_name:
        cmd.extend(["--include-task-name", task_name])
    for task_name in args.exclude_task_name:
        cmd.extend(["--exclude-task-name", task_name])
    # Harbor requires a model argument for bookkeeping; the adapter reads the
    # exact model/base URL from --agent-config. Export both LiteLLM aliases.
    env.setdefault("MSWEA_API_KEY", "EMPTY")
    env["OPENAI_BASE_URL"] = api_base
    env["OPENAI_API_BASE"] = api_base
    run(cmd, env=env)

    current_rows, aggregate_rows = collect_results(
        job_dir, destination, label, args.run_num
    )
    if len(current_rows) != args.n_tasks:
        raise SystemExit(
            f"Harbor produced {len(current_rows)} trial results, expected {args.n_tasks}; "
            f"raw job retained at {job_dir}"
        )
    current_names = {str(row["instance_id"]) for row in current_rows}
    run_rows = [row for row in aggregate_rows if int(row.get("run_num", 1)) == args.run_num]
    aggregate_names = {str(row["instance_id"]) for row in run_rows}
    dataset_names = {path.name for path in dataset_tasks}
    if args.task_name:
        expected_names = set(args.task_name)
    elif args.exclude_task_name:
        expected_names = dataset_names - set(args.exclude_task_name)
    else:
        expected_names = dataset_names
    unexpected_names = sorted(current_names - expected_names)
    if unexpected_names:
        raise SystemExit(
            "Harbor job contains tasks outside the selected task scope: "
            + ", ".join(unexpected_names)
        )
    missing_current_names = sorted(expected_names - current_names)
    if missing_current_names:
        raise SystemExit(
            "Harbor job is missing selected tasks: " + ", ".join(missing_current_names)
        )
    missing_names = sorted(dataset_names - aggregate_names)
    manifest = {
        "dataset": DATASET,
        "benchmark": args.result_benchmark,
        "track": "main",
        "result_scope": args.result_scope,
        "model_key": args.model_key,
        "cell": "di__binf__fc",
        "run_num": args.run_num,
        "completed_tasks": len(aggregate_names & dataset_names),
        "expected_tasks": len(dataset_names),
        "dataset_tasks": args.expected_tasks,
        "complete": not missing_names,
        "missing_tasks": missing_names,
        "tasks_file": str(tasks_file.relative_to(ROOT)) if tasks_file and tasks_file.is_relative_to(ROOT) else (str(tasks_file) if tasks_file else None),
        "raw_jobs_dir": str(jobs_dir.relative_to(ROOT)),
        "raw_jobs": sorted(path.name for path in jobs_dir.iterdir() if path.is_dir()),
    }
    (destination / "ICLR_CELL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        f"Collected this phase: {len(current_rows)}; "
        f"dataset run_{args.run_num}: {len(aggregate_names & dataset_names)}/{len(dataset_names)}; "
        f"all runs aggregate: {len(aggregate_rows)}"
    )

    if not args.skip_postprocess:
        run([sys.executable, str(ROOT / "dashboard/build_coverage.py")])
        run([sys.executable, str(ROOT / "dashboard/build_dashboard.py")])

    print(f"Aggregate: {destination / 'experiment_results.json'}")
    print(f"Raw Harbor job: {job_dir}")


if __name__ == "__main__":
    main()
