#!/usr/bin/env python3
"""Re-verify Terminal-Bench trials whose verifier failed, by replaying their commands.

Terminal-Bench counterpart of scripts/maintenance/reevaluate_swebench_candidates.py. The
generation is left untouched: the saved trajectory's commands are re-executed
in a fresh task container by src/agentctx/benchmarks/replay_agent.py (no model
call), then Harbor's verifier grades the rebuilt state. Only trajectories that
still contain every assistant turn are replayable; turns removed by a
compression primitive cannot be recovered, and such rows are listed but skipped.

plan:    read-only. Scans result trees for rows whose Harbor exception is in
         --exception (default VerifierTimeoutError) and no reward, decides
         replayability, detects a reward file the verifier wrote before Harbor
         gave up, writes a candidate JSON.
recover: no containers. For candidates whose raw trial directory holds a
         complete verifier run (verifier/reward.txt plus a pytest summary line
         in test-stdout.txt), records that reward as the verdict: it is the
         original container's own grading, only never parsed by Harbor.
run:     starts Harbor jobs, one per replayable candidate (recoverable ones
         are skipped unless --include-recoverable), writing evidence only under
         --output-dir (must lie outside ICLR_results, results and data).
         --dry-run prints the commands without starting anything.
apply:   previews index changes; --write backs up and updates reward/resolved
         with provenance (verdict_source="replay_verifier" or
         "verifier_reward_file", plus "reevaluation").

A replay is a reconstruction, not the original container. A verdict is applied
only when the replay is shown to reproduce the run: every command executed
without an error, returned the exit code recorded in the trajectory and, unless
--accept-output-mismatch is given, produced the recorded output. A command whose
observation was cleared by a compression primitive cannot be checked and, unless
--accept-uncomparable is given, also blocks the verdict (the submission echo is
exempt). Anything else is stored as "divergent" evidence and never written to
the indexes. `plan` reports per candidate how many commands lack an observation
(n_uncomparable) so fully checkable candidates can be chosen up front.

Typical sequence:

    python3 scripts/maintenance/replay_reverify_tb.py plan --out logs/replay_reverify/candidates.json
    python3 scripts/maintenance/replay_reverify_tb.py recover \\
        --candidates logs/replay_reverify/candidates.json --output-dir logs/replay_reverify/recover1
    venv-harbor/bin/python scripts/maintenance/replay_reverify_tb.py run \\
        --candidates logs/replay_reverify/candidates.json \\
        --output-dir logs/replay_reverify/run1 --limit 1        # smoke test first
    python3 scripts/maintenance/replay_reverify_tb.py apply --output-dir logs/replay_reverify/run1 [--write]
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agentctx.benchmarks.tb_verdict import (  # noqa: E402
    VERDICT_FIELDS, raw_trial_dir, reward_file_evidence, select_trials, verdict_fields, verifier_env_args,
)

DEFAULT_ROOTS = (
    ROOT / "ICLR_results" / "terminalbench",
    ROOT / "ICLR_results" / "terminalbench2",
)
PROTECTED_ROOTS = ("ICLR_results", "results", "data")
DATASETS = {
    "terminal-bench-core@0.1.1": ROOT / "data" / "tb1-harbor-0.1.1",
    "terminal-bench@2.0": ROOT / "data" / "tb2-harbor-prebuilt-2.0",
}
DEFAULT_EXCEPTIONS = ("VerifierTimeoutError",)
DEFAULT_CONFIG_SPECS = str(ROOT / "configs" / "config-tbench.yaml")
REPLAY_AGENT = "agentctx.benchmarks.replay_agent:ReplayAgent"
# Fields that describe evaluation or bookkeeping, not the generation.
PROVENANCE_FIELDS = set(VERDICT_FIELDS) | {
    "reevaluation", "verdict_audit", "attempts", "previous_attempts", "superseded_dir",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def read(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(row: dict) -> str:
    """Hash of the generation record; evaluation and bookkeeping fields excluded."""
    return sha(json.dumps({k: v for k, v in row.items() if k not in PROVENANCE_FIELDS},
                          sort_keys=True).encode())


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def resolved_roots(names) -> list[Path]:
    return [(ROOT / name).resolve() for name in names]


def run_dir_of(index: Path, row: dict) -> Path:
    return index.parent / str(row["instance_id"]) / str(row["condition"]) / f"run_{row.get('run_num', 1)}"


# raw_trial_dir / reward_file_evidence live in agentctx.benchmarks.tb_verdict so the
# normal runners recover reward files at collection time with the same rule.
_ = raw_trial_dir


def analyze_trajectory(trajectory: dict, row: dict) -> dict[str, Any]:
    """Decide whether the saved trajectory still holds every executed command."""
    messages = trajectory.get("messages") or []
    assistant = [m for m in messages if m.get("role") == "assistant"]
    n_actions = sum(len((m.get("extra") or {}).get("actions") or []) for m in assistant)
    # Commands whose observation is no longer in the trajectory (cleared by a
    # compression primitive) cannot be checked after the replay; the
    # submission echo is exempt (see SAFE_UNCOMPARABLE_COMMANDS).
    n_uncomparable = 0
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        actions = (message.get("extra") or {}).get("actions") or []
        following = messages[index + 1] if index + 1 < len(messages) else {}
        extra = following.get("extra") if following.get("role") == "user" else None
        comparable = len(actions) == 1 and isinstance(extra, dict) and "raw_output" in extra
        if not comparable:
            n_uncomparable += sum(not is_safe_uncomparable(a.get("command", "")) for a in actions)
    n_calls = row.get("n_calls")
    if n_calls is None:
        n_calls = ((trajectory.get("info") or {}).get("model_stats") or {}).get("api_calls")
    n_calls = int(n_calls or 0)
    events = int(row.get("compression_events") or 0)
    info = {"n_calls": n_calls, "n_assistant": len(assistant), "n_actions": n_actions,
            "n_uncomparable": n_uncomparable, "compression_events": events}
    if n_actions == 0:
        return {**info, "replayable": False, "reason": "trajectory holds no commands"}
    if events == 0:
        # Without a compression event the message list is the complete history
        # (n_calls may exceed the turn count by failed API attempts).
        return {**info, "replayable": True, "reason": "no compression event"}
    if len(assistant) == n_calls:
        return {**info, "replayable": True,
                "reason": f"all {n_calls} assistant turns present despite {events} compression event(s)"}
    return {**info, "replayable": False,
            "reason": f"compression removed {n_calls - len(assistant)} of {n_calls} assistant turns"}


# ── plan ─────────────────────────────────────────────────────────────────────

def plan(args) -> int:
    roots = [r if r.is_absolute() else ROOT / r for r in (args.source_root or list(DEFAULT_ROOTS))]
    roots = [r for r in roots if r.is_dir()]
    if not roots:
        raise ValueError("no result tree found")
    exceptions = set(args.exception or DEFAULT_EXCEPTIONS)
    candidates: list[dict] = []
    reasons = collections.Counter()
    per_cell = collections.defaultdict(collections.Counter)
    for root in roots:
        for index in sorted(root.rglob("experiment_results.json")):
            for row in read(index):
                if row.get("reward") is not None:
                    continue
                run_dir = run_dir_of(index, row)
                harbor_path = run_dir / "harbor_result.json"
                trajectory_path = run_dir / "trajectory.json"
                if not harbor_path.exists():
                    continue
                harbor = read(harbor_path)
                verdict = verdict_fields(harbor)
                if verdict["reward"] is not None or verdict["harbor_exception"] not in exceptions:
                    continue
                cell = display_path(index.parent)
                if not trajectory_path.exists():
                    analysis = {"replayable": False, "reason": "no trajectory.json",
                                "n_calls": row.get("n_calls"), "n_assistant": 0, "n_actions": 0,
                                "n_uncomparable": 0, "compression_events": row.get("compression_events")}
                    raw = b""
                else:
                    raw = trajectory_path.read_bytes()
                    analysis = analyze_trajectory(json.loads(raw), row)
                reasons[(analysis["replayable"], analysis["reason"].split(" despite")[0].split(" removed")[0])] += 1
                per_cell[cell]["replayable" if analysis["replayable"] else "not_replayable"] += 1
                reward_file = reward_file_evidence(harbor)
                if reward_file is not None:
                    per_cell[cell]["reward_file"] += 1
                candidates.append({
                    "result_file": display_path(index), "key": row["key"], "task": row["instance_id"],
                    "condition": row["condition"], "run_num": row.get("run_num", 1),
                    "cell": cell, "run_dir": display_path(run_dir),
                    "trajectory": display_path(trajectory_path),
                    "trajectory_sha256": sha(raw) if raw else None,
                    "dataset": row.get("dataset"), "benchmark_version": row.get("benchmark_version"),
                    "harbor_exception": verdict["harbor_exception"],
                    "harbor_exception_message": verdict["harbor_exception_message"],
                    "exit_status": row.get("exit_status"), "timestamp": row.get("timestamp"),
                    "previous_resolved": row.get("resolved"), "previous_reward": row.get("reward"),
                    "generation_sha256": identity(row),
                    "reward_file": reward_file,
                    **analysis,
                })
    replayable = sum(c["replayable"] for c in candidates)
    recoverable = sum(c["reward_file"] is not None for c in candidates)
    print(f"Candidates: {len(candidates)} ({replayable} replayable, {len(candidates) - replayable} not; "
          f"{recoverable} with a complete verifier reward file)")
    for (ok, reason), count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {count:5d}  {'replayable' if ok else 'skip':10s} {reason}")
    checkable = sum(c["replayable"] and c["n_uncomparable"] == 0 for c in candidates)
    print(f"Replayable with every command checkable against a recorded observation: {checkable} of {replayable} "
          f"(the rest need --accept-uncomparable to be applied)")
    if recoverable:
        both = sum(c["replayable"] and c["reward_file"] is not None for c in candidates)
        print(f"Reward file recoverable without containers: {recoverable} "
              f"({both} of them also replayable, {recoverable - both} not replayable)")
    print("Per cell:")
    for cell in sorted(per_cell):
        print(f"  {cell}: {dict(per_cell[cell])}")
    if not candidates:
        print("Nothing to write.")
        return 0
    out = args.out if args.out.is_absolute() else ROOT / args.out
    save(out, {"schema": 1, "created": dt.datetime.now().isoformat(),
               "exceptions": sorted(exceptions), "candidates": candidates})
    print(f"Wrote {display_path(out)}")
    return 0


# ── run ──────────────────────────────────────────────────────────────────────

def load_candidates(path: Path, *, only: list[str] | None, limit: int | None,
                    mode: str = "replay", include_recoverable: bool = False) -> list[dict]:
    payload = read(path)
    if mode == "recover":
        items = [c for c in payload["candidates"] if c.get("reward_file")]
        skipped = len(payload["candidates"]) - len(items)
    else:
        items = [c for c in payload["candidates"] if c["replayable"]]
        skipped = len(payload["candidates"]) - len(items)
        if not include_recoverable:
            recoverable = [c for c in items if c.get("reward_file")]
            if recoverable:
                print(f"Skipping {len(recoverable)} replayable candidate(s) that have a verifier reward file; "
                      "use `recover` for them or pass --include-recoverable.")
            items = [c for c in items if not c.get("reward_file")]
    if only:
        wanted = set(only)
        items = [c for c in items if c["key"] in wanted]
        missing = wanted - {c["key"] for c in items}
        if missing:
            raise ValueError(f"--only keys not replayable or unknown: {', '.join(sorted(missing))}")
    if limit is not None:
        items = items[:limit]
    if not items:
        raise ValueError(f"no {'recoverable' if mode == 'recover' else 'replayable'} candidates selected")
    # The generation evidence must not have changed since the plan.
    for item in items:
        src = ROOT / item["result_file"]
        rows = [r for r in read(src) if r["key"] == item["key"]]
        if len(rows) != 1:
            raise ValueError(f"expected exactly one row for {item['key']} in {item['result_file']}")
        if identity(rows[0]) != item["generation_sha256"]:
            raise ValueError(f"generation record changed since the plan: {item['key']}")
        if sha((ROOT / item["trajectory"]).read_bytes()) != item["trajectory_sha256"]:
            raise ValueError(f"trajectory changed since the plan: {item['key']}")
    print(f"Selected {len(items)} candidate(s); {skipped} in the plan file are not "
          f"{'recoverable' if mode == 'recover' else 'replayable'}.")
    return items


# ── recover ──────────────────────────────────────────────────────────────────

def recover_evidence(item: dict) -> dict:
    """Re-derive the reward-file verdict from disk and check it against the plan."""
    harbor = read(ROOT / item["run_dir"] / "harbor_result.json")
    fresh = reward_file_evidence(harbor)
    if fresh is None:
        raise ValueError("reward file or pytest summary no longer present")
    planned = item["reward_file"]
    if (fresh["reward_sha256"], fresh["stdout_sha256"]) != (planned["reward_sha256"], planned["stdout_sha256"]):
        raise ValueError("verifier files changed since the plan")
    return {"method": "reward_file", "reward": fresh["reward"], "resolved": fresh["reward"] > 0,
            "reward_file": fresh}


def recover(args) -> int:
    output = args.output_dir.resolve()
    if any(output.is_relative_to(root) for root in resolved_roots(PROTECTED_ROOTS)):
        raise ValueError("Use an output directory outside ICLR_results, results and data")
    items = load_candidates(args.candidates, only=args.only, limit=args.limit, mode="recover")
    manifest_path = output / "manifest.json"
    if output.exists():
        if not args.resume or not manifest_path.is_file():
            raise ValueError("Output already exists. Use a fresh directory or --resume with its manifest")
        manifest = read(manifest_path)
        if [(r["result_file"], r["key"]) for r in manifest["items"]] != [(r["result_file"], r["key"]) for r in items]:
            raise ValueError("Candidate selection changed since the saved manifest")
    else:
        manifest = {"schema": 1, "created": dt.datetime.now().isoformat(), "method": "reward_file",
                    "candidates": str(args.candidates.resolve()), "items": items}
    save(manifest_path, manifest)
    result_path = output / "results.json"
    results = read(result_path) if result_path.exists() else {}
    failed = []
    for index, item in enumerate(items):
        evidence = {"status": "error", "key": item["key"], "task": item["task"], "cell": item["cell"],
                    "started": dt.datetime.now().isoformat()}
        try:
            evidence.update(recover_evidence(item))
            evidence["status"] = "verified"
            print(f"[{index + 1}] {item['cell']} / {item['key']}: resolved={evidence['resolved']} "
                  f"({evidence['reward_file']['pytest_summary']})")
        except ValueError as exc:
            evidence["error"] = str(exc)
            failed.append(item["key"])
            print(f"[{index + 1}] !! {item['key']}: {exc}")
        evidence["finished"] = dt.datetime.now().isoformat()
        results[str(index)] = evidence
        save(result_path, results)
    print(f"Evidence saved: {output}\nCanonical results were not updated.")
    if failed:
        print(f"Not recoverable after all: {len(failed)}")
        return 1
    return 0


def dataset_for(item: dict, override: Path | None) -> Path:
    if override is not None:
        return override
    try:
        return DATASETS[item["dataset"]]
    except KeyError:
        raise ValueError(f"unknown dataset {item['dataset']!r} for {item['key']}; pass --dataset-path") from None


def build_command(args, item: dict, attempt: Path, job_name: str) -> list[str]:
    command = [
        str(args.harbor_bin), "run",
        "--agent", REPLAY_AGENT,
        "--model", args.model_name,
        "--path", str(dataset_for(item, args.dataset_path)),
        "--n-attempts", "1",
        "--max-retries", "0",
        "--n-tasks", "1",
        "--n-concurrent", "1",
        "--verifier-timeout-multiplier", str(args.verifier_timeout_multiplier),
        "--env", "docker",
        "--cpus", "ignore",
        "--jobs-dir", str(attempt / "harbor_jobs"),
        "--job-name", job_name,
        "--yes",
        *verifier_env_args(args.verifier_threads),
        "--include-task-name", item["task"],
    ]
    return command


def evaluate_one(args, index: int, item: dict, output: Path, env: dict[str, str]) -> dict:
    attempt = output / "jobs" / f"{index:04d}" / uuid.uuid4().hex
    trajectory = attempt / "trajectory.json"
    job_name = f"replay-{index:04d}-{uuid.uuid4().hex[:8]}"
    command = build_command(args, item, attempt, job_name)
    job_env = {**env, "REPLAY_TRAJECTORY": str(trajectory)}
    evidence = {
        "status": "error", "key": item["key"], "task": item["task"], "cell": item["cell"],
        "command": command, "cwd": str(ROOT), "attempt_dir": str(attempt),
        "job_dir": str(attempt / "harbor_jobs" / job_name),
        "trajectory_sha256": item["trajectory_sha256"],
        "started": dt.datetime.now().isoformat(),
    }
    if args.dry_run:
        evidence["status"] = "dry_run"
        print(f"[{index + 1}] {item['cell']} / {item['key']} ({item['n_actions']} commands)\n"
              f"    REPLAY_TRAJECTORY={trajectory}\n    {shlex.join(command)}")
        return evidence
    attempt.mkdir(parents=True)
    # A private copy of the trajectory: the evidence must not depend on the
    # canonical tree staying unchanged.
    shutil.copy2(ROOT / item["trajectory"], trajectory)
    print(f"[{index + 1}] replaying {item['cell']} / {item['key']} ({item['n_actions']} commands)", flush=True)
    with (attempt / "harness.log").open("w") as log:
        proc = subprocess.run(command, cwd=ROOT, env=job_env, stdout=log, stderr=subprocess.STDOUT)
    evidence["returncode"] = proc.returncode
    evidence["finished"] = dt.datetime.now().isoformat()
    try:
        evidence.update(collect_evidence(item, Path(evidence["job_dir"]),
                                         accept_output_mismatch=args.accept_output_mismatch,
                                         accept_uncomparable=args.accept_uncomparable))
        evidence["status"] = "verified"
    except Divergent as exc:
        # Graded, but not a reproduction of the original run: kept as evidence
        # for inspection, never applied.
        evidence["status"] = "divergent"
        evidence["error"] = str(exc)
    except ValueError as exc:
        evidence["error"] = str(exc)
    return evidence


class Divergent(ValueError):
    """The replay ran and was graded, but it did not reproduce the original run."""


# Commands whose effect needs no recorded observation to be trusted: the
# submission marker only echoes a constant and changes nothing.
SAFE_UNCOMPARABLE_COMMANDS = frozenset({"echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"})


def is_safe_uncomparable(command: str) -> bool:
    return command.strip() in SAFE_UNCOMPARABLE_COMMANDS


def divergence(log: list[dict], *, accept_output_mismatch: bool,
               accept_uncomparable: bool = False) -> dict[str, list[int]]:
    """Steps where the replay differed from the original run, or cannot be checked.

    A command that errored (timeout, exec failure) or returned a different
    exit code rebuilt a different state, so the verdict would grade the
    replay's failure, not the agent's work. Output text can differ for benign
    reasons (timestamps, pids), so output mismatches are fatal only unless
    ``accept_output_mismatch`` is set; they are always reported.

    A step whose original observation is missing (cleared by a compression
    primitive) cannot be checked at all; "not shown to differ" is not "shown
    to match", so such steps are fatal too unless ``accept_uncomparable`` is
    set. The only exception is a command whose effect is known without an
    observation (``SAFE_UNCOMPARABLE_COMMANDS``).
    """
    found = {
        "errors": [s["step"] for s in log if s.get("exception")],
        "returncode_mismatch": [s["step"] for s in log if s.get("returncode_match") is False],
        "output_mismatch": [s["step"] for s in log if s.get("output_match") is False],
        "uncomparable": [s["step"] for s in log
                         if s.get("returncode_match") is None and not is_safe_uncomparable(s.get("command", ""))],
    }
    fatal = found["errors"] + found["returncode_mismatch"]
    if not accept_output_mismatch:
        fatal += found["output_mismatch"]
    if not accept_uncomparable:
        fatal += found["uncomparable"]
    found["fatal"] = sorted(set(fatal))
    return found


def collect_evidence(item: dict, job_dir: Path, *, accept_output_mismatch: bool = False,
                     accept_uncomparable: bool = False) -> dict:
    """Read the replay job's trial: verdict plus replay fidelity.

    Raises ValueError when the trial is unusable and Divergent when the replay
    did not reproduce the original run (such a verdict must not be applied).
    """
    selected, _ = select_trials(job_dir, [item["task"]])
    if item["task"] not in selected:
        raise ValueError(f"no trial result for {item['task']} in {job_dir}")
    result_path = selected[item["task"]]
    result = read(result_path)
    verdict = verdict_fields(result)
    agent_dir = result_path.parent / "agent"
    summary = read(agent_dir / "replay_summary.json") if (agent_dir / "replay_summary.json").exists() else None
    log = read(agent_dir / "replay_log.json") if (agent_dir / "replay_log.json").exists() else []
    evidence = {
        "result_json": str(result_path), "replay_summary": summary,
        "harbor_exception": verdict["harbor_exception"],
        "harbor_exception_message": verdict["harbor_exception_message"],
    }
    if summary is None:
        raise ValueError("replay agent wrote no replay_summary.json")
    if summary.get("trajectory_sha256") != item["trajectory_sha256"]:
        raise ValueError("replayed trajectory differs from the candidate trajectory")
    if not summary.get("complete"):
        raise ValueError(f"replay incomplete: {summary.get('n_executed')}/{summary.get('n_actions')} commands "
                         f"({verdict['harbor_exception'] or 'no exception'})")
    if len(log) != summary.get("n_actions"):
        raise ValueError(f"replay_log.json holds {len(log)} steps, expected {summary.get('n_actions')}")
    if verdict["reward"] is None:
        raise ValueError(f"verifier produced no reward: {verdict['harbor_exception']}: "
                         f"{verdict['harbor_exception_message']}")
    found = divergence(log, accept_output_mismatch=accept_output_mismatch,
                       accept_uncomparable=accept_uncomparable)
    evidence.update({"reward": verdict["reward"], "resolved": verdict["resolved"], "divergence": found,
                     "accept_output_mismatch": accept_output_mismatch,
                     "accept_uncomparable": accept_uncomparable})
    if found["fatal"]:
        raise Divergent(
            f"replay not shown to reproduce the original run at step(s) {found['fatal']} "
            f"(errors {found['errors']}, returncode mismatch {found['returncode_mismatch']}, "
            f"output mismatch {found['output_mismatch']}, no original observation {found['uncomparable']}); "
            f"verdict resolved={verdict['resolved']} not applicable")
    return evidence


def run(args) -> int:
    output = args.output_dir.resolve()
    if any(output.is_relative_to(root) for root in resolved_roots(PROTECTED_ROOTS)):
        raise ValueError("Use an output directory outside ICLR_results, results and data "
                         "(for example logs/replay_reverify/<name>)")
    items = load_candidates(args.candidates, only=args.only, limit=args.limit,
                            include_recoverable=args.include_recoverable)
    manifest_path = output / "manifest.json"
    if output.exists() and not args.dry_run:
        if not args.resume or not manifest_path.is_file():
            raise ValueError("Output already exists. Use a fresh directory or --resume with its manifest")
        manifest = read(manifest_path)
        old = [(r["result_file"], r["key"], r["generation_sha256"]) for r in manifest["items"]]
        new = [(r["result_file"], r["key"], r["generation_sha256"]) for r in items]
        if old != new:
            raise ValueError("Candidate selection changed since the saved manifest")
    else:
        manifest = {"schema": 1, "created": dt.datetime.now().isoformat(),
                    "candidates": str(args.candidates.resolve()),
                    "verifier_timeout_multiplier": args.verifier_timeout_multiplier,
                    "verifier_threads": args.verifier_threads,
                    "accept_output_mismatch": args.accept_output_mismatch,
                    "accept_uncomparable": args.accept_uncomparable, "items": items}
    env = os.environ.copy()
    env.setdefault("DOCKER_HOST", f"unix:///run/user/{os.getuid()}/podman/podman.sock")
    env.update({
        "COMPOSE_BAKE": "false",
        "PYTHONPATH": os.pathsep.join(p for p in (str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH")) if p),
        "REPLAY_CONFIG_SPECS": args.config_specs,
    })
    if not args.dry_run:
        if not Path(args.harbor_bin).is_file():
            raise ValueError(f"Harbor executable not found: {args.harbor_bin}")
        health = subprocess.run(["docker", "info"], cwd=ROOT, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if health.returncode:
            raise ValueError(f"container service not reachable through DOCKER_HOST={env['DOCKER_HOST']}")
        save(manifest_path, manifest)
    result_path = output / "results.json"
    results = read(result_path) if result_path.exists() and not args.dry_run else {}
    lock = threading.Lock()
    stop = threading.Event()
    unverified: list[str] = []
    divergent: list[str] = []

    def work(index: int, item: dict) -> None:
        slot = str(index)
        with lock:
            done = results.get(slot, {}).get("status") == "verified"
        if done:
            print(f"[{index + 1}] verified already: {item['key']}", flush=True)
            return
        if stop.is_set():
            return
        evidence = evaluate_one(args, index, item, output, env)
        with lock:
            results[slot] = evidence
            if not args.dry_run:
                save(result_path, results)
            if evidence["status"] == "verified":
                print(f"    -> {item['key']}: resolved={evidence['resolved']} "
                      f"(reward {evidence['reward']}; output match "
                      f"{evidence['replay_summary']['n_output_matched']}/{evidence['replay_summary']['n_compared']})",
                      flush=True)
            elif evidence["status"] == "divergent":
                divergent.append(item["key"])
                print(f"    ~~ divergent {item['key']}: {evidence['error']}. Inspect {evidence['attempt_dir']}",
                      flush=True)
            elif evidence["status"] == "error":
                unverified.append(item["key"])
                print(f"    !! unverified {item['key']}: {evidence['error']}. Inspect {evidence['attempt_dir']}",
                      flush=True)
                if not args.continue_on_error:
                    stop.set()

    if args.n_parallel > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.n_parallel) as pool:
            list(pool.map(lambda pair: work(*pair), enumerate(items)))
    else:
        for index, item in enumerate(items):
            work(index, item)
            if stop.is_set():
                break
    if args.dry_run:
        print(f"\nDry run: {len(items)} Harbor job(s) would be started; nothing was executed or written.")
        return 0
    print(f"Evaluation evidence saved: {output}\nCanonical results were not updated.")
    if divergent:
        print(f"Divergent replays (graded but not applicable): {len(divergent)}")
        for key in divergent:
            print(f"  {key}")
    if unverified:
        print(f"Unverified candidates: {len(unverified)} (fix the cause and rerun with --resume)")
        for key in unverified:
            print(f"  {key}")
        return 1
    return 0


# ── apply ────────────────────────────────────────────────────────────────────

def checked_evidence(item: dict, evidence: dict, *, accept_output_mismatch: bool,
                     accept_uncomparable: bool) -> tuple[float, bool]:
    """Re-derive the verdict (and, for replays, the divergence check) from the files on disk."""
    if evidence.get("status") != "verified":
        raise ValueError("evidence not verified")
    if evidence.get("method") == "reward_file":
        fresh = recover_evidence(item)
    else:
        fresh = collect_evidence(item, Path(evidence["job_dir"]), accept_output_mismatch=accept_output_mismatch,
                                 accept_uncomparable=accept_uncomparable)
    if fresh["reward"] != evidence.get("reward") or fresh["resolved"] != evidence.get("resolved"):
        raise ValueError("saved evidence differs from the trial files")
    return fresh["reward"], fresh["resolved"]


def provenance(item: dict, evidence: dict, manifest: dict, row: dict, stamp: str) -> tuple[dict, str]:
    """(reevaluation record, verdict_source) for one applied verdict."""
    base = {"evaluated_at": evidence.get("finished") or stamp,
            "previous": {field: row.get(field) for field in VERDICT_FIELDS}}
    if evidence.get("method") == "reward_file":
        rf = evidence["reward_file"]
        return ({**base, "method": "reward_file", "trial_dir": rf["trial_dir"],
                 "reward_sha256": rf["reward_sha256"], "stdout_sha256": rf["stdout_sha256"],
                 "pytest_summary": rf["pytest_summary"]}, "verifier_reward_file")
    summary = evidence["replay_summary"]
    return ({**base, "method": "replay", "result_json": evidence["result_json"], "job_dir": evidence["job_dir"],
             "trajectory_sha256": evidence["trajectory_sha256"],
             "verifier_timeout_multiplier": manifest.get("verifier_timeout_multiplier"),
             "accept_output_mismatch": bool(manifest.get("accept_output_mismatch")),
             "accept_uncomparable": bool(manifest.get("accept_uncomparable")),
             "replay": {k: summary.get(k) for k in ("n_actions", "n_executed", "n_errors", "n_compared",
                                                     "n_output_matched", "n_returncode_matched")},
             "divergence": evidence.get("divergence")}, "replay_verifier")


def apply(args) -> int:
    output = args.output_dir.resolve()
    manifest = read(output / "manifest.json")
    results = read(output / "results.json") if (output / "results.json").exists() else {}
    updates: dict[Path, list] = {}
    hashes: dict[Path, str] = {}
    pending, divergent, changes = [], [], []
    accept_output_mismatch = bool(manifest.get("accept_output_mismatch"))
    accept_uncomparable = bool(manifest.get("accept_uncomparable"))
    stamp = dt.datetime.now().isoformat()
    for index, item in enumerate(manifest["items"]):
        evidence = results.get(str(index), {})
        if evidence.get("status") == "divergent":
            divergent.append(item["key"])
            continue
        if evidence.get("status") != "verified":
            pending.append(item["key"])
            continue
        reward, resolved = checked_evidence(item, evidence, accept_output_mismatch=accept_output_mismatch,
                                            accept_uncomparable=accept_uncomparable)
        src = ROOT / item["result_file"]
        if src not in updates:
            raw = src.read_bytes()
            hashes[src] = sha(raw)
            updates[src] = json.loads(raw)
        matches = [r for r in updates[src] if r["key"] == item["key"]]
        if len(matches) != 1 or identity(matches[0]) != item["generation_sha256"]:
            raise ValueError(f"generation changed after planning: {item['key']}")
        row = matches[0]
        changes.append({"cell": item["cell"], "key": item["key"],
                        "before": row.get("resolved"), "after": resolved, "reward": reward})
        row["reevaluation"], row["verdict_source"] = provenance(item, evidence, manifest, row, stamp)
        row["reward"] = reward
        row["resolved"] = resolved
        # harbor_exception keeps the original trial's failure for provenance.
    print(f"Verified evaluations: {len(changes)}; divergent (never applied): {len(divergent)}; "
          f"pending/errors: {len(pending)}")
    print(f"Resolved values changing: {sum(r['before'] != r['after'] for r in changes)}")
    for cell in sorted({c["cell"] for c in changes}):
        group = [c for c in changes if c["cell"] == cell]
        print(f"  {cell}: {len(group)} verified; {sum(c['after'] for c in group)} resolved after re-verification")
    if not args.write:
        print("Preview only. Add --write to back up and update canonical indexes.")
        return 0
    if pending and not args.allow_partial:
        raise ValueError("Unverified candidates remain; no indexes changed. Finish them, or use --allow-partial")
    if not changes:
        raise ValueError("No verified results to apply")
    backup = output / "backups" / uuid.uuid4().hex
    for src, expected in hashes.items():
        if sha(src.read_bytes()) != expected:
            raise ValueError(f"Index changed concurrently: {src}")
    for src in updates:
        dest = backup / display_path(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    save(backup / "changes.json", changes)
    for src, rows in updates.items():
        if sha(src.read_bytes()) != hashes[src]:
            raise ValueError(f"Index changed during apply; stop and inspect backups: {backup}")
        src.write_text(json.dumps(rows, indent=2))
    print(f"Updated {len(changes)} result rows. Backup and change list: {backup}")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    sub = commands.add_parser("plan", help="read-only candidate scan")
    sub.add_argument("--source-root", type=Path, action="append", default=None)
    sub.add_argument("--exception", action="append", default=None,
                     help=f"Harbor exception types to select (repeatable; default {DEFAULT_EXCEPTIONS[0]})")
    sub.add_argument("--out", type=Path,
                     default=Path("logs") / "replay_reverify" / f"candidates_{dt.date.today():%Y%m%d}.json")

    sub = commands.add_parser("recover", help="adopt reward files the verifier wrote before Harbor timed out")
    sub.add_argument("--candidates", type=Path, required=True)
    sub.add_argument("--output-dir", type=Path, required=True)
    sub.add_argument("--limit", type=int, default=None)
    sub.add_argument("--only", action="append", default=None, metavar="KEY")
    sub.add_argument("--resume", action="store_true")

    sub = commands.add_parser("run", help="replay and verify (starts containers)")
    sub.add_argument("--candidates", type=Path, required=True)
    sub.add_argument("--output-dir", type=Path, required=True)
    sub.add_argument("--include-recoverable", action="store_true",
                     help="also replay candidates that have a verifier reward file (default: leave them to recover)")
    sub.add_argument("--harbor-bin", type=Path, default=ROOT / "venv-harbor" / "bin" / "harbor")
    sub.add_argument("--dataset-path", type=Path, default=None,
                     help="override the dataset chosen from each row's dataset field")
    sub.add_argument("--config-specs", default=DEFAULT_CONFIG_SPECS,
                     help="os.pathsep-separated agent configs supplying environment.env/timeout")
    sub.add_argument("--model-name", default="replay/trajectory",
                     help="bookkeeping model name for Harbor (no model is called)")
    sub.add_argument("--verifier-timeout-multiplier", type=float, default=1.0)
    sub.add_argument("--verifier-threads", type=int, default=8,
                     help="OMP/BLAS thread cap inside the verifier (default 8)")
    sub.add_argument("--accept-output-mismatch", action="store_true",
                     help="treat differing command output as benign (timestamps, pids); command errors and "
                          "differing exit codes always mark the replay divergent")
    sub.add_argument("--accept-uncomparable", action="store_true",
                     help="apply verdicts even when some commands have no recorded observation to check "
                          "against (default: such replays are kept as divergent evidence; the submission "
                          "echo is always exempt)")
    sub.add_argument("--n-parallel", type=int, default=1, help="Harbor jobs to run concurrently")
    sub.add_argument("--limit", type=int, default=None, help="only the first N replayable candidates")
    sub.add_argument("--only", action="append", default=None, metavar="KEY", help="restrict to these row keys")
    sub.add_argument("--resume", action="store_true")
    sub.add_argument("--continue-on-error", action="store_true")
    sub.add_argument("--dry-run", action="store_true", help="print the Harbor commands; start nothing, write nothing")

    sub = commands.add_parser("apply", help="preview or write verified verdicts into the indexes")
    sub.add_argument("--output-dir", type=Path, required=True)
    sub.add_argument("--write", action="store_true")
    sub.add_argument("--allow-partial", action="store_true")

    args = parser.parse_args()
    if args.command == "plan":
        return plan(args)
    if args.command == "run":
        if args.verifier_timeout_multiplier <= 0 or args.verifier_threads <= 0 or args.n_parallel <= 0:
            raise ValueError("--verifier-timeout-multiplier, --verifier-threads and --n-parallel must be positive")
        if args.dry_run:
            return run(args)
    output = args.output_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / ("." + output.name + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another replay command is using this output directory") from None
        return {"run": run, "recover": recover, "apply": apply}[args.command](args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
