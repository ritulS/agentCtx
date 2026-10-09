# Cache reuse before and after compression

New SWE-Bench and Terminal-Bench runs record request-level cache usage in each
`token_log.json`. No extra inference or server-wide metrics polling is needed.
The API must return `usage.prompt_tokens_details.cached_tokens`.

For vLLM, start the agent server with `--enable-prompt-tokens-details` in addition
to its existing cache configuration. The Qwen launchers
`scripts/serving/start_vllm_qwen35_prefix_cache.sh` and
`scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh` now include this flag
(also inherited by wrappers calling the latter). Add it explicitly for other
launchers. An already-running server needs a restart to apply this setting;
updating the files does not change running servers or agents.

The log contains:

- `model_call_records`: each agent call's `cached_tokens`,
  `uncached_prompt_tokens`, `cache_hit_rate`, `cache_usage_status` and source,
  together with the existing step, status, prompt tokens and latency.
- `compression_cache_comparisons`: observed changes across each compression
  boundary, including budget-triggered compression and Online TRC clears.

Per-call values are only in `model_call_records` (one entry per agent call,
1-based `step`, failed calls included); there are no separate `step_*` arrays
for cache usage. If the agent runs without `agentctx` importable, the records
carry `cache_usage_status: collector_unavailable` and no cache fields.

Rates are fractions (`cached_tokens / prompt_tokens`). Missing usage is `null`,
not zero; invalid cache counts (negative, non-integer, or greater than the
reported prompt size) are also unknown. A zero-size prompt has no defined rate.
This collector consumes the OpenAI-compatible usage shape; it does not infer
counts from server-wide counters or other provider-specific usage fields.
Summary-model calls are not included in the agent's per-step records.

Existing compression step `s` means **after s agent calls have completed**.
The comparison is therefore call `s` versus call `s+1`, the first post-compression
call, both using 1-based call numbers. Compression before the first call has no
baseline. Compression whose following call has not completed remains pending
(`missing_after_call`). Calls without usage are not skipped. Format errors that
retain valid API usage can still be compared; call status is preserved.

When multiple changes occur before one call (e.g. Online TRC then budget
compression), one comparison lists both kinds and their count. Their separate
effects cannot be measured without intervening model calls.

Export one run or a whole results directory:

```bash
python3 analysis/compare_compression_cache.py /path/to/results --output /tmp/compression_cache.csv
```

### Reuse relative to the previous call

`before_processed_tokens = before_prompt_tokens + before_completion_tokens` is
what the server processed for call `s`, and
`reuse_ratio_vs_before_processed = after_cached_tokens / before_processed_tokens`
relates the first post-compression hit to it. It is a reference ratio only.
It is not a measurement of how much cache compression destroyed:

- The numerator does not distinguish which request produced the reused
  blocks. Concurrent runs sharing the same prefix or summarizer calls on the
  same server can contribute hits, so the ratio may exceed 1.
- Block rounding and eviction lower it without any compression damage.
- Both values are `null` when call `s` did not complete normally
  (`before_status` other than `ok`): a rejected completion never enters the
  history, so it is not a valid reference. They are also `null` when call `s`
  lacks valid prompt or completion counts.

Read it alongside the before/after hit rates and counts rather than as a
single answer.

The CSV identifies the source token log and before/after steps. Positive
`cached_tokens_drop` means fewer cached tokens after compression; positive
`cache_hit_rate_drop_pp` means a lower hit rate in percentage points. Negative
values represent increases. `uncached_prompt_tokens_increase` is after minus
before. Unknown values are blank. For example, 900/1000 cached before and
100/500 after gives an 800-token drop, a 70 percentage-point rate drop, and
300 more uncached tokens. A smaller prompt can lower cached token count without
lowering hit rate, so inspect both counts and rates.

These are observations across adjacent calls, not compression's isolated causal
effect: new tool output, cache eviction, concurrent clients and summarizer calls
on the same server can affect cache reuse. Pre-compression context token estimates
are not an API measurement of how that uncompressed request would have hit.
No token position or cache block identity is recorded.

Old logs without per-call cache usage remain unknown; this command does not
backfill from trajectories. The displayed source path identifies the task/run.
A token log that cannot be parsed (for example truncated by a killed run) is
skipped with a warning on stderr and counted in the summary line; the rest of
the export still completes.
