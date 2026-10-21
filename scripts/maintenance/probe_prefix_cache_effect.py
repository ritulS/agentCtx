#!/usr/bin/env python3
"""Does vLLM prefix caching change what the served model generates?

Written for Qwen3.5-35B-A3B, a hybrid (mamba + attention) model for which vLLM
0.17.1 defaults prefix caching OFF (the block-wise mamba-state cache is new
code); it serves any model on the agent port (the model id is read from
/v1/models, --model overrides). This probe isolates the cache's effect from everything else that differs between
agent runs: it replays real agent prompts (message prefixes of finished
trajectories) one at a time, greedily (temperature 0, fixed seed), against a
server with caching ON and one with caching OFF, and compares the generated
token streams and logprobs. Each prompt is sent twice per server, so the
within-server repeat agreement is the noise floor (continuous batching is not
bit-reproducible even with one request at a time), and on the ON server the
second pass runs against a warm cache (usage.prompt_tokens_details.cached_tokens
confirms the hit).

The server must be otherwise idle while collecting (no agent runs): other
requests change the batch composition and with it the kernels' reduction order.

Usage:
  # 1. choose prompts once (written to <out>/prompts.json, reused by every collect)
  # 2. with the caching-OFF server up and idle:
  python scripts/maintenance/probe_prefix_cache_effect.py collect --label off
  # 3. swap to the caching-ON server (scripts/serving/start_vllm_qwen35_prefix_cache.sh), then:
  python scripts/maintenance/probe_prefix_cache_effect.py collect --label on
  # 4.
  python scripts/maintenance/probe_prefix_cache_effect.py compare off on

Defaults: 40 prompts from the infra-clean runs of the 4 sandbox tasks in the
2026-10-08 uncapped cell, 512 generated tokens, output under
data/r2/probes/prefix_cache_effect/ (gitignored).

Another model (e.g. Devstral-Small-2507, 2026-10-17): point --out at a new dir
and reuse the Qwen prompt set with --prompts-from, so both models are probed on
the same 40 agent prompts:
  python scripts/maintenance/probe_prefix_cache_effect.py \
      --out data/r2/probes/prefix_cache_effect_devstral2507 collect --label off \
      --prompts-from data/r2/probes/prefix_cache_effect/prompts.json

Two controls separate "the cache changes the computation" from "two server
processes differ numerically" (Devstral-Small-2507, 2026-10-17: a fresh OFF
server agreed with the first OFF server on only 34/40 prompts, and the ON
server with the cache reset before every request agreed with that fresh OFF
server 40/40): collect a second OFF instance (`collect --label off2` after a
server restart) and, against a caching-ON server started with
VLLM_SERVER_DEV_MODE=1, `collect --label on_cold --reset-cache`.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from pathlib import Path

import requests

WS = Path(__file__).resolve().parents[2]
DEFAULT_CELL = WS / "data/r2/swebench/p100_su_free_majority/qwen35b/d05__b15k__adaptive-prefix3-sss"
DEFAULT_OUT = WS / "data/r2/probes/prefix_cache_effect"
SANDBOX_TASKS = [
    "django__django-11299", "scikit-learn__scikit-learn-25102",
    "scikit-learn__scikit-learn-10908", "scikit-learn__scikit-learn-11310",
]
DEFAULT_MODEL = "Qwen/Qwen3.5-35B-A3B"


def pick_prompts(cell: Path, n: int, seed: int) -> list[dict]:
    """n (run, k) message prefixes ending in a user turn, from infra-clean runs."""
    tags_file = cell / "failure_tags.csv"
    if not tags_file.exists():
        sys.exit(f"{tags_file} missing: run scripts/maintenance/tag_run_failures.py {cell} first")
    clean = [
        r for r in csv.DictReader(tags_file.open())
        if r["instance_id"] in SANDBOX_TASKS
        and r["runaway"] == "False" and r["hung"] == "False" and r["timeout"] == "False"
    ]
    rng = random.Random(seed)
    candidates = []
    for r in clean:
        run_dir = cell / r["instance_id"] / r["condition"] / f"run_{r['run_num']}"
        try:
            messages = json.loads((run_dir / "trajectory.json").read_text())["messages"]
        except Exception:
            continue
        for k in range(3, len(messages) + 1):
            if messages[k - 1]["role"] == "user":
                candidates.append((str(run_dir.relative_to(WS)), k))
    rng.shuffle(candidates)
    chosen = sorted(candidates[:n])
    out = []
    for run_rel, k in chosen:
        messages = json.loads((WS / run_rel / "trajectory.json").read_text())["messages"]
        prefix = [{"role": m["role"], "content": m["content"]} for m in messages[:k]]
        out.append({"id": f"{Path(run_rel).parts[-3]}/run_{Path(run_rel).name[4:]}/k{k}",
                    "run_dir": run_rel, "k": k, "chars": sum(len(m["content"]) for m in prefix),
                    "messages": prefix})
    return out


def query(api_base: str, model: str, messages: list[dict], max_tokens: int, timeout: float) -> dict:
    t0 = time.time()
    resp = requests.post(
        f"{api_base}/chat/completions",
        json={"model": model, "messages": messages, "temperature": 0, "seed": 0,
              "max_tokens": max_tokens, "logprobs": True, "top_logprobs": 1},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    choice = body["choices"][0]
    tokens = [(t["token"], t["logprob"]) for t in ((choice.get("logprobs") or {}).get("content") or [])]
    usage = body.get("usage") or {}
    return {
        "latency_s": round(time.time() - t0, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "reasoning": choice["message"].get("reasoning_content"),
        "content": choice["message"].get("content"),
        "tokens": tokens,
    }


def cmd_collect(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prompts_file = out / "prompts.json"
    if prompts_file.exists():
        prompts = json.loads(prompts_file.read_text())
        print(f"reusing {len(prompts)} prompts from {prompts_file}")
    elif args.prompts_from:
        prompts = json.loads(Path(args.prompts_from).read_text())
        prompts_file.write_text(json.dumps(prompts, indent=1))
        print(f"copied {len(prompts)} prompts from {args.prompts_from} to {prompts_file}")
    else:
        prompts = pick_prompts(Path(args.cell), args.n, args.seed)
        prompts_file.write_text(json.dumps(prompts, indent=1))
        print(f"wrote {len(prompts)} prompts to {prompts_file}")
    info = requests.get(f"{args.api_base}/models", timeout=30).json()
    metrics = requests.get(args.api_base.replace("/v1", "") + "/metrics", timeout=30).text
    cache_flag = next((line for line in metrics.splitlines() if "vllm:cache_config_info" in line and "enable_prefix_caching" in line), "")
    served = info["data"][0]["id"]
    model = args.model or served
    if model != served:
        sys.exit(f"--model {model} but the server at {args.api_base} serves {served}")
    print(f"server: {served}  {cache_flag[:160]}")
    results = {"label": args.label, "model": served, "api_base": args.api_base,
               "server_cache_config": cache_flag, "max_tokens": args.max_tokens, "runs": []}
    reset_url = args.api_base.replace("/v1", "") + "/reset_prefix_cache"
    if args.reset_cache:
        if 'enable_prefix_caching="True"' not in cache_flag:
            sys.exit("--reset-cache only makes sense against a prefix-caching-ON server")
        requests.post(reset_url, timeout=60).raise_for_status()  # 404 = server not started with VLLM_SERVER_DEV_MODE=1
    for i, p in enumerate(prompts, 1):
        passes = []
        for pass_no in (1, 2):
            if args.reset_cache:
                requests.post(reset_url, timeout=60).raise_for_status()
                time.sleep(0.5)
            r = query(args.api_base, model, p["messages"], args.max_tokens, args.timeout)
            if args.reset_cache and r["cached_tokens"]:
                sys.exit(f"{p['id']} pass{pass_no}: {r['cached_tokens']} cached tokens despite the reset")
            passes.append(r)
            print(f"[{i:3d}/{len(prompts)}] {p['id']:60s} pass{pass_no} prompt={r['prompt_tokens']} cached={r['cached_tokens']} "
                  f"gen={r['completion_tokens']} {r['latency_s']:6.1f}s", flush=True)
        results["runs"].append({"id": p["id"], "passes": passes})
        (out / f"{args.label}.json").write_text(json.dumps(results))
    print(f"wrote {out / (args.label + '.json')}")
    return 0


def agreement(a: list, b: list) -> dict:
    """Compare two generated token streams: identical?, first divergence, logprob gap."""
    n = min(len(a), len(b))
    first_div = next((i for i in range(n) if a[i][0] != b[i][0]), None)
    if first_div is None and len(a) != len(b):
        first_div = n
    common = n if first_div is None else first_div
    lp_gap = [abs(a[i][1] - b[i][1]) for i in range(common)]
    return {"identical": first_div is None, "first_divergence": first_div,
            "common_prefix": common, "mean_abs_logprob_gap": statistics.fmean(lp_gap) if lp_gap else 0.0,
            "max_abs_logprob_gap": max(lp_gap) if lp_gap else 0.0}


def summarize(name: str, pairs: list[dict]) -> None:
    ident = sum(p["identical"] for p in pairs)
    divs = [p["first_divergence"] for p in pairs if p["first_divergence"] is not None]
    gaps = [p["mean_abs_logprob_gap"] for p in pairs]
    print(f"{name:34s} identical {ident:3d}/{len(pairs):3d}   first divergence (tokens) median {statistics.median(divs) if divs else '-':>6}  "
          f"min {min(divs) if divs else '-':>4}   mean |Δlogprob| on common prefix {statistics.fmean(gaps):.4f}")


def cmd_compare(args) -> int:
    out = Path(args.out)
    a = json.loads((out / f"{args.label_a}.json").read_text())
    b = json.loads((out / f"{args.label_b}.json").read_text())
    ra = {r["id"]: r for r in a["runs"]}
    rb = {r["id"]: r for r in b["runs"]}
    ids = [i for i in ra if i in rb]
    print(f"{a['label']}: {a.get('model', DEFAULT_MODEL)}  {a['server_cache_config'][:120]}")
    print(f"{b['label']}: {b.get('model', DEFAULT_MODEL)}  {b['server_cache_config'][:120]}")
    print(f"prompts compared: {len(ids)}  (max_tokens {a['max_tokens']} / {b['max_tokens']})\n")
    within_a = [agreement(ra[i]["passes"][0]["tokens"], ra[i]["passes"][1]["tokens"]) for i in ids]
    within_b = [agreement(rb[i]["passes"][0]["tokens"], rb[i]["passes"][1]["tokens"]) for i in ids]
    across_11 = [agreement(ra[i]["passes"][0]["tokens"], rb[i]["passes"][0]["tokens"]) for i in ids]
    across_22 = [agreement(ra[i]["passes"][1]["tokens"], rb[i]["passes"][1]["tokens"]) for i in ids]
    summarize(f"{a['label']} pass1 vs {a['label']} pass2 (noise floor)", within_a)
    summarize(f"{b['label']} pass1 vs {b['label']} pass2 (noise floor)", within_b)
    summarize(f"{a['label']} pass1 vs {b['label']} pass1", across_11)
    summarize(f"{a['label']} pass2 vs {b['label']} pass2", across_22)
    for lab, rr in ((a["label"], ra), (b["label"], rb)):
        cached = [rr[i]["passes"][1]["cached_tokens"] or 0 for i in ids]
        prompt = [rr[i]["passes"][1]["prompt_tokens"] or 0 for i in ids]
        lat1 = statistics.median(rr[i]["passes"][0]["latency_s"] for i in ids)
        lat2 = statistics.median(rr[i]["passes"][1]["latency_s"] for i in ids)
        print(f"\n{lab}: pass2 cached_tokens/prompt_tokens = {sum(cached)}/{sum(prompt)}  median latency pass1 {lat1:.1f}s pass2 {lat2:.1f}s")
    print("\nReading: if across-server agreement is no worse than the within-server noise floor, the cache does not change the\n"
          "model's greedy behaviour on these prompts; if it diverges earlier / more often, the cache does.")
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "pair", "identical", "first_divergence", "mean_abs_logprob_gap", "max_abs_logprob_gap"])
            for name, pairs in (("within_a", within_a), ("within_b", within_b), ("across_p1", across_11), ("across_p2", across_22)):
                for i, p in zip(ids, pairs):
                    w.writerow([i, name, p["identical"], p["first_divergence"], f"{p['mean_abs_logprob_gap']:.5f}", f"{p['max_abs_logprob_gap']:.5f}"])
        print(f"per-prompt rows written to {args.csv}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="send every prompt twice to the live server and record the generations")
    c.add_argument("--label", required=True, help="e.g. off / on; names <out>/<label>.json")
    c.add_argument("--api-base", default="http://localhost:8000/v1")
    c.add_argument("--cell", default=str(DEFAULT_CELL), help="cell to sample prompts from (first collect only)")
    c.add_argument("--prompts-from", help="reuse this prompts.json instead of sampling from --cell (first collect only)")
    c.add_argument("--model", help="expected model id; default: whatever /v1/models reports")
    c.add_argument("--reset-cache", action="store_true",
                   help="POST /reset_prefix_cache before every request (caching-ON server started with "
                        "VLLM_SERVER_DEV_MODE=1): the ON engine with zero cache hits, e.g. --label on_cold")
    c.add_argument("--n", type=int, default=40)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--max-tokens", type=int, default=512)
    c.add_argument("--timeout", type=float, default=1800)
    c.set_defaults(func=cmd_collect)
    d = sub.add_parser("compare", help="compare two collected labels")
    d.add_argument("label_a")
    d.add_argument("label_b")
    d.add_argument("--csv", help="also write per-prompt rows here")
    d.set_defaults(func=cmd_compare)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
