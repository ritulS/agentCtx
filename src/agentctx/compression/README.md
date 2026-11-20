# Adaptive configuration

A user-supplied Python callback or JSON schedule can choose the next primitive,
budget / step interval and depth once after all compression operations in a
query. See [ADAPTIVE.md](ADAPTIVE.md) for the API, examples, timing, and event logs.

The primitives in this package are truncation (TR), the length-free summary
(SU-free) and the online Claude select family, ocs / ocsa (`primitives.py`,
`claude_extract.py` for the selector model). The ICLR-era primitives (SU-full,
SS, the partial forms, TRC and its stacks, OTRC, staggered), CLM (`clm/`), the
Jev selector backend (`jev_select.py`), the online Claude extract (oce) and the
incremental / threshold / output-extract / phase-gate select variants (ocsi,
ocst, ocstx, ocstx15, ocstx15p) were removed on 2026-11-19; git history before that commit has
their code, contracts and measurements.

# TR contract (standalone and SU-free fallback)

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
or SU-free truncation fallback:
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

SU-free uses this same TR policy only when all summary attempts
fail: target B*r, complete-turn deletion, and the same protected content and
diagnostics. A successful summary still has no length target and is not
post-truncated. The event `primitive` identifies which summary policy fell
back; `summary_outcomes.fallback` remains `"truncate"` for compatibility.

This policy uses `truncate_oldest_turns()`. The legacy `truncate()` function
(drop single messages from the front of the window) remains the budget-time
fallback of the online primitives, with a current-context-relative target.
Historical standalone TR runs used a current-context-relative target and
single-message deletion; do not mix them with runs of this revised policy.

Verify with `venv/bin/python -m unittest discover -s tests -p test_truncation.py -v`.

## Summary completeness (SU-free)

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
re-read the model output. SU-free still has no length target: an over-long
but complete reply is accepted.
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


Trajectory writes now stream JSON to a temporary file in the same directory,
flush and fsync it, then atomically replace the destination. Serialization,
write, or replacement failure keeps the previous snapshot intact. SIGKILL may
leave an incomplete `.trajectory.json.*.tmp` file; readers use only the final
`trajectory.json`.

Observation metadata retains at most 65,536 characters in `extra.raw_output`,
including an omission marker between the head and tail. Truncated metadata
carries `raw_output_truncated=true` and `raw_output_original_chars`. The
observation template still sees the full original output, so model-visible
content, token counting, summaries and submitted patches are unchanged. This
bounds retained history/event metadata, not the subprocess's temporary stdout
buffer or a custom template that renders the entire output.

SWE-bench aggregation records `trajectory_status` (`ok`, `missing`,
`unreadable`, `oversized`) and `n_calls_source`. Trajectories over 256 MiB are
not loaded into memory. Missing/unreadable/oversized snapshots recover the
completed-call count from `token_log.model_call_records`, or from the legacy
`step_prompt_tokens` array when call records are absent. A token log newer
than the last atomic snapshot also raises its count, without lowering a
trajectory's count for an in-flight call. This does not reconstruct a lost
submission: a run without a readable patch is still graded `resolved=false`,
and `trajectory_status` is the flag for excluding or annotating such rows in
analysis. Existing result files are not rewritten by this recovery code.


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
venv/bin/python -m unittest discover -s tests -p test_truncation.py -v
venv/bin/python -m unittest discover -s tests -p test_call_accounting.py -v
venv/bin/python -m unittest discover -s tests -p test_summary_cleaning.py -q
```

Tests cover complete-turn truncation, summary acceptance and parser errors,
net savings and persisted logs.


## Cache reuse around compression

Each `model_call_records` entry in a new token log carries cached/uncached
prompt tokens and the cache hit rate when the API exposes
`usage.prompt_tokens_details.cached_tokens`. `compression_cache_comparisons`
pairs the immediately preceding call with the first call after budget
compression or an online primitive, and reports `reuse_ratio_vs_before_processed`: the
observed hit divided by the previous call's prompt + completion. That is a
reference ratio, not a survival rate (hits can come from other requests, and
a failed previous call gives null). Missing usage stays null.
See [cache measurement and CSV export](../../../ICLR_experiments/analysis/COMPRESSION_CACHE.md)
for server setup, step numbering, and interpretation.
