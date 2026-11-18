#!/usr/bin/env python
"""Real Jev judgements (MSWEA_SELECT_BACKEND=jev, the online-jev-select cells) on the
history of an existing run, to check the key, the request shape and how Jev's per-message
relevance compares with the generative selector's choices.
Usage:
    venv/bin/python scripts/maintenance/probe_jev_select.py <run_dir> [--steps 10,20] [--min-tokens 15000]
                                                            [--cap 20000] [--no-anchor] [--dry-run]
Rebuilds the complete history from <run_dir>/events.jsonl, cuts it after the observation of
each requested step (the agent's state before call step+1) and judges every window message
exactly as the primitive does (keep_recent = MSWEA_EXTRACT_KEEP_RECENT, default 1, widened
to the turn). Prints the settings, then per step one line per message: uid, role, tokens,
Jev's probability, the decision (keep / drop / capped out), and, when the run is an
online-claude-select run whose token_log.json has a selection at that step, the generative
selector's decision for the same uid (K whole, P partial, D dropped) and the agreement.
--dry-run builds the requests and prints their sizes without calling the API.
Without --steps it judges every step whose history exceeds --min-tokens cl100k tokens.
Settings: TYPESAFE_API_KEY (or ~/.config/agentctx/typesafe_api_key), MSWEA_JEV_* as in
src/agentctx/compression/jev_select.py; MSWEA_JEV_JUDGEMENT_LOG=0 to skip the log.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(entry))

from agentctx.compression import primitives as mem                                  # noqa: E402
from agentctx.compression import jev_select                                         # noqa: E402


def _selection_at(token_log: dict | None, step: int) -> dict | None:
    """The generative selector's keep dict {uid: None | ranges} recorded for the
    firing before call step+1, or None."""
    if not token_log:
        return None
    for ev in token_log.get("online_claude_select_events") or []:
        if ev.get("step") == step and ev.get("selection"):
            return ev["selection"].get("keep") or {}
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--steps", default=None, help="comma-separated steps (1-based, the agent call whose turn ends the history)")
    ap.add_argument("--min-tokens", type=int, default=15000)
    ap.add_argument("--cap", type=int, default=None, help="selection cap in tokens (default: MSWEA_SELECT_CAP or none)")
    ap.add_argument("--no-anchor", action="store_true", help="no hysteresis bonus (default: anchored, previous context = the run's own context at that step when known, else none)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]
    msgs = [e["message"] for e in events]
    token_log = None
    if (run_dir / "token_log.json").exists():
        token_log = json.loads((run_dir / "token_log.json").read_text())
    ends: list[tuple[int, int]] = []
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
    settings = jev_select.jev_settings()
    print("settings:", json.dumps(settings))
    keep_recent = max(0, int(os.environ.get("MSWEA_EXTRACT_KEEP_RECENT", "1") or "1"))
    cap = args.cap if args.cap is not None else int(os.environ.get("MSWEA_SELECT_CAP", "0") or "0")
    task_text = mem._history_text(msgs[1:mem.N_PROTECTED])
    client = None
    if args.dry_run:
        def transport(body, headers):
            return 200, {"model": "dry-run", "answers": {jev_select.QUESTION_NAME: {"type": "noul", "noul": 0.5}},
                         "usage": {"input_tokens": len(body["state"]) // 4, "output_tokens": 0}}, None
        client = jev_select.JevClient(settings, transport=transport)
    for s, e in picks:
        full = msgs[:e]
        compressible = full[mem.N_PROTECTED:]
        k = mem._extract_keep_split(compressible, keep_recent)
        window, kept = compressible[:k], compressible[k:]
        if not window:
            print(f"step {s}: empty window"); continue
        prev_sel = _selection_at(token_log, s - 1) if token_log else None
        prev_uids = set(prev_sel) if (prev_sel and not args.no_anchor) else set()
        budget = max(0, cap - mem.count_tokens(full[:mem.N_PROTECTED]) - mem.count_tokens(kept)) if cap else None
        selection, rec, pt, ct, lat, _ids = jev_select.jev_select_window(
            task_text, window, kept, prev_uids, budget_tokens=budget, render=mem._select_render_message,
            anchor=not args.no_anchor, token_of=lambda m: mem.count_tokens([m]), client=client)
        ref = _selection_at(token_log, s)
        print(f"\nstep {s}: history {mem.count_tokens(full)} tokens, window {len(window)} messages, kept tail {len(kept)}; "
              f"jev model {rec['resolved_model']} requests {rec['requests']} errors {rec['errors']} "
              f"long_context {rec['long_context']} input_tokens {pt} wall {lat:.1f}s (sum {rec['latency_sum_s']}s); "
              f"kept {len(selection)} ({mem.count_tokens(mem.apply_selection(window, selection))} tokens)"
              + (f", capped out {len(rec['capped_out'])}" if budget is not None else ""))
        agree = total = 0
        for m in window:
            uid = mem._msg_uid(m)
            p = rec["probs"].get(uid)
            decision = "keep" if uid in selection else ("capped" if uid in rec["capped_out"] else "drop")
            line = (f"  {uid:>8} {m.get('role', '?')[:9]:<9} {mem.count_tokens([m]):>6} tok  p={'  n/a' if p is None else f'{p:.3f}'}"
                    f"  {decision:<6}")
            if ref is not None:
                r = "K" if uid in ref and ref[uid] is None else ("P" if uid in ref else "D")
                same = (decision == "keep") == (r != "D")
                agree += same; total += 1
                line += f"  model={r} {'=' if same else '!'}"
            print(line)
        if ref is not None and total:
            print(f"  agreement with the run's selector at this step: {agree}/{total} = {agree / total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
