# Summary-bug rerun: tooling and archive log

Created: 2026-09-07 17:54 CDT
Location: `/home/ak58925/agentCtx/archives/summary_bug_rerun_tooling_20260907_175359_CDT/`

This directory holds the scripts, the rerun list, and a log of every archive under
`/home/ak58925/agentCtx/archives/`. It contains no experiment results.

## Background

- In mini-swe-agent 2.2.6, summary calls went through the agent's `_parse_actions`.
  A summary response without a bash command raised a FormatError.
- Fix: commit `cd1716f` (`query_summary`) in `agentCtx-summarization`.
  Applied to the runtime tree `/home/ak58925/agentCtx` as commit `6b45448` (2026-09-07 17:23 CDT).
- Affected summary-condition runs were listed in `rerun_runs.csv`. Rows with reason
  `summary_marker_error` were archived so that the normal launcher re-executes only those runs.

## Files here

| Path | What it is |
|---|---|
| `scripts/export_query_errors.py` | Step 1. Scans ICLR_results and writes runs with FormatErrors to `runs_with_errors.csv` and `details/`. |
| `scripts/review_unmarked_summary_errors.py` | Step 2. Classifies runs without a summary marker into `review_unmarked.csv`. |
| `scripts/build_rerun_runs.py` | Step 3. Combines steps 1 and 2 into `rerun_runs.csv`, `rerun_condition_summary.csv`, `rerun_README.txt`. `--update-cohort` replaces one cohort's rows in an older list. |
| `scripts/archive_rerun_targets.py` | Selects rows from `rerun_runs.csv`, moves run and Harbor trial directories into `archives/<name>/`, and removes the rows from `experiment_results.json`. Dry run by default, `--execute` to apply. |
| `rerun_list/rerun_runs.csv` | The rerun list used for the archives. 1874 rows, 30 conditions. Scan of 16:12 with GLM rows replaced by the 17:31 rescan (written 17:35). |
| `rerun_list/rerun_runs.before-glm47flash-update-20260907-1735.csv` | The 16:27 version before the GLM update (1852 rows). The devstral archive was selected from this one. |
| `rerun_list/rerun_condition_summary.csv`, `rerun_list/rerun_README.txt` | Per-condition counts and column descriptions. |

All four scripts are uncommitted in `agentCtx-summarization` (HEAD `cd1716f`) as of 17:54.
Original locations: `agentCtx-summarization/scripts/` and `agentCtx-summarization/results/query-error-audit-20260907/`.

Rows in `rerun_runs.csv` by reason:

| cohort | section | summary_marker_error | summary_failure_accounting | summary_related_response |
|---|---|---|---|---|
| devstral24b | main | 324 | 104 | 47 |
| glm47flash | main | 224 | 212 | 28 |
| qwen35b | main | 396 | 202 | 78 |
| qwen35b | ablation | 157 | 86 | 16 |

Only the `summary_marker_error` column has been archived. The other two columns are listed but not archived.

## Archive log

### 2026-09-07: summary-bug rerun targets

All four were made with `archive_rerun_targets.py` (copied into each archive as `archive_operation.py`)
with `--rerun-reason summary_marker_error`. Moved directories keep their workspace-relative paths
(`ICLR_results/terminalbench/<section>/<cohort>/<cell>/<task>/<condition>/run_<n>/` and
`logs/harbor_jobs/terminalbench/<cohort>/<job>/<trial>/`). Other trials of the same Harbor job stayed in place.

| Archive directory | Time (CDT) | Selection | Runs | Cells | Result rows | Dirs moved | Source CSV |
|---|---|---|---|---|---|---|---|
| `devstral24b_summary_marker_error_20260907_171535_CDT` | 17:15:35 | devstral24b | 324 | 4 | 480 → 156 | 648 | 16:27 version |
| `qwen35b_main_summary_marker_error_20260907_174329_CDT` | 17:43:29 | qwen35b, main | 396 | 8 | 960 → 564 | 792 | 17:35 version |
| `qwen35b_ablation_summary_marker_error_20260907_174401_CDT` | 17:44:01 | qwen35b, ablation | 157 | 8 | 345 → 188 | 314 | 17:35 version |
| `glm47flash_main_summary_marker_error_20260907_174412_CDT` | 17:44:12 | glm47flash, main | 224 | 5 | 600 → 376 | 448 | 17:35 version |

"Dirs moved" = run directories + Harbor trial directories (one each per run).

Affected cells:

| Archive | Cells |
|---|---|
| devstral24b main | `d05__b4k__ss`, `d05__b4k__ss-partial`, `di__b4k__otrc-ss-partial`, `di__b4k__trc-ss` |
| qwen35b main | `d05__b3k__ss`, `d05__b3k__ss-partial`, `d05__b3k__su-full`, `d05__b3k__su-partial`, `di__b3k__otrc-ss-partial`, `di__b3k__otrc-su-partial`, `di__b3k__trc-ss`, `di__b3k__trc-su` |
| qwen35b ablation | `d05__b2k__ss`, `d05__b2k__ss-partial`, `d05__b2k__su-full`, `d05__b2k__su-partial`, `d05__b4k__ss`, `d05__b4k__ss-partial`, `d05__b4k__su-full`, `d05__b4k__su-partial` |
| glm47flash main | `d05__b3k__ss`, `d05__b3k__ss-partial`, `d05__b3k__su-full`, `di__b3k__trc-ss`, `di__b3k__trc-su` |

Each archive directory contains:

- `README.md`: reason, counts per cell/condition/run, task list, verification.
- `rerun_source/`: copy of the CSV used and the selected rows.
- `manifest.json`, `tasks.tsv`, `move_plan.json`, `moves_completed.jsonl`: what was moved, and where.
- `before/`: the complete `experiment_results.json` files before modification.
- `ICLR_results/`, `logs/`: the moved runs and trials. The `experiment_results.json` here holds only archived rows.

Commands (reconstructed from each README and the directory names; `~/.bash_history` was last saved at 14:55, so these commands are not in it):

```bash
cd /home/ak58925/agentCtx-summarization
venv/bin/python scripts/archive_rerun_targets.py --cohort-model-path devstral24b --rerun-reason summary_marker_error --execute
venv/bin/python scripts/archive_rerun_targets.py --cohort-model-path qwen35b --section main --rerun-reason summary_marker_error \
  --archive-name qwen35b_main_summary_marker_error_20260907_174329_CDT --execute
venv/bin/python scripts/archive_rerun_targets.py --cohort-model-path qwen35b --section ablation --rerun-reason summary_marker_error \
  --archive-name qwen35b_ablation_summary_marker_error_20260907_174401_CDT --execute
venv/bin/python scripts/archive_rerun_targets.py --cohort-model-path glm47flash --section main --rerun-reason summary_marker_error \
  --archive-name glm47flash_main_summary_marker_error_20260907_174412_CDT --execute
```

`trajectory.json` count in ICLR_results:

| When | Count |
|---|---|
| 16:12 scan | 5784 |
| 17:31 scan (after devstral archive, plus GLM trc-ss completion) | 5500 |
| 17:53 (after all four archives) | 4723 |

At 17:53: devstral24b main 1236, glm47flash main 736, qwen35b main 1706, qwen35b ablation 278.

### 2026-09-06: backups of results after the 09-05 afternoon resume (unrelated, for reference)

Made with one-off scripts (`archive_operation.py` in each directory), selecting by trial start time. See each README.

| Archive directory | Time (CDT) | Selection | Runs | Cells | Result rows | Harbor jobs moved |
|---|---|---|---|---|---|---|
| `devstral_since_20260905_145630_CDT` | 09-06 13:44 | devstral24b main, trials started after 09-05 14:56:30 | 680 | 6 | 1560 → 880 | 17 whole jobs |
| `glm_since_20260905_145712_CDT` | 09-06 13:53 | glm47flash main, trials started after 09-05 14:57:12 | 240, plus one interrupted job (11 trials) | 2 | 480 → 240 | 7 whole jobs |

## Rerun status (2026-09-07 17:53)

| Launcher | Status |
|---|---|
| `run_agent_models_expansion_tb.sh devstral main` | Running since 17:49:54 (PID 2996992), started at `d05__b4k__ss`. Log: `logs/followup_tb_devstral_main.nohup.log`. |
| `run_agent_models_expansion_tb.sh qwen main` | Running since 17:49:54 (PID 2996994), started at `d05__b3k__su-full`. Log: `logs/followup_tb_qwen_main.nohup.log`. |
| GLM main | Not started. The previous launcher was terminated during `di__b3k__otrc-tr`; GLM vLLM is down. |
| qwen ablation | Not started. `qwen main` does not cover ablation cells; run `bash scripts/run_agent_models_expansion_tb.sh qwen ablation`. |

Both running launchers use the runtime tree with the `6b45448` fix.

## Rebuilding rerun_runs.csv

```bash
cd /home/ak58925/agentCtx-summarization
venv/bin/python scripts/export_query_errors.py \
  --source-root /home/ak58925/agentCtx/ICLR_results --output-dir results/query-error-audit-<ts>
venv/bin/python scripts/review_unmarked_summary_errors.py \
  --audit-dir results/query-error-audit-<ts> --output-dir results/query-error-review-<ts>
venv/bin/python scripts/build_rerun_runs.py \
  --audit-dir results/query-error-audit-<ts> --review-dir results/query-error-review-<ts>
```

- Output directories must not exist yet. Scan takes about 25 s, review about 12 s (at 5500 trajectories).
- To refresh one cohort in an older list: add `--update-cohort <cohort> --into <old audit dir>`.
  The old files are kept as `*.before-<cohort>-update-<ts>.*`. The CSV here was made this way
  (GLM rows from `query-error-audit-20260907-1731` into `query-error-audit-20260907`).
- Archived runs are no longer in ICLR_results, so a new scan will not list them. Use the CSV here for the full pre-archive list.

## Notes

- Nothing was deleted. To restore an archive, move each `moves_completed.jsonl` destination back to its source
  and restore `experiment_results.json` from `before/`.
- `COVERAGE.csv` and `COVERAGE_TB.csv` do not reflect the archives. Regenerate with `python scripts/build_coverage.py` after the reruns.

## Local SWE-bench candidate CSV (2026-09-07)

The local `akiho-expansion` workspace contains SWE-bench results. A fresh scan of
22,979 trajectories produced outputs under
`archives/summary-bug-audit-20260907_185802_CDT/`:

- `archive_targets.csv`: 2,359 runs with `rerun_reason=summary_marker_error`,
  matching the selection rule used in the Terminal-Bench archives above.
- `archive_target_summary.csv`: counts by benchmark, section, and model.
- `rerun-list/rerun_runs.csv`: all 5,119 candidates, including 2,498 additional
  call-accounting cases and 262 response-content cases.
- `manual_review_inconsistent_counters.csv`: unmarked runs whose counters cannot
  support classification. These are excluded from the rerun list.
- `README.md`: local commands, selection details, and limitations.

The exporter now falls back to the matching `experiment_results.json` row when
`exit_info.json` is absent, and to condition directory names for legacy rows
without a primitive. Metadata provenance is recorded in `runs_with_errors.csv`.
The reviewer reports inconsistent counters as `not_established` instead of
stopping the whole audit or drawing an invalid accounting conclusion.

One marker candidate has no matching result-index row; it is flagged with
`result_index_status=missing` in `archive_targets.csv`. All candidate run paths exist.
No runs were moved and no experiment result indexes were modified.
`archive_rerun_targets.py` still assumes Terminal-Bench Harbor files and must be
adapted before using it to move SWE-bench runs.

### SWE-bench archive command

Use `scripts/archive_swebench_rerun_targets.py` in this tooling directory for
SWE-bench. It selects only `summary_marker_error`, moves run directories, and
removes matching result-index rows. Missing index rows are recorded in the
manifest and do not prevent archiving their run directories. Original indexes,
the source CSV, a move journal, and file checksums are kept in the destination.
Stop experiment launchers/workers before execution and keep them stopped until
completion. The script refuses execution when it detects active SWE-bench runners.

```bash
tooling=archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts
csv=archives/summary-bug-audit-20260907_185802_CDT/archive_targets.csv
archive_name="swebench_summary_marker_error_$(date +%Y%m%d_%H%M%S_%Z)"

# Preview only; does not create the archive.
venv/bin/python "$tooling/archive_swebench_rerun_targets.py" \
  --root "$PWD" --rerun-csv "$csv" --archive-name "$archive_name"

# Execute after checking the preview and stopping experiment writers.
venv/bin/python "$tooling/archive_swebench_rerun_targets.py" \
  --root "$PWD" --rerun-csv "$csv" --archive-name "$archive_name" --execute
```

Dry-run validation: 2,359 run directories, 58 cells, 2,358 recorded result rows,
and one unindexed run. Real data was not moved during command preparation.
The execute path was checked on temporary sample data, including an unindexed
run, preservation of an unrelated run, and backup/index consistency.

## 2026-09-07 19:44: Qwen main 10K/20K cells reused for ablation (SWE-bench)

Script: `scripts/reuse_qwen_main_for_ablation.py` (commit `4d9d2e4`). Copies the
ABL-30 subset of the legacy P100 `main/qwen35b` cells at 10K/20K (d05 singles and
di invariants) into `ablation/qwen35b`. Sources preserved; each destination cell
carries a `REUSE_MANIFEST.json` with per-run SHA-256 and pending keys.

```bash
venv/bin/python scripts/reuse_qwen_main_for_ablation.py            # dry run
venv/bin/python scripts/reuse_qwen_main_for_ablation.py --execute  # 19:44 CDT
```

Result: 22 cells, 1,761 runs copied, 219 pending (all "missing result row or
trajectory", i.e. runs already moved by the summary-marker archive above; no new
marker exclusions). Pending runs are filled by
`bash scripts/run_agent_models_expansion.sh qwen`, which skips keys already
recorded in the destination cell. Note: these runs now exist in both `main`
(P100) and `ablation` (ABL-30) for qwen35b; filter by `experiment_section`.

## 2026-09-08: agent.log attribution and archive of the remaining rerun targets (SWE-bench)

Why: trajectory.json only keeps the post-compression history, so FormatErrors from summary
calls that were later compressed away are invisible to the 2026-09-07 audit. agent.log
(subprocess stdout) keeps every message and the `step N` headers, which lets each
FormatError be attributed: a normal-agent failure consumes a step number, a summary
failure does not. Details: `scripts/attribute_agentlog.py` docstring and
`archives/summary-bug-audit-20260907_185802_CDT/agentlog-swebench/agentlog_README.txt`.

### Step 1: attribution scan — commit `25b7ca7` (2026-09-08 16:21 CDT)

Script: `scripts/attribute_agentlog.py` (sha256 `a20ad23d…`, identical to the file that
produced the outputs). Inputs: the 2026-09-07 audit directory and the marker archive
(audited copies of the 2,359 already-moved runs). Read-only on experiment files.

```bash
venv/bin/python archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/attribute_agentlog.py \
  --audit-dir archives/summary-bug-audit-20260907_185802_CDT \
  --source-root ICLR_results \
  --archive-root archives/swebench_summary_marker_error_20260907_192635_CDT \
  --output-dir archives/summary-bug-audit-20260907_185802_CDT/agentlog-swebench --workers 32
# self-check on non-summary conditions (must report 0 summary_confirmed):
#   same command with --all-conditions and --output-dir .../agentlog-swebench-allconditions
```

Result (16,166 summary-condition runs, all matching the audited trajectory/token_log):

| verdict | runs |
|---|---:|
| summary_confirmed (compression-event corroborated) | 6,367 |
| uncorroborated (mostly OTRC family) | 442 |
| tail_unresolved (killed in a summary loop) | 1,908 |
| inconsistent / multi_run_log (log-trajectory mismatch / launched twice) | 241 / 358 |
| no_summary_evidence | 6,850 |

Self-check: 6,813 non-summary runs, 0 `summary_confirmed`; 169 fail the structure checks
(`agentlog-swebench-allconditions/nonsummary_integrity.csv`, mostly TR runs launched twice
on 2026-08-23/24; not part of the summary-bug rerun).

### Step 2: rerun_runs.csv update — commit `25b7ca7`

`rerun-list/rerun_runs.csv` went from 5,119 rows (commit `be69dca`) to 9,322 rows by
appending `agentlog-swebench/rerun_runs_agentlog_additions.csv` (4,203 rows, same columns,
no duplicate trajectory keys). Backup kept locally as
`rerun-list/rerun_runs.before-agentlog-20260908-1605.csv` (not committed).

```bash
AUD=archives/summary-bug-audit-20260907_185802_CDT
cp $AUD/rerun-list/rerun_runs.csv $AUD/rerun-list/rerun_runs.before-agentlog-$(date +%Y%m%d-%H%M).csv
tail -n +2 $AUD/agentlog-swebench/rerun_runs_agentlog_additions.csv >> $AUD/rerun-list/rerun_runs.csv
```

| rerun_reason (new) | rerun_priority | rows |
|---|---|---:|
| agentlog_summary_failure | priority | 3,824 |
| agentlog_unverifiable | probable | 328 |
| agentlog_uncorroborated | probable | 42 |
| agentlog_tail_unresolved | probable | 9 |

`summary_failure_lower_bound` is filled only for `agentlog_summary_failure` rows.

### Step 3: archive of all remaining rerun targets — commit `16dacec` (2026-09-08 16:23 CDT)

Script: `scripts/archive_swebench_rerun_targets.py` with the new `--rerun-reason`
(repeatable) and `--source-stats` options. Non-marker rows are moved only if their
trajectory.json and token_log.json still have the audited size and mtime. The copy saved in
the archive (`archive_operation.py`, sha256 `e9c01912…`) is byte-identical to the committed
script. Executed 2026-09-08 16:20:42–16:20:59 CDT, no launcher running.

```bash
venv/bin/python archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/archive_swebench_rerun_targets.py \
  --rerun-csv archives/summary-bug-audit-20260907_185802_CDT/rerun-list/rerun_runs.csv \
  --source-stats archives/summary-bug-audit-20260907_185802_CDT/source_file_stats.json \
  --rerun-reason summary_failure_accounting --rerun-reason summary_related_response \
  --rerun-reason agentlog_summary_failure --rerun-reason agentlog_uncorroborated \
  --rerun-reason agentlog_tail_unresolved --rerun-reason agentlog_unverifiable \
  --archive-name swebench_summary_bug_remaining_20260908_162042_CDT --execute
```

| Archive directory | Selection | Runs | Cells | Index rows removed | Unindexed |
|---|---|---:|---:|---:|---:|
| `swebench_summary_bug_remaining_20260908_162042_CDT` | 6 reasons above | 6,963 | 98 | 6,952 | 11 |

| cohort / section | runs |
|---|---:|
| qwen35b / main | 2,719 |
| qwen35b / ablation | 933 |
| devstral24b / ablation | 1,795 |
| devstral24b / main | 840 |
| glm47flash / main | 676 |

Together with the 2026-09-07 marker archive (2,359 runs) every row of `rerun_runs.csv`
(9,322) is now out of `ICLR_results` and out of the result indexes, so the launcher's resume
re-executes all of them. `status.json` reports `complete`; `before/` holds the original
indexes and `moves_completed.jsonl` the move journal.
