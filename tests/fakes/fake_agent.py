#!/usr/bin/env python3
"""Stand-in for ``venv/bin/python`` as launched by the SWE-bench adapter.

Two ``-m`` entry points are emulated:

  minisweagent.run.benchmarks.swebench_single  writes trajectory.json and the
                                               token log at MSWEA_TOKEN_LOG_PATH
  swebench.harness.run_evaluation              writes the harness report

Every artifact is a pure function of argv and the MSWEA_* environment, so two
runners that build the same invocation get byte-identical files. The
invocation itself (argv, cwd, selected env) is recorded beside the outputs so
tests compare what the runner asked for, not only what came back.

The instance id selects the outcome: ``-crash`` exits 3 without writing a
trajectory, ``-nopatch`` finishes without a submission, anything else submits.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

RECORDED_ENV_PREFIXES = ("MSWEA_",)
RECORDED_ENV_KEYS = ("DOCKER_HOST", "PYTHONPATH", "PATH")


def option(argv: list[str], name: str) -> str | None:
    try:
        return argv[argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


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


def record(path: Path, argv: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "argv": argv,
        "cwd": os.getcwd(),
        "env": recorded_environment(),
    }, indent=2, sort_keys=True))


def run_agent(argv: list[str]) -> int:
    instance = option(argv, "--instance") or "unknown"
    trajectory = Path(option(argv, "-o") or "trajectory.json")
    record(trajectory.parent / "invocation.json", argv)

    if instance.endswith("-crash"):
        print(f"fake agent crashed on {instance}")
        return 3

    env = os.environ
    s = seed(
        instance,
        env.get("MSWEA_PRIMITIVE"),
        env.get("MSWEA_TOKEN_BUDGET"),
        env.get("MSWEA_COMPRESSION_RATIO"),
        env.get("MSWEA_RUN_KEY"),
    )
    budget = int(env.get("MSWEA_TOKEN_BUDGET") or 0)
    n_calls = 5 + s % 40
    events = 0 if budget >= 999_999_999 else 1 + s % 3
    step_tokens = [1000 + (s * (i + 1)) % 9000 for i in range(n_calls)]
    token_log = {
        "total_prompt_tokens": sum(step_tokens),
        "total_completion_tokens": 40 * n_calls,
        "total_tokens": sum(step_tokens) + 40 * n_calls,
        "total_latency_s": round(n_calls * 1.5, 2),
        "mean_latency_s": 1.5,
        "step_prompt_tokens": step_tokens,
        "compression_events": events,
        "compression_event_steps": [3 * (i + 1) for i in range(events)],
        "context_tokens_at_compression": [budget + 500 + i for i in range(events)],
        "context_tokens_after_compression": [budget // 2 + i for i in range(events)],
        "total_tokens_saved": events * (budget // 2 + 500),
        "mean_compression_ratio": 0.5 if events else 1.0,
        "summarization_prompt_tokens": 0,
        "summarization_latency_s": 0.0,
        "trc_truncation_fallback_events": 0,
        "online_trc_total_tokens_saved": 0,
        "online_trc_clears": 0,
        "online_trc_flags": [],
    }
    token_log_path = env.get("MSWEA_TOKEN_LOG_PATH")
    if token_log_path:
        Path(token_log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(token_log_path).write_text(json.dumps(token_log, indent=2))

    if instance.endswith("-nopatch"):
        exit_status, submission = "LimitsExceeded", ""
    else:
        exit_status = "Submitted"
        submission = (
            f"diff --git a/{instance}.py b/{instance}.py\n"
            f"--- a/{instance}.py\n+++ b/{instance}.py\n"
            f"@@ -1 +1 @@\n-pass\n+fix = {s % 1000}\n"
        )
    trajectory.parent.mkdir(parents=True, exist_ok=True)
    trajectory.write_text(json.dumps({
        "info": {
            "exit_status": exit_status,
            "submission": submission,
            "model_stats": {"api_calls": n_calls},
        },
        "messages": [],
    }, indent=2))
    print(f"fake agent finished {instance} with {exit_status}")
    return 0


def run_evaluation(argv: list[str]) -> int:
    predictions = json.loads(Path(option(argv, "--predictions_path")).read_text())
    instance = option(argv, "--instance_ids")
    run_id = option(argv, "--run_id")
    report_dir = Path(option(argv, "--report_dir"))
    report_dir.mkdir(parents=True, exist_ok=True)
    record(report_dir / f"invocation_{run_id}.json", argv)

    prediction = predictions[instance]
    resolved = seed(instance, prediction["model_patch"]) % 2 == 0
    report = {
        "resolved_ids": [instance] if resolved else [],
        "unresolved_ids": [] if resolved else [instance],
        "schema_version": 2,
    }
    (report_dir / f"{prediction['model_name_or_path']}.{run_id}.json").write_text(
        json.dumps(report, indent=2)
    )
    return 0


def main() -> int:
    argv = sys.argv[1:]
    module = option(argv, "-m")
    if module == "minisweagent.run.benchmarks.swebench_single":
        return run_agent(argv)
    if module == "swebench.harness.run_evaluation":
        return run_evaluation(argv)
    print(f"fake_agent: unsupported invocation {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
