#!/usr/bin/env python3
"""
E1 Experiment Runner
====================
Scale : 30 tasks (10 per repo × 3 repos) × 2 primitives × 8 budget levels × 3 runs
      = 1 440 agent runs + SWE-bench evaluation.

Repos : pallets/flask, django/django, sympy/sympy
Primitives : truncation | summarization
Budget levels : 100% (baseline), 90%, 75%, 60%, 50%, 40%, 30%, 25%
               — expressed as fractions of each task's own full-context token count.
Runs per config : 3

Two-phase budget design
-----------------------
Phase 0 — Baseline runs (budget_pct = 1.00, MSWEA_TOKEN_BUDGET = 999999):
  Run all 30 tasks × 2 primitives × 3 runs = 180 agent runs with no compression.
  The mean total_prompt_tokens across the 3 baseline runs for each (task, primitive)
  pair becomes that pair's "full-context token count".

Phase 1 — Compute per-task absolute budgets:
  For each (task, primitive) and each compressed pct in [0.90 … 0.25]:
    abs_budget = max(100, int(mean_baseline_tokens × pct))

Phase 2 — Compressed runs:
  Run all 7 compressed budget levels using the per-task absolute budgets.
  = 30 × 2 × 7 × 3 = 1 260 agent runs.

Usage
-----
# Full run (both phases then eval):
python scripts/run_experiment.py --with-eval

# Agents only:
python scripts/run_experiment.py

# Eval only (pick up existing agent results):
python scripts/run_experiment.py --eval-only
"""

import argparse
import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

WORKSPACE_ROOT  = Path(__file__).parent.parent
MINI_SWE_AGENT  = WORKSPACE_ROOT / "mini-swe-agent"
AGENT_CONFIG    = WORKSPACE_ROOT / "config-qwen-vllm.yaml"
TASKS_FILE      = WORKSPACE_ROOT / "selected_tasks.json"
RESULTS_DIR     = WORKSPACE_ROOT / "results"

REPOS = {
    "pallets/flask":  "flask",
    "django/django":  "django",
    "sympy/sympy":    "sympy",
}

PRIMITIVES          = ["truncation", "summarization"]
# All budget levels as fractions of each task's full-context token count.
# 1.00 = unconstrained baseline (MSWEA_TOKEN_BUDGET sentinel = 999 999).
BUDGET_PERCENTAGES  = [1.00, 0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.25]
RUNS_PER_TASK       = 3
N_TASKS_PER_REPO    = 10       # updated by select_tasks.py

# Agent limits
STEP_LIMIT    = 50
AGENT_TIMEOUT = 900            # seconds per run

# SWE-bench evaluation
SWE_BENCH_PYTHON = Path.home() / "waf_experiment" / "bin" / "python"
DOCKER_HOST      = f"unix:///run/user/{os.getuid()}/podman/podman.sock"
DATASET_SUBSET   = "lite"
DATASET_SPLIT    = "test"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _pct_tag(budget_pct: float) -> str:
    """Convert 0.40 → 'p040', 1.00 → 'p100'."""
    return f"p{int(round(budget_pct * 100)):03d}"


def run_key(instance_id: str, primitive: str, budget_pct: float, run_num: int) -> str:
    return f"{instance_id}__{primitive}__{_pct_tag(budget_pct)}__r{run_num}"


def run_dir(instance_id: str, primitive: str, budget_pct: float, run_num: int) -> Path:
    return RESULTS_DIR / instance_id / primitive / _pct_tag(budget_pct) / f"run_{run_num}"


def results_file_path() -> Path:
    return RESULTS_DIR / "experiment_results.json"


def load_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        print(f"ERROR: {TASKS_FILE} not found – run scripts/select_tasks.py first.")
        raise SystemExit(1)
    tasks = json.loads(TASKS_FILE.read_text())
    # Validate: must have at least one task per repo
    by_repo: dict[str, list] = defaultdict(list)
    for t in tasks:
        by_repo[t["repo"]].append(t)
    for repo in REPOS:
        if repo not in by_repo:
            print(f"WARNING: no tasks for repo {repo!r} in {TASKS_FILE}")
    print(f"Loaded {len(tasks)} tasks: "
          + ", ".join(f"{label}={len(by_repo[repo])}"
                      for repo, label in REPOS.items()))
    return tasks


def load_existing_results() -> list[dict]:
    p = results_file_path()
    return json.loads(p.read_text()) if p.exists() else []


def save_results(results: list[dict]) -> None:
    p = results_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2))


# ── Phase 0 & 2: Agent run ─────────────────────────────────────────────────────

def run_agent(
    instance_id: str,
    primitive:   str,
    budget_pct:  float,
    budget_abs:  int,
    run_num:     int,
) -> dict:
    """
    Run mini-swe-agent for one (task, primitive, budget_pct, run) combination.

    budget_pct = 1.00   → unconstrained baseline (MSWEA_TOKEN_BUDGET = 999999)
    budget_pct < 1.00   → compressed run using budget_abs tokens
    """
    key = run_key(instance_id, primitive, budget_pct, run_num)
    out = run_dir(instance_id, primitive, budget_pct, run_num)
    out.mkdir(parents=True, exist_ok=True)

    traj_file      = out / "trajectory.json"
    token_log_file = out / "token_log.json"
    log_file       = out / "agent.log"

    env = os.environ.copy()
    env["MSWEA_PRIMITIVE"]      = primitive
    env["MSWEA_TOKEN_BUDGET"]   = "999999" if budget_pct == 1.00 else str(budget_abs)
    env["MSWEA_TOKEN_LOG_PATH"] = str(token_log_file)
    env["DOCKER_HOST"]          = DOCKER_HOST
    # memory.py lives in the repo root; add it to PYTHONPATH so default.py can
    # do `import memory` regardless of the cwd the subprocess starts in.
    existing_pypath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (str(WORKSPACE_ROOT)
                         + (":" + existing_pypath if existing_pypath else ""))

    cmd = [
        "python", "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset",   DATASET_SUBSET,
        "--split",    DATASET_SPLIT,
        "--instance", instance_id,
        "-c", "swebench.yaml",
        "-c", str(AGENT_CONFIG),
        "-c", f"agent.step_limit={STEP_LIMIT}",
        "-o", str(traj_file),
        "-y",
        "--exit-immediately",
    ]

    t0 = time.time()
    returncode = -1
    try:
        with open(log_file, "w") as log:
            proc = subprocess.Popen(
                cmd, cwd=MINI_SWE_AGENT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            proc.wait(timeout=AGENT_TIMEOUT)
            returncode = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"    ! Timeout after {AGENT_TIMEOUT}s")
    except Exception as exc:
        print(f"    ! Launch error: {exc}")

    e2e_latency = round(time.time() - t0, 2)

    # ── Parse trajectory ──────────────────────────────────────────────────────
    n_calls = 0; patch_generated = False; submission = ""; exit_status = ""
    if traj_file.exists():
        try:
            traj        = json.loads(traj_file.read_text())
            info        = traj.get("info", {})
            n_calls     = info.get("model_stats", {}).get("api_calls", 0)
            exit_status = info.get("exit_status", "")
            submission  = info.get("submission", "") or ""
            patch_generated = bool(submission.strip())
        except Exception as exc:
            print(f"    ! Trajectory parse error: {exc}")

    # ── Parse token log ───────────────────────────────────────────────────────
    tok: dict = {}
    if token_log_file.exists():
        try:
            tok = json.loads(token_log_file.read_text())
        except Exception:
            pass

    result = {
        "key":          key,
        "instance_id":  instance_id,
        "primitive":    primitive,
        # Budget fields — budget_pct is primary; budget_abs is the token threshold sent
        # to the agent.  For the baseline run budget_abs = 999999 (sentinel).
        "budget_pct":   budget_pct,
        "budget_abs":   budget_abs,
        "is_baseline":  budget_pct == 1.00,
        "run_num":      run_num,
        "timestamp":    datetime.now().isoformat(),
        # process
        "returncode":     returncode,
        "e2e_latency_s":  e2e_latency,
        # agent metrics
        "n_calls":        n_calls,
        "exit_status":    exit_status,
        "patch_generated": patch_generated,
        "submission":     submission,
        "resolved":       None,              # filled by Phase 3 (SWE-bench eval)
        # token log
        "total_prompt_tokens":     tok.get("total_prompt_tokens", 0),
        "total_completion_tokens": tok.get("total_completion_tokens", 0),
        "total_tokens":            tok.get("total_tokens", 0),
        "llm_latency_s":           tok.get("total_latency_s", 0.0),
        "mean_latency_s":          tok.get("mean_latency_s", 0.0),
        # compression
        "compression_events":     tok.get("compression_events", 0),
        "total_tokens_saved":     tok.get("total_tokens_saved", 0),
        "mean_compression_ratio": tok.get("mean_compression_ratio", 1.0),
    }

    icon = "P" if patch_generated else "x"
    print(
        f"    [{icon}] e2e={e2e_latency:.0f}s  calls={n_calls:3d}  "
        f"prompt={result['total_prompt_tokens']:6d}  "
        f"comp_events={result['compression_events']}"
    )
    return result


# ── Phase 0: Baseline ──────────────────────────────────────────────────────────

def run_baseline_phase(tasks: list[dict], results: list[dict]) -> list[dict]:
    """Run all unconstrained (budget_pct=1.00) agent runs."""
    existing_keys = {r["key"] for r in results}
    needed = [
        (t["instance_id"], p, rn)
        for t in tasks
        for p in PRIMITIVES
        for rn in range(1, RUNS_PER_TASK + 1)
        if run_key(t["instance_id"], p, 1.00, rn) not in existing_keys
    ]
    total_baseline = len(tasks) * len(PRIMITIVES) * RUNS_PER_TASK
    done_baseline  = total_baseline - len(needed)
    print(f"\nPhase 0 — Baseline runs: {total_baseline} total "
          f"({done_baseline} done, {len(needed)} remaining)")

    for i, (iid, prim, rn) in enumerate(needed, done_baseline + 1):
        print(f"  [{i:4d}/{total_baseline}] baseline  {prim:<14} r{rn} | {iid}")
        r = run_agent(iid, prim, budget_pct=1.00, budget_abs=999999, run_num=rn)
        results.append(r)
        existing_keys.add(r["key"])
        save_results(results)

    return results


# ── Phase 1: Compute per-task budgets ─────────────────────────────────────────

def compute_task_budgets(results: list[dict]) -> dict[tuple, int]:
    """
    For each (instance_id, primitive), compute the mean total_prompt_tokens
    across all baseline runs, then derive absolute token budgets for each pct.

    Returns dict mapping (instance_id, primitive, budget_pct) -> abs_tokens.
    """
    baseline_toks: dict[tuple, list[int]] = defaultdict(list)
    for r in results:
        if r.get("is_baseline") and r.get("total_prompt_tokens", 0) > 0:
            baseline_toks[(r["instance_id"], r["primitive"])].append(
                r["total_prompt_tokens"]
            )

    task_budgets: dict[tuple, int] = {}
    missing = []
    for (iid, prim), toks in baseline_toks.items():
        mean_toks = int(sum(toks) / len(toks))
        for pct in BUDGET_PERCENTAGES[1:]:   # skip 1.00
            task_budgets[(iid, prim, pct)] = max(100, int(mean_toks * pct))

    # Warn about any (task, primitive) pairs with no baseline data
    all_pairs = {(t["instance_id"], p)
                 for t in load_tasks() for p in PRIMITIVES}
    for pair in all_pairs:
        if pair not in baseline_toks:
            missing.append(pair)
    if missing:
        print(f"\nWARNING: {len(missing)} (task, primitive) pairs have no baseline "
              f"token data — compressed runs for these will be skipped:")
        for iid, prim in missing:
            print(f"  {iid} / {prim}")

    return task_budgets


# ── Phase 2: Compressed runs ───────────────────────────────────────────────────

def run_compressed_phase(
    tasks:        list[dict],
    results:      list[dict],
    task_budgets: dict[tuple, int],
) -> list[dict]:
    """Run all compressed budget levels (pct < 1.00)."""
    existing_keys = {r["key"] for r in results}
    needed = []
    for t in tasks:
        for prim in PRIMITIVES:
            for pct in BUDGET_PERCENTAGES[1:]:
                abs_b = task_budgets.get((t["instance_id"], prim, pct))
                if abs_b is None:
                    continue
                for rn in range(1, RUNS_PER_TASK + 1):
                    k = run_key(t["instance_id"], prim, pct, rn)
                    if k not in existing_keys:
                        needed.append((t["instance_id"], prim, pct, abs_b, rn))

    total_compressed = (
        len(tasks) * len(PRIMITIVES) * (len(BUDGET_PERCENTAGES) - 1) * RUNS_PER_TASK
    )
    done_compressed = total_compressed - len(needed)
    print(f"\nPhase 2 — Compressed runs: {total_compressed} total "
          f"({done_compressed} done, {len(needed)} remaining)")

    for i, (iid, prim, pct, abs_b, rn) in enumerate(needed, done_compressed + 1):
        print(f"  [{i:4d}/{total_compressed}] "
              f"{_pct_tag(pct)}  {prim:<14} r{rn} | {iid}")
        r = run_agent(iid, prim, budget_pct=pct, budget_abs=abs_b, run_num=rn)
        results.append(r)
        existing_keys.add(r["key"])
        save_results(results)

    return results


def run_all_agents(tasks: list[dict]) -> list[dict]:
    results = load_existing_results()

    # Phase 0: baselines first
    results = run_baseline_phase(tasks, results)

    # Phase 1: derive per-task absolute budgets from baseline token counts
    print("\nPhase 1 — Computing per-task absolute budgets from baseline runs...")
    task_budgets = compute_task_budgets(results)
    print(f"  Computed budgets for {len(task_budgets)} (task, primitive, pct) triples.")

    # Phase 2: compressed runs
    results = run_compressed_phase(tasks, results, task_budgets)

    return results


# ── Phase 3: SWE-bench evaluation ─────────────────────────────────────────────

def _find_eval_output(predictions_stem: str, run_id: str) -> Path | None:
    candidates = [
        WORKSPACE_ROOT / f"Qwen2.5-Coder-72B-Instruct.{run_id}.json",
        WORKSPACE_ROOT / f"{predictions_stem}.{run_id}.json",
        WORKSPACE_ROOT / f"{run_id}.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    for p in WORKSPACE_ROOT.glob(f"*{run_id}*.json"):
        if p.name != "experiment_results.json":
            return p
    return None


def evaluate_run(result: dict) -> bool | None:
    iid  = result["instance_id"]
    key  = result["key"]

    preds_stem = f"preds_{key}"
    preds_path = WORKSPACE_ROOT / f"{preds_stem}.json"
    preds_path.write_text(json.dumps({
        iid: {
            "model_name_or_path": "Qwen2.5-Coder-72B-Instruct",
            "instance_id":        iid,
            "model_patch":        result["submission"],
        }
    }, indent=2))

    env = os.environ.copy()
    env["DOCKER_HOST"] = DOCKER_HOST

    cmd = [
        str(SWE_BENCH_PYTHON), "-m", "swebench.harness.run_evaluation",
        "--predictions_path", str(preds_path),
        "--max_workers", "1",
        "--instance_ids", iid,
        "--run_id", key,
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=WORKSPACE_ROOT, env=env,
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"    ! Eval timeout for {key}")
        return None
    except Exception as exc:
        print(f"    ! Eval error for {key}: {exc}")
        return None

    out_file = _find_eval_output(preds_stem, key)
    if out_file is None:
        print(f"    ! Eval output not found for {key}")
        return None
    try:
        data     = json.loads(out_file.read_text())
        return iid in data.get("resolved_ids", [])
    except Exception as exc:
        print(f"    ! Could not parse eval output: {exc}")
        return None


def run_swebench_eval(results: list[dict]) -> list[dict]:
    to_eval = [r for r in results if r["patch_generated"] and r["resolved"] is None]
    no_patch = sum(1 for r in results if not r["patch_generated"])
    print(f"\nSWE-bench evaluation: {len(to_eval)} runs to evaluate "
          f"({no_patch} had no patch)\n")

    for i, r in enumerate(to_eval, 1):
        print(f"  [{i:4d}/{len(to_eval)}] {r['key']}")
        resolved = evaluate_run(r)
        r["resolved"] = resolved
        print(f"    → {'RESOLVED' if resolved else ('FAILED' if resolved is False else 'ERROR')}")
        save_results(results)

    for r in results:
        if not r["patch_generated"]:
            r["resolved"] = False

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="E1 experiment runner")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--eval-only",  action="store_true")
    grp.add_argument("--with-eval",  action="store_true")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()

    n_total = len(tasks) * len(PRIMITIVES) * len(BUDGET_PERCENTAGES) * RUNS_PER_TASK
    print("=" * 72)
    print("E1 EXPERIMENT")
    print(f"  Tasks      : {len(tasks)}  ({N_TASKS_PER_REPO} per repo)")
    print(f"  Primitives : {PRIMITIVES}")
    print(f"  Budgets    : {[f'{int(p*100)}%' for p in BUDGET_PERCENTAGES]}")
    print(f"  Runs/config: {RUNS_PER_TASK}")
    print(f"  Total runs : {n_total}")
    print("=" * 72)

    if not args.eval_only:
        results = run_all_agents(tasks)
    else:
        results = load_existing_results()
        if not results:
            print("No existing results. Run without --eval-only first.")
            raise SystemExit(1)

    if args.eval_only or args.with_eval:
        results = run_swebench_eval(results)

    save_results(results)
    total    = len(results)
    patched  = sum(1 for r in results if r["patch_generated"])
    resolved = sum(1 for r in results if r.get("resolved") is True)
    print(f"\nDone. {total} results → {results_file_path()}")
    print(f"  Patches  : {patched}/{total}")
    print(f"  Resolved : {resolved}/{total}")
    print("\nRun scripts/analyze_results.py or scripts/plot_e1.py for analysis.")


if __name__ == "__main__":
    main()
