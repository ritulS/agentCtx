#!/usr/bin/env python3
"""Evaluate saved patches in isolated directories; apply verified results separately.

plan: read-only candidate validation.
run: starts SWE-bench containers, writes evidence only under --output-dir.
     A harness "Patch Apply Failed" verdict counts as resolved=False (as in the
     generation runner). Stops at the first unverified row unless
     --continue-on-error is given.
apply: previews index changes; --write backs up and updates resolved + provenance.
No command launches an agent or calls a language model.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = ROOT / "ICLR_results/issue/devstral_rule_otrc_20260910/reevaluation_candidates_combined.csv"


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(row):
    # Evaluation may change, but generation evidence must stay unchanged.
    return sha(json.dumps({k: v for k, v in row.items()
                           if k not in {"resolved", "reevaluation"}}, sort_keys=True).encode())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def source_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT / "ICLR_results/swebench") or path.name != "experiment_results.json":
        raise ValueError(f"Noncanonical result file: {relative}")
    return path


def candidates(path):
    result = []
    seen = set()
    files = {}
    with path.open() as stream:
        for candidate in csv.DictReader(stream):
            if candidate["action"] != "evaluate_only":
                raise ValueError("Candidate list must contain evaluate_only rows only")
            src = source_path(candidate["result_file"])
            if src not in files:
                files[src] = read(src)
            matches = [r for r in files[src] if r["key"] == candidate["key"]]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one result: {src}: {candidate['key']}")
            row = matches[0]
            if candidate.get("timestamp") and row.get("timestamp") != candidate["timestamp"]:
                raise ValueError(f"Generation timestamp changed since the audit: {candidate['key']}")
            key = (str(src), row["key"])
            if key in seen:
                raise ValueError(f"Duplicate candidate: {key}")
            seen.add(key)
            if row["instance_id"] != candidate["task"] or int(row["run_num"]) != int(candidate["run_num"]):
                raise ValueError(f"Candidate identity mismatch: {key}")
            if not row.get("patch_generated") or not (row.get("submission") or "").strip():
                raise ValueError(f"No saved patch: {key}")
            result.append({"result_file": str(src.relative_to(ROOT)), "key": row["key"],
                           "task": row["instance_id"], "cell": candidate["cell"],
                           "reason": candidate["reason"], "generation_sha256": identity(row),
                           "patch_sha256": sha(row["submission"].encode()),
                           "submission": row["submission"], "previous_resolved": row.get("resolved")})
    if not result:
        raise ValueError("Candidate list is empty")
    return result


def display(items):
    print(f"Candidates: {len(items)}")
    for cell, count in sorted(collections.Counter(r["cell"] for r in items).items()):
        print(f"  {cell}: {count}")


APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"   # swebench.harness.constants


def patch_apply_failed(evidence):
    """True when the harness log records a patch-apply failure for this attempt."""
    log = Path(evidence.get("instance_log", ""))
    return log.is_file() and APPLY_PATCH_FAIL in log.read_text(errors="replace")


def checked_report(item, evidence):
    report = Path(evidence["report"])
    patch = Path(evidence["patch"])
    if not patch.is_file():
        raise ValueError("Missing internal patch.diff")
    if sha(patch.read_bytes()) != item["patch_sha256"]:
        raise ValueError("Evaluated patch does not match the candidate patch")
    if evidence.get("verdict_source") == "patch_apply_failed":
        # No report.json is written when the patch does not apply; the generation
        # runner treats this as an ordinary failure, so verify the log and return False.
        if report.is_file():
            raise ValueError("Patch-apply-failed verdict but a report.json exists")
        if not patch_apply_failed(evidence):
            raise ValueError("Patch-apply-failed verdict is not backed by run_instance.log")
        return False
    if not report.is_file():
        raise ValueError("Missing internal report.json")
    data = read(report).get(item["task"], {})
    if type(data.get("resolved")) is not bool:
        raise ValueError("Internal report has no boolean resolved result")
    return data["resolved"]


def run(args):
    items = candidates(args.candidates)
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT / "ICLR_results"):
        raise ValueError("Use an output directory outside ICLR_results")
    manifest_path = output / "manifest.json"
    if output.exists():
        if not args.resume or not manifest_path.is_file():
            raise ValueError("Output already exists. Use a fresh directory or --resume with its manifest")
        manifest = read(manifest_path)
        old = [(r["result_file"], r["key"], r["generation_sha256"]) for r in manifest["items"]]
        new = [(r["result_file"], r["key"], r["generation_sha256"]) for r in items]
        if old != new:
            raise ValueError("Candidate generation records changed since the saved manifest")
        if manifest.get("model_tag", "devstral-2") != args.model_tag:
            raise ValueError(f"--model-tag differs from the saved manifest ({manifest.get('model_tag', 'devstral-2')})")
    else:
        manifest = {"schema": 1, "created": dt.datetime.now().isoformat(),
                    "candidates": str(args.candidates.resolve()), "model_tag": args.model_tag,
                    "items": items}
    # The Docker-compatible SDK is imported only for an explicitly requested run.
    env = os.environ.copy()
    env.setdefault("DOCKER_HOST", f"unix:///run/user/{os.getuid()}/podman/podman.sock")
    env["SWEBENCH_EVAL_THREADS"] = str(args.eval_threads)
    # Do not resolve(): venv/bin/python is a symlink and following it to the
    # system interpreter bypasses the virtualenv (no swebench module).
    python = str(Path(os.path.abspath(args.python)))
    check = [python, "-c",
             "import docker; c=docker.from_env(); assert c.ping(); print('Container service reachable')"]
    subprocess.run(check, env=env, check=True)
    save(manifest_path, manifest)
    result_path = output / "results.json"
    results = read(result_path) if result_path.exists() else {}
    display(items)
    unverified = []
    for index, item in enumerate(items):
        slot = str(index)
        if slot in results and results[slot].get("status") == "verified":
            checked_report(item, results[slot])
            print(f"[{index+1}/{len(items)}] verified already: {item['key']}", flush=True)
            continue
        attempt = output / "jobs" / f"{index:04d}" / uuid.uuid4().hex
        attempt.mkdir(parents=True)
        run_id = "reeval-" + uuid.uuid4().hex
        tag = args.model_tag   # harness log directory name; must match the model's eval tree
        prediction = attempt / "predictions.json"
        save(prediction, {item["task"]: {"instance_id": item["task"],
             "model_name_or_path": tag, "model_patch": item["submission"]}})
        # The wrapper caps OpenMP/BLAS threads inside the container (see its docstring).
        command = [python, str(ROOT / "scripts/swebench_eval_wrapper.py"),
                   "--predictions_path", str(prediction), "--instance_ids", item["task"],
                   "--run_id", run_id, "--report_dir", str(attempt),
                   "--dataset_name", "princeton-nlp/SWE-bench_Verified", "--split", "test",
                   "--max_workers", "1", "--timeout", str(args.test_timeout),
                   "--cache_level", "instance", "--clean", "False"]
        directory = attempt / "logs/run_evaluation" / run_id / tag / item["task"]
        evidence = {"status": "error", "command": command, "cwd": str(attempt),
                    "report": str(directory / "report.json"), "patch": str(directory / "patch.diff"),
                    "instance_log": str(directory / "run_instance.log"),
                    "started": dt.datetime.now().isoformat()}
        print(f"[{index+1}/{len(items)}] evaluating {item['cell']} / {item['key']}", flush=True)
        results[slot] = evidence
        save(result_path, results)
        with (attempt / "harness.log").open("w") as log:
            proc = subprocess.run(command, cwd=attempt, env=env, stdout=log, stderr=subprocess.STDOUT)
        evidence["returncode"] = proc.returncode
        try:
            if proc.returncode:
                raise ValueError(f"Harness exited with code {proc.returncode}")
            if not Path(evidence["report"]).is_file() and patch_apply_failed(evidence):
                evidence["verdict_source"] = "patch_apply_failed"
            else:
                evidence["verdict_source"] = "report"
            evidence["resolved"] = checked_report(item, evidence)
            evidence["status"] = "verified"
        except (ValueError, OSError, KeyError) as exc:
            evidence["error"] = str(exc)
        evidence["finished"] = dt.datetime.now().isoformat()
        save(result_path, results)
        if evidence["status"] == "verified":
            note = " (patch apply failed)" if evidence["verdict_source"] == "patch_apply_failed" else ""
            print(f"    -> resolved={evidence['resolved']}{note}", flush=True)
            continue
        unverified.append(item["key"])
        print(f"    !! unverified: {evidence['error']}. Inspect {attempt / 'harness.log'}", flush=True)
        if not args.continue_on_error:
            print("Stopped on unverified evaluation. Fix the cause and rerun with --resume, "
                  "or use --continue-on-error to record and skip.", flush=True)
            return 1
    print(f"Evaluation evidence saved: {output}\nCanonical results were not updated.")
    if unverified:
        print(f"Unverified candidates: {len(unverified)} (rerun with --resume after fixing the cause)")
        for key in unverified:
            print(f"  {key}")
        return 1
    return 0


def apply(args):
    output = args.output_dir.resolve()
    manifest = read(output / "manifest.json")
    results = read(output / "results.json")
    updates = {}
    hashes = {}
    pending = []
    changes = []
    for index, item in enumerate(manifest["items"]):
        evidence = results.get(str(index), {})
        if evidence.get("status") != "verified":
            pending.append(item["key"])
            continue
        value = checked_report(item, evidence)
        if value != evidence.get("resolved"):
            raise ValueError("Saved result differs from its internal evaluation report")
        src = source_path(item["result_file"])
        if src not in updates:
            raw = src.read_bytes()
            hashes[src] = sha(raw)
            updates[src] = json.loads(raw)
        matches = [r for r in updates[src] if r["key"] == item["key"]]
        if len(matches) != 1 or identity(matches[0]) != item["generation_sha256"]:
            raise ValueError(f"Generation changed after planning: {item['key']}")
        row = matches[0]
        changes.append({"cell": item["cell"], "key": item["key"],
                        "before": row.get("resolved"), "after": value})
        row["resolved"] = value
        row["reevaluation"] = {"report_path": evidence["report"],
                               "verdict_source": evidence.get("verdict_source", "report"),
                               "patch_sha256": item["patch_sha256"],
                               "evaluated_at": evidence["finished"]}
    print(f"Verified evaluations: {len(changes)}; pending/errors: {len(pending)}")
    print(f"Resolved values changing: {sum(r['before'] != r['after'] for r in changes)}")
    for cell in sorted({r['cell'] for r in changes}):
        group = [r for r in changes if r['cell'] == cell]
        print(f"  {cell}: {len(group)} verified; "
              f"{sum(r['before'] is True for r in group)} -> {sum(r['after'] for r in group)} resolved")
    if not args.write:
        print("Preview only. Add --write to back up and update canonical indexes.")
        return 0
    if pending and not args.allow_partial:
        raise ValueError("Unverified candidates remain; no indexes changed. Finish them, or explicitly use --allow-partial")
    if not changes:
        raise ValueError("No verified results to apply")
    backup = output / "backups" / uuid.uuid4().hex
    # Validate every source before making any index changes.
    for src, expected in hashes.items():
        if sha(src.read_bytes()) != expected:
            raise ValueError(f"Index changed concurrently: {src}")
    for src in updates:
        dest = backup / src.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    save(backup / "changes.json", changes)
    for src, rows in updates.items():
        if sha(src.read_bytes()) != hashes[src]:
            raise ValueError(f"Index changed during apply; stop and inspect backups: {backup}")
        save(src, rows)
    print(f"Updated {len(changes)} result rows. Backup and change list: {backup}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
        if name == "run":
            sub.add_argument("--output-dir", type=Path, required=True)
            sub.add_argument("--python", type=Path, default=ROOT / "venv/bin/python")
            sub.add_argument("--test-timeout", type=int, default=1800)
            sub.add_argument("--eval-threads", type=int, default=8,
                             help="OMP/BLAS thread cap inside evaluation containers (default 8)")
            sub.add_argument("--model-tag", default="devstral-2",
                             help="model_name_or_path used by the harness (devstral-2, qwen35-a3b, glm47-flash)")
            sub.add_argument("--resume", action="store_true")
            sub.add_argument("--continue-on-error", action="store_true",
                             help="Record unverified rows and keep going instead of stopping")
    sub = commands.add_parser("apply")
    sub.add_argument("--output-dir", type=Path, required=True)
    sub.add_argument("--write", action="store_true")
    sub.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        display(candidates(args.candidates))
        print("Read-only plan. No evaluations or writes performed.")
        return 0
    if args.command == "run" and args.test_timeout <= 0:
        raise ValueError("--test-timeout must be positive")
    if args.command == "run" and args.eval_threads <= 0:
        raise ValueError("--eval-threads must be positive")
    output = args.output_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / ("." + output.name + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another reevaluation command is using this output directory") from None
        return run(args) if args.command == "run" else apply(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
