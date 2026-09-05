"""Terminal-Bench execution through Harbor for ``run_experiment.py``."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

import yaml


class TerminalBench:
    """Adapter between the generic experiment runner and Harbor batches."""

    name = "terminal-bench"
    benchmark_version = "1.0"
    dataset_name = "terminal-bench-core@0.1.1"
    agent_import_path = (
        "scripts.bench_adapters.harbor_adapter:CompressionAgent"
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
                    if self._run_key(
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
        if os.environ.get("TB_REAP_FINISHED_HARBOR") != "1":
            subprocess.run(command, cwd=self.workspace_root, env=env, check=True)
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
            if not reaped and proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, command)
        rows = [
            self._normalize_trial(path.parent, condition, run_num, compression_ratio)
            for path in self._trial_result_paths(job_dir)
        ]
        if len(rows) != len(task_names):
            raise RuntimeError(
                f"Harbor produced {len(rows)} trial results, expected "
                f"{len(task_names)}; raw job retained at {job_dir}"
            )
        return sorted(rows, key=lambda row: row["instance_id"])

    @staticmethod
    def _trial_result_paths(job_dir: Path) -> list[Path]:
        for root in (job_dir / "trials", job_dir):
            for filename in ("result.json", "results.json"):
                paths = sorted(root.glob(f"*/{filename}"))
                if paths:
                    return paths
        return []

    def _normalize_trial(
        self,
        trial_dir: Path,
        condition: dict,
        run_num: int,
        compression_ratio: float,
    ) -> dict[str, Any]:
        result_path = trial_dir / "result.json"
        if not result_path.exists():
            result_path = trial_dir / "results.json"
        harbor_result = json.loads(result_path.read_text())
        task = harbor_result["task_name"]
        condition_name = condition["condition"]
        output = self.results_dir / task / condition_name / f"run_{run_num}"
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
        token_log = (
            json.loads(token_log_path.read_text()) if token_log_path.exists() else {}
        )
        exit_info_path = trial_dir / "agent" / "exit_info.json"
        exit_info = (
            json.loads(exit_info_path.read_text()) if exit_info_path.exists() else {}
        )
        reward = self._reward_value(harbor_result)
        timing = harbor_result.get("agent_execution") or {}
        row = {
            "key": self._run_key(task, condition_name, run_num),
            "benchmark": self.name,
            "benchmark_version": self.benchmark_version,
            "dataset": self.dataset_name,
            "instance_id": task,
            "condition": condition_name,
            "primitive": condition["primitive"],
            "budget": condition["budget"],
            "compression_ratio": compression_ratio,
            "is_baseline": condition["budget"] == 999_999_999,
            "run_num": run_num,
            "model": self.model_tag,
            "agent_model": self.model_tag,
            "timestamp": harbor_result.get("started_at") or datetime.now().isoformat(),
            "returncode": 0 if harbor_result.get("exception_info") is None else -1,
            "e2e_latency_s": self._seconds_between(
                harbor_result.get("started_at"), harbor_result.get("finished_at")
            ),
            "agent_latency_s": self._seconds_between(
                timing.get("started_at"), timing.get("finished_at")
            ),
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

    @staticmethod
    def _run_key(instance_id: str, condition: str, run_num: int) -> str:
        return f"{instance_id}__{condition}__r{run_num}"

    @staticmethod
    def _reward_value(result: dict[str, Any]) -> float | None:
        rewards = (result.get("verifier_result") or {}).get("rewards")
        if not isinstance(rewards, dict) or not rewards:
            return None
        value = rewards.get("reward")
        if value is None and len(rewards) == 1:
            value = next(iter(rewards.values()))
        return float(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _seconds_between(start: str | None, finish: str | None) -> float | None:
        if not start or not finish:
            return None
        try:
            return round(
                (datetime.fromisoformat(finish) - datetime.fromisoformat(start)).total_seconds(),
                2,
            )
        except ValueError:
            return None
