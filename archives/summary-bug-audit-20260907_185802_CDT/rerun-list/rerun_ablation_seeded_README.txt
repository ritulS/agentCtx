Ablation-side rerun rows for seeded copies of archived main runs
Generated: 2026-09-08T16:59:45-05:00
Input: archives/summary-bug-audit-20260907_185802_CDT/rerun-list/rerun_runs.csv
Archive roots: /home/ak58925/agentCtx/archives/swebench_summary_marker_error_20260907_192635_CDT, /home/ak58925/agentCtx/archives/swebench_summary_bug_remaining_20260908_162042_CDT
Model: qwen35b; ablation cells with a main counterpart: 16

Main rerun rows in those cells: 2607
  ABL-30 task, not in ablation index (ablation resume runs them): 217
  NEW-70 task (no ablation counterpart; not rerun by the launcher): 1912
  selected (identical to archived main run):      476
  excluded:                                       2
    ablation_copy_differs_from_archived_main: 2

Selected by rerun_reason:
  agentlog_summary_failure: 265
  agentlog_uncorroborated: 2
  agentlog_unverifiable: 1
  summary_failure_accounting: 172
  summary_related_response: 36
Selected by rerun_priority:
  priority: 437
  probable: 39
Selected by cell:
  d05__b10k__ss: 31
  d05__b10k__ss-partial: 10
  d05__b10k__su-full: 68
  d05__b10k__su-partial: 77
  d05__b20k__ss: 33
  d05__b20k__ss-partial: 14
  d05__b20k__su-full: 35
  d05__b20k__su-partial: 40
  di__b10k__otrc-ss-partial: 9
  di__b10k__otrc-su-partial: 58
  di__b10k__trc-ss: 32
  di__b10k__trc-su: 49
  di__b20k__otrc-ss-partial: 1
  di__b20k__otrc-su-partial: 11
  di__b20k__trc-ss: 4
  di__b20k__trc-su: 4

Archive command (dry run; add --execute after stopping launchers):
  venv/bin/python archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/archive_swebench_rerun_targets.py \
    --rerun-csv archives/summary-bug-audit-20260907_185802_CDT/rerun-list/rerun_runs_ablation_seeded.csv \
    --source-stats archives/summary-bug-audit-20260907_185802_CDT/rerun-list/source_file_stats_ablation_seeded.json \
    --section ablation --cohort-model-path qwen35b \
    --rerun-reason agentlog_summary_failure \
    --rerun-reason agentlog_uncorroborated \
    --rerun-reason agentlog_unverifiable \
    --rerun-reason summary_failure_accounting \
    --rerun-reason summary_related_response \
    --archive-name swebench_summary_bug_ablation_seeded_<YYYYMMDD_HHMMSS>_CDT
