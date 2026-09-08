# SWE-bench experiment command history: 2026-08-23–2026-09-07

Compiled by cross-checking local `.bash_history`, execution logs, Git history, calibration artifacts, and archive records in the `akiho-expansion` workspace. All times are **CDT (UTC−5)**. Inspection snapshot: **2026-09-07 20:41 CDT**. The detailed local log history starts with the August 23 run_3 expansion; earlier experiments in `Active_runs.md` are background and are not reconstructed here.

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
