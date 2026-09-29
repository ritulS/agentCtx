# Per-step KV cache ownership

This opt-in tracer records blocks held exclusively by a model request and
blocks simultaneously held by other requests. It uses vLLM V1's actual block
tables, not `cached_tokens` or server-wide `/metrics`.

## Enable for a new server session

The serving launchers accept `AGENTCTX_KV_TRACE_DIR`. For example, after the
existing server has been stopped at an appropriate time:

```bash
AGENTCTX_KV_TRACE_DIR="$PWD/logs/kv-cache/qwen" \
  bash scripts/serving/start_vllm_qwen35_prefix_cache.sh
```

Unset the variable for normal serving without instrumentation. An already
running server must be restarted to enable this; this implementation does not
stop or restart servers. The helper adds the repository's `src` to PYTHONPATH
and selects `agentctx.vllm_kv_trace.TracingScheduler`. For a manual vLLM launch,
set the same environment variables and pass that class with `--scheduler-cls`.
The factory preserves the configured synchronous/asynchronous scheduler.

## Export an agent run

New agent calls save the API response ID in `token_log.json`'s
`model_call_records`, including format-error responses. After a run:

```bash
PYTHONPATH=src python3 -m agentctx.kv_cache_trace \
  /path/to/task/condition/run_1 --trace-dir logs/kv-cache/qwen
```

This writes `kv_cache_steps.json` in the run directory, with each agent step's:

- exclusive, shared and total block counts and bytes at each recorded change;
- separate peaks for exclusive, shared and total bytes;
- request ID, timestamps, server trace file and layout metadata;
- completion/partial/missing/ambiguous measurement status.

`steps` has one row per agent model call. `summary_calls` has one row per
summarizer query made by a compression event (SU/SS families; one row per
attempt, rejected attempts included), joined through
`summary_outcomes[].response_ids` in `token_log.json`. Each row carries
`attempt_accepted` (this query produced the summary; only the last query of
an accepted event) and `event_accepted` (the event as a whole). When a
summarizer query raised (transport error, interrupt), the agent still records
the ids received before it, with `interrupted` set to the exception type; the
compression event itself never completed, so it has no
`compression_events.jsonl` record. Those rows are only
`complete` when the summarizer was served by the traced vLLM; a separately
served summarizer yields `not_found`. Summarizer requests are kept apart from
`steps` because they are not agent steps and run between two of them. Their
blocks are what other tasks' steps see as `shared` while they overlap, and
without this join they would look like an unrelated client. Outcomes logged
before response ids were recorded produce a warning, never an inferred match.
The file also carries a `notes` list restating the caveats below.

## Read this before using the numbers

- **`shared` is instantaneous co-ownership only.** A block is `shared` when
  two or more live requests hold it at that sampling instant. Reusing a block
  left by an already finished request (the previous step of the same task, or
  another task's finished step) is `exclusive` now, and cached-but-unowned
  blocks in the pool are charged to nobody. "Task KV" here means blocks held
  by an in-flight request, not the pool memory a task's prefix keeps warm.
- **Peaks are not simultaneous.** `peak_exclusive_*`, `peak_shared_*` and
  `peak_total_*` are independent maxima over the request lifetime. When a
  concurrent request finishes, a system-prompt block flips from `shared` to
  `exclusive` without any allocation. Do not add peak exclusive and peak
  shared; use `samples` (timestamped) for a time-resolved or time-integrated
  view.
- **Bytes are one tensor-parallel shard.** `*_bytes_per_worker` is the pool
  slot capacity of a single worker. Multiply by
  `metadata.tensor_parallel_size` (4 for the Qwen3.5 launchers) for the
  GPU-wide figure. Pipeline parallelism leaves bytes `null`.

The server writes one `kv-cache-<pid>-<uuid>.jsonl` per engine process. Copy
these files to the analysis machine when the server runs on another host.
No server HTTP endpoint or shared filesystem with the agent is required.
Old logs without response IDs in `model_call_records` cannot be joined by
this exporter; missing IDs are reported, never inferred from timing.

## Measurement meaning

- An agent step is one model call. A model call contains many engine scheduling
  iterations. The tracer observes allocation state after scheduling, processing
  model outputs and aborts, writing only changes. It does not poll every 10 s.
- Sharing means **simultaneous ownership by different requests** at that instant.
  Reusing a previous, completed request's cache can still be exclusive now.
  Requests are not experiment tasks: the logs do not identify whether another
  request belongs to another task, the same task, or an unrelated client.
- Bytes are **per model worker**, computed from configured KV tensor capacities
  divided by pool block count. They include slot padding, and hybrid models'
  state-cache blocks. They are allocated pool capacity, not just attention KV
  payload, not GPU-wide memory, and not newly allocated CUDA memory (vLLM
  reserves its pool in advance). TP replicas/shards are not summed.
- Physical block IDs are counted once per request across groups; null/padding
  placeholder blocks are excluded. Unreferenced reusable blocks are not charged
  to a request. A shared block appears in each owner's shared count, so summing
  request totals double-counts it. Independent peaks need not occur together:
  do not add peak exclusive and peak shared to get peak total.
- Pipeline parallel layouts have unknown bytes (`null`) rather than guessed
  totals; block counts are still recorded. A finished record means scheduler
  removal, including cancellations, not successful generation.
- Killed engines leave partial traces; transport failures without an API
  response cannot be attributed to an agent step by this exporter.
- Joining targets ordinary single-prompt, single-output chat/completions from
  vLLM V1, including its internal ID suffix. Batched prompts and multiple output
  branches are outside this interface; duplicate matches are marked ambiguous.
- Instrumentation scans live block tables and writes changes on the scheduler
  thread. It adds overhead; use the same setting when comparing timings. No
  measured latency-overhead bound is claimed.

The implementation is checked against installed vLLM **0.17.1**, including a
CPU-only test of real prefix-block allocation/sharing/freeing. vLLM's scheduler
interface is internal; other versions require validation before measurement.
No GPU generation validation is implied by those tests. Runtime tracing errors
are logged and disable tracing while letting inference continue.

```bash
venv/bin/python -m unittest discover -s tests -p test_kv_cache_trace.py -v
```
