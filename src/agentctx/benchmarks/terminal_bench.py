"""Terminal-Bench execution through Harbor for the experiment runner."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Any

import yaml

from .harbor_results import normalize_trial
from .results import run_key
from .tb_verdict import (
    needs_rerun,
    retry_exceptions_from_env,
    select_trials,
    trial_result_files,
    verifier_env_args,
    verifier_timeout_args,
)


class TerminalBench:
    """Adapter between the generic experiment runner and Harbor batches.

    Verdict handling (see ``tb_verdict.py``): a trial without a verifier reward
    is saved with ``resolved=None`` and its Harbor exception, never as a
    failure. A verifier timeout whose reward file was nevertheless written is
    graded from that file. Rows whose exception is infrastructure-related are
    re-run up to ``TB_MAX_BATCH_ATTEMPTS`` times (default 3); earlier attempts
    are kept next to the run directory as ``run_<n>.superseded.<k>``.
    ``TB_VERIFIER_TIMEOUT_MULTIPLIER`` (default 1.0) is passed to Harbor and
    recorded on every row.
    """

    name = "terminal-bench"
    benchmark_version = "1.0"
    dataset_name = "terminal-bench-core@0.1.1"
    agent_import_path = (
        "agentctx.benchmarks.harbor_adapter:CompressionAgent"
    )

    def __init__(self, workspace_root: Path, model_tag: str, results_dir: Path):
        self.workspace_root = workspace_root
        self.model_tag = model_tag
        self.results_dir = results_dir
        self.harbor = workspace_root / "venv-harbor" / "bin" / "harbor"
        self.dataset_path = workspace_root / "data" / "tb1-harbor-0.1.1"
        self.jobs_dir = (
            workspace_root / "logs" / "harbor_jobs" / "terminalbench" / model_tag
        )
        self.tb_config = workspace_root / "configs" / "config-tbench.yaml"
        self.docker_host = (
            f"unix:///run/user/{os.getuid()}/podman/podman.sock"
        )

    def load_tasks(
        self,
        tasks_file: Path,
        *,
        tasks_file_explicit: bool,
        ablation_name: str | None,
        ablation_tasks_file: Path,
        n_tasks: int,
        n_tasks_override: int | None,
    ) -> list[dict]:
        """Load task names from JSON or enumerate the local Harbor dataset."""
        if ablation_name:
            raise SystemExit("--ablation is not yet supported for terminal-bench")
        if not self.dataset_path.is_dir():
            raise SystemExit(
                f"Harbor-format Terminal-Bench dataset not found: {self.dataset_path}"
            )

        available = sorted(path.name for path in self.dataset_path.iterdir() if path.is_dir())
        if tasks_file_explicit:
            if not tasks_file.is_file():
                raise SystemExit(f"Terminal-Bench task list not found: {tasks_file}")
            payload = json.loads(tasks_file.read_text())
            names = payload.get("tasks") if isinstance(payload, dict) else payload
            if not isinstance(names, list) or not names:
                raise SystemExit(
                    "Terminal-Bench task file must contain a non-empty JSON array "
                    "or an object with a 'tasks' array"
                )
            if any(not isinstance(name, str) or not name for name in names):
                raise SystemExit("Terminal-Bench task names must be non-empty strings")
        else:
            # The generic runner's default is 100 SWE-bench tasks. Terminal-Bench
            # has fewer tasks, so an implicit default means "all available".
            limit = n_tasks_override if n_tasks_override is not None else len(available)
            names = available[:limit]

        missing = sorted(set(names) - set(available))
        if missing:
            raise SystemExit(
                "Terminal-Bench tasks not found in the local dataset: "
                + ", ".join(missing)
            )
        if len(set(names)) != len(names):
            raise SystemExit("Terminal-Bench task list contains duplicates")
        if n_tasks_override is not None:
            names = names[:n_tasks_override]
        return [{"instance_id": name} for name in names]

    def run_experiments(
        self,
        *,
        tasks: list[dict],
        conditions: list[dict],
        runs_per_task: int,
        existing_results: list[dict],
        save: Callable[[list[dict]], None],
        agent_config: Path,
        step_limit: int,
        agent_timeout: int,
        max_workers: int,
        compression_ratio: float,
    ) -> list[dict]:
        """Run one Harbor batch for each condition and repetition."""
        del step_limit, agent_timeout  # Terminal-Bench prompt/Harbor own these limits.
        self._validate_runtime(agent_config)
        model_name, api_base = self._load_model_config(agent_config)
        results = existing_results
        max_attempts = max(1, int(os.environ.get("TB_MAX_BATCH_ATTEMPTS", "3")))
        retry_exceptions = retry_exceptions_from_env()

        for condition in conditions:
            for run_num in range(1, runs_per_task + 1):
                for attempt in range(1, max_attempts + 1):
                    by_key = {row["key"]: row for row in results}
                    pending = []
                    for task in tasks:
                        key = run_key(
                            task["instance_id"], condition["condition"], run_num
                        )
                        row = by_key.get(key)
                        if row is None:
                            pending.append(task["instance_id"])
                        elif (
                            needs_rerun(row, retry_exceptions)
                            and int(row.get("attempts") or 1) < max_attempts
                        ):
                            pending.append(task["instance_id"])
                    if not pending:
                        break
                    if attempt > 1:
                        print(
                            f"Re-running {len(pending)} unverified task(s) for "
                            f"{condition['condition']} r{run_num} "
                            f"(attempt {attempt}/{max_attempts})",
                            flush=True,
                        )

                    rows = self._run_batch(
                        task_names=pending,
                        condition=condition,
                        run_num=run_num,
                        agent_config=agent_config,
                        model_name=model_name,
                        api_base=api_base,
                        n_concurrent=max_workers,
                        compression_ratio=compression_ratio,
                        attempt=attempt,
                    )
                    for row in rows:
                        previous = by_key.get(row["key"])
                        if previous is not None:
                            row["attempts"] = int(previous.get("attempts") or 1) + 1
                            row["previous_attempts"] = [
                                *previous.get("previous_attempts", []),
                                {
                                    "timestamp": previous.get("timestamp"),
                                    "harbor_exception": previous.get("harbor_exception"),
                                    "harbor_exception_message": previous.get(
                                        "harbor_exception_message"
                                    ),
                                    "superseded_dir": previous.get("superseded_dir"),
                                },
                            ]
                            results[results.index(previous)] = row
                        else:
                            results.append(row)
                        by_key[row["key"]] = row
                    # Save after every batch: generated trials must never be
                    # lost to a later failure in the same sweep.
                    save(results)
                self._report_unverified(results, condition["condition"], run_num)
        return results

    def evaluate_results(
        self, results: list[dict], save: Callable[[list[dict]], None]
    ) -> list[dict]:
        """Harbor grades each trial during execution; nothing to evaluate later.

        A trial without a verdict cannot be graded after the fact because its
        container is gone. Such rows keep ``resolved=None``; re-running the
        experiment (without ``--eval-only``) retries the retryable ones.
        """
        del save
        unverified = [row for row in results if row.get("resolved") is None]
        if unverified:
            print(
                f"{len(unverified)} Terminal-Bench row(s) have no verifier verdict "
                "(resolved=None); rerun the experiment to retry the retryable ones."
            )
        return results

    @staticmethod
    def _report_unverified(results: list[dict], condition: str, run_num: int) -> None:
        rows = [
            row for row in results
            if row.get("condition") == condition
            and int(row.get("run_num") or 0) == run_num
            and row.get("resolved") is None
        ]
        if not rows:
            return
        print(f"Unverified after all attempts ({condition} r{run_num}): {len(rows)}")
        for row in rows:
            print(
                f"    {row['instance_id']}: {row.get('harbor_exception')} "
                f"{row.get('harbor_exception_message') or ''}".rstrip()
            )

    def _validate_runtime(self, agent_config: Path) -> None:
        for path, label in (
            (self.harbor, "Harbor executable"),
            (self.dataset_path, "Terminal-Bench dataset"),
            (self.tb_config, "Terminal-Bench agent config"),
            (agent_config, "model agent config"),
        ):
            if not path.exists():
                raise SystemExit(f"{label} not found: {path}")

        env = os.environ.copy()
        env["DOCKER_HOST"] = self.docker_host
        health = subprocess.run(
            ["docker", "info"],
            cwd=self.workspace_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if health.returncode:
            raise SystemExit(
                f"rootless Podman is not reachable through DOCKER_HOST={self.docker_host}"
            )

    @staticmethod
    def _load_model_config(path: Path) -> tuple[str, str]:
        payload = yaml.safe_load(path.read_text()) or {}
        model = payload.get("model", {})
        name = model.get("model_name")
        api_base = model.get("model_kwargs", {}).get("api_base")
        if not name or not api_base:
            raise SystemExit(
                f"{path} must define model.model_name and model.model_kwargs.api_base"
            )
        return str(name), str(api_base)

    def _run_batch(
        self,
        *,
        task_names: list[str],
        condition: dict,
        run_num: int,
        agent_config: Path,
        model_name: str,
        api_base: str,
        n_concurrent: int,
        compression_ratio: float,
        attempt: int = 1,
    ) -> list[dict]:
        condition_name = condition["condition"]
        job_name = (
            f"{self.model_tag}-{condition_name}-r{run_num}-"
            f"{int(time.time() * 1000)}"
        )
        if attempt > 1:
            job_name += f"-a{attempt}"
        job_dir = self.jobs_dir / job_name
        config_specs = []
        if condition.get("config") is not None:
            config_specs.append(str(condition["config"]))
        config_specs.extend((str(agent_config), str(self.tb_config)))

        env = os.environ.copy()
        env.update({
            "DOCKER_HOST": self.docker_host,
            "COMPOSE_BAKE": "false",
            "PYTHONPATH": os.pathsep.join((
                str(self.workspace_root / "src"),
                str(self.workspace_root),
                str(self.workspace_root / "mini-swe-agent" / "src"),
            )),
            "MSWEA_PRIMITIVE": str(condition["primitive"]),
            "MSWEA_TOKEN_BUDGET": str(condition["budget"]),
            "MSWEA_COMPRESSION_RATIO": str(compression_ratio),
            "MSWEA_COST_TRACKING": "ignore_errors",
            "MSWEA_TB_CONFIGS": os.pathsep.join(config_specs),
            "OPENAI_BASE_URL": api_base,
            "OPENAI_API_BASE": api_base,
        })
        env.setdefault("MSWEA_API_KEY", "EMPTY")

        command = [
            str(self.harbor), "run",
            "--agent", self.agent_import_path,
            "--model", model_name,
            "--path", str(self.dataset_path),
            "--n-attempts", "1",
            # Retries are handled by run_experiments so that every attempt's
            # evidence is kept; Harbor's own retry deletes the failed trial.
            "--max-retries", "0",
            "--n-tasks", str(len(task_names)),
            "--n-concurrent", str(n_concurrent),
            "--env", "docker",
            "--cpus", "ignore",
            "--jobs-dir", str(self.jobs_dir),
            "--job-name", job_name,
            "--yes",
            *verifier_env_args(),
            *verifier_timeout_args(),
        ]
        for task_name in task_names:
            command.extend(("--include-task-name", task_name))

        print(
            f"\nHarbor batch: {condition_name} r{run_num}, "
            f"{len(task_names)} tasks"
            + (f", attempt {attempt}" if attempt > 1 else "")
        )
        # Never raise before collecting: a Harbor process that dies part-way
        # has usually finished (and graded) some trials, which must be saved.
        returncode = 0
        if os.environ.get("TB_REAP_FINISHED_HARBOR") != "1":
            returncode = subprocess.run(command, cwd=self.workspace_root, env=env).returncode
        else:
            proc = subprocess.Popen(command, cwd=self.workspace_root, env=env)
            reaped = False
            while proc.poll() is None:
                time.sleep(10)
                try:
                    summary = json.loads((job_dir / "result.json").read_text())
                    paths = self._trial_result_paths(job_dir)
                    trials = [json.loads(p.read_text()) for p in paths]
                    complete = (
                        summary.get("finished_at")
                        and len(trials) == len(task_names)
                        and {t["task_name"] for t in trials} == set(task_names)
                        and all(t.get("finished_at") for t in trials)
                    )
                    if not complete:
                        continue
                    latest = max(
                        p.stat().st_mtime
                        for p in job_dir.rglob("*") if p.is_file()
                    )
                    if time.time() - latest < 120:
                        continue
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                print(f"Reaping finished Harbor process: {job_dir}", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                reaped = True
                break
            if not reaped:
                returncode = proc.returncode
        # Collect whatever Harbor produced, even if the job died part-way:
        # generated trials are saved by the caller and the rest re-queued.
        selected, duplicates = select_trials(job_dir, task_names)
        if returncode and not selected:
            # Nothing to collect: a launch-time failure (bad flags, unreachable
            # container service), not a partial batch.
            raise subprocess.CalledProcessError(returncode, command)
        if returncode:
            print(
                f"    ! Harbor exited with status {returncode}; collecting the "
                f"{len(selected)} finished trial(s) and re-queuing the rest"
            )
        for task, rejected in sorted(duplicates.items()):
            print(
                f"    ! {task}: {len(rejected)} duplicate trial(s) in {job_dir.name}; "
                "keeping the one with a verdict / latest finish"
            )
        rows = [
            self._normalize_trial(path.parent, condition, run_num, compression_ratio)
            for path in selected.values()
        ]
        missing = sorted(set(task_names) - set(selected))
        if missing:
            print(
                f"    ! Harbor produced {len(rows)} of {len(task_names)} trial results; "
                f"missing: {', '.join(missing)} (raw job retained at {job_dir})"
            )
        return sorted(rows, key=lambda row: row["instance_id"])

    @staticmethod
    def _trial_result_paths(job_dir: Path) -> list[Path]:
        return trial_result_files(job_dir)

    def _normalize_trial(
        self,
        trial_dir: Path,
        condition: dict,
        run_num: int,
        compression_ratio: float,
    ) -> dict[str, Any]:
        return normalize_trial(
            trial_dir, self.results_dir, self.model_tag, run_num,
            condition=condition,
            compression_ratio=compression_ratio,
            benchmark=self.name,
            benchmark_version=self.benchmark_version,
            dataset=self.dataset_name,
            workspace_root=self.workspace_root,
            fill_missing_timestamp=True,
            supersede=True,
        )
