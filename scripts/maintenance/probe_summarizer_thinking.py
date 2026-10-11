#!/usr/bin/env python3
"""Does turning the summarizer's thinking OFF change what SU-free gets back?

In the capped sandbox cell (qwen35b-cap4k, 2026-10-10) the summarizer took 22%
of the wall-clock, and 45/228 summary events fell back to truncation: 164
attempt rejections for "missing_marker" (the model answered without the
[COMPRESSED HISTORY SUMMARY] markers) and 61 for "truncated" (the summary
*content* alone filled the 4096-token cap). The server runs with
--reasoning-parser qwen3, so the model's thinking never reaches the validator;
whether thinking OFF changes the acceptance rate (either way) cannot be read
off the existing data. This probe answers it on real prompts: it rebuilds the
exact summary request of recorded SU-free compression events (from the run's
events.jsonl / compression_events.jsonl, the same prompt builder as the
primitive), sends each to the live server with thinking ON and OFF at the
production sampling settings (temperature 0.2, max_tokens 4096), validates
the replies with the primitive's own clean_summary_text(), and compares
acceptance, rejection reasons, reply size, hidden-reasoning size and latency.

The server should be otherwise idle (latencies are compared; one request at a
time). Each prompt is sampled --samples times per mode with seeds 0..n-1.

Usage:
  # with the sandbox server up (any prefix-caching setting; same for both modes):
  python scripts/maintenance/probe_summarizer_thinking.py collect            # ~30 prompts x 2 modes x 2 samples
  python scripts/maintenance/probe_summarizer_thinking.py compare            # summary table + rows.csv

Defaults: 30 SU-free events (accepted and rejected alike) sampled from the runs
of data/r2/swebench/p100_su_free_majority/qwen35b-cap4k/d05__b15k__adaptive-prefix3-sss,
output under data/r2/probes/summarizer_thinking/ (gitignored). --off-max-tokens
lets the OFF mode use the production override's cap (2048) instead of 4096.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import requests

WS = Path(__file__).resolve().parents[2]
if str(WS / "src") not in sys.path:
    sys.path.insert(0, str(WS / "src"))
if str(WS / "scripts/maintenance") not in sys.path:
    sys.path.insert(0, str(WS / "scripts/maintenance"))

from agentctx.compression.primitives import (  # noqa: E402
    N_PROTECTED, SU_CLOSE_MARKER, SU_OPEN_MARKER, _history_text, _su_prompt, clean_summary_text,
)
from reconstruct_context import Replay  # noqa: E402

DEFAULT_CELL = WS / "data/r2/swebench/p100_su_free_majority/qwen35b-cap4k/d05__b15k__adaptive-prefix3-sss"
DEFAULT_OUT = WS / "data/r2/probes/summarizer_thinking"
MODEL = "Qwen/Qwen3.5-35B-A3B"
SUMMARY_PRIMITIVES = {"summarization_free", "summarization", "summarization_partial"}


class _PlainModel:
    """format_message() of the litellm text-based model: a plain role/content dict."""

    @staticmethod
    def format_message(**kwargs) -> dict:
        return {"role": kwargs.get("role", "user"), "content": kwargs.get("content", "")}


def _context_before_event(replay: Replay, event_idx: int) -> list[dict]:
    for i, (kind, rec) in enumerate(replay.ops):
        if kind == "compress" and rec["event_idx"] == event_idx:
            return replay.states[i - 1][1] if i > 0 else []
    raise KeyError(event_idx)


def pick_prompts(cell: Path, n: int, seed: int) -> list[dict]:
    """n summary requests rebuilt from recorded SU(-free) compression events of the cell."""
    candidates = []
    for ev_file in sorted(cell.glob("*/*/run_*/compression_events.jsonl")):
        run_dir = ev_file.parent
        for line in ev_file.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("primitive") in SUMMARY_PRIMITIVES and rec.get("summary_outcome"):
                candidates.append((run_dir, rec["event_idx"], rec))
    if not candidates:
        sys.exit(f"no summary compression events under {cell}")
    rng = random.Random(seed)
    rng.shuffle(candidates)
    chosen = sorted(candidates[:n], key=lambda t: (str(t[0]), t[1]))
    out = []
    for run_dir, event_idx, rec in chosen:
        replay = Replay(run_dir)
        if replay.mismatches:
            print(f"  warning: {run_dir.relative_to(WS)} replay mismatches: {replay.mismatches[:2]}", file=sys.stderr)
        messages = _context_before_event(replay, event_idx)
        prompt = _su_prompt(_PlainModel(), _history_text(messages[N_PROTECTED:]), None)
        so = rec["summary_outcome"]
        rel = run_dir.relative_to(WS)
        out.append({
            "id": f"{rel.parts[-3]}/{run_dir.name}/e{event_idx}",
            "run_dir": str(rel), "event_idx": event_idx, "step": rec.get("step"),
            "primitive": rec.get("primitive"),
            "recorded": {"accepted": so.get("accepted"), "attempts": so.get("attempts"),
                         "rejections": so.get("rejections"), "fallback": so.get("fallback")},
            "chars": sum(len(m["content"]) for m in prompt),
            "messages": prompt,
        })
    return out


def query(api_base: str, messages: list[dict], *, thinking: bool, max_tokens: int,
          temperature: float, seed: int, timeout: float) -> dict:
    body = {"model": MODEL, "messages": messages, "temperature": temperature, "seed": seed,
            "max_tokens": max_tokens}
    if not thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    t0 = time.time()
    resp = requests.post(f"{api_base}/chat/completions", json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    usage = data.get("usage") or {}
    content = choice["message"].get("content") or ""
    # vLLM 0.17 returns the parsed reasoning under "reasoning"; older builds used "reasoning_content".
    reasoning = choice["message"].get("reasoning") or choice["message"].get("reasoning_content") or ""
    text, flags = clean_summary_text(content, SU_OPEN_MARKER, SU_CLOSE_MARKER,
                                     finish_reason=choice.get("finish_reason"))
    return {
        "latency_s": round(time.time() - t0, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "reasoning_chars": len(reasoning),
        "content_chars": len(content),
        "accepted": text is not None,
        "rejected": flags.get("rejected"),
        "had_open_marker": flags.get("had_open_marker"),
        "had_close_marker": flags.get("had_close_marker"),
        "summary_chars": len(text) if text is not None else None,
        "content": content,
        "reasoning": reasoning,
    }


def cmd_collect(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prompts_file = out / "prompts.json"
    if prompts_file.exists():
        prompts = json.loads(prompts_file.read_text())
        print(f"reusing {len(prompts)} prompts from {prompts_file}")
    else:
        prompts = pick_prompts(Path(args.cell), args.n, args.seed)
        prompts_file.write_text(json.dumps(prompts, indent=1))
        print(f"wrote {len(prompts)} prompts to {prompts_file}")
    info = requests.get(f"{args.api_base}/models", timeout=30).json()
    metrics = requests.get(args.api_base.replace("/v1", "") + "/metrics", timeout=30).text
    cache_flag = next((line for line in metrics.splitlines()
                       if "vllm:cache_config_info" in line and "enable_prefix_caching" in line), "")
    print(f"server: {info['data'][0]['id']}  {cache_flag[:160]}")
    modes = {"on": args.max_tokens, "off": args.off_max_tokens or args.max_tokens}
    results_file = out / "results.json"
    results = {"server_cache_config": cache_flag, "temperature": args.temperature,
               "samples": args.samples, "max_tokens": modes, "runs": []}
    done = {}
    if results_file.exists() and not args.restart:
        results = json.loads(results_file.read_text())
        done = {r["id"]: r for r in results["runs"]}
        print(f"resuming: {len(done)} prompts already collected")
    for i, p in enumerate(prompts, 1):
        if p["id"] in done:
            continue
        row = {"id": p["id"], "recorded": p["recorded"], "prompt_chars": p["chars"], "on": [], "off": []}
        for s in range(args.samples):
            for mode in ("on", "off"):
                r = query(args.api_base, p["messages"], thinking=(mode == "on"), max_tokens=modes[mode],
                          temperature=args.temperature, seed=s, timeout=args.timeout)
                row[mode].append(r)
                print(f"[{i:3d}/{len(prompts)}] {p['id']:48s} {mode:3s} s{s} prompt={r['prompt_tokens']} "
                      f"gen={r['completion_tokens']:5d} reason={r['reasoning_chars']:6d}ch content={r['content_chars']:6d}ch "
                      f"{'ACCEPT' if r['accepted'] else 'reject:' + str(r['rejected']):22s} {r['latency_s']:6.1f}s", flush=True)
        results["runs"].append(row)
        results_file.write_text(json.dumps(results))
    print(f"wrote {results_file}")
    return 0


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float("nan")


def cmd_compare(args) -> int:
    out = Path(args.out)
    results = json.loads((out / "results.json").read_text())
    runs = results["runs"]
    print(f"server: {results['server_cache_config'][:120]}")
    print(f"prompts: {len(runs)}  samples/mode: {results['samples']}  temperature {results['temperature']}  "
          f"max_tokens on/off {results['max_tokens']['on']}/{results['max_tokens']['off']}")
    rec = Counter("accepted" if r["recorded"]["accepted"] else "fallback" for r in runs)
    print(f"recorded outcome of these events in the cell: {dict(rec)}\n")
    header = f"{'':34s}{'thinking ON':>16s}{'thinking OFF':>16s}"
    print(header)
    rows = {}
    for mode in ("on", "off"):
        att = [a for r in runs for a in r[mode]]
        rows.setdefault("attempts", []).append(len(att))
        rows.setdefault("accepted (per attempt)", []).append(f"{sum(a['accepted'] for a in att)}/{len(att)}")
        rows.setdefault("prompts with >=1 accept", []).append(f"{sum(any(a['accepted'] for a in r[mode]) for r in runs)}/{len(runs)}")
        rej = Counter(a["rejected"] for a in att if not a["accepted"])
        for reason in ("missing_marker", "truncated", "missing_close_marker", "empty_body", "ambiguous_reasoning"):
            rows.setdefault(f"  rejected: {reason}", []).append(rej.get(reason, 0))
        rows.setdefault("median latency (s)", []).append(f"{_med([a['latency_s'] for a in att]):.1f}")
        rows.setdefault("median completion tokens", []).append(f"{_med([a['completion_tokens'] for a in att]):.0f}")
        rows.setdefault("median reasoning chars", []).append(f"{_med([a['reasoning_chars'] for a in att]):.0f}")
        rows.setdefault("median content chars", []).append(f"{_med([a['content_chars'] for a in att]):.0f}")
        rows.setdefault("median accepted summary chars", []).append(f"{_med([a['summary_chars'] for a in att if a['accepted']]):.0f}")
        rows.setdefault("attempts > 2048 completion tokens", []).append(sum((a['completion_tokens'] or 0) > 2048 for a in att))
        rows.setdefault("attempts with content > 8000 chars", []).append(sum(a['content_chars'] > 8000 for a in att))
    for name, vals in rows.items():
        print(f"{name:34s}{str(vals[0]):>16s}{str(vals[1]):>16s}")
    # paired view: per prompt, accepted count ON vs OFF
    better = worse = same = 0
    for r in runs:
        a_on = sum(a["accepted"] for a in r["on"]); a_off = sum(a["accepted"] for a in r["off"])
        if a_off > a_on: better += 1
        elif a_off < a_on: worse += 1
        else: same += 1
    print(f"\nper prompt, accepts OFF vs ON: OFF better {better}, same {same}, ON better {worse}")
    print("Reading: thinking OFF helps if the accepted rate (esp. missing_marker) does not drop and latency falls;\n"
          "'attempts > 2048 completion tokens' in the OFF column is what the production override's\n"
          "max_tokens 2048 would cut (with thinking off, completion tokens are content tokens).")
    csv_path = Path(args.csv) if args.csv else out / "rows.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "recorded_accepted", "mode", "sample", "accepted", "rejected", "finish_reason",
                    "prompt_tokens", "completion_tokens", "reasoning_chars", "content_chars", "summary_chars", "latency_s"])
        for r in runs:
            for mode in ("on", "off"):
                for s, a in enumerate(r[mode]):
                    w.writerow([r["id"], r["recorded"]["accepted"], mode, s, a["accepted"], a["rejected"], a["finish_reason"],
                                a["prompt_tokens"], a["completion_tokens"], a["reasoning_chars"], a["content_chars"],
                                a["summary_chars"], a["latency_s"]])
    print(f"per-attempt rows written to {csv_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="rebuild summary prompts and query the server with thinking ON and OFF")
    c.add_argument("--cell", default=str(DEFAULT_CELL))
    c.add_argument("--out", default=str(DEFAULT_OUT))
    c.add_argument("--api-base", default="http://localhost:8000/v1")
    c.add_argument("--n", type=int, default=30, help="number of summary events to replay")
    c.add_argument("--seed", type=int, default=0, help="event selection seed")
    c.add_argument("--samples", type=int, default=2, help="samples per prompt per mode (seeds 0..n-1)")
    c.add_argument("--temperature", type=float, default=0.2, help="production summarizer temperature")
    c.add_argument("--max-tokens", type=int, default=4096, help="reply cap (thinking ON; OFF unless --off-max-tokens)")
    c.add_argument("--off-max-tokens", type=int, default=None, help="reply cap for thinking OFF (e.g. 2048, the override's)")
    c.add_argument("--timeout", type=float, default=900.0)
    c.add_argument("--restart", action="store_true", help="discard a partial results.json instead of resuming")
    c.set_defaults(fn=cmd_collect)
    k = sub.add_parser("compare", help="summarize results.json")
    k.add_argument("--out", default=str(DEFAULT_OUT))
    k.add_argument("--csv", default=None)
    k.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
