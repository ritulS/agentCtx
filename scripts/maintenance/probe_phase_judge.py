#!/usr/bin/env python
"""One or more real judge_phase_boundary() calls (the ocstx15p phase-boundary gate), to
check key, model, request shape and grammar on a real trajectory.
Usage:
    venv/bin/python scripts/maintenance/probe_phase_judge.py <run_dir> [--steps 10,20,30] [--min-tokens 15000]
Rebuilds the complete history from <run_dir>/events.jsonl, cuts it after the observation
of each requested step (the agent's state before call step+1, as DefaultAgent._phase_gate
sees it when the context is uncompressed) and asks the judge exactly as the gate does.
Without --steps it judges every step whose history exceeds --min-tokens cl100k tokens.
Prints the settings, then per step the verdict, reason, usage and attempt counts.
Selector settings as for the campaign, e.g.
    MSWEA_EXTRACT_PROVIDER=openrouter MSWEA_EXTRACT_MODEL=deepseek/deepseek-v4.1-flash-1017 \\
    MSWEA_EXTRACT_EFFORT=low MSWEA_EXTRACT_MAX_TOKENS=12000 MSWEA_SUMMARY_ATTEMPT_LOG=0 \\
    venv/bin/python scripts/maintenance/probe_phase_judge.py data/r2/.../run_1 --steps 12,20
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

from agentctx.compression import primitives as mem                                  # noqa: E402
from agentctx.compression.claude_extract import extract_settings                    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--steps", default=None, help="comma-separated steps (1-based, the agent call whose turn ends the history)")
    ap.add_argument("--min-tokens", type=int, default=15000)
    args = ap.parse_args()
    events = [json.loads(l) for l in (Path(args.run_dir) / "events.jsonl").read_text().splitlines() if l.strip()]
    msgs = [e["message"] for e in events]
    # history prefix ending with the observation(s) of each assistant turn
    ends: list[tuple[int, int]] = []     # (step, index after the turn's last message)
    step = 0
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant" and i >= mem.N_PROTECTED:
            step += 1
        if step and (i + 1 == len(msgs) or msgs[i + 1].get("role") == "assistant"):
            ends.append((step, i + 1))
    if args.steps:
        want = {int(x) for x in args.steps.split(",") if x.strip()}
        picks = [(s, e) for s, e in ends if s in want]
    else:
        picks = [(s, e) for s, e in ends if mem.count_tokens(msgs[:e]) > args.min_tokens]
    if not picks:
        print("no matching step"); return 1
    print("settings:", json.dumps(extract_settings()))
    for s, e in picks:
        ctx = msgs[:e]
        rec, pt, ct, lat = mem.judge_phase_boundary(ctx)
        outcome = mem.pop_summary_outcome()
        print(f"step {s}: {mem.count_tokens(ctx)} tokens, {len(ctx) - mem.N_PROTECTED} history messages -> "
              f"{rec['verdict']} ({rec['outcome']}); prompt {pt} completion {ct} latency {lat:.1f}s "
              f"attempts {outcome.get('attempts')} rejections {outcome.get('rejections')}")
        if rec.get("reason"):
            print(f"   reason: {rec['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
