#!/usr/bin/env python
"""One real selection call against Claude, to check key, model, request shape and grammar.
Usage:
    venv/bin/python scripts/maintenance/probe_claude_select.py [run_dir] [--max-messages N] [--keep-recent K]
Without a run_dir a small synthetic history (with a long pip-install style
output) is selected from. With a run_dir, the first N messages after system +
task of that run's events.jsonl (the complete history; falls back to
trajectory.json) are used. Prints the request settings, the accepted/rejected
verdict, usage (cache fields included), the directives Claude returned and the
rebuilt context. Needs ANTHROPIC_API_KEY or ~/.config/agentctx/anthropic_api_key,
like the primitive. With MSWEA_EXTRACT_PROVIDER=openrouter MSWEA_EXTRACT_MODEL=<vendor/model>
the same call goes through OpenRouter (OPENROUTER_API_KEY or
~/.config/agentctx/openrouter_api_key); the printed usage then also has `cost`.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

from agentctx.compression import primitives as mem                                  # noqa: E402
from agentctx.compression.claude_extract import extract_settings, get_extract_model  # noqa: E402

PIP = "\n".join(
    [f"Collecting dep{i}\n  Downloading dep{i}-1.{i}.0-py3-none-any.whl (1{i} kB)" for i in range(1, 30)]
    + ["Building wheels for collected packages: scikit-learn",
       "  error: subprocess-exited-with-error",
       "  × Building wheel for scikit-learn (pyproject.toml) did not run successfully.",
       "  │ exit code: 1"]
    + [f"  {w}" for w in ("...", "...")]
    + ["ERROR: Failed building wheel for scikit-learn",
       "Successfully installed numpy-1.24.4 scipy-1.10.1"]
)


def _m(role, content, uid):
    return {"role": role, "content": content, "extra": {"uid": uid}}


SYNTHETIC = [
    _m("system", "You are a helpful assistant that can interact with a computer.", "m00001"),
    _m("user", "Fix the bug: `parse_date('2024-02-30')` raises ValueError instead of returning None.", "m00002"),
    _m("assistant", "THOUGHT: find the function\n```bash\ngrep -rn 'def parse_date' src\n```", "m00003"),
    _m("user", "<returncode>0</returncode>\n<output>\nsrc/utils/dates.py:42:def parse_date(s):</output>", "m00004"),
    _m("assistant", "THOUGHT: install deps first\n```bash\npip install -e .\n```", "m00005"),
    _m("user", f"<returncode>1</returncode>\n<output>\n{PIP}</output>", "m00006"),
    _m("assistant", "THOUGHT: read it\n```bash\nsed -n 40,60p src/utils/dates.py\n```", "m00007"),
    _m("user", "<returncode>0</returncode>\n<output>\n40 import datetime\n41 \n42 def parse_date(s):\n43     return datetime.date.fromisoformat(s)\n</output>", "m00008"),
    _m("assistant", "THOUGHT: list unrelated files\n```bash\nls docs\n```", "m00009"),
    _m("user", "<returncode>0</returncode>\n<output>\nCHANGELOG.md  README.md  api.md  index.md</output>", "m00010"),
    _m("assistant", "THOUGHT: check tests\n```bash\nls tests\n```", "m00011"),
    _m("user", "<returncode>0</returncode>\n<output>\ntest_dates.py</output>", "m00012"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", nargs="?", type=Path)
    ap.add_argument("--max-messages", type=int, default=12)
    ap.add_argument("--keep-recent", type=int, default=1)
    args = ap.parse_args()
    if args.run_dir:
        events = args.run_dir / "events.jsonl"
        if events.exists():
            msgs = [json.loads(l)["message"] for l in events.read_text().splitlines()]
        else:
            traj = json.loads((args.run_dir / "trajectory.json").read_text())
            msgs = traj["messages"]
        for i, m in enumerate(msgs, 1):
            m.setdefault("extra", {}).setdefault("uid", f"m{i:05d}")
        full = msgs[:mem.N_PROTECTED] + msgs[mem.N_PROTECTED:mem.N_PROTECTED + args.max_messages]
    else:
        full = SYNTHETIC
    print("settings:", json.dumps(extract_settings()))
    print(f"history: {len(full)} messages, {mem.count_tokens(full)} tokens")
    model = get_extract_model()
    new, saved, pt, ct, lat = mem.online_claude_select(full, list(full), model, keep_recent=args.keep_recent)
    outcome = mem.pop_summary_outcome() or {}
    print(f"accepted={outcome.get('accepted')} attempts={outcome.get('attempts')} "
          f"rejections={outcome.get('rejections')} prompt_tokens={pt} completion_tokens={ct} "
          f"latency_s={lat:.1f} tokens_saved={saved}")
    print("selection:", json.dumps((outcome.get("flags") or {}).get("selection"), indent=None))
    log = mem.summary_attempt_log_path() if hasattr(mem, "summary_attempt_log_path") else None
    print("---- directives (last reply) ----")
    try:
        last = json.loads(Path(log).read_text().splitlines()[-1]) if log and Path(log).exists() else None
        print(last["content"] if last else "(attempt log disabled)")
    except Exception as exc:   # noqa: BLE001
        print(f"(could not read attempt log: {exc})")
    print("---- rebuilt context ----")
    for m in new:
        uid = (m.get("extra") or {}).get("uid")
        print(f"[{uid} {m['role']}]\n{m['content']}\n")
    return 0 if outcome.get("accepted") else 1


if __name__ == "__main__":
    sys.exit(main())
