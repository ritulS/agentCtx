"""SWE-bench-specific behavior for ``run_experiment_expansion.py``."""

from __future__ import annotations

import json
import os
import shutil
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

    # Harness-side test timeout (passed as --timeout so the harness itself stops
    # and removes the container) and the outer subprocess limit, which must also
    # cover image builds. Killing only the subprocess would orphan the container.
    EVAL_TEST_TIMEOUT_S = 1800
    EVAL_SUBPROCESS_TIMEOUT_S = EVAL_TEST_TIMEOUT_S + 900
    APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"   # swebench.harness.constants
    # OpenMP/BLAS thread cap inside evaluation containers; without it small-data
    # test suites spawn one thread per host core and never finish (see
    # scripts/swebench_eval_wrapper.py).
    EVAL_THREADS = 8

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
        self.docker_host = os.environ.get("DOCKER_HOST") or f"unix:///run/user/{os.getuid()}/podman/podman.sock"

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

        # The harness reuses an existing report.json for the same run_id (= key)
        # without comparing patches, so a regenerated run would inherit the
        # verdict of its previous patch. Remove this key's old harness output
        # and top-level reports before evaluating.
        run_dir = evaluation_dir / "logs" / "run_evaluation" / key
        if run_dir.exists():
            shutil.rmtree(run_dir)
        for name in self._eval_output_names(predictions_stem, key):
            (evaluation_dir / name).unlink(missing_ok=True)

        env = os.environ.copy()
        env.update(self.agent_environment())
        env["SWEBENCH_EVAL_THREADS"] = str(self.EVAL_THREADS)
        command = [
            str(self.python), str(self.workspace_root / "scripts" / "swebench_eval_wrapper.py"),
            "--predictions_path", str(predictions_path),
            "--max_workers", "1",
            "--instance_ids", instance_id,
            "--run_id", key,
            "--report_dir", str(evaluation_dir),
            "--dataset_name", "princeton-nlp/SWE-bench_Verified",
            "--split", self.dataset_split,
            "--timeout", str(self.EVAL_TEST_TIMEOUT_S),
            # Keep instance images (~2.8 GB each, ~100 tasks): the default
            # "env" level deletes them after every run, forcing a re-pull or
            # rebuild on the next evaluation of the same task and racing
            # against other harness runs (409 image conflicts).
            "--cache_level", "instance",
        ]
        try:
            subprocess.run(command, cwd=evaluation_dir, env=env, capture_output=True,
                           text=True, timeout=self.EVAL_SUBPROCESS_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            print(f"    ! Eval timeout for {key}")
            self._remove_eval_container(instance_id, key)
            return None
        except Exception as exc:
            print(f"    ! Eval error for {key}: {exc}")
            self._remove_eval_container(instance_id, key)
            return None

        # Confirm the harness evaluated this submission, not something else.
        patch_file = run_dir / self.model_tag / instance_id / "patch.diff"
        if not patch_file.exists() or patch_file.read_text() != result["submission"]:
            print(f"    ! Eval patch mismatch for {key}")
            return None

        output_file = self._find_eval_output(predictions_stem, key)
        if output_file is None:
            print(f"    ! Eval output not found for {key}")
            return None
        try:
            data = json.loads(output_file.read_text())
        except Exception as exc:
            print(f"    ! Could not parse eval output: {exc}")
            return None
        if instance_id in data.get("resolved_ids", []):
            return True
        if instance_id in data.get("unresolved_ids", []):
            return False
        # No report.json: the harness lists the instance under error_ids both for
        # a patch that does not apply (a genuine failure) and for environment
        # errors or test timeouts (not a verdict). Tell them apart via the log.
        instance_log = run_dir / self.model_tag / instance_id / "run_instance.log"
        if instance_log.exists() and self.APPLY_PATCH_FAIL in instance_log.read_text(errors="replace"):
            return False
        print(f"    ! Eval harness error for {key} (no verdict; will be retried)")
        return None

    def _remove_eval_container(self, instance_id: str, key: str) -> None:
        """Remove the harness container for this run if it survived the harness.

        The harness names it sweb.eval.<instance>.<run_id>; a container left
        running keeps burning CPU and blocks image removal (409 conflicts).
        """
        name = f"sweb.eval.{instance_id}.{key}"
        try:
            import docker  # the venv's Docker-compatible SDK, talks to podman
            client = docker.DockerClient(base_url=self.docker_host)
            try:
                client.containers.get(name).remove(force=True)
                print(f"    ! Removed leftover eval container {name}")
            except docker.errors.NotFound:
                pass
            finally:
                client.close()
        except Exception as exc:
            print(f"    ! Could not remove eval container {name}: {exc}")

    def _eval_output_names(self, predictions_stem: str, run_id: str) -> list[str]:
        """Top-level harness report names this runner recognizes for one run."""
        return [
            f"{self.model_tag}.{run_id}.json",
            f"{predictions_stem}.{run_id}.json",
            f"{run_id}.json",
        ]

    def _find_eval_output(self, predictions_stem: str, run_id: str) -> Path | None:
        # Exact names only: a glob such as "*__r1*.json" would also match "__r10".
        evaluation_dir = self.results_dir / "eval"
        for name in self._eval_output_names(predictions_stem, run_id):
            candidate = evaluation_dir / name
            if candidate.exists():
                return candidate
        return None
