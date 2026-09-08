Rerun candidates for the summary bug (compiled from a previous audit snapshot)

Conditions: 95
Priority reruns: 4857 runs
Additional candidates including inferred cases: 262 runs
Total recommended: 5119 runs

rerun_condition_summary.csv: Preserves the existing condition_summary.csv columns and adds rerun counts. Includes only conditions with at least one recommended run.
rerun_runs.csv: Lists 5119 target task/condition/run combinations. This does not request rerunning every run in each condition.

rerun_priority_runs = summary_marker_error_runs (2359) + summary_failure_accounting_runs (2498)
rerun_probable_runs = summary_related_response_runs (262)
rerun_recommended_runs = rerun_priority_runs + rerun_probable_runs
unresolved_runs = runs with an unestablished connection. Excluded from the recommended total. This does not mean unaffected.
runs_scanned and existing error counts cover each entire condition in the original audit, not just recommended runs.
Classifications based on summary markers or response content do not establish the call origin in every case. The original experiment logs are unchanged.
