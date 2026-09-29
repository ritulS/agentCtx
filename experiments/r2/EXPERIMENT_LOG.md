# r2 Experiment Log

Second campaign, after the ICLR 2027 submission. Runs live under `data/r2/`;
the ICLR runs stay frozen under `data/iclr26/` (currently
`ICLR_experiments/{swebench,terminalbench}`).

Entries record code as it was at the time.

## 2026-09-26 — Summary cleaning, validation and structural tagging

Commits: `56a4093` (cleaning, validation, retry, tag; submodule `65659cb`
for the online TRC) and the following commit (outcome tracking; submodule
`9ca02a0`). Submodule commits are on `event-log` of
`takeshiho0531/mini-swe-agent`, not yet pushed.

Origin: `ICLR_experiments/open_issues/resume_audit_20260908/` found the
model's inline `</think>` preamble on 219/220 saved structured summaries,
and 33 runs where the agent produced another summary right after one. The
preamble hid the marker line from TRC's `content.startswith` guard, so
summaries could be cleared as tool output. Whether the preamble caused the
re-summarizing is a hypothesis; the audit could not confirm it.

Reference implementations checked before designing the fix: Terminus 2
(`harbor.agents.terminus_2`) and the OpenHands SDK
(`openhands.sdk.context.condenser`). Both separate reasoning at the LLM
layer (`reasoning_content`, i.e. a server-side reasoning parser) and identify
summaries structurally (fixed slot in the chat / typed `Condensation` event),
not by parsing content; neither validates the summary text. Our vLLM servers
run without a reasoning parser (mini-swe-agent parses raw text), so the
separation has to happen in the primitives.

Changes (`src/agentctx/compression/primitives.py`, "Summary message handling"):

- `clean_summary_text(raw, open, close)` normalizes newlines, recognizes
  markers only as standalone lines, removes the reasoning preamble per
  `_reasoning_end()` (a response opening with `<think>` ends at the first
  `</think>`; a `</think>` with no marker line before it is an implicit-open
  preamble; a marked body that quotes `</think>` is left intact), extracts
  the body from the marker spans and re-wraps it in the canonical markers.
- Validation is separate from marking: rejected as `empty_body`,
  `unterminated_reasoning` (open `<think>` never closed) or
  `ambiguous_reasoning` (`</think>` present but no marker line, undecidable).
- `request_summary()` re-queries with the same prompt up to
  `MSWEA_SUMMARY_MAX_ATTEMPTS` (default 2); when every attempt is rejected,
  SU / SS / SU-partial / SS-partial fall back to `truncate()` instead of
  replacing the history with a non-summary.
- SU now asks for `[COMPRESSED HISTORY SUMMARY]` / `[END SUMMARY]` marker
  lines, like SS asks for `[CONTEXT SUMMARY]` / `[END CONTEXT SUMMARY]`.
- Summary messages carry `extra.kind = "summary"` and
  `extra.summary_format` (`had_think_preamble`, `had_open_marker`,
  `had_close_marker`, `rejected`, `attempts`). `is_summary_message()` checks
  the tag first and the marker prefix second (old trajectories). Used by
  `tool_result_clear`, `scored_tool_result_clear` and the online TRC in
  `mini-swe-agent/src/minisweagent/agents/default.py`.
- Tracking: every summary request leaves a `summary_outcome` record
  (`attempts`, `accepted`, `rejections`, `fallback`) that the agent stores in
  `compression_events.jsonl` (per event, `null` when no summary was
  requested) and in `token_log.json` (`summary_outcomes`,
  `summary_fallback_events`). `scripts/maintenance/reconstruct_context.py
  --event K` prints it.

Not changed: `truncate()` still drops summaries like any other compressible
message (TR semantics). vLLM reasoning parser stays off; enabling it
(`--reasoning-parser`) would also strip the agent's own thinking from the
history and is a separate ablation decision.

Known limit: a summarizer reply with no marker line that contains `</think>`
is rejected rather than guessed at; if the summarizer ignores the marker
instruction often, fallbacks rise. `summary_fallback_events` shows the rate.

Tests: `tests/test_summary_cleaning.py` (38 tests, FakeModel; run with
`uvx --with tiktoken --with pyyaml pytest tests/test_summary_cleaning.py`).

Open: whether the re-summarizing loop disappears in real runs. Check the
first r2 SS / SS-partial / TRC+SS / OTRC+SS-partial pilot for FormatErrors
following a summary, and the `rejections` / `fallback` counts.

## 2026-09-27 — Summary retries raised to 5; length-free summaries (SU-free / SS-free)

- `SUMMARY_MAX_ATTEMPTS` default 2 → 5 (`MSWEA_SUMMARY_MAX_ATTEMPTS` still
  overrides). The truncate() fallback now needs five consecutive rejected
  summarizer responses. Re-scoring the iclr26 Qwen3.5 summaries with the
  current rules under a reasoning-parser view gave a per-attempt rejection
  rate of 1/4559 (SU) and 0/4048 (SS), so with the parser on the fallback is
  effectively unreachable; without the parser (`REASONING_PARSER=none`) 91–100 %
  of those responses would be rejected (`ambiguous_reasoning`).
- New primitives `summarize_free` / `structured_summarize_free`
  (conditions `summarization-free` / `structured-summarize-free`, labels
  SU-free / SS-free): same call, cleaning and retry as SU-full / SS, but the
  prompt asks for a *concise* summary with no word target, so
  `compression_ratio` never reaches the summarizer. Classified
  depth-invariant; depth only sizes the truncate() fallback, as for TRC.
  Summary messages carry `summary_format.length_free = true`.
  SU / SS prompt construction moved into shared `_su_prompt` / `_ss_prompt`
  helpers (prompts byte-identical to before; `tests/test_summary_free.py`).

## 2026-09-26 — SWE-bench Verified per-run limits: 300 steps, 5400 s

`src/agentctx/experiments/runner.py`: `STEP_LIMIT` 125 → 300,
`AGENT_TIMEOUT` 1500 → 5400 s (~18 s/step, the same ratio plus headroom).
The SWE agent configs (`configs/config-{qwen-vllm,qwen-vllm-8002,devstral-vllm,
glm47flash-vllm,glm47flash-vllm-8004,fc-customprompt}.yaml`) carry
`step_limit: 300` for consistency; the runner passes `-c agent.step_limit=`
anyway. New flags `--step-limit` / `--agent-timeout` override per launch, and
`run_info.json` now records `agent_timeout_s` next to `step_limit`.

Why: in the 2026-09-08 audit 152/645 resumed Qwen runs (23.6 %) were killed
by the 1500 s limit, with almost all of the time spent in LLM latency; the
FC∞ "15 min – 1 hour" analysis attributed 45/98 failures to the timeout and
10 to the 125-step limit. Terminal-Bench limits are unchanged.

Consequence: r2 SWE-bench runs are not comparable to `iclr26` on
timeout / step-limit outcome classes. `tests/test_runner_equivalence.py`
compares against the pre-reorganization reference tree, which still has the
old limits, so the SWE scenarios now differ by design on `step_limit` /
`agent.step_limit=` (on top of the earlier `MSWEA_EVENT_LOG_DIR` difference).

## 2026-09-26 — vLLM reasoning parser on by default (Qwen3.5, GLM-4.7-Flash)

`scripts/lib/vllm_reasoning.sh` adds `reasoning_parser_args <default>`; the
serving scripts now pass `--reasoning-parser qwen3` (Qwen3.5-35B-A3B and 9B:
`start_vllm_qwen35_{prefix_cache,no_prefix_cache,no_prefix_cache_gpu4-7,
prefix_cache_ablation,swe_summarizer_ablation}.sh`, `start_vllm_qwen35_9b.sh`,
`start_vllm_summarizer.sh qwen35-9b`) or `--reasoning-parser glm47`
(`start_vllm_glm47flash.sh`). `REASONING_PARSER=none` reproduces the iclr26
serving; `REASONING_PARSER=<name>` picks another parser. Devstral (no thinking
in its template) and Gemma-4 (thinking off) are unchanged.

Why: the summarizer preamble fixed above was a symptom of the server
returning the whole "<think> ... </think>" span in `message.content`. With the
parser, vLLM moves the reasoning to `message.reasoning_content`; litellm and
mini-swe-agent keep that field on the stored message, and the Qwen3.5 / GLM
chat templates read `reasoning_content` back the same way they read inline
think tags (dropped for turns before the last user message), so the prompt
the model sees is unchanged.

What changes in the runs, and must be kept in mind when reading r2 numbers:

- `count_tokens()` counts `content` only, so the budget trigger no longer
  counts thinking. Compression fires later at the same nominal budget;
  `BUDGET_CALIBRATION.md` was done with thinking included.
- The summarizer's input (`history_text`) no longer contains the agent's
  thinking.
- Action parsing (`_parse_actions` on `content`) no longer sees code blocks
  written inside thinking, so FormatError rates may drop for that reason
  alone.
- A reply truncated inside its thinking arrives as empty `content`
  (`reasoning_content` holds the partial thinking) instead of thinking-only
  content; both are a FormatError with 0 actions.
- `trajectory.json` assistant messages gain a `reasoning_content` field, so
  the thinking is still on disk for analysis.

Verification so far: stub dry runs of the scripts show the argument on the
command line for the defaults, for `REASONING_PARSER=none`, and for both
summarizer presets. Not yet verified against a live server: that vLLM 0.17.1
accepts `reasoning_content` on assistant messages sent back by
mini-swe-agent, and that `summary_format.had_think_preamble` drops to ~0.
Do this on the first r2 smoke run before launching a cohort.


## 2026-09-27 — First r2 P30S cells (SU-free, FC, SS-free): two bugs, SU-free re-run

Code: the runs used the r2 launcher committed as `f69bc47` (uncommitted at
launch, on top of `55d3934`). Fixes: eval wrapper `21f3df0`, missing-marker
rejection `fca4779`; the SU-free re-run uses `fca4779` or later. Results:
`data/r2/swebench/p30s/qwen35b/<cell>/`. Log of the first launch:
`logs/experiments/r2_swebench_p30s_qwen35b-chain_20260927_031839.log`.

### The runs

Chain `di__b15k__su-free` → `di__binf__fc` → `di__b15k__ss-free`, P30S
(`task_lists/p30_swe_stratified.json`) × 3 runs = 90 runs per cell, 16
workers, 300 steps / 5400 s, SWE-bench eval after each cell. Qwen3.5-35B-A3B
on :8000 with prefix caching on, native max-model-len (262144) and
`--reasoning-parser qwen3`; the agent model is also the summarizer.
Agent phase 03:18–09:45 CDT; all 270 runs finished (two FC runs of
`scikit-learn-14087` hit the 5400 s wall clock, returncode -1).

### Bug 1 — every SWE-bench eval failed (rootless podman `lchown`)

Symptom: all 242 patches (su-free 77, fc 85, ss-free 80) ended with
"Eval harness error (no verdict; will be retried)". Every harness report had
the instance under `error_ids`.

Cause: `run_instance.log` shows `put_archive` of `/tmp/patch.diff` failing
with `lchown /tmp/patch.diff: invalid argument`. The harness's
`copy_to_container` tars the file with `tarfile.add`, which records the host
uid/gid (AD uid 1741623211). Rootless podman here has a single-UID user
namespace (no subuid range) and cannot chown to it. The old venv
(`~/ICLR27/agentCtx/venv`) carried a venv-local patch in
`swebench/harness/docker_utils.py` that zeroed uid/gid; the venv of this
clone was rebuilt from `requirements.txt` on 2026-09-27 02:40 and lost it.
The smoke test did not catch it: its only run had no patch, so it evaluated
nothing.

Fix: `scripts/swebench_eval_wrapper.py` now replaces
`swebench.harness.docker_utils.copy_to_container` (and the name bound in
`run_evaluation`) with the same function plus a tar filter that sets
uid/gid to 0 and clears uname/gname. It lives in the repo, so it survives
venv rebuilds; it is harmless under Docker. Verified by evaluating
`django__django-15368__summarization-free__r1` by hand (resolved).

Re-eval: relaunched the same chain at 15:01 (`ALLOW_NO_SLACK=1`; log
`..._chain-eval_20260927_150134.log`). The agent phase skipped all 90 keys
per cell and `--eval-only` re-evaluated. su-free finished with 0 harness
errors. Stopped at 16:03 on request (see below), with fc at 36/90 evaluated.

### Bug 2 — marker-less summarizer replies accepted as summaries

Symptom: in the SU-free cell, 76/245 summaries came from replies with no
marker line (`summary_outcome.flags.had_open_marker = false` in
`compression_events.jsonl`). Most were not summaries: the summarizer
continued the transcript as the agent. Example, django-15957 run 1, step 193,
the whole stored summary:

    [COMPRESSED HISTORY SUMMARY]
    ```mswea_bash_command
    cd /testbed && python test_reproduce.py
    ```
    [END SUMMARY]

The agent's entire compressible history was replaced by that one command.
The markers around it were added by `clean_summary_text`, which re-wraps
accepted bodies; the model did not write them.

| Raw reply | Content | SU-free | SS-free |
|---|---|---|---|
| no marker | a single bash block | 18 | 14 |
| no marker | starts as transcript (`[assistant]:`, `[user]:`, bash block) | 45 | 54 |
| no marker | looks like a summary | 13 | 15 |
| marker | a single bash block | 4 | 0 |
| marker | starts as transcript | 4 | 0 |
| marker | looks like a summary | 161 | 169 |

Runs with at least one marker-less summary: su-free 38/90 (19 tasks, all 3
runs for 8 of them), ss-free 40/90. In su-free those runs resolved 13/38,
the rest 39/52. 8 of the 13 su-free LimitsExceeded runs had a bare-command
summary.

Cause: rule 4 of `clean_summary_text` accepted a reply with no marker line
and no `</think>` as an "unformatted body". Without a reasoning parser, a
Qwen reply that ignored the marker instruction still carried the inline
`</think>`, so it was rejected as `ambiguous_reasoning` and retried; the
iclr26 SU-full cell (qwen35b, d05, 15k) has 0 bare-command summaries in
259. With `--reasoning-parser qwen3` (2026-09-26 entry above) the reasoning
is stripped server-side, the reply has no `</think>`, and rule 4 let it
through. The 2026-09-27 re-scoring that found a 1/4559 rejection rate under a
parser view used these same rules, so it counted such replies as accepted
and could not see this.

Not specific to the length-free prompt: two failing windows rebuilt from
`events.jsonl` and sent to the live server gave an agent continuation in 3/3
samples each, both with "concisely" and with "in approximately 600 words".
`chat_template_kwargs.enable_thinking=false` did not help. Moving the
instruction after the history (history wrapped in `<history>` tags) gave
the marker in 6/6 samples, but the bodies still copied the transcript; not
adopted.

Fix (`src/agentctx/compression/primitives.py`): a reply with no marker line
is rejected as `missing_marker` (an empty reply stays `empty_body`), which
feeds the existing path: up to `SUMMARY_MAX_ATTEMPTS` (5) re-queries, then
the `truncate()` fallback. Module comment and docstring updated.
`tests/test_summary_cleaning.py`: two tests rewritten for the new rule, three
added (the observed bare-command and fabricated-tool-output shapes, and a
close marker alone); 43 tests pass with
`venv/bin/python -m unittest tests.test_summary_cleaning tests.test_summary_free`.
Live check: `summarize_free` on the two failing windows through the real
model object gave `rejections = 5 × missing_marker`, `fallback = "truncate"`.

Known limits:
- These two windows fall back to truncate every time: at temperature 0.2 the
  retries return the same reply. Expect more `fallback: "truncate"` events
  in SU-free / SS-free than before; count them from `compression_events.jsonl`.
- Replies that write the marker and then continue as the agent (8/245 in
  su-free) still pass.
- Only r2 data is affected: nothing else ran with summaries after the parser
  change (2026-09-26 23:33). iclr26 ran without the parser.

### What was moved, and what is re-run

Moved on 2026-09-27 to
`archives/r2_p30s_qwen35b_free_missing_marker_20260927/` (original relative
path kept below it, `README.md` there): `di__b15k__su-free` (evaluated, 52
resolved / 38 unresolved) and `di__b15k__ss-free` (not evaluated). Both
cells are moved whole. Re-running only the affected runs would bias the cell:
the unaffected runs are the ones that happened not to draw a marker-less
reply, and they resolve far more often, so a partial re-run would count them
twice in effect.

- **SU-free:** re-run in full (90 runs) with the fix.
- **SS-free:** archived, not re-run for now.
- **FC:** unaffected (no summaries); kept in place. Eval stopped at 36/90
  (23 resolved); the other 54 are `resolved: null` and are picked up by
  running the `fc` preset again (agent phase skips, `--eval-only`
  evaluates the rest).

`run_info.json` records no commit, so runs are tied to code by launch time
against the commits above.

## 2026-09-29 — Unclosed-think replies: action taken from `reasoning_content`

Submodule `mini-swe-agent` (branch `event-log`): `LitellmTextbasedModelConfig`
gains `unclosed_think_fallback: bool = True`; `actions_text.py` gains
`find_regex_actions` / `count_regex_actions`. Parent: this entry only.

Why: the audit of r2 P30S run1 (`experiments/r2/audits/r2_p30s_run1_20260928/`)
found 800 FormatErrors in 13,193 agent calls. 444 of them had
`finish_reason == "stop"`, empty `content` and a non-empty
`reasoning_content`; every one of the 444 ends with a code block and 420 hold
exactly one `mswea_bash_command` block (median 83 completion tokens, 31
contain "THOUGHT:"). These are complete answers, not thinking cut short:
the Qwen3.5 chat template opens the reply with `<think>\n`, the model wrote
its answer without ever emitting `</think>`, and vLLM's qwen3 parser files a
reply with no `</think>` as "truncated, all reasoning" even at
`finish_reason == "stop"` (`vllm/reasoning/qwen3_reasoning_parser.py`).
Under the iclr26 serving (no parser) the same text was the content and its
command was executed (221 such accepted replies in the old FC cell, see
`thinking_parser_comparison_20260929.md` in the audit dir). The parser
therefore made action parsing stricter than in iclr26; this change restores
the iclr26 acceptance rule for exactly that signature.

Rule (`LitellmTextbasedModel._action_text`): when `finish_reason == "stop"`,
`content` is empty or whitespace, `reasoning_content` is non-empty and holds
exactly one action block, the action is parsed from `reasoning_content`, that
text becomes the stored message `content`, the `reasoning_content` key is
dropped from the message (the raw response stays in `extra.response`) and
`extra.action_source = "reasoning_content"` marks the message. Everything
else is unchanged: a `content` with an action always wins, `finish_reason ==
"length"` replies, zero-block and multi-block reasoning stay FormatErrors,
and replies that had a `content` keep their `reasoning_content`.
`unclosed_think_fallback: false` in the model config restores the 09-26
behaviour.

Not a prompt change: an instruction such as "do not stop inside your
thinking" targets a state the model is not in (it believes it answered), its
effect could only be measured by re-running, and it would change every
cell's condition. Not `enable_thinking: false` (changes the model), not
`REASONING_PARSER=none` (puts thinking back into `content`, so the budget
trigger and the summarizer input change too).

Verification: unit tests in
`mini-swe-agent/tests/models/test_litellm_textbased_model.py` (fallback
applied; not applied for length / zero / several blocks / no reasoning /
malformed content; disabled by config; `query()` rewrites the message and
keeps the raw response). Offline replay of all 13,193 saved r2 P30S run1
responses through the new `_action_text` + `parse_regex_actions`: 800
FormatErrors become 380 (420 recovered from `reasoning_content`; TR 81,
SU-free 97, TRC 159, FC 83), and all 12,393 previously accepted replies are
parsed identically. The replay only re-reads saved responses; it does not
predict the error count of a re-run, since the first recovered reply changes
the rest of the trajectory.

Consequences for the data: this is a harness change. r2 P30S run1 (120 runs,
2026-09-28) was produced without it and is not mixed with runs made after
it; failed calls are not replaced selectively. Every cell of the next
comparison is re-run with the fallback on. The 325 `finish_reason ==
"length"` errors at `max_tokens: 4096` are a separate decision and were not
changed here.

## 2026-09-29 — Archive pre-fallback P30S run_1

Moved `data/r2/swebench/p30s/qwen35b` to `archives/r2_p30s_qwen35b_run1_before_reasoning_fallback_20260929_034952/data/r2/swebench/p30s/qwen35b` at the user's request.
All four cells have 30 run_1 results (120 total); SU-free 17/30, TRC 17/30,
TR 16/30, FC 18/30. Preserved complete cell artifacts and copied the audit
and launch log. Verified all 1,505 files (225,902,483 bytes)
against SHA-256 hashes after moving. See the archive README for restoration
and manifest.json for the inventory. The 12-run reasoning-fallback smoke
remains in place. No new full batch was launched.
