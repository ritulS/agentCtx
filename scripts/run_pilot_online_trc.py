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
BASELINE_CONFIG = WORKSPACE_ROOT / "config-qwen-vllm.yaml"
ONLINE_TRC_CONFIG = WORKSPACE_ROOT / "config-online-trc.yaml"
RESULTS_DIR = WORKSPACE_ROOT / "results" / "online-trc-pilot"

PILOT_TASKS = [
    "django__django-11066",
    "django__django-11087",
    "django__django-11095",
    "django__django-11292",
    "django__django-11299",
]

CONDITIONS = [
    {"condition": "full-context", "primitive": "truncation",  "budget": 999_999_999, "config": BASELINE_CONFIG},
    {"condition": "online-trc",   "primitive": "online_trc",  "budget": 0,           "config": ONLINE_TRC_CONFIG},
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

    cmd = [
        str(WORKSPACE_ROOT / "venv" / "bin" / "python"),
        "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset",   DATASET_SUBSET,
        "--split",    DATASET_SPLIT,
        "--instance", instance_id,
        "-c", "swebench_backticks.yaml",
        "-c", str(config),
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
        f"  [{icon}] {instance_id:30s} {condition:12s}  "
        f"calls={n_calls:3d}  e2e={e2e:.0f}s  "
        f"tokens_saved={tok.get('online_trc_total_tokens_saved', 0):5d}  "
        f"flags={tok.get('online_trc_flag_counts', {})}"
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
        # token totals
        "total_prompt_tokens":     tok.get("total_prompt_tokens", 0),
        "total_completion_tokens": tok.get("total_completion_tokens", 0),
        "total_tokens":            tok.get("total_tokens", 0),
        "step_prompt_tokens":      tok.get("step_prompt_tokens", []),
        # online TRC
        "online_trc_flags":               tok.get("online_trc_flags", []),
        "online_trc_total_tokens_saved":  tok.get("online_trc_total_tokens_saved", 0),
        "online_trc_flag_counts":         tok.get("online_trc_flag_counts", {}),
        # compression (baseline will have none; kept for schema consistency)
        "compression_events":    tok.get("compression_events", 0),
        "total_tokens_saved":    tok.get("total_tokens_saved", 0),
    }


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("PILOT SUMMARY")
    print("=" * 70)

    baseline  = [r for r in results if r["condition"] == "full-context"]
    online    = [r for r in results if r["condition"] == "online-trc"]

    def patch_rate(rs): return sum(1 for r in rs if r["patch_generated"]) / max(len(rs), 1)

    print(f"\n  Patch rate  — full-context: {patch_rate(baseline):.0%}   online-trc: {patch_rate(online):.0%}")
    print(f"  Avg calls   — full-context: {sum(r['n_calls'] for r in baseline)/max(len(baseline),1):.1f}"
          f"  online-trc: {sum(r['n_calls'] for r in online)/max(len(online),1):.1f}")
    print(f"  Avg total tokens (prompt+completion):")
    print(f"    full-context: {sum(r['total_tokens'] for r in baseline)/max(len(baseline),1):,.0f}")
    print(f"    online-trc:   {sum(r['total_tokens'] for r in online)/max(len(online),1):,.0f}")

    if online:
        all_flags = []
        for r in online:
            all_flags.extend(e["flag"] for e in r.get("online_trc_flags", []))
        counts = Counter(all_flags)
        total  = max(sum(counts.values()), 1)
        print(f"\n  Online TRC flag distribution ({total} total clearing events):")
        for flag in ("none", "first_half", "second_half", "full"):
            n = counts.get(flag, 0)
            print(f"    {flag:12s}: {n:4d}  ({100*n/total:.1f}%)")
        missing = sum(1 for r in online for e in r.get("online_trc_flags", []) if not e.get("flag_found"))
        print(f"    missing     : {missing:4d}  ({100*missing/total:.1f}%)")
        total_saved = sum(r.get("online_trc_total_tokens_saved", 0) for r in online)
        print(f"\n  Total tokens cleared by online TRC: {total_saved:,}")
        avg_saved = total_saved / max(len(online), 1)
        print(f"  Avg per task: {avg_saved:,.0f}")

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
