#!/usr/bin/env python3
"""Replay a run's event log to recover the context the model saw at any step.

Inputs (written by mini-swe-agent when MSWEA_EVENT_LOG_DIR is set; run_experiment.py
sets it to the run directory):
    <run_dir>/events.jsonl              one record per message, appended when the
                                        message is added — i.e. BEFORE any primitive
                                        touches it. Fields: seq, uid, step, message.
    <run_dir>/compression_events.jsonl  one record per compression event (budget
                                        triggered or online TRC): dropped / replaced /
                                        added uids, summary text (in `added`),
                                        before_uids / after_uids, token counts.

Both files share one `seq` counter, so sorting by seq gives the exact order in
which the live message list was mutated.

Usage:
    python scripts/reconstruct_context.py <run_dir>                 # verify only
    python scripts/reconstruct_context.py <run_dir> --step 12       # print context sent for call 12
    python scripts/reconstruct_context.py <run_dir> --event 1       # print what event 1 removed

Library use:
    from scripts.reconstruct_context import Replay
    r = Replay(run_dir)
    ctx = r.context_at_call(12)      # list[dict] messages the model saw for call 12
    r.verify()                       # raises on any mismatch

Verification (`verify`):
  * each compression event's recorded before_uids/after_uids match the replayed list;
  * tiktoken counts of the replayed context match tokens_before/tokens_after in the
    event record and, when token_log.json exists, context_tokens_at/after_compression;
  * the final replayed list equals trajectory.json's messages (uid order + content).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from memory import count_tokens  # noqa: E402


def _uid(m: dict):
    return (m.get("extra") or {}).get("uid")


class Replay:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.events = self._load(self.run_dir / "events.jsonl")
        self.compressions = self._load(self.run_dir / "compression_events.jsonl", required=False)
        if not self.events:
            raise ValueError(f"{self.run_dir}: events.jsonl missing or empty")
        # Merge in mutation order.
        ops = [("add", e) for e in self.events] + [("compress", c) for c in self.compressions]
        ops.sort(key=lambda t: t[1]["seq"])
        self.ops = ops
        self.states: list[tuple[dict, list[dict]]] = []   # (op record, message list after op)
        self.mismatches: list[str] = []
        self._replay()

    @staticmethod
    def _load(path: Path, required: bool = True) -> list[dict]:
        if not path.is_file():
            if required:
                return []
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    # ── replay ──────────────────────────────────────────────────────────────
    def _replay(self) -> None:
        msgs: list[dict] = []
        for kind, rec in self.ops:
            if kind == "add":
                msgs = msgs + [rec["message"]]
            else:
                before_uids = [_uid(m) for m in msgs]
                if before_uids != rec["before_uids"]:
                    self.mismatches.append(
                        f"event {rec['event_idx']} (seq {rec['seq']}): replayed before_uids != recorded")
                tb = count_tokens(msgs)
                if tb != rec["tokens_before"]:
                    self.mismatches.append(
                        f"event {rec['event_idx']}: tokens_before replay={tb} recorded={rec['tokens_before']}")
                by_uid = {_uid(m): m for m in msgs}
                for r in rec["replaced"]:
                    m = by_uid[r["uid"]]
                    by_uid[r["uid"]] = {**m, "content": r["new_content"]}
                for a in rec["added"]:
                    by_uid[a["uid"]] = a["message"]
                new = []
                for u in rec["after_uids"]:
                    if u not in by_uid:
                        self.mismatches.append(f"event {rec['event_idx']}: after_uid {u} unknown")
                        continue
                    new.append(by_uid[u])
                dropped_set = set(rec["dropped"])
                for u in before_uids:
                    if u not in rec["after_uids"] and u not in dropped_set:
                        self.mismatches.append(f"event {rec['event_idx']}: {u} vanished but not in dropped")
                msgs = new
                ta = count_tokens(msgs)
                if ta != rec["tokens_after"]:
                    self.mismatches.append(
                        f"event {rec['event_idx']}: tokens_after replay={ta} recorded={rec['tokens_after']}")
            self.states.append((rec, msgs))

    # ── queries ─────────────────────────────────────────────────────────────
    def context_at_call(self, call: int) -> list[dict]:
        """Messages the model received for API call number `call` (1-based).

        The assistant message produced by call k is added with step == k (n_calls
        is incremented before the query), so the context is the state just before
        that message was appended.
        """
        for i, (kind, rec) in enumerate(self.ops):
            if kind == "add" and rec["message"].get("role") == "assistant" and rec["step"] == call:
                return self.states[i - 1][1] if i > 0 else []
        raise KeyError(f"no assistant message for call {call}")

    def n_calls(self) -> int:
        return max((rec["step"] for kind, rec in self.ops
                    if kind == "add" and rec["message"].get("role") == "assistant"), default=0)

    def final_messages(self) -> list[dict]:
        return self.states[-1][1] if self.states else []

    def event(self, idx: int) -> dict:
        for c in self.compressions:
            if c["event_idx"] == idx:
                return c
        raise KeyError(idx)

    def removed_messages(self, idx: int) -> list[dict]:
        """Original (pre-compression) messages that event `idx` dropped or replaced."""
        c = self.event(idx)
        originals = {e["uid"]: e["message"] for e in self.events}
        for prior in self.compressions:
            for a in prior["added"]:
                originals[a["uid"]] = a["message"]
        return [originals[u] for u in c["dropped"] + [r["uid"] for r in c["replaced"]]]

    # ── verification ────────────────────────────────────────────────────────
    def verify(self, trajectory: Path | None = None, token_log: Path | None = None) -> None:
        problems = list(self.mismatches)
        trajectory = trajectory or self.run_dir / "trajectory.json"
        token_log = token_log or self.run_dir / "token_log.json"
        if trajectory.is_file():
            traj = json.loads(trajectory.read_text())["messages"]
            fin = self.final_messages()
            if [_uid(m) for m in traj] != [_uid(m) for m in fin]:
                problems.append("final uid order differs from trajectory.json")
            else:
                for a, b in zip(traj, fin):
                    if a.get("content") != b.get("content"):
                        problems.append(f"content differs from trajectory.json at uid {_uid(a)}")
                        break
        if token_log.is_file():
            tl = json.loads(token_log.read_text())
            budget_events = [c for c in self.compressions if c["kind"] == "budget"]
            rec_at = tl.get("context_tokens_at_compression", [])
            rec_after = tl.get("context_tokens_after_compression", [])
            if [c["tokens_before"] for c in budget_events] != rec_at:
                problems.append("tokens_before of budget events != token_log.context_tokens_at_compression")
            if [c["tokens_after"] for c in budget_events] != rec_after:
                problems.append("tokens_after of budget events != token_log.context_tokens_after_compression")
            if [c["step"] for c in budget_events] != tl.get("compression_event_steps", []):
                problems.append("event steps != token_log.compression_event_steps")
        if problems:
            raise ValueError("\n".join(problems))


def _brief(m: dict, width: int = 100) -> str:
    c = m.get("content")
    if isinstance(c, list):
        c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    c = (c or "").replace("\n", "\\n")
    return f"{_uid(m):>8} {m.get('role', '?'):9} {count_tokens([m]):6d} tok  {c[:width]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--step", type=int, help="print the context sent for this API call (1-based)")
    ap.add_argument("--event", type=int, help="print what this compression event (1-based) removed")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    r = Replay(args.run_dir)
    if not args.no_verify:
        r.verify()
        print(f"OK: {len(r.events)} messages, {len(r.compressions)} compression events, "
              f"{r.n_calls()} calls; replay matches trajectory.json and token_log.json")
    if args.step is not None:
        ctx = r.context_at_call(args.step)
        print(f"\ncontext for call {args.step}: {len(ctx)} messages, {count_tokens(ctx)} tok")
        for m in ctx:
            print(_brief(m))
    if args.event is not None:
        c = r.event(args.event)
        print(f"\nevent {args.event}: kind={c['kind']} primitive={c.get('primitive')} picked={c.get('picked')} "
              f"step={c['step']} {c['tokens_before']}→{c['tokens_after']} tok "
              f"(target {c.get('target_tokens')}, fallback={c.get('trc_fallback')})")
        print(f"dropped {len(c['dropped'])}, replaced {len(c['replaced'])}, added {len(c['added'])}")
        for m in r.removed_messages(args.event):
            print("  -", _brief(m))
        for a in c["added"]:
            print("  +", _brief(a["message"], width=300))
    return 0


if __name__ == "__main__":
    sys.exit(main())
