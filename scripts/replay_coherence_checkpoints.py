#!/usr/bin/env python3
"""Replay RQ2 checkpoint prefixes in disposable SWE-bench containers.

The tool re-executes the recorded commands through the selected current-state
observation. It compares every return code and normalized output hash with the
stored full-context trajectory. Only checkpoints that pass this screen should
enter the causal pilot.

Examples
--------
  python3 scripts/replay_coherence_checkpoints.py \
    --manifest results/coherence/rq2_checkpoints.json \
    --max-checkpoints 1 \
    --output results/coherence/rq2_replay_screen.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

from coherence_lineage import ROOT, load_history, output_hash


def run_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def replay_checkpoint(checkpoint: dict, args: argparse.Namespace) -> dict:
    trajectory = ROOT / checkpoint["trajectory"]
    history = load_history(trajectory)
    if history.event_source != "trajectory" or not history.history_complete:
        return {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "eligible": False,
            "error": "checkpoint does not have a complete structured trajectory",
        }

    events = [event for event in history.events if event.step <= int(checkpoint["current_step"])]
    if args.dry_run:
        return {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "eligible": False,
            "dry_run": True,
            "commands": [event.command for event in events],
        }

    image = checkpoint.get("image") or history.image
    cwd = checkpoint.get("cwd") or history.cwd
    if not image:
        return {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "eligible": False,
            "error": "trajectory does not record a container image",
        }

    name = f"agentctx-coherence-{uuid.uuid4().hex[:10]}"
    env = os.environ.copy()
    if args.docker_host:
        env["DOCKER_HOST"] = args.docker_host

    launch = subprocess.run(
        [
            args.container_command,
            "run",
            "-d",
            "--name",
            name,
            "--rm",
            "-w",
            cwd,
            image,
            "sleep",
            "2h",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.pull_timeout,
        check=False,
        env=env,
    )
    if launch.returncode != 0:
        return {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "eligible": False,
            "error": f"container launch failed: {(launch.stdout + launch.stderr)[-1000:]}",
        }

    # Use the explicit name. Podman can emit pull progress before the ID.
    container = name
    comparisons = []
    try:
        for event in events:
            try:
                replayed = subprocess.run(
                    [
                        args.container_command,
                        "exec",
                        "-w",
                        cwd,
                        container,
                        "bash",
                        "-lc",
                        event.command,
                    ],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=args.command_timeout,
                    check=False,
                    env=env,
                )
                replay_hash = output_hash(replayed.stdout)
                comparisons.append(
                    {
                        "step": event.step,
                        "returncode_expected": event.returncode,
                        "returncode_replayed": replayed.returncode,
                        "returncode_match": replayed.returncode == event.returncode,
                        "output_sha256_expected": event.output_sha256,
                        "output_sha256_replayed": replay_hash,
                        "output_match": replay_hash == event.output_sha256,
                    }
                )
            except subprocess.TimeoutExpired:
                comparisons.append(
                    {
                        "step": event.step,
                        "returncode_match": False,
                        "output_match": False,
                        "timeout": True,
                    }
                )
                break
    finally:
        subprocess.run(
            [args.container_command, "rm", "-f", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
            env=env,
        )

    exact = [item for item in comparisons if item.get("returncode_match") and item.get("output_match")]
    stale = next(
        (item for item in comparisons if item["step"] == int(checkpoint["stale_step"])),
        None,
    )
    current = next(
        (item for item in comparisons if item["step"] == int(checkpoint["current_step"])),
        None,
    )
    all_exact = len(comparisons) == len(events) and len(exact) == len(events)
    mutation_steps = {event.step for event in events if event.is_mutation}
    mutation_returncodes_match = all(
        item.get("returncode_match")
        for item in comparisons
        if item["step"] in mutation_steps
    )
    resource_state_exact = bool(
        stale
        and current
        and stale.get("returncode_match")
        and stale.get("output_match")
        and current.get("returncode_match")
        and current.get("output_match")
    )
    return {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "task": checkpoint["task"],
        "trajectory": checkpoint["trajectory"],
        "events_expected": len(events),
        "events_replayed": len(comparisons),
        "exact_events": len(exact),
        "prefix_exact_rate": len(exact) / len(events) if events else 0.0,
        "prefix_exact": all_exact,
        "stale_output_match": bool(stale and stale.get("output_match")),
        "current_output_match": bool(current and current.get("output_match")),
        "mutation_returncodes_match": mutation_returncodes_match,
        "resource_state_exact": resource_state_exact,
        "eligible": resource_state_exact and mutation_returncodes_match,
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-checkpoints", type=int)
    parser.add_argument("--checkpoint-id", action="append", help="Replay only the named checkpoint")
    parser.add_argument("--container-command", default="docker")
    parser.add_argument("--docker-host", default=f"unix:///run/user/{os.getuid()}/podman/podman.sock")
    parser.add_argument("--command-timeout", type=int, default=120)
    parser.add_argument("--pull-timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    payload = json.loads(manifest_path.read_text())
    checkpoints = payload["checkpoints"]
    if args.checkpoint_id:
        requested = set(args.checkpoint_id)
        checkpoints = [item for item in checkpoints if item["checkpoint_id"] in requested]
        missing = requested - {item["checkpoint_id"] for item in checkpoints}
        if missing:
            parser.error(f"checkpoint IDs not found: {', '.join(sorted(missing))}")
    if args.max_checkpoints is not None:
        checkpoints = checkpoints[: args.max_checkpoints]

    results = []
    for index, checkpoint in enumerate(checkpoints, 1):
        print(f"[{index}/{len(checkpoints)}] {checkpoint['checkpoint_id']}")
        result = replay_checkpoint(checkpoint, args)
        results.append(result)
        print(
            f"  eligible={result.get('eligible')} "
            f"exact={result.get('exact_events', 0)}/{result.get('events_expected', 0)}"
        )

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "manifest": str(manifest_path),
                "screened": len(results),
                "eligible": sum(bool(result.get("eligible")) for result in results),
                "results": results,
            },
            indent=2,
        )
    )
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
