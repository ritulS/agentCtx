# TRC contract

The `tool-result-clear` condition (`MSWEA_PRIMITIVE=tool_result_clear`) uses
**K=3 tool results and complete-turn truncation to the budget**, as agreed on
2026-09-27. The implementation is in `primitives.py`; the agent hook is in
`mini-swe-agent/src/minisweagent/agents/default.py`.

## Trigger and clearing

Before a model call, if the estimated current context exceeds
`MSWEA_TOKEN_BUDGET = B`:

1. Identify tool results in the compressible history, preserving system and
   the initial task (`messages[:2]`). Native chat `tool` messages and user-role
   observations with `extra.raw_output` or `extra.returncode` are results.
   For legacy text histories, a user message immediately after an assistant
   is also treated as a result. Summaries and interrupt/parser feedback are
   excluded.
2. Keep the latest **three result messages** verbatim. This is a result count,
   not a count of all messages, steps, or assistant turns. Existing cleared
   results still occupy result slots.
3. Replace **every older result** with a `[TOOL OUTPUT CLEARED …]` placeholder.
   Do not stop early when the context crosses below B. Assistant messages,
   task text and summaries are not cleared. Already-cleared stubs are skipped.

There is no compression-ratio target in this stage. The function returns a
new message list without modifying its input; the agent adopts the result as
its working history. Original observations remain in the event log when
`MSWEA_EVENT_LOG_DIR` is enabled. This is not a reversible view over history.

## TR fallback

Recount after clearing. If the context still exceeds B, drop oldest complete
turns until it is at or below B. A turn is an assistant message and all its
following results/feedback up to the next assistant message. Multiple results
from one tool-call batch are removed together. A leading summary/feedback
block is a separate removable unit. The general `truncate()` primitive is
unchanged; TRC uses `truncate_oldest_turns()`.

System, initial task and the latest complete turn are always retained. The
K=3 guarantee applies only to clearing: fallback can retain fewer than three
results. If the protected messages and latest turn alone exceed B, record
`budget_exceeded_after_trc=true` and **continue with the next model call**.
The token log is flushed before that call so the overflow remains recorded
if the model request fails. The latest result's body stays intact.

B is a compression trigger, not a hard termination limit, consistent with
SU-free and SS-free. Normal model context limits, step limits and cost limits
still apply. A subsequent call can trigger compression again if the context
remains above B.

B is measured by the existing `count_tokens()` estimator (cl100k_base content
counts), not the provider's exact serialized request size. Clearing very short
outputs may increase token count; fallback uses the actual post-clear estimate.

Both clearing and TR fallback ignore `MSWEA_COMPRESSION_RATIO`. Meeting B
exactly gives no extra headroom, so later steps can trigger again immediately.

## Related conditions

- TRC+SU / TRC+SS, including their use in staggered policies, use the same
  clear-all-K=3 stage. If still above B, they use their existing summarizer
  and proportional summary target. Their **whole policy** is therefore not
  compression-ratio invariant.
- OTRC and scored TRC are separate policies and are unchanged by this revision.
- Existing runs used the old ratio-targeted clearing and single-message
  truncation. Do not treat those artifacts as runs of this revised policy or
  resume an old cell to mix the two implementations.

## Measurements

`token_log.json` contains `trc_events`, with one entry per invoked TRC stage:

- `policy`: `clear_all_keep3_budget_turns_v1`
- `step`, `primitive`, `picked`, `budget_tokens`, `keep_recent`
- `cleared_results`, `tokens_before`, `tokens_after_clear`, `tokens_after_trc`
- `clearing_tokens_saved`, `truncation_tokens_saved`
- `used_truncation_fallback`, `budget_exceeded_after_trc`

Savings subtract placeholder tokens and are signed, so net growth is visible.
For plain TRC their sum equals the event's total net savings. In a stacked
policy these fields cover the TRC stage only, before any summary.

Aggregate fields are `trc_clear_only_events`, `trc_clearing_tokens_saved`,
`trc_truncation_tokens_saved`, and the existing
`trc_truncation_fallback_events` (which also counts scored TRC's fallback).
A clear-only event means clearing fitted within B without TR fallback.
Event logs also include the stage measurements under `trc_stats`. SWE-bench
and Terminal-Bench result rows retain these fields when present.

## Verification

```bash
venv/bin/python -m unittest discover -s tests -p test_trc.py -v
venv/bin/python -m unittest discover -s tests -p test_summary_cleaning.py -q
```

Tests cover all-old-results clearing, K semantics, summaries and parser errors,
parallel tool results, pair preservation, exact-budget stopping, unattainable
budgets, net savings, ratio independence, stacked dispatch, and persisted logs.
