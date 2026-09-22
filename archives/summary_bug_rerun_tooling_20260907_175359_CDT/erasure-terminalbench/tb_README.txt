Terminal-Bench: trajectory/token_log attribution of possible erased summary failures
generated: 2026-09-08T18:58:10
workspace: /home/ak58925/agentCtx
archive roots: ['/home/ak58925/agentCtx/archives/devstral24b_summary_marker_error_20260907_171535_CDT', '/home/ak58925/agentCtx/archives/glm47flash_main_summary_marker_error_20260907_174412_CDT', '/home/ak58925/agentCtx/archives/qwen35b_ablation_summary_marker_error_20260907_174401_CDT', '/home/ak58925/agentCtx/archives/qwen35b_main_summary_marker_error_20260907_174329_CDT']
audit dirs: ['/home/ak58925/agentCtx-summarization/results/query-error-audit-20260907', '/home/ak58925/agentCtx-summarization/results/query-error-audit-20260907-1731']
review dirs: ['/home/ak58925/agentCtx-summarization/results/query-error-review-870-20260907', '/home/ak58925/agentCtx-summarization/results/query-error-review-20260907-1731']
rerun list: /home/ak58925/agentCtx/archives/summary_bug_rerun_tooling_20260907_175359_CDT/rerun_list/rerun_runs.csv (1874 rows)
fix time: 2026-09-07T17:23:33-05:00 (runs with Harbor started_at before this are pre-fix)

discovery: {'post_fix_skipped': 899, 'workspace': 3956, 'archive:devstral24b_summary_marker_error_20260907_171535_CDT': 324, 'archive:glm47flash_main_summary_marker_error_20260907_174412_CDT': 224, 'archive:qwen35b_ablation_summary_marker_error_20260907_174401_CDT': 157, 'archive:qwen35b_main_summary_marker_error_20260907_174329_CDT': 396}
summary-condition pre-fix runs scanned: 2981
verdicts: already_listed=1874, erasure_possible=485, token_log_stale=133, errors_intact_not_established=47, no_evidence_intact=442, source_changed=0, unreadable=0
additions to rerun_runs.csv: 618 (priority=0, probable=618)
listed runs not found on disk: 0
console-log check: worker.log present for 1400 runs, step headers found in them: 0 (must be 0: DefaultAgent prints no per-step output, so the SWE-bench agent.log method has nothing to read)
runs whose trajectory.json was still written >60s after exit_info.json (pre-2026-09-06 zombie agents): 1767
summary-condition runs with a stale token_log (trajectory saved >5s after token_log.json, or api_calls > step_prompt_tokens + 1): 1614; those not already listed or erasure_possible are token_log_stale
non-summary runs scanned (self-check): 2076; with summary-marker errors (method anomalies): 0 (must be 0)

verdict by prior audit classification (summary conditions):
  (no trajectory error): erasure_possible=452, token_log_stale=113, no_evidence_intact=442
  not_established: erasure_possible=33, token_log_stale=20, errors_intact_not_established=47
  summary_failure_accounting: already_listed=604
  summary_marker_error: already_listed=1101
  summary_related_response: already_listed=169

method: Terminal-Bench has no per-step console log (the agent is a DefaultAgent subclass run by the Harbor
adapter; agent.log in the run dir is Harbor's trial.log), so FormatErrors erased from trajectory.json by a later
compression cannot be recovered or attributed. A failed pre-fix summary call left a 'Format error' user message
that only a successful rewrite of the compressible window removes: a successful summary (summarization_prompt_tokens
> 0), or, for the *_partial variants, any compression event (head summarized, or truncate() fallback without an LLM
call). TRC and online TRC stub message content but keep 'extra' (interrupt_type, model_response), so they never
remove the evidence; for trc_summarize / trc_structured_summarize only the stage-2 summary counts.
erasure_possible = summarization_prompt_tokens > 0 or (compression_events > 0 and primitive not TRC-stacked).
verdicts: already_listed; erasure_possible (no established failure, but evidence may have been erased ->
probable/tb_erasure_possible); token_log_stale (token_log.json predates the final trajectory.json: before the
2026-09-06 zombie fix a Harbor timeout wrote token_log while the agent thread kept running, so a later compression
is not recorded -> probable/tb_unverifiable); errors_intact_not_established (all errors retained, call accounting
could not attribute them; unchanged, not added); no_evidence_intact (no retained error and nothing could have
erased one: no summary call failed, not added); source_changed (retained error count differs from the audited
one -> probable/tb_unverifiable); unreadable (-> probable/tb_unverifiable).
No Terminal-Bench addition is 'priority': nothing can be confirmed without a console log.
summary_marker_errors in the additions is the current retained count (0 for error-free runs);
summary_failure_lower_bound is left empty.
Runs already listed in rerun_runs.csv are annotated in rerun_runs_with_tb.csv, never duplicated.
Post-fix runs (reruns started after the fix) are skipped by Harbor started_at. Experiment files were read only.
