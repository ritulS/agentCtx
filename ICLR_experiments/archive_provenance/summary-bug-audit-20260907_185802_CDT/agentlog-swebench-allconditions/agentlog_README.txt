agent.log attribution of FormatErrors (summary call vs normal agent call)
generated: 2026-09-08T15:57:00
audit dir: /home/ak58925/agentCtx/archives/summary-bug-audit-20260907_185802_CDT
workspace: /home/ak58925/agentCtx
archive roots: ['/home/ak58925/agentCtx/archives/swebench_summary_marker_error_20260907_192635_CDT']

summary-condition runs scanned: 16166
verdicts: summary_confirmed=6367, uncorroborated=442, tail_unresolved=1908, inconsistent=241, multi_run_log=358, source_changed=0, log_missing=0, no_summary_evidence=6850
additions to rerun_runs.csv: 4203 (priority=3824, probable=379)
non-summary runs scanned (self-check): 6813; with any summary evidence (method anomalies): 15; of which verdict summary_confirmed: 0 (must be 0); failing structure checks: 169 -> nonsummary_integrity.csv

verdict by prior audit classification (summary conditions):
  (no trajectory error): summary_confirmed=2655, uncorroborated=18, inconsistent=46, multi_run_log=93, no_summary_evidence=2756
  not_established: summary_confirmed=1169, uncorroborated=24, tail_unresolved=9, inconsistent=77, multi_run_log=112, no_summary_evidence=4088
  summary_failure_accounting: summary_confirmed=1139, uncorroborated=190, tail_unresolved=1072, inconsistent=38, multi_run_log=59
  summary_marker_error: summary_confirmed=1187, uncorroborated=197, tail_unresolved=819, inconsistent=72, multi_run_log=83, no_summary_evidence=1
  summary_related_response: summary_confirmed=217, uncorroborated=13, tail_unresolved=8, inconsistent=8, multi_run_log=11, no_summary_evidence=5

method: between consecutive headers 'mini-swe-agent (step N, $C):' a normal-agent FormatError consumes
one step number and a summary FormatError consumes none (summarize() raises before n_calls += 1).
Headers and 'User:' / 'Format error:' / '<error>' sequences are accepted only directly after the Rule
line that step() prints before every query, and only when that rule follows the last line of a message;
other occurrences (echoed transcripts) are counted in fake_headers / fake_errors and ignored.
confirmation: an interval's summary failures count as confirmed only when token_log
compression_event_steps contains the interval's starting step (the compression that finally succeeded
after the failed summary calls). Summary evidence without that record is 'uncorroborated' (known
legitimate cause: OTRC online clearing can end the over-budget state without a compression event; a
fully quoted error block in a reply would look the same). Tail errors (after the last header) are never
confirmed: with an exit status they are counted as uncorroborated, without one (killed run, saved
api_calls may lag the log by one step) as tail_unresolved.
same-execution checks: trajectory.json and token_log.json must equal the audited size/mtime
(source_status == exact) and agent.log mtime must lie within 1800s of trajectory.json.
structure checks that block any confirmation: one process (one banner, increasing step numbers, no header
glued to the previous line), no cut multi-byte characters, no step consumed without a printed Format error
(unexplained_steps == 0), no tail errors after a Submitted exit, header count == token_log steps (+-1),
api_calls within [max_step, max_step + tail + 1].
verdicts: summary_confirmed; uncorroborated; tail_unresolved; inconsistent (structure or log/trajectory
disagreement); multi_run_log (interleaved output of two processes: the run was launched twice into the
same directory and its trajectory.json is whichever process saved last, so it is unreliable regardless
of the summary bug); source_changed (not provably the audited execution); log_missing;
no_summary_evidence (no summary FormatError detected; not proof that summaries never failed).
columns: summary_failures_raw = confirmed + uncorroborated + tail_unresolved (computation only);
summary_failure_lower_bound in the additions is filled only for summary_confirmed rows.
additions (summary conditions only): summary_confirmed -> priority/agentlog_summary_failure;
uncorroborated -> probable/agentlog_uncorroborated; tail_unresolved -> probable/agentlog_tail_unresolved;
inconsistent, multi_run_log, source_changed, log_missing -> probable/agentlog_unverifiable.
Non-summary conditions (--all-conditions) are never added; their summary evidence is a method anomaly.
Runs already listed in rerun_runs.csv are annotated in rerun_runs_with_agentlog.csv, never duplicated.
Experiment files were read only.
