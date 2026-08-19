#!/usr/bin/env python3
"""Terminal-Bench runner for the agentCtx compression experiments.

Drives `tb run` (terminal-bench 0.2.x, venv-tb) once per (condition, run_num)
— MSWEA_PRIMITIVE / MSWEA_TOKEN_BUDGET / MSWEA_COMPRESSION_RATIO are
process-wide in the fork, so a tb invocation can only host one condition.
The agent is tbench/agent_adapter.py:CompressionAgent (the fork's
DefaultAgent; compression code path identical to SWE-bench runs).

Outputs:
  results/tbench/runs/<condition>/r<run>/agent/<task>/run_<n>/
      trajectory.json  token_log.json  exit_info.json     (written by adapter)
  results/tbench/runs/<condition>/r<run>/tb/<run-id>/     (tb harness output)
  results/tbench/experiment_results.json                  (aggregate rows,
      same field names as the SWE-bench aggregate so analysis transfers)

Progress is appended to results/tbench/STATUS.md after every invocation.

Usage:
  venv/bin/python scripts/run_tbench.py --conditions full-context --runs 1 \
      --tasks-file task_lists/tbench_pilot_tasks.json          # pilot
  venv/bin/python scripts/run_tbench.py --runs 3 \
      --tasks-file task_lists/tbench_tasks.json                # main grid

Requires: podman API service on the rootless socket, prebuilt task images
(scripts/tb_prebuild_images.sh), vLLM on :8000.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_TB = REPO_ROOT / "venv-tb" / "bin" / "tb"
RESULTS_ROOT = REPO_ROOT / "results" / "tbench"
AGG_PATH = RESULTS_ROOT / "experiment_results.json"
STATUS_PATH = RESULTS_ROOT / "STATUS.md"
DATASET = "terminal-bench-core==0.1.1"
BENCHMARK_TAG = "terminal-bench-core-0.1.1"
AGENT_IMPORT_PATH = "tbench.agent_adapter:CompressionAgent"
AGENT_TIMEOUT_SEC = 1500  # match SWE-bench AGENT_TIMEOUT (25 min hard cap)

# Subset of scripts/run_experiment.py CONDITIONS in scope for the TB
# generalization experiment (user decision 2026-07-12: 4 core conditions).
TB_CONDITIONS = {
    "full-context": {"primitive": "truncation", "budget": 999_999_999},
    "truncation": {"primitive": "truncation", "budget": 15_000},
    "tool-result-clear": {"primitive": "tool_result_clear", "budget": 15_000},
    "structured-summarize": {"primitive": "structured_summarize", "budget": 15_000},
}

COMPRESSION_RATIO = 0.5


def _serving_max_model_len() -> int | None:
    """Read max_model_len from the live vLLM server so every row records the
    serving window it ran under (32k vs 100k regimes must never mix silently)."""
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:8000/v1/models", timeout=5) as r:
            return json.load(r)["data"][0].get("max_model_len")
    except Exception:
        return None


SERVING_MAX_MODEL_LEN = _serving_max_model_len()


def load_tasks(tasks_file: Path) -> list[str]:
    data = json.loads(tasks_file.read_text())
    return data["tasks"] if isinstance(data, dict) else list(data)


def load_agg() -> list[dict]:
    if AGG_PATH.exists():
        return json.loads(AGG_PATH.read_text())
    return []


def save_agg(rows: list[dict]) -> None:
    AGG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGG_PATH.write_text(json.dumps(rows, indent=1))


def append_status(line: str) -> None:
    ts = datetime.now().strftime("%H:%M")
    try:
        text = STATUS_PATH.read_text()
        marker = "## Run progress (auto-appended by run_tbench.py)\n"
        entry = f"- **{datetime.now().strftime('%Y-%m-%d')} {ts}** — {line}\n"
        if marker in text:
            head, tail = text.split(marker, 1)
            tail = tail.replace("_(nothing yet)_\n", "", 1)
            STATUS_PATH.write_text(head + marker + entry + tail)
        else:
            STATUS_PATH.write_text(text + "\n" + entry)
    except FileNotFoundError:
        pass
    print(f"[status] {line}", flush=True)


def parse_tb_results(tb_out_dir: Path, run_id: str) -> dict[str, bool | None]:
    """Return {task_id: is_resolved} from a tb run's results.json."""
    results_path = tb_out_dir / run_id / "results.json"
    resolved: dict[str, bool | None] = {}
    if not results_path.exists():
        return resolved
    data = json.loads(results_path.read_text())
    for trial in data.get("results", []):
        resolved[trial["task_id"]] = trial.get("is_resolved")
    return resolved


def build_row(
    task_id: str,
    cond_name: str,
    cond: dict,
    run_num: int,
    resolved: bool | None,
    agent_dir: Path,
    e2e_latency_s: float | None,
) -> dict:
    row = {
        "benchmark": BENCHMARK_TAG,
        "max_model_len": SERVING_MAX_MODEL_LEN,
        "instance_id": task_id,
        "condition": cond_name,
        "primitive": cond["primitive"],
        "budget": cond["budget"],
        "compression_ratio": COMPRESSION_RATIO,
        "is_baseline": cond_name == "full-context",
        "run_num": run_num,
        "resolved": bool(resolved) if resolved is not None else False,
        "tb_is_resolved_raw": resolved,
        "e2e_latency_s": e2e_latency_s,
    }
    run_dir = agent_dir / task_id / f"run_{run_num}"
    exit_info_path = run_dir / "exit_info.json"
    token_log_path = run_dir / "token_log.json"
    if exit_info_path.exists():
        ei = json.loads(exit_info_path.read_text())
        row["exit_status"] = ei.get("exit_status", "")
        row["n_calls"] = ei.get("n_calls")
    else:
        row["exit_status"] = "missing_exit_info"
        row["n_calls"] = None
    # "submitted" is the TB analog of SWE-bench patch_generated
    row["patch_generated"] = row["exit_status"] == "Submitted"
    if token_log_path.exists():
        tl = json.loads(token_log_path.read_text())
        row.update(tl)
        row["llm_latency_s"] = tl.get("total_latency_s")
    return row


def _ensure_podman_socket(docker_host: str) -> None:
    """Restart the podman API service if the socket is dead (it dying mid-grid
    on 2026-07-13 burned 9 invocations with instant connection-refused)."""
    check = ["docker", "info", "--format", "{{.ServerVersion}}"]
    for attempt in range(3):
        ok = subprocess.run(check, env=os.environ | {"DOCKER_HOST": docker_host},
                            capture_output=True, text=True).returncode == 0
        if ok:
            return
        append_status(f"podman socket dead (attempt {attempt + 1}/3) — restarting service")
        subprocess.run(["systemctl", "--user", "reset-failed", "podman-api.service"], capture_output=True)
        subprocess.run(
            ["systemd-run", "--user", "--unit=podman-api", "--collect",
             "podman", "system", "service", "--time=0",
             docker_host.removeprefix("unix://") and docker_host],
            capture_output=True, text=True,
        )
        time.sleep(5)
    raise RuntimeError("podman API socket unreachable after 3 restart attempts — aborting instead of burning the queue")


def run_condition(
    cond_name: str,
    cond: dict,
    run_num: int,
    tasks: list[str],
    n_concurrent: int,
    rows: list[dict],
    tag: str = "",
) -> None:
    suffix = f"-{tag}" if tag else ""
    run_id = f"{cond_name}-r{run_num}{suffix}"
    cond_root = RESULTS_ROOT / "runs" / f"{cond_name}{suffix}" / f"r{run_num}"
    agent_dir = cond_root / "agent"
    tb_out = cond_root / "tb"

    env = os.environ.copy()
    env.update(
        {
            "DOCKER_HOST": f"unix:///run/user/{os.getuid()}/podman/podman.sock",
            "PYTHONPATH": str(REPO_ROOT),
            "MSWEA_PRIMITIVE": cond["primitive"],
            "MSWEA_TOKEN_BUDGET": str(cond["budget"]),
            "MSWEA_COMPRESSION_RATIO": str(COMPRESSION_RATIO),
            "MSWEA_COST_TRACKING": "ignore_errors",
            "MSWEA_TB_OUTPUT_DIR": str(agent_dir),
            "MSWEA_TB_RUN_NUM": str(run_num),
        }
    )
    env.pop("MSWEA_TOKEN_LOG_PATH", None)  # per-task logs are adapter-written

    cmd = [
        str(VENV_TB),
        "run",
        "--dataset",
        DATASET,
        "--agent-import-path",
        AGENT_IMPORT_PATH,
        "--n-concurrent",
        str(n_concurrent),
        "--no-rebuild",
        "--no-cleanup",
        "--no-upload-results",
        "--global-agent-timeout-sec",
        str(AGENT_TIMEOUT_SEC),
        "--output-path",
        str(tb_out),
        "--run-id",
        run_id,
    ]
    for t in tasks:
        cmd.extend(["-t", t])

    # Guard: a dead podman socket makes every trial fail in seconds and burns
    # the whole queue (2026-07-13 incident). Abort hard instead; try one
    # supervised restart first.
    sock_ok = lambda: subprocess.run(
        ["docker", "info"], env=env, capture_output=True
    ).returncode == 0
    if not sock_ok():
        subprocess.run(["systemctl", "--user", "start", "podman-api.service"], capture_output=True)
        time.sleep(3)
        if not sock_ok():
            append_status(f"ABORT before `{cond_name}` r{run_num}: podman socket dead and restart failed")
            raise SystemExit(2)

    # Guard: vLLM died mid-grid on 2026-07-13 (systemd-oomd kill) and 19/24
    # tasks silently failed with InternalServerError. Wait for health; if it
    # stays down, abort rather than burn the pair.
    vllm_ok = lambda: subprocess.run(
        ["curl", "-s", "--max-time", "3", "http://localhost:8000/v1/models"],
        capture_output=True,
    ).returncode == 0
    if not vllm_ok():
        append_status(f"vLLM down before `{cond_name}` r{run_num} — waiting up to 15 min for recovery")
        for _ in range(90):
            time.sleep(10)
            if vllm_ok():
                break
        else:
            append_status(f"ABORT before `{cond_name}` r{run_num}: vLLM unreachable for 15 min")
            raise SystemExit(3)

    _ensure_podman_socket(env["DOCKER_HOST"])
    append_status(f"`{cond_name}` r{run_num} started ({len(tasks)} tasks, n-concurrent {n_concurrent})")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, cwd=REPO_ROOT, text=True, capture_output=True)
    elapsed = time.time() - t0
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-8:])
        append_status(f"`{cond_name}` r{run_num} tb exited rc={proc.returncode} after {elapsed/60:.0f}m — check {tb_out}/{run_id}/run.log")
        print(tail, file=sys.stderr)

    resolved_map = parse_tb_results(tb_out, run_id)
    per_task_e2e = elapsed / max(len(tasks), 1)  # coarse; tb doesn't expose per-trial wall time here
    n_res = 0
    for task_id in tasks:
        resolved = resolved_map.get(task_id)
        row = build_row(task_id, cond_name, cond, run_num, resolved, agent_dir, round(per_task_e2e, 1))
        rows[:] = [r for r in rows if not (r["instance_id"] == task_id and r["condition"] == cond_name and r["run_num"] == run_num)]
        rows.append(row)
        n_res += 1 if row["resolved"] else 0
    save_agg(rows)
    append_status(
        f"`{cond_name}` r{run_num} done in {elapsed/60:.0f}m — resolved {n_res}/{len(tasks)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conditions", nargs="+", default=list(TB_CONDITIONS), choices=list(TB_CONDITIONS))
    ap.add_argument("--tasks-file", type=Path, default=REPO_ROOT / "task_lists" / "tbench_tasks.json")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--start-run", type=int, default=1)
    ap.add_argument("--n-concurrent", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="re-run (cond, run) pairs that already have rows")
    ap.add_argument("--tag", default="", help="suffix for run-id/output dirs so separate batches don't collide on tb.lock")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks_file)
    rows = load_agg()
    done_pairs = {(r["condition"], r["run_num"]) for r in rows}

    total = len(args.conditions) * args.runs
    launched = 0
    for run_num in range(args.start_run, args.start_run + args.runs):
        for cond_name in args.conditions:
            if not args.force and (cond_name, run_num) in done_pairs:
                task_rows = [r for r in rows if r["condition"] == cond_name and r["run_num"] == run_num]
                if len(task_rows) >= len(tasks):
                    print(f"[skip] {cond_name} r{run_num} already complete ({len(task_rows)} rows)")
                    continue
            launched += 1
            print(f"[{launched}/{total}] {cond_name} r{run_num}", flush=True)
            run_condition(cond_name, TB_CONDITIONS[cond_name], run_num, tasks, args.n_concurrent, rows, tag=args.tag)

    n_resolved = sum(1 for r in rows if r["resolved"])
    print(f"\nAll done. {len(rows)} rows total, {n_resolved} resolved. Aggregate: {AGG_PATH}")


if __name__ == "__main__":
    main()
