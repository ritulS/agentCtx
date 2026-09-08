"""Terminal-Bench execution through Harbor for ``run_experiment.py``."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Any

import yaml

from .harbor_results import normalize_trial, trial_result_paths
from .results import run_key


class TerminalBench:
    """Adapter between the generic experiment runner and Harbor batches."""

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
        existing_keys = {result["key"] for result in results}

        for condition in conditions:
            for run_num in range(1, runs_per_task + 1):
                missing_tasks = [
                    task["instance_id"]
                    for task in tasks
                    if run_key(
                        task["instance_id"], condition["condition"], run_num
                    ) not in existing_keys
                ]
                if not missing_tasks:
                    continue

                rows = self._run_batch(
                    task_names=missing_tasks,
                    condition=condition,
                    run_num=run_num,
                    agent_config=agent_config,
                    model_name=model_name,
                    api_base=api_base,
                    n_concurrent=max_workers,
                    compression_ratio=compression_ratio,
                )
                for row in rows:
                    results.append(row)
                    existing_keys.add(row["key"])
                save(results)
        return results

    def evaluate_results(
        self, results: list[dict], save: Callable[[list[dict]], None]
    ) -> list[dict]:
        """Harbor grades each trial during execution, so no second pass is needed."""
        del save
        return results

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
    ) -> list[dict]:
        condition_name = condition["condition"]
        job_name = (
            f"{self.model_tag}-{condition_name}-r{run_num}-"
            f"{int(time.time() * 1000)}"
        )
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
            "--n-tasks", str(len(task_names)),
            "--n-concurrent", str(n_concurrent),
            "--env", "docker",
            "--cpus", "ignore",
            "--jobs-dir", str(self.jobs_dir),
            "--job-name", job_name,
            "--yes",
        ]
        for task_name in task_names:
            command.extend(("--include-task-name", task_name))

        print(
            f"\nHarbor batch: {condition_name} r{run_num}, "
            f"{len(task_names)} tasks"
        )
        subprocess.run(command, cwd=self.workspace_root, env=env, check=True)
        rows = [
            self._normalize_trial(path.parent, condition, run_num, compression_ratio)
            for path in trial_result_paths(job_dir)
        ]
        if len(rows) != len(task_names):
            raise RuntimeError(
                f"Harbor produced {len(rows)} trial results, expected "
                f"{len(task_names)}; raw job retained at {job_dir}"
            )
        return sorted(rows, key=lambda row: row["instance_id"])

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
            fill_missing_timestamp=True,
        )
