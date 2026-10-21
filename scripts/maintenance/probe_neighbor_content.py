#!/usr/bin/env python3
"""Does the CONTENT of concurrently served requests change what Qwen3.5-35B-A3B generates?

Follow-up to scripts/maintenance/probe_prefix_cache_effect.py. The isolated
(one run per fresh server) vs 3-worker sandbox cells mix two things: the NUMBER
of neighbours in the batch (kernel split / reduction order, i.e. numeric noise)
and the CONTENT of those neighbours (what information leakage would mean). This
probe separates them: every target prompt (a real agent prompt: a message
prefix of a finished trajectory) is generated greedily (temperature 0, seed 0)
under conditions that differ only in what the two co-scheduled neighbours are:

  alone   no neighbour (server otherwise idle)
  same    two prompts from OTHER RUNS of the SAME task
  other   two prompts from the OTHER repository (django <-> scikit-learn)
  self    two copies of the target prompt itself (strongest possible overlap)

Neighbours are kept in flight for the whole target generation: each neighbour
is one streaming request with ignore_eos that keeps decoding until the target
has finished (closing the stream aborts it), started before the target and
confirmed decoding (first token received) before the target is sent, so the
batch holds the target plus two steadily decoding neighbours the whole time
with one neighbour prefill per condition. The recorded coverage fraction
verifies it; the server's KV ownership trace can confirm co-residency via the
recorded response ids. Each condition is
collected twice per prompt, so within-condition repeat agreement is the noise
floor. Reading: if `same`, `other` and `self` agree with `alone` to the same
degree (and that degree is no worse than their own repeat agreement), the
neighbours' content does not enter the generation; concurrency adds batch
noise only. If `same`/`self` diverge from `alone` more often or earlier than
`other`, content matters.

Serving must be the sandbox condition (prefix caching OFF, the launcher checks)
and idle: no agent runs on the server while collecting.

Usage (Albus, caching-OFF server up and idle):
  python scripts/maintenance/probe_neighbor_content.py collect --label nb1
  python scripts/maintenance/probe_neighbor_content.py compare nb1 --csv data/r2/probes/neighbor_content/rows.csv
  python scripts/maintenance/probe_neighbor_content.py verify-trace nb1 --trace-dir logs/kv-cache/<server log name>

Defaults: the 40 prompts of the prefix-cache probe (reused from
data/r2/probes/prefix_cache_effect/prompts.json when present, else sampled the
same way), neighbour pool from the same cell, 512 generated tokens, output
under data/r2/probes/neighbor_content/ (gitignored).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_prefix_cache_effect import (  # noqa: E402
    DEFAULT_CELL, MODEL, SANDBOX_TASKS, WS, agreement, pick_prompts,
)

DEFAULT_OUT = WS / "data/r2/probes/neighbor_content"
PREFIX_PROBE_PROMPTS = WS / "data/r2/probes/prefix_cache_effect/prompts.json"
CONDITIONS = ("alone", "same", "other", "self")
N_NEIGHBOURS = 2


def repo_of(task_id: str) -> str:
    return task_id.split("__")[0]


def build_neighbour_pool(cell: Path, targets: list[dict], seed: int, per_task: int) -> dict:
    """per task: up to `per_task` prompts (one per run) from the infra-clean runs.

    A target's own run is excluded per target in assign_neighbours, not here:
    the clean runs of a task are few, and the targets already come from them.

    Same selection rule as pick_prompts (message prefixes ending in a user turn,
    k >= 3, infra-clean runs of the sandbox tasks), but the candidate scan keeps
    (run, k) pairs only and loads the few chosen trajectories afterwards.
    """
    tags_file = cell / "failure_tags.csv"
    if not tags_file.exists():
        sys.exit(f"{tags_file} missing: run scripts/maintenance/tag_run_failures.py {cell} first")
    clean = [
        r for r in csv.DictReader(tags_file.open())
        if r["instance_id"] in SANDBOX_TASKS
        and r["runaway"] == "False" and r["hung"] == "False" and r["timeout"] == "False"
    ]
    rng = random.Random(seed)
    rng.shuffle(clean)
    pool: dict[str, list[dict]] = {t: [] for t in SANDBOX_TASKS}
    for r in clean:
        task = r["instance_id"]
        if len(pool[task]) >= per_task:
            continue
        run_dir = cell / task / r["condition"] / f"run_{r['run_num']}"
        run_rel = str(run_dir.relative_to(WS))
        try:
            messages = json.loads((run_dir / "trajectory.json").read_text())["messages"]
        except Exception:
            continue
        ks = [k for k in range(3, len(messages) + 1) if messages[k - 1]["role"] == "user"]
        if not ks:
            continue
        k = rng.choice(ks)
        prefix = [{"role": m["role"], "content": m["content"]} for m in messages[:k]]
        pool[task].append({"id": f"{task}/run_{run_dir.name[4:]}/k{k}", "run_dir": run_rel, "k": k,
                           "chars": sum(len(m["content"]) for m in prefix), "messages": prefix})
    short = {t: len(v) for t, v in pool.items()}
    for t, n in short.items():
        if n < N_NEIGHBOURS:
            sys.exit(f"neighbour pool too small for {t}: {n} < {N_NEIGHBOURS} (relax --pool-per-task / use another cell)")
    print(f"neighbour pool (prompts per task, each from a distinct run): {short}")
    return pool


def assign_neighbours(targets: list[dict], pool: dict, seed: int) -> tuple[dict, dict]:
    """target id -> {same: [ids], other: [ids]} (self needs no assignment)."""
    by_id = {p["id"]: p for v in pool.values() for p in v}
    plan = {}
    for t in targets:
        task = t["id"].split("/")[0]
        rng = random.Random(f"{seed}:{t['id']}")
        same_pool = [p for p in pool[task] if p["run_dir"] != t["run_dir"]]
        if len(same_pool) < N_NEIGHBOURS:
            sys.exit(f"{t['id']}: only {len(same_pool)} same-task neighbour runs besides its own")
        other_pool = [p for task2, v in pool.items() if repo_of(task2) != repo_of(task) for p in v]
        plan[t["id"]] = {
            "same": [p["id"] for p in rng.sample(same_pool, N_NEIGHBOURS)],
            "other": [p["id"] for p in rng.sample(other_pool, N_NEIGHBOURS)],
        }
    return plan, by_id


def post(api_base: str, messages: list[dict], max_tokens: int, timeout: float, want_tokens: bool) -> dict:
    t0 = time.time()
    body = {"model": MODEL, "messages": messages, "temperature": 0, "seed": 0, "max_tokens": max_tokens}
    if want_tokens:
        body.update({"logprobs": True, "top_logprobs": 1})
    resp = requests.post(f"{api_base}/chat/completions", json=body, timeout=timeout)
    t1 = time.time()
    resp.raise_for_status()
    j = resp.json()
    choice = j["choices"][0]
    usage = j.get("usage") or {}
    rec = {
        "response_id": j.get("id"), "t_start": t0, "t_end": t1, "latency_s": round(t1 - t0, 2),
        "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
    }
    if want_tokens:
        rec["tokens"] = [(t["token"], t["logprob"]) for t in ((choice.get("logprobs") or {}).get("content") or [])]
        rec["reasoning"] = choice["message"].get("reasoning_content")
        rec["content"] = choice["message"].get("content")
    return rec


def server_running_requests(api_base: str) -> float | None:
    try:
        text = requests.get(api_base.replace("/v1", "") + "/metrics", timeout=10).text
    except Exception:
        return None
    for line in text.splitlines():
        if line.startswith("vllm:num_requests_running"):
            try:
                return float(line.rsplit(" ", 1)[1])
            except ValueError:
                return None
    return None


def wait_idle(api_base: str, timeout_s: float = 120) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        n = server_running_requests(api_base)
        if n is None or n == 0:
            return
        time.sleep(0.5)
    print("WARNING: server still reports running requests; continuing", flush=True)


def neighbour_stream(api_base: str, msgs: list[dict], max_tokens: int, timeout: float,
                     stop: threading.Event, started: threading.Event) -> dict:
    """One streaming request that decodes until `stop` (ignore_eos); closing the stream aborts it server-side."""
    t0 = time.time()
    body = {"model": MODEL, "messages": msgs, "temperature": 0, "seed": 0, "max_tokens": max_tokens,
            "stream": True, "ignore_eos": True}
    rid, n_chunks, t_first, err = None, 0, None, None
    try:
        with requests.post(f"{api_base}/chat/completions", json=body, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(chunk_size=1):
                if stop.is_set():
                    break
                if not line.startswith(b"data: ") or line == b"data: [DONE]":
                    continue
                n_chunks += 1
                if t_first is None:
                    t_first = time.time()
                    started.set()
                    try:
                        rid = json.loads(line[6:])["id"]
                    except Exception:
                        pass
    except Exception as exc:
        err = str(exc)[:200]
    finally:
        started.set()
    rec = {"response_id": rid, "t_start": t0, "t_first_token": t_first, "t_end": time.time(),
           "streamed_chunks": n_chunks}
    if err:
        rec["error"] = err
    return rec


def generate_with_neighbours(api_base: str, target: list[dict], neighbours: list[list[dict]],
                             max_tokens: int, neighbour_max_tokens: int, timeout: float, lead_s: float) -> dict:
    """Run the target once while every neighbour prompt is decoding continuously (restarted only if it ends)."""
    stop = threading.Event()
    windows: list[list[dict]] = [[] for _ in neighbours]
    started = [threading.Event() for _ in neighbours]

    def neighbour_loop(idx: int, msgs: list[dict]) -> None:
        while not stop.is_set():
            r = neighbour_stream(api_base, msgs, neighbour_max_tokens, timeout, stop, started[idx])
            windows[idx].append(r)
            if "error" in r and not stop.is_set():
                time.sleep(0.5)

    with ThreadPoolExecutor(max_workers=len(neighbours) or 1) as ex:
        futures = [ex.submit(neighbour_loop, i, msgs) for i, msgs in enumerate(neighbours)]
        if neighbours:
            for ev in started:  # every neighbour has produced its first token (prefill done) before the target arrives
                ev.wait(timeout=max(lead_s, 60.0))
            time.sleep(lead_s)
        rec = post(api_base, target, max_tokens, timeout, want_tokens=True)
        stop.set()
        for f in futures:
            f.result()
    rec["neighbours"] = windows
    rec["coverage"] = coverage(rec, windows, min_live=len(neighbours)) if neighbours else None
    rec["coverage_any"] = coverage(rec, windows, min_live=1) if neighbours else None
    return rec


def coverage(rec: dict, windows: list[list[dict]], min_live: int) -> float:
    """fraction of the target's [t_start, t_end] during which >= min_live neighbour requests were in flight."""
    t0, t1 = rec["t_start"], rec["t_end"]
    if t1 <= t0:
        return 0.0
    events = []
    for win in windows:
        for w in win:
            if "error" in w:
                continue
            a, b = max(w["t_start"], t0), min(w["t_end"], t1)
            if b <= a:
                continue  # no overlap with the target's window
            events.append((a, +1))
            events.append((b, -1))
    events.sort()
    live, covered, last = 0, 0.0, t0
    for t, d in events:
        if live >= min_live:
            covered += max(0.0, t - last)
        live += d
        last = t
    if live >= min_live:
        covered += max(0.0, t1 - last)
    return round(covered / (t1 - t0), 3)


def cmd_collect(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prompts_file = out / "prompts.json"
    if prompts_file.exists():
        targets = json.loads(prompts_file.read_text())
        print(f"reusing {len(targets)} target prompts from {prompts_file}")
    elif PREFIX_PROBE_PROMPTS.exists() and args.n == 40 and not args.resample:
        targets = json.loads(PREFIX_PROBE_PROMPTS.read_text())
        prompts_file.write_text(json.dumps(targets, indent=1))
        print(f"copied {len(targets)} target prompts from {PREFIX_PROBE_PROMPTS}")
    else:
        targets = pick_prompts(Path(args.cell), args.n, args.seed)
        prompts_file.write_text(json.dumps(targets, indent=1))
        print(f"wrote {len(targets)} target prompts to {prompts_file}")
    if args.limit:
        targets = targets[: args.limit]
    pool_file = out / "neighbours.json"
    if pool_file.exists():
        saved = json.loads(pool_file.read_text())
        pool, plan = saved["pool"], saved["plan"]
        by_id = {p["id"]: p for v in pool.values() for p in v}
        print(f"reusing neighbour pool / plan from {pool_file}")
    else:
        pool = build_neighbour_pool(Path(args.cell), json.loads(prompts_file.read_text()), args.seed + 1, args.pool_per_task)
        plan, by_id = assign_neighbours(json.loads(prompts_file.read_text()), pool, args.seed)
        pool_file.write_text(json.dumps({"pool": pool, "plan": plan}, indent=1))
        print(f"wrote neighbour pool / plan to {pool_file}")

    info = requests.get(f"{args.api_base}/models", timeout=30).json()
    metrics = requests.get(args.api_base.replace("/v1", "") + "/metrics", timeout=30).text
    cache_flag = next((line for line in metrics.splitlines() if "vllm:cache_config_info" in line and "enable_prefix_caching" in line), "")
    print(f"server: {info['data'][0]['id']}  {cache_flag[:160]}")
    if 'enable_prefix_caching="True"' in cache_flag and not args.allow_prefix_cache:
        sys.exit("server has prefix caching ON; the sandbox condition is OFF (--allow-prefix-cache overrides)")
    n_run = server_running_requests(args.api_base)
    if n_run:
        sys.exit(f"server is busy ({n_run:.0f} running requests); collect on an idle server")

    conditions = [c for c in args.conditions.split(",") if c]
    for c in conditions:
        if c not in CONDITIONS:
            sys.exit(f"unknown condition {c!r}; choose from {CONDITIONS}")
    result_file = out / f"{args.label}.json"
    if result_file.exists():
        results = json.loads(result_file.read_text())
        done = {r["id"] for r in results["runs"]}
        print(f"resuming {result_file}: {len(done)} prompts done")
    else:
        results = {"label": args.label, "server_cache_config": cache_flag, "max_tokens": args.max_tokens,
                   "neighbour_max_tokens": args.neighbour_max_tokens, "lead_s": args.lead_s,
                   "conditions": conditions, "passes": args.passes, "runs": []}
        done = set()
    rng = random.Random(args.seed)
    t_all = time.time()
    for i, t in enumerate(targets, 1):
        if t["id"] in done:
            continue
        run = {"id": t["id"], "neighbour_ids": plan[t["id"]], "cond": {c: [] for c in conditions}}
        for pass_no in range(1, args.passes + 1):
            order = conditions[:]
            rng.shuffle(order)
            for cond in order:
                if cond == "alone":
                    nb = []
                elif cond == "self":
                    nb = [t["messages"]] * N_NEIGHBOURS
                else:
                    nb = [by_id[nid]["messages"] for nid in plan[t["id"]][cond]]
                wait_idle(args.api_base)
                rec = generate_with_neighbours(args.api_base, t["messages"], nb, args.max_tokens,
                                               args.neighbour_max_tokens, args.timeout, args.lead_s)
                rec["pass"] = pass_no
                run["cond"][cond].append(rec)
                cov = "" if rec["coverage"] is None else (f" cov2={rec['coverage']:.2f} cov1={rec['coverage_any']:.2f} "
                                                          f"nb_reqs={sum(len(w) for w in rec['neighbours'])} nb_chunks={sum(x.get('streamed_chunks', 0) for w in rec['neighbours'] for x in w)}")
                print(f"[{i:3d}/{len(targets)}] {t['id']:52s} p{pass_no} {cond:5s} gen={rec['completion_tokens']:4d} "
                      f"{rec['latency_s']:6.1f}s{cov}", flush=True)
        results["runs"].append(run)
        result_file.write_text(json.dumps(results))
    print(f"wrote {result_file}  ({(time.time() - t_all) / 60:.1f} min)")
    return 0


def summarize(name: str, pairs: list[dict]) -> str:
    ident = sum(p["identical"] for p in pairs)
    divs = [p["first_divergence"] for p in pairs if p["first_divergence"] is not None]
    gaps = [p["mean_abs_logprob_gap"] for p in pairs]
    med = statistics.median(divs) if divs else "-"
    return (f"{name:30s} identical {ident:3d}/{len(pairs):3d}   first divergence median {med!s:>6}  min {min(divs) if divs else '-'!s:>4}"
            f"   mean |dlogprob| on common prefix {statistics.fmean(gaps) if gaps else 0:.4f}")


def cmd_compare(args) -> int:
    out = Path(args.out)
    res = json.loads((out / f"{args.label}.json").read_text())
    conds = res["conditions"]
    runs = [r for r in res["runs"] if all(len(r["cond"].get(c, [])) >= 2 for c in conds)]
    print(f"{res['label']}: {res['server_cache_config'][:120]}")
    print(f"prompts with 2 passes in every condition: {len(runs)}  conditions {conds}  max_tokens {res['max_tokens']}\n")
    rows = []
    tok = lambda r, c, p: r["cond"][c][p]["tokens"]  # noqa: E731
    print("noise floor (pass1 vs pass2 within a condition)")
    for c in conds:
        pairs = [agreement(tok(r, c, 0), tok(r, c, 1)) for r in runs]
        rows += [(r["id"], f"within_{c}", p) for r, p in zip(runs, pairs)]
        print("  " + summarize(c, pairs))
    if "alone" in conds:
        print("\nvs alone (pass1 vs pass1, pass2 vs pass2 pooled)")
        per_cond = {}
        for c in conds:
            if c == "alone":
                continue
            pairs = [agreement(tok(r, "alone", p), tok(r, c, p)) for r in runs for p in (0, 1)]
            per_cond[c] = pairs
            rows += [(r["id"], f"alone_vs_{c}_p{p + 1}", pr) for (r, p), pr in zip([(r, p) for r in runs for p in (0, 1)], pairs)]
            print("  " + summarize(f"alone vs {c}", pairs))
        if "same" in per_cond and "other" in per_cond:
            s, o = per_cond["same"], per_cond["other"]
            s_only = sum(a["identical"] and not b["identical"] for a, b in zip(s, o))
            o_only = sum(b["identical"] and not a["identical"] for a, b in zip(s, o))
            print(f"\n  paired: identical-to-alone under same but not other: {s_only};  under other but not same: {o_only}"
                  f"  (McNemar discordant pairs; a content effect would make these asymmetric)")
    if len(conds) > 1:
        print("\nbetween neighbour conditions (same pass)")
        for i, a in enumerate(conds):
            for b in conds[i + 1:]:
                if "alone" in (a, b):
                    continue
                pairs = [agreement(tok(r, a, p), tok(r, b, p)) for r in runs for p in (0, 1)]
                print("  " + summarize(f"{a} vs {b}", pairs))
    print("\nconcurrency check (neighbour coverage of the target's generation window)")
    for c in conds:
        if c == "alone":
            lat = statistics.median(r["cond"][c][p]["latency_s"] for r in runs for p in (0, 1))
            print(f"  {c:6s} median latency {lat:5.1f}s")
            continue
        cov2 = [r["cond"][c][p]["coverage"] for r in runs for p in (0, 1)]
        cov1 = [r["cond"][c][p]["coverage_any"] for r in runs for p in (0, 1)]
        lat = statistics.median(r["cond"][c][p]["latency_s"] for r in runs for p in (0, 1))
        print(f"  {c:6s} median latency {lat:5.1f}s   both neighbours live: mean {statistics.fmean(cov2):.2f} min {min(cov2):.2f}"
              f"   >=1 live: mean {statistics.fmean(cov1):.2f} min {min(cov1):.2f}")
    print("\nReading: content does not enter the generation if same / other / self agree with alone equally (and no worse than\n"
          "each condition's own repeat agreement). Earlier or more frequent divergence for same / self than for other = content effect.")
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "pair", "identical", "first_divergence", "mean_abs_logprob_gap", "max_abs_logprob_gap"])
            for i, name, p in rows:
                w.writerow([i, name, p["identical"], p["first_divergence"], f"{p['mean_abs_logprob_gap']:.5f}", f"{p['max_abs_logprob_gap']:.5f}"])
        print(f"per-prompt rows written to {args.csv}")
    return 0


def trace_rid(request_id: str) -> str:
    """The scheduler's request id is the API response id plus an 8-hex suffix (chatcmpl-<16hex>-<8hex>)."""
    head, _, tail = request_id.rpartition("-")
    return head if head.count("-") == 1 and len(tail) == 8 else request_id


def cmd_verify_trace(args) -> int:
    """Co-residency from the server's KV ownership trace (TracingScheduler): each request's residency is the
    interval from its first block snapshot to its 'finished' record (snapshots are written on allocation
    changes only, so intervals, not identical ticks, are compared). Reports the fraction of the target's
    residency during which both neighbour requests were resident."""
    out = Path(args.out)
    res = json.loads((out / f"{args.label}.json").read_text())
    wanted: dict[str, tuple[str, str, int, set[str]]] = {}  # target rid -> (prompt id, cond, pass, neighbour rids)
    for r in res["runs"]:
        for cond, recs in r["cond"].items():
            for rec in recs:
                nb = {w["response_id"] for win in rec.get("neighbours") or [] for w in win if w.get("response_id")}
                if rec.get("response_id"):
                    wanted[rec["response_id"]] = (r["id"], cond, rec["pass"], nb)
    all_ids = set(wanted) | {n for *_, nb in wanted.values() for n in nb}
    span: dict[str, list[float]] = {}  # rid -> [first_seen, last_seen/finished]
    files = sorted(Path(args.trace_dir).glob("kv-cache-*.jsonl"))
    if not files:
        sys.exit(f"no kv-cache-*.jsonl under {args.trace_dir}")
    for f in files:
        with f.open() as fh:
            for line in fh:
                if '"request_id"' not in line:
                    continue
                rec = json.loads(line)
                rid = trace_rid(rec.get("request_id") or "")
                if rid not in all_ids:
                    continue
                t = rec["time"]
                if rid in span:
                    span[rid][0] = min(span[rid][0], t)
                    span[rid][1] = max(span[rid][1], t)
                else:
                    span[rid] = [t, t]
    print(f"trace files {len(files)}; target requests found {sum(1 for t in wanted if t in span)}/{len(wanted)}; "
          f"neighbour requests found {sum(1 for n in all_ids - set(wanted) if n in span)}/{len(all_ids - set(wanted))}")

    def overlap(a: list[float], b: list[float]) -> float:
        return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

    probe_ids = set(span)
    by_cond: dict[str, list[float]] = {}
    for rid, (pid, cond, pass_no, nb) in wanted.items():
        if rid not in span:
            continue
        tgt = span[rid]
        dur = tgt[1] - tgt[0]
        if cond == "alone" or not nb:
            others = sum(1 for o in probe_ids if o != rid and overlap(span[o], tgt) > 0)
            by_cond.setdefault(cond, []).append(float(others > 0))
            continue
        if dur <= 0:
            continue
        # both resident: intersect the neighbour intervals, then overlap with the target
        lo = max(span[n][0] for n in nb if n in span) if all(n in span for n in nb) else None
        hi = min(span[n][1] for n in nb if n in span) if all(n in span for n in nb) else None
        frac = overlap([lo, hi], tgt) / dur if lo is not None and hi is not None and hi > lo else 0.0
        by_cond.setdefault(cond, []).append(round(frac, 3))
    for cond, vals in by_cond.items():
        if cond == "alone":
            print(f"  {cond:6s} targets whose residency overlapped any other probe request: {sum(vals):.0f}/{len(vals)} (expect 0)")
        else:
            print(f"  {cond:6s} fraction of the target's residency with BOTH neighbours resident: mean {statistics.fmean(vals):.3f} "
                  f"min {min(vals):.3f}  (n={len(vals)})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="generate every target under every condition, twice, on the live server")
    c.add_argument("--label", required=True, help="names <out>/<label>.json (resumable)")
    c.add_argument("--api-base", default="http://localhost:8000/v1")
    c.add_argument("--cell", default=str(DEFAULT_CELL), help="cell to sample targets / neighbours from")
    c.add_argument("--n", type=int, default=40, help="targets (40 = reuse the prefix-cache probe's prompts)")
    c.add_argument("--resample", action="store_true", help="sample new targets instead of reusing the prefix-cache probe's")
    c.add_argument("--limit", type=int, default=0, help="only the first N targets (smoke test)")
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--pool-per-task", type=int, default=15)
    c.add_argument("--conditions", default=",".join(CONDITIONS))
    c.add_argument("--passes", type=int, default=2)
    c.add_argument("--max-tokens", type=int, default=512)
    c.add_argument("--neighbour-max-tokens", type=int, default=4096, help="neighbours stream with ignore_eos until the target is done; this only bounds a runaway")
    c.add_argument("--lead-s", type=float, default=0.5, help="extra wait after every neighbour has produced its first token")
    c.add_argument("--timeout", type=float, default=1800)
    c.add_argument("--allow-prefix-cache", action="store_true")
    c.set_defaults(func=cmd_collect)
    d = sub.add_parser("compare", help="summarise one collected label")
    d.add_argument("label")
    d.add_argument("--csv", help="also write per-prompt rows here")
    d.set_defaults(func=cmd_compare)
    v = sub.add_parser("verify-trace", help="confirm co-residency of target and neighbours in the server's KV ownership trace")
    v.add_argument("label")
    v.add_argument("--trace-dir", required=True, help="logs/kv-cache/<server log name>/ of the server used for collect")
    v.set_defaults(func=cmd_verify_trace)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
