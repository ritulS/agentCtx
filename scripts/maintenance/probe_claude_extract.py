#!/usr/bin/env python
"""One real extraction call against Claude, to check key, model and request shape.

Usage:
    venv/bin/python scripts/maintenance/probe_claude_extract.py [run_dir]

Without a run_dir a small synthetic history is extracted. With a run_dir, the
compressible window of that run's final trajectory.json is used (the first
`--max-messages` messages after system + task, default 8). Prints the request
settings, the accepted/rejected verdict, usage and the extract. Needs
ANTHROPIC_API_KEY or ~/.config/agentctx/anthropic_api_key, like the primitive.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

from agentctx.compression import primitives as mem                 # noqa: E402
from agentctx.compression.claude_extract import extract_settings, get_extract_model  # noqa: E402

SYNTHETIC = [
    {"role": "system", "content": "You are a helpful assistant that can interact with a computer."},
    {"role": "user", "content": "Fix the bug: `parse_date('2024-02-30')` raises ValueError instead of returning None."},
    {"role": "assistant", "content": "THOUGHT: find the function\n```bash\ngrep -rn 'def parse_date' src\n```"},
    {"role": "user", "content": "src/utils/dates.py:42:def parse_date(s):"},
    {"role": "assistant", "content": "THOUGHT: read it\n```bash\nsed -n 40,60p src/utils/dates.py\n```"},
    {"role": "user", "content": "40 import datetime\n41 \n42 def parse_date(s):\n43     return datetime.date.fromisoformat(s)\n"},
    {"role": "assistant", "content": "THOUGHT: list unrelated files\n```bash\nls docs\n```"},
    {"role": "user", "content": "CHANGELOG.md  README.md  api.md  index.md"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", nargs="?", type=Path)
    ap.add_argument("--max-messages", type=int, default=8)
    args = ap.parse_args()

    if args.run_dir:
        traj = json.loads((args.run_dir / "trajectory.json").read_text())
        msgs = [{"role": m["role"], "content": m.get("content", "")} for m in traj["messages"]]
        messages = msgs[:mem.N_PROTECTED] + msgs[mem.N_PROTECTED:mem.N_PROTECTED + args.max_messages]
    else:
        messages = SYNTHETIC

    print("settings:", json.dumps(extract_settings()))
    print(f"window: {len(messages) - mem.N_PROTECTED} messages, {mem.count_tokens(messages)} tokens in")
    model = get_extract_model()
    new_messages, saved, pt, ct, latency = mem.online_claude_extract(messages, model)
    outcome = mem.pop_summary_outcome() or {}
    print(f"accepted={outcome.get('accepted')} attempts={outcome.get('attempts')} "
          f"rejections={outcome.get('rejections')} prompt_tokens={pt} completion_tokens={ct} "
          f"latency_s={latency:.1f} tokens_saved={saved}")
    if outcome.get("accepted"):
        print("---- extract ----")
        print(new_messages[mem.N_PROTECTED]["content"])
        return 0
    print("no extract accepted; see flags:", json.dumps(outcome.get("flags"), default=str))
    return 1


if __name__ == "__main__":
    sys.exit(main())
