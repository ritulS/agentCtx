#!/usr/bin/env python3
"""
WAF Experiment Runner
=====================
Design:  3 tasks × 3 primitives × 4 token budgets × 3 runs = 108 agent runs.

LLM context window : 50 000 tokens
  → start vLLM with: --max-model-len 50000
Token budgets under test: 10 000, 20 000, 30 000, 40 000
Memory primitives     : truncation | summarization | retrieval
Metrics collected     : e2e latency, token usage (prompt/completion), n_calls (tool
                        calls), compression events/savings, patch_generated, resolved.
WAF is computed in analyze_results.py from n_calls.

Usage
-----
# Phase 1 – run agents (uses venv at WORKSPACE_ROOT/venv)
python scripts/run_experiment.py

# Phase 2 – SWE-bench eval (uses ~/waf_experiment venv, Podman must be running)
python scripts/run_experiment.py --eval-only

# Run both phases end-to-end
python scripts/run_experiment.py --with-eval
"""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

WORKSPACE_ROOT = Path(__file__).parent.parent
MINI_SWE_AGENT = WORKSPACE_ROOT / "mini-swe-agent"
AGENT_CONFIG    = MINI_SWE_AGENT / "config-qwen-vllm.yaml"
TASKS_FILE      = WORKSPACE_ROOT / "selected_tasks.json"
RESULTS_DIR     = WORKSPACE_ROOT / "results"

# Experiment axes
PRIMITIVES    = ["truncation", "summarization"]
TOKEN_BUDGETS = [0, 1_000, 1_500, 2_500, 4_000]
# 0    → unconstrained baseline: MSWEA_TOKEN_BUDGET=999999 so compression never fires.
#        Used as the 100 % reference for budget_pct normalisation.
# 1000 → fires at step ~3 (very aggressive, keeps ~300 tok recent history)
# 1500 → fires at step ~7 (moderate, keeps ~800 tok recent history)
# 2500 → fires at step ~15 (mild, fires once on longer tasks)
# 4000 → near-baseline: rarely fires on typical 5-15 step runs
RUNS_PER_TASK = 1
N_TASKS       = 3          # one medium-complexity task per repo

# Agent limits
STEP_LIMIT    = 50         # max LLM calls per run
AGENT_TIMEOUT = 900        # seconds before killing a run

# SWE-bench evaluation
SWE_BENCH_PYTHON = Path.home() / "waf_experiment" / "bin" / "python"
DOCKER_HOST      = f"unix:///run/user/{os.getuid()}/podman/podman.sock"
DATASET_SUBSET   = "lite"
DATASET_SPLIT    = "test"

# ─── Helpers ──────────────────────────────────────────────────────────────────

SELECTED_IDS = [
    "pallets__flask-4045",       # flask: raise ValueError for dot in blueprint name
    "django__django-13447",      # django: add model class to app_list context
    "pytest-dev__pytest-5221",   # pytest: display fixture scope with --fixtures
]

def load_tasks() -> list[dict]:
    """Load the 3 hand-picked tasks from selected_tasks.json."""
    if not TASKS_FILE.exists():
        print(f"ERROR: {TASKS_FILE} not found – run scripts/select_tasks.py first.")
        raise SystemExit(1)
    with open(TASKS_FILE) as f:
        all_tasks = json.load(f)
    by_id = {t["instance_id"]: t for t in all_tasks}
    tasks = []
    for iid in SELECTED_IDS:
        if iid not in by_id:
            print(f"ERROR: task {iid!r} not found in {TASKS_FILE}")
            raise SystemExit(1)
        tasks.append(by_id[iid])
    return tasks


def run_key(instance_id: str, primitive: str, budget: int, run_num: int) -> str:
    return f"{instance_id}__{primitive}__b{budget:05d}__r{run_num}"


def run_dir(instance_id: str, primitive: str, budget: int, run_num: int) -> Path:
    return RESULTS_DIR / instance_id / primitive / str(budget) / f"run_{run_num}"


def results_file_path() -> Path:
    """Return deterministic path for master results JSON."""
    return RESULTS_DIR / "experiment_results.json"


def load_existing_results() -> list[dict]:
    p = results_file_path()
    if p.exists():
        return json.loads(p.read_text())
    return []


def save_results(results: list[dict]) -> None:
    p = results_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2))

# ─── Phase 1: Agent runs ──────────────────────────────────────────────────────

def run_agent(instance_id: str, primitive: str, budget: int, run_num: int) -> dict:
    """Run mini-swe-agent for one (task, primitive, budget, run) combination."""
    key = run_key(instance_id, primitive, budget, run_num)
    out = run_dir(instance_id, primitive, budget, run_num)
    out.mkdir(parents=True, exist_ok=True)

    traj_file      = out / "trajectory.json"
    token_log_file = out / "token_log.json"
    log_file       = out / "agent.log"

    env = os.environ.copy()
    env["MSWEA_PRIMITIVE"]      = primitive
    # budget=0 is the unconstrained baseline; use a large sentinel so compression
    # never fires.  The agent still runs the same primitive code-path.
    env["MSWEA_TOKEN_BUDGET"]   = "999999" if budget == 0 else str(budget)
    env["MSWEA_TOKEN_LOG_PATH"] = str(token_log_file)
    env["DOCKER_HOST"]          = DOCKER_HOST

    cmd = [
        "python", "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset",   DATASET_SUBSET,
        "--split",    DATASET_SPLIT,
        "--instance", instance_id,
        "-c", "swebench.yaml",
        "-c", str(AGENT_CONFIG),
        "-c", f"agent.step_limit={STEP_LIMIT}",
        "-o", str(traj_file),
        "-y",                  # yolo – no confirmation prompt
        "--exit-immediately",  # exit when agent finishes instead of prompting
    ]

    t0 = time.time()
    returncode = -1
    try:
        with open(log_file, "w") as log:
            proc = subprocess.Popen(
                cmd,
                cwd=MINI_SWE_AGENT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
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
    n_calls         = 0
    patch_generated = False
    submission      = ""
    exit_status     = ""

    if traj_file.exists():
        try:
            traj = json.loads(traj_file.read_text())
            info = traj.get("info", {})
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
        "key":              key,
        "instance_id":      instance_id,
        "primitive":        primitive,
        "budget":           budget,
        # budget=0 flags the unconstrained baseline run used to normalise budget_pct
        "is_baseline":      budget == 0,
        "budget_type":      "unconstrained" if budget == 0 else "compressed",
        "run_num":          run_num,
        "timestamp":        datetime.now().isoformat(),
        # process
        "returncode":       returncode,
        "e2e_latency_s":    e2e_latency,
        # agent metrics
        "n_calls":          n_calls,          # tool calls (LLM queries)
        "exit_status":      exit_status,
        "patch_generated":  patch_generated,
        "submission":       submission,
        "resolved":         None,             # filled by Phase 2
        # per-call token log totals
        "total_prompt_tokens":     tok.get("total_prompt_tokens", 0),
        "total_completion_tokens": tok.get("total_completion_tokens", 0),
        "total_tokens":            tok.get("total_tokens", 0),
        "llm_latency_s":           tok.get("total_latency_s", 0.0),
        "mean_latency_s":          tok.get("mean_latency_s", 0.0),
        # compression
        "compression_events":      tok.get("compression_events", 0),
        "total_tokens_saved":      tok.get("total_tokens_saved", 0),
        "mean_compression_ratio":  tok.get("mean_compression_ratio", 1.0),
    }

    status_icon = "P" if patch_generated else "x"
    print(
        f"    [{status_icon}] e2e={e2e_latency:.0f}s  calls={n_calls:3d}  "
        f"tokens={result['total_tokens']:6d}  comp_events={result['compression_events']}"
    )
    return result


def run_all_agents(tasks: list[dict]) -> list[dict]:
    """Run all (task × primitive × budget × run) combinations. Skip existing."""
    existing = load_existing_results()
    existing_keys = {r["key"] for r in existing}
    results = list(existing)

    total = len(tasks) * len(PRIMITIVES) * len(TOKEN_BUDGETS) * RUNS_PER_TASK
    done  = len([r for r in results if r["key"] in existing_keys])

    print(f"\nAgent runs: {total} total ({done} already done, "
          f"{total - done} remaining)\n")

    for task in tasks:
        iid = task["instance_id"]
        for primitive in PRIMITIVES:
            for budget in TOKEN_BUDGETS:
                for run_num in range(1, RUNS_PER_TASK + 1):
                    key = run_key(iid, primitive, budget, run_num)
                    if key in existing_keys:
                        print(f"  SKIP {key}")
                        continue

                    done += 1
                    print(f"  [{done:3d}/{total}] {primitive:14} b={budget:5d} r{run_num} | {iid}")
                    r = run_agent(iid, primitive, budget, run_num)
                    results.append(r)
                    existing_keys.add(key)
                    save_results(results)   # incremental save

    return results

# ─── Phase 2: SWE-bench evaluation ───────────────────────────────────────────

def _find_eval_output(predictions_stem: str, run_id: str) -> Path | None:
    """Locate the JSON file written by swebench run_evaluation."""
    # swebench writes: {model_name}.{run_id}.json or {predictions_stem}.{run_id}.json in cwd
    candidates = [
        WORKSPACE_ROOT / f"Qwen2.5-Coder-7B-Instruct.{run_id}.json",
        WORKSPACE_ROOT / f"{predictions_stem}.{run_id}.json",
        WORKSPACE_ROOT / f"{run_id}.json",
        WORKSPACE_ROOT / "logs" / f"{run_id}.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Broader glob
    for p in WORKSPACE_ROOT.glob(f"*{run_id}*.json"):
        if p.name != "experiment_results.json":
            return p
    return None


def evaluate_run(result: dict) -> bool | None:
    """
    Run swebench harness for one result dict that has a non-empty patch.
    Returns True/False/None (None = eval failed).
    """
    iid = result["instance_id"]
    key = result["key"]

    # Write a per-run predictions file
    preds_stem = f"preds_{key}"
    preds_path = WORKSPACE_ROOT / f"{preds_stem}.json"
    preds_path.write_text(json.dumps({
        iid: {
            "model_name_or_path": "Qwen2.5-Coder-7B-Instruct",
            "instance_id":        iid,
            "model_patch":        result["submission"],
        }
    }, indent=2))

    env = os.environ.copy()
    env["DOCKER_HOST"] = DOCKER_HOST

    cmd = [
        str(SWE_BENCH_PYTHON),
        "-m", "swebench.harness.run_evaluation",
        "--predictions_path", str(preds_path),
        "--max_workers", "1",
        "--instance_ids", iid,
        "--run_id", key,
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=WORKSPACE_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"    ! Eval timeout for {key}")
        return None
    except Exception as exc:
        print(f"    ! Eval error for {key}: {exc}")
        return None

    # Locate output JSON
    out_file = _find_eval_output(preds_stem, key)
    if out_file is None:
        print(f"    ! Eval output file not found for {key}")
        print(f"      stdout: {proc.stdout[-500:]}")
        return None

    try:
        data = json.loads(out_file.read_text())
        resolved = iid in data.get("resolved_ids", [])
        return resolved
    except Exception as exc:
        print(f"    ! Could not parse eval output: {exc}")
        return None


def run_swebench_eval(results: list[dict]) -> list[dict]:
    """Evaluate all runs that generated patches; update `resolved` in-place."""
    to_eval = [r for r in results if r["patch_generated"] and r["resolved"] is None]
    print(f"\nSWE-bench evaluation: {len(to_eval)} runs to evaluate "
          f"({sum(1 for r in results if not r['patch_generated'])} had no patch)\n")

    for i, r in enumerate(to_eval, 1):
        print(f"  [{i:3d}/{len(to_eval)}] {r['key']}")
        resolved = evaluate_run(r)
        r["resolved"] = resolved
        icon = "RESOLVED" if resolved else ("FAILED" if resolved is False else "ERROR")
        print(f"    → {icon}")
        save_results(results)

    # Mark no-patch runs as False
    for r in results:
        if not r["patch_generated"]:
            r["resolved"] = False

    return results

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="WAF experiment runner")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--eval-only",  action="store_true",
                     help="Skip agent runs; only run SWE-bench evaluation on existing results.")
    grp.add_argument("--with-eval",  action="store_true",
                     help="Run agents then immediately run SWE-bench evaluation.")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()

    print("=" * 72)
    print("WAF EXPERIMENT")
    print(f"  Tasks     : {len(tasks)}  ({', '.join(t['instance_id'] for t in tasks)})")
    print(f"  Primitives: {PRIMITIVES}")
    print(f"  Budgets   : {TOKEN_BUDGETS}")
    print(f"  Runs/task : {RUNS_PER_TASK}")
    print(f"  Total     : {len(tasks)*len(PRIMITIVES)*len(TOKEN_BUDGETS)*RUNS_PER_TASK} agent runs")
    print("=" * 72)

    if not args.eval_only:
        results = run_all_agents(tasks)
    else:
        results = load_existing_results()
        if not results:
            print("No existing results found. Run without --eval-only first.")
            raise SystemExit(1)

    if args.eval_only or args.with_eval:
        results = run_swebench_eval(results)

    # Final summary
    save_results(results)
    total = len(results)
    patched  = sum(1 for r in results if r["patch_generated"])
    resolved = sum(1 for r in results if r.get("resolved") is True)
    print(f"\nDone. {total} results saved → {results_file_path()}")
    print(f"  Patches generated : {patched}/{total}")
    print(f"  Resolved (eval)   : {resolved}/{total}")
    print("\nRun scripts/analyze_results.py to see WAF and aggregate metrics.")


if __name__ == "__main__":
    main()
