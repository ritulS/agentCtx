#!/usr/bin/env python3
"""Branch-point replay: does the context (full history vs OCSA selection) change
which fix Devstral chooses at the step where a run commits to one?

For each task, each finished run (FC, SU-free, OCSA of the Devstral-24B fc25
campaign) is scanned for its *decision call*: the first agent call whose reply
commits to the correct or to the known wrong fix (task-specific regexes below,
applied to the command first, then to the THOUGHT). The model is then re-queried
at that call (and `--offsets` calls earlier) under several contexts built from
the SAME history:

    own   the context the run actually sent (FC: the full history; SU-free: the
          full history until its first compression; OCSA: the real selection)
    full  the uncompressed history (== own for FC and pre-compression SU-free)
    sel   an OCSA selection of that history: the real one for OCSA runs; for
          FC / SU-free runs simulated by `select`, which calls the same selector
          (online_claude_select, anchored, cap 30000, keep-recent 3, DeepSeek
          V4.1 Flash via OpenRouter, effort low, temperature 0) before every call
          from the first one, exactly as the agent hook does

Each distinct context is sampled once at temperature 0 (the runs' setting; for
`own` this checks that the replay reproduces the original choice) and `--n`
times at `--temperature`. Identical contexts are sampled once and shared.

Sub-commands (run in order; each is resumable and writes under --out):
    plan     no API: detect decision calls, list the probes (plan.json)
    select   OpenRouter $: simulate OCSA selections on FC / SU-free histories
    sample   vLLM (Devstral, :8002): query every probe context
    report   label the samples, print per-task tables, write summary.csv

sympy-12419 has no fix decision: every run fixes `Identity._entry`; FC r2/r3 fail
because they submit a half-finished Python-3.11 import workaround (`matrices.py`'s
`collections.Callable` left), which the OCSA runs found by checking beyond the issue
example (matrix tests / explicit matrices) after confirming the fix. Its probes
(`plan --probe-calls`) sit right after that confirmation and right before the
submission, and the judge labels whether the reply runs such a broader check (A) or
heads for the submission (B), not a fix approach.

Usage:
    venv/bin/python scripts/maintenance/replay_decision.py plan
    venv/bin/python scripts/maintenance/replay_decision.py plan --probe-calls calls.json  # explicit probes
    venv/bin/python scripts/maintenance/replay_decision.py select
    venv/bin/python scripts/maintenance/replay_decision.py sample [--n 20 --temperature 0.7]
    venv/bin/python scripts/maintenance/replay_decision.py report
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from scripts.maintenance.reconstruct_context import Replay  # noqa: E402

BASE = ROOT / "data/r2/swebench/p30s"
CELLS = {
    "FC":     "devstral24b-iso-fc20/di__binf__fc",
    "SUfree": "devstral24b-iso-fc20/di__b21k__su-free",
    "OCSA":   "devstral24b-iso-fc20-dsflash/di__binf__ocsa",
}
DEFAULT_OUT = ROOT / "data/r2/probes/replay_decision_devstral24b_fc25"

# The OCSA cell's selector settings (experiment_results.json `extract_model`,
# conditions.py, run_r2_swe_sandbox_isolated_devstral24b_fc20.sh).
SELECTOR_ENV = {
    "MSWEA_EXTRACT_PROVIDER": "openrouter",
    "MSWEA_EXTRACT_MODEL": "deepseek/deepseek-v4.1-flash-1017",
    "MSWEA_EXTRACT_EFFORT": "low",
    "MSWEA_EXTRACT_MAX_TOKENS": "12000",
    "MSWEA_EXTRACT_PREFILL": "0",
    "MSWEA_SELECT_ANCHOR": "1",
    "MSWEA_SELECT_CAP": "30000",
}
KEEP_RECENT = 3

# Agent model as in configs/config-devstral-vllm-temp0.yaml.
AGENT_MODEL = "mistralai/Devstral-Small-2-24B-Instruct-2512"
AGENT_API_BASE = "http://localhost:8002/v1"
AGENT_MAX_TOKENS = 4096


# ── task-specific labels ────────────────────────────────────────────────────
# (code regex, thought regex) for each label; code wins when it matches.
LABELS = {
    "sympy__sympy-12419": {
        # "correct": a check beyond the issue example that reaches matrices.py (existing
        # matrix tests, explicit matrices); "wrong": heads for the submission
        "correct": (r"sympy/matrices|as_explicit|ImmutableMatrix|Matrix\(",
                    r"(run|check)\w* (the )?(existing )?matri(x|ces) tests"),
        "wrong":   (r"COMPLETE_TASK_AND_SUBMIT|git diff[^\n]*>",
                    r"(prepare|ready) to submit|submit (it|the patch)"),
    },
    "scikit-learn__scikit-learn-13135": {
        # gold: sort the k-means centers before taking midpoints
        "correct": (r"centers\s*=\s*np\.sort\(|np\.sort\(\s*(km\.fit|centers)|centers\.sort\(\)",
                    r"sort(ing)?\s+(the\s+)?(k-?means\s+)?(cluster\s+)?centers"),
        # sort the edges computed from unsorted centers: wrong values
        "wrong":   (r"bin_edges\[jj\]\s*=\s*np\.sort\(|np\.sort\(\s*bin_edges|bin_edges\[jj\]\.sort\(\)",
                    r"sort(ing)?\s+(the\s+)?bin[_ ]edges"),
    },
    "sympy__sympy-15875": {
        # gold: `if len(nz) == 0 or len(nz) == len(self.args): return None` (stay
        # undecided when every term is imaginary); the passing runs instead turn the
        # imaginary-case `return False` into `return None`, same direction
        # (thought: only proposals, "should / fix is to / change ... to return X",
        # not descriptions of what the code currently returns)
        "correct": (r"return\s+False[^\n]*/[^\n]*return\s+None|return\s+None",
                    r"(should|fix (is|would be) to|chang\w* [^.\n]{0,40}to)[ \t]+return[ \t]+`?None"
                    r"|return[ \t]+`?None`?[ \t]+instead"),
        # decide True / compute the imaginary part
        "wrong":   (r"return\s+True|im_part|sympy_im|expand\(b\)",
                    r"(should|fix (is|would be) to|chang\w* [^.\n]{0,40}to)[ \t]+return[ \t]+`?True"
                    r"|imaginary parts? (also )?sum to zero"),
    },
    "django__django-15525": {
        # gold: give the unsaved instance the target db (obj._state.db = db);
        # also accepted by the tests: skip the lookup when natural_key() fails
        "correct": (r"_state\.db\s*=|try:\s*\n\s*natural_key\s*=\s*Model\(\*\*data\)\.natural_key\(\)"
                    r"|except[^\n]*(ObjectDoesNotExist|Exception)[^\n]*:\s*\n[^\n]*(skip|natural)",
                    r"_state\.db|set(ting)? the (instance'?s? )?(database|db)"),
        # resolve FK natural keys in `data` first (a no-op: they are pks already)
        "wrong":   (r"get_by_natural_key\(\*field_value\)|for field in Model\._meta\.get_fields\(\)",
                    r"resolv\w* (the |any )?(fk|foreign[- ]key)s?( fields)?( that are)?( in)? natural[- ]key"),
    },
}


def _split(text: str) -> tuple[str, str]:
    marker = "```mswea_bash_command"
    if marker in text:
        head, _, cmd = text.partition(marker)
        return head, cmd
    return text, ""


def label(task: str, text: str) -> str:
    """correct | wrong | both | undecided."""
    thought, cmd = _split(text or "")
    # Code quoted inside the THOUGHT (the current source, not a proposal) is not a choice.
    thought = re.sub(r"```.*?(```|$)", " ", thought, flags=re.S)
    rules = LABELS[task]
    for part, idx in ((cmd, 0), (thought, 1)):
        hits = {lab for lab, pats in rules.items() if re.search(pats[idx], part, re.I)}
        if len(hits) == 1:
            return hits.pop()
        if hits:
            return "both"
    return "undecided"


# ── runs and contexts ───────────────────────────────────────────────────────
def iter_runs(tasks):
    for task in tasks:
        for cell, rel in CELLS.items():
            rows = {r["run_num"]: r for r in json.loads((BASE / rel / "experiment_results.json").read_text())
                    if r["instance_id"] == task}
            for run_dir in sorted(glob.glob(str(BASE / rel / task / "*" / "run_*"))):
                n = int(run_dir.rsplit("_", 1)[1])
                if n in rows:
                    yield task, cell, n, Path(run_dir), rows[n]


def full_history_at_call(rp: Replay, call: int) -> list[dict]:
    """Every message the agent added before call `call` (uncompressed). A message
    carries the call number current when it was added, so this is step < call;
    calls that ended in a format error have no assistant message, only the error."""
    return [rec["message"] for kind, rec in rp.ops if kind == "add" and rec["step"] < call]


def assistant_replies(rp: Replay) -> dict[int, str]:
    return {rec["step"]: rec["message"]["content"] for kind, rec in rp.ops
            if kind == "add" and rec["message"].get("role") == "assistant"}


def _wire(msgs: list[dict]) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


def _key(msgs: list[dict]) -> str:
    return hashlib.sha256(json.dumps(_wire(msgs), sort_keys=True).encode()).hexdigest()[:16]


def _probe_id(p: dict) -> str:
    return f"{p['task']}|{p['cell']}|r{p['run']}|c{p['call']}"


# ── plan ────────────────────────────────────────────────────────────────────
def cmd_plan(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    offsets = [int(x) for x in args.offsets.split(",")]
    # --decisions: {"<task>|<cell>|r<n>": {"call": N, "label": "correct|wrong|other"}} from a
    # human / blind-judge reading; overrides the regex-detected decision call and its label.
    overrides = json.loads(Path(args.decisions).read_text()) if args.decisions else {}
    # --probe-calls: {"<task>|<cell>|r<n>": {"calls": [N, ...], "label": "correct|wrong|other"}}
    # probes exactly those runs at exactly those calls (each its own decision call, offset 0);
    # every other run is skipped.
    explicit = json.loads(Path(args.probe_calls).read_text()) if args.probe_calls else None
    probes, runs = [], []
    for task, cell, n, run_dir, row in iter_runs(args.tasks):
        if explicit is not None:
            spec = explicit.get(f"{task}|{cell}|r{n}")
            if not spec:
                continue
            rp = Replay(run_dir)
            replies = assistant_replies(rp)
            runs.append({"task": task, "cell": cell, "run": n, "run_dir": str(run_dir.relative_to(ROOT)),
                         "resolved": bool(row["resolved"]), "n_calls": len(replies),
                         "decision_call": max(spec["calls"]), "decision_label": spec["label"],
                         "decision_source": "probe-calls", "regex_decision": [None, None],
                         "first_budget_compression": None})
            for call in spec["calls"]:
                if call not in replies:
                    raise SystemExit(f"{task}|{cell}|r{n}: call {call} has no assistant reply")
                probes.append({"task": task, "cell": cell, "run": n, "run_dir": str(run_dir.relative_to(ROOT)),
                               "resolved": bool(row["resolved"]), "decision_call": call, "offset": 0,
                               "call": call, "orig_label": spec["label"], "orig_decision_label": spec["label"]})
            continue
        rp = Replay(run_dir)
        replies = assistant_replies(rp)
        labels = {c: label(task, t) for c, t in sorted(replies.items())}
        decision = next((c for c, lab in labels.items() if lab in ("correct", "wrong")), None)
        regex_decision = (decision, labels.get(decision))
        ov = overrides.get(f"{task}|{cell}|r{n}")
        if ov:
            decision = ov["call"]
            labels[decision] = ov["label"]
        first_compression = min((c["step"] for c in rp.compressions if c.get("kind") == "budget"), default=None)
        runs.append({"task": task, "cell": cell, "run": n, "run_dir": str(run_dir.relative_to(ROOT)),
                     "resolved": bool(row["resolved"]), "n_calls": len(replies),
                     "decision_call": decision, "decision_label": labels.get(decision),
                     "decision_source": "override" if ov else "regex", "regex_decision": regex_decision,
                     "first_budget_compression": first_compression})
        if decision is None:
            continue
        # Offsets count replies, not calls: format-error calls have no reply to compare with.
        reply_calls = sorted(replies)
        at = reply_calls.index(decision)
        for off in offsets:
            if at - off < 0 or reply_calls[at - off] < 2:
                continue
            call = reply_calls[at - off]
            probes.append({"task": task, "cell": cell, "run": n, "run_dir": str(run_dir.relative_to(ROOT)),
                           "resolved": bool(row["resolved"]), "decision_call": decision, "offset": off,
                           "call": call, "orig_label": labels.get(call), "orig_decision_label": labels[decision]})
    (out / "plan.json").write_text(json.dumps({"offsets": offsets, "runs": runs, "probes": probes}, indent=1))
    print(f"{'task':34} {'cell':6} run res  calls decision label    1st-compr")
    for r in runs:
        print(f"{r['task']:34} {r['cell']:6} r{r['run']}  {'○' if r['resolved'] else '×'}  {r['n_calls']:5} "
              f"{str(r['decision_call']):>8} {str(r['decision_label']):9} {str(r['first_budget_compression']):>9}"
              f"   (regex: {r['regex_decision'][0]} {r['regex_decision'][1]})")
    need_sel = sum(1 for p in probes if p["cell"] != "OCSA")
    print(f"\n{len(probes)} probes ({len(offsets)} offsets); {need_sel} need a simulated selection (`select`).")
    print(f"wrote {out / 'plan.json'}")
    return 0


# ── select ──────────────────────────────────────────────────────────────────
def simulate_selection(run_dir: Path, upto: int, log) -> dict[int, list[dict]]:
    """Contexts an OCSA agent would have sent for calls 1..upto on this history."""
    from agentctx.compression import primitives as mem
    rp = Replay(run_dir)
    contexts, messages, prev_full = {}, None, []
    for call in range(1, upto + 1):
        full = full_history_at_call(rp, call)
        messages = list(full) if messages is None else messages + full[len(prev_full):]
        if call > 1 and len(full) > mem.N_PROTECTED + KEEP_RECENT:
            try:
                messages, *_ = mem.online_claude_select(full, messages, None, keep_recent=KEEP_RECENT)
            except Exception as exc:   # noqa: BLE001 - the agent also keeps its context on errors
                log(f"  call {call}: selector error {type(exc).__name__}: {exc}")
        contexts[call] = messages
        prev_full = full
    return contexts


def cmd_select(args) -> int:
    # Forced, not setdefault: a selector setting left in the shell must not leak in.
    os.environ.update(SELECTOR_ENV)
    os.environ.pop("MSWEA_EXTRACT_TEMPERATURE", None)   # provider default 0, as in the campaign
    out = Path(args.out)
    plan = json.loads((out / "plan.json").read_text())
    sel_dir = out / "selections"
    sel_dir.mkdir(exist_ok=True)
    os.environ.setdefault("MSWEA_SUMMARY_ATTEMPT_LOG", str(out / "selector_attempts.jsonl"))
    upto = defaultdict(int)
    for p in plan["probes"]:
        if p["cell"] != "OCSA":
            upto[(p["task"], p["cell"], p["run"], p["run_dir"])] = max(upto[(p["task"], p["cell"], p["run"], p["run_dir"])], p["call"])
    def one(item):
        (task, cell, n, run_dir), last = item
        dest = sel_dir / f"{task}__{cell}__r{n}.json"
        if dest.exists():
            return f"skip {dest.name} (exists)"
        tag = f"{task} {cell} r{n}"
        print(f"{tag}: selecting calls 1..{last}", flush=True)
        ctx = simulate_selection(ROOT / run_dir, last, lambda s: print(f"{tag}{s}", flush=True))
        dest.write_text(json.dumps({str(c): m for c, m in ctx.items()}))
        return f"{tag}: done"

    # Runs are independent (selector outcome state is thread-local); calls within a run are sequential.
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for msg in pool.map(one, sorted(upto.items())):
            print(msg, flush=True)
    print(f"selector settings: {SELECTOR_ENV}, keep_recent={KEEP_RECENT}")
    return 0


# ── sample ──────────────────────────────────────────────────────────────────
def probe_contexts(p: dict, out: Path) -> dict[str, list[dict]]:
    rp = Replay(ROOT / p["run_dir"])
    own = rp.context_at_call(p["call"])
    full = full_history_at_call(rp, p["call"])
    if p["cell"] == "OCSA":
        sel = own
    else:
        f = out / "selections" / f"{p['task']}__{p['cell']}__r{p['run']}.json"
        if not f.exists():
            raise SystemExit(f"missing {f}: run `select` first")
        sel = json.loads(f.read_text())[str(p["call"])]
    return {"own": own, "full": full, "sel": sel}


def cmd_sample(args) -> int:
    import openai
    out = Path(args.out)
    plan = json.loads((out / "plan.json").read_text())
    samples_f = out / "samples.jsonl"
    done = set()
    if samples_f.exists():
        for line in samples_f.read_text().splitlines():
            r = json.loads(line)
            done.add((r["ctx_key"], r["temperature"]))
    client = openai.OpenAI(base_url=args.api_base, api_key="EMPTY", timeout=1800, max_retries=2)

    # Distinct contexts across all probes (identical ones are sampled once).
    jobs, refs = {}, defaultdict(list)
    for p in plan["probes"]:
        for mode, msgs in probe_contexts(p, out).items():
            k = _key(msgs)
            jobs[k] = msgs
            refs[k].append({"probe": _probe_id(p), "mode": mode})
    (out / "context_refs.json").write_text(json.dumps(refs, indent=1))
    work = [(k, t, n) for k in jobs for t, n in ((0.0, 1), (args.temperature, args.n))
            if (k, t) not in done]
    print(f"{len(jobs)} distinct contexts, {len(work)} requests to send", flush=True)

    import requests
    root = args.api_base.rstrip("/").removesuffix("/v1")

    def cache_hits() -> float:
        m = re.search(r"^vllm:prefix_cache_hits_total\{[^}]*\}\s+(\S+)",
                      requests.get(f"{root}/metrics", timeout=30).text, re.M)
        return float(m.group(1)) if m else float("nan")

    def reset_cache() -> None:
        r = requests.post(f"{root}/reset_prefix_cache", timeout=60)
        if r.status_code == 404:
            raise SystemExit("POST /reset_prefix_cache -> 404: restart the server with VLLM_SERVER_DEV_MODE=1 "
                             "(or pass --no-reset-cache)")
        r.raise_for_status()

    def run(item):
        k, temp, n = item
        if args.reset_cache:
            reset_cache()
        hits0 = cache_hits()
        resp = client.chat.completions.create(model=args.model, messages=_wire(jobs[k]), temperature=temp,
                                              n=n, max_tokens=AGENT_MAX_TOKENS, seed=args.seed)
        # Prefix-cache tokens this request reused: 0 after a reset for n=1; with n>1 the
        # sibling samples may reuse the first one's prefill of the same prompt.
        hits = cache_hits() - hits0
        return [{"ctx_key": k, "temperature": temp, "idx": i, "text": c.message.content or "",
                 "finish_reason": c.finish_reason, "prompt_tokens": resp.usage.prompt_tokens,
                 "cache_reset": args.reset_cache, "prefix_cache_hit_tokens": hits}
                for i, c in enumerate(resp.choices)]

    # Greedy requests go first and one at a time, like an isolated run's calls (no batch
    # neighbours), so the temperature-0 replay of `own` checks reproduction fairly. With
    # --reset-cache (default) every request starts from an empty prefix cache, so all
    # requests are sent one at a time (a reset with requests in flight would not clear them).
    greedy = [w for w in work if w[1] == 0.0]
    hot = [w for w in work if w[1] != 0.0]
    with samples_f.open("a") as fh:
        for label_, items, workers in (("greedy", greedy, 1),
                                       ("hot", hot, 1 if args.reset_cache else args.workers)):
            with cf.ThreadPoolExecutor(workers) as pool:
                for i, rows in enumerate(pool.map(run, items), 1):
                    for r in rows:
                        fh.write(json.dumps(r) + "\n")
                    fh.flush()
                    if i % 10 == 0 or i == len(items):
                        print(f"  {label_} {i}/{len(items)}", flush=True)
    return 0


# ── judge ───────────────────────────────────────────────────────────────────
# The regex labels misread generated replies (a simulation script that sorts the centers
# under a "sort the bin_edges" plan; "expand the args" plans it does not know), so every
# reply is labelled by Claude, blind to the context it came from: it sees only the task
# rubric and the one reply. Approaches are named A / B / C, never "correct" / "wrong".
JUDGE_MODEL = "claude-haiku-5-5"   # the user's choice 2026-11-02: the cheap model
JUDGE_PRICE = (0.10, 0.50)           # $ per 1M input / output tokens, prompts <= 100K (Batches API: half)
JUDGE_SYSTEM = """\
You label one message written by an LLM coding agent that is fixing a GitHub issue. The \
message has a THOUGHT and usually one shell command. Decide whether, in THIS message, the \
agent commits to a specific fix approach, and which one.

Commitment: the message states the fix it will make ("The fix is to ...", "I'll change X \
to Y", "The solution is ...") or writes the change into the repository source (sed -i, a \
script that rewrites the source file, a patch). Not a commitment: describing the bug, \
explaining or quoting the existing code, listing options without choosing one, or saying \
it will look, check or test something without naming the fix.

A standalone test or simulation script is not itself the fix: judge by what the agent \
says the fix is, or by what it writes into the repository source. Code inside a \
simulation counts only when the agent presents it as the fix it is going to make.

If the message commits to an approach, label it with the letter from the rubric; \
otherwise label it "none". Put a short verbatim quote (at most 200 characters) from the \
message that shows the commitment in "evidence" (empty string for "none")."""
JUDGE_SYSTEM_12419 = """\
You label one message written by an LLM coding agent that is fixing a GitHub issue. The \
message has a THOUGHT and usually one shell command. The agent has already fixed the bug \
and confirmed it on the issue's example. Decide what this message does NEXT.

Label by the shell command when there is one (what it actually runs or writes), and by \
the THOUGHT only when there is no command. Put a short verbatim quote (at most 200 \
characters) from the message that shows the choice in "evidence"."""
JUDGE_RUBRIC = {
    "sympy__sympy-12419": """\
Issue: summing all elements of a symbolic Identity matrix gives 0 instead of n. The \
agent edited sympy (Identity._entry, summation code, and some `collections` imports so \
sympy imports on Python 3.11) and has just seen the issue's example give the right answer.
A = runs a check that reaches sympy's matrix code beyond the issue's symbolic example: \
the repository's existing tests for matrices (anything under sympy/matrices/, with \
pytest, sympy's test runner or by importing the test module), or code that builds \
explicit / concrete matrices (Matrix(...), ImmutableMatrix(...), .as_explicit(), a \
numeric-size Identity turned into an explicit matrix)
B = heads for the submission: writes the patch (git diff > file), prints it, submits \
(COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT) or writes the final summary of changes
C = anything else: other tests (e.g. summation tests or symbolic sums only), re-running \
the reproduction script, reading code, further edits
none = the message has no command and does not say what it will do next""",
    "scikit-learn__scikit-learn-13135": """\
Issue: KBinsDiscretizer with strategy='kmeans' fails because the k-means cluster centers, \
and therefore the bin edges computed as midpoints of consecutive centers, can be unsorted, \
which np.digitize rejects.
A = sort the k-means cluster centers before the bin edges are computed from them
B = compute the edges from the centers as they are, then sort the resulting bin_edges array
C = some other fix""",
    "sympy__sympy-15875": """\
Issue: Add._eval_is_zero gives a wrong answer (False) for a complex sum that is actually \
zero, e.g. -2*I + (1 + I)**2.
A = make the method return None (undecided, "can't tell") in the case where it currently \
wrongly returns False, i.e. stop asserting a definite answer there
B = make the method return True, or actively work out whether the expression is zero \
(e.g. expand, simplify or sum the terms or their imaginary parts, check whether the \
imaginary parts cancel) so that it can give a definite answer
C = some other fix""",
}
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"approach": {"type": "string", "enum": ["A", "B", "C", "none"]},
                   "evidence": {"type": "string"}},
    "required": ["approach", "evidence"],
    "additionalProperties": False,
}
JUDGE_LABEL = {"A": "correct", "B": "wrong", "C": "other", "none": "undecided"}


def judge_params(task: str, text: str, effort: str) -> dict:
    return {
        "model": JUDGE_MODEL,
        "max_tokens": 4096,
        "system": JUDGE_SYSTEM_12419 if task == "sympy__sympy-12419" else JUDGE_SYSTEM,
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        "messages": [{"role": "user", "content":
                      f"<rubric>\n{JUDGE_RUBRIC[task]}\n</rubric>\n\n<agent_message>\n{text}\n</agent_message>"}],
    }


def parse_judgment(msg) -> dict:
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    if msg.stop_reason == "refusal":
        return {"approach": None, "error": "refusal", **usage}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"approach": None, "error": f"unparsable ({msg.stop_reason})", **usage}
    return {"approach": data["approach"], "evidence": data["evidence"], **usage}


def judge_client():
    import anthropic
    from agentctx.compression.claude_extract import resolve_api_key
    key = resolve_api_key("anthropic")
    if not key:
        raise SystemExit("no Anthropic API key: export ANTHROPIC_API_KEY or write it to "
                         "~/.config/agentctx/anthropic_api_key")
    return anthropic.Anthropic(api_key=key)


def _cost(rows) -> float:
    return (sum(r.get("input_tokens", 0) for r in rows) * JUDGE_PRICE[0]
            + sum(r.get("output_tokens", 0) for r in rows) * JUDGE_PRICE[1]) / 1e6


def cmd_judge_calibrate(args, out: Path) -> int:
    """The 16 decision replies (labelled by the blind reading) and the replies 3 / 6 before
    them (first commitment comes later, so "none" is expected), labelled synchronously."""
    plan = json.loads((out / "plan.json").read_text())
    replies = {}
    items = []
    for r in plan["runs"]:
        if r["decision_call"] is None:
            continue
        key = (r["task"], r["cell"], r["run"])
        replies[key] = assistant_replies(Replay(ROOT / r["run_dir"]))
        items.append({**dict(zip(("task", "cell", "run"), key)), "call": r["decision_call"], "offset": 0,
                      "expected": {"correct": "A", "wrong": "B", "other": "C"}[r["decision_label"]]})
    for p in plan["probes"]:
        if p["offset"] > 0:
            items.append({"task": p["task"], "cell": p["cell"], "run": p["run"], "call": p["call"],
                          "offset": p["offset"], "expected": "none"})
    client = judge_client()

    def run(it):
        text = replies[(it["task"], it["cell"], it["run"])][it["call"]]
        msg = client.messages.create(**judge_params(it["task"], text, args.judge_effort))
        return {**it, **parse_judgment(msg)}

    with cf.ThreadPoolExecutor(8) as pool:
        res = list(pool.map(run, items))
    (out / f"judge_calibration_{args.judge_effort}.json").write_text(json.dumps(res, indent=1))
    for off in (0, 3, 6):
        rs = [r for r in res if r["offset"] == off]
        ok = sum(r["approach"] == r["expected"] for r in rs)
        print(f"offset -{off}: {ok}/{len(rs)} match the expected label")
        for r in rs:
            if r["approach"] != r["expected"]:
                print(f"   {r['task'][-12:]} {r['cell']:6} r{r['run']} call {r['call']}: expected {r['expected']}, "
                      f"got {r['approach']} {r.get('error', '')} | {r.get('evidence', '')[:120]}")
    print(f"effort {args.judge_effort}: ${_cost(res):.2f} at standard prices for {len(res)} calls")
    return 0


def cmd_judge(args) -> int:
    """Label every reply in samples.jsonl through the Message Batches API (resumable)."""
    out = Path(args.out)
    if args.calibrate:
        return cmd_judge_calibrate(args, out)
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    import time
    plan = json.loads((out / "plan.json").read_text())
    refs = json.loads((out / "context_refs.json").read_text())
    task_of_probe = {_probe_id(p): p["task"] for p in plan["probes"]}
    task_of_ctx = {k: task_of_probe[uses[0]["probe"]] for k, uses in refs.items()}
    samples = [json.loads(line) for line in (out / "samples.jsonl").read_text().splitlines()]
    judged_f, state_f = out / "judgments.jsonl", out / "judge_batches.json"
    judged = {}
    if judged_f.exists():
        for line in judged_f.read_text().splitlines():
            j = json.loads(line)
            if j.get("approach"):
                judged[j["i"]] = j
    state = json.loads(state_f.read_text()) if state_f.exists() else []
    client = judge_client()

    def collect(entry):
        while True:
            b = client.messages.batches.retrieve(entry["id"])
            if b.processing_status == "ended":
                break
            c = b.request_counts
            print(f"  batch {entry['id']}: processing {c.processing}, succeeded {c.succeeded}", flush=True)
            time.sleep(60)
        with judged_f.open("a") as fh:
            for res in client.messages.batches.results(entry["id"]):
                i = int(res.custom_id[1:])
                if res.result.type == "succeeded":
                    j = {"i": i, "effort": entry["effort"], **parse_judgment(res.result.message)}
                else:
                    j = {"i": i, "approach": None, "error": res.result.type}
                fh.write(json.dumps(j) + "\n")
                if j.get("approach"):
                    judged[i] = j
        entry["collected"] = True
        state_f.write_text(json.dumps(state, indent=1))

    for entry in state:
        if not entry.get("collected"):
            collect(entry)
    for _ in range(2):   # first pass, then one retry of whatever errored or was refused
        todo = [i for i in range(len(samples)) if i not in judged]
        if not todo:
            break
        reqs = [Request(custom_id=f"s{i:05d}", params=MessageCreateParamsNonStreaming(
                    **judge_params(task_of_ctx[samples[i]["ctx_key"]], samples[i]["text"], args.judge_effort)))
                for i in todo]
        b = client.messages.batches.create(requests=reqs)
        print(f"submitted batch {b.id} with {len(reqs)} requests", flush=True)
        state.append({"id": b.id, "n": len(reqs), "effort": args.judge_effort, "collected": False})
        state_f.write_text(json.dumps(state, indent=1))
        collect(state[-1])
    missing = len(samples) - len(judged)
    print(f"labelled {len(judged)}/{len(samples)} replies ({missing} missing); "
          f"~${_cost(judged.values()) / 2:.2f} at batch prices")
    return 0


# ── report ──────────────────────────────────────────────────────────────────
def cmd_report(args) -> int:
    out = Path(args.out)
    plan = json.loads((out / "plan.json").read_text())
    refs = json.loads((out / "context_refs.json").read_text())
    by_ctx = defaultdict(list)
    for i, line in enumerate((out / "samples.jsonl").read_text().splitlines()):
        r = json.loads(line)
        by_ctx[r["ctx_key"]].append({**r, "i": i})
    # Claude's labels (`judge`) when present, else the regex ones.
    judged = {}
    if (out / "judgments.jsonl").exists():
        for line in (out / "judgments.jsonl").read_text().splitlines():
            j = json.loads(line)
            if j.get("approach"):
                judged[j["i"]] = JUDGE_LABEL[j["approach"]]
    source = "Claude judge" if judged else "regex"

    def lab(task, s):
        return judged.get(s["i"], "unlabelled") if judged else label(task, s["text"])

    probe_of = {_probe_id(p): p for p in plan["probes"]}
    rows = []
    for k, uses in refs.items():
        samples = by_ctx.get(k, [])
        for use in uses:
            p = probe_of[use["probe"]]
            hot = [lab(p["task"], s) for s in samples if s["temperature"] > 0]
            greedy = [lab(p["task"], s) for s in samples if s["temperature"] == 0]
            c = Counter(hot)
            rows.append({**{f: p[f] for f in ("task", "cell", "run", "resolved", "decision_call", "offset",
                                               "call", "orig_label", "orig_decision_label")},
                         "mode": use["mode"], "ctx_key": k, "greedy": greedy[0] if greedy else None, "n": len(hot),
                         **{lb: c[lb] for lb in ("correct", "wrong", "other", "both", "undecided", "unlabelled")}})
    rows.sort(key=lambda r: (r["task"], r["offset"], r["cell"], r["run"], r["mode"]))
    with (out / "summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def share(rs):
        cor = sum(r["correct"] for r in rs)
        dec = cor + sum(r["wrong"] for r in rs)
        oth = sum(r["other"] for r in rs)
        return f"{cor}/{dec}" + (f" ({cor / dec:.0%})" if dec else "") + (f" +{oth}C" if oth else "")

    for task in sorted({r["task"] for r in rows}):
        print(f"\n## {task}  (correct / correct+wrong among the hot samples; labels: {source})")
        for off in sorted({r["offset"] for r in rows}):
            print(f"  offset -{off}:")
            for cell in CELLS:
                line = []
                for mode in ("own", "full", "sel"):
                    rs = [r for r in rows if r["task"] == task and r["offset"] == off
                          and r["cell"] == cell and r["mode"] == mode]
                    line.append(f"{mode} {share(rs):>14}")
                print(f"    {cell:6} " + "   ".join(line))
        print("  per run at the decision call (orig -> greedy own; correct/decided own | full | sel):")
        for r0 in [r for r in rows if r["task"] == task and r["offset"] == 0 and r["mode"] == "own"]:
            same = [r for r in rows if r["task"] == task and r["offset"] == 0
                    and r["cell"] == r0["cell"] and r["run"] == r0["run"] and r["call"] == r0["call"]]
            m = {r["mode"]: r for r in same}
            print(f"    {r0['cell']:6} r{r0['run']} {'○' if r0['resolved'] else '×'} call {r0['call']:3} "
                  f"{r0['orig_label']:>9} -> {str(r0['greedy']):9} | "
                  + " | ".join(f"{share([m[x]]):>12}" for x in ("own", "full", "sel") if x in m))
    greedy = [s for ss in by_ctx.values() for s in ss if s["temperature"] == 0]
    reset = sum(1 for s in greedy if s.get("cache_reset"))
    hit = sum(1 for s in greedy if (s.get("prefix_cache_hit_tokens") or 0) > 0)
    print(f"\ngreedy requests: {len(greedy)}, sent after a cache reset: {reset}, with prefix-cache hits: {hit}")
    print(f"wrote {out / 'summary.csv'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "select", "sample", "judge", "report"])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--tasks", nargs="+", default=list(LABELS))
    ap.add_argument("--offsets", default="0,3,6", help="replies before the decision call to probe (plan)")
    ap.add_argument("--decisions", help="JSON of decision calls/labels overriding the regex (plan)")
    ap.add_argument("--probe-calls", help="JSON of runs and the exact calls to probe; skips every other run (plan)")
    ap.add_argument("--n", type=int, default=20, help="samples per context at --temperature (sample)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--reset-cache", action=argparse.BooleanOptionalAction, default=True,
                    help="empty vLLM's prefix cache before every request (needs VLLM_SERVER_DEV_MODE=1; sample)")
    ap.add_argument("--workers", type=int, default=4, help="parallel requests (sample) or runs (select)")
    ap.add_argument("--model", default=AGENT_MODEL)
    ap.add_argument("--api-base", default=AGENT_API_BASE)
    ap.add_argument("--calibrate", action="store_true",
                    help="judge: label the 16 original decision replies and the replies before them first")
    ap.add_argument("--judge-effort", default="low", choices=["low", "medium", "high", "max"])
    args = ap.parse_args()
    return {"plan": cmd_plan, "select": cmd_select, "sample": cmd_sample, "judge": cmd_judge,
            "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
