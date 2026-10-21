#!/usr/bin/env python3
"""KV-cache occupancy over time for one task under several server regimes.

One panel per regime, stacked vertically. Within a panel the runs of the
task are laid out left to right in run order, and run k starts at the same
dashed line in every panel. Two layouts (``--layout``):

* ``per-run`` (default): every run fills one slot of equal width, i.e. the
  time inside a run is normalised to that run's own length (the length is
  printed above the slot). Panels do not share a time scale.
* ``shared-time``: real elapsed seconds inside a run; slot k is as wide as the
  longest run k across the regimes and the gap between runs (server restart,
  eval, container purge) is removed, so both panels share one time axis.

The solid line is the KV pool occupied by this run's live requests, taken
from the per-request ownership trace written by TracingScheduler
(``logs/kv-cache/<server log name>/kv-cache-*.jsonl``; see
src/agentctx/KV_CACHE_TRACE.md). Requests are matched to the run through the
response ids in token_log.json (agent steps and summarizer calls). Blocks are
converted to GiB across all tensor-parallel shards. Hollow markers are the
10-second ``/metrics`` samples from resource_log.jsonl (kv_cache_usage_pct of
the pool, converted with the pool size from serving_info.json), which are
machine-wide and serve as a cross-check; off by default, ``--metrics-samples``
draws them. ``--warm-cache-estimate`` overlays a dashed *estimate* of the KV
written to the pool since the server started (token counts, eviction ignored);
``--pool-trace`` overlays the *measured* counterpart from the tracer's pool
records (``type: pool``, servers started after 2026-10-21): blocks carrying a
prefix hash, owned by a live request or free, i.e. the warm prefix cache,
server-wide.

Usage:
  venv/bin/python scripts/maintenance/plot_kv_timeline.py \
      --task scikit-learn__scikit-learn-11578 \
      --regime "Isolated (fresh server per run)=data/r2/swebench/p30s/devstral2507-iso/di__b15k__su-free" \
      --regime "Persistent server=data/r2/swebench/p30s/devstral2507-serial/di__b15k__su-free" \
      --out plots/kv_timeline_sklearn11578.png
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import glob
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACE_ROOT = os.path.join(ROOT, "logs", "kv-cache")

# Categorical slots from the dataviz reference palette (light surface).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def local_ts(s: str) -> float:
    """resource_log timestamps are naive local time on the serving machine."""
    return dt.datetime.fromisoformat(s).timestamp()


def run_dirs(cell_dir: str, task: str) -> list[tuple[int, str]]:
    out = []
    for d in glob.glob(os.path.join(cell_dir, task, "*", "run_*")):
        m = re.search(r"run_(\d+)$", d)
        if m and os.path.exists(os.path.join(d, "token_log.json")):
            out.append((int(m.group(1)), d))
    return sorted(out)


def run_response_ids(run_dir: str) -> tuple[set[str], set[str]]:
    """(all response ids of the run, the subset that were summarizer calls)."""
    tl = json.load(open(os.path.join(run_dir, "token_log.json")))
    ids = {r["response_id"] for r in tl.get("model_call_records", []) if r.get("response_id")}
    summ = set()
    for o in tl.get("summary_outcomes", []):
        summ.update(i for i in o.get("response_ids", []) if i)
    return ids | summ, summ


def run_server_trace(run_dir: str, server_prefix: str) -> tuple[str, int]:
    """Trace directory of the agent server this run talked to, plus pool size in blocks."""
    si = json.load(open(os.path.join(run_dir, "serving_info.json")))
    log_name, pool_tokens, block_size = None, None, 16
    for s in si.get("server_logs", []):
        if s.get("server") == server_prefix:
            log_name = s["log"]
            for line in s.get("lines", []):
                m = re.search(r"GPU KV cache size: ([\d,]+) tokens", line)
                if m:
                    pool_tokens = int(m.group(1).replace(",", ""))
    for ep in si.get("endpoints", {}).values():
        bs = (ep.get("info_metrics", {}).get("vllm:cache_config_info", {}) or {}).get("block_size")
        if bs:
            block_size = int(bs)
    if log_name is None:
        raise SystemExit(f"{run_dir}: no server log named {server_prefix}* in serving_info.json")
    trace_dir = os.path.join(TRACE_ROOT, log_name[:-len(".log")])
    if not os.path.isdir(trace_dir):
        raise SystemExit(f"{run_dir}: trace dir {trace_dir} not found")
    pool_blocks = pool_tokens // block_size if pool_tokens else None
    return trace_dir, pool_blocks, block_size


_trace_cache: dict[str, tuple[dict, list[dict], list[dict]]] = {}


def load_trace(trace_dir: str) -> tuple[dict, list[dict], list[dict]]:
    """(metadata, per-request records, pool-wide records), each sorted by time."""
    if trace_dir in _trace_cache:
        return _trace_cache[trace_dir]
    meta, recs, pool = None, [], []
    for f in sorted(glob.glob(os.path.join(trace_dir, "kv-cache-*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            if r["type"] == "metadata":
                meta = r
            elif r["type"] == "pool":
                pool.append(r)
            elif "request_id" in r:
                recs.append(r)
    recs.sort(key=lambda r: (r["time"], r.get("tick", 0)))
    pool.sort(key=lambda r: (r["time"], r.get("tick", 0)))
    _trace_cache[trace_dir] = (meta, recs, pool)
    return _trace_cache[trace_dir]


def base_id(request_id: str) -> str:
    # vLLM appends an internal "-<8 hex>" suffix to the API response id.
    return re.sub(r"-[0-9a-f]{8}$", "", request_id)


def occupancy_series(recs, ids, t0, t1, bytes_per_block_gpu):
    """Step series (t, GiB) of blocks held by the run's live requests."""
    live: dict[str, int] = {}
    foreign = set()
    pts = []
    for r in recs:
        t = r["time"]
        if t < t0 - 60 or t > t1 + 60:
            continue
        rid = r["request_id"]
        if base_id(rid) not in ids:
            foreign.add(rid)
            continue
        if r["type"] == "snapshot":
            live[rid] = r["total_blocks"]
        elif r["type"] == "finished":
            live.pop(rid, None)
        pts.append((t, sum(live.values()) * bytes_per_block_gpu / 2**30))
    return pts, foreign


def load_regime(label, cell_dir, task, server_prefix):
    runs = []
    for k, d in run_dirs(cell_dir, task):
        rows = [json.loads(l) for l in open(os.path.join(d, "resource_log.jsonl"))]
        t0, t1 = local_ts(rows[0]["t"]), local_ts(rows[-1]["t"])
        trace_dir, pool_blocks, block_size = run_server_trace(d, server_prefix)
        meta, recs, pool_recs = load_trace(trace_dir)
        bpb_gpu = meta["bytes_per_block_per_worker"] * meta["tensor_parallel_size"]
        # Measured warm cache: blocks with a prefix hash (owned or free), server-wide. Carry the last
        # value from before the run in so the line starts at the run's left edge.
        pool_pts = []
        before = [r for r in pool_recs if r["time"] < t0]
        if before:
            pool_pts.append((t0, before[-1]["hashed_blocks"] * bpb_gpu / 2**30))
        pool_pts += [(r["time"], r["hashed_blocks"] * bpb_gpu / 2**30)
                     for r in pool_recs if t0 <= r["time"] <= t1 + 60]
        tp_size = meta["tensor_parallel_size"]
        ids, summ_ids = run_response_ids(d)
        pts, foreign = occupancy_series(recs, ids, t0, t1, bpb_gpu)
        # Per agent step: (trace start time, prompt tokens, cached tokens) for --series cache.
        first_t = {}
        for r in recs:
            b = base_id(r["request_id"])
            if b in ids and t0 - 60 <= r["time"] <= t1 + 60 and b not in first_t:
                first_t[b] = r["time"]
        tl = json.load(open(os.path.join(d, "token_log.json")))
        steps = [(first_t[r["response_id"]], r.get("prompt_tokens") or 0, r.get("cached_tokens") or 0)
                 for r in tl.get("model_call_records", []) if r.get("response_id") in first_t]
        calls = [(first_t[r["response_id"]], r.get("prompt_tokens") or 0, r.get("cached_tokens") or 0,
                  r.get("completion_tokens") or 0)
                 for r in tl.get("model_call_records", []) if r.get("response_id") in first_t]
        comp_steps = list(tl.get("compression_event_steps", []) or [])
        # Summarizer requests: (first snapshot, finished) spans, drawn as bands.
        spans = {}
        for r in recs:
            b = base_id(r["request_id"])
            if b in summ_ids and t0 - 60 <= r["time"] <= t1 + 60:
                lo, hi = spans.get(b, (r["time"], r["time"]))
                spans[b] = (min(lo, r["time"]), max(hi, r["time"]))
        matched = {base_id(r["request_id"]) for r in recs if t0 - 60 <= r["time"] <= t1 + 60} & ids
        # Summarizer calls (summary_attempts.jsonl) as (first snapshot, prompt, cached, completion); cached is
        # None in the attempt log so far and the pool records show no prefix hit for these requests.
        summ_calls = []
        sa = os.path.join(d, "summary_attempts.jsonl")
        if os.path.exists(sa):
            for line in open(sa):
                a = json.loads(line)
                rid = a.get("response_id")
                if rid in spans:
                    summ_calls.append((spans[rid][0], a.get("prompt_tokens") or 0, a.get("cached_tokens") or 0,
                                       a.get("completion_tokens") or 0))
        samples = []
        for row in rows:
            v = next(iter(row.get("vllm", {}).values()), {}).get("kv_cache_usage_pct")
            if v is not None and pool_blocks:
                samples.append((local_ts(row["t"]), v / 100 * pool_blocks * bpb_gpu / 2**30))
        runs.append(dict(k=k, dir=d, t0=t0, t1=t1, pts=pts, samples=samples, summ_spans=list(spans.values()),
                         steps=steps, calls=calls, summ_calls=summ_calls, trace_dir=trace_dir,
                         bpb_gpu=bpb_gpu, tp=tp_size, block_size=block_size, comp_steps=comp_steps,
                         n_ids=len(ids), n_matched=len(matched), foreign=len(foreign),
                         pool_pts=pool_pts, peak=max((g for _, g in pts), default=0.0)))
    resolved = {}
    er = os.path.join(cell_dir, "experiment_results.json")
    if os.path.exists(er):
        for i, row in enumerate(r for r in json.load(open(er)) if r.get("instance_id") == task):
            resolved[row.get("run_num", i + 1)] = row.get("resolved")
    return dict(label=label, cell=cell_dir, runs=runs, resolved=resolved)


# ── prompt divergence between consecutive runs (--divergence) ──────────────────────────────

def load_tokenizer(path):
    """Devstral's tekken tokenizer (mistral_common). `path` is tekken.json; None → newest HF-cache snapshot."""
    if path is None:
        cands = sorted(glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--mistralai--Devstral-Small-2507/snapshots/*/tekken.json")),
            key=os.path.getmtime)
        if not cands:
            sys.exit("no tekken.json in the HF cache; pass --tokenizer")
        path = cands[-1]
    from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
    enc = MistralTokenizer.from_file(path).instruct_tokenizer.tokenizer
    return lambda text: enc.encode(text, bos=False, eos=False)


def _last_launch(events):
    """events.jsonl of a run launched twice into the same dir holds both launches; keep the last."""
    start = 0
    for i, e in enumerate(events):
        if e["seq"] == 1:
            start = i
    return events[start:]


def prompts_per_step(run_dir):
    """Replay events.jsonl + compression_events.jsonl: list indexed by call k-1 of the message list
    the model received for call k (same logic as scripts/maintenance/reconstruct_context.py)."""
    def load(name):
        path = os.path.join(run_dir, name)
        return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []
    events = _last_launch(load("events.jsonl"))
    comps, seen = [], set()
    for c in load("compression_events.jsonl"):
        key = (c["seq"], c.get("event_idx"))
        if key not in seen:            # duplicated launch → duplicated records
            seen.add(key)
            comps.append(c)
    uid = lambda m: (m.get("extra") or {}).get("uid")
    ops = sorted([("add", e) for e in events] + [("compress", c) for c in comps], key=lambda t: t[1]["seq"])
    msgs, prompts = [], []
    for kind, rec in ops:
        if kind == "add":
            m = rec["message"]
            if m.get("role") == "assistant":
                prompts.append(list(msgs))      # context just before this call's reply was appended
            msgs = msgs + [m]
        else:
            by = {uid(m): m for m in msgs}
            for r in rec.get("replaced", []):
                by[r["uid"]] = {**by[r["uid"]], "content": r["new_content"]}
            for a in rec.get("added", []):
                by[a["uid"]] = a["message"]
            msgs = [by[u] for u in rec["after_uids"] if u in by]
    return prompts


class _TokCache:
    def __init__(self, encode):
        self.encode, self.cache = encode, {}

    def __call__(self, m):
        key = (m.get("role"), m.get("content") or "")
        if key not in self.cache:
            self.cache[key] = self.encode(key[1])
        return self.cache[key]


def _unmatched_tokens(a, b, exact_limit=3000):
    """Tokens of b not matched to a. Exact alignment (difflib) for short sequences, else
    common prefix + common suffix (the middle counts as different)."""
    if a == b:
        return 0
    if len(a) <= exact_limit and len(b) <= exact_limit:
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        return len(b) - sum(size for _, _, size in sm.get_matching_blocks())
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    return len(b) - i - j


def divergence_vs_previous(prev_prompts, cur_prompts, tok):
    """Per call k of the current run: (tokens of the prompt not matched to the previous run's
    prompt for the same k, prompt tokens, previous run had call k). Messages are the alignment
    units; messages a difflib opcode pairs as 'replace' are diffed token by token."""
    out = []
    for k, cur in enumerate(cur_prompts):
        n_cur = sum(len(tok(m)) for m in cur)
        if k >= len(prev_prompts):
            out.append((None, n_cur, False))
            continue
        prev = prev_prompts[k]
        pk = [(m.get("role"), m.get("content")) for m in prev]
        ck = [(m.get("role"), m.get("content")) for m in cur]
        if pk == ck:
            out.append((0, n_cur, True))
            continue
        diff = 0
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, pk, ck, autojunk=False).get_opcodes():
            if op == "equal" or op == "delete":
                continue
            if op == "insert":
                diff += sum(len(tok(m)) for m in cur[j1:j2])
                continue
            pa, cb = prev[i1:i2], cur[j1:j2]
            for x, y in zip(pa, cb):
                diff += _unmatched_tokens(tok(x), tok(y))
            for y in cb[len(pa):]:
                diff += len(tok(y))
        out.append((diff, n_cur, True))
    return out


def attach_divergence(regimes, encode):
    tok = _TokCache(encode)
    for reg in regimes:
        prev = None
        for run in reg["runs"]:
            cur = prompts_per_step(run["dir"])
            run["n_prompts"] = len(cur)
            run["divergence"] = None if prev is None else divergence_vs_previous(prev, cur, tok)
            prev = cur


def warm_cache_estimate(reg):
    """Per run: step points (time, GiB) of the estimated KV written to the server's pool since that
    server started: for every agent and summarizer call the prompt tokens vLLM did not find in the
    prefix cache plus the completion tokens. The summarizer prompt is charged in full when no
    cached_tokens were recorded: measured against the pool records on 2026-10-21 (sklearn-11578,
    Devstral), one SU event added 14,944 tokens of hashed blocks for a 14,526-token prompt + 434
    completion, i.e. the summarizer request shares no prefix with the agent context (an earlier
    version charged only the prompt beyond the agent's last prompt and undercounted ~2.2 GiB per SU).
    Cumulative across the runs that share a server (same trace dir); eviction is ignored, so this is
    an upper bound on the warm prefix cache. --pool-trace is the measured counterpart."""
    carried = {}
    for run in reg["runs"]:
        key = run["trace_dir"]
        tot = carried.get(key, 0)
        bs, bpb = run["block_size"], run["bpb_gpu"]
        events = [(t, max(p - c, 0) + comp) for t, p, c, comp in run["calls"]]
        for t, p, c, comp in run["summ_calls"]:
            events.append((t, max(p - c, 0) + comp))
        events.sort()
        pts = [(run["t0"], tot / bs * bpb / 2**30)]
        for t, new_tokens in events:
            tot += new_tokens
            pts.append((t, tot / bs * bpb / 2**30))
        pts.append((run["t1"], tot / bs * bpb / 2**30))
        carried[key] = tot
        run["warm_pts"] = pts


def prefilled_tokens(p, c, bs):
    """Tokens vLLM actually prefilled. The partial tail block is never cached and the last prompt
    token always needs a forward pass, so a prompt is never 100% cached; when every whole block hits
    on an exact block multiple vLLM recomputes the whole last block and reports miss == block_size.
    That case is drawn as 0 (nothing of the prompt body was prefilled)."""
    m = p - c
    return 0 if (m == bs and p % bs == 0) else m


def panel_title(args, reg):
    """Panel label, plus the cell directory unless --no-cell-path."""
    if args.no_cell_path:
        return reg["label"]
    return f"{reg['label']}   ({os.path.relpath(reg['cell'], ROOT)})"


def render_prefill_steps(args, regimes, n_runs):
    slot_w = [max(len(r["runs"][k]["steps"]) for r in regimes if k < len(r["runs"])) + 1 for k in range(n_runs)]
    slot_x = [0.0]
    for w in slot_w:
        slot_x.append(slot_x[-1] + w)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
                         "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                         "axes.linewidth": 0.6, "axes.edgecolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK, "axes.labelcolor": INK,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    div = bool(getattr(args, "divergence", False))
    rows = len(regimes) * (2 if div else 1)
    fig, axes = plt.subplots(rows, 1, sharex=True, sharey=not div,
                             figsize=(13, 2.9 * rows + 0.6), constrained_layout=True)
    axes = list(axes) if rows > 1 else [axes]
    pre_axes = axes[::2] if div else axes
    div_axes = axes[1::2] if div else []
    for ax in pre_axes[1:]:
        ax.sharey(pre_axes[0])
    for ax in div_axes[1:]:
        ax.sharey(div_axes[0])
    ymax = max(prefilled_tokens(p, c, run["block_size"]) for r in regimes for run in r["runs"]
               for _, p, c in run["steps"]) / 1000
    for i, (ax, reg) in enumerate(zip(pre_axes, regimes)):
        col = SERIES[i % len(SERIES)]
        for run in reg["runs"]:
            x0 = slot_x[run["k"] - 1]
            bs = run["block_size"]
            n = len(run["steps"])
            xs = [x0 + j for j in range(1, n + 1)]
            pre = [prefilled_tokens(p, c, bs) / 1000 for _, p, c in run["steps"]]
            full = [v * 1000 >= bs for v in pre]          # at least one whole block recomputed
            ax.bar([x for x, f in zip(xs, full) if f], [v for v, f in zip(pre, full) if f], width=0.8, color=col, lw=0)
            ax.bar([x for x, f in zip(xs, full) if not f], [v for v, f in zip(pre, full) if not f], width=0.8,
                   color=INK2, alpha=0.35, lw=0)
            # The run ended here: grey out the rest of the slot so a short run is not read as
            # "steps that prefilled nothing".
            if x0 + n + 0.5 < slot_x[run["k"]]:
                ax.axvspan(x0 + n + 0.5, slot_x[run["k"]], color=GRID, alpha=0.6, lw=0, zorder=0)
            for cs in run["comp_steps"]:
                xc = x0 + cs + 0.5
                ax.axvline(xc, color=INK2, lw=0.7, ls=(0, (1.5, 1.5)), ymax=0.78)
                ax.text(xc, ymax * 0.93, "SU", ha="center", va="top", fontsize=7, color=INK2)
            res = reg["resolved"].get(run["k"])
            tag = "" if res is None else (" ✓" if res else " ✗")
            n_miss = sum(full)
            ax.text(x0 + 0.6, ymax * 1.04, f"{n} steps{tag}\nprefix-cache block miss: {n_miss}/{n}", fontsize=7.5, color=INK2,
                    ha="left", va="bottom")
        for k in range(n_runs + 1):
            ax.axvline(slot_x[k], color=INK2, lw=0.7, ls=(0, (3, 3)), zorder=0)
        ax.set_title(panel_title(args, reg), loc="left", color=INK)
        ax.set_ylabel("Tokens prefilled per agent step (k)")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, ymax * 1.22)
        ax.set_xticks([slot_x[k] + slot_w[k] / 2 for k in range(n_runs)])
        ax.set_xticklabels([f"run {k + 1}" for k in range(n_runs)])
        ax.tick_params(axis="x", length=0)
    if div:
        dmax = max((n if args.divergence_outline else (d or 0) for r in regimes for run in r["runs"]
                    if run.get("divergence") for d, n, _ in run["divergence"]), default=1) / 1000
        for i, (ax, reg) in enumerate(zip(div_axes, regimes)):
            col = SERIES[i % len(SERIES)]
            for run in reg["runs"]:
                x0 = slot_x[run["k"] - 1]
                n = len(run["steps"])
                dv = run.get("divergence")
                if dv is None:                      # run 1: nothing to compare with
                    ax.axvspan(x0, slot_x[run["k"]], color=GRID, alpha=0.9, lw=0, zorder=0)
                    ax.text(x0 + 0.6, dmax * 1.04, f"{n} steps\nno previous run", fontsize=7.5, color=INK2,
                            ha="left", va="bottom")
                    continue
                xs = [x0 + j for j in range(1, len(dv) + 1)]
                if args.divergence_outline:
                    # Faint outline: the whole prompt at that step, so a bar reaching it means "entirely different".
                    ax.step([x - 0.5 for x in xs] + [xs[-1] + 0.5], [n / 1000 for _, n, _ in dv] + [dv[-1][1] / 1000],
                            where="post", color=INK2, lw=0.6, alpha=0.45)
                ax.bar([x for x, (d, _, _) in zip(xs, dv) if d], [d / 1000 for d, _, _ in dv if d],
                       width=0.8, color=col, lw=0)
                # Steps beyond the previous run's length: hatched, nothing to compare with.
                beyond = [x for x, (d, _, has) in zip(xs, dv) if not has]
                if beyond:
                    ax.axvspan(beyond[0] - 0.5, beyond[-1] + 0.5, facecolor="none", edgecolor=INK2,
                               hatch="////", lw=0, alpha=0.25, zorder=0)
                if x0 + len(dv) + 0.5 < slot_x[run["k"]]:
                    ax.axvspan(x0 + len(dv) + 0.5, slot_x[run["k"]], color=GRID, alpha=0.6, lw=0, zorder=0)
                for cs in run["comp_steps"]:
                    ax.axvline(x0 + cs + 0.5, color=INK2, lw=0.7, ls=(0, (1.5, 1.5)), ymax=0.78)
                first = next((j + 1 for j, (d, _, _) in enumerate(dv) if d), None)
                same = sum(1 for d, _, has in dv if has and d == 0)
                n_prev = sum(1 for _, _, has in dv if has)
                lab = (f"identical prompt: {same}/{n_prev} steps" +
                       (f"\nfirst differs at step {first}" if first else "\nnever differs"))
                if n_prev < len(dv):
                    lab += f"\nrun {run['k'] - 1} ended at step {n_prev}"
                ax.text(x0 + 0.6, dmax * 1.04, lab, fontsize=7.5, color=INK2, ha="left", va="bottom")
            for k in range(n_runs + 1):
                ax.axvline(slot_x[k], color=INK2, lw=0.7, ls=(0, (3, 3)), zorder=0)
            ax.set_title(f"{reg['label']} — prompt tokens differing from run k−1 at the same step",
                         loc="left", color=INK, fontsize=9)
            ax.set_ylabel("Differing prompt tokens (k)")
            ax.grid(axis="y", color=GRID, lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_ylim(0, dmax * 1.22)
            ax.set_xticks([slot_x[k] + slot_w[k] / 2 for k in range(n_runs)])
            ax.set_xticklabels([f"run {k + 1}" for k in range(n_runs)])
            ax.tick_params(axis="x", length=0)
    axes[-1].set_xlabel("Agent step within each run (one bar per model call)")
    axes[-1].set_xlim(0, slot_x[-1])
    handles = [Patch(facecolor=INK2, label="≥ 1 whole block of the prompt prefilled (prefix-cache miss)"),
               Patch(facecolor=INK2, alpha=0.35, label="every whole block hit: only the partial tail block (< 16 tokens) recomputed, invisible at this scale"),
               Line2D([], [], color=INK2, lw=0.7, ls=(0, (1.5, 1.5)), label="SU = compression event after this step")]
    if div:
        handles.append(Patch(facecolor="none", edgecolor=INK2, hatch="////", alpha=0.25,
                             label="divergence panels: previous run had already ended"))
        if args.divergence_outline:
            handles.append(Line2D([], [], color=INK2, lw=0.6, alpha=0.45, label="outline = whole prompt at that step"))
    fig.suptitle(args.title or (f"{args.task}: tokens prefilled per agent step"
                                + (" and prompt divergence from the previous run" if div else "")),
                 x=0.01, ha="left", fontsize=11)
    if not args.no_legend:
        axes[0].legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), frameon=False, fontsize=8,
                       ncol=2, borderaxespad=0.0, handlelength=1.6)
        axes[0].set_title(axes[0].get_title(loc="left"), loc="left", color=INK, pad=36)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=170)
    print(f"wrote {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--regime", action="append", required=True, metavar="LABEL=CELL_DIR",
                    help="panel label and cell directory (holding <task>/<condition>/run_N); repeatable, top to bottom")
    ap.add_argument("--server-prefix", default="vllm_devstral2507_prefixcache",
                    help="server log name prefix (serving_info.json 'server' field) of the agent model server")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-runs", type=int, default=None, help="only draw runs 1..N")
    ap.add_argument("--metrics-samples", action="store_true",
                    help="also draw the 10 s /metrics samples of resource_log.jsonl as hollow markers")
    ap.add_argument("--series", choices=["kv", "cache", "prefill-steps"], default="kv",
                    help="kv: KV blocks held by live requests; cache: per-step prompt tokens vs prefix-cache hits "
                         "(filled = tokens actually prefilled); prefill-steps: x = agent step instead of time, "
                         "bars = tokens prefilled at each step (--layout is ignored: slot k is as wide as the "
                         "longest run k in steps)")
    ap.add_argument("--layout", choices=["per-run", "shared-time"], default="per-run",
                    help="per-run: equal-width slots, time normalised per run; shared-time: real seconds, shared axis")
    ap.add_argument("--title", default=None)
    ap.add_argument("--no-cell-path", action="store_true", help="panel titles show only the label, not the cell directory")
    ap.add_argument("--no-legend", action="store_true", help="omit the legend (prefill-steps only)")
    ap.add_argument("--divergence", action="store_true",
                    help="prefill-steps only: under each regime add a panel of, per step, the tokens of the "
                         "prompt that do not match the previous run's prompt at the same step (messages "
                         "aligned with difflib, differing messages diffed token by token; run 1 greyed out)")
    ap.add_argument("--warm-cache-estimate", action="store_true",
                    help="kv series: overlay a dashed cumulative estimate of the KV written to each server's pool "
                         "(uncached prompt tokens + completions of every agent and summarizer call, summed across "
                         "the runs that share a server; eviction ignored). For servers with pool records prefer "
                         "--pool-trace, the measured value.")
    ap.add_argument("--pool-trace", action="store_true",
                    help="kv series: overlay the measured warm prefix cache from the tracer's pool records "
                         "(blocks carrying a prefix hash, owned or free; server-wide, so other clients of a "
                         "shared server count too). Servers started after 2026-10-21 only.")
    ap.add_argument("--divergence-outline", action="store_true",
                    help="with --divergence: also draw each step's whole prompt length as a faint outline")
    ap.add_argument("--tokenizer", default=None,
                    help="tekken.json for --divergence (default: Devstral-Small-2507 from the HF cache)")
    args = ap.parse_args()

    regimes = []
    for spec in args.regime:
        label, cell = spec.split("=", 1)
        regimes.append(load_regime(label, os.path.join(ROOT, cell) if not os.path.isabs(cell) else cell,
                                   args.task, args.server_prefix))

    if args.max_runs:
        for r in regimes:
            r["runs"] = [run for run in r["runs"] if run["k"] <= args.max_runs]
    n_runs = max(len(r["runs"]) for r in regimes)
    if args.series == "prefill-steps":
        if args.divergence:
            attach_divergence(regimes, load_tokenizer(args.tokenizer))
        render_prefill_steps(args, regimes, n_runs)
        return
    if args.layout == "shared-time":
        slot_w = [max((r["runs"][k]["t1"] - r["runs"][k]["t0"]) for r in regimes if k < len(r["runs"]))
                  for k in range(n_runs)]
        to_min = 1 / 60
    else:
        slot_w = [1.0] * n_runs
        to_min = 1.0
    slot_x = [0.0]
    for w in slot_w:
        slot_x.append(slot_x[-1] + w)

    def xpos(run, t):
        """Figure x of trace time t inside run (before the to_min scaling)."""
        x0 = slot_x[run["k"] - 1]
        if args.layout == "shared-time":
            return x0 + t - run["t0"]
        return x0 + (t - run["t0"]) / max(run["t1"] - run["t0"], 1e-9)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
                         "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                         "axes.linewidth": 0.6, "axes.edgecolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK, "axes.labelcolor": INK,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(len(regimes), 1, sharex=True, sharey=True,
                             figsize=(13, 2.9 * len(regimes) + 0.6), constrained_layout=True)
    axes = list(axes) if len(regimes) > 1 else [axes]
    if args.series == "cache":
        ymax = max(p for r in regimes for run in r["runs"] for _, p, _ in run["steps"]) / 1000
    else:
        ymax = max(max(max((g for _, g in run["pts"]), default=0), max((g for _, g in run["samples"]), default=0))
                   for r in regimes for run in r["runs"])
        if args.warm_cache_estimate:
            for reg in regimes:
                warm_cache_estimate(reg)
            ymax = max(ymax, max(g for r in regimes for run in r["runs"] for _, g in run["warm_pts"]))
        if args.pool_trace:
            if not any(run["pool_pts"] for r in regimes for run in r["runs"]):
                sys.exit("--pool-trace: no pool records in these traces (server started before the "
                         "tracer wrote them?)")
            ymax = max(ymax, max((g for r in regimes for run in r["runs"] for _, g in run["pool_pts"]),
                                 default=0))

    tp = max((run.get("tp", 1) for r in regimes for run in r["runs"]), default=1)
    for i, (ax, reg) in enumerate(zip(axes, regimes)):
        col = SERIES[i % len(SERIES)]
        for run in reg["runs"]:
            x0 = slot_x[run["k"] - 1]
            if args.series == "cache":
                if run["steps"]:
                    xs = [xpos(run, t) * to_min for t, _, _ in run["steps"]] + [xpos(run, run["t1"]) * to_min]
                    pr = [p / 1000 for _, p, _ in run["steps"]] + [run["steps"][-1][1] / 1000]
                    ca = [c / 1000 for _, _, c in run["steps"]] + [run["steps"][-1][2] / 1000]
                    ax.fill_between(xs, ca, pr, step="post", color=col, alpha=0.9, lw=0)
                    ax.step(xs, pr, where="post", color=col, lw=1.0)
                    ax.step(xs, ca, where="post", color=INK2, lw=0.7, ls=(0, (1.5, 1.5)))
                    # Strip below the axis: one tick per step; filled when the step prefilled anything
                    # beyond the partial tail block (miss >= block_size), hollow when it was a full hit.
                    bs = run["block_size"]
                    edges = [xpos(run, t) * to_min for t, _, _ in run["steps"]] + [xpos(run, run["t1"]) * to_min]
                    # vLLM never reports a prompt as 100% cached: when every block hits it still recomputes the
                    # last one, so a prompt that is an exact block multiple shows miss == block_size on a full
                    # hit. Treat that case as a hit.
                    flags = [(p - c) >= bs and not ((p - c) == bs and p % bs == 0) for _, p, c in run["steps"]]
                    y_lo, y_hi = -ymax * 0.105, -ymax * 0.025
                    # Background of the strip = full hit; each step that prefilled a block is painted over it,
                    # so the strip reads as a bar that is solid where prefill happened and blank where it did not.
                    ax.fill_between([edges[0], edges[-1]], y_lo, y_hi, color=GRID, lw=0, zorder=3)
                    # Explicit [start, width) segments: fill_between(where=..., step="post") would drop the
                    # last segment of every solid stretch.
                    min_w = (slot_w[run["k"] - 1] * to_min) * 0.004  # keep a 1-second step visible
                    ax.broken_barh([(edges[i], max(edges[i + 1] - edges[i], min_w)) for i, f in enumerate(flags) if f],
                                   (y_lo, y_hi - y_lo), color=col, lw=0, zorder=4)
                    run["n_miss"] = sum(flags)
            elif run["pts"]:
                xs = [xpos(run, t) * to_min for t, _ in run["pts"]]
                ys = [g for _, g in run["pts"]]
                ax.step(xs, ys, where="post", color=col, lw=1.1, solid_joinstyle="round")
                if args.warm_cache_estimate and run.get("warm_pts"):
                    ax.step([xpos(run, t) * to_min for t, _ in run["warm_pts"]], [g for _, g in run["warm_pts"]],
                            where="post", color=INK2, lw=1.0, ls=(0, (3, 2)), zorder=2)
                if args.pool_trace and run.get("pool_pts"):
                    xs_p = [xpos(run, t) * to_min for t, _ in run["pool_pts"]] + [xpos(run, run["t1"]) * to_min]
                    ys_p = [g for _, g in run["pool_pts"]] + [run["pool_pts"][-1][1]]
                    ax.step(xs_p, ys_p, where="post", color=INK, lw=1.0, ls=(0, (1, 1.5)), zorder=2)
            if run["samples"] and args.metrics_samples:
                ax.scatter([xpos(run, t) * to_min for t, _ in run["samples"]],
                           [g for _, g in run["samples"]], s=14, facecolors="none",
                           edgecolors=col, linewidths=0.7, alpha=0.75, zorder=3)
            for lo, hi in run["summ_spans"]:
                ax.axvspan(xpos(run, lo) * to_min, xpos(run, hi) * to_min, color=col, alpha=0.18, lw=0, zorder=0)
                ax.text((xpos(run, lo) + xpos(run, hi)) / 2 * to_min, ymax * 0.93, "SU", ha="center", va="top",
                        fontsize=7, color=INK2)
            res = reg["resolved"].get(run["k"])
            tag = "" if res is None else (" ✓" if res else " ✗")
            dur = (run["t1"] - run["t0"]) / 60
            if args.series == "cache" and run["steps"]:
                tag += f"\nprefix-cache block miss: {run['n_miss']}/{len(run['steps'])} steps"
            pad = 10 if args.layout == "shared-time" else 0.03
            ax.text((x0 + pad) * to_min, ymax * 1.04, f"{dur:.1f} min{tag}", fontsize=7.5, color=INK2,
                    ha="left", va="bottom")
        for k in range(n_runs + 1):
            ax.axvline(slot_x[k] * to_min, color=INK2, lw=0.7, ls=(0, (3, 3)), zorder=0)
        ax.set_title(panel_title(args, reg), loc="left", color=INK)
        if args.series == "cache":
            ax.set_ylabel("Prompt tokens per step (k)")
        else:
            ax.set_ylabel(f"KV cache (GiB, summed over {tp} GPUs)")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(-ymax * 0.12 if args.series == "cache" else 0, ymax * 1.22)
        if args.series == "cache":
            ax.axhline(0, color=INK2, lw=0.6)
            ax.set_yticks([t for t in ax.get_yticks() if t >= 0])

    top = axes[0]
    for k in (range(n_runs) if args.layout == "shared-time" else []):
        top.text((slot_x[k] + slot_w[k] / 2) * to_min, ymax * 1.16, f"run {k + 1}", ha="center", va="bottom",
                 fontsize=9, color=INK, fontweight="bold")
    if args.layout == "shared-time":
        axes[-1].set_xlabel("Elapsed agent time, minutes (gaps between runs removed; dashed = run start)")
    else:
        axes[-1].set_xlabel("Time within each run, normalised to the run's own length")
        for ax in axes:
            ax.set_xticks([(slot_x[k] + 0.5) for k in range(n_runs)])
            ax.set_xticklabels([f"run {k + 1}" for k in range(n_runs)])
            ax.tick_params(axis="x", length=0)
    axes[-1].set_xlim(0, slot_x[-1] * to_min)
    if args.series == "cache":
        handles = [Line2D([], [], color=INK2, lw=1.0, label="prompt tokens of the step"),
                   Line2D([], [], color=INK2, lw=0.7, ls=(0, (1.5, 1.5)), label="served from the prefix cache"),
                   Patch(facecolor=INK2, alpha=0.9, label="filled = actually prefilled (cache miss)"),
                   Patch(facecolor=INK2, label="bar below axis: steps that prefilled ≥ 1 whole block (16 tokens) of the prompt"),
                   Patch(facecolor=GRID, label="bar blank: every whole block hit, only the partial tail block (< 16 tokens) recomputed")]
    else:
        handles = [Line2D([], [], color=INK2, lw=1.1,
                          label="KV cache in use by the current request (one spike per step)")]
        if args.warm_cache_estimate:
            handles.append(Line2D([], [], color=INK2, lw=1.0, ls=(0, (3, 2)),
                                  label="KV cache kept in GPU memory since server start (cumulative estimate)"))
        if args.pool_trace:
            handles.append(Line2D([], [], color=INK, lw=1.0, ls=(0, (1, 1.5)),
                                  label="KV cache kept in GPU memory (measured: blocks with a prefix hash, owned or free)"))
    if args.metrics_samples and args.series == "kv":
        handles.append(Line2D([], [], marker="o", ls="none", markerfacecolor="none", markeredgecolor=INK2,
                              markersize=4, label="/metrics, 10 s samples"))
    handles.append(Patch(facecolor=INK2, alpha=0.18,
                         label="SU triggered" if args.series == "kv" else "SU = summarizer request"))
    default_title = (f"{args.task}: prefix-cache hits per step" if args.series == "cache"
                     else f"{args.task}: KV-cache occupancy per run")
    fig.suptitle(args.title or default_title, x=0.01, ha="left", fontsize=11)
    axes[0].legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), frameon=False, fontsize=8,
                   ncol=3, borderaxespad=0.0, handlelength=1.6)
    axes[0].set_title(axes[0].get_title(loc="left"), loc="left", color=INK,
                      pad=22 + (14 if len(handles) > 3 else 0))   # ncol=3: a 4th handle starts a 2nd row

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=170)
    print(f"wrote {args.out}")
    for reg in regimes:
        print(f"== {reg['label']}")
        for run in reg["runs"]:
            print(f"  run {run['k']:2d}: {(run['t1']-run['t0'])/60:5.1f} min, ids {run['n_matched']}/{run['n_ids']} matched "
                  f"in trace, foreign requests {run['foreign']}, peak {run['peak']:.2f} GiB, "
                  + (f"warm pool at end {run['pool_pts'][-1][1]:.2f} GiB, " if run["pool_pts"] else "")
                  + f"resolved={reg['resolved'].get(run['k'])}")


if __name__ == "__main__":
    main()
