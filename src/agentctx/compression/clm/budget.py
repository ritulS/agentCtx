# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Context-budget mechanism of the CLM harness, ported to mini-swe-agent.

Ported from ``clm/clm_harness/utils/budget.py`` of context-language-models
(CC BY-NC 4.0; the header above is the original's and refers to that repository's
LICENSE). The policy is unchanged:

  * NO mechanical truncation. When the retained context crosses ``budget - reserve``
    the newest turns are ROLLED BACK until there is room to compact in and the model
    is told to compact (up to ``max_num_retry_on_limit`` times); after that it gets
    ONE final turn and the run stops.
  * Escalating NUDGES at fixed budget fractions (each fires once, re-arms when the
    model compacts back below it) and an URGENT nudge every turn near the limit.
  * Newest-output CAP so a single large observation cannot blow the budget.

Changes from the original, all forced by the host harness:

  * Token counts come from an injected ``count_fn`` (agentCtx's tiktoken cl100k
    ``count_tokens``, the ruler of every other agentCtx condition) instead of the CLM
    harness's own counter. Calibration to the served tokenizer is off unless
    ``calibrate=True``, and :meth:`BudgetController.calibrate` takes the reported
    ``prompt_tokens`` directly.
  * Observations are found with an injected ``is_observation`` predicate: the
    text-based agent delivers them as ``user`` messages, not ``tool`` messages.
  * A rollback never leaves an assistant turn last. In the text-based agent every
    assistant turn is an action followed by its observation, so a trailing one would
    be an action without a result (and a prefill for the next request).
  * The final-turn and urgent-nudge wording says that unsubmitted work is lost: the
    original says the work is "graded as-is", which holds for the CLM harness (the
    sandbox is graded) but not here (only a submitted patch is evaluated).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


#: consecutive ignored rollbacks tolerated before the rollback starts digging deeper
_ROLLBACK_ESCALATE_AFTER = 3


def head_tail_truncate(text: str, keep_tokens: int, budget: int, encoder: Any) -> str:
    """Keep the head and tail of ``text`` totalling ~``keep_tokens``, eliding the
    middle with a marker. Only ever applied to the NEWEST message."""
    toks = encoder.encode(text, disallowed_special=())
    if len(toks) <= keep_tokens:
        return text
    keep = max(keep_tokens - 48, 128)  # ~48 tokens for the marker; floor 128
    head_n = keep // 2
    tail_n = keep - head_n
    elided = len(toks) - head_n - tail_n
    head = encoder.decode(toks[:head_n])
    tail = encoder.decode(toks[-tail_n:])
    return (
        f"{head}\n\n[... {elided} tokens elided to respect the {budget}-token "
        f"context cap; narrow the command, or compact stale context with your "
        f"context-editing tools ...]\n\n{tail}"
    )


@dataclass
class BudgetDecision:
    """Outcome of one pre-send budget check."""

    token_count: int
    action: str  # "continue" | "rollback" | "final_turn" | "stop"
    messages: list[dict[str, Any]] = field(default_factory=list)
    log: dict[str, Any] | None = None


class BudgetController:
    """Deterministic, truncation-free context-budget state machine."""

    def __init__(
        self,
        budget_tokens: int,
        *,
        count_fn: Callable[[list[dict[str, Any]]], int],
        encoder: Any = None,
        is_observation: Callable[[dict[str, Any]], bool] | None = None,
        reserve_tokens: int = 2048,
        nudge_ratios: list[float] | None = None,
        compaction_hint: str = "",
        persistent_nudge_ratio: float | str | None = None,
        persistent_nudge_obs_mult: float = 2.0,
        max_num_retry_on_limit: int = 0,
        retry_edit_margin_tokens: int = 2048,
        protect_prefix: int = 2,
        calibrate: bool = False,
    ) -> None:
        self.budget = int(budget_tokens or 0)
        self.reserve = int(reserve_tokens)
        self._count_fn = count_fn
        self._encoder = encoder
        self._is_observation = is_observation or (lambda m: m.get("role") == "tool")
        # count_fn -> served-tokenizer ratio, learned from real responses (calibrate=True).
        self.tok_ratio = 1.0
        self._calibrate_enabled = bool(calibrate)
        self.strict_target = self.budget - self.reserve if self.budget else 0
        self.nudge_ratios = sorted(f for f in (nudge_ratios or []) if 0.0 < f < 1.0)
        # Retry-on-limit: instead of spending the one final turn, roll the newest turns
        # back off the context until `retry_edit_margin` tokens are free, then demand a
        # compaction. Repeat up to N times. 0 == final turn, then stop.
        self.max_num_retry_on_limit = max(0, int(max_num_retry_on_limit))
        self.retry_edit_margin = int(retry_edit_margin_tokens)
        self.protect_prefix = int(protect_prefix)   # leading messages a rollback must keep
        self.n_retry_on_limit = 0
        self.n_turns_rolled_back = 0
        # Rollbacks since the model last actually compacted (see note_compaction). A fixed
        # margin can be too small for whatever output keeps blowing the budget, which
        # livelocks the model into replaying it, so each rollback digs deeper than the last.
        self._consec_rollbacks = 0
        # When set (fraction of strict_target), fire an URGENT nudge EVERY turn while the
        # retained context sits in [ratio*strict_target, strict_target].
        # "adaptive": the urgent band is sized from the recent observations instead of a
        # fixed fraction (see adaptive_persistent_trigger).
        self.persistent_nudge_adaptive = (
            isinstance(persistent_nudge_ratio, str)
            and persistent_nudge_ratio.strip().lower() == "adaptive"
        )
        self.persistent_nudge_obs_mult = float(persistent_nudge_obs_mult)
        self.persistent_nudge_ratio = (
            float(persistent_nudge_ratio)
            if not self.persistent_nudge_adaptive
            and persistent_nudge_ratio and 0.0 < float(persistent_nudge_ratio) < 1.0
            else None
        )
        self.compaction_hint = compaction_hint
        # What the high nudge says happens on overflow.
        self.overflow_consequence = (
            "if you cross the limit you get one final turn and then the session ends"
        )
        self._nudged: set[float] = set()   # tiers already fired (re-arm on compaction)
        self._finalized = False            # granted the one final turn on overflow
        self.n_nudges = 0

    @property
    def enabled(self) -> bool:
        return self.budget > 0

    @property
    def finalized(self) -> bool:
        return self._finalized

    def raw_count(self, messages: list[dict[str, Any]]) -> int:
        return int(self._count_fn(messages))

    def count(self, messages: list[dict[str, Any]]) -> int:
        """Retained-context token count, scaled by :attr:`tok_ratio` (1.0 unless the
        controller calibrates to the served tokenizer)."""
        return int(self.raw_count(messages) * self.tok_ratio)

    def calibrate(self, prompt_tokens: Any, raw_sent_tokens: int) -> None:
        """Fold the server's reported ``prompt_tokens`` for a request whose messages
        counted ``raw_sent_tokens`` into :attr:`tok_ratio`.

        Clamped to [0.5, 3.0]: a wilder ratio means something else went wrong
        (truncated or cached prompt, a gateway that counts differently) and must
        not be allowed to corrupt the budget.
        """
        if not self._calibrate_enabled:
            return
        try:
            pt = int(prompt_tokens or 0)
        except (TypeError, ValueError):
            return
        if pt <= 0 or raw_sent_tokens <= 0:
            return
        ratio = pt / raw_sent_tokens
        if 0.5 <= ratio <= 3.0:
            self.tok_ratio = ratio

    def evaluate(self, messages: list[dict[str, Any]]) -> BudgetDecision:
        """Pre-send budget check. Mutates internal state (fired tiers, finalized flag).
        Returns any messages to append + a log fragment + the action to take."""
        if not self.enabled:
            return BudgetDecision(0, "continue")
        tc = self.count(messages)
        # Re-arm any tier / the final-turn grant the model has compacted back below.
        self._nudged = {f for f in self._nudged if tc >= int(self.budget * f)}
        if tc > self.strict_target:
            # Roll back + retry takes precedence over the final turn while retries remain
            # and the protected prefix still leaves room to compact in.
            if (
                self.n_retry_on_limit < self.max_num_retry_on_limit
                and self.strict_target > self.retry_edit_margin
                and len(messages) > self.protect_prefix  # something is actually droppable
            ):
                self.n_retry_on_limit += 1
                self._consec_rollbacks += 1
                return BudgetDecision(
                    tc, "rollback",
                    log={"budget_rollback_retry": self.n_retry_on_limit, "tokens": tc},
                )
            if self._finalized:
                return BudgetDecision(tc, "stop", log={"budget_stop": True, "tokens": tc})
            self._finalized = True
            return BudgetDecision(
                tc, "final_turn",
                messages=[{"role": "user", "content": self.final_message(tc)}],
                log={"budget_final_turn": True, "tokens": tc},
            )
        self._finalized = False
        # Persistent high-water nudge: once within ratio*strict_target of the wall, nag
        # EVERY turn (not one-shot). Takes precedence over the tiered nudge.
        if self.persistent_nudge_ratio and tc >= int(self.strict_target * self.persistent_nudge_ratio):
            self.n_nudges += 1
            return BudgetDecision(
                tc, "continue",
                messages=[{"role": "user", "content": self.persistent_nudge_message(tc)}],
                log={"context_budget_nudge": "persistent", "tokens": tc},
            )
        if self.persistent_nudge_adaptive:
            need, obs, rule = self.adaptive_persistent_trigger(messages)
            if self.strict_target - tc < need:
                self.n_nudges += 1
                frac = (self.strict_target - need) / self.strict_target
                return BudgetDecision(
                    tc, "continue",
                    messages=[{"role": "user",
                               "content": self.persistent_nudge_message(tc, ratio=frac)}],
                    log={"context_budget_nudge": "persistent", "tokens": tc,
                         "persistent_rule": rule, "persistent_need": need, "recent_obs": obs},
                )
        # Escalating nudge: fire the highest crossed tier not yet fired (mark all crossed
        # so we never de-escalate to a lower-urgency message on a later turn).
        crossed = [f for f in self.nudge_ratios if tc >= int(self.budget * f)]
        to_fire = [f for f in crossed if f not in self._nudged]
        if to_fire:
            tier = max(to_fire)
            self._nudged |= set(crossed)
            self.n_nudges += 1
            return BudgetDecision(
                tc, "continue",
                messages=[{"role": "user", "content": self.nudge_message(tier, tc)}],
                log={"context_budget_nudge": tier, "tokens": tc},
            )
        return BudgetDecision(tc, "continue")

    #: Observations considered by the adaptive urgent band.
    ADAPTIVE_OBS_WINDOW = 3
    #: The adaptive band never reaches below this fraction of the limit.
    ADAPTIVE_FLOOR = 0.5
    #: Width of the band when recent outputs are small (the classic 90% rule).
    ADAPTIVE_MIN_BAND = 0.10

    def adaptive_persistent_trigger(self, messages: list[dict[str, Any]]) -> tuple[int, int, str]:
        """Headroom below the limit inside which the adaptive urgent nudge fires.

        need = max(10% of the limit, c x the largest of the last 3 observations), capped
        at half the limit. Returns ``(need, obs, rule)`` where rule is "ratio" (the 10%
        band), "obs" (output-sized) or "obs_capped" (hit the 50% floor)."""
        limit = self.strict_target
        tools = [m for m in messages[self.protect_prefix:] if self._is_observation(m)]
        obs = max((self.count([m]) for m in tools[-self.ADAPTIVE_OBS_WINDOW:]), default=0)
        by_ratio = int(self.ADAPTIVE_MIN_BAND * limit)
        by_obs = int(self.persistent_nudge_obs_mult * obs)
        cap = int((1.0 - self.ADAPTIVE_FLOOR) * limit)
        if by_obs <= by_ratio:
            return by_ratio, obs, "ratio"
        if by_obs > cap:
            return cap, obs, "obs_capped"
        return by_obs, obs, "obs"

    def note_compaction(self) -> None:
        """The model actually condensed its context — stop digging deeper on the next
        rollback. Dipping back under the limit is NOT enough: that happens every cycle of
        a livelock, so only a real compaction resets the escalation."""
        self._consec_rollbacks = 0

    def rollback_margin(self) -> int:
        """Rollback depth for the current attempt: ``retry_edit_margin``, growing only
        once the model has ignored several rollbacks in a row."""
        depth = max(1, self._consec_rollbacks - _ROLLBACK_ESCALATE_AFTER)
        return min(
            self.retry_edit_margin * depth,
            max(3 * self.strict_target // 4, self.retry_edit_margin),
        )

    def rollback_to_margin(
        self, messages: list[dict[str, Any]], protect: int | None = None, margin: int | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """Drop the NEWEST turns (in place) until the retained context leaves `margin`
        free tokens under the strict target, so the model has room to issue a compaction
        command. Never touches the protected prefix and never leaves an assistant turn
        last (an action without its observation).

        Returns ``(dropped_messages, tokens_after)``."""
        target = max(self.strict_target - (self.rollback_margin() if margin is None else margin), 0)
        protect = self.protect_prefix if protect is None else protect
        dropped: list[dict[str, Any]] = []
        while len(messages) > protect and self.count(messages) > target:
            dropped.append(messages.pop())
            while len(messages) > protect and messages[-1].get("role") == "assistant":
                dropped.append(messages.pop())
        self.n_turns_rolled_back += len(dropped)
        return list(reversed(dropped)), self.count(messages)

    def rollback_message(
        self, n_dropped: int, tokens_after: int, tried: list[str] | None = None
    ) -> str:
        body = (
            f"[SYSTEM NOTICE — CONTEXT LIMIT HIT (retry {self.n_retry_on_limit}/"
            f"{self.max_num_retry_on_limit})] Your context crossed the {self.budget}-token limit, "
            f"so your {n_dropped} most recent turn(s) were ROLLED BACK and are gone — that work is "
            f"no longer in your context and cannot be recovered ({self.n_turns_rolled_back} turn(s) "
            f"lost so far). You are now at ~{tokens_after}/{self.strict_target} tokens, which leaves "
            "room for exactly one thing: CONDENSE YOUR CONTEXT THIS TURN and do nothing else. "
            "Replace stale regions with short summaries."
        )
        if self.compaction_hint:
            body += " " + self.compaction_hint
        if tried:
            body += (
                "\nThese commands already ran and their output is what blew your budget, so their "
                "turns were discarded. Re-running them will just lose the context again — if you "
                "need one, make it print far less (head/grep/count instead of dumping):\n"
                + "\n".join(f"  - {c}" for c in tried)
            )
        return body

    def final_message(self, tokens: int) -> str:
        return (
            f"[SYSTEM NOTICE] You have reached your context budget ({tokens}/{self.budget} "
            "tokens). This is your FINAL turn: submit your solution now, exactly as the task "
            "instructions require, because after this turn the session ends and work that "
            "has not been submitted is lost."
        )

    def persistent_nudge_message(self, tokens: int, ratio: float | None = None) -> str:
        ratio = self.persistent_nudge_ratio if ratio is None else ratio
        body = (
            f"You are at {tokens}/{self.strict_target} tokens — over "
            f"{int(round(ratio * 100))}% of your hard context limit and about "
            "to be cut off. Compact your context THIS TURN (do nothing else): remove stale regions "
            "now. If you cross the limit you get exactly one final turn and then the session ends; "
            "work that has not been submitted by then is lost."
        )
        if self.compaction_hint:
            body += " " + self.compaction_hint
        return "CONTEXT BUDGET NUDGE (URGENT): " + body

    #: Note contract appended to the 50% and 75% nudge tiers.
    _NOTE_CONTRACT = (
        "When you write a replacement note, COPY facts forward from the text you are "
        "replacing (quote them): every RULED OUT candidate with its reason and the words "
        "'do not retry'; the exact queries/commands already tried; exact values marked "
        "VERIFIED or UNVERIFIED; and a NEXT line."
    )

    def nudge_message(self, frac: float, tokens: int) -> str:
        """Nudge text for the tier ``frac``.

        * <=25%: informational only; the compaction hint is NOT appended, since a how-to
          at this tier tends to trigger premature wholesale deletion.
        * <=50%: finish the current unit of work, then tidy once, following the note contract.
        * higher: compact settled spans without wiping, plus the note contract and the
          overflow consequence.
        """
        pct = int(round(frac * 100))
        if frac <= 0.25:
            return (
                "CONTEXT BUDGET NUDGE: "
                f"context is at ~{pct}% of your {self.budget}-token budget ({tokens} tokens). "
                "No action needed. Before your next few searches, make sure your notes "
                "record which queries and documents you already tried."
            )
        if frac <= 0.50:
            body = (
                f"context is at ~{pct}% of your {self.budget}-token budget ({tokens} tokens). "
                "Finish the unit of work in flight, then tidy ONCE. "
                + self._NOTE_CONTRACT
            )
        else:
            body = (
                f"context is at ~{pct}% of your {self.budget}-token budget ({tokens} tokens) — "
                "close to the limit. Compact settled spans now — but do NOT wipe: edits "
                "keeping under 25% of the region they touch are usually followed by "
                "re-doing the deleted work. "
                + self._NOTE_CONTRACT
                + (f" {self.overflow_consequence}." if self.overflow_consequence else "")
            )
        if self.compaction_hint:
            body += " " + self.compaction_hint
        return "CONTEXT BUDGET NUDGE: " + body

    def cap_newest_output(
        self, messages: list[dict[str, Any]], content: str, *, floor: int = 128
    ) -> str:
        """Head/tail-truncate the NEWEST observation so it leaves room under the budget
        (only ever the newest message; cache-friendly)."""
        if not self.enabled or self._encoder is None:
            return content
        room = self.strict_target - self.raw_count(messages)
        body = self.raw_count([{"role": "user", "content": content}])
        if body <= room:
            return content
        return head_tail_truncate(content, max(room, floor), self.budget, self._encoder)
