#!/usr/bin/env python3
"""Continue a finished full-context run from call K under another context regime.

Question (2026-11-04): would an FC run that failed have gone differently if the
online selector (OCSA) had shaped its context around the turning point? The
earlier one-reply replays (replay_decision.py) showed that swapping the context
for a single call changes nothing; this script lets the agent run ON from the
turning point and grades the result.

For one source run (a finished `full-context` run with events.jsonl) and a
start call K:
  1. a fresh task container is started and the commands of calls 1..K-1 are
     re-executed in order (the source run was greedy, so the state should be
     reproducible; every command's output is compared with the recorded
     observation and logged to replay_log.json);
  2. the agent is seeded with the source history before call K and runs on
     from call K with the same model / config as the campaign
     (configs/config-devstral-vllm-temp0.yaml, temperature 0), to Submitted or
     the step limit;
  3. the patch is graded with the SWE-bench harness (same adapter as the
     campaign), the verdict goes to <run_dir>/continuation.json and to
     <out>/continuation_results.json.

Modes (`--mode`):
  fc       full context throughout (the control: the same start, no selector)
  window   calls a..b (`--window a-b`, default K..K+2*(T-K) around the turning
           point T) go through online_claude_select exactly as in the OCSA cell
           (anchored, cap 30000, keep-recent 3, DeepSeek V4.1 Flash via
           OpenRouter); the selector's first anchor is the selection an OCSA
           agent would have had at call K-1 (`--selections`, simulated by
           replay_decision.py `select` on the same history). After call b the
           selector is not called again: the context is the last selection
           plus everything the agent adds from then on (append only; nothing
           hidden comes back).

Sub-commands:
  plan    write <out>/plan.json for the 6 failed FC runs of the turning-point
          analysis (sklearn-13135 r1/r2, sympy-15875 r1/r3, sympy-12419 r2/r3)
  run     one continuation (arguments below), then grade it
  batch   every (plan entry x mode x rep) not yet recorded, sequentially; the
          vLLM prefix cache is reset before every run (server started with
          VLLM_SERVER_DEV_MODE=1), as in the campaign's isolated driver

Needs: the Devstral vLLM server on :8002, the rootless podman socket
(DOCKER_HOST, default unix:///run/user/<uid>/podman/podman.sock; the
`docker` CLI talks to it), OPENROUTER_API_KEY or
~/.config/agentctx/openrouter_api_key for `window`.

Usage:
    venv/bin/python scripts/maintenance/continue_run.py plan
    venv/bin/python scripts/maintenance/continue_run.py run --source <fc run dir> --start K --mode window \
        --window a-b --selections <selections json> --out-dir <run dir> [--step-limit N] [--no-eval]
    venv/bin/python scripts/maintenance/continue_run.py batch [--reps 3] [--modes fc,window]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src", ROOT / "mini-swe-agent" / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from scripts.maintenance.reconstruct_context import Replay  # noqa: E402

DEFAULT_OUT = ROOT / "data/r2/probes/continue_fc_turning"
FC_CELL = ROOT / "data/r2/swebench/p30s/devstral24b-iso-fc20/di__binf__fc"
AGENT_CONFIG = ROOT / "configs/config-devstral-vllm-temp0.yaml"
BENCH_CONFIG = ROOT / "mini-swe-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml"
MODEL_TAG = "devstral-2"          # the campaign's run tag (eval dirs are named by it)
STEP_LIMIT = 300
AGENT_API_BASE = "http://localhost:8002/v1"
INFINITE_BUDGET = "999999999"

# The OCSA cell's selector (experiment_results.json `extract_model`, conditions.py,
# run_r2_swe_sandbox_isolated_devstral24b_fc20.sh); same values as replay_decision.py.
SELECTOR_ENV = {
    "MSWEA_EXTRACT_PROVIDER": "openrouter",
    "MSWEA_EXTRACT_MODEL": "deepseek/deepseek-v4.1-flash-1017",
    "MSWEA_EXTRACT_EFFORT": "low",
    "MSWEA_EXTRACT_MAX_TOKENS": "12000",
    "MSWEA_EXTRACT_PREFILL": "0",
    "MSWEA_SELECT_ANCHOR": "1",
    "MSWEA_SELECT_CAP": "30000",
    "MSWEA_EXTRACT_KEEP_RECENT": "3",
}

# Turning points of the failed FC runs (call numbers = model calls, as in
# token_log.json; the per-run reading is in the 2026-11-04 session notes):
# 13135 / 15875: the call whose reply commits to the wrong fix (sort the bin
# edges; return True); 12419: the call that confirms the fix on the issue
# example, after which the OCSA runs ran the matrix tests and FC r2/r3 did not.
PROBES = ROOT / "data/r2/probes"
TURNING_POINTS = [
    # task, run, turning call, selections json (simulated OCSA contexts of this history)
    ("scikit-learn__scikit-learn-13135", 1, 20,
     PROBES / "replay_decision_devstral24b_fc25/selections/scikit-learn__scikit-learn-13135__FC__r1.json"),
    ("scikit-learn__scikit-learn-13135", 2, 19,
     PROBES / "replay_decision_devstral24b_fc25/selections/scikit-learn__scikit-learn-13135__FC__r2.json"),
    ("sympy__sympy-15875", 1, 29,
     PROBES / "replay_decision_devstral24b_fc25_turning/selections/sympy__sympy-15875__FC__r1.json"),
    ("sympy__sympy-15875", 3, 22,
     PROBES / "replay_decision_devstral24b_fc25_turning/selections/sympy__sympy-15875__FC__r3.json"),
    ("sympy__sympy-12419", 2, 110,
     PROBES / "replay_decision_devstral24b_fc25_turning/selections/sympy__sympy-12419__FC__r2.json"),
    ("sympy__sympy-12419", 3, 114,
     PROBES / "replay_decision_devstral24b_fc25_turning/selections/sympy__sympy-12419__FC__r3.json"),
]
HALF_WINDOW = 10


def docker_host() -> str:
    return os.environ.get("DOCKER_HOST") or f"unix:///run/user/{os.getuid()}/podman/podman.sock"


# ── plan ────────────────────────────────────────────────────────────────────
def cmd_plan(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for task, run, turning, sel in TURNING_POINTS:
        source = FC_CELL / task / "full-context" / f"run_{run}"
        start = turning - HALF_WINDOW
        if not json.loads(sel.read_text()).get(str(start - 1)):
            raise SystemExit(f"{sel}: no simulated context for call {start - 1}")
        entries.append({"task": task, "source_run": run, "source_run_dir": str(source.relative_to(ROOT)),
                        "turning_call": turning, "start": start, "window": [start, turning + HALF_WINDOW],
                        "selections": str(sel.relative_to(ROOT))})
    (out / "plan.json").write_text(json.dumps({"half_window": HALF_WINDOW, "entries": entries}, indent=1))
    for e in entries:
        print(f"{e['task']:34} FC r{e['source_run']}  turning {e['turning_call']:4}  start {e['start']:4}  "
              f"window {e['window'][0]}-{e['window'][1]}")
    print(f"wrote {out / 'plan.json'}")
    return 0


# ── one continuation ────────────────────────────────────────────────────────
def seed_records(rp: Replay, start: int) -> list[dict]:
    """Event records (as written) of every message the source agent added before call `start`."""
    return [rec for kind, rec in rp.ops if kind == "add" and rec["step"] < start]


def replay_commands(env, records: list[dict], log) -> list[dict]:
    """Re-execute the commands of the seeded assistant turns in `env`, in order."""
    results = []
    msgs = [r["message"] for r in records]
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        actions = (m.get("extra") or {}).get("actions") or []
        obs = msgs[i + 1] if i + 1 < len(msgs) and msgs[i + 1].get("role") == "user" else None
        rec_out = (obs.get("extra") or {}).get("raw_output") if obs else None
        rec_rc = (obs.get("extra") or {}).get("returncode") if obs else None
        for action in actions:
            t0 = time.time()
            try:
                out = env.execute(action)
            except Exception as exc:   # noqa: BLE001 - Submitted cannot occur before the start call
                out = {"output": f"<replay exception {type(exc).__name__}: {exc}>", "returncode": -1}
            got = out.get("output", "")
            rc = out.get("returncode")
            exact = rec_out is not None and got == rec_out
            same_rc = rec_rc is not None and str(rc) == str(rec_rc)
            results.append({"step": records[i]["step"], "uid": records[i]["uid"], "command": action.get("command"),
                            "returncode": rc, "recorded_returncode": rec_rc, "returncode_match": same_rc,
                            "output_match": exact, "output_chars": len(got),
                            "recorded_chars": len(rec_out) if rec_out is not None else None,
                            "seconds": round(time.time() - t0, 2),
                            **({} if exact else {"output_head": got[:400],
                                                  "recorded_head": (rec_out or "")[:400]})})
            log(f"  replay call {records[i]['step']:4} rc {rc!s:>3} {'=' if exact else '≠'} "
                f"{(action.get('command') or '')[:70]!r}")
    return results


def build_agent(args, out_dir: Path, mode: str, seed: list[dict], context: list[dict], start: int,
                window: tuple[int, int] | None, key: str):
    """Model, environment and the seeded agent, configured as the campaign's runs."""
    from minisweagent.config import get_config_from_spec
    from minisweagent.utils.serialize import recursive_merge
    from minisweagent.models import get_model
    from minisweagent.run.benchmarks.swebench import get_sb_environment
    from minisweagent.agents.interactive import InteractiveAgent
    from minisweagent.exceptions import InterruptAgentFlow

    os.environ.update({
        "MSWEA_COST_TRACKING": "ignore_errors",
        "MSWEA_PRIMITIVE": "online_claude_select" if mode == "window" else "truncation",  # as conditions.py
        "MSWEA_TOKEN_BUDGET": INFINITE_BUDGET,
        "MSWEA_COMPRESSION_RATIO": "0.5",
        "MSWEA_TOKEN_LOG_PATH": str(out_dir / "token_log.json"),
        "MSWEA_RUN_KEY": key,
        "MSWEA_EVENT_LOG_DIR": str(out_dir),
        "DOCKER_HOST": docker_host(),
    })
    if mode == "window":
        os.environ.update(SELECTOR_ENV)             # forced: nothing from the shell leaks in
        os.environ.pop("MSWEA_EXTRACT_TEMPERATURE", None)   # provider default 0, as in the campaign
    config = recursive_merge(
        get_config_from_spec(str(BENCH_CONFIG)),
        get_config_from_spec(str(args.agent_config)),
        {"agent": {"step_limit": args.step_limit, "mode": "yolo", "confirm_exit": False,
                   "output_path": str(out_dir / "trajectory.json")}},
    )
    if args.api_base:
        config["model"].setdefault("model_kwargs", {})["api_base"] = args.api_base
    env = get_sb_environment(config, {"instance_id": args.task})
    model = get_model(config=config.get("model", {}))
    agent_cfg = dict(config.get("agent", {}))
    agent_cfg.pop("agent_class", None)

    class ContinuedAgent(InteractiveAgent):
        """InteractiveAgent (the campaign's class, yolo mode) seeded with a history."""

        def _online_claude(self, kind: str):
            # The hook runs before n_calls is incremented: the call about to be made is n_calls + 1.
            if window is not None and not (window[0] <= self.n_calls + 1 <= window[1]):
                return None
            return super()._online_claude(kind)

        def run(self, task: str = "", **kwargs) -> dict:
            self.extra_template_vars |= {"task": task, **kwargs}
            full = [r["message"] for r in seed]
            self._full_messages = list(full)
            self.messages = list(context)
            self.n_calls = start - 1
            self._evt_seq = max(r["seq"] for r in seed)
            for r in seed:
                self._evt_append("events.jsonl", {**r, "origin": "seeded"})
            if [m["extra"]["uid"] for m in self.messages] != [m["extra"]["uid"] for m in full] or any(
                    a["content"] != b["content"] for a, b in zip(self.messages, full)):
                # The seeded context is not the full history: record it as a compression event
                # so reconstruct_context.py can replay this run from its own logs.
                before = self._evt_snapshot(full)
                self._evt_record_compression("seed_selection", before, source=str(args.source),
                                             start_call=start, mode=mode)
            self.save(self.config.output_path)
            while True:
                try:
                    self.step()
                except InterruptAgentFlow as e:
                    self.add_messages(*e.messages)
                except Exception as e:
                    self.handle_uncaught_exception(e)
                    raise
                finally:
                    try:
                        self.save(self.config.output_path)
                    finally:
                        self._write_token_log()
                if self.messages[-1].get("role") == "exit":
                    break
            return self.messages[-1].get("extra", {})

    agent = ContinuedAgent(model, env, **agent_cfg)
    return agent, env, config


def seeded_context(mode: str, seed: list[dict], selections: Path | None, start: int) -> list[dict]:
    """The agent's context before the hook of call `start`.

    fc: the full seeded history. window: the OCSA context of call start-1 (simulated
    selection, newest messages verbatim) plus the messages added at step start-1,
    i.e. exactly what an OCSA agent holds when its hook runs before call `start`."""
    full = [r["message"] for r in seed]
    if mode == "fc":
        return list(full)
    ctx = json.loads(selections.read_text()).get(str(start - 1))
    if not ctx:
        raise SystemExit(f"{selections}: no simulated context for call {start - 1}")
    by_uid = {r["message"]["extra"]["uid"]: r["message"] for r in seed}
    unknown = [m["extra"]["uid"] for m in ctx if m["extra"]["uid"] not in by_uid]
    if unknown:
        raise SystemExit(f"{selections}: context of call {start - 1} holds uids not in the history: {unknown}")
    # Partial keeps carry their own (cut) content; whole keeps use the history's message object.
    out = [by_uid[m["extra"]["uid"]] if m["content"] == by_uid[m["extra"]["uid"]]["content"] else m for m in ctx]
    out += [r["message"] for r in seed if r["step"] == start - 1 and r["message"]["extra"]["uid"] not in
            {m["extra"]["uid"] for m in out}]
    return out


def evaluate(out: Path, task: str, key: str, submission: str) -> bool | None:
    from agentctx.benchmarks.swe_bench import SweBench
    bench = SweBench(ROOT, MODEL_TAG, out)
    return bench._evaluate_run({"instance_id": task, "key": key, "submission": submission})


def cmd_run(args) -> int:
    source = ROOT / args.source if not Path(args.source).is_absolute() else Path(args.source)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "continuation.json").exists() and not args.force:
        print(f"{out_dir}: continuation.json exists (use --force to redo)")
        return 0
    for name in ("events.jsonl", "compression_events.jsonl", "summary_attempts.jsonl", "token_log.json",
                 "trajectory.json", "replay_log.json"):
        (out_dir / name).unlink(missing_ok=True)
    args.task = args.task or source.parents[1].name
    key = args.key or f"{args.task}__cont-{args.mode}-k{args.start}__r{args.rep}"
    window = None
    if args.mode == "window":
        a, b = (int(x) for x in args.window.split("-"))
        window = (a, b)
        if not args.selections:
            raise SystemExit("--mode window needs --selections")
    rp = Replay(source)
    seed = seed_records(rp, args.start)
    if not seed or seed[-1]["step"] != args.start - 1:
        raise SystemExit(f"{source}: no messages for call {args.start - 1}; last seeded step "
                         f"{seed[-1]['step'] if seed else None}")
    context = seeded_context(args.mode, seed, ROOT / args.selections if args.selections else None, args.start)
    log_f = (out_dir / "continue.log").open("a")

    def log(s: str) -> None:
        print(s, flush=True)
        log_f.write(s + "\n")
        log_f.flush()

    log(f"== {key}: source {source.relative_to(ROOT)}, start call {args.start}, mode {args.mode}"
        f"{'' if window is None else f', selector window {window[0]}-{window[1]}'}; "
        f"seeded {len(seed)} messages, context {len(context)} messages")
    meta = {"key": key, "task": args.task, "source_run_dir": str(source.relative_to(ROOT)), "start_call": args.start,
            "mode": args.mode, "window": window, "selections": args.selections, "rep": args.rep,
            "selector_env": SELECTOR_ENV if args.mode == "window" else None,
            "agent_config": str(Path(args.agent_config).relative_to(ROOT)), "step_limit": args.step_limit,
            "seeded_messages": len(seed), "seeded_context_messages": len(context),
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    t0 = time.time()
    agent, env, config = build_agent(args, out_dir, args.mode, seed, context, args.start, window, key)
    try:
        log(f"container {env.container_id[:12]} ({config['environment']['image']}); replaying "
            f"{sum(1 for r in seed if r['message'].get('role') == 'assistant')} commands")
        replay = replay_commands(env, seed, log)
        (out_dir / "replay_log.json").write_text(json.dumps(replay, indent=1))
        n_exact = sum(r["output_match"] for r in replay)
        n_rc = sum(r["returncode_match"] for r in replay)
        meta["replay"] = {"commands": len(replay), "output_match": n_exact, "returncode_match": n_rc,
                          "seconds": round(time.time() - t0, 1)}
        log(f"replay: {n_exact}/{len(replay)} outputs identical, {n_rc}/{len(replay)} return codes identical")
        task_text = seed[1]["message"]["content"] if len(seed) > 1 else ""
        log(f"agent: running on from call {args.start} (step limit {args.step_limit})")
        t1 = time.time()
        try:
            result = agent.run(task_text)
        except Exception as exc:   # noqa: BLE001 - e.g. a context overflow (BadRequestError), as in the campaign
            # The agent already added the exit message (handle_uncaught_exception) and saved the
            # trajectory; the run counts as a failure without a patch, like the campaign's rows.
            last = agent.messages[-1] if agent.messages else {}
            result = dict(last.get("extra", {})) if last.get("role") == "exit" else {}
            result.setdefault("exit_status", type(exc).__name__)
            result.setdefault("submission", "")
            meta["agent_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            log(f"agent raised {type(exc).__name__}; recorded as a failed run")
        finally:
            meta["agent_seconds"] = round(time.time() - t1, 1)
    finally:
        try:
            subprocess.run([config["environment"].get("executable", "docker"), "rm", "-f", env.container_id],
                           capture_output=True, timeout=120)
        except Exception as exc:   # noqa: BLE001
            log(f"container removal failed: {exc}")
    meta.update({"exit_status": result.get("exit_status"), "n_calls": agent.n_calls,
                 "calls_this_run": agent.n_calls - (args.start - 1),
                 "submission": result.get("submission", ""), "resolved": None})
    log(f"agent finished: {meta['exit_status']} after {meta['calls_this_run']} calls "
        f"(total {agent.n_calls}), {meta['agent_seconds']} s")
    (out_dir / "continuation.json").write_text(json.dumps(meta, indent=1))
    if args.eval and meta["submission"].strip():
        log("evaluating with the SWE-bench harness ...")
        meta["resolved"] = evaluate(Path(args.out), args.task, key, meta["submission"])
        log(f"resolved: {meta['resolved']}")
    elif args.eval:
        meta["resolved"] = False
        log("no submission: resolved = False")
    meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "continuation.json").write_text(json.dumps(meta, indent=1))
    results_f = Path(args.out) / "continuation_results.json"
    rows = json.loads(results_f.read_text()) if results_f.exists() else []
    rows = [r for r in rows if r["key"] != key] + [{k: v for k, v in meta.items() if k != "selector_env"}]
    results_f.write_text(json.dumps(rows, indent=1))
    return 0


# ── batch ───────────────────────────────────────────────────────────────────
def reset_prefix_cache(api_base: str, log) -> None:
    import requests
    root = api_base.rstrip("/").removesuffix("/v1")
    r = requests.post(f"{root}/reset_prefix_cache", timeout=60)
    if r.status_code == 404:
        raise SystemExit("POST /reset_prefix_cache -> 404: start the server with VLLM_SERVER_DEV_MODE=1")
    r.raise_for_status()
    log("prefix cache reset")


def cmd_batch(args) -> int:
    import requests
    out = Path(args.out)
    plan = json.loads((out / "plan.json").read_text())
    modes = args.modes.split(",")
    try:
        requests.get(f"{args.api_base}/models", timeout=10).raise_for_status()
    except Exception as exc:   # noqa: BLE001
        raise SystemExit(f"agent server not reachable at {args.api_base}: {exc}")
    jobs = []
    for rep in range(1, args.reps + 1):          # rep-major: rep 1 of everything first
        for e in plan["entries"]:
            for mode in modes:
                run_dir = out / e["task"] / f"cont-{mode}-k{e['start']}" / f"run_{rep}"
                done = (run_dir / "continuation.json").exists() and \
                    json.loads((run_dir / "continuation.json").read_text()).get("resolved") is not None
                if not done:
                    jobs.append((e, mode, rep, run_dir))
    print(f"{len(jobs)} continuation runs to do ({len(plan['entries'])} start points x {modes} x {args.reps} reps)")
    for i, (e, mode, rep, run_dir) in enumerate(jobs, 1):
        print(f"\n[{i}/{len(jobs)}] {e['task']} FC r{e['source_run']} start {e['start']} mode {mode} rep {rep}", flush=True)
        reset_prefix_cache(args.api_base, print)
        cmd = [sys.executable, __file__, "run", "--source", e["source_run_dir"], "--start", str(e["start"]),
               "--mode", mode, "--window", f"{e['window'][0]}-{e['window'][1]}", "--selections", e["selections"],
               "--out", str(out), "--out-dir", str(run_dir), "--rep", str(rep), "--api-base", args.api_base,
               "--step-limit", str(args.step_limit), "--task", e["task"]]
        if args.dry_run:
            print("  " + " ".join(cmd))
            continue
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"  run exited with {rc}; stopping")
            return rc
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "run", "batch"])
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="probe dir (plan.json, eval/, continuation_results.json)")
    ap.add_argument("--source", help="run: the source FC run dir (relative to the repo root or absolute)")
    ap.add_argument("--task", help="run: instance id (default: from the source path)")
    ap.add_argument("--start", type=int, help="run: first call made by the continued agent (K)")
    ap.add_argument("--mode", choices=["fc", "window"], default="window")
    ap.add_argument("--window", help="run: selector window a-b in call numbers (mode window)")
    ap.add_argument("--selections", help="run: simulated OCSA contexts of the source history (mode window)")
    ap.add_argument("--out-dir", help="run: the continuation's run dir")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--key", help="run: result key (default <task>__cont-<mode>-k<start>__r<rep>)")
    ap.add_argument("--step-limit", type=int, default=STEP_LIMIT, help="agent.step_limit (total calls, source included)")
    ap.add_argument("--agent-config", default=str(AGENT_CONFIG))
    ap.add_argument("--api-base", default=AGENT_API_BASE)
    ap.add_argument("--eval", action=argparse.BooleanOptionalAction, default=True, help="run: grade the patch")
    ap.add_argument("--force", action="store_true", help="run: redo a run dir that has a continuation.json")
    ap.add_argument("--reps", type=int, default=3, help="batch: continuations per (start point, mode)")
    ap.add_argument("--modes", default="fc,window", help="batch: modes to run")
    ap.add_argument("--dry-run", action="store_true", help="batch: print the commands only")
    args = ap.parse_args()
    if args.command == "run":
        for req in ("source", "start", "out_dir"):
            if getattr(args, req) is None:
                ap.error(f"run needs --{req.replace('_', '-')}")
    return {"plan": cmd_plan, "run": cmd_run, "batch": cmd_batch}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
