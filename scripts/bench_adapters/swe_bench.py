"""SWE-bench-specific behavior for ``run_experiment_expansion.py``."""

from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
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
