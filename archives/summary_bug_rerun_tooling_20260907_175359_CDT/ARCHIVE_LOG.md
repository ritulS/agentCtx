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
