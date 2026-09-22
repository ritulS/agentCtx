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

## 2026-09-08: Terminal-Bench counterpart of the SWE-bench agent.log expansion (update NOT yet applied)

On SWE-bench (branch `akiho-expansion`, commit `25b7ca7`, cherry-picked as `fcef550`) `attribute_agentlog.py`
recovered FormatErrors that a later successful compression had erased from `trajectory.json` by reading the
mini-swe-agent console output (`agent.log`, written by `scripts/run_experiment.py`), and appended 4,203 rows.

That method has no input on Terminal-Bench:

- The Harbor adapter runs a `DefaultAgent` subclass (`CheckpointAgent`) that prints nothing per step.
  `agent.log` in a TB run directory is a copy of Harbor's `trial.log` (docker/environment messages).
  `worker.log` (Harbor trial `agent/`, only after the 2026-09-06 zombie fix) holds the banner and tracebacks;
  0 step headers in 1,400 files.
- `model_stats.api_calls` in `trajectory.json` is the agent's own `n_calls` (`default.py`), not a model-side counter.

`scripts/attribute_tb_erasure.py` therefore uses the only per-run evidence there is. A failed pre-fix summary call
left a `Format error` user message that only a successful rewrite of the compressible window removes
(successful summary; or any event for the `*_partial` variants, whose fallback is `truncate()`). TRC and online TRC
stub message *content* but keep `extra` (`interrupt_type`, `model_response`), so they never remove the evidence;
for `trc_summarize` / `trc_structured_summarize` only the stage-2 summary (`summarization_prompt_tokens > 0`) counts.
Runs where such a rewrite happened and no summary failure was established are `probable / tb_erasure_possible`;
runs with no retained error and no possible rewrite are clean (`no_evidence_intact`). The intact verdicts assume
`token_log.json` describes the same state as `trajectory.json`; before the 2026-09-06 zombie fix a Harbor timeout
wrote `token_log.json` while the agent thread kept saving `trajectory.json`, so runs whose trajectory is newer than
the token_log by more than 5 s, or whose `api_calls` lead `step_prompt_tokens` by more than one call, are
`token_log_stale` → `probable / tb_unverifiable` instead (reviewer feedback of 2026-09-08). Nothing can be
confirmed, so no TB addition is `priority`. Pre-fix = Harbor `started_at` before the runtime fix (`6b45448`,
17:23:33 CDT); the 899 reruns started after it are skipped. Runs are read from `ICLR_results/` and the four
`*_summary_marker_error_*` archives (no path appears twice).

Outputs in `erasure-terminalbench/` (committed: additions, condition summary, README, anomalies; the two per-run
CSVs are gitignored):

| Verdict | Runs |
|---|---|
| summary-condition pre-fix runs scanned | 2981 |
| already_listed | 1874 |
| erasure_possible → **addition** `probable / tb_erasure_possible` | **485** (452 error-free, 33 previously `not_established`) |
| token_log_stale → **addition** `probable / tb_unverifiable` | **133** (113 error-free, 20 previously `not_established`; 118 with trajectory >60 s after exit, 15 by the api_calls gap only) |
| errors_intact_not_established (unchanged, not added) | 47 |
| no_evidence_intact (clean, not added) | 442 |
| source_changed / unreadable | 0 / 0 |
| non-summary runs with summary-marker errors (must be 0) | 0 |

Additions total 618: devstral24b main 256, glm47flash main 167, qwen35b main 138, qwen35b ablation 57. The largest
cells are `devstral24b d05__b4k__su-full` and `di__b4k__trc-su`: runs whose summaries succeeded and so erased
whatever failed before. Per-cell counts: `erasure-terminalbench/tb_condition_summary.csv`.

Command used (read-only on experiment files):

```bash
cd /home/ak58925/agentCtx
T=archives/summary_bug_rerun_tooling_20260907_175359_CDT; S=/home/ak58925/agentCtx-summarization/results
python3 $T/scripts/attribute_tb_erasure.py \
  --audit-dir $S/query-error-audit-20260907 --audit-dir $S/query-error-audit-20260907-1731 \
  --review-dir $S/query-error-review-870-20260907 --review-dir $S/query-error-review-20260907-1731 \
  --rerun-list $T/rerun_list/rerun_runs.csv --output-dir $T/erasure-terminalbench --all-conditions
```

**Pending update command** (not run; verified with `--dry-run`: headers equal, no duplicates, 1874 → 2492 rows).
It backs up the list as `rerun_runs.before-tb-erasure-update-<ts>.csv` and appends an "Update history" line to
`rerun_README.txt`:

```bash
python3 $T/scripts/append_rerun_additions.py --rerun-list $T/rerun_list/rerun_runs.csv \
  --additions $T/erasure-terminalbench/rerun_runs_tb_additions.csv --label tb-erasure
```

Archiving for rerun is a separate step. Note that the 2026-09-07 archives covered only `summary_marker_error`; the
`summary_failure_accounting` (604) and `summary_related_response` (169) rows are still in `ICLR_results/` (verified
2026-09-08 from `erasure-terminalbench/tb_attribution.csv`, all 773 at `location=workspace`). One archive per cohort
with all four pending reasons covers both (dry run 2026-09-08: devstral24b 151+256, glm47flash 240+167,
qwen35b 382+195 = 1,391 runs):

```bash
for c in devstral24b glm47flash qwen35b; do
  python3 $T/scripts/archive_rerun_targets.py --rerun-csv $T/rerun_list/rerun_runs.csv \
    --cohort-model-path $c \
    --rerun-reason summary_failure_accounting summary_related_response tb_erasure_possible tb_unverifiable \
    --archive-name ${c}_summary_bug_rerun2_$(date +%Y%m%d_%H%M%S)_CDT --execute
done
```

565 of the 618 new rows have no FormatError at all, so those are a judgement call on erased or unrecorded evidence,
not a detected bug.

**Applied 2026-09-08 19:13-19:14 CDT.** `rerun_runs.csv` 1874 → 2492 rows (backup
`rerun_list/rerun_runs.before-tb-erasure-update-20260908-1913.csv`), then the three archives below with the four
reasons above. Each archive's `README.md` and `tasks.tsv` are committed; the run data are not.

Provenance (agentCtx, branch `akiho-expansion-terminalbench-0829`):

| Item | Commit | Notes |
|---|---|---|
| Code that ran all three commands below | `26d5fbc` | `attribute_tb_erasure.py` and `append_rerun_additions.py` are first committed here, identical to the files that were executed; `archive_rerun_targets.py` is unchanged since `f64dbe6` (2026-09-07). |
| Runtime fix the reruns will use | `6b45448` | `memory.py` `query_summary`; unchanged since. |
| SWE-bench method this replaces | `fcef550` | cherry-pick of `25b7ca7` on `akiho-expansion`. |
| Audit inputs | — | `agentCtx-summarization` (HEAD `cd1716f`) `results/query-error-audit-20260907{,-1731}`, `query-error-review-870-20260907`, `query-error-review-20260907-1731`. |

Commands, in the order executed (all from `/home/ak58925/agentCtx`, `T=archives/summary_bug_rerun_tooling_20260907_175359_CDT`):

```bash
# 1. attribution (18:58 CDT; read-only on experiment files)
S=/home/ak58925/agentCtx-summarization/results
python3 $T/scripts/attribute_tb_erasure.py \
  --audit-dir $S/query-error-audit-20260907 --audit-dir $S/query-error-audit-20260907-1731 \
  --review-dir $S/query-error-review-870-20260907 --review-dir $S/query-error-review-20260907-1731 \
  --rerun-list $T/rerun_list/rerun_runs.csv --output-dir $T/erasure-terminalbench --all-conditions

# 2. rerun list update (19:13 CDT): 1874 -> 2492 rows
python3 $T/scripts/append_rerun_additions.py --rerun-list $T/rerun_list/rerun_runs.csv \
  --additions $T/erasure-terminalbench/rerun_runs_tb_additions.csv --label tb-erasure

# 3. archive (19:14 CDT): one archive per cohort, dry run passed beforehand for each
for c in devstral24b glm47flash qwen35b; do
  python3 $T/scripts/archive_rerun_targets.py --rerun-csv $T/rerun_list/rerun_runs.csv \
    --cohort-model-path $c \
    --rerun-reason summary_failure_accounting summary_related_response tb_erasure_possible tb_unverifiable \
    --archive-name ${c}_summary_bug_rerun2_$(date +%Y%m%d_%H%M%S)_CDT --execute
done
```

| Archive directory | Time (CDT) | Selection | Runs | Cells | Result rows |
|---|---|---|---|---|---|
| `devstral24b_summary_bug_rerun2_20260908_191403_CDT` | 19:14:03 | devstral24b, 4 reasons | 407 (151 old + 256 new) | 8 | 960 → 553 |
| `glm47flash_summary_bug_rerun2_20260908_191403_CDT` | 19:14:03 | glm47flash, 4 reasons | 407 (240 + 167) | 6 | 698 → 291 |
| `qwen35b_summary_bug_rerun2_20260908_191404_CDT` | 19:14:04 | qwen35b main + ablation, 4 reasons | 577 (382 + 195) | 16 | 1148 → 571 |

`trajectory.json` count in `ICLR_results/terminalbench` afterwards: 3487. Next: relaunch
`run_agent_models_expansion_tb.sh` for devstral main, qwen main, qwen ablation, glm main (see "Rerun status"),
then `python scripts/build_coverage.py`.

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
