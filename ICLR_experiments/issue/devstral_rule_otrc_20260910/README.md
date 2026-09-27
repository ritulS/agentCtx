# Devstral TR, TRC, and OTRC family audit (2026-09-10)

Scope: SWE-bench main, TR@21K / TRC@21K / OTRC+TR@21K / OTRC+SU-partial@21K / OTRC+SS-partial@21K / OTRC@∞, each with 100 tasks × 3 runs, for 1800 records in total. Ablations and FC are excluded. All times are CDT.

## Conclusions

No evidence was found that would require regenerating all 1800 current runs. However, 28 candidates require evaluation only: 11 reused report.json files associated with old patch.diff files that differ from the new patches, 16 encountered container image state 409 errors, and 1 encountered an evaluation timeout. Combined with the 241 candidates from the previous SU/SS/TRC+SU/SS audit, there are 269 unique reevaluation candidates. FC regeneration candidates are not included in this count.

| Condition | Current records | 9/10 partial reruns | Reconstructed maximum concurrency | Stale evaluations for different patches | Evaluation environment failures/timeouts | Total reevaluation candidates |
|---|---:|---:|---:|---:|---:|---:|
| TR | 300 | 0 | 16 / — | 0 | 3 | 3 |
| TRC | 300 | 0 | 16 / — | 0 | 3 | 3 |
| OTRC+TR | 300 | 0 | 16 / — | 0 | 1 | 1 |
| OTRC+SU-partial | 300 | 47 | 16 / 16 | 4 | 4 | 8 |
| OTRC+SS-partial | 300 | 36 | 16 / 16 | 7 | 3 | 10 |
| OTRC@∞ | 300 | 0 | 16 / — | 0 | 3 | 3 |

## Generation, configuration, and concurrency

- The set of 100 tasks × runs 1/2/3 agrees across all conditions, with no duplicate keys. Every record contains agent calls. Call counts, exit states, token arrays, compression records, and LLM time agree across the result index, token_log, and trajectory. Prompt and time aggregates are also consistent. Existing structural analysis of agent.log classified every record as no_summary_evidence, with no evidence of multiple processes or null bytes.
- SHA256 hashes of the 6 result indexes and the size/mtime of 5400 run artifacts remained stable before and after reading. Experiment files were not modified.
- Start times were reconstructed as timestamp−e2e. Where necessary, original results were reconstructed to 300 records using pre-archive records. Excluding the first 1 second after each start to avoid boundary errors from rounding and record persistence, the maximum concurrency was 16 for each condition. The 9/10 partial reruns for the 2 conditions also reached 16. This is not direct verification from process argv.
- Current and pre-archive Devstral main/ablation records showed no evidence that generation in other cells overlapped the audited generation windows. This method cannot rule out unrecorded attempts, external jobs, or load from other users.
- The common configurations for TR/TRC and the OTRC family differ only in system_template, reflecting the specialized instructions required by OTRC. All 1200 OTRC-family records have online_trc_clears>0; TR/TRC records have 0. Each cell's primitive, budget (21K or ∞), and depth=0.5 are also consistent.
- Shared settings include temperature=0.2, max_tokens=4096, localhost:8002, agent step_limit=125, and mini_version=2.2.6. The 83 records from 9/10 have configurations and image names matching the archived original trajectories for the same task/run. Output paths and task-specific images were excluded from the configuration comparison; images were checked separately between original and current runs. Matching image tags do not guarantee matching digests.
- OTRC+SU-partial contains 253 original + 47 new records; OTRC+SS-partial contains 264 original + 36 new records. Only 1 of the 517 retained original records has a summary call, and there is no log evidence of summary failure, including in that record. The other 516 have no summary calls.

## TR resume history

The initial launch on 8/31 at 02:00:42 had many failures before startup, with resumes recorded at 02:30 and 02:34. Repeated completion lines alone are not treated as evidence of concurrent duplicate execution of successful attempts.

- The initial block has 261 completion lines: 244 with calls=0 and 17 with calls>0. All 244 calls=0 keys have been replaced in the current index by results from 02:34 onward.
- Current results consist of 21 records from the initial launch (last completion at 02:09:52) and 279 from 02:34:20 onward. The execution windows of these 2 current groups do not overlap, consistent with the resume log's 21 done / 279 remaining.
- Of the 21 current records from the initial launch, 4 cannot be matched directly to completion lines in that initial launcher block. The cause of the missing stdout is undetermined. However, each current run has a single-process structure and consistent index/token/trajectory records.
- This provides no basis for discarding all TR records as if they had the overlapping active jobs observed for FC on 8/29. A strict speed comparison at the same point in time would require a separate small measurement under identical conditions.

## Dedicated OTRC@∞ rerun

The current 300 records span 9/3 13:10:29–15:54:40. The separate logs/devstral24b_p100_otrc_rerun.log contains completion records for 300 runs with 300 unique keys. These were distinguished from the old failed data that the shared launcher reported as fully complete on 9/2. logs/devstral24b_p100_otrc_eval_retry.log covers retries of only 2 evaluations, not duplicate generation.

## Effective vLLM settings

Startup logs from 9/9–10 show vLLM 0.17.1, TP=4, max_model_len=65536, max_num_seqs=64, and prefix caching enabled. Of the records audited here, only the 83 partial reruns from 9/10 fall within the observation period of these logs. For both conditions, the observed maximum Running+Waiting was 16, maximum GPU KV utilization was 12.4%, and displayed cache hit rates while non-idle were 74.9–95.1%. These hit rates are server aggregates, not exact rates for each run.

vLLM startup logs from 8/31–9/3 are unavailable, so the vLLM version, effective prefix cache state, and GPU load at that time cannot be established. There are no Git differences in startup scripts or agent config, but this does not prove full equivalence of the effective environments.

## Evaluation issues and scope

Predictions, patch.diff files, and internal report.json files were compared for 1235 records with patches. Of these, 1201 have reports created after generation that match the current patches and verdicts. Another 11 reuse stale reports for different patches. There are 23 records without internal reports: 16 have container 409 errors, 1 has an evaluation timeout, and the remaining 6 are explained by Patch Apply Failed for the current patch. Those 6 are retained as ordinary patch failures and excluded from this reevaluation list.

The 11 stale reports comprise 4 OTRC+SU-partial and 7 OTRC+SS-partial records. The cause is the same as in the previous audit: the generation runner invokes the harness with the same run_id, and the harness uses an existing report.json without comparing patches. Example: scikit-learn__scikit-learn-10297__otrc-su-partial__r1 was generated on 9/10 at 04:55:43, but its internal report is dated 9/2 at 06:24:02, and the original and current patches differ.

Of the 17 evaluation environment failures/timeouts, 15 concern scikit-learn__scikit-learn-14710, with 1 each for sympy__sympy-19637 and sympy__sympy-18189. Specific keys and log locations are recorded in reevaluation_candidates.csv.

Reevaluation should use the current submission and a new run_id or isolated evaluation output directory to prevent stale reports from causing evaluation to be skipped. Resolve the causes of container image state errors first. Update the result index and outcomes.csv only after confirming evaluation of the correct patch. No generation, evaluation, server startup, or updates to existing CSV files were performed during this audit.

## Files

- runs.csv / summary.json: Generation consistency, configuration hashes, and original/rerun aggregates for 1800 records.
- launches.csv: Relevant launches from the shared launcher. TR is aggregated by stdout block boundaries, so consult the resume analysis above as well. OTRC@∞ is supplemented by its dedicated log.
- server_metrics.csv / extra_checks.json: Configuration, coverage, time overlap checks, and server observations. eval_mismatch in extra_checks is a preliminary comparison of top-level reports; refer to evaluation_classification.csv for final judgments.
- evaluation_checks.csv / evaluation_classification.csv: Evaluation comparisons for 1235 records with patches.
- reevaluation_candidates.csv: The 28 candidates from this audit.
- reevaluation_candidates_combined.csv: 241 previous + 28 current candidates = 269 total. FC is excluded.
- audit_generation.py / audit_extra.py / audit_evaluation.py / classify_evaluation.py: Read-only audit scripts. They write diagnostic outputs only.
