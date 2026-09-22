# Experiment command history: 2026-08-30–2026-09-05

Compiled by cross-checking `.bash_history`, execution logs, and existing experiment records in this workspace. All times are **CDT (UTC−5)**. Since shell history has no timestamps, times generally refer to stage starts recorded in logs, not when commands were entered. August 29 entries provide background.

Commands are excerpts from historical experiment launches, retaining relevant settings. Many entries omit `nohup`, `setsid`, redirection, and shared Podman environment variables. Resumes, skips, and preprocessing are included but distinguished from new trials. No new experiments were run while compiling this document.

## Launch chronology

| Start (CDT) | Experiment or operation | Launch command (excerpt) | Progress and outcome | Source log |
|---|---|---|---|---|
| 08/29 16:10 (background) | TB1 prebuild / single UID | `bash scripts/tb_harbor_prebuild_images.sh` | 42 succeeded, 38 failed. The remaining images were rebuilt on August 30. | [tb1_harbor_prebuild.log:114467](../logs/tb1_harbor_prebuild.log#L114467) |
| 08/29 18:03 (background) | Qwen / TB1 42 tasks / FC run 2–5 | `bash scripts/run_terminalbench_rootless_fc_expansion.sh qwen` | 42 × 5 including run 1. The log extends through August 29 at 21:19. | [qwen_rootless_fc_runs2-5_launcher.log:2](../logs/qwen_rootless_fc_runs2-5_launcher.log#L2) |
| 08/30 03:44:28 | Devstral / TB1 42 tasks / FC run 1 | `bash scripts/run_budget_calibration_tb.sh devstral-rootless` | DONE at 04:33:24. | [devstral24b_tb1_fc_run1.log:1](../logs/devstral24b_tb1_fc_run1.log#L1) |
| 08/30 04:33:25 | Devstral / TB1 42 tasks / FC run 2–5 | `bash scripts/run_terminalbench_rootless_fc_expansion.sh devstral` | Run 3 at 05:19, run 4 at 06:04, run 5 at 06:46. | [devstral24b_tb1_p80_rootless_fc_runs2-5.log:1](../logs/devstral24b_tb1_p80_rootless_fc_runs2-5.log#L1) |
| 08/30 11:52:56 | GLM / TB1 42 tasks / FC run 1 | `bash scripts/run_budget_calibration_tb.sh glm-rootless` | DONE at 12:50:23. | [glm47flash_tb1_fc_run1.log:1](../logs/glm47flash_tb1_fc_run1.log#L1) |
| 08/30 12:50:24 | GLM / TB1 42 tasks / FC run 2–5 | `bash scripts/run_terminalbench_rootless_fc_expansion.sh glm` | Reached run 3 at 13:57; later resumed through another launcher. | [glm47flash_tb1_p80_rootless_fc_runs2-5.log:1](../logs/glm47flash_tb1_p80_rootless_fc_runs2-5.log#L1) |
| 08/30 16:09:26 | GLM FC runs 3–5 resume | `START_RUN=3 END_RUN=5 bash scripts/run_terminalbench_rootless_fc_expansion.sh glm` | Run 3 advanced to the next stage in about 5 seconds. Run 4 at 16:09:31, run 5 at 17:09:22. Do not count all entries as newly executed trials. | [glm47flash_tb1_p80_rootless_fc_runs3-5.log:1](../logs/glm47flash_tb1_p80_rootless_fc_runs3-5.log#L1) |
| 08/30 19:25:49 | TB1 prebuild smoke (after subuid setup) | `bash scripts/tb_harbor_prebuild_images.sh write-compressor` | 1 succeeded, 0 failed at 19:26:14. Prerequisites: uidmap installation, subuid/subgid configuration, and podman system migrate. | [tb1_harbor_prebuild.log:114470](../logs/tb1_harbor_prebuild.log#L114470) |
| 08/30 19:26:52 | TB1 full prebuild resume | `nohup setsid bash scripts/tb_harbor_prebuild_images.sh > logs/tb1_harbor_prebuild_driver.log 2>&1 < /dev/null &` | 80 succeeded, 0 failed at 19:57:44. Existing images were reused. | [tb1_harbor_prebuild_driver.log:1](../logs/tb1_harbor_prebuild_driver.log#L1) |
| 08/30 20:22:27 | Qwen / TB1 remaining 38 tasks / FC run 1 | `N_CONCURRENT=4 bash scripts/run_budget_calibration_tb.sh qwen-subuid` | Together with the 42-task subset, this covers the 80-task calibration. | [qwen35b_tb_p80_subuid_required_launcher.log:1](../logs/qwen35b_tb_p80_subuid_required_launcher.log#L1) |
| 08/30 23:05:31 | Devstral / TB1 remaining 38 tasks / FC run 1 | `N_CONCURRENT=4 bash scripts/run_budget_calibration_tb.sh devstral-subuid` | DONE at 23:54:31. | [devstral24b_tb_p80_subuid_required_launcher.log:2](../logs/devstral24b_tb_p80_subuid_required_launcher.log#L2) |
| 08/31 00:25:01 | GLM / TB1 remaining 38 tasks / FC run 1 | `N_CONCURRENT=4 bash scripts/run_budget_calibration_tb.sh glm-subuid` | DONE at 01:33:42. | [glm47flash_tb_p80_subuid_required_launcher.log:2](../logs/glm47flash_tb_p80_subuid_required_launcher.log#L2) |
| 08/31 02:53:55 | Qwen / TB1 P-80 / budget 27K | `QWEN_P_BUDGET=27000 N_CONCURRENT=4 bash scripts/run_agent_models_expansion_tb.sh qwen` | Started with TR; later changed to 3K. This does not indicate completion of the full Main grid. | [run_agent_models_expansion_tb_qwen.nohup.log:1](../logs/run_agent_models_expansion_tb_qwen.nohup.log#L1) |
| 08/31 09:53:32 | Qwen / TB1 P-80 / budget 3K | `QWEN_P_BUDGET=3000 N_CONCURRENT=4 bash scripts/run_agent_models_expansion_tb.sh qwen` | Started with TR, reached SU-full at 18:13:46, then switched to P-40. | [run_agent_models_expansion_tb_qwen_b3k.nohup.log:1](../logs/run_agent_models_expansion_tb_qwen_b3k.nohup.log#L1) |
| 08/31 18:21:08 | Original GLM launcher reaches runs 4/5 again | `bash scripts/run_terminalbench_rootless_fc_expansion.sh glm (within the existing launcher)` | Continuation of the August 30 launch log. The stages advance quickly, so this is not counted as 42 × 2 new trials. | [glm47flash_tb1_p80_rootless_fc_runs2-5.log:210](../logs/glm47flash_tb1_p80_rootless_fc_runs2-5.log#L210) |
| 08/31 18:26:18 | Qwen / TB1 Main P-40 / budget 3K | `bash scripts/run_agent_models_expansion_tb.sh qwen main` | Passed TR immediately and proceeded to SU-full and subsequent cells. Primitives ran sequentially on September 1–3. | [followup_tb_qwen.log:1](../logs/followup_tb_qwen.log#L1) |
| 09/03 12:48:48 | Qwen Main resume → ablation | `N_CONCURRENT=4 bash scripts/run_qwen_tb_with_slack.sh` | The wrapper invokes qwen both. Main complete at 14:32:50 (1,560 planned runs); P-15 ablation started at the same time. | [followup_tb_qwen.log:7542](../logs/followup_tb_qwen.log#L7542) |
| 09/03 22:56:29 | Devstral / TB1 Main P-40 / budget 4K | `N_CONCURRENT=4 setsid bash scripts/run_agent_models_expansion_tb.sh devstral main` | Overlaps with Qwen ablation. Shell history records the Devstral server starting on GPUs 4,5,6,7. | [followup_tb_devstral.log:1](../logs/followup_tb_devstral.log#L1) |
| 09/04 10:42:45 | TB2 prebuild smoke | `TB2_HARBOR_SOURCE_DATASET="$PWD/data/terminal-bench-2-source" bash scripts/tb2_harbor_prebuild_images.sh adaptive-rejection-sampler` | 1 succeeded at 10:42:51. | [tb2_harbor_prebuild.log:1](../logs/tb2_harbor_prebuild.log#L1) |
| 09/04 10:43:24 | TB2 full prebuild | `TB2_HARBOR_SOURCE_DATASET="$PWD/data/terminal-bench-2-source" bash scripts/tb2_harbor_prebuild_images.sh` | 89 succeeded at 11:36:57. The failed (1): .git entry refers to a non-task directory. | [tb2_harbor_prebuild_launcher.log:3](../logs/tb2_harbor_prebuild_launcher.log#L3) |
| 09/04 13:33:38 | Qwen / TB2 89 tasks / FC run 1 | `AGENT_TIMEOUT_MULTIPLIER=2.0 bash scripts/run_budget_calibration_tb2.sh qwen` | Repeated BadRequestError due to the context-length limit. Remaining tasks were later resumed with timeout multiplier 1.0. | [tb2_qwen35b_fc_run1.nohup.log:2](../logs/tb2_qwen35b_fc_run1.nohup.log#L2) |
| 09/04 14:57:03 | Qwen / TB2 remaining 65 tasks / FC run 1 resume | `AGENT_TIMEOUT_MULTIPLIER=1.0 TB2_JOB_NAME=tb2-qwen35b-fc-run1-resume-1x bash scripts/run_budget_calibration_tb2.sh qwen task_lists/tbench2_qwen_fc_run1_remaining.json` | The same launch command appears twice in history. The log ends with an aggregation error: 129 trial results / expected 65. | [tb2_qwen35b_fc_run1_resume_1x.nohup.log:2](../logs/tb2_qwen35b_fc_run1_resume_1x.nohup.log#L2) |
| 09/04 18:53:19 | Qwen / TB2 caffe-cifar-10 single-task retry | `N_CONCURRENT=1 AGENT_TIMEOUT_MULTIPLIER=1.0 TB2_JOB_NAME="tb2-qwen35b-fc-run1-caffe-retry-$(date +%Y%m%d-%H%M%S)" bash scripts/run_budget_calibration_tb2.sh qwen task_lists/tbench2_caffe_retry.json` | 1 trial executed, Mean 0. Aggregation failed due to a task-scope mismatch. | [tb2_caffe_retry.nohup.log:2](../logs/tb2_caffe_retry.nohup.log#L2) |
| 09/04 20:14:24 | GLM / TB1 Main P-40 / budget 3K | `N_CONCURRENT=4 bash scripts/run_glm_tb_main_with_slack.sh` | Invokes glm main. TR → SU-full → SU-partial on September 5 at 05:17. | [followup_tb_glm.log:1](../logs/followup_tb_glm.log#L1) |
| 09/05 10:26:25 | Devstral Main recovery and resume | `PYTHONUNBUFFERED=1 TB_REAP_FINISHED_HARBOR=1 N_CONCURRENT=4 bash scripts/run_agent_models_expansion_tb.sh devstral main` | Skipped existing cells and reached the TRC+SS run 2 batch. | [followup_tb_devstral_resume_20260905_102625.log:1](../logs/followup_tb_devstral_resume_20260905_102625.log#L1) |
| 09/05 14:56:30 | Devstral Main resume | `N_CONCURRENT=4 bash scripts/run_agent_models_expansion_tb.sh devstral main` | Skipped existing cells and reached TRC+SS. Full Main completion was not confirmed in the logs. | [followup_tb_devstral_main.nohup.log:2](../logs/followup_tb_devstral_main.nohup.log#L2) |
| 09/05 14:57:12 | GLM Main resume | `bash scripts/run_glm_tb_main_with_slack.sh` | The log passes existing TR/SU-full cells and reaches SU-partial. Full Main completion was not confirmed in the logs. | [followup_tb_glm_main.nohup.log:2](../logs/followup_tb_glm_main.nohup.log#L2) |

## Cell transitions within each launch

The table below lists all cell-start entries extracted from the Main and ablation logs in chronological order. During resumes, cells that advance within seconds may skip existing results; a start entry alone does not establish new execution or completion. In cell names, `b3k` means a budget of 3,000, `d05` means depth 0.5, `di` means depth-invariant, and `binf` means an unlimited compression budget.

| Start (CDT) | Cell | Source |
|---|---|---|
| 08/31 18:26:18 | `main/qwen35b/d05__b3k__tr` | [followup_tb_qwen.log:2](../logs/followup_tb_qwen.log#L2) |
| 08/31 18:26:19 | `main/qwen35b/d05__b3k__su-full` | [followup_tb_qwen.log:16](../logs/followup_tb_qwen.log#L16) |
| 09/01 00:32:56 | `main/qwen35b/d05__b3k__su-partial` | [followup_tb_qwen.log:922](../logs/followup_tb_qwen.log#L922) |
| 09/01 08:58:14 | `main/qwen35b/d05__b3k__ss` | [followup_tb_qwen.log:1881](../logs/followup_tb_qwen.log#L1881) |
| 09/01 14:40:32 | `main/qwen35b/d05__b3k__ss-partial` | [followup_tb_qwen.log:2696](../logs/followup_tb_qwen.log#L2696) |
| 09/02 01:21:22 | `main/qwen35b/di__b3k__trc` | [followup_tb_qwen.log:3655](../logs/followup_tb_qwen.log#L3655) |
| 09/02 03:24:16 | `main/qwen35b/di__b3k__trc-su` | [followup_tb_qwen.log:3780](../logs/followup_tb_qwen.log#L3780) |
| 09/02 09:13:08 | `main/qwen35b/di__b3k__trc-ss` | [followup_tb_qwen.log:4559](../logs/followup_tb_qwen.log#L4559) |
| 09/02 14:33:01 | `main/qwen35b/di__b3k__otrc-tr` | [followup_tb_qwen.log:5348](../logs/followup_tb_qwen.log#L5348) |
| 09/02 16:55:20 | `main/qwen35b/di__b3k__otrc-su-partial` | [followup_tb_qwen.log:5474](../logs/followup_tb_qwen.log#L5474) |
| 09/02 22:53:41 | `main/qwen35b/di__b3k__otrc-ss-partial` | [followup_tb_qwen.log:6343](../logs/followup_tb_qwen.log#L6343) |
| 09/03 04:32:06 | `main/qwen35b/di__binf__fc` | [followup_tb_qwen.log:7230](../logs/followup_tb_qwen.log#L7230) |
| 09/03 06:46:37 | `main/qwen35b/di__binf__otrc` | [followup_tb_qwen.log:7503](../logs/followup_tb_qwen.log#L7503) |
| 09/03 12:48:48 | `main/qwen35b/d05__b3k__tr` | [followup_tb_qwen.log:7543](../logs/followup_tb_qwen.log#L7543) |
| 09/03 12:48:49 | `main/qwen35b/d05__b3k__su-full` | [followup_tb_qwen.log:7557](../logs/followup_tb_qwen.log#L7557) |
| 09/03 12:48:50 | `main/qwen35b/d05__b3k__su-partial` | [followup_tb_qwen.log:7571](../logs/followup_tb_qwen.log#L7571) |
| 09/03 12:48:51 | `main/qwen35b/d05__b3k__ss` | [followup_tb_qwen.log:7585](../logs/followup_tb_qwen.log#L7585) |
| 09/03 12:48:51 | `main/qwen35b/d05__b3k__ss-partial` | [followup_tb_qwen.log:7599](../logs/followup_tb_qwen.log#L7599) |
| 09/03 12:48:52 | `main/qwen35b/di__b3k__trc` | [followup_tb_qwen.log:7613](../logs/followup_tb_qwen.log#L7613) |
| 09/03 12:48:53 | `main/qwen35b/di__b3k__trc-su` | [followup_tb_qwen.log:7627](../logs/followup_tb_qwen.log#L7627) |
| 09/03 12:48:54 | `main/qwen35b/di__b3k__otrc-tr` | [followup_tb_qwen.log:7655](../logs/followup_tb_qwen.log#L7655) |
| 09/03 12:48:54 | `main/qwen35b/di__b3k__trc-ss` | [followup_tb_qwen.log:7641](../logs/followup_tb_qwen.log#L7641) |
| 09/03 12:48:55 | `main/qwen35b/di__b3k__otrc-su-partial` | [followup_tb_qwen.log:7669](../logs/followup_tb_qwen.log#L7669) |
| 09/03 12:48:56 | `main/qwen35b/di__b3k__otrc-ss-partial` | [followup_tb_qwen.log:7683](../logs/followup_tb_qwen.log#L7683) |
| 09/03 12:48:57 | `main/qwen35b/di__binf__fc` | [followup_tb_qwen.log:7697](../logs/followup_tb_qwen.log#L7697) |
| 09/03 12:48:57 | `main/qwen35b/di__binf__otrc` | [followup_tb_qwen.log:7711](../logs/followup_tb_qwen.log#L7711) |
| 09/03 14:32:50 | `ablation/qwen35b/d05__b2k__tr` | [followup_tb_qwen.log:7802](../logs/followup_tb_qwen.log#L7802) |
| 09/03 15:23:05 | `ablation/qwen35b/d05__b2k__su-full` | [followup_tb_qwen.log:7927](../logs/followup_tb_qwen.log#L7927) |
| 09/03 18:11:06 | `ablation/qwen35b/d05__b2k__su-partial` | [followup_tb_qwen.log:8463](../logs/followup_tb_qwen.log#L8463) |
| 09/03 20:57:42 | `ablation/qwen35b/d05__b2k__ss` | [followup_tb_qwen.log:8993](../logs/followup_tb_qwen.log#L8993) |
| 09/03 22:56:29 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:2](../logs/followup_tb_devstral.log#L2) |
| 09/03 23:40:30 | `ablation/qwen35b/d05__b2k__ss-partial` | [followup_tb_qwen.log:9493](../logs/followup_tb_qwen.log#L9493) |
| 09/04 01:07:51 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:118](../logs/followup_tb_devstral.log#L118) |
| 09/04 02:21:14 | `ablation/qwen35b/d05__b4k__tr` | [followup_tb_qwen.log:10020](../logs/followup_tb_qwen.log#L10020) |
| 09/04 03:20:54 | `ablation/qwen35b/d05__b4k__su-full` | [followup_tb_qwen.log:10145](../logs/followup_tb_qwen.log#L10145) |
| 09/04 04:38:09 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:284](../logs/followup_tb_devstral.log#L284) |
| 09/04 05:40:54 | `ablation/qwen35b/d05__b4k__su-partial` | [followup_tb_qwen.log:10529](../logs/followup_tb_qwen.log#L10529) |
| 09/04 08:01:53 | `ablation/qwen35b/d05__b4k__ss` | [followup_tb_qwen.log:10940](../logs/followup_tb_qwen.log#L10940) |
| 09/04 09:31:02 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:645](../logs/followup_tb_devstral.log#L645) |
| 09/04 10:18:11 | `ablation/qwen35b/d05__b4k__ss-partial` | [followup_tb_qwen.log:11296](../logs/followup_tb_qwen.log#L11296) |
| 09/04 17:04:26 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:2339](../logs/followup_tb_devstral.log#L2339) |
| 09/04 20:14:24 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:2](../logs/followup_tb_glm.log#L2) |
| 09/04 23:01:13 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:3446](../logs/followup_tb_devstral.log#L3446) |
| 09/04 23:01:55 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:133](../logs/followup_tb_glm.log#L133) |
| 09/05 01:15:00 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:3576](../logs/followup_tb_devstral.log#L3576) |
| 09/05 05:04:02 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:3724](../logs/followup_tb_devstral.log#L3724) |
| 09/05 05:17:40 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:939](../logs/followup_tb_glm.log#L939) |
| 09/05 10:26:25 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:3980](../logs/followup_tb_devstral.log#L3980) |
| 09/05 10:26:26 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:3994](../logs/followup_tb_devstral.log#L3994) |
| 09/05 10:26:26 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:4008](../logs/followup_tb_devstral.log#L4008) |
| 09/05 10:26:27 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:4022](../logs/followup_tb_devstral.log#L4022) |
| 09/05 10:26:28 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:4036](../logs/followup_tb_devstral.log#L4036) |
| 09/05 10:26:29 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:4050](../logs/followup_tb_devstral.log#L4050) |
| 09/05 10:26:30 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:4078](../logs/followup_tb_devstral.log#L4078) |
| 09/05 10:26:30 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:4064](../logs/followup_tb_devstral.log#L4064) |
| 09/05 14:56:30 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:4098](../logs/followup_tb_devstral.log#L4098) |
| 09/05 14:56:31 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:4112](../logs/followup_tb_devstral.log#L4112) |
| 09/05 14:56:31 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:4126](../logs/followup_tb_devstral.log#L4126) |
| 09/05 14:56:32 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:4140](../logs/followup_tb_devstral.log#L4140) |
| 09/05 14:56:33 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:4154](../logs/followup_tb_devstral.log#L4154) |
| 09/05 14:56:34 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:4168](../logs/followup_tb_devstral.log#L4168) |
| 09/05 14:56:35 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:4182](../logs/followup_tb_devstral.log#L4182) |
| 09/05 14:56:36 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:4196](../logs/followup_tb_devstral.log#L4196) |
| 09/05 14:57:12 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:944](../logs/followup_tb_glm.log#L944) |
| 09/05 14:57:13 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:958](../logs/followup_tb_glm.log#L958) |
| 09/05 14:57:14 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:972](../logs/followup_tb_glm.log#L972) |

## Limits on timestamps and completion claims

- `.bash_history` contains another TB1 prebuild invocation (line 566 when inspected), but no corresponding new timestamped log was identified. Its date remains unknown; it is not treated as the same execution as the August 30 full prebuild.
- The August 30 host configuration changes are documented in [tb_prebuild.md](tb_prebuild.md). The remaining 38 tasks were built with rootless Podman while preserving ownership semantics.
- Qwen Main has a completion entry on September 3 at 14:32:50. Ablation has start entries through the 4K SS-partial cell on September 4 at 10:18, and the nohup log ends with `Terminated`. This does not establish completion of the full ablation grid.
- The TB2 resume and single-task retry logs end with aggregation errors. However, the canonical `ICLR_results/terminalbench2/main/qwen35b/di__binf__fc/experiment_results.json` contained 89 records when inspected. Later postprocessing and successful completion of the original command are separate events.
- Model switches involved `start_vllm_qwen35.sh`, `start_vllm_devstral.sh`, `start_vllm_glm47flash.sh`, or direct vLLM commands. Some logs were overwritten, so not all server start times can be reconstructed. September 5 history also records GLM starting on GPUs 4,5,6,7.
- No new SWE-bench experiment launches were found for this period in the inspected shell history and local logs. This does not rule out launches on other hosts or from shells whose history was not saved.
- Repeated monitoring commands such as `tail`, `ps`, and `nvidia-smi`, dashboard updates, and result aggregation are omitted from the table.
