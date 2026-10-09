# r2 P30S Qwen3.5 run1 audit — 2026-09-28

> Archived on 2026-09-29: the source data was moved to `archives/r2_p30s_qwen35b_run1_before_reasoning_fallback_20260929_034952/data/r2/swebench/p30s/qwen35b`. Original paths below refer to the locations at the time of the audit.

Scope: SU-free / TRC / TR / FC under `data/r2/swebench/p30s/qwen35b/`, with 30 P30S tasks × run_1 per condition. Earlier run_1–3 data and smoke runs are excluded.

Launch log: `logs/experiments/r2_swebench_p30s_qwen35b-fixed-run1_20260928_023626.log`. Execution window: 2026-09-28 02:36:26–06:34:24 CDT. No experiment or evaluation processes remained at the time of the audit (the vLLM server was still running). All 120 runs have final verdicts; no execution or evaluation is pending.

| Condition | Resolved | 300-step limit | Non-diff submissions | Format errors / calls | Compression events |
|---|---:|---:|---:|---:|---:|
| d05__b15k__tr | 16/30 | 7 | 1 | 166/4095 (4.1%) | 134 |
| di__b15k__su-free | 17/30 | 3 | 0 | 175/2817 (6.2%) | 74 |
| di__b15k__trc | 17/30 | 6 | 1 | 227/3570 (6.4%) | 691 |
| di__binf__fc | 18/30 | 1 | 3 | 232/2711 (8.6%) | 0 |

## 1. Format errors: reasoning-only output and output limits

There were 800 FormatErrors in 13,193 calls (6.06%), affecting 115/120 runs. All reported "Expected exactly 1 action, found 0". Failed responses are stored in the feedback message's `extra.response` field in `events.jsonl`.

- 444 calls: `finish_reason=stop`, empty `content`, and non-empty `reasoning_content`. Some contain commands in the reasoning field.
- 325 calls: `finish_reason=length`, `completion_tokens=4096`. Content is empty in 323 cases and partially generated in 2.
- 31 calls: `stop` with non-empty content that does not match the required format, such as a `bash` code block instead of `mswea_bash_command`.

These observations indicate a mismatch between model responses with separated reasoning and the required action format, plus truncation at `max_tokens=4096`, rather than server crashes. This audit alone cannot establish whether the cause is a parser defect or the model's output format. Format errors count toward the 300-step limit and incur token usage and latency. FC has the highest rate, 232/2711 (8.56%), which matters when interpreting comparisons across conditions.

## 2. Five source-text submissions failed patch application

The final command was `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat <source>`, submitting text that was not a git diff. These five cases are the only entries in evaluation `error_ids`, and all five logs contain "Patch Apply Failed". They are failures under the current protocol, not infrastructure failures or pending evaluations.

| Condition | Task | Final command |
|---|---|---|
| d05__b15k__tr | sympy__sympy-17318 | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat /testbed/sympy/simplify/sqrtdenest.py &#124; head -20` |
| di__b15k__trc | django__django-12276 | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat /testbed/django/forms/widgets.py &#124; head -400 &#124; tail -30` |
| di__binf__fc | sympy__sympy-15875 | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat /testbed/sympy/core/add.py &#124; head -600 &#124; tail -80` |
| di__binf__fc | django__django-15525 | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat /testbed/django/core/serializers/base.py &#124; grep -n "def build_instance" -A 30` |
| di__binf__fc | django__django-11734 | `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat /testbed/django/db/models/sql/query.py &#124; head -n 1720 &#124; tail -n 20` |

`patch_generated=true` means only that the submission is non-empty (`src/agentctx/benchmarks/swe_bench.py:149–151`). Interpreting it as a count of valid diffs overcounts by five. `Submitted` also does not guarantee resolution or a valid patch.

## 3. Repeated commands and the step limit

17/120 runs reached `LimitsExceeded` at 300 steps (SU-free 3, TRC 6, TR 7, FC 1). All have empty submissions and are counted as failures. No run reached the 5400-second wall-clock timeout.

Notable examples (counts refer to exact command matches across the entire run, not necessarily consecutive executions):

- TRC / django-17084: `grep -n "def.*aggregate" /testbed/django/db/models/sql/compiler.py` ran 253 times. Reached the 300-step limit.
- FC / scikit-learn-14053: the same `sed -n '892,896p' sklearn/tree/export.py` ran 154 times. Also had 84 format errors and reached the 300-step limit.
- TR / scikit-learn-25232: the same command displaying lines 115–125 ran 82 times. Reached the 300-step limit.
- TR / django-15525: the same command displaying lines 325–350 ran 79 times. Reached the 300-step limit.

Compression cannot be established as the cause of these loops; they also occur in FC. See `runs.csv` for the complete per-task data.

## 4. SU-free includes TR when summarization fails

Of 74 compression events, 59 accepted a summary and 15 (20.3%) fell back to truncation after five retries. This occurred in 11/30 runs. Rejection reasons were `missing_marker` 89, `empty_body` 3, and `ambiguous_reasoning` 1, including retries that eventually succeeded. All 59 accepted summaries had an opening marker. Inspection of their beginnings and lengths found none of the short, command-only summaries seen previously; this was not an exhaustive factual-consistency review of the summaries.

The fallback behaves as implemented, but treating SU-free as a pure summarization operation would be inaccurate. `summary_fallback_events` is present in `token_log.json` and is not currently copied into `experiment_results.json`, so aggregation must include it explicitly.

## 5. Consistency of compression, records, and evaluation

- Each condition's 30 tasks match `p30_swe_stratified.json`. All run numbers are 1, with no duplicate keys.
- `Replay.verify()` in `scripts/maintenance/reconstruct_context.py` succeeded for all 120 runs. Event before/after UIDs and token counts, final trajectories, and token logs agree.
- Across all 899 compression events, the primitive matches the condition and `picked=None`. FC has no compression events.
- No compression event exceeded the budget afterward or produced zero or negative token savings. TR also has zero `target_not_met`, `budget_exceeded`, and `zero_reduction` events.
- 293 of TRC's 691 events also used turn truncation. This follows the current policy: clear while retaining the latest three results, then remove complete turns if still over budget.
- For all 103 non-empty submissions, the result JSON, prediction, and evaluation `patch.diff` match exactly. Tests completed for 98; the other 5 failed patch application as described above. The remaining 17 runs reached the step limit without a submission. There are no unexplained evaluation failures.
- Call counts agree with `model_call_records` and the per-step arrays. All 800 format errors have usage records. SU-free's `total_prompt_tokens` equals the sum of `step_prompt_tokens` plus `summarization_prompt_tokens`; adding summary tokens again would double-count them.
- No `model_call_records` entry has `status=error` indicating a transport/API error. Every run has `returncode=0`; `LimitsExceeded` is also caught normally, so return codes alone must not be used to determine success.

## Interpretation and next steps

The data is complete, and there is no evidence supporting wholesale invalidation due to mismatched compression conditions or corrupted logs. However, these results reflect the current harness, including format errors, invalid submissions, repetition, and SU fallback. Differences from one run per task across 30 tasks (FC 18, SU/TRC 17, TR 16) do not establish that one condition is superior.

Before the next comparative experiment, it is worth reviewing reasoning/content handling, the 4096-token output limit, and submission-patch validation. Changes alter the evaluation conditions, so failed cases from this batch should not be selectively replaced. This audit did not modify experiment code, results, or server settings, and did not rerun generation or evaluation.

Artifacts: [runs.csv](runs.csv), [summary.json](summary.json). This audit inspected only local logs and source code.

## Additional checks: how code and configuration contribute

A read-only check of `reasoning_content` using the actual `action_regex` for the 444 calls with empty content and `finish_reason=stop` found exactly one command block in the required format in 420 cases (23 had zero; 1 had 35). Because `_parse_actions()` in `litellm_textbased_model.py` examines only content, these 420 cases were also rejected as having zero actions. The combination of reasoning separation and content-only action extraction is the direct path producing these FormatErrors. The commands' semantic validity and execution success were not verified; executing proposals from reasoning unchanged is not necessarily an appropriate fix. It remains uncertain whether the parser misinterpreted the response or the model omitted final content.

The five invalid submissions originated when the model submitted source text instead of the requested git patch. The exit handler in `environments/docker.py` also marks a run as `Submitted` based only on the completion marker and `returncode=0`, without validating the diff. Under this implementation, the run ends without an opportunity to request a correction. The subsequent evaluation is correct to mark these cases as failures.

Truncation at 4096 tokens is tied to the `max_tokens` setting in `configs/config-qwen-vllm.yaml`. Whether raising the limit improves results has not been tested. The causal relationship between repetition loops and compression is also unresolved. Consistent records therefore do not establish that code and configuration have no effect.
