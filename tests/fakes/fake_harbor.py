#!/usr/bin/env python3
"""Stand-in for ``venv-harbor/bin/harbor run`` as launched by the Terminal-Bench adapter.

Creates the job directory Harbor would have produced, one trial per
``--include-task-name``, with deterministic artifacts derived from the task
name and the MSWEA_* environment. The invocation (argv, cwd, selected env) is
recorded in the job directory so tests can compare it.

The task name selects the outcome: ``-fail`` is graded with reward 0,
``-timeout`` has no verifier result and ends with AgentTimeoutError,
anything else is graded with reward 1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

RECORDED_ENV_PREFIXES = ("MSWEA_", "OPENAI_")
RECORDED_ENV_KEYS = ("DOCKER_HOST", "COMPOSE_BAKE", "PYTHONPATH", "PATH")
EPOCH = datetime(2026, 1, 1, 0, 0, 0)


def option(argv: list[str], name: str) -> str | None:
    try:
        return argv[argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


def options(argv: list[str], name: str) -> list[str]:
    return [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == name]


def seed(*parts) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
    return int(digest[:12], 16)


def recorded_environment() -> dict[str, str]:
    env = os.environ
    return {
        key: env[key]
        for key in sorted(env)
        if key.startswith(RECORDED_ENV_PREFIXES) or key in RECORDED_ENV_KEYS
    }


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def write_trial(job_dir: Path, task: str, index: int) -> None:
    env = os.environ
    # Seed only from values that are identical across sandboxes: anything that
    # embeds a path (MSWEA_TB_CONFIGS, jobs dir) would make the two sides differ.
    s = seed(
        task,
        env.get("MSWEA_PRIMITIVE"),
        env.get("MSWEA_TOKEN_BUDGET"),
        env.get("MSWEA_COMPRESSION_RATIO"),
        Path(env.get("MSWEA_TB_CONFIGS", "").split(os.pathsep)[0]).name,
    )
    trial_dir = job_dir / "trials" / f"{task}__1"
    started = EPOCH + timedelta(minutes=index)
    agent_finished = started + timedelta(seconds=30 + s % 600)
    finished = agent_finished + timedelta(seconds=5)
    n_calls = 4 + s % 30
    budget = int(env.get("MSWEA_TOKEN_BUDGET") or 0)
    events = 0 if budget >= 999_999_999 else 1 + s % 2

    if task.endswith("-timeout"):
        exit_status = "AgentTimeoutError"
        verifier_result = None
        exception_info = {
            "exception_type": "AgentTimeoutError",
            "exception_message": "agent exceeded its time limit",
        }
    else:
        exit_status = "Submitted"
        reward = 0.0 if task.endswith("-fail") else 1.0
        verifier_result = {"rewards": {"reward": reward}}
        exception_info = None

    write_json(trial_dir / "result.json", {
        "task_name": task,
        "trial_name": trial_dir.name,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "agent_execution": {
            "started_at": started.isoformat(),
            "finished_at": agent_finished.isoformat(),
        },
        "verifier_result": verifier_result,
        "exception_info": exception_info,
    })
    write_json(trial_dir / "agent" / "trajectory.json", {
        "info": {"exit_status": exit_status, "model_stats": {"api_calls": n_calls}},
        "messages": [],
    })
    write_json(trial_dir / "agent" / "token_log.json", {
        "total_prompt_tokens": 1200 * n_calls + s % 500,
        "total_completion_tokens": 35 * n_calls,
        "total_tokens": 1235 * n_calls + s % 500,
        "total_latency_s": round(n_calls * 1.25, 2),
        "mean_latency_s": 1.25,
        "compression_events": events,
        "compression_event_steps": [2 * (i + 1) for i in range(events)],
        "total_tokens_saved": events * (budget // 2),
    })
    write_json(trial_dir / "agent" / "exit_info.json", {
        "exit_status": exit_status,
        "n_calls": n_calls,
        "primitive": env.get("MSWEA_PRIMITIVE", ""),
        "token_budget": env.get("MSWEA_TOKEN_BUDGET", ""),
        "compression_ratio": env.get("MSWEA_COMPRESSION_RATIO", ""),
    })
    (trial_dir / "trial.log").write_text(f"fake harbor trial for {task}: {exit_status}\n")


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] != "run":
        print(f"fake_harbor: unsupported invocation {argv}", file=sys.stderr)
        return 2
    jobs_dir = Path(option(argv, "--jobs-dir") or "jobs")
    job_name = option(argv, "--job-name") or "job"
    job_dir = jobs_dir / job_name
    job_dir.mkdir(parents=True, exist_ok=True)

    tasks = options(argv, "--include-task-name")
    dataset = Path(option(argv, "--path") or ".")
    missing = [task for task in tasks if not (dataset / task).is_dir()]
    if missing:
        print(f"fake_harbor: tasks not in dataset: {missing}", file=sys.stderr)
        return 1

    write_json(job_dir / "invocation.json", {
        "argv": argv,
        "cwd": os.getcwd(),
        "env": recorded_environment(),
    })
    for index, task in enumerate(tasks):
        write_trial(job_dir, task, index)
    write_json(job_dir / "result.json", {
        "job_name": job_name,
        "n_trials": len(tasks),
        "started_at": EPOCH.isoformat(),
        "finished_at": (EPOCH + timedelta(minutes=len(tasks) + 1)).isoformat(),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
