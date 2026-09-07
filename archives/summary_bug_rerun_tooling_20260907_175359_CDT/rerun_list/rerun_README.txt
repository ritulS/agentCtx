Rerun candidates for the summary bug (compiled from a previous audit snapshot)

Conditions: 30
Priority reruns: 1705 runs
Additional candidates including inferred cases: 169 runs
Total recommended: 1874 runs

rerun_condition_summary.csv: Preserves the existing condition_summary.csv columns and adds rerun counts. Includes only conditions with at least 1 recommended run.
rerun_runs.csv: Lists 1874 target task/condition/run combinations. This does not request rerunning every run in each condition.

rerun_priority_runs = summary_marker_error_runs (1101) + summary_failure_accounting_runs (604)
rerun_probable_runs = summary_related_response_runs (169)
rerun_recommended_runs = rerun_priority_runs + rerun_probable_runs
unresolved_runs = runs with an unestablished connection. Excluded from the recommended total. This does not mean unaffected.
runs_scanned and existing error counts cover each entire condition in the original audit, not just recommended runs.
Classifications based on summary markers or response content do not establish the call origin in every case. The original experiment logs are unchanged.

Update history:
- 20260907-1735: cohort_model_path=glm47flash rows replaced with rescan results from query-error-audit-20260907-1731 (query-error-review-20260907-1731) (442 rows -> 464 rows). Other cohorts retain their original snapshot rows. Previous files saved as *.before-glm47flash-update-20260907-1735.*.
