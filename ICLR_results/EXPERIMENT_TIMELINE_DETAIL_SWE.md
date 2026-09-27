# SWE-bench experiment command history: 2026-08-23–2026-09-27

Compiled by cross-checking local `.bash_history`, execution logs, Git history, calibration artifacts, and archive records in the `akiho-expansion` workspace. All times are **CDT (UTC−5)**. Inspection snapshot: **2026-09-07 20:41 CDT**. The detailed local log history starts with the August 23 run_3 expansion; earlier experiments in `Active_runs.md` are background and are not reconstructed here. A continuation covering 2026-09-08–2026-09-27 (second inspection snapshot **2026-09-27 14:42 CDT**, after the workspace moved to `/home/ak58925/ICLR27/agentCtx`) follows the original September 7 sections below.

This follows the structure of [EXPERIMENT_TIMELINE_DETAIL.md on akiho-expansion-terminalbench-0829](https://github.com/ritulS/agentCtx/blob/41cd02e78d9d186a2f2c6a804b8ff18de6d03a32/ICLR_results/EXPERIMENT_TIMELINE_DETAIL.md). The remote branch tip was verified as `41cd02e78d9d186a2f2c6a804b8ff18de6d03a32` during compilation. SWE evidence below comes from this local workspace, not the Terminal-Bench host.

Commands are historical excerpts, with `nohup`, redirection, and shared Podman environment settings often omitted. Reconstructed commands are labeled; current scripts may differ from the versions used at launch. Shell history has no command timestamps, so exact times come from log banners unless explicitly labeled as approximate, metadata-derived, or documented. Stage starts and resumes do not imply new trials or completion. No experiments were launched, resumed, stopped, or modified while compiling this document.

## Launch chronology

| Start (CDT) | Experiment or operation | Launch command (excerpt) | Progress and outcome | Source log / record |
|---|---|---|---|---|
| 08/23 17:24:53; 17:26:34 | Qwen / runs per task 2 → 3 / initial start and restart | `bash scripts/run_run3_expansion.sh` (historical script; reconstructed) | Block 1 starts twice. The second entry runs NEW-70 singles, with 700 existing and 350 remaining keys at 15K. Later blocks fill the ABL-30 portion. | [run3_expansion.log:1](../logs/run3_expansion.log#L1), [run3_expansion.log:19](../logs/run3_expansion.log#L19) |
| 08/25 12:11:06 | Qwen / run_3 expansion resume | `bash scripts/run_run3_expansion.sh` (reconstructed) | Revisits P100 singles, then ABL-30 source cells. Block 2 starts 08/25 21:38:35; Block 3 starts 08/26 16:03:09; unlimited baselines start 08/28 05:40:29. Completion marker: 08/28 10:54:59. | [run3_expansion.log:7359](../logs/run3_expansion.log#L7359), [run3_expansion.log:20144](../logs/run3_expansion.log#L20144) |
| 08/28 (time not recorded) | Qwen / organize completed run_3 grid | `python3 scripts/archive_and_organize_qwen35b_swebench.py --backup-root /home/ak58925/agentCtx_backups/run3-complete-2026-08-28` (historical path) | Copied results to ICLR_results; 65 cells reported COMPLETE (35 main, 30 ablation) at that time. This predates the summary-marker archive and the September 7 scope adjustment. | [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#follow-up-1--runstask-2--3) |
| 08/28 12:15:07 | Devstral / SB:P100 / FC run_1 calibration | `bash scripts/run_budget_calibration_sb.sh devstral` (reconstructed from wrapper output) | 100 uncompressed trajectories; DONE at 14:06:40. FC run_1 is reused by the main grid. | [devstral24b_sb_fc_run1.log:1](../logs/devstral24b_sb_fc_run1.log#L1), [devstral24b_sb_fc_run1.log:482](../logs/devstral24b_sb_fc_run1.log#L482) |
| 08/28 15:38:19 | GLM / SB:P100 / FC run_1 calibration | `bash scripts/run_budget_calibration_sb.sh glm` (reconstructed from wrapper output) | 100 uncompressed trajectories; DONE at 17:47:00. This is a completed calibration even though the older experiment log still has GLM TODO entries. | [glm47flash_sb_fc_run1.log:1](../logs/glm47flash_sb_fc_run1.log#L1), [glm47flash_sb_fc_run1.log:459](../logs/glm47flash_sb_fc_run1.log#L459) |
| 08/28 19:28:46 | Devstral / initial main / superseded 43K budget | `bash scripts/run_agent_models_expansion.sh devstral` (historical settings reconstructed from log) | Starts TR@43K. The old grid used A/P/B = 38K/43K/49K; it was subsequently archived. | [followup_agent_models_devstral.log:1](../logs/followup_agent_models_devstral.log#L1) |
| 08/29 00:15:06; 00:30:32 | Devstral / old main grid resumes | `MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion.sh devstral` | TR@43K is revisited. The experiment log identifies commit 20df6a5 for the 00:30 launch; cell records confirm this was still the old budget grid. | [followup_agent_models_devstral.log:1093](../logs/followup_agent_models_devstral.log#L1093), [followup_agent_models_devstral.log:1111](../logs/followup_agent_models_devstral.log#L1111) |
| 08/29 15:19:15; 17:20:12; 17:21:46 | Devstral / old ABL-30 phase and repeated phase starts | `bash scripts/run_agent_models_expansion.sh devstral` (within historical launchers) | Repeated/interleaved cell entries occur. Completion banners appear on 08/31 at 01:06:18, 01:07:46, and 01:08:36. They are launcher markers, not evidence of three independent successful grids. | [followup_agent_models_devstral.log:20444](../logs/followup_agent_models_devstral.log#L20444), [followup_agent_models_devstral.log:21774](../logs/followup_agent_models_devstral.log#L21774), [followup_agent_models_devstral.log:21966](../logs/followup_agent_models_devstral.log#L21966), [followup_agent_models_devstral.log:55537](../logs/followup_agent_models_devstral.log#L55537) |
| 08/31 before 02:00 (exact time unrecorded) | Devstral / archive old 38K/43K/49K cells | Shell-history move loop for old numeric-budget directories | Old-budget results, logs, and script/config snapshots survive under /home/ak58925/agentCtx_backups/devstral-swebench-p75-p85-p95_38k-43k-49k_complete-20260831/. Unlimited baseline cells were retained. This is an archive operation, not new trials. | Local .bash_history (old-budget archive block); external backup directory |
| 08/31 02:00:42 | Devstral / adopted 21K main / failed attempt | `bash scripts/run_agent_models_expansion_notified.sh devstral` | TR has zero-call failures. The 02:28:10-named Podman-failure backup reports 265 original rows, 21 retained, 244 removed, and 260 run directories quarantined; the directory timestamp does not establish an exact repair completion time. | [followup_agent_models_devstral.log:56060](../logs/followup_agent_models_devstral.log#L56060), [followup_agent_models_devstral.log:56078](../logs/followup_agent_models_devstral.log#L56078); external backup repair_summary.txt |
| 08/31 02:30:26; 02:34:19 | Devstral / adopted 17K/21K/24K grid / resume | `MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh devstral` | The 02:30 entry has no following worker output before the 02:34 restart. The sustained resume starts TR at 02:34:20, then progresses through main. PID 2882597 is recorded in EXPERIMENT_LOG.md. | [followup_agent_models_devstral.log:56600](../logs/followup_agent_models_devstral.log#L56600), [followup_agent_models_devstral.log:56602](../logs/followup_agent_models_devstral.log#L56602) |
| 09/02 13:58:34 | Devstral / adopted grid reaches ABL-30 | `bash scripts/run_agent_models_expansion.sh devstral` (within the 08/31 resume) | Starts d03__b17k__tr after main FC/OTRC stages. Those baseline stages include existing-key skips; OTRC is separately repaired on September 3. | [followup_agent_models_devstral.log:68245](../logs/followup_agent_models_devstral.log#L68245) |
| 09/03 about 13:10 | Devstral / quarantine and rerun P100 OTRC | `venv/bin/python3 scripts/run_experiment_iclr.py --iclr-section main --iclr-model devstral24b --iclr-cell di__binf__otrc --conditions online-trc --budget 999999999 --runs-per-task 3 --max-workers 16 …` | Quarantined index contains 300 zero-call records dated 08/29. Replacement result timestamps span 09/03 13:14:55–15:54:40; generation and patch evaluation are separate stages. Launch estimate uses PID-file mtime, not a timestamped launch banner. | [devstral24b_p100_otrc_rerun.log:1](../logs/devstral24b_p100_otrc_rerun.log#L1); [quarantined index](../quarantined_results/devstral24b_di__binf__otrc_failed_20260829/experiment_results.json) |
| 09/03 about 20:01 | Devstral / OTRC evaluation-only retry | `venv/bin/python3 scripts/run_experiment_iclr.py … --eval-only` (same OTRC cell) | Retry log records two patch evaluations, both FAILED; no new agent trials. Time is the PID-file mtime. | [devstral24b_p100_otrc_eval_retry.log:16](../logs/devstral24b_p100_otrc_eval_retry.log#L16) |
| 09/03 20:07:38 | Devstral / main and ablation resume | `MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh devstral` | Main is revisited; ABL-30 resumes at 20:08:37. Completion banner appears 09/04 22:38:44, but the final cells include zero-call failures; subsequent repair was needed. | [followup_agent_models_devstral.log:72579](../logs/followup_agent_models_devstral.log#L72579), [followup_agent_models_devstral.log:73046](../logs/followup_agent_models_devstral.log#L73046), [followup_agent_models_devstral.log:83682](../logs/followup_agent_models_devstral.log#L83682) |
| 09/04 23:21:50 | Devstral / post-repair resume | `bash scripts/run_agent_models_expansion_notified.sh devstral` (wrapper association from history) | Main → ablation at 23:21:52; completion banner at 23:33:46. Existing bad rows could still be skipped; a further retry selection follows. | [followup_agent_models_devstral.log:83684](../logs/followup_agent_models_devstral.log#L83684), [followup_agent_models_devstral.log:85944](../logs/followup_agent_models_devstral.log#L85944) |
| 09/04 about 23:39:24 | Devstral / select ablation retry rows | One-off repair script (exact command not reconstructed) | Saved retry manifest contains 2,176 keys across 25 cells. Time comes from the backup directory name; row timestamps in the manifest describe the old results. | [retry_manifest.json](../backups/devstral_ablation_retry_20260904_233924_467453/retry_manifest.json) |
| 09/04 23:55:21 | Devstral / retry selected ABL-30 failures | `MAX_WORKERS=16 RUN_EVAL=1 PYTHONUNBUFFERED=1 bash scripts/run_agent_models_expansion_notified.sh devstral` | Main and earlier ablation cells are revisited; missing keys execute. Last model completion banner: 09/06 13:44:22; wrapper completion at 13:44:23. The September 7 summary-marker archive later removes additional runs. | [followup_agent_models_devstral.log:85946](../logs/followup_agent_models_devstral.log#L85946), [followup_agent_models_devstral.log:95679](../logs/followup_agent_models_devstral.log#L95679) |
| 09/06 17:51:42 | GLM / main P100 / primary budget 13K | `MAX_WORKERS=16 RUN_EVAL=1 PYTHONUNBUFFERED=1 bash scripts/run_agent_models_expansion_notified.sh glm` | TR → SU-full at 23:59:49 → SU-partial on 09/07 07:27:08 → SS at 14:57:43. Last agent progress is 191/300 in SS; no main/ablation completion banner. The launcher reports that the notification webhook was not configured. | [followup_agent_models_glm_launcher.log:2](../logs/followup_agent_models_glm_launcher.log#L2), [followup_agent_models_glm.log:1](../logs/followup_agent_models_glm.log#L1) |
| 09/07 (fix/audit; precise launch time unavailable) | SWE / summary-call bug fix and archive candidate audit | Audit scripts retained under archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/ | Local audit scans 22,979 trajectories and selects 2,359 summary_marker_error runs. Additional accounting/response candidates are not part of the automatic archive selection. | [local audit README](../archives/summary-bug-audit-20260907_185802_CDT/README.md) |
| 09/07 19:26:44 (archive metadata) | SWE / archive summary-marker runs | `venv/bin/python …/archive_swebench_rerun_targets.py --root "$PWD" --rerun-csv …/archive_targets.csv --archive-name swebench_summary_marker_error_20260907_192635_CDT --execute` (reconstructed) | Archive status is complete: 2,359 run directories, 2,358 index rows removed; one run was unindexed. This is preprocessing for reruns. | [archive README](../archives/swebench_summary_marker_error_20260907_192635_CDT/README.md), [status.json](../archives/swebench_summary_marker_error_20260907_192635_CDT/status.json) |
| 09/07 19:44 (documented) | Qwen / reuse 10K/20K main results for ABL-30 | `venv/bin/python scripts/reuse_qwen_main_for_ablation.py --execute` | Copied 1,761 existing runs across 22 ablation cells; 219 keys remained pending. Source P100 cells were preserved, so copied runs must not be counted as independent trials. | [archive/reuse log](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md#2026-09-07-1944-qwen-main-10k20k-cells-reused-for-ablation-swe-bench) |
| 09/07 20:01:53 | Qwen / summary-bug rerun / P100 then ABL-30 | `MAX_WORKERS=16 RUN_EVAL=1 QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 bash scripts/run_agent_models_expansion_notified.sh qwen` | Resume HEAD da461d6, with an uncommitted step_completion_tokens recording change. Reaches SS@15K at 20:08:05. No completion banner; see the inspection snapshot below before treating it as currently running. | [followup_agent_models_qwen_launcher.log:1](../logs/followup_agent_models_qwen_launcher.log#L1), [followup_agent_models_qwen_launcher.log:106](../logs/followup_agent_models_qwen_launcher.log#L106) |

## Budget and cohort decisions

| Model / phase | A / P / B (tokens) | Interpretation / source |
|---|---|---|
| Qwen | 10,000 / 15,000 / 20,000 | Existing budget values; September 7 launcher uses P100 at 15K plus unlimited baselines, and ABL-30 for the budget/depth ablations. Legacy 10K/20K P100 source cells remain on disk. |
| Devstral calibration report, August 28 | 16,000 / 19,000 / 23,000 | Trigger-rate matching (96% / 90% / 77%); [saved report](swebench/main/devstral24b/di__binf__fc/calibration_report.txt). These are reference outputs, not the final adopted grid. |
| Devstral superseded grid | 38,000 / 43,000 / 49,000 | Historical P75/P85/P95 grid; archived August 31. Log cell starts below retain those original names. |
| Devstral adopted grid | 17,000 / 21,000 / 24,000 | P5/P15/P25 rule rounded to 1K; [decision and commit provenance](EXPERIMENT_LOG.md#devstral-status--2026-08-31-1345-cdt). Working-tree launcher changes used at the 08/31 02:34 resume were later committed as `7b4bbe4`. |
| GLM calibration report, August 28 | 9,000 / 11,000 / 15,000 | Trigger-rate matching (96% / 90% / 74%); [saved report](swebench/main/glm47flash/di__binf__fc/calibration_report.txt). |
| GLM adopted launcher grid | 10,000 / 13,000 / 15,000 | [Launcher defaults](../scripts/run_agent_models_expansion.sh) and [experiment plan](../exp_plans/FOLLOWUP_EXPERIMENTS.md); log explicitly records `budget=13000` for `bP`. A separate timestamped budget-approval event was not identified. |

The current per-model target is 13 main cells × 100 tasks × 3 runs = **3,900** keys, plus 52 ablation cells × 30 tasks × 3 runs = **4,680** keys, totaling **8,580 planned keys**. This target is not a count of new runs in any one resume. FC calibration collects only run_1 and is reused. The older Qwen layout has 35 main + 30 ablation cells; the September 7 reuse operation adds 22 ablation cells while keeping their main sources. Do not sum both layouts as independent experiments.

`d03/d05/d07` denote depths 0.3/0.5/0.7; `di` is depth-invariant. Numeric tags such as `b21k` denote token budgets; GLM uses `bA/bP/bB` for 10K/13K/15K in the adopted grid. `binf` means an unlimited compression threshold, represented by 999,999,999 in commands, not an unlimited model context window. Expansion workers are 16; vLLM `--max-num-seqs` is a separate server setting.

## Cell transitions within each launch

All **465 timestamped cell-start entries** from the four primary logs are retained below: Qwen run_3 (39), Devstral (418), GLM (4), and Qwen September 7 resume (4). Mirrored launcher/nohup logs are not counted again. FC calibration and standalone OTRC retries are covered in the launch chronology because they do not have the same cell-start marker.

Within each table, entries are sorted by logged time and then source line. Devstral's old log contains interleaved repeats and NUL bytes; NUL bytes were ignored during extraction without removing newlines. Repeated starts can represent another launcher, a retry, or an existing-key skip. Even an `8,580 planned runs` completion banner does not establish that all keys represent valid agent executions or evaluated patches.

### Qwen run_3 expansion: legacy source-cell transitions

Paths in this table are relative to `results/ablations/` (a symlink to `data/swebench/ablations/`). A source cell can contain several conditions, subsequently split into ICLR cells by the organization script. NEW-70 and ABL-30 stages together fill the intended cohort; a `p100-*` directory name alone does not identify the task subset executed in a particular stage. The historical launcher is available at `git show 27606ac:scripts/run_run3_expansion.sh`.

| Start (CDT) | Cell / settings | Source |
|---|---|---|
| 08/23 17:24:53 | `p100-singles-15000` — budget=15000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:2](../logs/run3_expansion.log#L2) |
| 08/23 17:26:34 | `p100-singles-15000` — budget=15000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:4](../logs/run3_expansion.log#L4) |
| 08/24 01:25:25 | `p100-singles-10000` — budget=10000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:2465](../logs/run3_expansion.log#L2465) |
| 08/24 01:35:29 | `p100-singles-10000` — budget=10000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:2486](../logs/run3_expansion.log#L2486) |
| 08/24 09:25:41 | `p100-singles-20000` — budget=20000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:4822](../logs/run3_expansion.log#L4822) |
| 08/24 09:35:02 | `p100-singles-20000` — budget=20000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:4843](../logs/run3_expansion.log#L4843) |
| 08/25 12:11:06 | `p100-singles-15000` — budget=15000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:7360](../logs/run3_expansion.log#L7360) |
| 08/25 12:11:17 | `p100-singles-10000` — budget=10000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:7398](../logs/run3_expansion.log#L7398) |
| 08/25 12:12:46 | `p100-singles-20000` — budget=20000 depth=0.5 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:7442](../logs/run3_expansion.log#L7442) |
| 08/25 12:12:59 | `timing-10k` — budget=10000 depth=0.5 ; truncation summarization | [run3_expansion.log:7482](../logs/run3_expansion.log#L7482) |
| 08/25 13:31:30 | `timing-20k` — budget=20000 depth=0.5 ; truncation summarization | [run3_expansion.log:7707](../logs/run3_expansion.log#L7707) |
| 08/25 14:44:34 | `partial-10000` — budget=10000 depth=0.5 ; summarization-partial structured-summarize-partial structured-summarize | [run3_expansion.log:7950](../logs/run3_expansion.log#L7950) |
| 08/25 16:53:49 | `partial-15000` — budget=15000 depth=0.5 ; summarization-partial structured-summarize-partial | [run3_expansion.log:8294](../logs/run3_expansion.log#L8294) |
| 08/25 18:06:17 | `partial-20000` — budget=20000 depth=0.5 ; summarization-partial structured-summarize-partial structured-summarize | [run3_expansion.log:8539](../logs/run3_expansion.log#L8539) |
| 08/25 19:58:42 | `qwen3.5-35B-A3B_15k_Fullrun` — budget=15000 depth=0.5 ; truncation summarization structured-summarize | [run3_expansion.log:8899](../logs/run3_expansion.log#L8899) |
| 08/25 21:38:35 | `p100-depth30-singles-15000` — budget=15000 depth=0.3 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:9244](../logs/run3_expansion.log#L9244) |
| 08/26 00:38:58 | `p100-depth30-singles-10000` — budget=10000 depth=0.3 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:9801](../logs/run3_expansion.log#L9801) |
| 08/26 03:45:19 | `p100-depth30-singles-20000` — budget=20000 depth=0.3 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:10336](../logs/run3_expansion.log#L10336) |
| 08/26 06:49:32 | `p100-depth70-singles-15000` — budget=15000 depth=0.7 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:10911](../logs/run3_expansion.log#L10911) |
| 08/26 10:00:59 | `p100-depth70-singles-10000` — budget=10000 depth=0.7 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:11475](../logs/run3_expansion.log#L11475) |
| 08/26 13:01:21 | `p100-depth70-singles-20000` — budget=20000 depth=0.7 ; truncation summarization summarization-partial structured-summarize structured-summarize-partial | [run3_expansion.log:12017](../logs/run3_expansion.log#L12017) |
| 08/26 16:03:09 | `p100-trc-15000` — budget=15000 depth=0.5 ; tool-result-clear trc-su trc-ss | [run3_expansion.log:12585](../logs/run3_expansion.log#L12585) |
| 08/26 21:10:04 | `p100-otrc-15000` — budget=15000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:13362](../logs/run3_expansion.log#L13362) |
| 08/27 02:06:00 | `p100-trc-10000` — budget=10000 depth=0.5 ; tool-result-clear trc-su trc-ss | [run3_expansion.log:14121](../logs/run3_expansion.log#L14121) |
| 08/27 06:18:38 | `p100-otrc-10000` — budget=10000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:14872](../logs/run3_expansion.log#L14872) |
| 08/27 10:31:33 | `p100-trc-20000` — budget=20000 depth=0.5 ; tool-result-clear trc-su trc-ss | [run3_expansion.log:15576](../logs/run3_expansion.log#L15576) |
| 08/27 15:04:41 | `p100-otrc-20000` — budget=20000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:16366](../logs/run3_expansion.log#L16366) |
| 08/27 19:08:26 | `timing-10k` — budget=10000 depth=0.5 ; tool-result-clear | [run3_expansion.log:17118](../logs/run3_expansion.log#L17118) |
| 08/27 19:42:27 | `timing-20k` — budget=20000 depth=0.5 ; tool-result-clear | [run3_expansion.log:17251](../logs/run3_expansion.log#L17251) |
| 08/27 20:23:32 | `stacked-15000` — budget=15000 depth=0.5 ; trc-su trc-ss | [run3_expansion.log:17392](../logs/run3_expansion.log#L17392) |
| 08/27 21:35:13 | `otrc-stacked-15000` — budget=15000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:17644](../logs/run3_expansion.log#L17644) |
| 08/27 23:10:06 | `stacked-10000` — budget=10000 depth=0.5 ; trc-su trc-ss | [run3_expansion.log:18001](../logs/run3_expansion.log#L18001) |
| 08/28 00:21:14 | `otrc-stacked-10000` — budget=10000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:18251](../logs/run3_expansion.log#L18251) |
| 08/28 01:59:25 | `stacked-20000` — budget=20000 depth=0.5 ; trc-su trc-ss | [run3_expansion.log:18567](../logs/run3_expansion.log#L18567) |
| 08/28 03:16:29 | `otrc-stacked-20000` — budget=20000 depth=0.5 ; otrc-tr otrc-su-partial otrc-ss-partial | [run3_expansion.log:18827](../logs/run3_expansion.log#L18827) |
| 08/28 05:04:42 | `qwen3.5-35B-A3B_15k_Fullrun` — budget=15000 depth=0.5 ; tool-result-clear | [run3_expansion.log:19186](../logs/run3_expansion.log#L19186) |
| 08/28 05:40:29 | `p100-inf` — budget=999999999 depth=0.5 ; full-context online-trc | [run3_expansion.log:19328](../logs/run3_expansion.log#L19328) |
| 08/28 09:17:51 | `qwen3.5-35B-A3B_15k_Fullrun` — budget=999999999 depth=0.5 ; full-context | [run3_expansion.log:19861](../logs/run3_expansion.log#L19861) |
| 08/28 10:11:45 | `qwen35-a3b_online-trc` — budget=999999999 depth=0.5 ; online-trc | [run3_expansion.log:20004](../logs/run3_expansion.log#L20004) |

### Devstral: superseded grid, August 28–31

These starts predate the adopted 17K/21K/24K resume. They remain historical evidence; old-budget results belong to the external archive described above. Unlimited baseline entries also appear here; the failed OTRC baseline was later quarantined and replaced.

| Start (CDT) | Cell | Source |
|---|---|---|
| 08/28 19:28:46 | `main/devstral24b/d05__b43k__tr` | [followup_agent_models_devstral.log:2](../logs/followup_agent_models_devstral.log#L2) |
| 08/29 00:15:06 | `main/devstral24b/d05__b43k__tr` | [followup_agent_models_devstral.log:1094](../logs/followup_agent_models_devstral.log#L1094) |
| 08/29 00:30:32 | `main/devstral24b/d05__b43k__tr` | [followup_agent_models_devstral.log:1112](../logs/followup_agent_models_devstral.log#L1112) |
| 08/29 00:30:48 | `main/devstral24b/d05__b43k__su-full` | [followup_agent_models_devstral.log:1152](../logs/followup_agent_models_devstral.log#L1152) |
| 08/29 00:30:56 | `main/devstral24b/d05__b43k__su-full` | [followup_agent_models_devstral.log:1232](../logs/followup_agent_models_devstral.log#L1232) |
| 08/29 00:31:14 | `main/devstral24b/d05__b43k__su-full` | [followup_agent_models_devstral.log:1284](../logs/followup_agent_models_devstral.log#L1284) |
| 08/29 02:39:45 | `main/devstral24b/d05__b43k__su-partial` | [followup_agent_models_devstral.log:3395](../logs/followup_agent_models_devstral.log#L3395) |
| 08/29 02:44:22 | `main/devstral24b/d05__b43k__su-partial` | [followup_agent_models_devstral.log:3541](../logs/followup_agent_models_devstral.log#L3541) |
| 08/29 03:33:05 | `main/devstral24b/d05__b43k__su-partial` | [followup_agent_models_devstral.log:4029](../logs/followup_agent_models_devstral.log#L4029) |
| 08/29 05:23:44 | `main/devstral24b/d05__b43k__ss` | [followup_agent_models_devstral.log:6229](../logs/followup_agent_models_devstral.log#L6229) |
| 08/29 05:26:06 | `main/devstral24b/d05__b43k__ss` | [followup_agent_models_devstral.log:6254](../logs/followup_agent_models_devstral.log#L6254) |
| 08/29 05:30:43 | `main/devstral24b/d05__b43k__ss` | [followup_agent_models_devstral.log:6293](../logs/followup_agent_models_devstral.log#L6293) |
| 08/29 07:43:54 | `main/devstral24b/d05__b43k__ss-partial` | [followup_agent_models_devstral.log:8660](../logs/followup_agent_models_devstral.log#L8660) |
| 08/29 07:46:00 | `main/devstral24b/d05__b43k__ss-partial` | [followup_agent_models_devstral.log:8869](../logs/followup_agent_models_devstral.log#L8869) |
| 08/29 07:51:35 | `main/devstral24b/d05__b43k__ss-partial` | [followup_agent_models_devstral.log:8894](../logs/followup_agent_models_devstral.log#L8894) |
| 08/29 09:50:21 | `main/devstral24b/di__b43k__trc` | [followup_agent_models_devstral.log:10757](../logs/followup_agent_models_devstral.log#L10757) |
| 08/29 09:52:45 | `main/devstral24b/di__b43k__trc` | [followup_agent_models_devstral.log:10932](../logs/followup_agent_models_devstral.log#L10932) |
| 08/29 10:50:41 | `main/devstral24b/di__b43k__trc-su` | [followup_agent_models_devstral.log:12199](../logs/followup_agent_models_devstral.log#L12199) |
| 08/29 11:31:44 | `main/devstral24b/di__b43k__trc` | [followup_agent_models_devstral.log:12743](../logs/followup_agent_models_devstral.log#L12743) |
| 08/29 12:26:11 | `main/devstral24b/di__b43k__trc-su` | [followup_agent_models_devstral.log:14176](../logs/followup_agent_models_devstral.log#L14176) |
| 08/29 12:38:21 | `main/devstral24b/di__b43k__trc-ss` | [followup_agent_models_devstral.log:14402](../logs/followup_agent_models_devstral.log#L14402) |
| 08/29 12:38:30 | `main/devstral24b/di__b43k__trc-ss` | [followup_agent_models_devstral.log:14494](../logs/followup_agent_models_devstral.log#L14494) |
| 08/29 12:38:45 | `main/devstral24b/di__b43k__trc-su` | [followup_agent_models_devstral.log:14578](../logs/followup_agent_models_devstral.log#L14578) |
| 08/29 12:38:45 | `main/devstral24b/di__b43k__trc-ss` | [followup_agent_models_devstral.log:14612](../logs/followup_agent_models_devstral.log#L14612) |
| 08/29 14:26:08 | `main/devstral24b/di__b43k__otrc-tr` | [followup_agent_models_devstral.log:16615](../logs/followup_agent_models_devstral.log#L16615) |
| 08/29 14:26:35 | `main/devstral24b/di__b43k__otrc-su-partial` | [followup_agent_models_devstral.log:17249](../logs/followup_agent_models_devstral.log#L17249) |
| 08/29 14:27:02 | `main/devstral24b/di__b43k__otrc-ss-partial` | [followup_agent_models_devstral.log:17883](../logs/followup_agent_models_devstral.log#L17883) |
| 08/29 14:27:28 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:18517](../logs/followup_agent_models_devstral.log#L18517) |
| 08/29 14:37:17 | `main/devstral24b/di__b43k__otrc-tr` | [followup_agent_models_devstral.log:18758](../logs/followup_agent_models_devstral.log#L18758) |
| 08/29 14:37:17 | `main/devstral24b/di__b43k__otrc-su-partial` | [followup_agent_models_devstral.log:18792](../logs/followup_agent_models_devstral.log#L18792) |
| 08/29 14:37:17 | `main/devstral24b/di__b43k__otrc-ss-partial` | [followup_agent_models_devstral.log:18826](../logs/followup_agent_models_devstral.log#L18826) |
| 08/29 14:37:17 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:18860](../logs/followup_agent_models_devstral.log#L18860) |
| 08/29 15:18:48 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:19810](../logs/followup_agent_models_devstral.log#L19810) |
| 08/29 15:19:15 | `ablation/devstral24b/d03__b38k__tr` | [followup_agent_models_devstral.log:20445](../logs/followup_agent_models_devstral.log#L20445) |
| 08/29 16:09:50 | `main/devstral24b/di__b43k__otrc-tr` | [followup_agent_models_devstral.log:20925](../logs/followup_agent_models_devstral.log#L20925) |
| 08/29 16:09:50 | `main/devstral24b/di__b43k__otrc-su-partial` | [followup_agent_models_devstral.log:20959](../logs/followup_agent_models_devstral.log#L20959) |
| 08/29 16:09:50 | `main/devstral24b/di__b43k__otrc-ss-partial` | [followup_agent_models_devstral.log:20993](../logs/followup_agent_models_devstral.log#L20993) |
| 08/29 16:09:50 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:21027](../logs/followup_agent_models_devstral.log#L21027) |
| 08/29 17:00:53 | `ablation/devstral24b/d03__b38k__su-full` | [followup_agent_models_devstral.log:21669](../logs/followup_agent_models_devstral.log#L21669) |
| 08/29 17:20:12 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:21740](../logs/followup_agent_models_devstral.log#L21740) |
| 08/29 17:20:12 | `ablation/devstral24b/d03__b38k__tr` | [followup_agent_models_devstral.log:21775](../logs/followup_agent_models_devstral.log#L21775) |
| 08/29 17:21:44 | `ablation/devstral24b/d03__b38k__su-full` | [followup_agent_models_devstral.log:21815](../logs/followup_agent_models_devstral.log#L21815) |
| 08/29 17:21:46 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:21932](../logs/followup_agent_models_devstral.log#L21932) |
| 08/29 17:21:46 | `ablation/devstral24b/d03__b38k__tr` | [followup_agent_models_devstral.log:21967](../logs/followup_agent_models_devstral.log#L21967) |
| 08/29 17:21:46 | `ablation/devstral24b/d03__b38k__su-full` | [followup_agent_models_devstral.log:22001](../logs/followup_agent_models_devstral.log#L22001) |
| 08/29 18:15:07 | `ablation/devstral24b/d03__b38k__su-partial` | [followup_agent_models_devstral.log:22576](../logs/followup_agent_models_devstral.log#L22576) |
| 08/29 18:15:39 | `ablation/devstral24b/d03__b38k__su-partial` | [followup_agent_models_devstral.log:22747](../logs/followup_agent_models_devstral.log#L22747) |
| 08/29 18:16:35 | `ablation/devstral24b/d03__b38k__su-partial` | [followup_agent_models_devstral.log:22930](../logs/followup_agent_models_devstral.log#L22930) |
| 08/29 19:35:07 | `ablation/devstral24b/d03__b38k__ss` | [followup_agent_models_devstral.log:23618](../logs/followup_agent_models_devstral.log#L23618) |
| 08/29 19:35:27 | `ablation/devstral24b/d03__b38k__ss` | [followup_agent_models_devstral.log:23724](../logs/followup_agent_models_devstral.log#L23724) |
| 08/29 19:56:59 | `ablation/devstral24b/d03__b38k__ss` | [followup_agent_models_devstral.log:23966](../logs/followup_agent_models_devstral.log#L23966) |
| 08/29 20:28:20 | `ablation/devstral24b/d03__b38k__ss-partial` | [followup_agent_models_devstral.log:24600](../logs/followup_agent_models_devstral.log#L24600) |
| 08/29 20:30:30 | `ablation/devstral24b/d03__b38k__ss-partial` | [followup_agent_models_devstral.log:24714](../logs/followup_agent_models_devstral.log#L24714) |
| 08/29 21:16:39 | `ablation/devstral24b/d03__b38k__ss-partial` | [followup_agent_models_devstral.log:25184](../logs/followup_agent_models_devstral.log#L25184) |
| 08/29 21:53:29 | `ablation/devstral24b/d03__b43k__tr` | [followup_agent_models_devstral.log:25591](../logs/followup_agent_models_devstral.log#L25591) |
| 08/29 21:54:16 | `ablation/devstral24b/d03__b43k__tr` | [followup_agent_models_devstral.log:25737](../logs/followup_agent_models_devstral.log#L25737) |
| 08/29 21:55:44 | `ablation/devstral24b/d03__b43k__tr` | [followup_agent_models_devstral.log:25881](../logs/followup_agent_models_devstral.log#L25881) |
| 08/29 23:16:48 | `ablation/devstral24b/d03__b43k__su-full` | [followup_agent_models_devstral.log:26682](../logs/followup_agent_models_devstral.log#L26682) |
| 08/29 23:16:49 | `ablation/devstral24b/d03__b43k__su-full` | [followup_agent_models_devstral.log:26822](../logs/followup_agent_models_devstral.log#L26822) |
| 08/29 23:22:54 | `ablation/devstral24b/d03__b43k__su-full` | [followup_agent_models_devstral.log:26970](../logs/followup_agent_models_devstral.log#L26970) |
| 08/30 00:09:28 | `ablation/devstral24b/d03__b43k__su-partial` | [followup_agent_models_devstral.log:27650](../logs/followup_agent_models_devstral.log#L27650) |
| 08/30 00:17:57 | `ablation/devstral24b/d03__b43k__su-partial` | [followup_agent_models_devstral.log:27756](../logs/followup_agent_models_devstral.log#L27756) |
| 08/30 00:23:51 | `ablation/devstral24b/d03__b43k__su-partial` | [followup_agent_models_devstral.log:27892](../logs/followup_agent_models_devstral.log#L27892) |
| 08/30 01:26:17 | `ablation/devstral24b/d03__b43k__ss` | [followup_agent_models_devstral.log:28588](../logs/followup_agent_models_devstral.log#L28588) |
| 08/30 01:26:46 | `ablation/devstral24b/d03__b43k__ss` | [followup_agent_models_devstral.log:28710](../logs/followup_agent_models_devstral.log#L28710) |
| 08/30 01:29:37 | `ablation/devstral24b/d03__b43k__ss` | [followup_agent_models_devstral.log:28868](../logs/followup_agent_models_devstral.log#L28868) |
| 08/30 02:05:49 | `ablation/devstral24b/d03__b43k__ss-partial` | [followup_agent_models_devstral.log:29561](../logs/followup_agent_models_devstral.log#L29561) |
| 08/30 02:09:57 | `ablation/devstral24b/d03__b43k__ss-partial` | [followup_agent_models_devstral.log:29615](../logs/followup_agent_models_devstral.log#L29615) |
| 08/30 02:11:06 | `ablation/devstral24b/d03__b43k__ss-partial` | [followup_agent_models_devstral.log:29687](../logs/followup_agent_models_devstral.log#L29687) |
| 08/30 02:12:12 | `ablation/devstral24b/d03__b49k__tr` | [followup_agent_models_devstral.log:29791](../logs/followup_agent_models_devstral.log#L29791) |
| 08/30 02:12:44 | `ablation/devstral24b/d03__b49k__su-full` | [followup_agent_models_devstral.log:30005](../logs/followup_agent_models_devstral.log#L30005) |
| 08/30 02:13:16 | `ablation/devstral24b/d03__b49k__su-partial` | [followup_agent_models_devstral.log:30219](../logs/followup_agent_models_devstral.log#L30219) |
| 08/30 02:13:49 | `ablation/devstral24b/d03__b49k__ss` | [followup_agent_models_devstral.log:30433](../logs/followup_agent_models_devstral.log#L30433) |
| 08/30 02:21:44 | `ablation/devstral24b/d03__b49k__ss-partial` | [followup_agent_models_devstral.log:30892](../logs/followup_agent_models_devstral.log#L30892) |
| 08/30 02:49:39 | `ablation/devstral24b/d03__b49k__tr` | [followup_agent_models_devstral.log:31027](../logs/followup_agent_models_devstral.log#L31027) |
| 08/30 02:49:39 | `ablation/devstral24b/d03__b49k__su-full` | [followup_agent_models_devstral.log:31061](../logs/followup_agent_models_devstral.log#L31061) |
| 08/30 02:49:39 | `ablation/devstral24b/d03__b49k__su-partial` | [followup_agent_models_devstral.log:31095](../logs/followup_agent_models_devstral.log#L31095) |
| 08/30 02:49:39 | `ablation/devstral24b/d03__b49k__ss` | [followup_agent_models_devstral.log:31129](../logs/followup_agent_models_devstral.log#L31129) |
| 08/30 02:49:40 | `ablation/devstral24b/d03__b49k__ss-partial` | [followup_agent_models_devstral.log:31163](../logs/followup_agent_models_devstral.log#L31163) |
| 08/30 03:22:04 | `ablation/devstral24b/d03__b49k__tr` | [followup_agent_models_devstral.log:31564](../logs/followup_agent_models_devstral.log#L31564) |
| 08/30 03:22:04 | `ablation/devstral24b/d03__b49k__su-full` | [followup_agent_models_devstral.log:31598](../logs/followup_agent_models_devstral.log#L31598) |
| 08/30 03:22:04 | `ablation/devstral24b/d03__b49k__su-partial` | [followup_agent_models_devstral.log:31632](../logs/followup_agent_models_devstral.log#L31632) |
| 08/30 03:22:04 | `ablation/devstral24b/d03__b49k__ss` | [followup_agent_models_devstral.log:31666](../logs/followup_agent_models_devstral.log#L31666) |
| 08/30 03:22:05 | `ablation/devstral24b/d03__b49k__ss-partial` | [followup_agent_models_devstral.log:31700](../logs/followup_agent_models_devstral.log#L31700) |
| 08/30 03:38:55 | `ablation/devstral24b/d07__b38k__tr` | [followup_agent_models_devstral.log:32004](../logs/followup_agent_models_devstral.log#L32004) |
| 08/30 03:39:00 | `ablation/devstral24b/d07__b38k__tr` | [followup_agent_models_devstral.log:32145](../logs/followup_agent_models_devstral.log#L32145) |
| 08/30 03:39:10 | `ablation/devstral24b/d07__b38k__tr` | [followup_agent_models_devstral.log:32321](../logs/followup_agent_models_devstral.log#L32321) |
| 08/30 05:03:08 | `ablation/devstral24b/d07__b38k__su-full` | [followup_agent_models_devstral.log:33123](../logs/followup_agent_models_devstral.log#L33123) |
| 08/30 05:03:42 | `ablation/devstral24b/d07__b38k__su-full` | [followup_agent_models_devstral.log:33253](../logs/followup_agent_models_devstral.log#L33253) |
| 08/30 05:03:52 | `ablation/devstral24b/d07__b38k__su-full` | [followup_agent_models_devstral.log:33411](../logs/followup_agent_models_devstral.log#L33411) |
| 08/30 05:47:58 | `ablation/devstral24b/d07__b38k__su-partial` | [followup_agent_models_devstral.log:34012](../logs/followup_agent_models_devstral.log#L34012) |
| 08/30 05:56:11 | `ablation/devstral24b/d07__b38k__su-partial` | [followup_agent_models_devstral.log:34098](../logs/followup_agent_models_devstral.log#L34098) |
| 08/30 06:20:31 | `ablation/devstral24b/d07__b38k__su-partial` | [followup_agent_models_devstral.log:34328](../logs/followup_agent_models_devstral.log#L34328) |
| 08/30 07:22:00 | `ablation/devstral24b/d07__b38k__ss` | [followup_agent_models_devstral.log:35032](../logs/followup_agent_models_devstral.log#L35032) |
| 08/30 07:23:41 | `ablation/devstral24b/d07__b38k__ss` | [followup_agent_models_devstral.log:35192](../logs/followup_agent_models_devstral.log#L35192) |
| 08/30 07:25:18 | `ablation/devstral24b/d07__b38k__ss` | [followup_agent_models_devstral.log:35356](../logs/followup_agent_models_devstral.log#L35356) |
| 08/30 08:16:59 | `ablation/devstral24b/d07__b38k__ss-partial` | [followup_agent_models_devstral.log:36064](../logs/followup_agent_models_devstral.log#L36064) |
| 08/30 08:23:53 | `ablation/devstral24b/d07__b38k__ss-partial` | [followup_agent_models_devstral.log:36157](../logs/followup_agent_models_devstral.log#L36157) |
| 08/30 08:34:09 | `ablation/devstral24b/d07__b38k__ss-partial` | [followup_agent_models_devstral.log:36298](../logs/followup_agent_models_devstral.log#L36298) |
| 08/30 09:34:06 | `ablation/devstral24b/d07__b43k__tr` | [followup_agent_models_devstral.log:36985](../logs/followup_agent_models_devstral.log#L36985) |
| 08/30 09:36:33 | `ablation/devstral24b/d07__b43k__tr` | [followup_agent_models_devstral.log:37117](../logs/followup_agent_models_devstral.log#L37117) |
| 08/30 09:45:09 | `ablation/devstral24b/d07__b43k__tr` | [followup_agent_models_devstral.log:37291](../logs/followup_agent_models_devstral.log#L37291) |
| 08/30 11:00:45 | `ablation/devstral24b/d07__b43k__su-full` | [followup_agent_models_devstral.log:38070](../logs/followup_agent_models_devstral.log#L38070) |
| 08/30 11:00:59 | `ablation/devstral24b/d07__b43k__su-full` | [followup_agent_models_devstral.log:38220](../logs/followup_agent_models_devstral.log#L38220) |
| 08/30 11:01:26 | `ablation/devstral24b/d07__b43k__su-full` | [followup_agent_models_devstral.log:38378](../logs/followup_agent_models_devstral.log#L38378) |
| 08/30 11:56:41 | `ablation/devstral24b/d07__b43k__su-partial` | [followup_agent_models_devstral.log:39113](../logs/followup_agent_models_devstral.log#L39113) |
| 08/30 11:56:57 | `ablation/devstral24b/d07__b43k__su-partial` | [followup_agent_models_devstral.log:39189](../logs/followup_agent_models_devstral.log#L39189) |
| 08/30 12:04:14 | `ablation/devstral24b/d07__b43k__su-partial` | [followup_agent_models_devstral.log:39279](../logs/followup_agent_models_devstral.log#L39279) |
| 08/30 12:43:41 | `ablation/devstral24b/d07__b43k__ss` | [followup_agent_models_devstral.log:39962](../logs/followup_agent_models_devstral.log#L39962) |
| 08/30 12:45:24 | `ablation/devstral24b/d07__b43k__ss` | [followup_agent_models_devstral.log:40024](../logs/followup_agent_models_devstral.log#L40024) |
| 08/30 12:51:03 | `ablation/devstral24b/d07__b43k__ss` | [followup_agent_models_devstral.log:40253](../logs/followup_agent_models_devstral.log#L40253) |
| 08/30 13:12:26 | `ablation/devstral24b/d07__b43k__ss-partial` | [followup_agent_models_devstral.log:40618](../logs/followup_agent_models_devstral.log#L40618) |
| 08/30 13:19:29 | `ablation/devstral24b/d07__b43k__ss-partial` | [followup_agent_models_devstral.log:40684](../logs/followup_agent_models_devstral.log#L40684) |
| 08/30 13:45:59 | `ablation/devstral24b/d07__b43k__ss-partial` | [followup_agent_models_devstral.log:40988](../logs/followup_agent_models_devstral.log#L40988) |
| 08/30 14:36:02 | `ablation/devstral24b/d07__b49k__tr` | [followup_agent_models_devstral.log:41541](../logs/followup_agent_models_devstral.log#L41541) |
| 08/30 14:36:47 | `ablation/devstral24b/d07__b49k__tr` | [followup_agent_models_devstral.log:41707](../logs/followup_agent_models_devstral.log#L41707) |
| 08/30 14:40:26 | `ablation/devstral24b/d07__b49k__tr` | [followup_agent_models_devstral.log:41881](../logs/followup_agent_models_devstral.log#L41881) |
| 08/30 15:49:39 | `ablation/devstral24b/d07__b49k__su-full` | [followup_agent_models_devstral.log:42641](../logs/followup_agent_models_devstral.log#L42641) |
| 08/30 15:51:17 | `ablation/devstral24b/d07__b49k__su-full` | [followup_agent_models_devstral.log:42736](../logs/followup_agent_models_devstral.log#L42736) |
| 08/30 15:51:21 | `ablation/devstral24b/d07__b49k__su-full` | [followup_agent_models_devstral.log:42850](../logs/followup_agent_models_devstral.log#L42850) |
| 08/30 16:32:38 | `ablation/devstral24b/d07__b49k__su-partial` | [followup_agent_models_devstral.log:43466](../logs/followup_agent_models_devstral.log#L43466) |
| 08/30 16:34:02 | `ablation/devstral24b/d07__b49k__su-partial` | [followup_agent_models_devstral.log:43529](../logs/followup_agent_models_devstral.log#L43529) |
| 08/30 16:50:18 | `ablation/devstral24b/d07__b49k__su-partial` | [followup_agent_models_devstral.log:43833](../logs/followup_agent_models_devstral.log#L43833) |
| 08/30 17:09:01 | `ablation/devstral24b/d07__b49k__ss` | [followup_agent_models_devstral.log:44074](../logs/followup_agent_models_devstral.log#L44074) |
| 08/30 17:16:50 | `ablation/devstral24b/d07__b49k__ss` | [followup_agent_models_devstral.log:44152](../logs/followup_agent_models_devstral.log#L44152) |
| 08/30 18:23:32 | `ablation/devstral24b/d07__b49k__ss` | [followup_agent_models_devstral.log:44839](../logs/followup_agent_models_devstral.log#L44839) |
| 08/30 18:32:14 | `ablation/devstral24b/d07__b49k__ss-partial` | [followup_agent_models_devstral.log:44969](../logs/followup_agent_models_devstral.log#L44969) |
| 08/30 18:32:31 | `ablation/devstral24b/d07__b49k__ss-partial` | [followup_agent_models_devstral.log:45128](../logs/followup_agent_models_devstral.log#L45128) |
| 08/30 18:32:36 | `ablation/devstral24b/d07__b49k__ss-partial` | [followup_agent_models_devstral.log:45285](../logs/followup_agent_models_devstral.log#L45285) |
| 08/30 19:24:39 | `ablation/devstral24b/d05__b38k__tr` | [followup_agent_models_devstral.log:45928](../logs/followup_agent_models_devstral.log#L45928) |
| 08/30 19:25:53 | `ablation/devstral24b/d05__b38k__tr` | [followup_agent_models_devstral.log:46019](../logs/followup_agent_models_devstral.log#L46019) |
| 08/30 20:29:04 | `ablation/devstral24b/d05__b38k__su-full` | [followup_agent_models_devstral.log:46647](../logs/followup_agent_models_devstral.log#L46647) |
| 08/30 20:29:20 | `ablation/devstral24b/d05__b38k__tr` | [followup_agent_models_devstral.log:46807](../logs/followup_agent_models_devstral.log#L46807) |
| 08/30 20:29:43 | `ablation/devstral24b/d05__b38k__su-full` | [followup_agent_models_devstral.log:46851](../logs/followup_agent_models_devstral.log#L46851) |
| 08/30 20:37:05 | `ablation/devstral24b/d05__b38k__su-full` | [followup_agent_models_devstral.log:47017](../logs/followup_agent_models_devstral.log#L47017) |
| 08/30 21:55:12 | `ablation/devstral24b/d05__b38k__su-partial` | [followup_agent_models_devstral.log:47812](../logs/followup_agent_models_devstral.log#L47812) |
| 08/30 21:55:36 | `ablation/devstral24b/d05__b38k__su-partial` | [followup_agent_models_devstral.log:47952](../logs/followup_agent_models_devstral.log#L47952) |
| 08/30 21:56:02 | `ablation/devstral24b/d05__b38k__su-partial` | [followup_agent_models_devstral.log:48106](../logs/followup_agent_models_devstral.log#L48106) |
| 08/30 22:45:24 | `ablation/devstral24b/d05__b38k__ss` | [followup_agent_models_devstral.log:48712](../logs/followup_agent_models_devstral.log#L48712) |
| 08/30 22:55:37 | `ablation/devstral24b/d05__b38k__ss` | [followup_agent_models_devstral.log:48908](../logs/followup_agent_models_devstral.log#L48908) |
| 08/30 22:57:50 | `ablation/devstral24b/d05__b38k__ss` | [followup_agent_models_devstral.log:49041](../logs/followup_agent_models_devstral.log#L49041) |
| 08/31 00:05:27 | `ablation/devstral24b/d05__b38k__ss-partial` | [followup_agent_models_devstral.log:49742](../logs/followup_agent_models_devstral.log#L49742) |
| 08/31 00:07:07 | `ablation/devstral24b/d05__b38k__ss-partial` | [followup_agent_models_devstral.log:49894](../logs/followup_agent_models_devstral.log#L49894) |
| 08/31 00:07:19 | `ablation/devstral24b/d05__b38k__ss-partial` | [followup_agent_models_devstral.log:50037](../logs/followup_agent_models_devstral.log#L50037) |
| 08/31 00:50:42 | `ablation/devstral24b/di__b38k__trc` | [followup_agent_models_devstral.log:50734](../logs/followup_agent_models_devstral.log#L50734) |
| 08/31 00:51:21 | `ablation/devstral24b/di__b38k__trc` | [followup_agent_models_devstral.log:50900](../logs/followup_agent_models_devstral.log#L50900) |
| 08/31 00:51:24 | `ablation/devstral24b/di__b38k__trc-su` | [followup_agent_models_devstral.log:50938](../logs/followup_agent_models_devstral.log#L50938) |
| 08/31 00:54:14 | `ablation/devstral24b/di__b38k__trc` | [followup_agent_models_devstral.log:51131](../logs/followup_agent_models_devstral.log#L51131) |
| 08/31 00:54:14 | `ablation/devstral24b/di__b38k__trc-su` | [followup_agent_models_devstral.log:51165](../logs/followup_agent_models_devstral.log#L51165) |
| 08/31 00:55:08 | `ablation/devstral24b/di__b38k__trc-su` | [followup_agent_models_devstral.log:51246](../logs/followup_agent_models_devstral.log#L51246) |
| 08/31 00:55:58 | `ablation/devstral24b/di__b38k__trc-ss` | [followup_agent_models_devstral.log:51324](../logs/followup_agent_models_devstral.log#L51324) |
| 08/31 00:58:28 | `ablation/devstral24b/di__b38k__trc-ss` | [followup_agent_models_devstral.log:51360](../logs/followup_agent_models_devstral.log#L51360) |
| 08/31 00:59:22 | `ablation/devstral24b/di__b38k__trc-ss` | [followup_agent_models_devstral.log:51396](../logs/followup_agent_models_devstral.log#L51396) |
| 08/31 00:59:54 | `ablation/devstral24b/di__b38k__otrc-tr` | [followup_agent_models_devstral.log:51610](../logs/followup_agent_models_devstral.log#L51610) |
| 08/31 01:00:01 | `ablation/devstral24b/di__b38k__otrc-su-partial` | [followup_agent_models_devstral.log:51824](../logs/followup_agent_models_devstral.log#L51824) |
| 08/31 01:00:07 | `ablation/devstral24b/di__b38k__otrc-ss-partial` | [followup_agent_models_devstral.log:52038](../logs/followup_agent_models_devstral.log#L52038) |
| 08/31 01:00:14 | `ablation/devstral24b/d05__b49k__tr` | [followup_agent_models_devstral.log:52252](../logs/followup_agent_models_devstral.log#L52252) |
| 08/31 01:01:02 | `ablation/devstral24b/d05__b49k__su-full` | [followup_agent_models_devstral.log:52592](../logs/followup_agent_models_devstral.log#L52592) |
| 08/31 01:01:40 | `ablation/devstral24b/d05__b49k__su-partial` | [followup_agent_models_devstral.log:52806](../logs/followup_agent_models_devstral.log#L52806) |
| 08/31 01:02:13 | `ablation/devstral24b/d05__b49k__ss` | [followup_agent_models_devstral.log:53020](../logs/followup_agent_models_devstral.log#L53020) |
| 08/31 01:02:45 | `ablation/devstral24b/d05__b49k__ss-partial` | [followup_agent_models_devstral.log:53234](../logs/followup_agent_models_devstral.log#L53234) |
| 08/31 01:03:24 | `ablation/devstral24b/di__b38k__otrc-tr` | [followup_agent_models_devstral.log:53448](../logs/followup_agent_models_devstral.log#L53448) |
| 08/31 01:03:24 | `ablation/devstral24b/di__b38k__otrc-su-partial` | [followup_agent_models_devstral.log:53482](../logs/followup_agent_models_devstral.log#L53482) |
| 08/31 01:03:24 | `ablation/devstral24b/di__b38k__otrc-ss-partial` | [followup_agent_models_devstral.log:53516](../logs/followup_agent_models_devstral.log#L53516) |
| 08/31 01:03:24 | `ablation/devstral24b/d05__b49k__tr` | [followup_agent_models_devstral.log:53550](../logs/followup_agent_models_devstral.log#L53550) |
| 08/31 01:03:24 | `ablation/devstral24b/d05__b49k__su-full` | [followup_agent_models_devstral.log:53584](../logs/followup_agent_models_devstral.log#L53584) |
| 08/31 01:03:24 | `ablation/devstral24b/d05__b49k__su-partial` | [followup_agent_models_devstral.log:53741](../logs/followup_agent_models_devstral.log#L53741) |
| 08/31 01:03:25 | `ablation/devstral24b/d05__b49k__ss` | [followup_agent_models_devstral.log:53775](../logs/followup_agent_models_devstral.log#L53775) |
| 08/31 01:03:25 | `ablation/devstral24b/d05__b49k__ss-partial` | [followup_agent_models_devstral.log:53809](../logs/followup_agent_models_devstral.log#L53809) |
| 08/31 01:03:47 | `ablation/devstral24b/di__b49k__trc` | [followup_agent_models_devstral.log:53900](../logs/followup_agent_models_devstral.log#L53900) |
| 08/31 01:04:19 | `ablation/devstral24b/di__b49k__trc-su` | [followup_agent_models_devstral.log:54114](../logs/followup_agent_models_devstral.log#L54114) |
| 08/31 01:05:09 | `ablation/devstral24b/di__b38k__otrc-tr` | [followup_agent_models_devstral.log:54338](../logs/followup_agent_models_devstral.log#L54338) |
| 08/31 01:05:09 | `ablation/devstral24b/di__b38k__otrc-su-partial` | [followup_agent_models_devstral.log:54372](../logs/followup_agent_models_devstral.log#L54372) |
| 08/31 01:05:09 | `ablation/devstral24b/di__b38k__otrc-ss-partial` | [followup_agent_models_devstral.log:54406](../logs/followup_agent_models_devstral.log#L54406) |
| 08/31 01:05:09 | `ablation/devstral24b/d05__b49k__tr` | [followup_agent_models_devstral.log:54440](../logs/followup_agent_models_devstral.log#L54440) |
| 08/31 01:05:10 | `ablation/devstral24b/d05__b49k__su-full` | [followup_agent_models_devstral.log:54474](../logs/followup_agent_models_devstral.log#L54474) |
| 08/31 01:05:10 | `ablation/devstral24b/d05__b49k__su-partial` | [followup_agent_models_devstral.log:54508](../logs/followup_agent_models_devstral.log#L54508) |
| 08/31 01:05:10 | `ablation/devstral24b/d05__b49k__ss` | [followup_agent_models_devstral.log:54542](../logs/followup_agent_models_devstral.log#L54542) |
| 08/31 01:05:10 | `ablation/devstral24b/d05__b49k__ss-partial` | [followup_agent_models_devstral.log:54576](../logs/followup_agent_models_devstral.log#L54576) |
| 08/31 01:05:12 | `ablation/devstral24b/di__b49k__trc` | [followup_agent_models_devstral.log:54612](../logs/followup_agent_models_devstral.log#L54612) |
| 08/31 01:05:12 | `ablation/devstral24b/di__b49k__trc-su` | [followup_agent_models_devstral.log:54646](../logs/followup_agent_models_devstral.log#L54646) |
| 08/31 01:05:14 | `ablation/devstral24b/di__b49k__trc-ss` | [followup_agent_models_devstral.log:54682](../logs/followup_agent_models_devstral.log#L54682) |
| 08/31 01:05:45 | `ablation/devstral24b/di__b49k__otrc-tr` | [followup_agent_models_devstral.log:54896](../logs/followup_agent_models_devstral.log#L54896) |
| 08/31 01:05:56 | `ablation/devstral24b/di__b49k__otrc-su-partial` | [followup_agent_models_devstral.log:55110](../logs/followup_agent_models_devstral.log#L55110) |
| 08/31 01:06:07 | `ablation/devstral24b/di__b49k__otrc-ss-partial` | [followup_agent_models_devstral.log:55324](../logs/followup_agent_models_devstral.log#L55324) |
| 08/31 01:07:45 | `ablation/devstral24b/di__b49k__trc` | [followup_agent_models_devstral.log:55641](../logs/followup_agent_models_devstral.log#L55641) |
| 08/31 01:07:46 | `ablation/devstral24b/di__b49k__trc-su` | [followup_agent_models_devstral.log:55675](../logs/followup_agent_models_devstral.log#L55675) |
| 08/31 01:07:46 | `ablation/devstral24b/di__b49k__trc-ss` | [followup_agent_models_devstral.log:55709](../logs/followup_agent_models_devstral.log#L55709) |
| 08/31 01:07:46 | `ablation/devstral24b/di__b49k__otrc-tr` | [followup_agent_models_devstral.log:55743](../logs/followup_agent_models_devstral.log#L55743) |
| 08/31 01:07:46 | `ablation/devstral24b/di__b49k__otrc-su-partial` | [followup_agent_models_devstral.log:55777](../logs/followup_agent_models_devstral.log#L55777) |
| 08/31 01:07:46 | `ablation/devstral24b/di__b49k__otrc-ss-partial` | [followup_agent_models_devstral.log:55811](../logs/followup_agent_models_devstral.log#L55811) |
| 08/31 01:08:35 | `ablation/devstral24b/di__b49k__trc-ss` | [followup_agent_models_devstral.log:55923](../logs/followup_agent_models_devstral.log#L55923) |
| 08/31 01:08:35 | `ablation/devstral24b/di__b49k__otrc-tr` | [followup_agent_models_devstral.log:55957](../logs/followup_agent_models_devstral.log#L55957) |
| 08/31 01:08:36 | `ablation/devstral24b/di__b49k__otrc-su-partial` | [followup_agent_models_devstral.log:55991](../logs/followup_agent_models_devstral.log#L55991) |
| 08/31 01:08:36 | `ablation/devstral24b/di__b49k__otrc-ss-partial` | [followup_agent_models_devstral.log:56025](../logs/followup_agent_models_devstral.log#L56025) |

### Devstral: adopted grid and repairs, August 31–September 6

The first 21K attempt includes Podman-related failures; the sustained 02:34 resume follows repair. September 3 and September 4 repeats retain their original log times so that skips and later retries can be traced separately.

| Start (CDT) | Cell | Source |
|---|---|---|
| 08/31 02:00:42 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:56061](../logs/followup_agent_models_devstral.log#L56061) |
| 08/31 02:30:26 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:56601](../logs/followup_agent_models_devstral.log#L56601) |
| 08/31 02:34:20 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:56603](../logs/followup_agent_models_devstral.log#L56603) |
| 08/31 06:35:50 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:57682](../logs/followup_agent_models_devstral.log#L57682) |
| 08/31 11:22:55 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:58677](../logs/followup_agent_models_devstral.log#L58677) |
| 08/31 18:49:26 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:59680](../logs/followup_agent_models_devstral.log#L59680) |
| 09/01 00:38:02 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:60682](../logs/followup_agent_models_devstral.log#L60682) |
| 09/01 08:15:11 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:61729](../logs/followup_agent_models_devstral.log#L61729) |
| 09/01 13:06:31 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:62873](../logs/followup_agent_models_devstral.log#L62873) |
| 09/01 17:52:02 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:63985](../logs/followup_agent_models_devstral.log#L63985) |
| 09/01 22:07:52 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:65111](../logs/followup_agent_models_devstral.log#L65111) |
| 09/02 02:47:33 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:66119](../logs/followup_agent_models_devstral.log#L66119) |
| 09/02 08:21:48 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:67131](../logs/followup_agent_models_devstral.log#L67131) |
| 09/02 13:58:07 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:68165](../logs/followup_agent_models_devstral.log#L68165) |
| 09/02 13:58:34 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:68211](../logs/followup_agent_models_devstral.log#L68211) |
| 09/02 13:58:34 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:68246](../logs/followup_agent_models_devstral.log#L68246) |
| 09/02 15:20:16 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:68610](../logs/followup_agent_models_devstral.log#L68610) |
| 09/02 16:50:33 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:68933](../logs/followup_agent_models_devstral.log#L68933) |
| 09/02 19:14:19 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:69274](../logs/followup_agent_models_devstral.log#L69274) |
| 09/02 20:59:53 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:69590](../logs/followup_agent_models_devstral.log#L69590) |
| 09/02 23:17:18 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:69926](../logs/followup_agent_models_devstral.log#L69926) |
| 09/03 00:30:00 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:70302](../logs/followup_agent_models_devstral.log#L70302) |
| 09/03 02:04:17 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:70615](../logs/followup_agent_models_devstral.log#L70615) |
| 09/03 04:21:15 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:70954](../logs/followup_agent_models_devstral.log#L70954) |
| 09/03 06:06:42 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:71278](../logs/followup_agent_models_devstral.log#L71278) |
| 09/03 08:21:28 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:71623](../logs/followup_agent_models_devstral.log#L71623) |
| 09/03 09:33:53 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:71994](../logs/followup_agent_models_devstral.log#L71994) |
| 09/03 10:54:16 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:72328](../logs/followup_agent_models_devstral.log#L72328) |
| 09/03 20:07:38 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:72580](../logs/followup_agent_models_devstral.log#L72580) |
| 09/03 20:07:38 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:72614](../logs/followup_agent_models_devstral.log#L72614) |
| 09/03 20:07:38 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:72648](../logs/followup_agent_models_devstral.log#L72648) |
| 09/03 20:07:38 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:72682](../logs/followup_agent_models_devstral.log#L72682) |
| 09/03 20:07:48 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:72720](../logs/followup_agent_models_devstral.log#L72720) |
| 09/03 20:07:57 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:72758](../logs/followup_agent_models_devstral.log#L72758) |
| 09/03 20:08:07 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:72796](../logs/followup_agent_models_devstral.log#L72796) |
| 09/03 20:08:17 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:72834](../logs/followup_agent_models_devstral.log#L72834) |
| 09/03 20:08:17 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:72868](../logs/followup_agent_models_devstral.log#L72868) |
| 09/03 20:08:17 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:72902](../logs/followup_agent_models_devstral.log#L72902) |
| 09/03 20:08:27 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:72940](../logs/followup_agent_models_devstral.log#L72940) |
| 09/03 20:08:37 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:72978](../logs/followup_agent_models_devstral.log#L72978) |
| 09/03 20:08:37 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:73012](../logs/followup_agent_models_devstral.log#L73012) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:73047](../logs/followup_agent_models_devstral.log#L73047) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:73081](../logs/followup_agent_models_devstral.log#L73081) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:73115](../logs/followup_agent_models_devstral.log#L73115) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:73149](../logs/followup_agent_models_devstral.log#L73149) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:73183](../logs/followup_agent_models_devstral.log#L73183) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:73217](../logs/followup_agent_models_devstral.log#L73217) |
| 09/03 20:08:37 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:73251](../logs/followup_agent_models_devstral.log#L73251) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:73285](../logs/followup_agent_models_devstral.log#L73285) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:73319](../logs/followup_agent_models_devstral.log#L73319) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:73353](../logs/followup_agent_models_devstral.log#L73353) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:73387](../logs/followup_agent_models_devstral.log#L73387) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:73421](../logs/followup_agent_models_devstral.log#L73421) |
| 09/03 20:08:38 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:73455](../logs/followup_agent_models_devstral.log#L73455) |
| 09/03 20:12:56 | `ablation/devstral24b/d03__b24k__ss` | [followup_agent_models_devstral.log:73511](../logs/followup_agent_models_devstral.log#L73511) |
| 09/03 21:56:12 | `ablation/devstral24b/d03__b24k__ss-partial` | [followup_agent_models_devstral.log:73847](../logs/followup_agent_models_devstral.log#L73847) |
| 09/04 00:07:38 | `ablation/devstral24b/d07__b17k__tr` | [followup_agent_models_devstral.log:74194](../logs/followup_agent_models_devstral.log#L74194) |
| 09/04 01:23:16 | `ablation/devstral24b/d07__b17k__su-full` | [followup_agent_models_devstral.log:74568](../logs/followup_agent_models_devstral.log#L74568) |
| 09/04 03:10:06 | `ablation/devstral24b/d07__b17k__su-partial` | [followup_agent_models_devstral.log:74870](../logs/followup_agent_models_devstral.log#L74870) |
| 09/04 05:32:32 | `ablation/devstral24b/d07__b17k__ss` | [followup_agent_models_devstral.log:75190](../logs/followup_agent_models_devstral.log#L75190) |
| 09/04 06:54:20 | `ablation/devstral24b/d07__b17k__ss-partial` | [followup_agent_models_devstral.log:75490](../logs/followup_agent_models_devstral.log#L75490) |
| 09/04 09:15:52 | `ablation/devstral24b/d07__b21k__tr` | [followup_agent_models_devstral.log:75823](../logs/followup_agent_models_devstral.log#L75823) |
| 09/04 10:30:20 | `ablation/devstral24b/d07__b21k__su-full` | [followup_agent_models_devstral.log:76205](../logs/followup_agent_models_devstral.log#L76205) |
| 09/04 11:55:16 | `ablation/devstral24b/d07__b21k__su-partial` | [followup_agent_models_devstral.log:76526](../logs/followup_agent_models_devstral.log#L76526) |
| 09/04 14:16:17 | `ablation/devstral24b/d07__b21k__ss` | [followup_agent_models_devstral.log:76856](../logs/followup_agent_models_devstral.log#L76856) |
| 09/04 15:37:41 | `ablation/devstral24b/d07__b21k__ss-partial` | [followup_agent_models_devstral.log:77169](../logs/followup_agent_models_devstral.log#L77169) |
| 09/04 17:45:10 | `ablation/devstral24b/d07__b24k__tr` | [followup_agent_models_devstral.log:77519](../logs/followup_agent_models_devstral.log#L77519) |
| 09/04 19:04:13 | `ablation/devstral24b/d07__b24k__su-full` | [followup_agent_models_devstral.log:77891](../logs/followup_agent_models_devstral.log#L77891) |
| 09/04 20:21:34 | `ablation/devstral24b/d07__b24k__su-partial` | [followup_agent_models_devstral.log:78217](../logs/followup_agent_models_devstral.log#L78217) |
| 09/04 22:34:21 | `ablation/devstral24b/d07__b24k__ss` | [followup_agent_models_devstral.log:78551](../logs/followup_agent_models_devstral.log#L78551) |
| 09/04 22:34:34 | `ablation/devstral24b/d07__b24k__ss-partial` | [followup_agent_models_devstral.log:78764](../logs/followup_agent_models_devstral.log#L78764) |
| 09/04 22:34:45 | `ablation/devstral24b/d05__b17k__tr` | [followup_agent_models_devstral.log:78978](../logs/followup_agent_models_devstral.log#L78978) |
| 09/04 22:34:56 | `ablation/devstral24b/d05__b17k__su-full` | [followup_agent_models_devstral.log:79192](../logs/followup_agent_models_devstral.log#L79192) |
| 09/04 22:35:08 | `ablation/devstral24b/d05__b17k__su-partial` | [followup_agent_models_devstral.log:79406](../logs/followup_agent_models_devstral.log#L79406) |
| 09/04 22:35:19 | `ablation/devstral24b/d05__b17k__ss` | [followup_agent_models_devstral.log:79620](../logs/followup_agent_models_devstral.log#L79620) |
| 09/04 22:35:30 | `ablation/devstral24b/d05__b17k__ss-partial` | [followup_agent_models_devstral.log:79834](../logs/followup_agent_models_devstral.log#L79834) |
| 09/04 22:35:41 | `ablation/devstral24b/di__b17k__trc` | [followup_agent_models_devstral.log:80048](../logs/followup_agent_models_devstral.log#L80048) |
| 09/04 22:35:52 | `ablation/devstral24b/di__b17k__trc-su` | [followup_agent_models_devstral.log:80262](../logs/followup_agent_models_devstral.log#L80262) |
| 09/04 22:36:02 | `ablation/devstral24b/di__b17k__trc-ss` | [followup_agent_models_devstral.log:80475](../logs/followup_agent_models_devstral.log#L80475) |
| 09/04 22:36:12 | `ablation/devstral24b/di__b17k__otrc-tr` | [followup_agent_models_devstral.log:80689](../logs/followup_agent_models_devstral.log#L80689) |
| 09/04 22:36:23 | `ablation/devstral24b/di__b17k__otrc-su-partial` | [followup_agent_models_devstral.log:80903](../logs/followup_agent_models_devstral.log#L80903) |
| 09/04 22:36:33 | `ablation/devstral24b/di__b17k__otrc-ss-partial` | [followup_agent_models_devstral.log:81117](../logs/followup_agent_models_devstral.log#L81117) |
| 09/04 22:36:44 | `ablation/devstral24b/d05__b24k__tr` | [followup_agent_models_devstral.log:81330](../logs/followup_agent_models_devstral.log#L81330) |
| 09/04 22:36:54 | `ablation/devstral24b/d05__b24k__su-full` | [followup_agent_models_devstral.log:81544](../logs/followup_agent_models_devstral.log#L81544) |
| 09/04 22:37:05 | `ablation/devstral24b/d05__b24k__su-partial` | [followup_agent_models_devstral.log:81758](../logs/followup_agent_models_devstral.log#L81758) |
| 09/04 22:37:15 | `ablation/devstral24b/d05__b24k__ss` | [followup_agent_models_devstral.log:81972](../logs/followup_agent_models_devstral.log#L81972) |
| 09/04 22:37:26 | `ablation/devstral24b/d05__b24k__ss-partial` | [followup_agent_models_devstral.log:82186](../logs/followup_agent_models_devstral.log#L82186) |
| 09/04 22:37:36 | `ablation/devstral24b/di__b24k__trc` | [followup_agent_models_devstral.log:82400](../logs/followup_agent_models_devstral.log#L82400) |
| 09/04 22:37:47 | `ablation/devstral24b/di__b24k__trc-su` | [followup_agent_models_devstral.log:82614](../logs/followup_agent_models_devstral.log#L82614) |
| 09/04 22:37:57 | `ablation/devstral24b/di__b24k__trc-ss` | [followup_agent_models_devstral.log:82828](../logs/followup_agent_models_devstral.log#L82828) |
| 09/04 22:38:08 | `ablation/devstral24b/di__b24k__otrc-tr` | [followup_agent_models_devstral.log:83040](../logs/followup_agent_models_devstral.log#L83040) |
| 09/04 22:38:21 | `ablation/devstral24b/di__b24k__otrc-su-partial` | [followup_agent_models_devstral.log:83254](../logs/followup_agent_models_devstral.log#L83254) |
| 09/04 22:38:33 | `ablation/devstral24b/di__b24k__otrc-ss-partial` | [followup_agent_models_devstral.log:83468](../logs/followup_agent_models_devstral.log#L83468) |
| 09/04 23:21:50 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:83685](../logs/followup_agent_models_devstral.log#L83685) |
| 09/04 23:21:50 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:83719](../logs/followup_agent_models_devstral.log#L83719) |
| 09/04 23:21:50 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:83753](../logs/followup_agent_models_devstral.log#L83753) |
| 09/04 23:21:50 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:83787](../logs/followup_agent_models_devstral.log#L83787) |
| 09/04 23:21:50 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:83821](../logs/followup_agent_models_devstral.log#L83821) |
| 09/04 23:21:50 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:83855](../logs/followup_agent_models_devstral.log#L83855) |
| 09/04 23:21:51 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:83889](../logs/followup_agent_models_devstral.log#L83889) |
| 09/04 23:21:51 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:83923](../logs/followup_agent_models_devstral.log#L83923) |
| 09/04 23:21:51 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:83957](../logs/followup_agent_models_devstral.log#L83957) |
| 09/04 23:21:51 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:83991](../logs/followup_agent_models_devstral.log#L83991) |
| 09/04 23:21:51 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:84025](../logs/followup_agent_models_devstral.log#L84025) |
| 09/04 23:21:51 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:84059](../logs/followup_agent_models_devstral.log#L84059) |
| 09/04 23:21:51 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:84093](../logs/followup_agent_models_devstral.log#L84093) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:84128](../logs/followup_agent_models_devstral.log#L84128) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:84162](../logs/followup_agent_models_devstral.log#L84162) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:84196](../logs/followup_agent_models_devstral.log#L84196) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:84230](../logs/followup_agent_models_devstral.log#L84230) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:84264](../logs/followup_agent_models_devstral.log#L84264) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:84298](../logs/followup_agent_models_devstral.log#L84298) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:84332](../logs/followup_agent_models_devstral.log#L84332) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:84366](../logs/followup_agent_models_devstral.log#L84366) |
| 09/04 23:21:52 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:84400](../logs/followup_agent_models_devstral.log#L84400) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:84434](../logs/followup_agent_models_devstral.log#L84434) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:84468](../logs/followup_agent_models_devstral.log#L84468) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:84502](../logs/followup_agent_models_devstral.log#L84502) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:84536](../logs/followup_agent_models_devstral.log#L84536) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b24k__ss` | [followup_agent_models_devstral.log:84570](../logs/followup_agent_models_devstral.log#L84570) |
| 09/04 23:21:53 | `ablation/devstral24b/d03__b24k__ss-partial` | [followup_agent_models_devstral.log:84604](../logs/followup_agent_models_devstral.log#L84604) |
| 09/04 23:21:53 | `ablation/devstral24b/d07__b17k__tr` | [followup_agent_models_devstral.log:84638](../logs/followup_agent_models_devstral.log#L84638) |
| 09/04 23:21:53 | `ablation/devstral24b/d07__b17k__su-full` | [followup_agent_models_devstral.log:84672](../logs/followup_agent_models_devstral.log#L84672) |
| 09/04 23:21:59 | `ablation/devstral24b/d07__b17k__su-partial` | [followup_agent_models_devstral.log:84708](../logs/followup_agent_models_devstral.log#L84708) |
| 09/04 23:21:59 | `ablation/devstral24b/d07__b17k__ss` | [followup_agent_models_devstral.log:84742](../logs/followup_agent_models_devstral.log#L84742) |
| 09/04 23:21:59 | `ablation/devstral24b/d07__b17k__ss-partial` | [followup_agent_models_devstral.log:84776](../logs/followup_agent_models_devstral.log#L84776) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b21k__tr` | [followup_agent_models_devstral.log:84810](../logs/followup_agent_models_devstral.log#L84810) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b21k__su-full` | [followup_agent_models_devstral.log:84844](../logs/followup_agent_models_devstral.log#L84844) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b21k__su-partial` | [followup_agent_models_devstral.log:84878](../logs/followup_agent_models_devstral.log#L84878) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b21k__ss` | [followup_agent_models_devstral.log:84912](../logs/followup_agent_models_devstral.log#L84912) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b21k__ss-partial` | [followup_agent_models_devstral.log:84946](../logs/followup_agent_models_devstral.log#L84946) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b24k__tr` | [followup_agent_models_devstral.log:84980](../logs/followup_agent_models_devstral.log#L84980) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b24k__su-full` | [followup_agent_models_devstral.log:85014](../logs/followup_agent_models_devstral.log#L85014) |
| 09/04 23:22:00 | `ablation/devstral24b/d07__b24k__su-partial` | [followup_agent_models_devstral.log:85048](../logs/followup_agent_models_devstral.log#L85048) |
| 09/04 23:33:44 | `ablation/devstral24b/d07__b24k__ss` | [followup_agent_models_devstral.log:85128](../logs/followup_agent_models_devstral.log#L85128) |
| 09/04 23:33:44 | `ablation/devstral24b/d07__b24k__ss-partial` | [followup_agent_models_devstral.log:85162](../logs/followup_agent_models_devstral.log#L85162) |
| 09/04 23:33:44 | `ablation/devstral24b/d05__b17k__tr` | [followup_agent_models_devstral.log:85196](../logs/followup_agent_models_devstral.log#L85196) |
| 09/04 23:33:44 | `ablation/devstral24b/d05__b17k__su-full` | [followup_agent_models_devstral.log:85230](../logs/followup_agent_models_devstral.log#L85230) |
| 09/04 23:33:44 | `ablation/devstral24b/d05__b17k__su-partial` | [followup_agent_models_devstral.log:85264](../logs/followup_agent_models_devstral.log#L85264) |
| 09/04 23:33:44 | `ablation/devstral24b/d05__b17k__ss` | [followup_agent_models_devstral.log:85298](../logs/followup_agent_models_devstral.log#L85298) |
| 09/04 23:33:44 | `ablation/devstral24b/d05__b17k__ss-partial` | [followup_agent_models_devstral.log:85332](../logs/followup_agent_models_devstral.log#L85332) |
| 09/04 23:33:44 | `ablation/devstral24b/di__b17k__trc` | [followup_agent_models_devstral.log:85366](../logs/followup_agent_models_devstral.log#L85366) |
| 09/04 23:33:45 | `ablation/devstral24b/di__b17k__trc-su` | [followup_agent_models_devstral.log:85400](../logs/followup_agent_models_devstral.log#L85400) |
| 09/04 23:33:45 | `ablation/devstral24b/di__b17k__trc-ss` | [followup_agent_models_devstral.log:85434](../logs/followup_agent_models_devstral.log#L85434) |
| 09/04 23:33:45 | `ablation/devstral24b/di__b17k__otrc-tr` | [followup_agent_models_devstral.log:85468](../logs/followup_agent_models_devstral.log#L85468) |
| 09/04 23:33:45 | `ablation/devstral24b/di__b17k__otrc-su-partial` | [followup_agent_models_devstral.log:85502](../logs/followup_agent_models_devstral.log#L85502) |
| 09/04 23:33:45 | `ablation/devstral24b/di__b17k__otrc-ss-partial` | [followup_agent_models_devstral.log:85536](../logs/followup_agent_models_devstral.log#L85536) |
| 09/04 23:33:45 | `ablation/devstral24b/d05__b24k__tr` | [followup_agent_models_devstral.log:85570](../logs/followup_agent_models_devstral.log#L85570) |
| 09/04 23:33:45 | `ablation/devstral24b/d05__b24k__su-full` | [followup_agent_models_devstral.log:85604](../logs/followup_agent_models_devstral.log#L85604) |
| 09/04 23:33:45 | `ablation/devstral24b/d05__b24k__su-partial` | [followup_agent_models_devstral.log:85638](../logs/followup_agent_models_devstral.log#L85638) |
| 09/04 23:33:45 | `ablation/devstral24b/d05__b24k__ss` | [followup_agent_models_devstral.log:85672](../logs/followup_agent_models_devstral.log#L85672) |
| 09/04 23:33:45 | `ablation/devstral24b/d05__b24k__ss-partial` | [followup_agent_models_devstral.log:85706](../logs/followup_agent_models_devstral.log#L85706) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__trc` | [followup_agent_models_devstral.log:85740](../logs/followup_agent_models_devstral.log#L85740) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__trc-su` | [followup_agent_models_devstral.log:85774](../logs/followup_agent_models_devstral.log#L85774) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__trc-ss` | [followup_agent_models_devstral.log:85808](../logs/followup_agent_models_devstral.log#L85808) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__otrc-tr` | [followup_agent_models_devstral.log:85842](../logs/followup_agent_models_devstral.log#L85842) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__otrc-su-partial` | [followup_agent_models_devstral.log:85876](../logs/followup_agent_models_devstral.log#L85876) |
| 09/04 23:33:46 | `ablation/devstral24b/di__b24k__otrc-ss-partial` | [followup_agent_models_devstral.log:85910](../logs/followup_agent_models_devstral.log#L85910) |
| 09/04 23:55:21 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:85947](../logs/followup_agent_models_devstral.log#L85947) |
| 09/04 23:55:21 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:85981](../logs/followup_agent_models_devstral.log#L85981) |
| 09/04 23:55:21 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:86015](../logs/followup_agent_models_devstral.log#L86015) |
| 09/04 23:55:21 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:86049](../logs/followup_agent_models_devstral.log#L86049) |
| 09/04 23:55:21 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:86083](../logs/followup_agent_models_devstral.log#L86083) |
| 09/04 23:55:21 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:86117](../logs/followup_agent_models_devstral.log#L86117) |
| 09/04 23:55:21 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:86151](../logs/followup_agent_models_devstral.log#L86151) |
| 09/04 23:55:22 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:86185](../logs/followup_agent_models_devstral.log#L86185) |
| 09/04 23:55:22 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:86219](../logs/followup_agent_models_devstral.log#L86219) |
| 09/04 23:55:22 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:86253](../logs/followup_agent_models_devstral.log#L86253) |
| 09/04 23:55:22 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:86287](../logs/followup_agent_models_devstral.log#L86287) |
| 09/04 23:55:22 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:86321](../logs/followup_agent_models_devstral.log#L86321) |
| 09/04 23:55:22 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:86355](../logs/followup_agent_models_devstral.log#L86355) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:86390](../logs/followup_agent_models_devstral.log#L86390) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:86424](../logs/followup_agent_models_devstral.log#L86424) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:86458](../logs/followup_agent_models_devstral.log#L86458) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:86492](../logs/followup_agent_models_devstral.log#L86492) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:86526](../logs/followup_agent_models_devstral.log#L86526) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:86560](../logs/followup_agent_models_devstral.log#L86560) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:86594](../logs/followup_agent_models_devstral.log#L86594) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:86628](../logs/followup_agent_models_devstral.log#L86628) |
| 09/04 23:55:23 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:86662](../logs/followup_agent_models_devstral.log#L86662) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:86696](../logs/followup_agent_models_devstral.log#L86696) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:86730](../logs/followup_agent_models_devstral.log#L86730) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:86764](../logs/followup_agent_models_devstral.log#L86764) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:86798](../logs/followup_agent_models_devstral.log#L86798) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b24k__ss` | [followup_agent_models_devstral.log:86832](../logs/followup_agent_models_devstral.log#L86832) |
| 09/04 23:55:24 | `ablation/devstral24b/d03__b24k__ss-partial` | [followup_agent_models_devstral.log:86866](../logs/followup_agent_models_devstral.log#L86866) |
| 09/04 23:55:24 | `ablation/devstral24b/d07__b17k__tr` | [followup_agent_models_devstral.log:86900](../logs/followup_agent_models_devstral.log#L86900) |
| 09/04 23:55:24 | `ablation/devstral24b/d07__b17k__su-full` | [followup_agent_models_devstral.log:86934](../logs/followup_agent_models_devstral.log#L86934) |
| 09/04 23:55:24 | `ablation/devstral24b/d07__b17k__su-partial` | [followup_agent_models_devstral.log:86968](../logs/followup_agent_models_devstral.log#L86968) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b17k__ss` | [followup_agent_models_devstral.log:87002](../logs/followup_agent_models_devstral.log#L87002) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b17k__ss-partial` | [followup_agent_models_devstral.log:87036](../logs/followup_agent_models_devstral.log#L87036) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b21k__tr` | [followup_agent_models_devstral.log:87070](../logs/followup_agent_models_devstral.log#L87070) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b21k__su-full` | [followup_agent_models_devstral.log:87104](../logs/followup_agent_models_devstral.log#L87104) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b21k__su-partial` | [followup_agent_models_devstral.log:87138](../logs/followup_agent_models_devstral.log#L87138) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b21k__ss` | [followup_agent_models_devstral.log:87172](../logs/followup_agent_models_devstral.log#L87172) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b21k__ss-partial` | [followup_agent_models_devstral.log:87206](../logs/followup_agent_models_devstral.log#L87206) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b24k__tr` | [followup_agent_models_devstral.log:87240](../logs/followup_agent_models_devstral.log#L87240) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b24k__su-full` | [followup_agent_models_devstral.log:87274](../logs/followup_agent_models_devstral.log#L87274) |
| 09/04 23:55:25 | `ablation/devstral24b/d07__b24k__su-partial` | [followup_agent_models_devstral.log:87308](../logs/followup_agent_models_devstral.log#L87308) |
| 09/05 00:23:59 | `ablation/devstral24b/d07__b24k__ss` | [followup_agent_models_devstral.log:87398](../logs/followup_agent_models_devstral.log#L87398) |
| 09/05 02:02:18 | `ablation/devstral24b/d07__b24k__ss-partial` | [followup_agent_models_devstral.log:87726](../logs/followup_agent_models_devstral.log#L87726) |
| 09/05 04:07:38 | `ablation/devstral24b/d05__b17k__tr` | [followup_agent_models_devstral.log:88087](../logs/followup_agent_models_devstral.log#L88087) |
| 09/05 05:14:04 | `ablation/devstral24b/d05__b17k__su-full` | [followup_agent_models_devstral.log:88459](../logs/followup_agent_models_devstral.log#L88459) |
| 09/05 06:50:17 | `ablation/devstral24b/d05__b17k__su-partial` | [followup_agent_models_devstral.log:88771](../logs/followup_agent_models_devstral.log#L88771) |
| 09/05 09:14:28 | `ablation/devstral24b/d05__b17k__ss` | [followup_agent_models_devstral.log:89096](../logs/followup_agent_models_devstral.log#L89096) |
| 09/05 10:56:31 | `ablation/devstral24b/d05__b17k__ss-partial` | [followup_agent_models_devstral.log:89411](../logs/followup_agent_models_devstral.log#L89411) |
| 09/05 13:10:50 | `ablation/devstral24b/di__b17k__trc` | [followup_agent_models_devstral.log:89754](../logs/followup_agent_models_devstral.log#L89754) |
| 09/05 14:15:51 | `ablation/devstral24b/di__b17k__trc-su` | [followup_agent_models_devstral.log:90122](../logs/followup_agent_models_devstral.log#L90122) |
| 09/05 15:24:26 | `ablation/devstral24b/di__b17k__trc-ss` | [followup_agent_models_devstral.log:90478](../logs/followup_agent_models_devstral.log#L90478) |
| 09/05 16:31:08 | `ablation/devstral24b/di__b17k__otrc-tr` | [followup_agent_models_devstral.log:90838](../logs/followup_agent_models_devstral.log#L90838) |
| 09/05 17:46:34 | `ablation/devstral24b/di__b17k__otrc-su-partial` | [followup_agent_models_devstral.log:91175](../logs/followup_agent_models_devstral.log#L91175) |
| 09/05 19:29:43 | `ablation/devstral24b/di__b17k__otrc-ss-partial` | [followup_agent_models_devstral.log:91512](../logs/followup_agent_models_devstral.log#L91512) |
| 09/05 21:08:36 | `ablation/devstral24b/d05__b24k__tr` | [followup_agent_models_devstral.log:91832](../logs/followup_agent_models_devstral.log#L91832) |
| 09/05 22:15:13 | `ablation/devstral24b/d05__b24k__su-full` | [followup_agent_models_devstral.log:92208](../logs/followup_agent_models_devstral.log#L92208) |
| 09/05 23:40:20 | `ablation/devstral24b/d05__b24k__su-partial` | [followup_agent_models_devstral.log:92537](../logs/followup_agent_models_devstral.log#L92537) |
| 09/06 01:58:02 | `ablation/devstral24b/d05__b24k__ss` | [followup_agent_models_devstral.log:92875](../logs/followup_agent_models_devstral.log#L92875) |
| 09/06 03:20:58 | `ablation/devstral24b/d05__b24k__ss-partial` | [followup_agent_models_devstral.log:93199](../logs/followup_agent_models_devstral.log#L93199) |
| 09/06 05:35:49 | `ablation/devstral24b/di__b24k__trc` | [followup_agent_models_devstral.log:93548](../logs/followup_agent_models_devstral.log#L93548) |
| 09/06 06:42:49 | `ablation/devstral24b/di__b24k__trc-su` | [followup_agent_models_devstral.log:93923](../logs/followup_agent_models_devstral.log#L93923) |
| 09/06 07:52:43 | `ablation/devstral24b/di__b24k__trc-ss` | [followup_agent_models_devstral.log:94306](../logs/followup_agent_models_devstral.log#L94306) |
| 09/06 09:04:26 | `ablation/devstral24b/di__b24k__otrc-tr` | [followup_agent_models_devstral.log:94684](../logs/followup_agent_models_devstral.log#L94684) |
| 09/06 10:34:40 | `ablation/devstral24b/di__b24k__otrc-su-partial` | [followup_agent_models_devstral.log:95020](../logs/followup_agent_models_devstral.log#L95020) |
| 09/06 11:59:45 | `ablation/devstral24b/di__b24k__otrc-ss-partial` | [followup_agent_models_devstral.log:95347](../logs/followup_agent_models_devstral.log#L95347) |

### GLM main and Qwen summary-bug resume, September 6–7

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/06 17:51:42 | `main/glm47flash/d05__bP__tr` | [followup_agent_models_glm.log:2](../logs/followup_agent_models_glm.log#L2) |
| 09/06 23:59:49 | `main/glm47flash/d05__bP__su-full` | [followup_agent_models_glm.log:1076](../logs/followup_agent_models_glm.log#L1076) |
| 09/07 07:27:08 | `main/glm47flash/d05__bP__su-partial` | [followup_agent_models_glm.log:2134](../logs/followup_agent_models_glm.log#L2134) |
| 09/07 14:57:43 | `main/glm47flash/d05__bP__ss` | [followup_agent_models_glm.log:3141](../logs/followup_agent_models_glm.log#L3141) |
| 09/07 20:01:53 | `main/qwen35b/d05__b15k__tr` | [followup_agent_models_qwen.log:2](../logs/followup_agent_models_qwen.log#L2) |
| 09/07 20:01:54 | `main/qwen35b/d05__b15k__su-full` | [followup_agent_models_qwen.log:36](../logs/followup_agent_models_qwen.log#L36) |
| 09/07 20:08:05 | `main/qwen35b/d05__b15k__su-partial` | [followup_agent_models_qwen.log:72](../logs/followup_agent_models_qwen.log#L72) |
| 09/07 20:08:05 | `main/qwen35b/d05__b15k__ss` | [followup_agent_models_qwen.log:106](../logs/followup_agent_models_qwen.log#L106) |

## September 7 archive and inspection snapshot

The summary-call bug required a bash action in a summary response, producing FormatErrors. The local SWE audit selected only `summary_marker_error` for automatic archiving. The 2,359 selected runs break down as follows ([selection summary](../archives/summary-bug-audit-20260907_185802_CDT/archive_target_summary.csv)):

| Model | Main archived runs | Ablation archived runs | Total |
|---|---:|---:|---:|
| Qwen35b | 1,133 | 430 | 1,563 |
| Devstral24b | 256 | 511 | 767 |
| GLM47flash | 29 | 0 | 29 |
| Total | 1,418 | 941 | 2,359 |

The archive [status.json](../archives/swebench_summary_marker_error_20260907_192635_CDT/status.json) confirms completion with 2,358 removed index rows; one selected run had no index row. The local audit also lists 2,498 accounting cases and 262 response-content cases that were not automatically archived. The earlier Terminal-Bench archive counts in the shared [ARCHIVE_LOG.md](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md) concern another benchmark/workspace and are not SWE totals. Its local audit/dry-run paragraphs describe an earlier state; the final SWE archive status supersedes those statements.

At **20:41 CDT**, the inspected local process table contained no `run_agent_models_expansion` or `run_experiment_iclr.py` workers. The Qwen launcher PID `2558165` and GLM launcher PID `2478928` recorded on disk were absent. This establishes only that those launchers were not running at inspection, not why or exactly when they stopped. Qwen's latest cell-start marker is SS@15K at 20:08:05; GLM's log ends during SS, with no completion banner. The 20:01 Qwen launch in EXPERIMENT_LOG.md is a historical resume record, not proof of a still-active process.

## Limits on timestamps and completion claims

- Shell-history lines identify commands but do not date them. Where a matching launch banner is unavailable (OTRC retry, repair operations, file organization), the table explicitly labels the weaker time evidence. File and directory names are not treated as exact start/end times.
- The source logs, raw result indexes, backup manifests, and calibration artifacts are mostly gitignored/local. Relative links preserve the evidence location but may not resolve in a fresh clone. The old Devstral budget and Podman-repair backups are outside the repository under `/home/ak58925/agentCtx_backups/`; their names and inspected contents are recorded above without implying Git availability.
- `run_info.json` can be overwritten by a resume: the quarantined OTRC cell's run-info start reads September 2, while its 300 failed result rows are dated August 29. Canonical OTRC run-info later reads September 4, while replacement result rows are dated September 3. The chronology uses the evidence appropriate to each event.
- Log completion markers describe launcher traversal. Old-budget Devstral logs and the September 4 22:38 completion include zero-call failures. Later repair and summary-marker archiving mean historical COMPLETE statuses are not current valid-run coverage. No resolve-rate claim is inferred from those markers.
- The old `EXPERIMENT_LOG.md` GLM TODOs and earlier `Active_runs.md` statuses are not authoritative for the September snapshot; timestamped calibration/launch logs show later activity. The current experiment plan and launcher also supersede older Qwen cohort conventions for the September 7 rerun.
- The Qwen 1,761-run reuse is copying existing evidence, not generating independent samples. Filter by experiment section/cohort and consult destination `REUSE_MANIFEST.json` files when combining legacy main and ablation results.
- The September 7 Qwen resume used HEAD `da461d6` plus an uncommitted `scripts/run_experiment.py` change recording `step_completion_tokens`, as documented in [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#2026-09-07--summary-bug-rerun-and-qwen-swe-bench-resume). A Git commit alone does not describe that entire runtime tree.
- This is the local SWE history for the stated date range. Missing logs or unsaved shell history can hide other launches; no claim is made about other hosts. Monitoring, repeated server probes, dashboard builds, and routine aggregation are omitted.

---

# Continuation: 2026-09-08–2026-09-27

Second compilation pass, made on **2026-09-27** (inspection snapshot **14:42 CDT**) after the workspace was moved from `/home/ak58925/agentCtx` to `/home/ak58925/ICLR27/agentCtx` on 09/26. Shell-history lines and log banners from before the move still name the old path; relative links below resolve from the new location. Sources: `~/.bash_history` (2,000 lines, no timestamps, several shells interleaved), launcher/runner logs under `logs/`, archive `status.json` files, re-evaluation `jobs/` mtimes, Git reflog, and the backfilled [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#2026-09-08--2026-09-26--backfilled-entries-swe-bench-on-dobby-terminal-bench-cells-from-albus), which already records launch commands and HEADs for this period. This continuation adds the timeline view: what ran when, in which order, and where each start/stop is evidenced. Terminal-Bench cells collected on Albus are not reconstructed here (see the Albus TODO in EXPERIMENT_LOG.md).

`SLACK_WEBHOOK_URL`, `DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"` and `PATH="/home/rs67788/.local/bin:$PATH"` (rootless Podman) were exported before every launch and are omitted from the excerpts. `env` variable lists are abbreviated with `…` where EXPERIMENT_LOG.md has the full form.

## Launch chronology, September 8–27

| Start (CDT) | Experiment or operation | Launch command (excerpt) | Progress and outcome | Source log / record |
|---|---|---|---|---|
| 09/08 16:05–16:23 (commit times) | SWE / agent.log attribution and archive of the remaining summary-bug rerun targets | `venv/bin/python …/attribute_agentlog.py --audit-dir … --source-root ICLR_results --archive-root …/swebench_summary_marker_error_20260907_192635_CDT --output-dir …/agentlog-swebench --workers 32`; then `…/archive_swebench_rerun_targets.py --rerun-csv …/rerun_runs.csv --source-stats … --rerun-reason summary_failure_accounting … --archive-name swebench_summary_bug_remaining_20260908_162042_CDT --execute` | `rerun_runs.csv` grows 5,119 → 9,322 rows. Archive executed 16:20:42–16:20:59 with no launcher running: 6,963 runs, 98 cells, 6,952 index rows removed, 11 unindexed (qwen main 2,719, qwen ablation 933, devstral ablation 1,795, devstral main 840, glm main 676). Commits `25b7ca7` 16:21, `16dacec` 16:23. | [ARCHIVE_LOG.md](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md), [status.json](../archives/swebench_summary_bug_remaining_20260908_162042_CDT/status.json) |
| 09/08 between 16:10:25 and 16:20:42 | Qwen / stop the 09/07 launcher | `kill -TERM "$(cat logs/followup_agent_models_qwen_launcher.pid)"` (guarded by an `ps -o args=` match on `run_agent_models_expansion_notified.sh qwen`) | The 09/07 launch had finished main at 05:39:42 and was traversing ABL-30 (last cell start `d05__b10k__su-partial` 16:10:25). The archive at 16:20:42 records no launcher running. No stop banner is written by the launcher. | [followup_agent_models_qwen.log:4140](../logs/followup_agent_models_qwen.log#L4140), [ARCHIVE_LOG.md](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md) |
| 09/08 16:41:25 | Qwen / main-only resume, first attempt | `nohup env MAX_WORKERS=16 RUN_EVAL=1 SECTIONS=main PYTHON="$PWD/venv/bin/python3" QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 bash scripts/run_agent_models_expansion_notified.sh qwen` | Launcher log prints `notify_slack.py: SLACK_WEBHOOK_URL is not configured` at the launch line; TR and SU-full cells start, then the launcher was killed with the same guarded `kill -TERM`. The next launch line also carries the not-configured notice; a webhook was read in interactively between them. | [followup_agent_models_qwen_launcher.log:4141](../logs/followup_agent_models_qwen_launcher.log#L4141), [followup_agent_models_qwen.log:4141](../logs/followup_agent_models_qwen.log#L4141) |
| 09/08 16:48:02 | Qwen / main-only resume (summary-bug rerun, P100 @15K + ∞) | same command; launcher PID 3862052 | Executes the 917 missing keys of the 15K summary-family cells (SU-partial 21:19 → SS 09/09 02:26 → SS-partial 05:39 → TRC family 07:35 → OTRC family 10:56 → FC/OTRC∞ 14:52). `sections run: main (ablation skipped)` at **09/09 14:53:13**. HEAD `bbe9e5d`, `SECTIONS` override uncommitted until `4cbf6ed`. | [followup_agent_models_qwen.log:4177](../logs/followup_agent_models_qwen.log#L4177), [followup_agent_models_qwen.log:7699](../logs/followup_agent_models_qwen.log#L7699), [resume audit](issue/resume_audit_20260908/report.md) |
| 09/09 before 15:33 | Serving switch Qwen → Devstral | `kill -TERM 2552238` (Qwen vLLM), `bash scripts/start_vllm_devstral.sh` (:8002, TP=4, 65536) | Shell history only; no timestamp beyond the Devstral launch that follows. | shell history |
| 09/09 15:33:07 | Devstral / main rerun of the archived summary-bug runs (P100 @21K) | `nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh devstral` | SU-full 15:33 → SU-partial 18:18 → SS 21:35 → SS-partial 09/10 00:12 → TRC family 03:16 → OTRC family 04:50 → FC/OTRC∞ pass 06:14. `sections run: main (ablation skipped)` at **09/10 06:14:27**. 1,096 keys re-executed per the 09/10 audits. | [followup_agent_models_devstral.log:95681](../logs/followup_agent_models_devstral.log#L95681), [followup_agent_models_devstral.log:99917](../logs/followup_agent_models_devstral.log#L99917) |
| 09/10 12:58:46 | GLM / main resume attempt | `nohup env PYTHON="$PWD/venv/bin/python3" MAX_WORKERS=16 RUN_EVAL=1 SECTIONS=main bash scripts/run_agent_models_expansion_notified.sh glm` (after `bash scripts/start_vllm_glm47flash.sh`) | TR passes at 12:58:46, SU-full starts 12:59:13 and reaches 203/300 (last entry a 1500 s timeout). Stopped the same day with a `pkill -TERM` sequence over launcher, runner, agents and the GLM vLLM to free the GPUs for the Devstral FC regeneration. No completion banner; the next GLM banner is 09/14. | [followup_agent_models_glm.log:3651](../logs/followup_agent_models_glm.log#L3651), [followup_agent_models_glm.log:3694](../logs/followup_agent_models_glm.log#L3694), [followup_agent_models_glm.log:4125](../logs/followup_agent_models_glm.log#L4125) |
| 09/10 (before 16:47; exact time unrecorded) | Devstral / archive FC∞ run_2/run_3 | `python3 scripts/archive_devstral_fc_r23.py --archive-name devstral_fc_r23_before_rerun_20260910 --execute` | `status.json`: removed 200, remaining 100 (run_1 = calibration kept), 677 paths moved. Script committed 09/13 in `d4332a5`. | [status.json](../archives/devstral_fc_r23_before_rerun_20260910/status.json) |
| 09/10 16:47:30 | Devstral / main FC∞ regeneration | `nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 PYTHONUNBUFFERED=1 PYTHON="$PWD/venv/bin/python3" bash scripts/run_agent_models_expansion_notified.sh devstral` | Every cell except FC has 0 missing keys and passes 16:47:30–16:48:03; `di__binf__fc` runs 16:48:03 → 19:55:54 (200 runs); `sections run: main (ablation skipped)` at **19:55:55**. | [followup_agent_models_devstral.log:99919](../logs/followup_agent_models_devstral.log#L99919), [followup_agent_models_devstral.log:100302](../logs/followup_agent_models_devstral.log#L100302), [followup_agent_models_devstral.log:101110](../logs/followup_agent_models_devstral.log#L101110) |
| 09/10 22:13; 22:26; 09/11 10:12 → 11:05 | Devstral / main verdict re-evaluation (269 candidates) | `nohup venv/bin/python3 scripts/reevaluate_swebench_candidates.py run --output-dir archives/reeval_devstral_main_20260910 --continue-on-error`; resumed with `--resume --continue-on-error --eval-threads 8` | 22:13 attempt failed on the Python path (log kept as `.failed-python-path`); 22:26 attempt started and was killed with stale `sweb.eval` containers removed (`.aborted-20260910`); the 10:12 resume finishes at 11:05 (job mtimes 09/10 22:26 → 09/11 11:05). 174 True / 94 False / 1 unverified (`sympy__sympy-18189__online-trc__r3`). Applied with `apply --allow-partial --write`. Evaluation only; no agent runs. | [reeval_devstral_main_20260910.log](../logs/reeval_devstral_main_20260910.log), [reeval_devstral_main_20260910.pid](../logs/reeval_devstral_main_20260910.pid) (mtime 09/11 10:12) |
| 09/11 about 11:05–11:12 | Devstral / FC cell evaluation-only pass | `venv/bin/python3 scripts/run_experiment_iclr.py --iclr-section main --iclr-model devstral24b --iclr-cell di__binf__fc … --conditions full-context --runs-per-task 3 --max-workers 16 --eval-only` | Evaluates the regenerated FC runs after the re-evaluation apply. Time from EXPERIMENT_LOG.md; no separate log file. | [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#2026-09-10--devstral-fc-run_2run_3-archived-and-regenerated) |
| 09/11 11:14 → 12:24 | Qwen / main verdict re-evaluation (150 candidates) | `nohup venv/bin/python3 scripts/reevaluate_swebench_candidates.py run --candidates ICLR_results/issue/reeval_candidates_qwen35b_main_20260910/candidates.csv --output-dir archives/reeval_qwen35b_main_20260911 --model-tag qwen35-a3b --continue-on-error --eval-threads 8` | 84 True / 66 False; `apply --write`. Job mtimes 11:14 → 12:24. | [reeval_qwen35b_main_20260911.log](../logs/reeval_qwen35b_main_20260911.log), [reeval_qwen35b_main_20260911.pid](../logs/reeval_qwen35b_main_20260911.pid) |
| 09/11 15:05 → 15:36 | GLM / main verdict re-evaluation (37 candidates) | same form with `--candidates …/reeval_candidates_glm47flash_main_20260910/candidates.csv --output-dir archives/reeval_glm47flash_main_20260911 --model-tag glm47-flash` | 22 True / 14 False / 1 unverified (`sympy__sympy-19637__truncation__r3`); `apply --allow-partial --write`, then `aggregate_benchmark_results.py` and `dashboard/build_coverage.py`. | [reeval_glm47flash_main_20260911.log](../logs/reeval_glm47flash_main_20260911.log), [reeval_glm47flash_main_20260911.pid](../logs/reeval_glm47flash_main_20260911.pid) |
| 09/11 17:16 (archive name) | Qwen / archive the 476 seeded ablation copies | `bash scripts/archive_qwen_ablation_seeded.sh` (dry run), then `--execute` | `status.json`: 476 runs, 476 index rows removed. These are the 09/07 copies of main runs that were archived afterwards; the fresh ABL-30 runs of 09/08 are not touched. | [status.json](../archives/swebench_summary_bug_ablation_seeded_20260911_171617_374762025/status.json) |
| 09/11 17:17:08 | Qwen / ABL-25 ablation rerun (52 cells) | `nohup env SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 bash scripts/run_agent_models_expansion_notified.sh qwen` (Qwen vLLM restarted by hand, `--max-model-len 102400 --max-num-seqs 64`, no prefix caching) | Banner already reads `section 2 ablation (ABL-25)` (launcher switch uncommitted until `4cbf6ed`). d03 → d07 → d05 → depth-invariant at 10K → d05 20K → depth-invariant at 20K; `complete: sections=ablation` at **09/12 23:03:25**. | [followup_agent_models_qwen.log:7701](../logs/followup_agent_models_qwen.log#L7701), [followup_agent_models_qwen.log:13957](../logs/followup_agent_models_qwen.log#L13957) |
| 09/13 00:59:32 | Devstral / ABL-25 ablation, first launch | `nohup env SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 PYTHONUNBUFFERED=1 PYTHON="$PWD/venv/bin/python3" DEVSTRAL_A_BUDGET=17000 DEVSTRAL_P_BUDGET=21000 DEVSTRAL_B_BUDGET=24000 bash scripts/run_agent_models_expansion_notified.sh devstral` (Qwen vLLM stopped, `bash scripts/start_vllm_devstral.sh`) | d03 (17K/21K/24K) then d07 up to `d07__b24k__su-partial` (17:15:29). Stopped, with the Devstral vLLM, before the 17:58 Qwen limit-rerun launch (`kill -TERM 1642775`, `kill -TERM 1638339` in shell history; no stop banner). | [followup_agent_models_devstral.log:101112](../logs/followup_agent_models_devstral.log#L101112), [followup_agent_models_devstral.log:106455](../logs/followup_agent_models_devstral.log#L106455) |
| 09/13 17:58:59 → 22:36 | Qwen / FC∞ limit-failure rerun, phase 1 (55 runs, 200 steps / 3600 s) | `nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh` (after `DRY_RUN=1`; Qwen vLLM restarted on :8000, rootless Podman socket) | 55/55 recorded: resolved 12, submitted-unresolved 23, timeout again 14, step limit again 5, BadRequest 1. Results outside `ICLR_results/` (`results/adaptive_context_management/swebench/reruns/…diff=15m1h/`). | [rerun_qwen35b_fc_limits_phase1_launcher.log](../logs/rerun_qwen35b_fc_limits_phase1_launcher.log), [Active_runs.md](../Active_runs.md) |
| 09/13 22:56:55 → 09/14 00:01 | Qwen / FC∞ limit-failure rerun, phase 3 (10 runs) | `PHASE=3 nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh` | 10/10: resolved 3, submitted-unresolved 5, step limit again 1, BadRequest 1. | [rerun_qwen35b_fc_limits_phase3_launcher.log](../logs/rerun_qwen35b_fc_limits_phase3_launcher.log), [rerun_qwen35b_fc_limits_phase3.log](../logs/rerun_qwen35b_fc_limits_phase3.log) |
| 09/14 00:14 (killed); 00:17:43 → 02:14:11 → 04:44:10 | Qwen / overnight chain: phase 2 (17) then phase-1 again-19 (19), 300 steps / 5400 s | `P2_STEP_LIMIT=300 P2_TIMEOUT=5400 AGAIN_STEP_LIMIT=300 AGAIN_TIMEOUT=5400 nohup bash adaptive_context_management_analysis/run_rerun_limits_overnight.sh` | First launch killed after about 3 minutes (`kill 663530`, `kill -TERM 663537`) because the webhook was a placeholder; relaunch waits for phase 3, stage A 00:17:43–02:14:11 (exit 0), stage B 02:14:11–04:44:10 (exit 0). Overlay CSV rebuilt with `build_rerun_outcomes.py`. | [rerun_qwen35b_fc_limits_overnight.log:2](../logs/rerun_qwen35b_fc_limits_overnight.log#L2), [rerun_qwen35b_fc_limits_overnight.log:7](../logs/rerun_qwen35b_fc_limits_overnight.log#L7) |
| 09/14 09:51:20 | Devstral / ABL-25 ablation relaunch | `nohup env AGENTCTX_WS="$PWD" PYTHON="$PWD/venv/bin/python3" SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 DEVSTRAL_A_BUDGET=17000 DEVSTRAL_P_BUDGET=21000 DEVSTRAL_B_BUDGET=24000 bash scripts/run_agent_models_expansion_notified.sh devstral` (Devstral vLLM restarted 09:49, PID 1988226) | Cells through `d07__b24k__su-partial` revisited with 0 missing keys within 3 s; `d07__b24k__ss` executes from 09:53:48; d05 and depth-invariant cells follow; `complete: sections=ablation` at **19:00:57**. | [followup_agent_models_devstral.log:106646](../logs/followup_agent_models_devstral.log#L106646), [followup_agent_models_devstral.log:110690](../logs/followup_agent_models_devstral.log#L110690) |
| 09/14 20:52:45 | GLM / mistaken `SECTIONS=ablation` launch | `nohup env SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh glm > logs/followup_agent_models_glm_launcher.log` (Devstral vLLM killed, `bash scripts/start_vllm_glm47flash.sh`) | The `>` redirection truncated the launcher log, so the launcher log now starts here; the older GLM history survives only in `followup_agent_models_glm.log`. Terminated with `kill -TERM` after `d03__bA__tr` started. | [followup_agent_models_glm_launcher.log:1](../logs/followup_agent_models_glm_launcher.log#L1), [followup_agent_models_glm.log:4126](../logs/followup_agent_models_glm.log#L4126) |
| 09/14 20:53:53 | GLM / main P100 @13K | `nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh glm >> …` | SU-full 20:53 → SU-partial 23:35 → SS 09/15 05:25 → SS-partial 12:22 → TRC 18:50 → TRC+SU 23:59 → TRC+SS 09/16 06:07 → OTRC family 12:00 → FC∞ 09/17 04:19 → OTRC∞ 08:14; `sections run: main (ablation skipped)` at **09/17 13:50:28**. 13 cells × 300. | [followup_agent_models_glm.log:4128](../logs/followup_agent_models_glm.log#L4128), [followup_agent_models_glm.log:16080](../logs/followup_agent_models_glm.log#L16080) |
| 09/14–09/17 (between the GLM launch and the summarizer commits) | Terminal-Bench results synced from Albus (first rsync) | `rsync -avh --partial --progress ak58925@albus.ece.utexas.edu:/home/ak58925/agentCtx/ICLR_results/terminalbench /home/ak58925/agentCtx/ICLR_results/` (in a `tmux new -s copy-from-albus` session) | Copy only; no SWE trials. | shell history |
| 09/17 14:38:11 → 14:38:40 | Qwen / summarizer-ablation smoke (Qwen3.5-9B summarizer) | `N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 RUN_EVAL=0 CELLS=d05__b15k__su-full:summarization:0.5 ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/run_qwen_swe_summarizer_ablation.sh` (agent `start_vllm_qwen35.sh` :8000, summarizer `start_vllm_summarizer.sh qwen35-9b` :8001) | 1 task, no eval; `*-smoke` directory ignored by coverage. | [followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log:1](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log#L1) |
| 09/17 15:37:24 → 19:15:50 | Qwen / summarizer ablation, Qwen3.5-9B summarizer (ABL-25 × 3, 2 cells) | `nohup bash scripts/run_qwen_swe_summarizer_ablation_notified.sh` | `d05__b15k__su-full` 15:37:24, `di__b15k__trc-su` 17:35:53, complete 19:15:50. Output `model_ablation/qwen35b-sum-qwen35-9b/`. | [followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:1](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L1), [:297](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L297), [:612](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L612) |
| 09/18 10:31:14 → 13:55:49 | Qwen / summarizer ablation, Gemma-4-12B summarizer | `nohup env SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b bash scripts/run_qwen_swe_summarizer_ablation_notified.sh` (after `bash scripts/stop_vllm.sh logs/vllm_summarizer_qwen35-9b.pid` and `bash scripts/start_vllm_summarizer.sh gemma4-12b`; a leftover 9B process was first `kill -9`ed) | `su-full` 10:31:14, `trc-su` 12:27:40, complete 13:55:49. Gemma config committed after the run (`3c44002`, 14:40). | [followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:1](../logs/followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L1), [:292](../logs/followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L292), [:611](../logs/followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L611) |
| 09/18 14:28 (PID file) | Qwen vLLM restarted with prefix caching | `bash scripts/start_vllm_qwen35_prefix_cache.sh` (PID 1217568, :8000) | `vllm_qwen35_a3b.log` holds four `enable_prefix_caching=False` startups (08/23–09/14) and this single `=True` one. | [vllm_qwen35_a3b.pid](../logs/vllm_qwen35_a3b.pid) |
| 09/18 14:35:36 → 14:36:36 | Qwen / prefix-cache smoke | `N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 CELLS=d05__b15k__su-full:summarization:0.5 ICLR_MODEL=qwen35b-prefixcache-smoke bash scripts/run_qwen_swe_prefix_cache_ablation.sh` | 1 task; hit rate 76.5%. | [followup_sb_qwen_qwen35b-prefixcache-smoke.log:25](../logs/followup_sb_qwen_qwen35b-prefixcache-smoke.log#L25) |
| 09/18 14:37:23 → 09/19 02:23:07 | Qwen / prefix-cache ablation, 15K grid (11 cells × ABL-25 × 3) | `nohup bash scripts/run_qwen_swe_prefix_cache_ablation_notified.sh` (launcher PID 1243729) | TR 14:37 → SU-full 15:36 → SU-partial 16:40 → SS 17:40 → SS-partial 18:45 → TRC 19:48 → TRC+SU 20:49 → TRC+SS 21:56 → OTRC+TR 23:02 → OTRC+SU-partial 09/19 00:10 → OTRC+SS-partial 01:15; complete 02:23:07. Per-cell hit rates 85–91% (TR/TRC family) and 63–67% (OTRC family); whole grid 82.6%. Workflow committed 3 min after launch (`e5d25ca`). | [followup_sb_qwen_qwen35b-prefixcache.log:1](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L1), [:3353](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3353) |
| 09/19 19:36:08 → 21:53:16 | Qwen / prefix-cache baselines FC∞ and OTRC∞ (150 runs) | `nohup env CELLS="di__binf__fc:full-context:0.5 di__binf__otrc:online-trc:0.5" bash scripts/run_qwen_swe_prefix_cache_ablation_notified.sh` | FC∞ 19:36:08 (hit 96.3%), OTRC∞ 20:49:42 (69.8%); complete 21:53:16. Same 125-step / 1500 s limits as the caching-off main cells. | [followup_sb_qwen_qwen35b-prefixcache.log:3355](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3355), [:3997](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3997) |
| 09/19 23:53 (PID file); 09/20 00:00:06 | GLM / ABL-25 ablation (52 cells) | `nohup env -u MSWEA_SUMMARY_MODEL_CONFIG -u MSWEA_SUMMARY_MODEL_NAME -u MSWEA_SUMMARY_API_BASE SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 bash scripts/run_agent_models_expansion_notified.sh glm >> …` (after `bash scripts/start_vllm_glm47flash.sh`) | d03 (A/P/B) 09/20 → d07 09/21 → d05 and depth-invariant at A 09/22 → d05 and depth-invariant at B 09/22–23; `complete: sections=ablation (full grid: 3,900 main + 3,900 ablation runs)` at **09/23 10:31:24**. | [followup_agent_models_glm.log:16082](../logs/followup_agent_models_glm.log#L16082), [followup_agent_models_glm.log:31752](../logs/followup_agent_models_glm.log#L31752) |
| 09/23 11:32 → 13:42 | Qwen / main review-253 re-evaluation (evidence only) | `nohup venv/bin/python scripts/reevaluate_swebench_candidates.py run --candidates ICLR_results/issue/reeval_candidates_qwen35b_review253_20260923/candidates.csv --output-dir ICLR_results/ICLR_reeval/qwen35b_main_review253_20260923 --model-tag qwen35-a3b --continue-on-error` (after `plan`) | 253/253 verified: 165 True / 88 False; 134 False→True versus the 09/10 audit, 0 True→False. Canonical indexes not updated by this step. Job mtimes 11:32 → 13:42. | [reeval_qwen35b_review253_20260923.log](../logs/reeval_qwen35b_review253_20260923.log), [manifest.json](ICLR_reeval/qwen35b_main_review253_20260923/manifest.json) |
| 09/24 between 11:44 and 16:01 (index mtimes 15:57) | Qwen / apply review-253 to the canonical main indexes | `venv/bin/python scripts/reevaluate_swebench_candidates.py apply --output-dir ICLR_results/ICLR_reeval/qwen35b_main_review253_20260923 --write`; `cp -r …/backups/*/ archive/swebench_main_qwen35b_pre_reeval_20260924/`; `venv/bin/python analysis/aggregate_benchmark_results.py --benchmark swebench`; `venv/bin/python scripts/build_coverage.py` | All 35 `main/qwen35b` indexes rewritten; pre-apply copies kept under `archive/`. Commit `397c232` 16:01 carries the updated outcomes table. | [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#2026-092324--qwen-main-review-253-re-evaluation-applied-09-24) |
| 09/24 15:14:50 → 16:27; applied by 16:31 | Qwen / ABL-25 ablation 155-run re-evaluation and apply | `nohup venv/bin/python scripts/reevaluate_swebench_candidates.py run --candidates ICLR_results/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv --output-dir ICLR_results/ICLR_reeval/qwen35b_ablation_abl25_155_20260924 --model-tag qwen35-a3b --continue-on-error`; then `apply … --write`, backup copy, aggregate, coverage | 155/155 verified, all `resolved=False` (no verdict flips); affected `ablation/qwen35b` indexes carry mtime 16:31. | [reeval_qwen35b_ablation155_20260924.pid](../logs/reeval_qwen35b_ablation155_20260924.pid), [reeval_qwen35b_ablation155_20260924.log](../logs/reeval_qwen35b_ablation155_20260924.log) |
| 09/24–09/25 | Terminal-Bench model/prefix-cache ablations synced from Albus (second rsync) | `rsync … albus…:/home/ak58925/agentCtx/ICLR_results/terminalbench/{model_ablation,prefix_cache_ablation} /home/ak58925/agentCtx/ICLR_results/terminalbench/` | Copy only. | shell history |
| 09/25–09/26 | Figure and documentation commits only | — | No SWE launches; `git log` 09/25 is figure work, 09/26 17:59–18:39 is the re-eval results and the EXPERIMENT_LOG backfill. | `git log` |
| 09/26 18:12:01 → 18:14:08 | Workspace move to `~/ICLR27/` | `crontab -l > ~/crontab.bak; crontab -l \| grep -v publish_cron.sh \| crontab -; kill 232881; mkdir -p ~/ICLR27; mv ~/agentCtx ~/ICLR27/agentCtx; mv ~/agentCtx-data ~/ICLR27/agentCtx-data; git worktree repair ~/ICLR27/agentCtx-data; grep -rlI --null "/home/ak58925/agentCtx" venv*/bin venv*/lib/python*/site-packages/*.pth \| xargs -0 sed -i 's#/home/ak58925/agentCtx#/home/ak58925/ICLR27/agentCtx#g'; ( crontab -l; echo "0,30 * * * * /home/ak58925/ICLR27/agentCtx/dashboard/publish_cron.sh" ) \| crontab -; nohup venv/bin/python dashboard/watch.py --interval-minutes 10 > logs/watch.log` | Dashboard cron and watcher stopped, directories moved, venv paths rewritten, cron re-added with the new path, watcher restarted (first rebuild 18:14:08). The webhook was then moved into `~/.config/agentctx/slack.env` (`set -a; source …`). No experiment process was running. | [crontab.bak](/home/ak58925/crontab.bak) (mtime 18:12:01), [watch.log:3](../logs/watch.log#L3) |
| 09/27 02:41:12 (server); 02:48, 02:50:12 (smoke); 03:18:40 → 09:45:39 (chain) | Post-ICLR r2 campaign in a **separate checkout** `~/adaptive-context-management/agentCtx` (branch `akiho-dev`, HEAD `55d3934`) | `N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 CELLS=di__b15k__su-free:summarization-free:0.5 R2_MODEL=qwen35b-smoke bash scripts/expansions/run_r2_swe_p30s.sh`; then `RUNS_PER_TASK=3 bash scripts/notify_run.sh --unit r2/swebench/p30s/qwen35b-chain --lock r2_p30s_chain -- bash -c 'for p in su-free fc ss-free; do bash scripts/notify_run.sh --foreground --unit "r2/swebench/p30s/qwen35b-$p" -- bash scripts/expansions/run_r2_swe_p30s.sh "$p" \|\| exit 1; done'` | Qwen3.5-35B-A3B served with `--reasoning-parser qwen3` and prefix caching (PID 2052914, :8000). P30S cohort (`task_lists/p30_swe_stratified.json`) × 3 runs, 300 steps / 5400 s: `di__b15k__su-free` 03:18:40 → 05:08:29, `di__binf__fc` 05:08:30 → 07:32:50, `di__b15k__ss-free` 07:32:51 → 09:45:39; 90 records per cell. The chain log has 242 `Eval harness error … (no verdict; will be retried)` lines and the indexes hold `resolved=null` for 77/90 (SU-free), 85/90 (FC) and 80/90 (SS-free); only LimitsExceeded/no-patch rows carry `False`. These runs are outside `ICLR_results/` and outside this repository; they are listed here only because they are in the same shell history. | [r2 EXPERIMENT_LOG.md](/home/ak58925/adaptive-context-management/agentCtx/experiments/r2/EXPERIMENT_LOG.md), [chain log](/home/ak58925/adaptive-context-management/agentCtx/logs/experiments/r2_swebench_p30s_qwen35b-chain_20260927_031839.log) |

## Serving and infrastructure changes in this period

| When (CDT) | Change | Evidence |
|---|---|---|
| 09/09 before 15:33 | Qwen vLLM (PID 2552238) stopped; Devstral vLLM started on :8002 | shell history, [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#2026-09-09--devstral-main-rerun-of-the-archived-summary-bug-runs-p100-21k) |
| 09/10 12:58 and same-day stop | GLM vLLM (:8003, `venv-glm-cu129-clean`) started for the main resume attempt, then `pkill -TERM … GLM-4.7-Flash` | shell history |
| 09/10 (after the GLM stop) | Devstral vLLM restarted for the FC regeneration; `rg 'enable_prefix_caching=' logs/vllm_devstral.log` checked | shell history |
| 09/11 | The re-evaluation tooling (`34ac3cb`, `b244237`, `90a4899`) capped container threads and lowered the harness test timeout to 600 s after leftover `pytest` processes with 255 threads were found; 28 stale `sweb.eval.*` containers from 09/06 removed with `podman rm -f` | shell history, `git log` |
| 09/11 before 17:17 | Qwen vLLM restarted by hand (TP=4, `--max-model-len 102400 --max-num-seqs 64`) after killing the Devstral server | shell history |
| 09/13 before 00:59 | Qwen vLLM stopped, Devstral started; 09/13 evening reversed again for the limit reruns; 09/14 09:49 Devstral started (PID 1988226); 09/14 evening Devstral killed, GLM started | PID files, shell history |
| 09/17 14:31 / 09/18 10:20 | Qwen agent server via `start_vllm_qwen35.sh` (PID 4040709, `--gpu-memory-utilization 0.70`) plus summarizer servers on :8001 (9B, then Gemma PID 3147809) | PID files |
| 09/18 14:28 | Qwen server with `--enable-prefix-caching` (PID 1217568); kept up through 09/19 21:53 for the whole prefix-cache grid (the launcher reads `/metrics`) | [vllm_qwen35_a3b.pid](../logs/vllm_qwen35_a3b.pid) |
| 09/19 23:53 | GLM server (PID 2687709) for the ABL-25 ablation | [vllm_glm47flash.pid](../logs/vllm_glm47flash.pid) |
| 09/23 15:14–15:58 | `mini-swe-agent` submodule repointed to `takeshiho0531/mini-swe-agent` branch `event-log` (`f221b57`), then bumped for the online-TRC task-statement fix (`9af9bda`). Existing OTRC results were not re-run. | `git log`, [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#harness-bug--online-trc-hook-cleared-the-task-statement-fixed-2026-09-23) |
| 09/26 23:14–09/27 00:39 (other checkout) | r2 code: summary cleaning/validation, 300 steps / 5400 s limits, reasoning parser on by default, SU-free / SS-free primitives | [r2 EXPERIMENT_LOG.md](/home/ak58925/adaptive-context-management/agentCtx/experiments/r2/EXPERIMENT_LOG.md) |

## Cell transitions within each launch, September 8–23

Rows are the `--- <section>/<model>/<cell> ---` banners the launcher writes when it enters a cell. A cell whose keys are all present passes in seconds, so consecutive rows with the same timestamp are skips, not trials. Line numbers refer to the runner logs (`followup_agent_models_<model>.log`); the GLM launcher log was truncated on 09/14 and cannot be used for earlier entries.

### Qwen 09/07 launcher: rest of main and the ABL-30 traversal, until it was stopped on 09/08

Continuation of the 09/07 20:01:53 launch (the September 7 table above ends at SS@15K). Cells with no missing keys pass in seconds. The ABL-30 rows executed here stay in the ablation indexes next to the later ABL-25 rerun, which is why several `ablation/qwen35b` cells hold more than 75 records; the 476 ablation copies seeded from archived main runs are a different set and were archived on 09/11. The launcher was stopped between the 16:10:25 cell start and the 16:20:42 archive, which reports no launcher running.

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/07 21:49:14 | `main/qwen35b/d05__b15k__ss-partial` | [followup_agent_models_qwen.log:368](../logs/followup_agent_models_qwen.log#L368) |
| 09/08 01:17:19 | `main/qwen35b/di__b15k__trc` | [followup_agent_models_qwen.log:947](../logs/followup_agent_models_qwen.log#L947) |
| 09/08 01:27:19 | `main/qwen35b/di__b15k__trc-su` | [followup_agent_models_qwen.log:984](../logs/followup_agent_models_qwen.log#L984) |
| 09/08 01:37:19 | `main/qwen35b/di__b15k__trc-ss` | [followup_agent_models_qwen.log:1021](../logs/followup_agent_models_qwen.log#L1021) |
| 09/08 02:15:12 | `main/qwen35b/di__b15k__otrc-tr` | [followup_agent_models_qwen.log:1083](../logs/followup_agent_models_qwen.log#L1083) |
| 09/08 02:25:13 | `main/qwen35b/di__b15k__otrc-su-partial` | [followup_agent_models_qwen.log:1120](../logs/followup_agent_models_qwen.log#L1120) |
| 09/08 02:26:04 | `main/qwen35b/di__b15k__otrc-ss-partial` | [followup_agent_models_qwen.log:1156](../logs/followup_agent_models_qwen.log#L1156) |
| 09/08 05:19:41 | `main/qwen35b/di__binf__fc` | [followup_agent_models_qwen.log:1485](../logs/followup_agent_models_qwen.log#L1485) |
| 09/08 05:29:41 | `main/qwen35b/di__binf__otrc` | [followup_agent_models_qwen.log:1522](../logs/followup_agent_models_qwen.log#L1522) |
| 09/08 05:39:42 | `ablation/qwen35b/d03__b10k__tr` | [followup_agent_models_qwen.log:1560](../logs/followup_agent_models_qwen.log#L1560) |
| 09/08 05:39:43 | `ablation/qwen35b/d03__b10k__su-full` | [followup_agent_models_qwen.log:1594](../logs/followup_agent_models_qwen.log#L1594) |
| 09/08 05:39:43 | `ablation/qwen35b/d03__b10k__su-partial` | [followup_agent_models_qwen.log:1628](../logs/followup_agent_models_qwen.log#L1628) |
| 09/08 05:39:43 | `ablation/qwen35b/d03__b10k__ss` | [followup_agent_models_qwen.log:1662](../logs/followup_agent_models_qwen.log#L1662) |
| 09/08 07:03:17 | `ablation/qwen35b/d03__b10k__ss-partial` | [followup_agent_models_qwen.log:1850](../logs/followup_agent_models_qwen.log#L1850) |
| 09/08 08:32:57 | `ablation/qwen35b/d03__b15k__tr` | [followup_agent_models_qwen.log:2104](../logs/followup_agent_models_qwen.log#L2104) |
| 09/08 08:32:57 | `ablation/qwen35b/d03__b15k__su-full` | [followup_agent_models_qwen.log:2138](../logs/followup_agent_models_qwen.log#L2138) |
| 09/08 08:32:57 | `ablation/qwen35b/d03__b15k__su-partial` | [followup_agent_models_qwen.log:2172](../logs/followup_agent_models_qwen.log#L2172) |
| 09/08 08:32:57 | `ablation/qwen35b/d03__b15k__ss` | [followup_agent_models_qwen.log:2206](../logs/followup_agent_models_qwen.log#L2206) |
| 09/08 09:03:33 | `ablation/qwen35b/d03__b15k__ss-partial` | [followup_agent_models_qwen.log:2302](../logs/followup_agent_models_qwen.log#L2302) |
| 09/08 09:55:24 | `ablation/qwen35b/d03__b20k__tr` | [followup_agent_models_qwen.log:2466](../logs/followup_agent_models_qwen.log#L2466) |
| 09/08 09:55:24 | `ablation/qwen35b/d03__b20k__su-full` | [followup_agent_models_qwen.log:2500](../logs/followup_agent_models_qwen.log#L2500) |
| 09/08 09:55:24 | `ablation/qwen35b/d03__b20k__su-partial` | [followup_agent_models_qwen.log:2534](../logs/followup_agent_models_qwen.log#L2534) |
| 09/08 09:55:25 | `ablation/qwen35b/d03__b20k__ss` | [followup_agent_models_qwen.log:2568](../logs/followup_agent_models_qwen.log#L2568) |
| 09/08 10:13:57 | `ablation/qwen35b/d03__b20k__ss-partial` | [followup_agent_models_qwen.log:2636](../logs/followup_agent_models_qwen.log#L2636) |
| 09/08 10:55:02 | `ablation/qwen35b/d07__b10k__tr` | [followup_agent_models_qwen.log:2768](../logs/followup_agent_models_qwen.log#L2768) |
| 09/08 10:55:02 | `ablation/qwen35b/d07__b10k__su-full` | [followup_agent_models_qwen.log:2802](../logs/followup_agent_models_qwen.log#L2802) |
| 09/08 11:03:10 | `ablation/qwen35b/d07__b10k__su-partial` | [followup_agent_models_qwen.log:2838](../logs/followup_agent_models_qwen.log#L2838) |
| 09/08 11:04:58 | `ablation/qwen35b/d07__b10k__ss` | [followup_agent_models_qwen.log:2876](../logs/followup_agent_models_qwen.log#L2876) |
| 09/08 11:57:03 | `ablation/qwen35b/d07__b10k__ss-partial` | [followup_agent_models_qwen.log:3046](../logs/followup_agent_models_qwen.log#L3046) |
| 09/08 13:20:58 | `ablation/qwen35b/d07__b15k__tr` | [followup_agent_models_qwen.log:3329](../logs/followup_agent_models_qwen.log#L3329) |
| 09/08 13:20:58 | `ablation/qwen35b/d07__b15k__su-full` | [followup_agent_models_qwen.log:3363](../logs/followup_agent_models_qwen.log#L3363) |
| 09/08 13:25:28 | `ablation/qwen35b/d07__b15k__su-partial` | [followup_agent_models_qwen.log:3401](../logs/followup_agent_models_qwen.log#L3401) |
| 09/08 13:25:28 | `ablation/qwen35b/d07__b15k__ss` | [followup_agent_models_qwen.log:3435](../logs/followup_agent_models_qwen.log#L3435) |
| 09/08 13:54:39 | `ablation/qwen35b/d07__b15k__ss-partial` | [followup_agent_models_qwen.log:3530](../logs/followup_agent_models_qwen.log#L3530) |
| 09/08 14:52:21 | `ablation/qwen35b/d07__b20k__tr` | [followup_agent_models_qwen.log:3734](../logs/followup_agent_models_qwen.log#L3734) |
| 09/08 14:52:21 | `ablation/qwen35b/d07__b20k__su-full` | [followup_agent_models_qwen.log:3768](../logs/followup_agent_models_qwen.log#L3768) |
| 09/08 14:52:22 | `ablation/qwen35b/d07__b20k__su-partial` | [followup_agent_models_qwen.log:3802](../logs/followup_agent_models_qwen.log#L3802) |
| 09/08 14:52:22 | `ablation/qwen35b/d07__b20k__ss` | [followup_agent_models_qwen.log:3836](../logs/followup_agent_models_qwen.log#L3836) |
| 09/08 15:16:09 | `ablation/qwen35b/d07__b20k__ss-partial` | [followup_agent_models_qwen.log:3918](../logs/followup_agent_models_qwen.log#L3918) |
| 09/08 16:04:04 | `ablation/qwen35b/d05__b10k__tr` | [followup_agent_models_qwen.log:4066](../logs/followup_agent_models_qwen.log#L4066) |
| 09/08 16:04:05 | `ablation/qwen35b/d05__b10k__su-full` | [followup_agent_models_qwen.log:4100](../logs/followup_agent_models_qwen.log#L4100) |
| 09/08 16:10:25 | `ablation/qwen35b/d05__b10k__su-partial` | [followup_agent_models_qwen.log:4140](../logs/followup_agent_models_qwen.log#L4140) |

### Qwen main-only resume: 09/08 16:41:25 (stopped) and 16:48:02 → 09/09 14:53:13

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/08 16:41:25 | `main/qwen35b/d05__b15k__tr` | [followup_agent_models_qwen.log:4142](../logs/followup_agent_models_qwen.log#L4142) |
| 09/08 16:41:25 | `main/qwen35b/d05__b15k__su-full` | [followup_agent_models_qwen.log:4176](../logs/followup_agent_models_qwen.log#L4176) |
| 09/08 16:48:02 | `main/qwen35b/d05__b15k__tr` | [followup_agent_models_qwen.log:4178](../logs/followup_agent_models_qwen.log#L4178) |
| 09/08 16:48:02 | `main/qwen35b/d05__b15k__su-full` | [followup_agent_models_qwen.log:4212](../logs/followup_agent_models_qwen.log#L4212) |
| 09/08 21:19:15 | `main/qwen35b/d05__b15k__su-partial` | [followup_agent_models_qwen.log:4907](../logs/followup_agent_models_qwen.log#L4907) |
| 09/09 02:26:59 | `main/qwen35b/d05__b15k__ss` | [followup_agent_models_qwen.log:5660](../logs/followup_agent_models_qwen.log#L5660) |
| 09/09 05:39:03 | `main/qwen35b/d05__b15k__ss-partial` | [followup_agent_models_qwen.log:6135](../logs/followup_agent_models_qwen.log#L6135) |
| 09/09 07:35:11 | `main/qwen35b/di__b15k__trc` | [followup_agent_models_qwen.log:6445](../logs/followup_agent_models_qwen.log#L6445) |
| 09/09 07:35:17 | `main/qwen35b/di__b15k__trc-su` | [followup_agent_models_qwen.log:6481](../logs/followup_agent_models_qwen.log#L6481) |
| 09/09 09:37:39 | `main/qwen35b/di__b15k__trc-ss` | [followup_agent_models_qwen.log:6800](../logs/followup_agent_models_qwen.log#L6800) |
| 09/09 10:56:35 | `main/qwen35b/di__b15k__otrc-tr` | [followup_agent_models_qwen.log:7017](../logs/followup_agent_models_qwen.log#L7017) |
| 09/09 10:56:41 | `main/qwen35b/di__b15k__otrc-su-partial` | [followup_agent_models_qwen.log:7053](../logs/followup_agent_models_qwen.log#L7053) |
| 09/09 13:45:01 | `main/qwen35b/di__b15k__otrc-ss-partial` | [followup_agent_models_qwen.log:7477](../logs/followup_agent_models_qwen.log#L7477) |
| 09/09 14:52:58 | `main/qwen35b/di__binf__fc` | [followup_agent_models_qwen.log:7627](../logs/followup_agent_models_qwen.log#L7627) |
| 09/09 14:53:05 | `main/qwen35b/di__binf__otrc` | [followup_agent_models_qwen.log:7663](../logs/followup_agent_models_qwen.log#L7663) |

### Devstral main rerun (P100 @21K): 09/09 15:33:07 → 09/10 06:14:27

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/09 15:33:07 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:95682](../logs/followup_agent_models_devstral.log#L95682) |
| 09/09 15:33:07 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:95716](../logs/followup_agent_models_devstral.log#L95716) |
| 09/09 18:18:26 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:96613](../logs/followup_agent_models_devstral.log#L96613) |
| 09/09 21:35:38 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:97515](../logs/followup_agent_models_devstral.log#L97515) |
| 09/10 00:12:05 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:98270](../logs/followup_agent_models_devstral.log#L98270) |
| 09/10 03:16:49 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:99093](../logs/followup_agent_models_devstral.log#L99093) |
| 09/10 03:16:49 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:99127](../logs/followup_agent_models_devstral.log#L99127) |
| 09/10 04:02:22 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:99333](../logs/followup_agent_models_devstral.log#L99333) |
| 09/10 04:50:12 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:99520](../logs/followup_agent_models_devstral.log#L99520) |
| 09/10 04:50:13 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:99554](../logs/followup_agent_models_devstral.log#L99554) |
| 09/10 05:44:51 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:99719](../logs/followup_agent_models_devstral.log#L99719) |
| 09/10 06:14:27 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:99849](../logs/followup_agent_models_devstral.log#L99849) |
| 09/10 06:14:27 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:99883](../logs/followup_agent_models_devstral.log#L99883) |

### Devstral main FC∞ regeneration: 09/10 16:47:30 → 19:55:55

Every cell except `di__binf__fc` reported 0 missing keys and passed within seconds.

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/10 16:47:30 | `main/devstral24b/d05__b21k__tr` | [followup_agent_models_devstral.log:99920](../logs/followup_agent_models_devstral.log#L99920) |
| 09/10 16:47:30 | `main/devstral24b/d05__b21k__su-full` | [followup_agent_models_devstral.log:99954](../logs/followup_agent_models_devstral.log#L99954) |
| 09/10 16:47:30 | `main/devstral24b/d05__b21k__su-partial` | [followup_agent_models_devstral.log:99988](../logs/followup_agent_models_devstral.log#L99988) |
| 09/10 16:47:30 | `main/devstral24b/d05__b21k__ss` | [followup_agent_models_devstral.log:100022](../logs/followup_agent_models_devstral.log#L100022) |
| 09/10 16:47:38 | `main/devstral24b/d05__b21k__ss-partial` | [followup_agent_models_devstral.log:100058](../logs/followup_agent_models_devstral.log#L100058) |
| 09/10 16:47:46 | `main/devstral24b/di__b21k__trc` | [followup_agent_models_devstral.log:100094](../logs/followup_agent_models_devstral.log#L100094) |
| 09/10 16:47:46 | `main/devstral24b/di__b21k__trc-su` | [followup_agent_models_devstral.log:100128](../logs/followup_agent_models_devstral.log#L100128) |
| 09/10 16:47:46 | `main/devstral24b/di__b21k__trc-ss` | [followup_agent_models_devstral.log:100162](../logs/followup_agent_models_devstral.log#L100162) |
| 09/10 16:47:54 | `main/devstral24b/di__b21k__otrc-tr` | [followup_agent_models_devstral.log:100198](../logs/followup_agent_models_devstral.log#L100198) |
| 09/10 16:47:54 | `main/devstral24b/di__b21k__otrc-su-partial` | [followup_agent_models_devstral.log:100232](../logs/followup_agent_models_devstral.log#L100232) |
| 09/10 16:48:02 | `main/devstral24b/di__b21k__otrc-ss-partial` | [followup_agent_models_devstral.log:100268](../logs/followup_agent_models_devstral.log#L100268) |
| 09/10 16:48:03 | `main/devstral24b/di__binf__fc` | [followup_agent_models_devstral.log:100302](../logs/followup_agent_models_devstral.log#L100302) |
| 09/10 19:55:54 | `main/devstral24b/di__binf__otrc` | [followup_agent_models_devstral.log:101076](../logs/followup_agent_models_devstral.log#L101076) |

### Qwen ABL-25 ablation: 09/11 17:17:08 → 09/12 23:03:25

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/11 17:17:08 | `ablation/qwen35b/d03__b10k__tr` | [followup_agent_models_qwen.log:7702](../logs/followup_agent_models_qwen.log#L7702) |
| 09/11 17:17:08 | `ablation/qwen35b/d03__b10k__su-full` | [followup_agent_models_qwen.log:7736](../logs/followup_agent_models_qwen.log#L7736) |
| 09/11 18:27:48 | `ablation/qwen35b/d03__b10k__su-partial` | [followup_agent_models_qwen.log:7970](../logs/followup_agent_models_qwen.log#L7970) |
| 09/11 19:34:26 | `ablation/qwen35b/d03__b10k__ss` | [followup_agent_models_qwen.log:8197](../logs/followup_agent_models_qwen.log#L8197) |
| 09/11 20:05:08 | `ablation/qwen35b/d03__b10k__ss-partial` | [followup_agent_models_qwen.log:8317](../logs/followup_agent_models_qwen.log#L8317) |
| 09/11 20:19:21 | `ablation/qwen35b/d03__b15k__tr` | [followup_agent_models_qwen.log:8383](../logs/followup_agent_models_qwen.log#L8383) |
| 09/11 20:19:21 | `ablation/qwen35b/d03__b15k__su-full` | [followup_agent_models_qwen.log:8417](../logs/followup_agent_models_qwen.log#L8417) |
| 09/11 21:13:19 | `ablation/qwen35b/d03__b15k__su-partial` | [followup_agent_models_qwen.log:8592](../logs/followup_agent_models_qwen.log#L8592) |
| 09/11 22:10:42 | `ablation/qwen35b/d03__b15k__ss` | [followup_agent_models_qwen.log:8774](../logs/followup_agent_models_qwen.log#L8774) |
| 09/11 22:54:37 | `ablation/qwen35b/d03__b15k__ss-partial` | [followup_agent_models_qwen.log:8919](../logs/followup_agent_models_qwen.log#L8919) |
| 09/11 23:18:11 | `ablation/qwen35b/d03__b20k__tr` | [followup_agent_models_qwen.log:9001](../logs/followup_agent_models_qwen.log#L9001) |
| 09/11 23:18:11 | `ablation/qwen35b/d03__b20k__su-full` | [followup_agent_models_qwen.log:9035](../logs/followup_agent_models_qwen.log#L9035) |
| 09/11 23:58:14 | `ablation/qwen35b/d03__b20k__su-partial` | [followup_agent_models_qwen.log:9163](../logs/followup_agent_models_qwen.log#L9163) |
| 09/12 00:48:13 | `ablation/qwen35b/d03__b20k__ss` | [followup_agent_models_qwen.log:9319](../logs/followup_agent_models_qwen.log#L9319) |
| 09/12 01:26:47 | `ablation/qwen35b/d03__b20k__ss-partial` | [followup_agent_models_qwen.log:9439](../logs/followup_agent_models_qwen.log#L9439) |
| 09/12 01:50:24 | `ablation/qwen35b/d07__b10k__tr` | [followup_agent_models_qwen.log:9523](../logs/followup_agent_models_qwen.log#L9523) |
| 09/12 01:50:24 | `ablation/qwen35b/d07__b10k__su-full` | [followup_agent_models_qwen.log:9557](../logs/followup_agent_models_qwen.log#L9557) |
| 09/12 02:57:38 | `ablation/qwen35b/d07__b10k__su-partial` | [followup_agent_models_qwen.log:9774](../logs/followup_agent_models_qwen.log#L9774) |
| 09/12 04:14:35 | `ablation/qwen35b/d07__b10k__ss` | [followup_agent_models_qwen.log:10005](../logs/followup_agent_models_qwen.log#L10005) |
| 09/12 04:43:10 | `ablation/qwen35b/d07__b10k__ss-partial` | [followup_agent_models_qwen.log:10131](../logs/followup_agent_models_qwen.log#L10131) |
| 09/12 04:51:02 | `ablation/qwen35b/d07__b15k__tr` | [followup_agent_models_qwen.log:10189](../logs/followup_agent_models_qwen.log#L10189) |
| 09/12 04:51:02 | `ablation/qwen35b/d07__b15k__su-full` | [followup_agent_models_qwen.log:10223](../logs/followup_agent_models_qwen.log#L10223) |
| 09/12 05:48:59 | `ablation/qwen35b/d07__b15k__su-partial` | [followup_agent_models_qwen.log:10407](../logs/followup_agent_models_qwen.log#L10407) |
| 09/12 06:59:48 | `ablation/qwen35b/d07__b15k__ss` | [followup_agent_models_qwen.log:10610](../logs/followup_agent_models_qwen.log#L10610) |
| 09/12 07:33:59 | `ablation/qwen35b/d07__b15k__ss-partial` | [followup_agent_models_qwen.log:10722](../logs/followup_agent_models_qwen.log#L10722) |
| 09/12 07:58:21 | `ablation/qwen35b/d07__b20k__tr` | [followup_agent_models_qwen.log:10814](../logs/followup_agent_models_qwen.log#L10814) |
| 09/12 07:58:22 | `ablation/qwen35b/d07__b20k__su-full` | [followup_agent_models_qwen.log:10848](../logs/followup_agent_models_qwen.log#L10848) |
| 09/12 08:49:34 | `ablation/qwen35b/d07__b20k__su-partial` | [followup_agent_models_qwen.log:11000](../logs/followup_agent_models_qwen.log#L11000) |
| 09/12 09:34:52 | `ablation/qwen35b/d07__b20k__ss` | [followup_agent_models_qwen.log:11132](../logs/followup_agent_models_qwen.log#L11132) |
| 09/12 10:12:29 | `ablation/qwen35b/d07__b20k__ss-partial` | [followup_agent_models_qwen.log:11242](../logs/followup_agent_models_qwen.log#L11242) |
| 09/12 10:32:04 | `ablation/qwen35b/d05__b10k__tr` | [followup_agent_models_qwen.log:11300](../logs/followup_agent_models_qwen.log#L11300) |
| 09/12 10:32:04 | `ablation/qwen35b/d05__b10k__su-full` | [followup_agent_models_qwen.log:11334](../logs/followup_agent_models_qwen.log#L11334) |
| 09/12 11:43:11 | `ablation/qwen35b/d05__b10k__su-partial` | [followup_agent_models_qwen.log:11560](../logs/followup_agent_models_qwen.log#L11560) |
| 09/12 12:57:55 | `ablation/qwen35b/d05__b10k__ss` | [followup_agent_models_qwen.log:11807](../logs/followup_agent_models_qwen.log#L11807) |
| 09/12 14:15:09 | `ablation/qwen35b/d05__b10k__ss-partial` | [followup_agent_models_qwen.log:12066](../logs/followup_agent_models_qwen.log#L12066) |
| 09/12 15:24:08 | `ablation/qwen35b/di__b10k__trc` | [followup_agent_models_qwen.log:12313](../logs/followup_agent_models_qwen.log#L12313) |
| 09/12 15:24:08 | `ablation/qwen35b/di__b10k__trc-su` | [followup_agent_models_qwen.log:12347](../logs/followup_agent_models_qwen.log#L12347) |
| 09/12 16:12:23 | `ablation/qwen35b/di__b10k__trc-ss` | [followup_agent_models_qwen.log:12514](../logs/followup_agent_models_qwen.log#L12514) |
| 09/12 17:01:28 | `ablation/qwen35b/di__b10k__otrc-tr` | [followup_agent_models_qwen.log:12679](../logs/followup_agent_models_qwen.log#L12679) |
| 09/12 17:01:28 | `ablation/qwen35b/di__b10k__otrc-su-partial` | [followup_agent_models_qwen.log:12713](../logs/followup_agent_models_qwen.log#L12713) |
| 09/12 17:54:20 | `ablation/qwen35b/di__b10k__otrc-ss-partial` | [followup_agent_models_qwen.log:12886](../logs/followup_agent_models_qwen.log#L12886) |
| 09/12 18:46:16 | `ablation/qwen35b/d05__b20k__tr` | [followup_agent_models_qwen.log:13057](../logs/followup_agent_models_qwen.log#L13057) |
| 09/12 18:46:16 | `ablation/qwen35b/d05__b20k__su-full` | [followup_agent_models_qwen.log:13091](../logs/followup_agent_models_qwen.log#L13091) |
| 09/12 19:26:21 | `ablation/qwen35b/d05__b20k__su-partial` | [followup_agent_models_qwen.log:13217](../logs/followup_agent_models_qwen.log#L13217) |
| 09/12 20:15:43 | `ablation/qwen35b/d05__b20k__ss` | [followup_agent_models_qwen.log:13374](../logs/followup_agent_models_qwen.log#L13374) |
| 09/12 21:02:50 | `ablation/qwen35b/d05__b20k__ss-partial` | [followup_agent_models_qwen.log:13517](../logs/followup_agent_models_qwen.log#L13517) |
| 09/12 21:56:49 | `ablation/qwen35b/di__b20k__trc` | [followup_agent_models_qwen.log:13673](../logs/followup_agent_models_qwen.log#L13673) |
| 09/12 21:56:49 | `ablation/qwen35b/di__b20k__trc-su` | [followup_agent_models_qwen.log:13707](../logs/followup_agent_models_qwen.log#L13707) |
| 09/12 22:00:51 | `ablation/qwen35b/di__b20k__trc-ss` | [followup_agent_models_qwen.log:13753](../logs/followup_agent_models_qwen.log#L13753) |
| 09/12 22:09:44 | `ablation/qwen35b/di__b20k__otrc-tr` | [followup_agent_models_qwen.log:13797](../logs/followup_agent_models_qwen.log#L13797) |
| 09/12 22:09:44 | `ablation/qwen35b/di__b20k__otrc-su-partial` | [followup_agent_models_qwen.log:13831](../logs/followup_agent_models_qwen.log#L13831) |
| 09/12 22:37:27 | `ablation/qwen35b/di__b20k__otrc-ss-partial` | [followup_agent_models_qwen.log:13904](../logs/followup_agent_models_qwen.log#L13904) |

### Devstral ABL-25 ablation, first launch 09/13 00:59:32 (stopped after `d07__b24k__su-partial`)

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/13 00:59:32 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:101113](../logs/followup_agent_models_devstral.log#L101113) |
| 09/13 00:59:32 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:101147](../logs/followup_agent_models_devstral.log#L101147) |
| 09/13 01:51:44 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:101435](../logs/followup_agent_models_devstral.log#L101435) |
| 09/13 02:43:42 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:101725](../logs/followup_agent_models_devstral.log#L101725) |
| 09/13 03:30:45 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:101957](../logs/followup_agent_models_devstral.log#L101957) |
| 09/13 04:16:28 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:102199](../logs/followup_agent_models_devstral.log#L102199) |
| 09/13 04:16:28 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:102233](../logs/followup_agent_models_devstral.log#L102233) |
| 09/13 05:06:08 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:102493](../logs/followup_agent_models_devstral.log#L102493) |
| 09/13 05:53:45 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:102759](../logs/followup_agent_models_devstral.log#L102759) |
| 09/13 06:42:21 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:103003](../logs/followup_agent_models_devstral.log#L103003) |
| 09/13 07:27:46 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:103233](../logs/followup_agent_models_devstral.log#L103233) |
| 09/13 07:27:46 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:103267](../logs/followup_agent_models_devstral.log#L103267) |
| 09/13 08:04:54 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:103467](../logs/followup_agent_models_devstral.log#L103467) |
| 09/13 08:48:23 | `ablation/devstral24b/d03__b24k__ss` | [followup_agent_models_devstral.log:103695](../logs/followup_agent_models_devstral.log#L103695) |
| 09/13 09:24:09 | `ablation/devstral24b/d03__b24k__ss-partial` | [followup_agent_models_devstral.log:103879](../logs/followup_agent_models_devstral.log#L103879) |
| 09/13 10:03:50 | `ablation/devstral24b/d07__b17k__tr` | [followup_agent_models_devstral.log:104091](../logs/followup_agent_models_devstral.log#L104091) |
| 09/13 10:03:50 | `ablation/devstral24b/d07__b17k__su-full` | [followup_agent_models_devstral.log:104125](../logs/followup_agent_models_devstral.log#L104125) |
| 09/13 10:59:47 | `ablation/devstral24b/d07__b17k__su-partial` | [followup_agent_models_devstral.log:104417](../logs/followup_agent_models_devstral.log#L104417) |
| 09/13 11:52:40 | `ablation/devstral24b/d07__b17k__ss` | [followup_agent_models_devstral.log:104703](../logs/followup_agent_models_devstral.log#L104703) |
| 09/13 12:43:45 | `ablation/devstral24b/d07__b17k__ss-partial` | [followup_agent_models_devstral.log:104961](../logs/followup_agent_models_devstral.log#L104961) |
| 09/13 13:30:48 | `ablation/devstral24b/d07__b21k__tr` | [followup_agent_models_devstral.log:105221](../logs/followup_agent_models_devstral.log#L105221) |
| 09/13 13:30:48 | `ablation/devstral24b/d07__b21k__su-full` | [followup_agent_models_devstral.log:105255](../logs/followup_agent_models_devstral.log#L105255) |
| 09/13 14:22:32 | `ablation/devstral24b/d07__b21k__su-partial` | [followup_agent_models_devstral.log:105517](../logs/followup_agent_models_devstral.log#L105517) |
| 09/13 15:07:25 | `ablation/devstral24b/d07__b21k__ss` | [followup_agent_models_devstral.log:105755](../logs/followup_agent_models_devstral.log#L105755) |
| 09/13 15:49:34 | `ablation/devstral24b/d07__b21k__ss-partial` | [followup_agent_models_devstral.log:105973](../logs/followup_agent_models_devstral.log#L105973) |
| 09/13 16:31:50 | `ablation/devstral24b/d07__b24k__tr` | [followup_agent_models_devstral.log:106195](../logs/followup_agent_models_devstral.log#L106195) |
| 09/13 16:31:50 | `ablation/devstral24b/d07__b24k__su-full` | [followup_agent_models_devstral.log:106229](../logs/followup_agent_models_devstral.log#L106229) |
| 09/13 17:15:29 | `ablation/devstral24b/d07__b24k__su-partial` | [followup_agent_models_devstral.log:106455](../logs/followup_agent_models_devstral.log#L106455) |

### Devstral ABL-25 ablation, relaunch 09/14 09:51:20 → 19:00:57

Cells through `d07__b24k__su-partial` were revisited with 0 missing keys (all start within 09:51:20–09:51:23); execution resumes at `d07__b24k__ss`.

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/14 09:51:20 | `ablation/devstral24b/d03__b17k__tr` | [followup_agent_models_devstral.log:106647](../logs/followup_agent_models_devstral.log#L106647) |
| 09/14 09:51:20 | `ablation/devstral24b/d03__b17k__su-full` | [followup_agent_models_devstral.log:106681](../logs/followup_agent_models_devstral.log#L106681) |
| 09/14 09:51:20 | `ablation/devstral24b/d03__b17k__su-partial` | [followup_agent_models_devstral.log:106715](../logs/followup_agent_models_devstral.log#L106715) |
| 09/14 09:51:20 | `ablation/devstral24b/d03__b17k__ss` | [followup_agent_models_devstral.log:106749](../logs/followup_agent_models_devstral.log#L106749) |
| 09/14 09:51:20 | `ablation/devstral24b/d03__b17k__ss-partial` | [followup_agent_models_devstral.log:106783](../logs/followup_agent_models_devstral.log#L106783) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b21k__tr` | [followup_agent_models_devstral.log:106817](../logs/followup_agent_models_devstral.log#L106817) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b21k__su-full` | [followup_agent_models_devstral.log:106851](../logs/followup_agent_models_devstral.log#L106851) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b21k__su-partial` | [followup_agent_models_devstral.log:106885](../logs/followup_agent_models_devstral.log#L106885) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b21k__ss` | [followup_agent_models_devstral.log:106919](../logs/followup_agent_models_devstral.log#L106919) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b21k__ss-partial` | [followup_agent_models_devstral.log:106953](../logs/followup_agent_models_devstral.log#L106953) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b24k__tr` | [followup_agent_models_devstral.log:106987](../logs/followup_agent_models_devstral.log#L106987) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b24k__su-full` | [followup_agent_models_devstral.log:107021](../logs/followup_agent_models_devstral.log#L107021) |
| 09/14 09:51:21 | `ablation/devstral24b/d03__b24k__su-partial` | [followup_agent_models_devstral.log:107055](../logs/followup_agent_models_devstral.log#L107055) |
| 09/14 09:51:22 | `ablation/devstral24b/d03__b24k__ss` | [followup_agent_models_devstral.log:107089](../logs/followup_agent_models_devstral.log#L107089) |
| 09/14 09:51:22 | `ablation/devstral24b/d03__b24k__ss-partial` | [followup_agent_models_devstral.log:107123](../logs/followup_agent_models_devstral.log#L107123) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b17k__tr` | [followup_agent_models_devstral.log:107157](../logs/followup_agent_models_devstral.log#L107157) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b17k__su-full` | [followup_agent_models_devstral.log:107191](../logs/followup_agent_models_devstral.log#L107191) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b17k__su-partial` | [followup_agent_models_devstral.log:107225](../logs/followup_agent_models_devstral.log#L107225) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b17k__ss` | [followup_agent_models_devstral.log:107259](../logs/followup_agent_models_devstral.log#L107259) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b17k__ss-partial` | [followup_agent_models_devstral.log:107293](../logs/followup_agent_models_devstral.log#L107293) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b21k__tr` | [followup_agent_models_devstral.log:107327](../logs/followup_agent_models_devstral.log#L107327) |
| 09/14 09:51:22 | `ablation/devstral24b/d07__b21k__su-full` | [followup_agent_models_devstral.log:107361](../logs/followup_agent_models_devstral.log#L107361) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b21k__su-partial` | [followup_agent_models_devstral.log:107395](../logs/followup_agent_models_devstral.log#L107395) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b21k__ss` | [followup_agent_models_devstral.log:107429](../logs/followup_agent_models_devstral.log#L107429) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b21k__ss-partial` | [followup_agent_models_devstral.log:107463](../logs/followup_agent_models_devstral.log#L107463) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b24k__tr` | [followup_agent_models_devstral.log:107497](../logs/followup_agent_models_devstral.log#L107497) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b24k__su-full` | [followup_agent_models_devstral.log:107531](../logs/followup_agent_models_devstral.log#L107531) |
| 09/14 09:51:23 | `ablation/devstral24b/d07__b24k__su-partial` | [followup_agent_models_devstral.log:107565](../logs/followup_agent_models_devstral.log#L107565) |
| 09/14 09:53:48 | `ablation/devstral24b/d07__b24k__ss` | [followup_agent_models_devstral.log:107612](../logs/followup_agent_models_devstral.log#L107612) |
| 09/14 10:34:11 | `ablation/devstral24b/d07__b24k__ss-partial` | [followup_agent_models_devstral.log:107812](../logs/followup_agent_models_devstral.log#L107812) |
| 09/14 11:09:12 | `ablation/devstral24b/d05__b17k__tr` | [followup_agent_models_devstral.log:108004](../logs/followup_agent_models_devstral.log#L108004) |
| 09/14 11:09:12 | `ablation/devstral24b/d05__b17k__su-full` | [followup_agent_models_devstral.log:108038](../logs/followup_agent_models_devstral.log#L108038) |
| 09/14 12:05:10 | `ablation/devstral24b/d05__b17k__su-partial` | [followup_agent_models_devstral.log:108324](../logs/followup_agent_models_devstral.log#L108324) |
| 09/14 12:56:47 | `ablation/devstral24b/d05__b17k__ss` | [followup_agent_models_devstral.log:108621](../logs/followup_agent_models_devstral.log#L108621) |
| 09/14 13:46:39 | `ablation/devstral24b/d05__b17k__ss-partial` | [followup_agent_models_devstral.log:108873](../logs/followup_agent_models_devstral.log#L108873) |
| 09/14 14:38:06 | `ablation/devstral24b/di__b17k__trc` | [followup_agent_models_devstral.log:109145](../logs/followup_agent_models_devstral.log#L109145) |
| 09/14 14:38:06 | `ablation/devstral24b/di__b17k__trc-su` | [followup_agent_models_devstral.log:109179](../logs/followup_agent_models_devstral.log#L109179) |
| 09/14 14:52:10 | `ablation/devstral24b/di__b17k__trc-ss` | [followup_agent_models_devstral.log:109263](../logs/followup_agent_models_devstral.log#L109263) |
| 09/14 15:03:48 | `ablation/devstral24b/di__b17k__otrc-tr` | [followup_agent_models_devstral.log:109335](../logs/followup_agent_models_devstral.log#L109335) |
| 09/14 15:03:48 | `ablation/devstral24b/di__b17k__otrc-su-partial` | [followup_agent_models_devstral.log:109369](../logs/followup_agent_models_devstral.log#L109369) |
| 09/14 15:21:15 | `ablation/devstral24b/di__b17k__otrc-ss-partial` | [followup_agent_models_devstral.log:109459](../logs/followup_agent_models_devstral.log#L109459) |
| 09/14 15:37:47 | `ablation/devstral24b/d05__b24k__tr` | [followup_agent_models_devstral.log:109541](../logs/followup_agent_models_devstral.log#L109541) |
| 09/14 15:37:47 | `ablation/devstral24b/d05__b24k__su-full` | [followup_agent_models_devstral.log:109575](../logs/followup_agent_models_devstral.log#L109575) |
| 09/14 16:20:00 | `ablation/devstral24b/d05__b24k__su-partial` | [followup_agent_models_devstral.log:109795](../logs/followup_agent_models_devstral.log#L109795) |
| 09/14 17:00:48 | `ablation/devstral24b/d05__b24k__ss` | [followup_agent_models_devstral.log:110022](../logs/followup_agent_models_devstral.log#L110022) |
| 09/14 17:43:14 | `ablation/devstral24b/d05__b24k__ss-partial` | [followup_agent_models_devstral.log:110214](../logs/followup_agent_models_devstral.log#L110214) |
| 09/14 18:22:34 | `ablation/devstral24b/di__b24k__trc` | [followup_agent_models_devstral.log:110424](../logs/followup_agent_models_devstral.log#L110424) |
| 09/14 18:23:07 | `ablation/devstral24b/di__b24k__trc-su` | [followup_agent_models_devstral.log:110460](../logs/followup_agent_models_devstral.log#L110460) |
| 09/14 18:29:32 | `ablation/devstral24b/di__b24k__trc-ss` | [followup_agent_models_devstral.log:110502](../logs/followup_agent_models_devstral.log#L110502) |
| 09/14 18:36:23 | `ablation/devstral24b/di__b24k__otrc-tr` | [followup_agent_models_devstral.log:110542](../logs/followup_agent_models_devstral.log#L110542) |
| 09/14 18:36:23 | `ablation/devstral24b/di__b24k__otrc-su-partial` | [followup_agent_models_devstral.log:110576](../logs/followup_agent_models_devstral.log#L110576) |
| 09/14 18:49:39 | `ablation/devstral24b/di__b24k__otrc-ss-partial` | [followup_agent_models_devstral.log:110626](../logs/followup_agent_models_devstral.log#L110626) |

### GLM main resume attempt: 09/10 12:58:46 (stopped the same day)

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/10 12:58:46 | `main/glm47flash/d05__bP__tr` | [followup_agent_models_glm.log:3652](../logs/followup_agent_models_glm.log#L3652) |
| 09/10 12:59:13 | `main/glm47flash/d05__bP__su-full` | [followup_agent_models_glm.log:3694](../logs/followup_agent_models_glm.log#L3694) |

### GLM mistaken ablation launch (09/14 20:52:45) and main P100 @13K: 20:53:53 → 09/17 13:50:28

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/14 20:52:45 | `ablation/glm47flash/d03__bA__tr` | [followup_agent_models_glm.log:4127](../logs/followup_agent_models_glm.log#L4127) |
| 09/14 20:53:53 | `main/glm47flash/d05__bP__tr` | [followup_agent_models_glm.log:4129](../logs/followup_agent_models_glm.log#L4129) |
| 09/14 20:53:54 | `main/glm47flash/d05__bP__su-full` | [followup_agent_models_glm.log:4163](../logs/followup_agent_models_glm.log#L4163) |
| 09/14 23:35:52 | `main/glm47flash/d05__bP__su-partial` | [followup_agent_models_glm.log:4574](../logs/followup_agent_models_glm.log#L4574) |
| 09/15 05:25:42 | `main/glm47flash/d05__bP__ss` | [followup_agent_models_glm.log:5528](../logs/followup_agent_models_glm.log#L5528) |
| 09/15 12:22:12 | `main/glm47flash/d05__bP__ss-partial` | [followup_agent_models_glm.log:6563](../logs/followup_agent_models_glm.log#L6563) |
| 09/15 18:50:45 | `main/glm47flash/di__bP__trc` | [followup_agent_models_glm.log:7658](../logs/followup_agent_models_glm.log#L7658) |
| 09/15 23:59:11 | `main/glm47flash/di__bP__trc-su` | [followup_agent_models_glm.log:8755](../logs/followup_agent_models_glm.log#L8755) |
| 09/16 06:07:24 | `main/glm47flash/di__bP__trc-ss` | [followup_agent_models_glm.log:9880](../logs/followup_agent_models_glm.log#L9880) |
| 09/16 12:00:45 | `main/glm47flash/di__bP__otrc-tr` | [followup_agent_models_glm.log:11006](../logs/followup_agent_models_glm.log#L11006) |
| 09/16 17:15:47 | `main/glm47flash/di__bP__otrc-su-partial` | [followup_agent_models_glm.log:12103](../logs/followup_agent_models_glm.log#L12103) |
| 09/16 22:41:26 | `main/glm47flash/di__bP__otrc-ss-partial` | [followup_agent_models_glm.log:13151](../logs/followup_agent_models_glm.log#L13151) |
| 09/17 04:19:39 | `main/glm47flash/di__binf__fc` | [followup_agent_models_glm.log:14187](../logs/followup_agent_models_glm.log#L14187) |
| 09/17 08:14:01 | `main/glm47flash/di__binf__otrc` | [followup_agent_models_glm.log:14952](../logs/followup_agent_models_glm.log#L14952) |

### GLM ABL-25 ablation: 09/20 00:00:06 → 09/23 10:31:24

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/20 00:00:06 | `ablation/glm47flash/d03__bA__tr` | [followup_agent_models_glm.log:16083](../logs/followup_agent_models_glm.log#L16083) |
| 09/20 01:12:28 | `ablation/glm47flash/d03__bA__su-full` | [followup_agent_models_glm.log:16342](../logs/followup_agent_models_glm.log#L16342) |
| 09/20 03:07:04 | `ablation/glm47flash/d03__bA__su-partial` | [followup_agent_models_glm.log:16644](../logs/followup_agent_models_glm.log#L16644) |
| 09/20 04:50:49 | `ablation/glm47flash/d03__bA__ss` | [followup_agent_models_glm.log:16940](../logs/followup_agent_models_glm.log#L16940) |
| 09/20 06:37:37 | `ablation/glm47flash/d03__bA__ss-partial` | [followup_agent_models_glm.log:17243](../logs/followup_agent_models_glm.log#L17243) |
| 09/20 08:24:22 | `ablation/glm47flash/d03__bP__tr` | [followup_agent_models_glm.log:17532](../logs/followup_agent_models_glm.log#L17532) |
| 09/20 09:37:05 | `ablation/glm47flash/d03__bP__su-full` | [followup_agent_models_glm.log:17827](../logs/followup_agent_models_glm.log#L17827) |
| 09/20 11:25:13 | `ablation/glm47flash/d03__bP__su-partial` | [followup_agent_models_glm.log:18136](../logs/followup_agent_models_glm.log#L18136) |
| 09/20 13:05:28 | `ablation/glm47flash/d03__bP__ss` | [followup_agent_models_glm.log:18443](../logs/followup_agent_models_glm.log#L18443) |
| 09/20 14:52:11 | `ablation/glm47flash/d03__bP__ss-partial` | [followup_agent_models_glm.log:18748](../logs/followup_agent_models_glm.log#L18748) |
| 09/20 16:32:34 | `ablation/glm47flash/d03__bB__tr` | [followup_agent_models_glm.log:19053](../logs/followup_agent_models_glm.log#L19053) |
| 09/20 17:52:02 | `ablation/glm47flash/d03__bB__su-full` | [followup_agent_models_glm.log:19359](../logs/followup_agent_models_glm.log#L19359) |
| 09/20 19:29:27 | `ablation/glm47flash/d03__bB__su-partial` | [followup_agent_models_glm.log:19659](../logs/followup_agent_models_glm.log#L19659) |
| 09/20 21:08:21 | `ablation/glm47flash/d03__bB__ss` | [followup_agent_models_glm.log:19968](../logs/followup_agent_models_glm.log#L19968) |
| 09/20 22:56:01 | `ablation/glm47flash/d03__bB__ss-partial` | [followup_agent_models_glm.log:20268](../logs/followup_agent_models_glm.log#L20268) |
| 09/21 00:29:51 | `ablation/glm47flash/d07__bA__tr` | [followup_agent_models_glm.log:20579](../logs/followup_agent_models_glm.log#L20579) |
| 09/21 01:45:20 | `ablation/glm47flash/d07__bA__su-full` | [followup_agent_models_glm.log:20875](../logs/followup_agent_models_glm.log#L20875) |
| 09/21 03:29:09 | `ablation/glm47flash/d07__bA__su-partial` | [followup_agent_models_glm.log:21176](../logs/followup_agent_models_glm.log#L21176) |
| 09/21 05:06:37 | `ablation/glm47flash/d07__bA__ss` | [followup_agent_models_glm.log:21478](../logs/followup_agent_models_glm.log#L21478) |
| 09/21 07:01:05 | `ablation/glm47flash/d07__bA__ss-partial` | [followup_agent_models_glm.log:21769](../logs/followup_agent_models_glm.log#L21769) |
| 09/21 08:42:45 | `ablation/glm47flash/d07__bP__tr` | [followup_agent_models_glm.log:22070](../logs/followup_agent_models_glm.log#L22070) |
| 09/21 10:05:10 | `ablation/glm47flash/d07__bP__su-full` | [followup_agent_models_glm.log:22379](../logs/followup_agent_models_glm.log#L22379) |
| 09/21 11:54:37 | `ablation/glm47flash/d07__bP__su-partial` | [followup_agent_models_glm.log:22679](../logs/followup_agent_models_glm.log#L22679) |
| 09/21 13:31:51 | `ablation/glm47flash/d07__bP__ss` | [followup_agent_models_glm.log:22983](../logs/followup_agent_models_glm.log#L22983) |
| 09/21 15:17:31 | `ablation/glm47flash/d07__bP__ss-partial` | [followup_agent_models_glm.log:23288](../logs/followup_agent_models_glm.log#L23288) |
| 09/21 17:00:41 | `ablation/glm47flash/d07__bB__tr` | [followup_agent_models_glm.log:23600](../logs/followup_agent_models_glm.log#L23600) |
| 09/21 18:19:19 | `ablation/glm47flash/d07__bB__su-full` | [followup_agent_models_glm.log:23906](../logs/followup_agent_models_glm.log#L23906) |
| 09/21 20:08:13 | `ablation/glm47flash/d07__bB__su-partial` | [followup_agent_models_glm.log:24216](../logs/followup_agent_models_glm.log#L24216) |
| 09/21 21:48:55 | `ablation/glm47flash/d07__bB__ss` | [followup_agent_models_glm.log:24529](../logs/followup_agent_models_glm.log#L24529) |
| 09/21 23:29:27 | `ablation/glm47flash/d07__bB__ss-partial` | [followup_agent_models_glm.log:24830](../logs/followup_agent_models_glm.log#L24830) |
| 09/22 01:10:22 | `ablation/glm47flash/d05__bA__tr` | [followup_agent_models_glm.log:25143](../logs/followup_agent_models_glm.log#L25143) |
| 09/22 02:24:33 | `ablation/glm47flash/d05__bA__su-full` | [followup_agent_models_glm.log:25434](../logs/followup_agent_models_glm.log#L25434) |
| 09/22 04:15:39 | `ablation/glm47flash/d05__bA__su-partial` | [followup_agent_models_glm.log:25727](../logs/followup_agent_models_glm.log#L25727) |
| 09/22 06:01:08 | `ablation/glm47flash/d05__bA__ss` | [followup_agent_models_glm.log:26028](../logs/followup_agent_models_glm.log#L26028) |
| 09/22 07:50:06 | `ablation/glm47flash/d05__bA__ss-partial` | [followup_agent_models_glm.log:26324](../logs/followup_agent_models_glm.log#L26324) |
| 09/22 09:30:56 | `ablation/glm47flash/di__bA__trc` | [followup_agent_models_glm.log:26623](../logs/followup_agent_models_glm.log#L26623) |
| 09/22 10:52:08 | `ablation/glm47flash/di__bA__trc-su` | [followup_agent_models_glm.log:26920](../logs/followup_agent_models_glm.log#L26920) |
| 09/22 12:19:42 | `ablation/glm47flash/di__bA__trc-ss` | [followup_agent_models_glm.log:27235](../logs/followup_agent_models_glm.log#L27235) |
| 09/22 13:55:54 | `ablation/glm47flash/di__bA__otrc-tr` | [followup_agent_models_glm.log:27541](../logs/followup_agent_models_glm.log#L27541) |
| 09/22 15:14:10 | `ablation/glm47flash/di__bA__otrc-su-partial` | [followup_agent_models_glm.log:27827](../logs/followup_agent_models_glm.log#L27827) |
| 09/22 16:42:10 | `ablation/glm47flash/di__bA__otrc-ss-partial` | [followup_agent_models_glm.log:28101](../logs/followup_agent_models_glm.log#L28101) |
| 09/22 18:08:32 | `ablation/glm47flash/d05__bB__tr` | [followup_agent_models_glm.log:28379](../logs/followup_agent_models_glm.log#L28379) |
| 09/22 19:29:02 | `ablation/glm47flash/d05__bB__su-full` | [followup_agent_models_glm.log:28680](../logs/followup_agent_models_glm.log#L28680) |
| 09/22 21:10:32 | `ablation/glm47flash/d05__bB__su-partial` | [followup_agent_models_glm.log:28994](../logs/followup_agent_models_glm.log#L28994) |
| 09/22 22:41:55 | `ablation/glm47flash/d05__bB__ss` | [followup_agent_models_glm.log:29309](../logs/followup_agent_models_glm.log#L29309) |
| 09/23 00:22:52 | `ablation/glm47flash/d05__bB__ss-partial` | [followup_agent_models_glm.log:29611](../logs/followup_agent_models_glm.log#L29611) |
| 09/23 01:54:24 | `ablation/glm47flash/di__bB__trc` | [followup_agent_models_glm.log:29913](../logs/followup_agent_models_glm.log#L29913) |
| 09/23 03:18:10 | `ablation/glm47flash/di__bB__trc-su` | [followup_agent_models_glm.log:30228](../logs/followup_agent_models_glm.log#L30228) |
| 09/23 04:42:31 | `ablation/glm47flash/di__bB__trc-ss` | [followup_agent_models_glm.log:30538](../logs/followup_agent_models_glm.log#L30538) |
| 09/23 06:09:47 | `ablation/glm47flash/di__bB__otrc-tr` | [followup_agent_models_glm.log:30854](../logs/followup_agent_models_glm.log#L30854) |
| 09/23 07:32:36 | `ablation/glm47flash/di__bB__otrc-su-partial` | [followup_agent_models_glm.log:31159](../logs/followup_agent_models_glm.log#L31159) |
| 09/23 09:03:50 | `ablation/glm47flash/di__bB__otrc-ss-partial` | [followup_agent_models_glm.log:31455](../logs/followup_agent_models_glm.log#L31455) |

### Summarizer and prefix-cache ablations (own launcher logs)

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/17 14:38:11 | `model_ablation/qwen35b-sum-qwen35-9b-smoke/d05__b15k__su-full` (1 task, smoke) | [followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log:3](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log#L3) |
| 09/17 15:37:24 | `model_ablation/qwen35b-sum-qwen35-9b/d05__b15k__su-full` | [followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:3](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L3) |
| 09/17 17:35:53 | `model_ablation/qwen35b-sum-qwen35-9b/di__b15k__trc-su` | [followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:297](../logs/followup_sb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L297) |
| 09/18 10:31:14 | `model_ablation/qwen35b-sum-gemma4-12b/d05__b15k__su-full` | [followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:3](../logs/followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L3) |
| 09/18 12:27:40 | `model_ablation/qwen35b-sum-gemma4-12b/di__b15k__trc-su` | [followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:292](../logs/followup_sb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L292) |
| 09/18 14:35:36 | `prefix_cache_ablation/qwen35b-prefixcache-smoke/d05__b15k__su-full` (1 task, smoke) | [followup_sb_qwen_qwen35b-prefixcache-smoke.log:4](../logs/followup_sb_qwen_qwen35b-prefixcache-smoke.log#L4) |
| 09/18 14:37:23 | `prefix_cache_ablation/qwen35b-prefixcache/d05__b15k__tr` (hit 90.4%) | [followup_sb_qwen_qwen35b-prefixcache.log:4](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L4) |
| 09/18 15:36:43 | `prefix_cache_ablation/qwen35b-prefixcache/d05__b15k__su-full` (85.8%) | [followup_sb_qwen_qwen35b-prefixcache.log:289](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L289) |
| 09/18 16:40:01 | `prefix_cache_ablation/qwen35b-prefixcache/d05__b15k__su-partial` (87.0%) | [followup_sb_qwen_qwen35b-prefixcache.log:577](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L577) |
| 09/18 17:40:39 | `prefix_cache_ablation/qwen35b-prefixcache/d05__b15k__ss` (86.6%) | [followup_sb_qwen_qwen35b-prefixcache.log:888](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L888) |
| 09/18 18:45:31 | `prefix_cache_ablation/qwen35b-prefixcache/d05__b15k__ss-partial` (87.3%) | [followup_sb_qwen_qwen35b-prefixcache.log:1187](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L1187) |
| 09/18 19:48:08 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__trc` (91.0%) | [followup_sb_qwen_qwen35b-prefixcache.log:1494](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L1494) |
| 09/18 20:49:00 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__trc-su` (89.7%) | [followup_sb_qwen_qwen35b-prefixcache.log:1820](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L1820) |
| 09/18 21:56:51 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__trc-ss` (89.3%) | [followup_sb_qwen_qwen35b-prefixcache.log:2132](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L2132) |
| 09/18 23:02:05 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__otrc-tr` (66.9%) | [followup_sb_qwen_qwen35b-prefixcache.log:2442](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L2442) |
| 09/19 00:10:32 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__otrc-su-partial` (65.6%) | [followup_sb_qwen_qwen35b-prefixcache.log:2755](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L2755) |
| 09/19 01:15:34 | `prefix_cache_ablation/qwen35b-prefixcache/di__b15k__otrc-ss-partial` (63.3%) | [followup_sb_qwen_qwen35b-prefixcache.log:3055](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3055) |
| 09/19 19:36:08 | `prefix_cache_ablation/qwen35b-prefixcache/di__binf__fc` (96.3%) | [followup_sb_qwen_qwen35b-prefixcache.log:3358](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3358) |
| 09/19 20:49:42 | `prefix_cache_ablation/qwen35b-prefixcache/di__binf__otrc` (69.8%) | [followup_sb_qwen_qwen35b-prefixcache.log:3680](../logs/followup_sb_qwen_qwen35b-prefixcache.log#L3680) |

## Archives and re-evaluations, September 8–24

Evaluation-only operations and archive moves change the canonical indexes without producing new agent trials. They are listed here so that index mtimes and record counts can be matched to an operation.

| When (CDT) | Operation | Effect on `ICLR_results/swebench` | Record |
|---|---|---|---|
| 09/08 16:20:42–16:20:59 | Archive of the remaining summary-bug rerun targets | 6,963 runs moved, 6,952 index rows removed across 98 cells; together with the 09/07 marker archive every row of the 9,322-row rerun list is out of the indexes | [status.json](../archives/swebench_summary_bug_remaining_20260908_162042_CDT/status.json) |
| 09/10 (before 16:47) | Devstral FC∞ run_2/run_3 archive | 200 index rows removed from `main/devstral24b/di__binf__fc`, 100 (run_1) remain; 677 paths moved | [status.json](../archives/devstral_fc_r23_before_rerun_20260910/status.json) |
| 09/10 22:26 → 09/11 11:05 (apply after) | Devstral main re-evaluation, 269 candidates | 174 True / 94 False written with `--allow-partial`; 1 unverified left as is | [manifest.json](../archives/reeval_devstral_main_20260910/manifest.json), [results.json](../archives/reeval_devstral_main_20260910/results.json) |
| 09/11 11:14 → 12:24 | Qwen main re-evaluation, 150 candidates | 84 True / 66 False written | [results.json](../archives/reeval_qwen35b_main_20260911/results.json) |
| 09/11 15:05 → 15:36 | GLM main re-evaluation, 37 candidates | 22 True / 14 False written; 1 unverified | [results.json](../archives/reeval_glm47flash_main_20260911/results.json) |
| 09/11 17:16 | Qwen seeded-ablation-copy archive | 476 runs and 476 index rows removed from `ablation/qwen35b` | [status.json](../archives/swebench_summary_bug_ablation_seeded_20260911_171617_374762025/status.json) |
| 09/23 11:32 → 13:42; applied 09/24 by 15:57 | Qwen main review-253 re-evaluation | 165 True / 88 False; all 35 `main/qwen35b` indexes rewritten on apply; pre-apply copies in `archive/swebench_main_qwen35b_pre_reeval_20260924/` | [results.json](ICLR_reeval/qwen35b_main_review253_20260923/results.json) |
| 09/24 15:14 → 16:27; applied by 16:31 | Qwen ABL-25 155-run re-evaluation | 155 False, no flips; pre-apply copies in `archive/swebench_ablation_qwen35b_pre_reeval_20260924/` | [results.json](ICLR_reeval/qwen35b_ablation_abl25_155_20260924/results.json) |

One-off manual index edit found in shell history (date not recorded, between the 09/06 stale-container cleanup and the 09/10 GLM launch): `ablation/devstral24b/di__b24k__otrc-ss-partial` row `sympy__sympy-19637__otrc-ss-partial__r3` was set from `resolved=null` to `False` with `eval_note='harness timeout 600s; patch removes i=j+2 in kernS while-loop -> infinite loop in test_sympify'`, after a backup to `experiment_results.json.bak-19637`. This is a hand-written verdict, not a harness verdict.

## September 27 inspection snapshot

At **14:42 CDT** the process table held no `run_agent_models_expansion`, `run_experiment_iclr.py`, `reevaluate_swebench_candidates.py`, `run_qwen_swe_*_ablation` or r2 runner process. Running were the Qwen3.5-35B-A3B vLLM server started at 02:41:12 from the other checkout (`/home/ak58925/adaptive-context-management/agentCtx/venv`, PID 2052914, port 8000, about 74 GB on each of the four GPUs) and the rootless Podman API service (PID 4142791). The r2 chain finished at 09:45:39; its lock files (`r2_p30s_chain.lock`, `r2_sb_p30s_qwen35b.lock`) remain under that checkout's `logs/experiments/` without a live process. The dashboard cron (`0,30 * * * * /home/ak58925/ICLR27/agentCtx/dashboard/publish_cron.sh`) is active and last committed to the `agentCtx-data` worktree at 14:30. The PID files under `logs/` (`followup_agent_models_{qwen,devstral,glm}_launcher.pid`, `reeval_*.pid`, `vllm_*.pid`) all belong to finished processes and are stale.

Two other checkouts exist on this machine and appear in the shell history: `~/organized/agentCtx` (branch `akiho-dev`, HEAD `51605c4`, used for the `akiho-clean-*` reorganization branches and the 09/26 `chore: chose 30 subset tasks for swe` commit) and `~/adaptive-context-management/agentCtx` (the r2 campaign above). Neither writes to `~/ICLR27/agentCtx/ICLR_results/`.

## Limits on timestamps and completion claims (continuation)

- The bash history covers about 2,000 lines from the 08/31 Devstral launch onward, with commands from several shells and tmux sessions interleaved and undated. Where a command has no matching log banner (server restarts, `pkill` sequences, `rsync`, the one-off index edit), the row says so and gives the nearest bounding timestamps instead of a start time.
- Launcher stops are never logged by the launcher itself. A stop time is given as an interval between the last cell banner and the next dated event; the 09/13 Devstral stop, the 09/10 GLM stop and the 09/08 Qwen stop are all of this kind.
- The `SLACK_WEBHOOK_URL is not configured` notice appears at both 09/08 Qwen launch lines, so the launcher log alone does not show which launch had a working webhook. The 16:48:02 launch ran to the 09/09 completion banner either way.
- Launcher completion banners (`sections run: main`, `complete: sections=ablation`) describe traversal, not verdict quality. Re-evaluations on 09/10–11 and 09/23–24 rewrote verdicts after some of these banners; the index mtimes, not the banners, date the current verdicts.
- The GLM launcher log was truncated by the mistaken 09/14 20:52 launch. Its 09/06 and 09/10 history is only in `followup_agent_models_glm.log`, which both attempts appended to.
- The r2 chain of 09/27 evaluated with harness errors on most records (`resolved=null` for 77–85 of 90 per cell). Those counts are reported as found; nothing was retried or fixed while compiling this document. No experiments were launched, resumed, stopped or modified during the 09/27 inspection either.
- Terminal-Bench cells on Albus, the Albus launch commands and the `logs/followup_tb_*` files are outside this host and are not reconstructed here.
