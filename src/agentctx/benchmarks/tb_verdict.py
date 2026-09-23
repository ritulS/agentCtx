"""Verdict semantics shared by the Terminal-Bench runners.

Harbor grades each trial inside the trial itself: the verifier runs in the
task container right after the agent, and the container is then deleted. Two
consequences drive everything in this module.

1. A trial without a verifier reward was never graded. That happens when the
   environment failed to start, the tests directory could not be copied, the
   job was cancelled, or the verifier timed out. Recording such a trial as
   ``resolved=False`` silently turns an evaluation error into a task failure
   (the same defect fixed for SWE-bench in ``swe_bench.py``). Here the row keeps
   ``resolved=None`` plus the Harbor exception, so the runner can re-run it and
   the analysis can tell "unverified" from "failed".
2. Because the container is gone, the only way to obtain a verdict later is to
   run the trial again, which regenerates the sample. Re-runs are therefore
   limited to failures unrelated to the agent's work (``DEFAULT_RETRY_EXCEPTIONS``).
   Verifier timeouts are kept as their own outcome (``verifier_timeout``), as in
   the original Terminal-Bench harness; add ``VerifierTimeoutError`` to
   ``TB_RETRY_EXCEPTIONS`` to re-run them instead.

The verifier thread cap mirrors ``scripts/swebench_eval_wrapper.py``: without
it, OpenMP/BLAS libraries spawn one thread per host core inside the task
container and small test suites spend their time in synchronisation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

DEFAULT_VERIFIER_THREADS = 8
# Harbor's --verifier-timeout-multiplier. Verifier timeouts on this host are
# dominated by dependency installation inside test.sh (apt/pip/uv), not by the
# agent's solution, so a larger multiplier does not change the generation and
# makes grading complete; the value is recorded on every row.
DEFAULT_VERIFIER_TIMEOUT_MULTIPLIER = 1.0
PYTEST_SUMMARY = re.compile(
    r"^=+ .*\b(passed|failed|error|errors|skipped|no tests ran)\b.* in [0-9.]+s.*=+$")
THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

# Harbor exception types after which the trial has no verdict for reasons
# unrelated to the agent's work. These are re-run by the runners.
DEFAULT_RETRY_EXCEPTIONS = frozenset({
    "EnvironmentStartTimeoutError",
    "EnvironmentBuildTimeoutError",
    "AgentSetupTimeoutError",
    "AddTestsDirError",
    "CancelledError",
})
# Harbor wraps some infrastructure failures in a bare RuntimeError; the
# message tells them apart from agent-side RuntimeErrors.
RETRYABLE_RUNTIME_ERROR_PREFIXES = ("Docker compose command failed",)

VERDICT_FIELDS = (
    "reward", "resolved", "verdict_source", "harbor_exception",
    "harbor_exception_message",
)


def task_name(result: dict[str, Any]) -> str:
    """Task name as a dataset directory name (Harbor may namespace it)."""
    return str(result.get("task_name") or "").rsplit("/", 1)[-1]


def reward_value(result: dict[str, Any]) -> float | None:
    rewards = (result.get("verifier_result") or {}).get("rewards")
    if not isinstance(rewards, dict) or not rewards:
        return None
    value = rewards.get("reward")
    if value is None and len(rewards) == 1:
        value = next(iter(rewards.values()))
    return float(value) if isinstance(value, (int, float)) else None


def exception_type(result: dict[str, Any]) -> str | None:
    info = result.get("exception_info")
    if not isinstance(info, dict):
        return None
    return info.get("exception_type") or None


def exception_message(result: dict[str, Any], limit: int = 200) -> str | None:
    info = result.get("exception_info")
    if not isinstance(info, dict):
        return None
    message = info.get("exception_message")
    if not message:
        return None
    message = str(message).splitlines()[0]
    return message[:limit]


def verdict_fields(result: dict[str, Any]) -> dict[str, Any]:
    """Row fields describing the verdict of one Harbor trial result.

    ``resolved`` is a bool only when the verifier produced a reward; otherwise
    it is None and ``verdict_source`` is "none".
    """
    reward = reward_value(result)
    return {
        "reward": reward,
        "resolved": (reward > 0) if reward is not None else None,
        "verdict_source": "verifier" if reward is not None else "none",
        "harbor_exception": exception_type(result),
        "harbor_exception_message": exception_message(result),
    }


def raw_trial_dir(result: dict[str, Any]) -> Path | None:
    """The Harbor trial directory a result.json came from (via trial_uri / config)."""
    uri = result.get("trial_uri") or ""
    if uri.startswith("file://"):
        path = Path(unquote(urlparse(uri).path))
        if path.is_dir():
            return path
    trials_dir = (result.get("config") or {}).get("trials_dir")
    name = result.get("trial_name")
    if trials_dir and name and (Path(trials_dir) / name).is_dir():
        return Path(trials_dir) / name
    return None


def reward_file_evidence(result: dict[str, Any], trial_dir: Path | None = None) -> dict[str, Any] | None:
    """A verifier verdict the container wrote although Harbor reported a timeout.

    The verifier directory is bind-mounted, so ``verifier/reward.txt`` is the
    container's own final write (every task's test.sh writes it from pytest's
    exit code as its last step). It is accepted only together with a pytest
    summary line at the end of ``test-stdout.txt``: the test session ran to
    completion and only Harbor's wait on the exec exceeded the limit.
    """
    trial = trial_dir if trial_dir is not None else raw_trial_dir(result)
    if trial is None:
        return None
    reward_path = trial / "verifier" / "reward.txt"
    stdout_path = trial / "verifier" / "test-stdout.txt"
    if not reward_path.is_file() or not stdout_path.is_file():
        return None
    try:
        reward = float(reward_path.read_text().strip())
    except ValueError:
        return None
    lines = [line.strip() for line in stdout_path.read_text(errors="replace").splitlines() if line.strip()]
    summary = next((line for line in reversed(lines[-5:]) if PYTEST_SUMMARY.match(line)), None)
    if summary is None:
        return None
    return {"trial_dir": str(trial), "reward_path": str(reward_path), "reward": reward,
            "reward_sha256": hashlib.sha256(reward_path.read_bytes()).hexdigest(),
            "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
            "pytest_summary": summary}


def trial_verdict(result: dict[str, Any], trial_dir: Path | None = None) -> dict[str, Any]:
    """``verdict_fields`` plus recovery of a reward file Harbor failed to parse.

    When Harbor reports ``VerifierTimeoutError`` but the verifier wrote its
    reward (see ``reward_file_evidence``), the trial is graded after all: the
    row gets that reward with ``verdict_source="verifier_reward_file"`` and the
    evidence under ``reward_file``. ``harbor_exception`` keeps the timeout.
    """
    fields = verdict_fields(result)
    if fields["reward"] is not None or fields["harbor_exception"] != "VerifierTimeoutError":
        return fields
    evidence = reward_file_evidence(result, trial_dir)
    if evidence is None:
        return fields
    fields.update({"reward": evidence["reward"], "resolved": evidence["reward"] > 0,
                   "verdict_source": "verifier_reward_file", "reward_file": evidence})
    return fields


def has_verdict(row: dict[str, Any]) -> bool:
    return row.get("reward") is not None or isinstance(row.get("resolved"), bool)


def retry_exceptions_from_env(
    variable: str = "TB_RETRY_EXCEPTIONS",
    default: Iterable[str] = DEFAULT_RETRY_EXCEPTIONS,
) -> frozenset[str]:
    """Exception types to re-run; ``TB_RETRY_EXCEPTIONS`` adds to the default.

    Prefix an entry with "-" to remove it from the default set, e.g.
    ``TB_RETRY_EXCEPTIONS=VerifierTimeoutError,-CancelledError``.
    """
    names = set(default)
    for item in os.environ.get(variable, "").split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("-"):
            names.discard(item[1:])
        else:
            names.add(item)
    return frozenset(names)


def is_retryable(
    exception: str | None,
    message: str | None,
    retry_exceptions: Iterable[str] = DEFAULT_RETRY_EXCEPTIONS,
) -> bool:
    if not exception:
        return False
    if exception in retry_exceptions:
        return True
    if exception == "RuntimeError" and message:
        return message.startswith(RETRYABLE_RUNTIME_ERROR_PREFIXES)
    return False


def needs_rerun(
    row: dict[str, Any],
    retry_exceptions: Iterable[str] = DEFAULT_RETRY_EXCEPTIONS,
) -> bool:
    """True for a saved row that has no verdict and failed for a retryable reason."""
    if has_verdict(row):
        return False
    return is_retryable(
        row.get("harbor_exception"), row.get("harbor_exception_message"),
        retry_exceptions,
    )


def verifier_timeout_multiplier(value: float | None = None) -> float:
    """Multiplier for Harbor's verifier timeout (``TB_VERIFIER_TIMEOUT_MULTIPLIER``)."""
    if value is None:
        value = float(os.environ.get("TB_VERIFIER_TIMEOUT_MULTIPLIER", DEFAULT_VERIFIER_TIMEOUT_MULTIPLIER))
    if value <= 0:
        raise ValueError(f"verifier timeout multiplier must be positive, got {value}")
    return value


def verifier_timeout_args(value: float | None = None) -> list[str]:
    return ["--verifier-timeout-multiplier", str(verifier_timeout_multiplier(value))]


def verifier_env_args(threads: int | None = None) -> list[str]:
    """``harbor run`` arguments capping OpenMP/BLAS threads inside the verifier."""
    if threads is None:
        threads = int(os.environ.get("TB_VERIFIER_THREADS", DEFAULT_VERIFIER_THREADS))
    if threads < 1:
        raise ValueError(f"verifier thread cap must be positive, got {threads}")
    args: list[str] = []
    for key in THREAD_ENV_KEYS:
        args.extend(("--verifier-env", f"{key}={threads}"))
    return args


def trial_result_files(job_dir: Path) -> list[Path]:
    """Trial result files below a Harbor job directory (0.20 layout or older)."""
    for root in (job_dir / "trials", job_dir):
        for filename in ("result.json", "results.json"):
            paths = sorted(root.glob(f"*/{filename}"))
            if paths:
                return paths
    return []


def select_trials(
    job_dir: Path, task_names: Iterable[str] | None = None
) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    """Pick one trial result per task from a job directory.

    When a task has several trials (relaunched job, Harbor retries), the trial
    with a verifier verdict wins; among equals the most recently finished one.
    Returns ``(selected, duplicates)`` where ``duplicates`` lists the rejected
    result files per task.
    """
    wanted = set(task_names) if task_names is not None else None
    best: dict[str, tuple[tuple, Path]] = {}
    duplicates: dict[str, list[Path]] = {}
    for path in trial_result_files(job_dir):
        try:
            result = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        task = task_name(result)
        if not task or (wanted is not None and task not in wanted):
            continue
        rank = (
            reward_value(result) is not None,
            str(result.get("finished_at") or ""),
            str(result.get("started_at") or ""),
        )
        if task not in best:
            best[task] = (rank, path)
            continue
        if rank > best[task][0]:
            duplicates.setdefault(task, []).append(best[task][1])
            best[task] = (rank, path)
        else:
            duplicates.setdefault(task, []).append(path)
    return {task: path for task, (_, path) in best.items()}, duplicates
