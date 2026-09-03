"""SWE-bench-specific behavior for ``run_experiment_expansion.py``."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable


class SweBench:
    """Adapter between the generic experiment runner and SWE-bench.

    Public methods intentionally correspond to the points at which benchmarks
    differ: selecting tasks, launching one task, interpreting its output, and
    evaluating completed runs.
    """

    name = "swe-bench"
    REPOS = {
        "django/django": "django",
        "sympy/sympy": "sympy",
        "scikit-learn/scikit-learn": "scikit-learn",
    }

    def __init__(self, workspace_root: Path, model_tag: str, results_dir: Path):
        self.workspace_root = workspace_root
        self.model_tag = model_tag
        self.results_dir = results_dir
        self.python = workspace_root / "venv" / "bin" / "python"
        self.dataset_subset = "verified"
        self.dataset_split = "test"
        self.docker_host = f"unix:///run/user/{os.getuid()}/podman/podman.sock"

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
        """Load SWE-bench tasks, preserving the existing balanced sampling."""
        if ablation_name:
            if tasks_file_explicit:
                tasks = json.loads(tasks_file.read_text())
                source_desc = f"custom task file {tasks_file}"
            else:
                if not ablation_tasks_file.exists():
                    raise SystemExit(f"ERROR: ablation task file not found at {ablation_tasks_file}")
                tasks = json.loads(ablation_tasks_file.read_text())
                source_desc = "fixed 30-task set"
            if n_tasks_override is not None and n_tasks_override < len(tasks):
                tasks = tasks[:n_tasks_override]
                source_desc += f" (sliced to first {n_tasks_override} via --n-tasks)"
            by_repo = defaultdict(int)
            for task in tasks:
                by_repo[task["repo"]] += 1
            counts = ", ".join(f"{repo}={count}" for repo, count in sorted(by_repo.items()))
            print(f"Ablation mode ({source_desc}) — {len(tasks)} tasks: {counts}")
            return tasks

        if not tasks_file.exists():
            raise SystemExit(f"ERROR: {tasks_file} not found – run scripts/select_tasks.py first.")
        all_tasks = json.loads(tasks_file.read_text())
        by_repo: dict[str, list] = defaultdict(list)
        for task in all_tasks:
            by_repo[task["repo"]].append(task)

        n_base, n_remainder = divmod(n_tasks, len(self.REPOS))
        tasks: list[dict] = []
        counts_parts = []
        for index, (repo, label) in enumerate(self.REPOS.items()):
            count = n_base + (1 if index < n_remainder else 0)
            repo_tasks = by_repo.get(label, [])
            if len(repo_tasks) < count:
                print(f"WARNING: only {len(repo_tasks)} tasks for {repo} (need {count})")
            tasks.extend(repo_tasks[:count])
            counts_parts.append(f"{label}={count}")
        print(f"Using {len(tasks)} tasks: {', '.join(counts_parts)}")
        return tasks

    def agent_environment(self) -> dict[str, str]:
        """Environment variables required by the SWE-bench container runtime."""
        return {"DOCKER_HOST": self.docker_host}

    def build_agent_command(
        self,
        instance_id: str,
        config_chain: list[str],
        trajectory_file: Path,
        step_limit: int,
    ) -> list[str]:
        """Build the mini-swe-agent command for one SWE-bench instance."""
        command = [
            str(self.python),
            "-m", "minisweagent.run.benchmarks.swebench_single",
            "--subset", self.dataset_subset,
            "--split", self.dataset_split,
            "--instance", instance_id,
            "-c", "swebench_backticks.yaml",
        ]
        for config in config_chain:
            command += ["-c", config]
        command += [
            "-c", f"agent.step_limit={step_limit}",
            "-o", str(trajectory_file),
            "-y",
            "--exit-immediately",
        ]
        return command

    def parse_trajectory(self, trajectory_file: Path) -> dict:
        """Return benchmark-neutral outcome fields from a SWE-bench trajectory."""
        trajectory = json.loads(trajectory_file.read_text())
        info = trajectory.get("info", {})
        submission = info.get("submission", "") or ""
        return {
            "n_calls": info.get("model_stats", {}).get("api_calls", 0),
            "exit_status": info.get("exit_status", ""),
            "submission_generated": bool(submission.strip()),
            # These fields retain the existing result-file schema.
            "patch_generated": bool(submission.strip()),
            "submission": submission,
            "resolved": None,
        }

    def empty_outcome(self) -> dict:
        """Outcome used when a trajectory is missing or cannot be parsed."""
        return {
            "n_calls": 0,
            "exit_status": "",
            "submission_generated": False,
            "patch_generated": False,
            "submission": "",
            "resolved": None,
        }

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
        """Run the SWE-bench task × condition × repetition grid."""
        results = existing_results
        existing_keys = {result["key"] for result in results}
        needed = []
        for task in tasks:
            for condition in conditions:
                for run_num in range(1, runs_per_task + 1):
                    key = self._run_key(
                        task["instance_id"], condition["condition"], run_num
                    )
                    if key not in existing_keys:
                        needed.append((task["instance_id"], condition, run_num))

        total = len(tasks) * len(conditions) * runs_per_task
        done = total - len(needed)
        print(f"\nAgent runs: {total} total ({done} done, {len(needed)} remaining)")

        lock = threading.Lock()
        completed = [done]

        def run_one(item):
            instance_id, condition, run_num = item
            return self._run_agent(
                instance_id=instance_id,
                condition=condition["condition"],
                primitive=condition["primitive"],
                budget=condition["budget"],
                run_num=run_num,
                agent_config=agent_config,
                step_limit=step_limit,
                agent_timeout=agent_timeout,
                config=condition.get("config"),
                compression_ratio=compression_ratio,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(run_one, item): item for item in needed}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    completed[0] += 1
                    results.append(result)
                    existing_keys.add(result["key"])
                    save(results)
                    print(
                        f"  [{completed[0]:4d}/{total}]  "
                        f"{result['condition']:<14} r{result['run_num']} | "
                        f"{result['instance_id']}  calls={result['n_calls']} "
                        f"exit={result['exit_status']}"
                    )
        return results

    @staticmethod
    def _run_key(instance_id: str, condition: str, run_num: int) -> str:
        return f"{instance_id}__{condition}__r{run_num}"

    def _run_agent(
        self,
        *,
        instance_id: str,
        condition: str,
        primitive: str,
        budget: int,
        run_num: int,
        agent_config: Path,
        step_limit: int,
        agent_timeout: int,
        config: Path | None = None,
        compression_ratio: float = 0.5,
    ) -> dict:
        """Run mini-swe-agent for one task, condition, and repetition."""
        key = self._run_key(instance_id, condition, run_num)
        output_dir = self.results_dir / instance_id / condition / f"run_{run_num}"
        output_dir.mkdir(parents=True, exist_ok=True)

        trajectory_file = output_dir / "trajectory.json"
        token_log_file = output_dir / "token_log.json"
        log_file = output_dir / "agent.log"

        env = os.environ.copy()
        env.update({
            "MSWEA_COST_TRACKING": "ignore_errors",
            "MSWEA_PRIMITIVE": primitive,
            "MSWEA_TOKEN_BUDGET": str(budget),
            "MSWEA_COMPRESSION_RATIO": str(compression_ratio),
            "MSWEA_TOKEN_LOG_PATH": str(token_log_file),
            "MSWEA_RUN_KEY": key,
        })
        env.update(self.agent_environment())

        local_bin = str(Path.home() / ".local" / "bin")
        if local_bin not in env.get("PATH", ""):
            env["PATH"] = local_bin + ":" + env.get("PATH", "")
        env["PYTHONPATH"] = str(self.workspace_root) + (
            ":" + env["PYTHONPATH"] if "PYTHONPATH" in env else ""
        )

        config_chain = []
        if config is not None:
            config_chain.append(str(config))
            if Path(agent_config) != Path(config):
                config_chain.append(str(agent_config))
        else:
            config_chain.append(str(agent_config))
        command = self.build_agent_command(
            instance_id, config_chain, trajectory_file, step_limit
        )

        started = time.time()
        returncode = -1
        process = None
        try:
            with log_file.open("w") as log:
                process = subprocess.Popen(
                    command,
                    cwd=self.workspace_root / "mini-swe-agent",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                process.wait(timeout=agent_timeout)
                returncode = process.returncode
        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
            print(f"    ! Timeout after {agent_timeout}s")
        except Exception as exc:
            print(f"    ! Launch error: {exc}")

        e2e_latency = round(time.time() - started, 2)
        outcome = self.empty_outcome()
        if trajectory_file.exists():
            try:
                outcome = self.parse_trajectory(trajectory_file)
            except Exception as exc:
                print(f"    ! Trajectory parse error: {exc}")

        token_log = {}
        if token_log_file.exists():
            try:
                token_log = json.loads(token_log_file.read_text())
            except Exception:
                pass

        result = {
            "key": key,
            "instance_id": instance_id,
            "condition": condition,
            "primitive": primitive,
            "budget": budget,
            "compression_ratio": compression_ratio,
            "is_baseline": budget == 999_999_999,
            "run_num": run_num,
            "timestamp": datetime.now().isoformat(),
            "returncode": returncode,
            "e2e_latency_s": e2e_latency,
            "total_prompt_tokens": token_log.get("total_prompt_tokens", 0),
            "total_completion_tokens": token_log.get("total_completion_tokens", 0),
            "total_tokens": token_log.get("total_tokens", 0),
            "llm_latency_s": token_log.get("total_latency_s", 0.0),
            "mean_latency_s": token_log.get("mean_latency_s", 0.0),
            "step_prompt_tokens": token_log.get("step_prompt_tokens", []),
            "compression_events": token_log.get("compression_events", 0),
            "compression_event_steps": token_log.get("compression_event_steps", []),
            "context_tokens_at_compression": token_log.get("context_tokens_at_compression", []),
            "context_tokens_after_compression": token_log.get("context_tokens_after_compression", []),
            "total_tokens_saved": token_log.get("total_tokens_saved", 0),
            "mean_compression_ratio": token_log.get("mean_compression_ratio", 1.0),
            "summarization_prompt_tokens": token_log.get("summarization_prompt_tokens", 0),
            "summarization_latency_s": token_log.get("summarization_latency_s", 0.0),
            "trc_truncation_fallback_events": token_log.get("trc_truncation_fallback_events", 0),
            "online_trc_total_tokens_saved": token_log.get("online_trc_total_tokens_saved", 0),
            "online_trc_clears": token_log.get("online_trc_clears", 0),
            "online_trc_flags": token_log.get("online_trc_flags", []),
        }
        result.update(outcome)

        icon = "P" if outcome["submission_generated"] else "x"
        print(
            f"    [{icon}] e2e={e2e_latency:.0f}s  calls={outcome['n_calls']:3d}  "
            f"comp_events={result['compression_events']:2d}  "
            f"exit={outcome['exit_status']}"
        )
        return result

    def evaluate_results(self, results: list[dict], save: Callable[[list[dict]], None]) -> list[dict]:
        """Evaluate all unevaluated patches with the SWE-bench harness."""
        work = [result for result in results if "seeded_from" not in result]
        to_eval = [r for r in work if r["patch_generated"] and r["resolved"] is None]
        no_patch = sum(1 for r in work if not r["patch_generated"])
        print(f"\nSWE-bench evaluation: {len(to_eval)} runs to evaluate ({no_patch} had no patch); "
              f"{len(results) - len(work)} seeded stubs skipped\n")

        for index, result in enumerate(to_eval, 1):
            print(f"  [{index:4d}/{len(to_eval)}] {result['key']}")
            result["resolved"] = self._evaluate_run(result)
            status = "RESOLVED" if result["resolved"] else ("FAILED" if result["resolved"] is False else "ERROR")
            print(f"    → {status}")
            save(results)

        for result in work:
            if not result["patch_generated"]:
                result["resolved"] = False
        return results

    def _evaluate_run(self, result: dict) -> bool | None:
        instance_id, key = result["instance_id"], result["key"]
        predictions_dir = self.results_dir / "preds"
        evaluation_dir = self.results_dir / "eval"
        predictions_dir.mkdir(parents=True, exist_ok=True)
        evaluation_dir.mkdir(parents=True, exist_ok=True)

        predictions_stem = f"preds_{key}"
        predictions_path = predictions_dir / f"{predictions_stem}.json"
        predictions_path.write_text(json.dumps({instance_id: {
            "model_name_or_path": self.model_tag,
            "instance_id": instance_id,
            "model_patch": result["submission"],
        }}, indent=2))

        env = os.environ.copy()
        env.update(self.agent_environment())
        command = [
            str(self.python), "-m", "swebench.harness.run_evaluation",
            "--predictions_path", str(predictions_path),
            "--max_workers", "1",
            "--instance_ids", instance_id,
            "--run_id", key,
            "--report_dir", str(evaluation_dir),
            "--dataset_name", "princeton-nlp/SWE-bench_Verified",
            "--split", self.dataset_split,
        ]
        try:
            subprocess.run(command, cwd=evaluation_dir, env=env, capture_output=True,
                           text=True, timeout=600)
        except subprocess.TimeoutExpired:
            print(f"    ! Eval timeout for {key}")
            return None
        except Exception as exc:
            print(f"    ! Eval error for {key}: {exc}")
            return None

        output_file = self._find_eval_output(predictions_stem, key)
        if output_file is None:
            print(f"    ! Eval output not found for {key}")
            return None
        try:
            data = json.loads(output_file.read_text())
            return instance_id in data.get("resolved_ids", [])
        except Exception as exc:
            print(f"    ! Could not parse eval output: {exc}")
            return None

    def _find_eval_output(self, predictions_stem: str, run_id: str) -> Path | None:
        evaluation_dir = self.results_dir / "eval"
        candidates = [
            evaluation_dir / f"{self.model_tag}.{run_id}.json",
            evaluation_dir / f"{predictions_stem}.{run_id}.json",
            evaluation_dir / f"{run_id}.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return next(evaluation_dir.glob(f"*{run_id}*.json"), None)
