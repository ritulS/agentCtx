#!/usr/bin/env python
"""Real Jev line-level judgements (MSWEA_OUTPUT_EXTRACT_BACKEND=jev) on the long tool
outputs of an existing run, compared with the line ranges the run's generative selector
kept for the same outputs.
Usage:
    venv/bin/python scripts/maintenance/probe_jev_line_extract.py <run_dir> [--uids m00120,m00011]
                                                                  [--min-tokens 1000] [--dry-run]
Without --uids every observation above --min-tokens cl100k tokens is judged. For each output
the probe prints the settings, the per-line probabilities summarised by decile, the ranges
Jev keeps (MSWEA_JEV_LINE_THRESHOLD / _BLOCK / _PAD / _MAX_FRACTION), and, when the run's
token_log.json has online_claude_select selections with a line range for that uid, the
selector's ranges at each such step, the per-line AUC of Jev's probability against the
selector's kept lines, and the overlap of the two line sets. Settings: TYPESAFE_API_KEY,
MSWEA_JEV_*; MSWEA_JEV_JUDGEMENT_LOG=0 to skip the log.
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


def _selector_ranges(token_log: dict | None, uid: str) -> list[tuple[int, list]]:
    """[(step, ranges)] for every selection that kept ``uid`` partially."""
    out = []
    for ev in (token_log or {}).get("online_claude_select_events") or []:
        keep = ((ev.get("selection") or {}).get("keep") or {})
        if uid in keep and keep[uid] is not None:
            out.append((ev.get("step"), keep[uid]))
    return out


def _lines_of(ranges) -> set:
    return {i for a, b in ranges for i in range(a, b + 1)}


def _auc(probs: dict, n: int, block: int, positive: set) -> float | None:
    pos, neg = [], []
    for i in range(1, n + 1):
        key = jev_select.line_id(((i - 1) // block) * block + 1)
        p = probs.get(key)
        if p is None:
            continue
        (pos if i in positive else neg).append(p)
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--uids", default=None, help="comma-separated observation uids (default: every output above --min-tokens)")
    ap.add_argument("--min-tokens", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]
    msgs = [e["message"] for e in events]
    token_log = json.loads((run_dir / "token_log.json").read_text()) if (run_dir / "token_log.json").exists() else None
    by_uid = {mem._msg_uid(m): i for i, m in enumerate(msgs) if mem._msg_uid(m)}
    if args.uids:
        uids = [u.strip() for u in args.uids.split(",") if u.strip()]
    else:
        uids = [mem._msg_uid(m) for i, m in enumerate(msgs)
                if i >= mem.N_PROTECTED and m.get("role") in ("user", "tool") and mem.count_tokens([m]) > args.min_tokens]
    if not uids:
        print("no matching output"); return 1
    print("settings:", json.dumps(jev_select.jev_settings()), "lines:", json.dumps(jev_select.line_settings()))
    task_text = mem._history_text(msgs[1:mem.N_PROTECTED])
    client = None
    if args.dry_run:
        def transport(body, headers):
            answers = {k: {"type": "noul", "noul": 0.5} for k in body["questions"]}
            return 200, {"model": "dry-run", "answers": answers,
                         "usage": {"input_tokens": len(body["state"]) // 4, "output_tokens": 0}}, None
        client = jev_select.JevClient(jev_select.jev_settings(), transport=transport)
    ls = jev_select.line_settings()
    for uid in uids:
        if uid not in by_uid:
            print(f"\n{uid}: not in events.jsonl"); continue
        i = by_uid[uid]
        obs = msgs[i]
        cmd = next((msgs[j] for j in range(i - 1, -1, -1) if msgs[j].get("role") == "assistant"), None)
        n = len(mem._msg_text(obs).split("\n"))
        ranges, rec, pt, ct, lat, _ids = jev_select.jev_extract_output(
            task_text, mem._select_render_message(cmd) if cmd else "", mem._msg_text(obs), uid, client=client)
        kept = n if ranges is None else sum(b - a + 1 for a, b in ranges)
        probs = {k: v for k, v in rec["probs"].items() if v is not None}
        bins = [0] * 10
        for p in probs.values():
            bins[min(int(p * 10), 9)] += 1
        print(f"\n{uid}: {n} lines, {mem.count_tokens([obs])} tokens; jev {rec['resolved_model']} requests {rec['requests']} "
              f"errors {rec['errors']} long_context {rec['long_context']} state {rec['state_bytes']} bytes "
              f"input_tokens {pt} wall {lat:.1f}s; kept {kept}/{n} lines"
              + (" (whole)" if ranges is None else f" in {len(ranges)} ranges: {[list(r) for r in ranges][:8]}"))
        print("  p by decile (blocks):", " ".join(f"{b:3d}" for b in bins),
              f"| mean {sum(probs.values()) / max(1, len(probs)):.3f} max {max(probs.values()) if probs else 0:.2f}")
        for step, sel_ranges in _selector_ranges(token_log, uid):
            pos = _lines_of(sel_ranges)
            jev_lines = set(range(1, n + 1)) if ranges is None else _lines_of(ranges)
            auc = _auc(rec["probs"], n, ls["block"], pos)
            inter = len(pos & jev_lines)
            print(f"  selector at step {step}: kept {len(pos)} lines {sel_ranges} | per-line AUC {('n/a' if auc is None else f'{auc:.2f}')} "
                  f"| overlap {inter}/{len(pos)} of selector's lines in Jev's keep, Jev keeps {len(jev_lines)} "
                  f"| mean p on selector's lines {sum(rec['probs'].get(jev_select.line_id(((i - 1) // ls['block']) * ls['block'] + 1)) or 0 for i in pos) / max(1, len(pos)):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
