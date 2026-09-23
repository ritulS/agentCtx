#!/usr/bin/env python3
"""Collect Terminal-Bench 1.0 FC trajectories with rootless Podman.

The full 80-task, one-attempt Harbor job is stored in the canonical ICLR cell:

  ICLR_experiments/terminalbench/main/<model-key>/di__binf__fc/

Named subsets can be kept separate beneath the track directory, for example:

  ICLR_experiments/terminalbench/main/p80_rootless/<model-key>/di__binf__fc/
  ICLR_experiments/terminalbench/main/p80_subuid_required/<model-key>/di__binf__fc/

Harbor's raw job is retained outside ``ICLR_experiments`` under ``logs/harbor_jobs``.
Each trial's canonical artifacts are normalized to
``<task>/full-context/run_<N>``.  The aggregate keeps the same token fields as
the SWE-Bench runner, including ``step_prompt_tokens``. Conversion and result
merging live in ``agentctx.benchmarks.harbor_results``.

Use --calibration-dir for an isolated collection outside ICLR_experiments. Both
normalized results and raw Harbor state stay there; dashboard updates are disabled.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTCTX_SRC = ROOT / "src"
if str(AGENTCTX_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTCTX_SRC))

# Support both direct CLI execution and import through scripts.calibration.*.
if __package__:
    from .log_vllm_prefix_cache import PrefixCacheRecorder
else:
    from log_vllm_prefix_cache import PrefixCacheRecorder

from agentctx import INFINITE_BUDGET  # noqa: E402
from agentctx.benchmarks import harbor_results  # noqa: E402
from agentctx.benchmarks.harbor_results import collect_results  # noqa: E402
from agentctx.benchmarks.tb_verdict import (  # noqa: E402
    verifier_env_args, verifier_timeout_args, verifier_timeout_multiplier,
)


# Set by main() from --verifier-timeout-multiplier; None = TB_VERIFIER_TIMEOUT_MULTIPLIER / 1.0.
VERIFIER_TIMEOUT_MULTIPLIER: float | None = None
EXPECTED_TASKS = 80
# Overridden by --dataset-name / --benchmark-version (TB2 launchers) and read
# by prepare_tb2_fc_resume.py; the defaults are the shared TB1 constants.
DATASET = harbor_results.DATASET
BENCHMARK_VERSION = harbor_results.BENCHMARK_VERSION
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
        "--verifier-timeout-multiplier",
        type=float,
        default=None,
        help="multiply each task's verifier timeout (default: TB_VERIFIER_TIMEOUT_MULTIPLIER or 1.0); "
             "verifier timeouts here are dominated by dependency installs in test.sh",
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
        "--calibration-dir", type=Path, default=None,
        help="isolated collection directory outside ICLR_experiments (also disables postprocess)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate inputs and print paths/command without writing files or running Harbor",
    )
    parser.add_argument(
        "--metrics-url", default=None,
        help="vLLM metrics URL override; isolated calibration records /metrics automatically",
    )
    parser.add_argument(
        "--result-scope",
        choices=("p80_rootless", "p80_subuid_required"),
        default=None,
        help="optional result namespace beneath ICLR_experiments/terminalbench/main",
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
    global VERIFIER_TIMEOUT_MULTIPLIER
    try:
        VERIFIER_TIMEOUT_MULTIPLIER = verifier_timeout_multiplier(args.verifier_timeout_multiplier)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
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
    result_root = ROOT / "ICLR_experiments" / args.result_benchmark / "main"
    if args.result_scope:
        result_root /= args.result_scope
    destination = result_root / args.model_key / "di__binf__fc"
    # Keep infrastructure-specific Harbor state out of the canonical ICLR
    # results hierarchy documented in ICLR_experiments/README.md.
    jobs_dir = (
        ROOT / "logs" / "harbor_jobs" / args.job_benchmark / "main"
        / args.model_key / "di__binf__fc"
    )
    job_name = args.job_name or f"{args.job_prefix}-{args.model_key}-fc-run{args.run_num}"
    if Path(job_name).name != job_name or job_name in (".", ".."):
        raise SystemExit("--job-name must be a single directory name")
    if args.calibration_dir:
        if args.result_scope:
            raise SystemExit("--calibration-dir cannot be combined with --result-scope")
        calibration_dir = args.calibration_dir.resolve()
        destination = (calibration_dir / "results").resolve()
        jobs_dir = (calibration_dir / "harbor_jobs").resolve()
        # Resolve symlinks as well: neither results nor infrastructure state
        # may enter the canonical tree, even through an existing directory link.
        protected = (ROOT / "ICLR_experiments").resolve()
        for path in (calibration_dir, destination, jobs_dir, (jobs_dir / job_name).resolve()):
            if path.is_relative_to(protected) or protected.is_relative_to(path):
                raise SystemExit("--calibration-dir must be separate from ICLR_experiments")
        args.skip_postprocess = True
    elif args.metrics_url:
        raise SystemExit("--metrics-url requires --calibration-dir")
    job_dir = jobs_dir / job_name
    metrics_recorder = None
    if args.calibration_dir:
        base = urlsplit(api_base)
        metrics_url = args.metrics_url or urlunsplit((base.scheme, base.netloc, "/metrics", "", ""))
        metrics_recorder = PrefixCacheRecorder(
            metrics_url, calibration_dir / "metrics" / job_name / "prefix_cache.jsonl",
        )
    docker_host = args.docker_host or f"unix:///run/user/{os.getuid()}/podman/podman.sock"

    env = os.environ.copy()
    env.update({
        "DOCKER_HOST": docker_host,
        # Docker Compose v5 otherwise delegates builds to a privileged buildx
        # container.  That container cannot create /sys/fs/cgroup/docker under
        # rootless Podman; use Podman's Docker-compatible build API directly.
        "COMPOSE_BAKE": "false",
        "PYTHONPATH": os.pathsep.join((
            str(ROOT / "src"), str(ROOT), str(ROOT / "mini-swe-agent/src")
        )),
        "MSWEA_PRIMITIVE": "truncation",
        "MSWEA_TOKEN_BUDGET": str(INFINITE_BUDGET),
        "MSWEA_COMPRESSION_RATIO": "0.5",
        "MSWEA_COST_TRACKING": "ignore_errors",
        "MSWEA_TB_CONFIGS": os.pathsep.join((str(config), str(ROOT / "configs/config-tbench.yaml"))),
    })
    phase = "FC calibration" if args.run_num == 1 else "FC repetition"
    print(
        f"{phase}: {args.display_name}, {label}, "
        f"run_{args.run_num}, {args.n_tasks} tasks"
    )
    print(f"Output: {destination}")
    print(f"Raw Harbor job: {job_dir}")
    print(f"Verifier timeout multiplier: {VERIFIER_TIMEOUT_MULTIPLIER}")
    print(f"Postprocess: {'disabled' if args.skip_postprocess else 'enabled'}")
    if metrics_recorder:
        print(f"Prefix-cache metrics: {metrics_recorder.url} -> {metrics_recorder.output} (every 10s)")
    cmd = [
        str(harbor), "run",
        "--agent", "agentctx.benchmarks.harbor_adapter:CompressionAgent",
        "--model", model_name,
        "--path", str(dataset_path),
        "--n-attempts", "1",
        "--max-retries", "0",
        "--n-tasks", str(args.n_tasks),
        "--n-concurrent", str(args.n_concurrent),
        "--agent-timeout-multiplier", str(args.agent_timeout_multiplier),
        *verifier_timeout_args(VERIFIER_TIMEOUT_MULTIPLIER),
        "--env", "docker",
        "--cpus", "ignore",
        "--jobs-dir", str(jobs_dir),
        "--job-name", job_name,
        "--yes",
        # Cap OpenMP/BLAS threads inside the verifier (see tb_verdict.py).
        *verifier_env_args(),
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
    if args.dry_run:
        import shlex

        print("+", shlex.join(cmd))
        return
    health = subprocess.run(
        ["docker", "info"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if health.returncode:
        raise SystemExit(
            f"rootless Podman API is not reachable through DOCKER_HOST={docker_host}; "
            "start `podman system service` first"
        )
    destination.mkdir(parents=True, exist_ok=True)
    with metrics_recorder if metrics_recorder else nullcontext():
        run(cmd, env=env)

    current_rows, aggregate_rows = collect_results(
        job_dir, destination, label, args.run_num,
        benchmark_version=BENCHMARK_VERSION,
        dataset=DATASET,
        workspace_root=ROOT,
        verifier_timeout_multiplier=VERIFIER_TIMEOUT_MULTIPLIER,
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
        "track": "calibration" if args.calibration_dir else "main",
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
        "raw_jobs_dir": str(jobs_dir.relative_to(ROOT)) if jobs_dir.is_relative_to(ROOT) else str(jobs_dir),
        "raw_jobs": sorted(path.name for path in jobs_dir.iterdir() if path.is_dir()),
    }
    manifest_name = "CALIBRATION_MANIFEST.json" if args.calibration_dir else "ICLR_CELL_MANIFEST.json"
    (destination / manifest_name).write_text(
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
