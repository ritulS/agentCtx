#!/usr/bin/env python
"""One real extract_tool_output() call (the ocstx per-output pre-extraction), to check
key, model, request shape and grammar on a real long tool output.
Usage:
    venv/bin/python scripts/maintenance/probe_output_extract.py <run_dir> [--uid m00127] [--min-tokens 1000]
Takes the observation with the given uid from <run_dir>/events.jsonl (or, without
--uid, the first observation above --min-tokens cl100k tokens), the assistant message
that issued it and the task statement, calls the extractor exactly as
DefaultAgent._output_extract does and prints the settings, the verdict, usage, the
directives returned and the text that would replace the output. Selector settings as
for the campaign, e.g.
    MSWEA_EXTRACT_PROVIDER=openrouter MSWEA_EXTRACT_MODEL=deepseek/deepseek-v4.1-flash-1017 \\
    MSWEA_EXTRACT_EFFORT=low MSWEA_EXTRACT_MAX_TOKENS=12000 MSWEA_SUMMARY_ATTEMPT_LOG=0 \\
    venv/bin/python scripts/maintenance/probe_output_extract.py data/r2/.../run_1 --uid m00127
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
    ap.add_argument("--uid", default=None)
    ap.add_argument("--min-tokens", type=int, default=1000)
    args = ap.parse_args()
    events = [json.loads(l) for l in (Path(args.run_dir) / "events.jsonl").read_text().splitlines() if l.strip()]
    msgs = [e["message"] for e in events]
    task_text = mem._history_text(msgs[1:mem.N_PROTECTED])
    obs = cmd = None
    for i, m in enumerate(msgs):
        if m.get("role") not in ("user", "tool") or i < mem.N_PROTECTED:
            continue
        if (args.uid and mem._msg_uid(m) == args.uid) or (not args.uid and mem.count_tokens([m]) > args.min_tokens):
            obs = m
            cmd = next((p for p in reversed(msgs[:i]) if p.get("role") == "assistant"), None)
            break
    if obs is None:
        print("no matching observation"); return 1
    print("settings:", json.dumps(extract_settings()))
    print(f"observation {mem._msg_uid(obs)}: {mem.count_tokens([obs])} tokens, "
          f"{len(mem._msg_text(obs).split(chr(10)))} lines; command message {mem._msg_uid(cmd) if cmd else None}")
    new, rec, pt, ct, lat = mem.extract_tool_output(obs, cmd, task_text)
    outcome = mem.pop_summary_outcome()
    print(f"outcome: {json.dumps(rec)}")
    print(f"usage: prompt {pt} completion {ct} latency {lat:.1f}s attempts {outcome.get('attempts')} "
          f"rejections {outcome.get('rejections')} accepted {outcome.get('accepted')}")
    if new is None:
        print("output unchanged")
    else:
        print(f"--- replacement ({mem.count_tokens([{'content': new}])} tokens) ---")
        print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
