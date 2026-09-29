# Adaptive configuration

A user-supplied Python callback or JSON schedule can choose the next primitive,
trigger (token budget or OTRC step interval), and depth once after all compression
operations in a query. See
[ADAPTIVE.md](ADAPTIVE.md) for the API, examples, OTRC timing, and event logs.

# TR contract (standalone and SU-free/SS-free fallback)

For `MSWEA_PRIMITIVE=truncation`, compression fires before a model call when
the estimated current context exceeds `MSWEA_TOKEN_BUDGET = B`. The target
is `max(1, floor(B * MSWEA_COMPRESSION_RATIO))`, including protected content.
Drop oldest complete assistant turns, including all following tool results
and feedback up to the next assistant. A leading summary/feedback block is
a separate removable unit. Preserve `messages[:2]` (system and initial task)
and the latest turn, with its result bodies intact. If those alone exceed the
target or B, keep them and continue with the model call. Existing before/after
counts and saved-token measurements still record such attempts, even if no
tokens were removed; the event log records the budget-relative target.

`token_log.json` stores one entry in `tr_events` per standalone TR invocation
or SU-free/SS-free truncation fallback:
`policy=budget_ratio_complete_turns_v1`, `step`, `primitive`, `budget_tokens`,
`target_tokens`, `tokens_before`, `tokens_after`, `tokens_saved`, and three
independent flags (multiple can be true for the same event):

- `target_not_met`: post-TR tokens are strictly greater than the target B*r.
- `budget_exceeded`: post-TR tokens are strictly greater than B.
- `zero_reduction`: before/after token counts are equal.

Equality with the target or budget is success for that limit. An ordinary
successful compression has all three flags false. The corresponding totals
are `tr_target_not_met_events`, `tr_budget_exceeded_events`, and
`tr_zero_reduction_events`; their sum is not a count of distinct events.
These totals do not alter `compression_events`, which still counts attempts.

The same event record appears as `tr_stats` in `compression_events.jsonl`.
Both logs are saved before the model call, so a failed request retains its
preceding TR diagnostics. Harbor's `CheckpointAgent` also flushes these stats
to the trial's `worker_checkpoint.json` before inference, independently of
`MSWEA_TOKEN_LOG_PATH`. The parent recovers that checkpoint into `token_log.json`
after killing a timed-out worker. The in-flight model call's usage is still
unknown. SWE-bench and Terminal-Bench result rows preserve these fields. Runs
without a TR invocation have an empty list and zero totals;
historical logs without the fields remain missing, not inferred successes.

SU-free and SS-free use this same TR policy only when all summary attempts
fail: target B*r, complete-turn deletion, and the same protected content and
diagnostics. A successful summary still has no length target and is not
post-truncated. The event `primitive` identifies which summary policy fell
back; `summary_outcomes.fallback` remains `"truncate"` for compatibility.

This policy uses `truncate_oldest_turns()`. The legacy `truncate()` function
and its uses in other summaries, OTRC+TR, scored TRC and staggered policies
are unchanged, as are their compression targets. TRC still uses its existing
complete-turn fallback to B. Historical standalone TR runs used a
current-context-relative target and single-message deletion; do not mix them
with runs of this revised policy.

Verify with `venv/bin/python -m unittest discover -s tests -p test_truncation.py -v`.

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
   The placeholder uses the result's original `extra.uid_step`, which survives
   history truncation. Legacy results without that field show `step unknown`.
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

## Summary completeness (SU, SS, partial and free variants)

`clean_summary_text()` accepts a summarizer reply only when it is a finished
marked block. Besides the marker and reasoning checks (rejections
`missing_marker`, `empty_body`, `unterminated_reasoning`,
`ambiguous_reasoning`), since 2026-09-29 it rejects:

- `truncated`: the provider reported `finish_reason == "length"`. The
  reply was cut off by the token limit whatever it contains.
- `missing_close_marker`: the open marker line is never followed by a
  close marker line. Before this date the body ran to the end of the reply
  and the close marker was appended; the r2 P30S run1 audit
  (`experiments/r2/audits/r2_p30s_run1_20260929`) found a 133,948-character
  transcript copy accepted that way, growing the history from 15,123 to
  31,684 tokens in one SU-free event.

Rejected replies take the existing retry path (`MSWEA_SUMMARY_MAX_ATTEMPTS`,
default 5) and then the TR fallback. `extra.summary_format` on the accepted
message and `summary_outcomes[].rejections` in `token_log.json` name the
reasons; `summary_outcomes[].flags` (and `summary_outcome.flags` in
`compression_events.jsonl`) hold the accepted or last rejected reply's
marker flags, `finish_reason` and `raw_chars`, so later audits need not
re-read the model output. SU-free / SS-free still
have no length target: an over-long but complete reply is accepted.
Summary-based runs made before and after this date are not the same
condition.

## Net savings

`total_tokens_saved` is the sum of what the primitives report per event,
which is clamped at 0, so an event that grew the history counts as 0.
`net_tokens_saved` is the signed sum of the recorded
`context_tokens_at_compression - context_tokens_after_compression`, and
`growth_events` counts events whose after exceeds before. Both are computed
from arrays that every token log already holds, so old runs can be
re-aggregated without re-running; SWE-bench result rows carry them (with
`summary_fallback_events`) when the token log has them.

## Failed calls and log durability

After every compression the agent flushes `trajectory.json` together with
`token_log.json` (since 2026-09-29; before, the trajectory was written only
at the end of the step, which never happens when the harness kills the
process on timeout, so it lagged the event log by one compression). A
SWE-bench run killed by the harness timeout gets `exit_status="Timeout"`
(when the agent left none) and `timed_out=true` in its result row.


For the LiteLLM chat/text model path used by the Qwen, SU-free and FC runs,
a rejected response retains its provider response in the `FormatError`.
The agent counts its prompt/completion tokens, cost and elapsed time exactly
once, then continues the existing format-error flow. Feedback `extra.response`
retains usage, reasoning and finish reason for diagnosis without sending these
metadata fields back to the model.

`step_prompt_tokens`, `step_completion_tokens` and `step_latency_s` now include
failed agent queries. `model_call_records` gives each call's explicit `step`,
`status` (`ok`, `format_error`, `error`), `error_type`, token counts and latency.
When the provider supplied no usage (for example a transport failure), its
record has null token counts; the legacy arrays use zero placeholders. These
are missing measurements, not evidence that the failed request used no tokens.
The elapsed time includes retries within that model query.

Every budget-compression event is flushed before the next model call, even
when compression brought the context below B. Logs are also flushed after
successful/failed queries and in the agent run loop's `finally` block, covering
submission, step/cost limits and exceptions. Token-log writes use an atomic
replacement so an interrupted write does not leave truncated JSON. A hard kill
while waiting for a response cannot record that unfinished call's usage; the
preceding compression is already persisted. The trajectory may still reflect
the last completed step; event logs retain the intervening compression.

This fixes subsequent runs. Historical rejected responses without provider
usage cannot be repaired exactly from their saved content. Historical
compression totals can be reconstructed separately from event logs.

## Verification

```bash
venv/bin/python -m unittest discover -s tests -p test_trc.py -v
venv/bin/python -m unittest discover -s tests -p test_call_accounting.py -v
venv/bin/python -m unittest discover -s tests -p test_summary_cleaning.py -q
```

Tests cover all-old-results clearing, K semantics, summaries and parser errors,
parallel tool results, pair preservation, exact-budget stopping, unattainable
budgets, net savings, ratio independence, stacked dispatch, and persisted logs.


## Cache reuse around compression

Each `model_call_records` entry in a new token log carries cached/uncached
prompt tokens and the cache hit rate when the API exposes
`usage.prompt_tokens_details.cached_tokens`. `compression_cache_comparisons`
pairs the immediately preceding call with the first call after budget
compression or Online TRC, and reports `reuse_ratio_vs_before_processed`: the
observed hit divided by the previous call's prompt + completion. That is a
reference ratio, not a survival rate (hits can come from other requests, and
a failed previous call gives null). Missing usage stays null.
See [cache measurement and CSV export](../../../analysis/COMPRESSION_CACHE.md)
for server setup, step numbering, and interpretation.
