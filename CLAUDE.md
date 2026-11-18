# agentCtx — project context

## What this project is

Empirical study of context-compression strategies for LLM agents on SWE-bench
Verified. The agent (`mini-swe-agent`) runs a tool-use loop, accumulating
trajectory tokens; a compression primitive fires when the token budget is
exceeded. Primitives include single-strategy (TR, SU-full, SU-partial, SS,
SS-partial, TRC), threshold-stacked (TRC+SU, TRC+SS), online (OTRC and
OTRC-stacked variants), and the new staggered ones that alternate or randomize
between two primitives at compression-event time.

Data flows: `results/ablations/<exp>/<task>/<condition>/run_<n>/trajectory.json`
→ `Review1/build_review1.py` → `Review1/Review1.csv` → analysis scripts in
`Review1/`. Paper spine: "compression beyond the budget" — even at unlimited
budget, no-compression resolves fewer tasks than compressed strategies on a
deployment-class agent. Online clearing wins on token cost; threshold stacking
wins on resolve rate.

## Two-machine workflow

This project is worked on across two machines:

- **Dobby** (primary): development, P100 expansion runs, depth/budget
  ablations, the staggered pilot. Serves Qwen3.5-35B-A3B continuously.
- **Albus** (8× A6000): hosts model-expansion runs (Qwen2.5-7B, Llama 3.3 70B)
  and the quantization sweep. Different model serving per phase. For
  Qwen3.5-35B-A3B SWE-bench runs there, `AGENTCTX_PROFILE=albus-swe`
  (`scripts/lib/profiles.sh`) serves on all 8 GPUs (TP=8) and runs 8 workers.

**Sync discipline**: at task boundaries — finishing one experiment phase or
moving from analysis to runs — push commits from whichever machine you edited
on, then pull on the other. Don't let a code change live on one machine for
more than half a day without pushing. Code goes through git; experiment
results and logs are gitignored (too large) and transferred via rsync if
needed for cross-machine analysis. All collected run data lives in `data/`
(see `data/README.md`); `results/ablations`, `results/tbench`, and
`Review1/raw` are compatibility symlinks into it.

Per-machine queues live in [exp_plans/DOBBY_PLAN.md](exp_plans/DOBBY_PLAN.md)
and [exp_plans/ALBUS_PLAN.md](exp_plans/ALBUS_PLAN.md).

## Where things live

- `src/agentctx/compression/primitives.py` — compression primitive functions (`truncate`, `summarize`,
  `summarize_partial`, `structured_summarize`, `tool_result_clear`, etc.).
  Two Claude-backed online primitives share `src/agentctx/compression/claude_extract.py`
  (Anthropic SDK, default `claude-opus-5-5`; `MSWEA_EXTRACT_MODEL` / `_EFFORT` /
  `_EVERY` / `_KEEP_RECENT`, default keep-recent 1 since 2026-10-25 = the newest
  turn stays verbatim) and fire before every agent model call once the
  previous observation is in the history; neither has a budget.
  `MSWEA_EXTRACT_PROVIDER=openrouter` (added 2026-10-26, for cheaper selector
  models) sends the identical prompts through OpenRouter's OpenAI-compatible
  endpoint via the `openai` SDK instead: `MSWEA_EXTRACT_MODEL=<vendor/model>` is
  then required, the key comes from `OPENROUTER_API_KEY` or
  `~/.config/agentctx/openrouter_api_key`, effort is sent as OpenRouter's
  `reasoning.effort` (also accepts `minimal` / `none`), `temperature` 0 is sent
  by default (`MSWEA_EXTRACT_TEMPERATURE`, since 2026-10-26; `none` omits it,
  which stays the anthropic default because thinking forbids it), the `cache_control`
  breakpoints are passed through, and usage gains `cost` (credits) and
  `reasoning_tokens`. Only the API call differs (client, request body, response
  mapping); prompts, validation, retries, event logs, condition names and cell
  tags are unchanged, so tag the model dir to tell OpenRouter runs apart; the
  token log's `extract_model` records `provider` + `model`:
  `online_claude_extract` (condition `online-claude-extract`, cell tag `oce`)
  sends the compressible window of the CURRENT context to Claude and replaces it
  with Claude's rewritten `[CONTEXT EXTRACT]` block (abstractive; Claude's own
  words, and in practice its plans, reach the agent).
  `online_claude_select` (condition `online-claude-select`, cell tag `ocs`,
  added 2026-10-25) is the extractive one for the "does the agent solve the task
  on the task-relevant information alone?" question: Claude is shown the COMPLETE
  history (`DefaultAgent._full_messages`, never compressed) with message uids and
  numbered output lines and replies with directives only (`keep <uid>`,
  `keep <uid> L<a>-<b>`, `drop <uid>`, `none`); the context is rebuilt from the
  original messages (whole, or the kept lines with `[... N lines omitted ...]`),
  so Claude never writes a word the agent reads, and a message dropped earlier can
  return later. A reply with prose, a `keep` of an unknown uid or an out-of-range
  line range is rejected and re-queried (`request_summary(validate=parse_selection)`),
  then "unchanged"; a `drop` of an unknown uid, a `keep` of a protected uid or
  of a gap inside the window's uid range (uids are not contiguous), and a range
  on an assistant message (kept whole) are tolerated (added 2026-10-26 for
  non-Claude selectors). `MSWEA_EXTRACT_PREFILL=1` (openrouter only) ends the prompt with an
  assistant message holding the open-marker line, so the reply cannot start as
  anything but a selection (the free Nemotron 3 Ultra otherwise answered as the
  agent from the second call on).
  `online-claude-select-anchored` (cell tag `ocsa`, added 2026-10-27) is the same
  primitive with two additions set through the condition's `env`
  (`MSWEA_SELECT_ANCHOR=1`, `MSWEA_SELECT_CAP=30000`; `conditions.py`): every
  history message is tagged with its token count and whether it was in the
  agent's context at the previous step, the selector is told to start from that
  selection and change as little as possible, and the selected history must fit
  the cap (an over-budget reply is rejected as `over_budget`, a correction
  message is appended and it is re-queried; `request_summary(on_reject=...)`).
  Selection records then carry `anchor`, `cap`, `budget_window`,
  `selected_tokens` and the stability counts `carried` / `added` / `removed`.
  Motivation: on the free Nemotron selector the plain cell's consecutive
  selections overlapped only ~50% (Jaccard) and twice exceeded Devstral's 65k
  context.
  `online-claude-select-incremental` (cell tag `ocsi`, added 2026-11-07) is the
  same primitive and grammar with `MSWEA_SELECT_SOURCE=context`
  (`select_source()` in `primitives.py`; default `full`): the selector is shown
  the agent's CURRENT context (what the previous selection kept, trimmed
  outputs included, plus the newest turn) instead of the complete history, so
  the context can only shrink, a dropped message or line never returns, and the
  selector prompt is context-sized (the extractive counterpart of OCE's input
  window). A line range on an already-trimmed output counts the lines of the
  trimmed text (the omission marker is one line). No anchor tags, no cap by
  default (`MSWEA_SELECT_CAP` can be added through the condition's `env`).
  Select events and selection records then carry `source: context`;
  `tokens_full` still counts the untouched complete history and `tokens_saved`
  is relative to the current context. Preset `ocsi` of the Devstral fc20
  launcher runs the cell `di__binf__ocsi`.
  `online-claude-select-threshold` (cell tag `ocst`, preset `ocst`, added
  2026-11-12) is the ocsa selector (anchor tags, cap) fired only while the
  context exceeds `MSWEA_EXTRACT_FIRE_ABOVE` tokens (30000; the gate lives in
  `DefaultAgent`'s online hook and also applies to `online_claude_extract`),
  with the cap lowered to 20000 so the rebuilt context has room to grow before
  the next firing. Between firings the context is append-only, so the agent
  model's prefix cache serves every step (the per-step ocsa cell re-prefilled
  ~57% of its prompt tokens: in-place drops, line-range changes and revivals
  moved text every step); a few selector calls per run instead of one per step.
  Its anchoring is the `MSWEA_SELECT_ANCHOR=trailing` form (added 2026-11-12):
  the header tag carries the token count only, and the previous-context uids
  and the budget figure sit in the trailing instruction block, so the system
  prompt and every history block are byte-identical from call to call and the
  selector's own prompt cache serves them (ocsa's per-header "in / not in
  context last step" tags and the budget figure in the system prompt changed
  every step: 6% cache hit on OpenRouter vs 92% for plain ocs). `1` keeps the
  2026-10-27 header form byte for byte (ocsa, replay tools). Selection records
  carry `anchor_style`.
  `online-claude-select-threshold-output-extract` (cell tag `ocstx`, preset
  `ocstx`, added 2026-11-12) is ocst plus a per-output pre-extraction
  (`MSWEA_OUTPUT_EXTRACT_ABOVE=1000` through the condition's `env`;
  `output_extract_threshold()` / `extract_tool_output()` in `primitives.py`,
  `DefaultAgent._output_extract` in the submodule, called from
  `execute_actions` of both agents right after the observations are added):
  every NEW tool output above the threshold is handed to the same extractor
  model with the task statement (cache breakpoint) and the agent message that
  issued the command, in the selector's directive grammar on that one message
  (`keep <uid>`, `keep <uid> L<a>-<b>`, `none`; `keep all` tolerated), and the
  kept lines replace the output's `content` IN PLACE under a fixed one-line
  note (`OUTPUT_EXTRACT_NOTE_FMT`: "tool output pre-extracted: K of N lines
  kept; the omitted lines were deleted from the history and cannot be
  recovered"), `[... N lines omitted ...]` where it cut; `none` leaves the note
  and one marker. The observation object is shared by `self.messages` and
  `_full_messages`, and its `extra.raw_output` copy is removed, so the
  omitted lines leave the context, the complete history the threshold
  selector re-selects from, and the trajectory at once: the only
  online-claude-select cell where dropped output text can never return
  (events.jsonl still holds the raw observation, logged before the
  extraction; `replay_agent.py` then skips its output-match check for that
  turn). A rejected reply is re-queried like a selector reply; when no attempt
  is accepted the output stays whole (fallback `unchanged`); errors count
  toward `MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS` like a selector error. Logs:
  `output_extract_events` (+ `_threshold`, `_accepted`, `_trimmed`,
  `_removed`, `_errors`, `_total_tokens_saved`) in token_log.json and the
  result rows, primitive `output_extract` in `summary_outcomes`
  (flags `output_extract`), `extra.output_extract` on the message, and a
  `kind: output_extract` record in `compression_events.jsonl` (the uid in
  `replaced`, `before_uids == after_uids`), which `reconstruct_context.py`
  replays; a compression event consumes a uid seq, so uids skip after one.
  On the ocst4 ocst runs only 2-4 outputs per run exceed 1000 tokens
  (6-11k of the 19-32k observation tokens). Smoke-test with
  `scripts/maintenance/probe_output_extract.py <run_dir> --uid <uid>`.
  `online-claude-select-threshold-output-extract-15k` (cell tag `ocstx15`,
  preset `ocstx15`, added 2026-11-12) is ocstx with the firing threshold
  halved (`MSWEA_EXTRACT_FIRE_ABOVE=15000`) and the cap lowered in the same
  2:3 proportion (`MSWEA_SELECT_CAP=10000`); the pre-extraction threshold is
  unchanged.
  `online-claude-select-threshold-output-extract-15k-phase` (cell tag
  `ocstx15p`, preset `ocstx15p`, added 2026-11-12) is ocstx15 with a
  phase-boundary gate on the threshold firing (`MSWEA_PHASE_GATE=1` through
  the condition's `env`; `phase_gate_config()` / `judge_phase_boundary()` in
  `primitives.py`, `DefaultAgent._phase_gate` in the submodule, called from
  the online hook in `query()` once the context exceeds
  `MSWEA_EXTRACT_FIRE_ABOVE`): a due firing is first put to the same
  extractor model as a question. The judge is shown the task statement and
  the agent's CURRENT context (every message rendered as the selector renders
  it, cache breakpoint on the last history block; the system prompt and the
  trailing question carry no per-step figures, so only the new history blocks
  are uncached) and replies between `[PHASE VERDICT]` / `[END PHASE VERDICT]`
  with `boundary` or `continue` on the first line and an optional one-line
  reason (`parse_phase_verdict()`; anything else is answered with a
  correction and re-queried through `request_summary(validate=...,
  on_reject=...)`). The selector fires only on `boundary`; on `continue` the
  step runs with the context untouched and the question is asked again before
  the next step. Above `MSWEA_PHASE_GATE_FORCE_ABOVE` tokens (30000 in the
  condition; default twice the firing threshold, `0` = no ceiling, a value at
  or below the threshold is rejected) the selector fires without asking, so a
  judge that never sees a boundary cannot let the context grow past the agent
  model's window; when no reply is accepted (fallback `fire`) or the judge
  errors below `MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS`, it fires as it would
  without the gate. The judge never writes a word the agent reads and changes
  no message, so nothing goes to `compression_events.jsonl`; its records go to
  `phase_judge_events` (+ `_config`, `_calls`, `_boundary`, `_continue`,
  `_forced`, `_errors`) in token_log.json and the result rows, each event
  carrying `step`, `tokens`, `verdict`, `reason`, `outcome`
  (accepted | fallback | forced | error), `forced`, `fired` and usage, and to
  `summary_outcomes` as primitive `phase_judge` (flags `phase_judge`).
  `MSWEA_EXTRACT_PREFILL=1` prefills the phase marker for the judge.
  Smoke-test with `scripts/maintenance/probe_phase_judge.py <run_dir>
  [--steps a,b]`, which judges the uncompressed history of an existing run
  after the given steps.
  `online-jev-select` (cell tag `ojs`, preset `ojs`, added 2026-11-17) is the
  same primitive with the selector backend switched to TypeSafe's Jev decision
  model (`MSWEA_SELECT_BACKEND=jev` through the condition's `env`;
  `select_backend()` in `primitives.py`, the backend in
  `src/agentctx/compression/jev_select.py`, `POST api.typesafe.ai/v1/systemone`
  over httpx, key `TYPESAFE_API_KEY` or `~/.config/agentctx/typesafe_api_key`).
  Instead of one generative call over the complete history, every window
  message is judged ON ITS OWN, in parallel (`MSWEA_JEV_WORKERS`, 8): Jev is
  shown the task statement, the agent's newest turn (`MSWEA_JEV_CONTEXT_TURNS`,
  1) and the candidate rendered as the selector renders it, and answers a
  `noul` question ("the agent still needs this message") with a probability.
  A message is kept WHOLE when probability + anchor bonus clears
  `MSWEA_JEV_KEEP_THRESHOLD` (0.5; the bonus `MSWEA_JEV_ANCHOR_BONUS`, 0.15,
  applies to messages in the previous context when `MSWEA_SELECT_ANCHOR` is on:
  the anchoring is a hysteresis here, no tags, no prompt), and under
  `MSWEA_SELECT_CAP` (30000) the kept messages are ranked by score (ties:
  newer first) and taken while they fit, so no reply is ever rejected or
  re-queried. Jev returns typed values only: no line ranges, and it never
  writes a word the agent reads. Each judgement is LOCAL (Jev cannot see that a
  message is redundant with or superseded by another), which is the question
  the cell asks. Requests above ~30000 bytes get TypeSafe's long-context
  header (`MSWEA_JEV_LONG_CONTEXT=header`; `truncate` cuts the candidate to
  fit instead). A judgement that fails after `MSWEA_JEV_MAX_RETRIES` keeps its
  message and is recorded with `error`; a 401/403 or a selection where every
  judgement failed raises, counted by `MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS`.
  Window, kept tail, rebuild, record and event-log kind are those of
  `online_claude_select`; the selection record adds `backend: jev` and `jev`
  (per-uid `probs` / `scores`, threshold, `requests`, `errors`,
  `long_context`, `capped_out`, usage), the summary outcome counts one attempt
  per Jev request with its request ids, every judgement goes to
  `jev_judgements.jsonl` beside `summary_attempts.jsonl`
  (`MSWEA_JEV_JUDGEMENT_LOG`), and token_log.json / the result rows carry
  `select_backend` and `jev_model`. `online-jev-select-threshold` (`ojst`) is
  the backend fired like ocst (above 30000, cap 20000);
  `online-jev-select-threshold-output-extract` (`ojstx`) adds the ocstx
  per-output pre-extraction, which still uses the generative extractor model
  (both keys needed). Smoke-test and compare with a run's own selections with
  `scripts/maintenance/probe_jev_select.py <run_dir> --steps a,b [--cap N]
  [--dry-run]`. Tests: `tests/test_jev_select.py` (no API).
  The selector prompt is a block list with a cache breakpoint on the last history
  block, so the growing history is served from the prompt cache. Both conditions
  use the benchmark default agent prompt (the OTRC / OCE prompt deltas are empty
  since 2026-10-25; the agent system prompt is identical in every condition).
  Needs `ANTHROPIC_API_KEY` or `~/.config/agentctx/anthropic_api_key`; smoke-test
  with `scripts/maintenance/probe_claude_extract.py` /
  `probe_claude_select.py`. Per-step records go to
  `online_claude_{extract,select}_events` in token_log.json (select events carry
  `tokens_full` and the `selection` counts) and `kind: online_claude_{extract,select}`
  in `compression_events.jsonl` (partial keeps appear as `replaced`, same uid).
  The root-level `memory.py` is only an alias to this module: the pinned
  mini-swe-agent commit (b54c485) still does `import memory` from its
  compression hook and event log. Remove the alias once the submodule is
  bumped to a commit that imports `agentctx.compression.primitives` directly.
- `mini-swe-agent/` — submodule. Pinned to 2549932 on branch `event-log` of
  `github.com/takeshiho0531/mini-swe-agent` (per-run event log + online-TRC
  clear-target fix) until that branch is merged upstream as
  ritulS/mini-swe-agent PR #1; the upstream branch is
  `agentctx-customizations` (dec8de2). The dispatch chain in
  `src/minisweagent/agents/default.py` calls primitives based on
  `MSWEA_PRIMITIVE` env var.
- `src/agentctx/compression/clm/` — CLM self-editing (condition and primitive
  `clm`, cell tag `clm`, finite-budget `di__b<N>k__clm` cells; added 2026-11-10),
  ported from `../context-language-models` (`clm/clm_harness`, CC BY-NC 4.0:
  `context_string.py` is a verbatim copy, `budget.py` a port that lists its
  changes). The agent's history after the protected prefix is mirrored to
  `/tmp/.live_ctx/LIVE_CTX_MAIN.txt` in the task container before every command
  (`docker exec` on stdin) and the agent compacts it by editing that file; the
  file is read back after the command and, when changed, parsed back into
  `self.messages`. No primitive fires on its own and nothing is truncated: the
  budget (limit = budget − 2048 reserve) produces nudges, caps the newest output
  to the room left, and at the limit rolls the newest turns back and demands a
  compaction (up to 50 times, then one final turn and exit status
  `ContextBudgetExceeded`, no submission). `session.py` holds the hooks
  `DefaultAgent` calls (`_clm`, built when `MSWEA_PRIMITIVE=clm`; before / after
  the model call in `query()`, around the action in `execute_actions()` of both
  `DefaultAgent` and `InteractiveAgent`) and documents the `MSWEA_CLM_*`
  settings. Differences from the CLM harness, all deliberate: every model call
  counts as a step (a compaction turn is not free), tokens are agentCtx's cl100k
  `count_tokens` (`MSWEA_CLM_CALIBRATE=1` scales to the served tokenizer as the
  CLM harness does), the action format / task prompt / grading are
  mini-swe-agent's. It is the ONLY condition whose agent system prompt differs
  from the benchmark default: `configs/config-clm.yaml` appends the
  mirror-editing section (the user's decision 2026-11-10). Logs: `clm_*` keys in
  token_log.json and the result rows (`clm_events`, `clm_edits`,
  `clm_rollbacks`, ...); in `compression_events.jsonl` an applied edit is a
  `clm_edit` record that replaces the whole editable window (every window
  message `dropped`, the parsed-back ones `added` with new uids, untouched
  turns included) and a rollback is a `clm_rollback` record;
  `reconstruct_context.py` replays both. Tests: `tests/test_clm.py` (no model,
  no container). Not yet run against a real server or container.
- `src/agentctx/` — shared Python package. `compression/` (primitives),
  `benchmarks/` (SWE-Bench and Terminal-Bench/Harbor adapters, verdict
  handling in `tb_verdict.py`, shared result conversion in
  `harbor_results.py` / `results.py`, the replay agent), `experiments/`
  (`conditions.py`, `runner.py`, `iclr.py`) and `summary_config.py`
  (summarizer-model overrides). `WORKSPACE_ROOT` and the `INFINITE_BUDGET`
  sentinel for uncompressed baselines are defined once in
  `src/agentctx/__init__.py`.
- `scripts/run_experiment.py` — CLI entry point for
  `src/agentctx/experiments/runner.py`. Conditions defined in
  `src/agentctx/experiments/conditions.py`; `--ablation`, `--budget`,
  `--tasks-file`, `--conditions`, `--summary-config` control a single sweep;
  the runner selects a benchmark adapter with `--benchmark`.
  `scripts/run_experiment_iclr.py` runs one cell of the canonical ICLR
  results tree. `scripts/run_experiment_r2.py` is the same launcher for
  the post-ICLR r2 extension campaign; it writes to
  `data/r2/<swebench|terminalbench>/<section>/<model>/<cell>/` (gitignored)
  and shares cell naming/validation with the ICLR launcher; r2-only sections
  are `p30s`, `p30s_never7`, `p100_minus_p30s` (the 70 P100 tasks outside
  P30S), `p100_minus_p30s_never13` (its 13 never-resolved tasks; the
  never-resolved lists come from `scripts/maintenance/never_resolved_tasks.py`)
  `p100_fc_only4` (the 4 P100 tasks resolved under full context but never
  under fixed TR or SU-free) and `p100_su_free_majority` / `p100_tr_majority`
  (tasks resolved in ≥2 of 3 fixed SU-free / TR runs, from
  `scripts/maintenance/majority_resolved_tasks.py`; uniform `sss` / `ttt`
  adaptive cells via `scripts/expansions/run_r2_swe_majority_uniform.sh`),
  and r2 alone accepts `adaptive-<tag>` cells
  (schedule-driven primitive order; see `src/agentctx/compression/ADAPTIVE.md`). Launchers are grouped under
  `scripts/{calibration,expansions,serving,harbor,maintenance}/`; see
  `scripts/README.md`.
- `tests/` — runner-equivalence suite: runs `scripts/run_experiment.py`,
  `scripts/run_experiment_iclr.py` and the calibration launchers from the
  working tree and from the reference branch (`origin/akiho-clean-20260921-preorg`,
  the pre-reorganization tree) against deterministic fakes and diffs
  everything they write, plus unit tests for verdicts, the summarizer guard
  and the ablation launcher. `uvx --with pyyaml pytest`; see
  `tests/README.md`. Run it after touching `src/agentctx/experiments/` or
  `src/agentctx/benchmarks/`.
- Agent timeouts above 2 h need a longer task container: mini-swe-agent's
  `DockerEnvironment` keeps the container alive with `sleep <container_timeout>`
  (default `2h`), after which every command fails with "no container with name
  or ID" until the step limit. Set `environment.container_timeout` in the agent
  config above `AGENT_TIMEOUT` (`configs/config-devstral-vllm-temp0.yaml` has
  `"5h"` since 2026-10-31; the 90-min default of the other launchers is safe).
- Event log (failure analysis): the SWE-bench adapter
  (`src/agentctx/benchmarks/swe_bench.py`) sets `MSWEA_EVENT_LOG_DIR` so each
  run dir also gets `events.jsonl` (every message as added, before
  compression, with a stable `extra.uid`) and `compression_events.jsonl`
  (per event: dropped/replaced/added uids, summary text, before/after uid
  order). `scripts/maintenance/reconstruct_context.py <run_dir> [--step N]
  [--event K]` replays them and verifies against trajectory.json /
  token_log.json. Runs before 2026-09-23 only have the final trajectory.
  Since 2026-10-11 the same dir also gets `summary_attempts.jsonl`: every
  summarizer reply verbatim (accepted or rejected, with the rejection reason,
  `outcome` accepted|retry|fallback, finish_reason, usage, provider response
  id, the model's reasoning when returned, and the cleaned summary when
  accepted); written by `request_summary` in `primitives.py`
  (`MSWEA_SUMMARY_ATTEMPT_LOG` names another file, `0` disables).
- Physical-resource log: `src/agentctx/resource_monitor.py` samples, while
  the SWE-bench adapter waits for the agent subprocess, the agent process
  tree's RSS, the task container's cgroup memory (name taken from
  `agent.log`), `nvidia-smi` per GPU and the vLLM `/metrics` KV-cache usage
  of the endpoints in the config chain and of a separately served summarizer
  (`MSWEA_SUMMARY_MODEL_CONFIG` / `MSWEA_SUMMARY_API_BASE`; every 10 s,
  `AGENTCTX_RESOURCE_SAMPLE_S`)
  into `<run_dir>/resource_log.jsonl`, and adds `peak_agent_rss_mb`,
  `peak_container_mem_mb`, `peak_gpu_mem_used_mb`, `mean_kv_cache_usage_pct`
  etc. to the run's row in `experiment_results.json`. GPU and vLLM figures are
  machine-wide (shared by concurrent runs). It also writes
  `<run_dir>/serving_info.json` once per run: the endpoints' `/v1/models` and
  `vllm:cache_config_info` labels plus the startup lines of the live vLLM
  logs ("GPU KV cache size: N tokens", "Available KV cache memory", ...; the
  periodic usage lines are kept apart, last few only), so
  a run's per-step context length (`step_prompt_tokens` in token_log.json)
  can later be converted into the KV-cache MB it occupied.
  `AGENTCTX_RESOURCE_MONITOR=0` disables it. `run_info.json` / `run_info.md`
  record `resource_monitoring_enabled`, `resource_monitoring_supported` and
  `resource_sample_interval_s` (configured interval, including when OFF).
  Each new `experiment_results.json` row retains these settings and adds
  `resource_monitoring_started`: whether the sampler was started, not whether
  every probe succeeded. To tell whether a row was sampled, check
  `resource_monitoring_started`, not the presence of these keys (the settings
  are written to every new row, sampled or not). Existing rows are not
  backfilled on resume; absent fields mean unknown, not OFF. `run_info`
  describes the latest launch, so use individual rows for comparisons across
  resumed launches. Terminal-Bench has no periodic sampler and records
  supported/enabled/started as false and the interval as null.
  These flags do not describe the separate server-side KV ownership tracer.
  Runs before 2026-09-27 have no resource data.
- Per-request KV-cache ownership (on by default, `src/agentctx/KV_CACHE_TRACE.md`):
  every `scripts/serving/start_vllm_*.sh` installs
  `agentctx.vllm_kv_trace.TracingScheduler` (`--scheduler-cls`), which logs
  each live request's exclusive vs. shared physical blocks on every scheduler
  change to `kv-cache-<pid>-<uuid>.jsonl` in `logs/kv-cache/<server log name>/`
  (`AGENTCTX_KV_TRACE_DIR` overrides the dir, `AGENTCTX_KV_TRACE=0` turns it
  off; servers launched before 2026-10-03 traced only when the dir was set). `python -m agentctx.kv_cache_trace
  <run_dir> --trace-dir <dir>` joins them to agent steps
  (`model_call_records[].response_id`) and summarizer calls
  (`summary_outcomes[].response_ids`) into `<run_dir>/kv_cache_steps.json`.
  Caveats: shared = simultaneous co-ownership only; peaks are not
  simultaneous; bytes are per TP shard. Runs before 2026-09-29 have no
  response ids.
- `ICLR_experiments/plotting/` — ICLR figure code: `plot_bank.py` is the
  single file holding every renderer (shared style, Figure 1 schematic,
  Figures 2-5, appendix companions, the former `paper_figures.py` and
  `appendix_*.py` tools as `plot_bank.py <tool>` sub-commands; `--help`
  documents each) and the audited Q3 exports
  `q3_combined_*.csv` that Figure 5 reads. Rendered figures (PNG) and their
  value CSVs go to `ICLR_experiments/plotting/plots/` (gitignored).
- `ICLR_experiments/` — canonical ICLR run data and records: `SOURCE_OF_TRUTH.md`
  (paper target and source-of-truth table; it wins over every other doc), the
  experiment plan/grid (`FOLLOWUP_EXPERIMENTS.md`), `EXPERIMENT_LOG_{SWE,TB}.md`
  (bugs and audits are sections of the SWE log), `BUDGET_CALIBRATION.md`,
  `open_issues/` (still-open data audits with their scripts), `reeval_evidence/`
  (re-evaluation manifests and verdicts), `archive_provenance/` (notes, task
  lists and tooling for run data retired to the gitignored `archives/`) and
  `plotting/` (figure code, see above).
- `Review1/` — analysis suite. `Review1.csv` is the central data file. Scripts:
  `sanity.py`, `paired_analysis.py`, `routing_evidence.py`,
  `predictability_sprint.py`, `winners_table.py`, `plot_review1.py`,
  `plot_depth_outcomes.py`.
- `task_lists/` — pinned task JSONs (the 100-task set, the 6-task staggered
  pilot, etc.).
- `exp_plans/` — HANDOFF_COHERENCE (current direction), PRIOR_WORK_MLSys,
  DOBBY_PLAN, ALBUS_PLAN, CHARACTERIZATION_PAPER_PLAN_100tasks. Retired plans
  live in git history or `~/agentCtx_attic/exp_plans/`.
- `logs/` — gitignored. Shell launchers write
  `logs/experiments/<name>_<timestamp>.log` (+ `<name>.latest.log` symlink,
  locks, pid files) and vLLM servers write `logs/servers/vllm_<name>_<timestamp>.log`
  (+ `vllm_<name>.pid`); the outermost script owns the file through
  `scripts/lib/logpaths.sh` (`experiment_log`, `emit`, `AGENTCTX_LOG_FILE`).
  `scripts/notify_run.sh` wraps any launcher with Slack notices and
  detaches by default. Data directories under `logs/` (`harbor_jobs/`, ...)
  are separate.
- `Active_runs.md` — live status of long-running experiments. Update on
  launch/kill/completion.
- `COVERAGE.csv` — auto-generated cell-coverage sheet (one row per
  observed benchmark × model × primitive × budget × depth, with scope and
  status. Dirty/archived data is excluded; fresh Terminal-Bench data is read
  from its canonical path. Regenerate with
  `python dashboard/build_coverage.py` (then `dashboard/build_dashboard.py`)
  after any run completes or Review1.csv is rebuilt.

## Vocabulary

Use these terms when discussing experimental coverage and depth runs.

**Primitive families** (mechanistic split by whether `compression_ratio` engages):

- **depth-tunable** — TR, SU-full, SU-partial, SS, SS-partial. The 5
  primitives whose behavior is a function of `compression_ratio`. Studied at
  all 3 depths.
- **depth-invariant** — TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial,
  OTRC+SS-partial, SU-free, SS-free. The 8 primitives where `compression_ratio`
  doesn't engage meaningfully. Studied at canonical depth only. SU-free /
  SS-free (`summarization-free`, `structured-summarize-free`) are SU-full / SS
  with no word target in the summarizer prompt ("concisely" only); depth only
  sizes their truncate fallback.

**Depths:**

- **canonical depth** = 0.5 (default; the only depth in scope for
  depth-invariant primitives).
- **tail depths** = 0.3, 0.7 (studied for depth-tunable primitives only).
- **depth grid** = {0.3, 0.5, 0.7} (the symmetric 3-point set).

**Cohorts:**

- **ABL-30** — original 30 FC-stratified ablation tasks
  (`results/ablations/tasks.json`).
- **NEW-70** — the 70 added tasks (`task_lists/p100_new_tasks.json`).
- **P100** — full cohort = ABL-30 ∪ NEW-70
  (`task_lists/swe_verified/p100_all_100_tasks.json`).

**Scope rule** (main model = Qwen3.5-35B-A3B) for whether a
`(primitive, budget, depth, cohort)` cell is in-scope for the paper:

- `depth-tunable` × `depth grid` × cohort ⊇ {P100 if budget=15k, ABL-30 if
  budget ∈ {10k, 20k}}.
- `depth-invariant` × `canonical depth` × **P100 at every budget**.

Any other `(primitive, depth, budget, cohort)` combination is **out-of-scope**
and not run. Model-expansion runs on Albus (Qwen2.5-7B, Llama 3.3 70B) follow
their own reduced-cohort scopes documented in `exp_plans/ALBUS_PLAN.md`.

## Critical rules

- **Never commit** `results/`, `logs/`, `archive/`, `temp/`, `Review1/raw/`,
  `PaperSections/`, `figures/`, `Review1/figures/` — all gitignored.
- **Always update** `Active_runs.md` when launching or killing a long-running
  experiment.
- **Submodule updates**: `cd mini-swe-agent`, commit + push there first
  (branch `event-log` on takeshiho0531/mini-swe-agent while the upstream PR is
  open), then `git add mini-swe-agent` in parent
  to record the new pointer.
- **Don't write to `PaperSections/`** files without showing the user the draft
  content in chat first.
- **Don't propose routing/cascade as a paper direction** — user has called
  these dead ends.
