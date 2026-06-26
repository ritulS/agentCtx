#!/usr/bin/env python3
"""
Online TRC Pilot Runner
=======================
5 tasks × 2 conditions × 1 run = 10 agent runs.

Conditions
----------
  full-context  : baseline (no compression, budget sentinel)
  online-trc    : MSWEA_PRIMITIVE=online_trc, no budget needed

Results written to: results/online-trc-pilot/
"""

import json
import os
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
MINI_SWE_AGENT = WORKSPACE_ROOT / "mini-swe-agent"
BASELINE_CONFIG = WORKSPACE_ROOT / "configs/config-qwen-vllm.yaml"
ONLINE_TRC_CONFIG = WORKSPACE_ROOT / "configs/config-online-trc.yaml"
RESULTS_DIR = WORKSPACE_ROOT / "results" / "online-trc-pilot"

PILOT_TASKS = [
    "django__django-11066",
    "django__django-11087",
    "django__django-11095",
    "django__django-11292",
    "django__django-11299",
]

CONDITIONS = [
    {"condition": "full-context",    "primitive": "truncation", "budget": 999_999_999, "config": BASELINE_CONFIG},
    {"condition": "online-trc",      "primitive": "online_trc", "budget": 999_999_999, "config": ONLINE_TRC_CONFIG},
    {"condition": "online-trc-20k",  "primitive": "online_trc", "budget": 20_000,      "config": ONLINE_TRC_CONFIG},
]

STEP_LIMIT    = 75
AGENT_TIMEOUT = 1200  # 20 min

DATASET_SUBSET = "verified"
DATASET_SPLIT  = "test"
DOCKER_HOST    = f"unix:///run/user/{os.getuid()}/podman/podman.sock"


def run_agent(instance_id: str, cond: dict) -> dict:
    condition = cond["condition"]
    primitive = cond["primitive"]
    budget    = cond["budget"]
    config    = cond["config"]

    out = RESULTS_DIR / instance_id / condition / "run_1"
    out.mkdir(parents=True, exist_ok=True)

    traj_file      = out / "trajectory.json"
    token_log_file = out / "token_log.json"
    log_file       = out / "agent.log"

    env = os.environ.copy()
    env["MSWEA_COST_TRACKING"]  = "ignore_errors"
    env["MSWEA_PRIMITIVE"]      = primitive
    env["MSWEA_TOKEN_BUDGET"]   = str(budget)
    env["MSWEA_TOKEN_LOG_PATH"] = str(token_log_file)
    env["DOCKER_HOST"]          = DOCKER_HOST
    env["PYTHONPATH"] = str(WORKSPACE_ROOT) + (":" + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    local_bin = str(Path.home() / ".local" / "bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = local_bin + ":" + env.get("PATH", "")

    # configs/config-online-trc.yaml is a delta (prompt only, no model section), so chain
    # it before BASELINE_CONFIG to get the model from the baseline. For the FC
    # condition, config IS BASELINE_CONFIG so no chaining needed.
    config_chain = ["swebench_backticks.yaml"]
    if config != BASELINE_CONFIG:
        config_chain += [str(config), str(BASELINE_CONFIG)]
    else:
        config_chain += [str(config)]
    cmd = [
        str(WORKSPACE_ROOT / "venv" / "bin" / "python"),
        "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset",   DATASET_SUBSET,
        "--split",    DATASET_SPLIT,
        "--instance", instance_id,
    ]
    for c in config_chain:
        cmd += ["-c", c]
    cmd += [
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

    e2e = round(time.time() - t0, 2)

    # Parse trajectory
    n_calls = 0; patch_generated = False; exit_status = ""
    if traj_file.exists():
        try:
            traj        = json.loads(traj_file.read_text())
            info        = traj.get("info", {})
            n_calls     = info.get("model_stats", {}).get("api_calls", 0)
            exit_status = info.get("exit_status", "")
            patch_generated = bool((info.get("submission") or "").strip())
        except Exception as exc:
            print(f"    ! Traj parse error: {exc}")

    # Parse token log
    tok: dict = {}
    if token_log_file.exists():
        try:
            tok = json.loads(token_log_file.read_text())
        except Exception:
            pass

    icon = "P" if patch_generated else "x"
    print(
        f"  [{icon}] {instance_id:30s} {condition:15s}  "
        f"calls={n_calls:3d}  e2e={e2e:.0f}s  "
        f"tok_saved={tok.get('online_trc_total_tokens_saved', 0):5d}  "
        f"clears={tok.get('online_trc_clears', 0)}  "
        f"compress={tok.get('compression_events', 0)}"
    )

    return {
        "instance_id":     instance_id,
        "condition":       condition,
        "primitive":       primitive,
        "timestamp":       datetime.now().isoformat(),
        "returncode":      returncode,
        "e2e_latency_s":   e2e,
        "n_calls":         n_calls,
        "exit_status":     exit_status,
        "patch_generated": patch_generated,
        "resolved":        None,
        "total_prompt_tokens":            tok.get("total_prompt_tokens", 0),
        "total_completion_tokens":        tok.get("total_completion_tokens", 0),
        "total_tokens":                   tok.get("total_tokens", 0),
        "step_prompt_tokens":             tok.get("step_prompt_tokens", []),
        "online_trc_total_tokens_saved":  tok.get("online_trc_total_tokens_saved", 0),
        "online_trc_clears":              tok.get("online_trc_clears", 0),
        "compression_events":             tok.get("compression_events", 0),
        "total_tokens_saved":             tok.get("total_tokens_saved", 0),
    }


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("PILOT SUMMARY")
    print("=" * 70)

    def avg(rs, key): return sum(r[key] for r in rs) / max(len(rs), 1)
    def patch_rate(rs): return sum(1 for r in rs if r["patch_generated"]) / max(len(rs), 1)

    conds = ["full-context", "online-trc", "online-trc-20k"]
    groups = {c: [r for r in results if r["condition"] == c] for c in conds}

    print(f"\n  {'Condition':<20} {'Patch%':>7} {'AvgCalls':>9} {'AvgTokens':>11} {'TokSaved':>9} {'Compress':>9}")
    print(f"  {'-'*20} {'-'*7} {'-'*9} {'-'*11} {'-'*9} {'-'*9}")
    for c in conds:
        rs = groups[c]
        if not rs: continue
        print(f"  {c:<20} {patch_rate(rs):>7.0%} {avg(rs,'n_calls'):>9.1f} "
              f"{avg(rs,'total_tokens'):>11,.0f} "
              f"{avg(rs,'online_trc_total_tokens_saved'):>9,.0f} "
              f"{avg(rs,'compression_events'):>9.1f}")

    print("=" * 70 + "\n")


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / "pilot_results.json"

    total = len(PILOT_TASKS) * len(CONDITIONS)
    print(f"Online TRC Pilot: {len(PILOT_TASKS)} tasks × {len(CONDITIONS)} conditions = {total} runs")
    print(f"Results → {RESULTS_DIR}\n")

    results = []
    n = 0
    for task in PILOT_TASKS:
        for cond in CONDITIONS:
            n += 1
            print(f"[{n}/{total}] {task} / {cond['condition']}")
            r = run_agent(task, cond)
            results.append(r)
            results_file.write_text(json.dumps(results, indent=2))

    print_summary(results)
    print(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
