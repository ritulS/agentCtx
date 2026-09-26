# Devstral summary conditions: consistency audit of original runs and reruns

Scope: SWE-bench main, 21K, D=0.5, SU-full / SU-partial / SS / SS-partial / TRC+SU / TRC+SS. Each condition contains 100 tasks × 3 runs, for 1800 records in total. All times are CDT. Ablations and OTRC variants are outside the scope of this audit.

## Conclusions

No evidence was found that would justify regenerating all runs. However, 241 records require evaluation only: 224 reused stale evaluation reports for patches that differ from the current patches, 14 encountered evaluation container image state errors, and 3 encountered evaluation timeouts. Current success rates should be treated as provisional until reevaluation is complete. Generation time and token counts are separate from the evaluation cache issue.

Existing experiment_results.json, trajectory, token_log, agent.log, and outcomes.csv files were not modified. No generation, evaluation, or server startup was performed.

| Condition | Original results retained | 9/9–10 reruns | Retained runs with summary calls | Stale evaluations with mismatched patches | Evaluation environment failures/timeouts | Total reevaluation candidates |
|---|---:|---:|---:|---:|---:|---:|
| SU-full | 59 | 241 | 1 | 89 | 3 | 92 |
| SU-partial | 62 | 238 | 0 | 10 | 3 | 13 |
| SS | 79 | 221 | 17 | 68 | 2 | 70 |
| SS-partial | 82 | 218 | 24 | 37 | 3 | 40 |
| TRC+SU | 250 | 50 | 0 | 10 | 3 | 13 |
| TRC+SS | 255 | 45 | 1 | 10 | 3 | 13 |

## Generation checks

- All 1800 records cover the complete set of 100 tasks × runs 1/2/3, with no duplicate keys. Token counts, arrays, LLM time, and compression records agree between the result index and token logs; trajectory call counts and exit states also agree. Prompt and time aggregation formulas are consistent. Index SHA256 hashes and the size/mtime of 1800 × 3 files remained stable before and after reading.
- Reconstructing and comparing the original archived results showed a maximum concurrency of 16 per condition for both original runs and reruns. Start times were reconstructed as timestamp−e2e, excluding the first 1 second after each start to avoid boundary errors from rounding and record persistence. This is not a direct CLI configuration record, but it also agrees with the launcher default of 16.
- Only 1 shared launcher log was aggregated. Original runs have 300 completion lines per condition; reruns have 241/238/221/218/50/45, with 0 duplicate keys within each launch. Reappearances of the same cell names on 9/3–4 show all runs already complete and 0 executed, rather than duplicate generation.
- Current and pre-archive Devstral main/ablation records showed no evidence of attempts in other cells overlapping the generation windows of the 6 audited conditions. This does not establish the absence of unrecorded processes or other users' jobs.
- Configurations stored in the trajectories agree between the 1800 current and 1800 original records. Output paths and task-specific images were excluded from the configuration comparison; image names were checked separately for each matching task/run and agreed. Shared settings include system/instance prompts, model config, temperature=0.2, max_tokens=4096, localhost:8002, step_limit=125, and environment settings. Current budget=21000 and compression_ratio=0.5 also agree. mini_version is 2.2.6. Matching image tags do not prove matching image digests.
- All 1800 agent.log files were audited again using the structural and step-accounting checks in the existing attribute_agentlog.py. All were classified as no_summary_evidence, with no evidence of null bytes or multiple processes. This classification means no errors were observed; it is not complete proof for every call.
- The 787 retained original results are unchanged from the pre-archive index records except for backfilled step_completion_tokens. Of these, 744 have summarization_prompt_tokens=0. The other 43 have successful summary calls, with no evidence of summary FormatError. In TRC+SU/SS, compression_events can increase from TRC alone and should not be confused with the number of summary calls.
- The Git diff shows that summary fix f669241 disables the action parser for summary calls. It does not change ordinary agent calls or the content of summaries that returned successfully under the old version. The generation runner diff only adds persistence of step_completion_tokens. A simple comparison of original-run and rerun averages is biased by selection for the bug, task difficulty, and compression frequency, and cannot be interpreted as a difference in server speed.

## Server

The 9/9 logs confirm vLLM 0.17.1, TP=4, max_model_len=65536, max_num_seqs=64, prefix caching=True, chunked prefill=True, and max_num_batched_tokens=2048. Samples from the audited period show a maximum Running+Waiting of 16, maximum KV utilization of 18.0%, and displayed prefix hit rates of 79.9–97.5% while non-idle. These hit rates are server aggregates, not exact cache rates for individual conditions. vLLM startup logs for the original runs are unavailable, so the vLLM version, effective prefix cache settings, GPU load, and model revision at that time cannot be established. There are no Git differences in the startup scripts or agent config, but full equivalence of the effective environments remains unproven. Uncommitted changes for DOCKER_HOST support also prevent complete reconstruction of the original and current container endpoints.

## Evaluation issues

The audit checked 1495 records with patches. Of these, 1227 have report.json files created after the attempt, matching the current patches and verdicts. In 224 records, patch.diff associated with an old report.json differs from the new submission. Another 24 reuse old report.json files with exactly matching patches. There are 20 records without report.json: 14 have Docker/Podman image state 409 errors, 3 have 600-second evaluation timeouts also recorded by the launcher, and the remaining 3 have Patch Apply Failed for the current patch and can be retained as ordinary failures.

All 17 container failures/timeouts concern scikit-learn__scikit-learn-14710. Of these, 14 are recorded as False and 3 as null; unevaluated attempts should not be conflated with failures to solve the task. The image inconsistency must be resolved before reevaluation.

Cause: scripts/bench_adapters/swe_bench.py invokes the harness with the same run_id and model tag even after saving a new prediction. When report.json already exists, the installed swebench/harness/run_evaluation.py treats evaluation as complete and returns the existing verdict without comparing patches. A newly written top-level eval/*.json file alone does not prove that evaluation was rerun.

Example: d05__b21k__su-full / django__django-11292__summarization__r1 has generation timestamp 2026-09-09T15:37:44.489796, while its internal report.json is dated 2026-08-31T09:44:19.960703. patch.diff differs from the new submission, and the current resolved=True agrees with that old report.

Some runs without patches still have stale top-level eval files, but they are excluded from these candidates. Use the current index as the reference and do not fill in resolved values from stale eval files.

## Recommended next steps

1. Rerun evaluation only for the 241 records in reevaluation_candidates.csv. Regeneration is unnecessary. Use a new run_id or an isolated evaluation output directory to prevent existing reports from causing evaluation to be skipped. Update the index only after confirming that evaluation used the existing current patch.
2. Optionally add the 24 records that reused old reports for identical patches if evaluation timing must also be standardized strictly. These are not included in the required candidates.
3. Regenerate outcomes.csv and figures after evaluation is complete. Neither was updated during this audit.

## Outputs

- runs.csv: Generation checks for 1800 records, original/rerun classification, log classifications, and configuration hashes.
- launches.csv: All launcher appearances and execution counts for the audited conditions.
- server_metrics.csv: Server observations during the rerun period.
- summary.json / extra_checks.json: Aggregates, configurations, and supplementary checks. eval_mismatch in extra_checks.json is a preliminary check that also compares null values for runs without patches against stale top-level reports. Use evaluation_classification.csv for final classifications.
- evaluation_checks.csv / evaluation_classification.csv: Internal report, prediction, and patch comparisons and final classifications for the 1495 records with patches.
- reevaluation_candidates.csv: The 241 records requiring evaluation only.
- audit_generation.py / audit_extra.py / classify_evaluation.py: Diagnostic scripts used for this audit. Experiment inputs are read only.
