#!/usr/bin/env python
"""Offline "is the agent going the wrong way?" judge over finished runs.

Replays each run's complete history (events.jsonl, never compressed) and, every
--interval agent steps, asks a judge model whether the agent is still on a track
that can end in a correct fix. Nothing is fed back to the agent: this measures
only whether a periodic check could tell failing runs apart early (and where it
places the onset), before any intervention experiment is worth running.

Modes:
    nogold  problem statement + history only (the realistic judge)
    gold    + the reference patch (upper bound: the judge knows one correct fix)

Views (what history the judge is shown at checkpoint k):
    full     every message up to step k, as added (before any compression or
             selection); identical for every condition at a given step
    context  what the agent itself works from after step k: the context of call
             k+1, replayed with scripts/maintenance/reconstruct_context.py (after
             SU's summaries / the online selector's keep-drop). Same as `full`
             for full-context; for ODE it asks whether the selected context still
             lets a judge see the run going wrong

The judge is called through the same OpenRouter client as the online selector
(agentctx.compression.claude_extract), default deepseek/deepseek-v4.1-flash-1017
at effort low, temperature 0. The prompt is ordered system / problem / [gold] /
history / question, so consecutive checkpoints of one run share a growing prefix
(provider-side prefix cache); checkpoints of a run are therefore judged in order.
The `context` view of a compressed run does not grow monotonically, so it caches less.

Usage:
    venv/bin/python scripts/maintenance/onset_judge.py judge CELL_DIR... --out DIR \
        [--modes nogold,gold] [--view full|context|both] [--interval 10] [--tasks a,b]
        [--max-runs N] [--workers 4] [--dry-run]
    venv/bin/python scripts/maintenance/onset_judge.py report --out DIR [--labels labels.json] [--threshold 0.5]

CELL_DIR is a cell dir holding experiment_results.json (e.g.
data/r2/swebench/p30s/devstral24b-iso-fc20/di__binf__fc, or the ODE cell
data/r2/swebench/p30s/devstral24b-iso-fc20-dsflash/di__binf__ocsa); several cells
may be given at once. Results go to <out>/judge_<mode>.jsonl (view full) and
<out>/judge_<mode>_ctx.jsonl (view context), one record per (run, checkpoint),
tagged with the run's condition; an interrupted judge
resumes, skipping records already written. --dry-run builds every prompt and
prints call / token counts (chars/4) without calling the API.

`report` prints, per output file and condition: AUROC of p_fail vs. final failure at each checkpoint
(all runs, and within tasks whose runs disagree), the first alarm step per run,
the false-alarm rate on resolved runs, and, with --labels, alarm vs. the hand
labelled onset / anchor steps ({"<task>__<cond>__r<n>": {"onset": s, "anchor": s}}).
Baseline: "not yet submitted by step k" alone (failed runs are longer).
"""
import argparse
import glob
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash-1017"
ARROW_GLOB = str(Path("~/.cache/huggingface/datasets/princeton-nlp___swe-bench_verified/"
                      "default/0.0.0/*/swe-bench_verified-test.arrow").expanduser())

# v1 (2026-11-01) judged committed work ("exploration that has not yet committed to
# anything is on track") and alarmed only after the wrong edit; its records are kept
# as v1_judge_*.jsonl. v2 judges the agent's understanding and adds `feedback`.
PROMPT_VERSION = 2

SYSTEM = """You are reviewing the work of an autonomous coding agent that is fixing an issue in a code repository. The agent works in a shell, one command per step; you see its reasoning, commands and outputs so far.

Your job: judge whether the agent's current understanding is correct, namely
- what the correct behaviour is (what result the fixed code should produce),
- where the bug is, and
- what kind of change is needed.
Judge the beliefs and plans visible in its reasoning, its reproduction scripts and its tests, not only its source edits. The agent is off track as soon as it holds and acts on a wrong belief, even before it edits any source file: for example a reproduction script or test that expects a wrong output, a stated plan to change the wrong behaviour or the wrong place, a misreading of the issue, or a conclusion that contradicts evidence in its own outputs. It is also off track if it has broken unrelated behaviour. It is on track while it is still exploring without having adopted a wrong belief, or while its stated understanding is correct, however slow or inefficient its work is. Judge direction, not style or efficiency.

Your reply has two text fields with different readers:
- `reason` is for researchers only and is never shown to the agent; state your diagnosis freely.
- `feedback` may later be shown to the agent. It may only point out what in the agent's current understanding looks questionable and what it should re-check, using only things already in its history or the issue. It must NOT state or hint at the correct fix, the correct expected output, the file, function or line to change, or any code, and must not reveal anything from a reference fix. Leave it empty ("") when the agent is on track."""

GOLD_NOTE = """A reference fix for this issue is shown below. Other correct fixes may exist; use it to understand what the correct behaviour and the right place to change are, not as the only acceptable diff."""

QUESTION = """The history above ends at step {k}. Reply with one JSON object and nothing else:
{{"verdict": "on_track" | "off_track", "p_fail": <probability 0-1 that this run ends without a correct fix>, "onset_step": <first step where the agent adopted the wrong belief, or null if on track>, "reason": "<one or two sentences, for researchers>", "feedback": "<for the agent, no answer; empty if on track>"}}"""

CORRECTION = """That reply could not be used. Reply again with exactly one JSON object holding all five fields (verdict, p_fail as a number, onset_step, reason, feedback) and nothing else."""

RETRY_TEMPERATURE = 0.7

_lock = threading.Lock()
_retry_models = {}


def _retry_model(model):
    """The judge at RETRY_TEMPERATURE, sharing the API client."""
    from agentctx.compression.claude_extract import ClaudeExtractModel
    with _lock:
        if id(model) not in _retry_models:
            _retry_models[id(model)] = ClaudeExtractModel(
                {**model.settings, "temperature": RETRY_TEMPERATURE}, client=model.client())
        return _retry_models[id(model)]


# ── data ────────────────────────────────────────────────────────────────────
def _gold_patches() -> dict:
    import pyarrow as pa
    path = glob.glob(ARROW_GLOB)[0]
    with pa.memory_map(path) as src:
        try:
            table = pa.ipc.open_stream(src).read_all()
        except pa.ArrowInvalid:
            table = pa.ipc.open_file(src).read_all()
    return dict(zip(table.column("instance_id").to_pylist(), table.column("patch").to_pylist()))


def _cond_dir(cell: Path, task: str) -> Path | None:
    subs = [p for p in (cell / task).iterdir() if p.is_dir()] if (cell / task).is_dir() else []
    return subs[0] if len(subs) == 1 else None


def discover(cells: list[str], tasks: set[str] | None) -> list[dict]:
    runs = []
    for cell in map(Path, cells):
        for row in json.loads((cell / "experiment_results.json").read_text()):
            task = row.get("instance_id") or row.get("task")
            if tasks and task not in tasks:
                continue
            cdir = _cond_dir(cell, task)
            run_dir = cdir / f"run_{row['run_num']}" if cdir else None
            if not run_dir or not (run_dir / "events.jsonl").exists():
                print(f"skip {task} {row.get('condition')} r{row['run_num']}: no events.jsonl", file=sys.stderr)
                continue
            runs.append({
                "id": f"{task}__{row['condition']}__r{row['run_num']}",
                "cell": str(cell), "task": task, "condition": row["condition"], "run": row["run_num"],
                "resolved": bool(row.get("resolved")), "exit_status": row.get("exit_status"),
                "dir": str(run_dir),
            })
    return runs


def load_history(run_dir: str) -> tuple[str, list[tuple[int, str, str]], int, dict]:
    """(problem statement, [(step, role, content)] after the task message, last agent
    step, uid -> step)."""
    events = [json.loads(line) for line in open(Path(run_dir) / "events.jsonl")]
    events = [e for e in events if e.get("origin") == "agent"]
    msgs = [e for e in events if e["message"].get("role") in ("user", "assistant")]
    problem = msgs[0]["message"]["content"]
    hist = [(int(e["step"]), e["message"]["role"], e["message"].get("content") or "") for e in msgs[1:]]
    last = max((s for s, r, _ in hist if r == "assistant"), default=0)
    return problem, hist, last, {e["uid"]: int(e["step"]) for e in events}


def history_at(view: str, hist, k: int, replay=None, uid_step=None) -> list[tuple[int | None, str, str]]:
    """The (step, role, content) entries the judge sees at checkpoint k. In the
    context view a message the agent did not write (an SU summary) has step None."""
    if view == "full":
        return [h for h in hist if h[0] <= k]
    # A format-error step logs no assistant message; take the next call that has one.
    call = k + 1
    while True:
        try:
            ctx = replay.context_at_call(call)
            break
        except KeyError:
            if call > replay.n_calls():
                raise
            call += 1
    out = []
    for m in ctx[2:]:   # system prompt and task message are given separately
        uid = (m.get("extra") or {}).get("uid") or m.get("uid")
        content = m.get("content") or ""
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        out.append((uid_step.get(uid), m.get("role"), content))
    return out


def _problem_text(task_msg: str) -> str:
    m = re.search(r"<pr_description>(.*?)</pr_description>", task_msg, re.S)
    return (m.group(1) if m else task_msg).strip()


def transcript(entries) -> str:
    out = []
    for step, role, content in entries:
        where = f"[step {step}]" if step is not None else "[inserted, not written by the agent]"
        out.append(f"{where} {'AGENT' if role == 'assistant' else 'OUTPUT'}:\n{content}")
    return "\n\n".join(out)


def build_messages(problem: str, entries, k: int, gold: str | None) -> list[dict]:
    head = f"<issue>\n{_problem_text(problem)}\n</issue>"
    if gold is not None:
        head += f"\n\n{GOLD_NOTE}\n<reference_fix>\n{gold}\n</reference_fix>"
    body = f"<agent_history>\n{transcript(entries)}\n</agent_history>"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": head},
            {"type": "text", "text": body, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": QUESTION.format(k=k)},
        ]},
    ]


def checkpoints(last: int, interval: int) -> list[int]:
    # Strictly before the final (submitting) step: a check there could not change anything.
    return list(range(interval, last, interval))


def parse_verdict(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if v.get("verdict") not in ("on_track", "off_track"):
        return None
    try:
        v["p_fail"] = min(max(float(v.get("p_fail")), 0.0), 1.0)
    except (TypeError, ValueError):
        return None
    if not isinstance(v.get("feedback", ""), str):
        return None
    onset = v.get("onset_step")
    v["onset_step"] = int(onset) if isinstance(onset, (int, float)) or (isinstance(onset, str) and onset.isdigit()) else None
    return v


# ── judge ───────────────────────────────────────────────────────────────────
def _done(path: Path) -> set:
    if not path.exists():
        return set()
    return {(r["id"], r["k"]) for r in map(json.loads, path.open())
            if r.get("verdict") and r.get("prompt_version", 1) == PROMPT_VERSION}


def judge_run(run, mode, view, gold, interval, model, out_path, done, dry):
    problem, hist, last, uid_step = load_history(run["dir"])
    replay = None
    if view == "context":
        from scripts.maintenance.reconstruct_context import Replay
        replay = Replay(run["dir"])
    n_calls = n_chars = 0
    for k in checkpoints(last, interval):
        if (run["id"], k) in done:
            continue
        entries = history_at(view, hist, k, replay, uid_step)
        msgs = build_messages(problem, entries, k, gold)
        chars = len(SYSTEM) + sum(len(b["text"]) for b in msgs[1]["content"])
        n_calls += 1
        n_chars += chars
        if dry:
            continue
        # Retries: at temperature 0 an identical re-query repeats the same reply, so an
        # empty reply (reasoning ran into --max-tokens) is re-asked once at
        # RETRY_TEMPERATURE, and a reply with JSON that misses a field is answered
        # with a correction turn (gold replies often dropped p_fail).
        verdict, raw, usages, query_msgs, m = None, "", [], msgs, model
        for _ in range(3):
            reply = m.query(query_msgs)
            raw = reply.get("content") or ""
            usages.append(reply["extra"]["response"]["usage"])
            verdict = parse_verdict(raw)
            if verdict:
                break
            if not raw.strip():
                m = _retry_model(model)
                query_msgs = msgs
            else:
                query_msgs = msgs + [{"role": "assistant", "content": raw},
                                     {"role": "user", "content": CORRECTION}]
        rec = {**{x: run[x] for x in ("id", "task", "condition", "run", "resolved", "exit_status")},
               "dir": run["dir"], "mode": mode, "view": view, "prompt_version": PROMPT_VERSION,
               "k": k, "last_step": last, "verdict": None, "raw": raw, "usage": usages,
               "model": model.settings["model"], "effort": model.settings["effort"]}
        if verdict:
            rec.update(verdict=verdict["verdict"], p_fail=verdict["p_fail"],
                       onset_step=verdict["onset_step"], reason=verdict.get("reason"),
                       feedback=verdict.get("feedback") or "")
        with _lock, out_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    return n_calls, n_chars


def cmd_judge(args):
    import os
    runs = discover(args.cells, set(args.tasks.split(",")) if args.tasks else None)
    if args.max_runs:
        runs = runs[: args.max_runs]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    golds = _gold_patches() if "gold" in args.modes.split(",") else {}
    model = None
    if not args.dry_run:
        os.environ.setdefault("MSWEA_EXTRACT_PROVIDER", "openrouter")
        os.environ.setdefault("MSWEA_EXTRACT_MODEL", args.model)
        os.environ.setdefault("MSWEA_EXTRACT_EFFORT", args.effort)
        # A normal verdict takes ~1k completion tokens; the 16k default only let
        # runaway reasoning burn budget before returning nothing.
        os.environ.setdefault("MSWEA_EXTRACT_MAX_TOKENS", str(args.max_tokens))
        from agentctx.compression.claude_extract import ClaudeExtractModel, extract_settings
        model = ClaudeExtractModel(extract_settings())
        print("judge:", json.dumps(model.settings), file=sys.stderr)
    print(f"{len(runs)} runs ({sum(not r['resolved'] for r in runs)} failed)", file=sys.stderr)
    views = ["full", "context"] if args.view == "both" else [args.view]
    for view in views:
        # full-context has no compression, so its context view repeats the full one.
        vruns = [r for r in runs if not (view == "context" and r["condition"] == "full-context")]
        for mode in args.modes.split(","):
            path = out / f"judge_{mode}{'_ctx' if view == 'context' else ''}.jsonl"
            done = _done(path)
            with ThreadPoolExecutor(args.workers) as pool:
                res = list(pool.map(lambda r: judge_run(
                    r, mode, view, golds.get(r["task"]) if mode == "gold" else None,
                    args.interval, model, path, done, args.dry_run), vruns))
            calls, chars = sum(c for c, _ in res), sum(c for _, c in res)
            print(f"{mode}/{view}: {len(vruns)} runs, {calls} calls, ~{chars / 4 / 1e6:.1f}M input tokens (chars/4)"
                  + (" [dry run]" if args.dry_run else f" -> {path}"), file=sys.stderr)


# ── report ──────────────────────────────────────────────────────────────────
def auroc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def cmd_report(args):
    labels = json.loads(Path(args.labels).read_text()) if args.labels else {}
    for path in sorted(Path(args.out).glob("judge_*.jsonl")):
        all_recs = [json.loads(line) for line in path.open()]
        conds = sorted({r["condition"] for r in all_recs})
        for cond in conds + (["ALL"] if len(conds) > 1 else []):
            group = [r for r in all_recs if cond == "ALL" or r["condition"] == cond]
            _report_group(f"{path.stem.split('_', 1)[1]} / {cond}", group, labels, args.threshold)


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def leaked_terms(rec, golds, cache) -> set:
    """Identifiers of the reference fix's added lines that appear in the judge's
    feedback but nowhere in the issue or the history up to the checkpoint: new
    information the feedback would hand the agent. A heuristic flag, not proof."""
    fb = rec.get("feedback") or ""
    gold = golds.get(rec["task"])
    if not fb or not gold or not rec.get("dir"):
        return set()
    added = {w for line in gold.splitlines() if line.startswith("+") and not line.startswith("+++")
             for w in _IDENT.findall(line)}
    key = (rec["dir"], rec["k"])
    if key not in cache:
        problem, hist, _, _ = load_history(rec["dir"])
        cache[key] = set(_IDENT.findall(problem + transcript(history_at("full", hist, rec["k"]))))
    return (added & set(_IDENT.findall(fb))) - cache[key]


def _report_group(title, all_recs, labels, thr):
        versions = {r.get("prompt_version", 1) for r in all_recs}
        if len(versions) > 1:
            print(f"\n!! {title}: mixed prompt versions {sorted(versions)}; using v{PROMPT_VERSION} only")
            all_recs = [r for r in all_recs if r.get("prompt_version", 1) == PROMPT_VERSION]
        recs = [r for r in all_recs if r.get("verdict")]
        if not recs:
            return
        runs = {}
        for r in recs:
            runs.setdefault(r["id"], {"meta": r, "ck": {}})["ck"][r["k"]] = r
        print(f"\n=== {title}: {len(runs)} runs, {len(recs)} checkpoints, "
              f"parse-fail {len(all_recs) - len(recs)} ===")
        mixed = {t for t in {m["meta"]["task"] for m in runs.values()}
                 if len({m["meta"]["resolved"] for m in runs.values() if m["meta"]["task"] == t}) == 2}
        ks = sorted({k for m in runs.values() for k in m["ck"]})
        print("k    n_alive  fail  AUROC(judge)  AUROC(mixed tasks)  AUROC(baseline: still running)")
        for k in ks:
            # A run that already submitted before k keeps its last verdict (no new evidence).
            sc, y, scm, ym, base = [], [], [], [], []
            for m in runs.values():
                prior = [kk for kk in m["ck"] if kk <= k]
                if not prior:
                    continue
                s = m["ck"][max(prior)]["p_fail"]
                fail = not m["meta"]["resolved"]
                sc.append(s); y.append(fail); base.append(m["meta"]["last_step"] > k)
                if m["meta"]["task"] in mixed:
                    scm.append(s); ym.append(fail)
            a, am, ab = auroc(sc, y), auroc(scm, ym), auroc([float(b) for b in base], y)
            fmt = lambda v: "  -  " if v is None else f"{v:.3f}"
            print(f"{k:<4} {sum(base):>7}  {sum(y):>4}  {fmt(a):>12}  {fmt(am):>18}  {fmt(ab):>14}")
        # The verdict and p_fail disagree often enough (off_track at p_fail 0.3) that
        # each alarm rule is reported on its own.
        rules = {
            f"p_fail >= {thr}": lambda c: c["p_fail"] >= thr,
            "off_track": lambda c: c["verdict"] == "off_track",
            f"p_fail >= {thr} or off_track": lambda c: c["p_fail"] >= thr or c["verdict"] == "off_track",
        }
        for name, rule in rules.items():
            print(f"\nfirst alarm ({name}):")
            fa = tot_ok = 0
            for rid, m in sorted(runs.items()):
                alarm = next((k for k in sorted(m["ck"]) if rule(m["ck"][k])), None)
                if m["meta"]["resolved"]:
                    tot_ok += 1
                    fa += alarm is not None
                    if alarm is not None:
                        print(f"  ok   {rid}: FALSE alarm {alarm} / last {m['meta']['last_step']}")
                    continue
                lab = labels.get(rid, {})
                extra = ""
                if lab:
                    extra = f"  onset {lab.get('onset')} anchor {lab.get('anchor')}"
                    if alarm is not None and lab.get("anchor") is not None:
                        extra += "  [before anchor]" if alarm < lab["anchor"] else "  [after anchor]"
                said = m["ck"][alarm].get("onset_step") if alarm is not None else None
                print(f"  FAIL {rid}: alarm {alarm} (judge onset {said}) / last {m['meta']['last_step']}{extra}")
            print(f"  false alarms on resolved runs: {fa}/{tot_ok}")
        golds, cache = _gold_patches(), {}
        with_fb = [r for r in recs if r.get("feedback")]
        leaks = [(r, t) for r in with_fb for t in [leaked_terms(r, golds, cache)] if t]
        # Code-ish feedback (backticks, dotted / snake_case names, calls) names places
        # or code even when the names are already in the history: review by hand.
        codeish = [r for r in with_fb if re.search(r"`|\b\w+\.\w+|\b[a-z]+_\w+|\w\(", r["feedback"])]
        print(f"feedback given: {len(with_fb)}; possible answer leaks (reference-fix identifiers "
              f"not yet in the history): {len(leaks)}; code-like feedback: {len(codeish)}")
        for r, t in leaks[:10]:
            print(f"  LEAK {r['id']} k={r['k']}: {sorted(t)} | {r['feedback'][:160]}")
        for r in codeish[:10]:
            print(f"  CODE {r['id']} k={r['k']}: {r['feedback'][:160]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge")
    j.add_argument("cells", nargs="+")
    j.add_argument("--out", required=True)
    j.add_argument("--modes", default="nogold,gold")
    j.add_argument("--view", choices=("full", "context", "both"), default="full")
    j.add_argument("--interval", type=int, default=10)
    j.add_argument("--tasks")
    j.add_argument("--max-runs", type=int)
    j.add_argument("--workers", type=int, default=4)
    j.add_argument("--model", default=DEFAULT_MODEL)
    j.add_argument("--effort", default="low")
    j.add_argument("--max-tokens", type=int, default=6000)
    j.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("report")
    r.add_argument("--out", required=True)
    r.add_argument("--labels")
    r.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()
    (cmd_judge if args.cmd == "judge" else cmd_report)(args)


if __name__ == "__main__":
    main()
