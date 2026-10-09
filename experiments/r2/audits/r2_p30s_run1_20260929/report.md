# r2 P30S Qwen3.5 run1 Rerun Audit — 2026-09-29

This audit covers 4 conditions × 30 tasks × run_1 under `data/r2/swebench/p30s/qwen35b/`. The latest run took place on **2026-09-29 03:57:42–10:53:44 CDT**. The log is `logs/experiments/r2_swebench_p30s_qwen35b-fallback-32k-run1_20260929_035742.log`. All 120 saved configs were confirmed to have `max_tokens=32768` and `unclosed_think_fallback=true`. Previous runs are stored separately under archives. The statement in Active_runs.md that no new full batch has been run does not match the latest data.

This was an audit only. No experiment code, settings, or source data were changed, and neither generation nor evaluation was rerun.

## Results

| Condition | resolved | Step limit | 5400-second timeout | Invalid submission | FormatError / calls | reasoning fallback |
|---|---:|---:|---:|---:|---:|---:|
| SU-free | 19/30 | 1 | 2 | 0 | 69/2439 | 198 |
| TRC | 18/30 | 1 | 2 | 1 | 98/2560 | 582 |
| TR | 16/30 | 5 | 1 | 0 | 80/3120 | 294 |
| FC | 18/30 | 1 | 2 | 1 | 69/2277 | 729 |

The resolved status is final for every run. The previous run1 resolved counts were SU-free 17, TRC 17, TR 16, and FC 18. Format errors decreased from **800/13193 (6.06%) → 316/10396 (3.04%)**. All 1803 reasoning fallbacks met the conditions of stop, empty content, and a single action, and the stored content matched the original reasoning. There were no cases missed by the fix: zero FormatErrors with stop, empty content, and a single action.

## 1. High priority: a verbatim transcript is accepted as a summary, more than doubling the history

SU-free / `django__django-15957` / compression step 32:

- Input 15,123 → output **31,684 tokens** (using the code's cl100k_base token counts).
- The accepted body contained **133,948 characters**. It was a transcript copy repeating `[assistant]:` / `[user]:` and source code, rather than a normal summary.
- It had an opening marker but no closing marker. It was still marked `accepted=true`. Generation took 573 seconds.
- The next agent call, 33, actually consumed **prompt_tokens=34,153**. The following compression at step 33 reduced the history again, from 31,777→1,773.
- The task's final evaluation was unresolved. This anomaly alone, however, cannot be identified as the cause of failure.

The direct code path:

1. Around `src/agentctx/compression/primitives.py:340`: when the closing marker is missing, the body is taken through the end of the response. There is no validation to reject transcript copies.
2. In the same file at `:420`: `request_summary()` accepts the response based only on the body formatting result, without checking `finish_reason`.
3. In the same file at `:712–716`: `_summarize_free()` measures the length after summarization but accepts the result even if it is longer than the original or exceeds the budget.
4. From `mini-swe-agent/.../agents/default.py:478` onward, the model is called after a single compression. There is no loop to immediately compress again until the history fits within the budget.

An offline fake model reproduced acceptance of a response with `finish_reason=length` containing only an opening marker and a transcript fragment. However, the actual raw summarization API response was not saved, so it is not possible to confirm whether this 133,948-character response had a finish reason of `length`.

SU-free intentionally has no length target. This case combines the absence of a length target with acceptance of even an incomplete transcript copy as a summary. The first priority is to define validation for finish status, markers, and transcript copies, along with the handling of compression failures.

## 2. Aggregated compression savings hide history growth

Because `_summarize_free()` uses `max(0, tokens_before - tokens_after)`, the **16,561-token increase above becomes tokens_saved_reported=0**.

For the same task, `total_tokens_saved=85,848`, whereas the sum of signed per-event differences is **69,287**. Interpreting the former as net savings overstates the reduction by 16,561. The growth is still visible in the event before/after counts and compression ratio; the source data is not corrupted. Aggregation needs to distinguish the sum of positive savings from net savings.

## 3. Generation still hits the 32K limit and contributes to timeouts

Of the 316 FormatErrors, **204 had finish_reason=length and completion_tokens=32768**. The remaining 112 had stop but did not satisfy the required action format (72 with empty content and zero actions in reasoning, 3 with empty content and multiple actions, and 37 with non-empty content but zero actions). There were 325 length errors under the previous 4096 limit.

Output consumption from length errors alone increased from 1,331,200→**6,684,672 tokens** (about fivefold). All 7 timeouts hit the 5400-second limit. Waiting for recorded length errors alone consumed the following time:

| Condition / Task | Length error count | Wait time for length errors (seconds, rounded) |
|---|---:|---:|
| TR / django-15525 | 13 | 4663 |
| SU-free / django-15098 | 10 | 3978 |
| SU-free / sklearn-14087 | 13 | 5124 |
| TRC / django-17084 | 11 | 4650 |
| TRC / django-15957 | 12 | 5002 |
| FC / django-15098 | 12 | 4861 |
| FC / django-11734 | 9 | 3890 |

The previous run had zero timeouts. This comparison involves different trajectories with both the limit increase and fallback changed at the same time, so not all performance differences can be attributed causally to max_tokens alone. However, the logs directly confirm that long invalid responses consumed most of the available time in these runs. Raising the limit alone does not resolve the issue.

## 4. Non-diff submissions are still accepted, ending the run

For `django__django-15525` under TRC and FC, the final command was `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat .../base.py | sed ...`. It submitted a source fragment instead of a patch.

`mini-swe-agent/src/minisweagent/environments/docker.py:145–151` sets Submitted based only on the completion marker and returncode=0. `src/agentctx/benchmarks/swe_bench.py:145–151` sets patch_generated=true for any non-empty string. The agent exits without an opportunity to correct the submission, and both subsequently receive `Patch Apply Failed` in evaluation. This is not an incorrect evaluation verdict. The count decreased from 5 previously to 2 now, but the code issue remains unfixed.

## 5. Saved states diverge on timeout, and the exit reason is empty

Event reconstruction matched exactly for **119/120 runs**. The exception was TRC / `django__django-17084`.

- There were no inconsistencies in pre/post-compression UIDs or token counts within the event sequence.
- The final compression at step 153 (event seq 326) changed 16,238→14,861 tokens and 127→121 messages.
- `trajectory.json` exactly matched the 127 messages **immediately before** that compression. The events and token_log reflected the state after compression.
- `default.py:770` saves only token_log immediately after compression; the trajectory is saved in finally (`:285–289`) when the step completes.
- `swe_bench.py:317–320` calls `process.kill()` on timeout, preventing finally from running. This is consistent with the saved state being left behind before the next model call finishes.

All 7 timeouts also had `exit_status=""` and `returncode=-1`, because the runner does not explicitly map TimeoutExpired to the result's exit_status. The results table confirms these as failures, but classification based only on exit_status misses the timeouts. For a call still unfinished at SIGKILL, local records cannot establish token usage before the response is returned.

## 6. SU-free fallback to TR and repetition

Of SU-free's 63 compressions, **15 (23.8%)** fell back to TR after 5 summarization retries, affecting 9/30 runs. Of the 48 accepted summaries, none lacked an opening marker, and only the case above lacked a closing marker. Inspection of the remaining body lengths and openings found none of the short command-only summaries seen previously, but factual consistency was not verified for every summary.

`summary_fallback_events` / `summary_outcomes` are present in token_log but are not copied to experiment_results. Treating SU-free as pure summarization leads to misleading comparisons. TRC also used turn truncation in 202 of 374 compressions, but this follows its existing design and already has aggregation fields.

Repetition of identical read commands also persists. FC / django-11734 repeated the same sed command 193 times, and FC / django-17084 repeated it 180 times (exact-match counts across the entire run, not consecutive repetitions). They hit the timeout and step limit, respectively. The code has no repetition suppression, and repetition also appears in responses handled through fallback, but the model's own repetition should not be conflated with a code defect. It also occurs in FC, which performs no compression.

## Additional consistency checks

- Each condition exactly matched the 30 P30S tasks, with all run numbers equal to 1 and no duplicates.
- Across all 105 non-empty submissions, the result submission, preds model_patch, and evaluation patch.diff matched. The only evaluation error_ids were the 2 invalid submissions above.
- In every run, n_calls, the model_call_records count, and the step token array lengths matched. There were zero recorded API/transport errors.
- In every run, total_prompt_tokens = sum of agent step prompt tokens + summarization_prompt_tokens. Do not add summarization tokens again.
- The primitive matched the condition in all 542 compressions, with picked=None. FC had zero compressions. The only event exceeding the budget or failing to reduce the history was the SU-free case above.
- There is no evidence that the current fallback fix misses previously accepted single-action responses.

Priority order: acceptance of incomplete summaries → reporting of net compression savings → SWE-bench submission validation → timeout persistence and classification. Measure runaway generation and repetition separately; do not treat a limit change alone as a solution.

Audit outputs: `runs.csv`, `summary.json`, `errors.json`, `summaries.json`, and `replay.json`. Basic aggregation can be rerun with `audit.py` in this directory (uses local workspace paths).
