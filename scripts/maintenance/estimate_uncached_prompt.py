#!/usr/bin/env python3
"""Estimate the UNCACHED agent prompt tokens of a run under vLLM prefix caching.

The served vLLM did not report `prompt_tokens_details.cached_tokens` for the
Devstral fc25 cells (`cache_usage_status: unavailable` in token_log.json), so
the uncached share of every agent call is reconstructed from the event log:

  * the context of call k is replayed from events.jsonl / compression_events.jsonl
    (`reconstruct_context.Replay`), one message list per call;
  * a prefix cache is simulated at message granularity: the cached prefix of
    call k is the longest common message prefix (role + content identical)
    with ANY earlier call of the same run (the isolated driver starts a fresh
    server per run, so the cache holds only this run's prompts; LRU eviction is
    ignored, which makes the cached share an upper bound and the uncached share
    a lower bound), rounded down to whole 16-token blocks as vLLM does;
  * token counts are cl100k (`count_tokens`); the uncached fraction of the
    replayed context is applied to the served `step_prompt_tokens` of that
    call, so the totals are in served tokens.

A `--match prev` variant matches against the previous call only (the
stricter cache model). Both are written per call.

Usage (defaults = the Devstral-24B fc25 OCSA cell vs its FC cell):
  venv/bin/python scripts/maintenance/estimate_uncached_prompt.py
  venv/bin/python scripts/maintenance/estimate_uncached_prompt.py --no-plot

Outputs under --out (default data/r2/probes/uncached_prompt_estimate/):
  per_call.csv   one row per agent call (run, call, served prompt, cached/uncached est.)
  per_run.csv    one row per run
  per_task.csv   per-task means of both cells and their ratio
  uncached_input_tokens.png  the figure (grouped bars + ratio panel)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "scripts" / "maintenance"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from agentctx.compression.primitives import count_tokens  # noqa: E402
from reconstruct_context import Replay  # noqa: E402

P30S = ROOT / "data/r2/swebench/p30s"
DEFAULT_A = P30S / "devstral24b-iso-fc20-dsflash/di__binf__ocsa"
DEFAULT_B = P30S / "devstral24b-iso-fc20/di__binf__fc"
DEFAULT_OUT = ROOT / "data/r2/probes/uncached_prompt_estimate"
BLOCK = 16

_tok_cache: dict[str, int] = {}


def msg_key_tokens(m: dict) -> tuple[str, int]:
    content = m.get("content") or ""
    if isinstance(content, list):
        content = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    key = hashlib.sha1((m.get("role", "") + "\x00" + str(content)).encode()).hexdigest()
    if key not in _tok_cache:
        _tok_cache[key] = count_tokens([m])
    return key, _tok_cache[key]


def contexts_by_call(rp: Replay) -> dict[int, list[dict]]:
    """Context (message list) the model received for each call, keyed by call number."""
    out: dict[int, list[dict]] = {}
    for i, (kind, rec) in enumerate(rp.ops):
        if kind == "add" and rec["step"] >= 1 and rec["step"] not in out:
            out[rec["step"]] = rp.states[i - 1][1] if i > 0 else []
    return out


class PrefixTrie:
    """Message-level trie of every earlier prompt; node value = cumulative tokens."""

    def __init__(self):
        self.root: dict = {}

    def longest_prefix_tokens(self, seq: list[tuple[str, int]]) -> int:
        node, matched = self.root, 0
        for key, ntok in seq:
            nxt = node.get(key)
            if nxt is None:
                break
            matched += ntok
            node = nxt
        return matched

    def insert(self, seq: list[tuple[str, int]]) -> None:
        node = self.root
        for key, _ in seq:
            node = node.setdefault(key, {})


def served_steps(run_dir: Path, results_rows: list[dict] | None, run_num: int, instance: str) -> list[int] | None:
    tl = run_dir / "token_log.json"
    if tl.is_file():
        return json.loads(tl.read_text())["step_prompt_tokens"]
    if results_rows is not None:
        for r in results_rows:
            if r["instance_id"] == instance and r["run_num"] == run_num:
                return r["step_prompt_tokens"]
    return None


def analyse_run(run_dir: Path, served: list[int], match: str) -> list[dict]:
    rp = Replay(run_dir)
    ctxs = contexts_by_call(rp)
    trie = PrefixTrie()
    prev_seq: list[tuple[str, int]] = []
    rows = []
    n_calls = len(served)
    for k in range(1, n_calls + 1):
        ctx = ctxs.get(k)
        if ctx is None:
            rows.append({"call": k, "served_prompt": served[k - 1], "replay_tokens": None,
                         "matched_any": None, "matched_prev": None, "status": "no_record"})
            continue
        seq = [msg_key_tokens(m) for m in ctx]
        total = sum(t for _, t in seq)
        m_any = trie.longest_prefix_tokens(seq)
        # previous-call-only match
        m_prev = 0
        for (ka, ta), (kb, _) in zip(seq, prev_seq):
            if ka != kb:
                break
            m_prev += ta
        # whole blocks only; a prompt cannot be cached beyond its own length
        m_any = min(m_any // BLOCK * BLOCK, total)
        m_prev = min(m_prev // BLOCK * BLOCK, total)
        trie.insert(seq)
        prev_seq = seq
        rows.append({"call": k, "served_prompt": served[k - 1], "replay_tokens": total,
                     "matched_any": m_any, "matched_prev": m_prev, "status": "ok"})
    for r in rows:
        if r["status"] != "ok" or not r["replay_tokens"]:
            r["cached_any"] = r["cached_prev"] = 0
            r["uncached_any"] = r["uncached_prev"] = r["served_prompt"]
            continue
        scale = r["served_prompt"] / r["replay_tokens"]
        r["cached_any"] = r["matched_any"] * scale
        r["cached_prev"] = r["matched_prev"] * scale
        r["uncached_any"] = r["served_prompt"] - r["cached_any"]
        r["uncached_prev"] = r["served_prompt"] - r["cached_prev"]
    return rows


def collect_cell(cell: Path, label: str, match: str) -> tuple[list[dict], list[dict]]:
    rows_run, rows_call = [], []
    res_file = cell / "experiment_results.json"
    results = json.loads(res_file.read_text()) if res_file.is_file() else None
    for tl_or_ev in sorted(cell.glob("*/*/run_*/events.jsonl")):
        run_dir = tl_or_ev.parent
        if "invalid" in run_dir.parts:
            continue
        instance = run_dir.parts[-3]
        run_num = int(run_dir.name.split("_")[1])
        served = served_steps(run_dir, results, run_num, instance)
        if served is None:
            print(f"  skip {run_dir}: no served step_prompt_tokens", file=sys.stderr)
            continue
        calls = analyse_run(run_dir, served, match)
        for c in calls:
            rows_call.append({"cell": label, "instance_id": instance, "run": run_num, **c})
        agg = {
            "cell": label, "instance_id": instance, "run": run_num, "n_calls": len(calls),
            "prompt_tokens": sum(c["served_prompt"] for c in calls),
            "uncached_any": sum(c["uncached_any"] for c in calls),
            "uncached_prev": sum(c["uncached_prev"] for c in calls),
            "no_record_calls": sum(1 for c in calls if c["status"] != "ok"),
        }
        agg["cached_share_any"] = 1 - agg["uncached_any"] / agg["prompt_tokens"] if agg["prompt_tokens"] else None
        rows_run.append(agg)
        print(f"  {label} {instance} r{run_num}: calls {agg['n_calls']}, prompt {agg['prompt_tokens']/1e6:.2f}M, "
              f"uncached(any) {agg['uncached_any']/1e6:.2f}M ({100*(1-agg['cached_share_any']):.0f}%)", file=sys.stderr)
    return rows_run, rows_call


def per_task(rows_run: list[dict], a: str, b: str, field: str) -> list[dict]:
    tasks = sorted({r["instance_id"] for r in rows_run if r["cell"] == a})
    out = []
    for t in tasks:
        ra = [r for r in rows_run if r["cell"] == a and r["instance_id"] == t]
        rb = [r for r in rows_run if r["cell"] == b and r["instance_id"] == t]
        if not rb:
            continue
        ma, mb = st.mean(r[field] for r in ra), st.mean(r[field] for r in rb)
        out.append({"instance_id": t, f"{a}_runs": len(ra), f"{b}_runs": len(rb),
                    f"{a}_{field}": ma, f"{b}_{field}": mb, "ratio": ma / mb if mb else None,
                    f"{a}_prompt": st.mean(r["prompt_tokens"] for r in ra),
                    f"{b}_prompt": st.mean(r["prompt_tokens"] for r in rb)})
    return out


def short(t: str) -> str:
    repo, num = t.split("__")[1].rsplit("-", 1)
    return f"{repo.replace('scikit-learn', 'sklearn')}-{num}"


def plot(tasks: list[dict], a: str, b: str, field: str, out: Path, label_a: str, label_b: str,
         title: str, subtitle: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    tasks = sorted(tasks, key=lambda r: r["ratio"])
    n = len(tasks)
    names = [short(r["instance_id"]) for r in tasks]
    va = np.array([r[f"{a}_{field}"] for r in tasks]) / 1e6
    vb = np.array([r[f"{b}_{field}"] for r in tasks]) / 1e6
    ratio = np.array([r["ratio"] for r in tasks])
    col_a, col_b, ink, muted = "#E8641B", "#C9C7BC", "#1F1F1F", "#6B6B6B"

    fig, (ax, axr) = plt.subplots(1, 2, figsize=(10.5, 7.2), gridspec_kw={"width_ratios": [2.6, 1.0], "wspace": 0.08})
    y = np.arange(n)
    h = 0.38
    ax.barh(y - h / 2, va, h, color=col_a, label=label_a)
    ax.barh(y + h / 2, vb, h, color=col_b, label=label_b)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Uncached input tokens per run (millions)", color=muted)
    ax.set_xlim(0, max(va.max(), vb.max()) * 1.06)
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD"); ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(axis="x", colors=muted)
    ax.grid(axis="x", color="#EEEEEE", lw=0.8); ax.set_axisbelow(True)

    lo, hi = 10 ** np.floor(np.log10(ratio.min())), 10 ** np.ceil(np.log10(ratio.max()))
    axr.set_xscale("log")
    for yi, r in zip(y, ratio):
        c = col_a if r < 1 else col_b
        left, width = (r, 1 - r) if r < 1 else (1.0, r - 1)
        axr.barh(yi, width, h * 1.6, left=left, color=c)
        txt = f"{r:.2f}×"
        if r < 1:
            axr.text(r / 1.08, yi, txt, ha="right", va="center", fontsize=8, color=ink)
        else:
            axr.text(r * 1.08, yi, txt, ha="left", va="center", fontsize=8, color=ink)
    axr.axvline(1.0, color=ink, lw=1.2)
    axr.set_yticks(y); axr.set_yticklabels([]); axr.invert_yaxis()
    ticks = [t for t in (0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50) if lo / 1.5 <= t <= hi * 1.5]
    axr.set_xticks(ticks); axr.set_xticklabels([f"{t:g}×" for t in ticks], fontsize=8, color=muted)
    axr.set_xlim(min(ratio.min(), 1) / 2.2, max(ratio.max(), 1) * 2.2)
    axr.set_xlabel(f"{label_a.split(' (')[0]} / {label_b}", color=muted)
    for s in ("top", "right", "left"):
        axr.spines[s].set_visible(False)
    axr.spines["bottom"].set_color("#DDDDDD")
    axr.tick_params(axis="y", length=0)
    lower = int((ratio < 1).sum())
    med = float(np.median(ratio))
    word = "lower" if lower >= n / 2 else "higher"
    cnt = lower if word == "lower" else n - lower
    box = f"{label_a} {word}\nin {cnt} of {n} tasks\nmedian {med:.2f}×"
    # the top rows (smallest ratios) leave the right of the left panel empty
    ax.text(0.97, 0.97, box, transform=ax.transAxes, ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#DDDDDD"))

    fig.suptitle(title, x=0.01, y=0.985, ha="left", fontsize=14, fontweight="bold", color=ink)
    fig.text(0.01, 0.935, subtitle, ha="left", va="top", fontsize=9.5, color=muted, linespacing=1.4)
    fig.subplots_adjust(top=0.875, bottom=0.08, left=0.13, right=0.98)
    fig.savefig(out, dpi=160)
    print(f"wrote {out}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell-a", type=Path, default=DEFAULT_A, help="compressed cell (orange)")
    ap.add_argument("--cell-b", type=Path, default=DEFAULT_B, help="reference cell (grey)")
    ap.add_argument("--label-a", default="OCSA (DeepSeek select)")
    ap.add_argument("--label-b", default="Full context")
    ap.add_argument("--match", choices=["any", "prev"], default="any",
                    help="cache model used for the figure: any earlier call (default) or previous call only")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    ra, ca = collect_cell(args.cell_a, "a", args.match)
    rb, cb = collect_cell(args.cell_b, "b", args.match)
    field = f"uncached_{args.match}"
    tasks = per_task(ra + rb, "a", "b", field)

    def dump(name, rows):
        if not rows:
            return
        with (args.out / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    dump("per_call.csv", ca + cb)
    dump("per_run.csv", ra + rb)
    dump("per_task.csv", tasks)

    for lab, rows in (("a", ra), ("b", rb)):
        tot_p = sum(r["prompt_tokens"] for r in rows); tot_u = sum(r[field] for r in rows)
        print(f"{lab}: runs {len(rows)}, prompt {tot_p/1e6:.1f}M, uncached({args.match}) {tot_u/1e6:.1f}M "
              f"= {100*tot_u/tot_p:.1f}% of input; per-run median uncached "
              f"{st.median(r[field] for r in rows)/1e6:.2f}M", file=sys.stderr)
    ratios = [t["ratio"] for t in tasks]
    print(f"per-task ratio a/b: median {st.median(ratios):.2f}, a lower in {sum(r < 1 for r in ratios)}/{len(ratios)}",
          file=sys.stderr)

    if not args.no_plot:
        na = sorted({t["a_runs"] for t in tasks}); nb = sorted({t["b_runs"] for t in tasks})
        plot(tasks, "a", "b", field, args.out / "uncached_input_tokens.png", args.label_a, args.label_b,
             title="Rebuilding the context every step leaves most input tokens uncached"
             if st.median(ratios) > 1 else "Uncached input tokens",
             subtitle=f"SWE-bench Verified, {len(tasks)} tasks, mean per task ({args.label_b}: {'/'.join(map(str, nb))} runs, "
                      f"{args.label_a}: {'/'.join(map(str, na))} runs)\nPrefix-cache estimate: tokens beyond the longest common prefix "
                      f"with {'any earlier' if args.match == 'any' else 'the previous'} prompt of the same run (16-token blocks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
