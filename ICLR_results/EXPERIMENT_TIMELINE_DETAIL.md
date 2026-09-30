# Experiment command history: 2026-08-30–2026-09-28

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

---

# Continuation: 2026-09-06–2026-09-28

Appended on 2026-09-29 using the same method: `.bash_history`, launcher logs, vLLM logs, archive notes, and [EXPERIMENT_LOG_TB.md](EXPERIMENT_LOG_TB.md) were cross-checked. All times are **CDT (UTC−5)**. The host is Albus (8× A6000) for every entry. `.bash_history` interleaves several shells and has no timestamps, so times come from log headers, vLLM log timestamps, or (where marked) file and directory mtimes. `SLACK_WEBHOOK_URL` setup, `DOCKER_HOST`/Podman socket checks, and readiness `curl` loops preceding most launches are omitted.

## Launch chronology (continued)

| Start (CDT) | Experiment or operation | Launch command (excerpt) | Progress and outcome | Source log |
|---|---|---|---|---|
| 09/06 (before 14:46) | Stop the September 5 afternoon runs (wrong GPU assignment) and archive them | `kill -TERM -- -<GLM launcher PGID>`; `kill -TERM -- -<Devstral vLLM PGID> -<GLM vLLM PGID>` | The 09/05 14:56 Devstral launch had already logged `TB (3.a) complete` at 09/06 13:07:48; the 09/05 14:57 GLM launch ends in `Terminated`. The runs used Devstral on GPUs 0–3 and GLM on 4–7, so 680 Devstral and 240 GLM results were withdrawn and archived. | [followup_tb_devstral.log:6913](../logs/followup_tb_devstral.log#L6913), [followup_tb_glm_main.nohup.log:1935](../logs/followup_tb_glm_main.nohup.log#L1935) |
| 09/06 (before 14:46) | vLLM restart with the corrected GPU assignment | `GLM_CUDA_VISIBLE_DEVICES=0,1,2,3 bash scripts/start_vllm_glm47flash.sh`; `DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 bash scripts/start_vllm_devstral.sh`; `venv-harbor/bin/python -m scripts.bench_adapters.check_vllm_cancellation glm\|devstral` | The cancellation check and `unittest scripts.bench_adapters.test_harbor_cancellation` ran before relaunch. Server start times cannot be recovered because the logs were overwritten. | — |
| 09/06 14:46:19 | GLM / TB1 Main P-40 / 3K restart | `N_CONCURRENT=4 nohup bash scripts/run_glm_tb_main_with_slack.sh >> logs/followup_tb_glm_main.nohup.log 2>&1 < /dev/null &` | Kept 240 results and re-executed from `su-partial` run 1. It reached `otrc-tr` at 09/07 17:12:03 and was then stopped (`Terminated`) before the 17:44 archive step. | [followup_tb_glm.log:2876](../logs/followup_tb_glm.log#L2876) |
| 09/06 14:46:19 | Devstral / TB1 Main P-40 / 4K restart | `N_CONCURRENT=4 nohup bash scripts/run_devstral_tb_main_with_slack.sh >> logs/followup_tb_devstral_main.nohup.log 2>&1 < /dev/null &` | Kept 880 results and re-executed from `trc-ss` run 2. Complete at 09/07 08:52:12. | [followup_tb_devstral.log:6914](../logs/followup_tb_devstral.log#L6914) |
| 09/07 14:48 (dir name) | SWE-bench / Devstral summary smoke (separate checkout `~/agentCtx-summarization`) | `venv/bin/python -u scripts/run_experiment.py --benchmark swe-bench --model-tag devstral-summary-smoke --ablation "$RUN_NAME" --agent-config configs/config-devstral-vllm.yaml --summary-config configs/config-devstral-vllm.yaml --tasks-file task_lists/p100_all_100_tasks.json --n-tasks 1 --conditions summarization structured-summarize --budget 3000 --depth 0.5 --runs-per-task 1 --max-workers 1` | 1 task × 2 conditions × 1 run. Output: `results/ablations/smoke-devstral-summary-20260907-144807`. Not part of `ICLR_results/`. | — |
| 09/07 15:17 (dir name) | Same SWE-bench smoke after the summary fix | Same command with `RUN_NAME=smoke-devstral-summary-fixed-$(date +%Y%m%d-%H%M%S)` | Output: `results/ablations/smoke-devstral-summary-fixed-20260907-151711`. This was used to check the `query_summary` fix (`cd1716f`) that was later brought in as `6b45448`. | — |
| 09/07 17:15:35 – 17:44:12 | Archive `summary_marker_error` runs for rerun | `venv/bin/python scripts/archive_rerun_targets.py --execute` (Devstral by default); `venv/bin/python scripts/archive_rerun_targets.py --cohort-model-path qwen35b\|glm47flash --section main\|ablation --rerun-reason summary_marker_error --archive-name <model>_<section>_summary_marker_error_$(date +%Y%m%d_%H%M%S)_CDT --execute` | Archived 324 Devstral Main runs at 17:15:35, 396 Qwen Main runs at 17:43:29, 157 Qwen ablation runs at 17:44:01, and 224 GLM Main runs at 17:44:12. Evaluation and data handling only; no trials were run. | [ARCHIVE_LOG.md](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md) |
| 09/07 (before 17:49) | Server switch: stop GLM, start Qwen | `kill -TERM -- -<GLM launcher PGID>`; `kill -TERM -- -<GLM vLLM PGID>`; `QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3 QWEN_TENSOR_PARALLEL_SIZE=4 bash scripts/start_vllm_qwen35.sh` | Qwen on GPUs 0–3 (:8000) and Devstral on GPUs 4–7 (:8002). | — |
| 09/07 17:49:54 | Qwen Main rerun (after summary fix) | `N_CONCURRENT=4 nohup setsid bash scripts/run_qwen_tb_main_with_slack.sh >> logs/followup_tb_qwen_main.nohup.log 2>&1 < /dev/null &` | HEAD `6b45448`. Complete at 09/08 07:42:02. | [followup_tb_qwen.log:11563](../logs/followup_tb_qwen.log#L11563) |
| 09/07 17:49:54 | Devstral Main rerun (after summary fix) | `N_CONCURRENT=4 nohup setsid bash scripts/run_devstral_tb_main_with_slack.sh >> logs/followup_tb_devstral_main.nohup.log 2>&1 < /dev/null &` | HEAD `6b45448`. Complete at 09/08 05:43:44. | [followup_tb_devstral.log:7759](../logs/followup_tb_devstral.log#L7759) |
| 09/08 (before 10:37) | Server switch: Qwen → GLM (GPUs 0–3) | `DEVSTRAL_CUDA_VISIBLE_DEVICES=0,1,2,3 bash scripts/start_vllm_devstral.sh` (then stopped by PID check); `GLM_CUDA_VISIBLE_DEVICES=0,1,2,3 bash scripts/start_vllm_glm47flash.sh` | History also records a short-lived Devstral server on GPUs 0–3 that was started and stopped before GLM. | — |
| 09/08 10:37:39 | GLM Main resume | `GLM_TB_LOG_FILE="$PWD/logs/followup_tb_glm_main_$(date +%Y%m%d_%H%M%S).log" nohup setsid bash scripts/run_glm_tb_main_with_slack.sh </dev/null >"$GLM_TB_LOG_FILE" 2>&1 &` | HEAD `df7cb96`. Reached `trc-ss` at 17:05:50 and was terminated around 19:05 for the rerun2 archive step. | [followup_tb_glm_main_20260908_103738.log:1](../logs/followup_tb_glm_main_20260908_103738.log#L1) |
| 09/08 19:14:03 | Second summary-bug archive (`rerun2`) | `python3 $T/scripts/append_rerun_additions.py --rerun-list $T/rerun_list/rerun_runs.csv --additions $T/erasure-terminalbench/rerun_runs_tb_additions.csv --label tb-erasure`; `python3 $T/scripts/archive_rerun_targets.py --rerun-csv $T/rerun_list/rerun_runs.csv --cohort-model-path <m> --rerun-reason summary_failure_accounting summary_related_response tb_erasure_possible tb_unverifiable --archive-name <m>_summary_bug_rerun2_$(date +%Y%m%d_%H%M%S)_CDT --execute` | Archived 407 Devstral runs, 407 GLM runs, and 577 Qwen runs (Main + ablation). No trials were run. | [EXPERIMENT_LOG_TB.md §5(a)](EXPERIMENT_LOG_TB.md#main-completion) |
| 09/08 19:27:54 | Qwen Main relaunch | `nohup setsid env N_CONCURRENT=4 bash scripts/run_qwen_tb_main_with_slack.sh </dev/null >>logs/followup_tb_qwen_main.nohup.log 2>&1 &` | HEAD `26d5fbc`. Complete at 09/09 07:47:07, with 1,560 planned runs. | [followup_tb_qwen.log:12609](../logs/followup_tb_qwen.log#L12609) |
| 09/09 09:15 (mtime) | GLM / TB1 P-80 / FC run 1, native context re-collection | `GLM_MAX_MODEL_LEN=native bash scripts/start_vllm_glm47flash.sh`; `nohup venv-harbor/bin/python -u scripts/run_budget_calibration_tb.py --model-key glm47flash --agent-config configs/config-glm47flash-vllm.yaml --calibration-dir "$TB_CAL_DIR" --job-name tb1-glm47flash-native-p80-fc-run1 --run-num 1 --n-tasks 80 --n-concurrent 4` | 80/80 collected and 26 resolved. `launcher.log` was last written at 10:54. Output: `calibration_results/terminalbench/glm47flash_native_p80/`. | [launcher.log](../calibration_results/terminalbench/glm47flash_native_p80/launcher.log) |
| 09/09 09:58 (mtime) | Devstral / TB1 P-80 / FC run 1, native context re-collection | `DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 DEVSTRAL_MAX_MODEL_LEN=native DEVSTRAL_MAX_NUM_SEQS=4 bash scripts/start_vllm_devstral.sh`; `... run_budget_calibration_tb.py --model-key devstral24b --agent-config configs/config-devstral-vllm.yaml --job-name tb1-devstral24b-native-p80-fc-run1 --run-num 1 --n-tasks 80 --n-concurrent 2` | 80/80 collected and 24 resolved. `launcher.log` was last written at 12:35. Both vLLM servers were stopped afterwards. | [launcher.log](../calibration_results/terminalbench/devstral24b_native_p80/launcher.log) |
| 09/10 ~21:03 | Devstral Main relaunch attempt | `nohup setsid env N_CONCURRENT=4 PYTHONUNBUFFERED=1 bash scripts/run_devstral_tb_main_with_slack.sh >> logs/followup_tb_devstral_main.nohup.log 2>&1 < /dev/null &` | Exited immediately because `SLACK_WEBHOOK_URL` was unset. No trials were run. | [followup_tb_devstral_main.nohup.log:4314](../logs/followup_tb_devstral_main.nohup.log#L4314) |
| 09/10 21:05:28 | Devstral Main relaunch | `DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 DEVSTRAL_MAX_MODEL_LEN=65536 bash scripts/start_vllm_devstral.sh`; `DEVSTRAL_TB_LOG_FILE="$PWD/logs/devstral_main_$(date +%Y%m%d_%H%M%S).log" nohup setsid env N_CONCURRENT=4 PYTHONUNBUFFERED=1 bash scripts/run_devstral_tb_main_with_slack.sh > "$DEVSTRAL_TB_LOG_FILE" 2>&1 < /dev/null &` | HEAD `26d5fbc`. Complete at 09/11 10:46:48, with 1,560 planned runs. | [devstral_main_20260910_210528.log:1](../logs/devstral_main_20260910_210528.log#L1) |
| 09/10 21:16 (mtime) | Qwen / TB1 P-80 / FC run 1, native context (262K) re-collection | `QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3 QWEN_MAX_MODEL_LEN=native QWEN_MAX_NUM_SEQS=4 bash scripts/start_vllm_qwen35.sh`; `nohup setsid venv-harbor/bin/python -u scripts/run_budget_calibration_tb.py --model-key qwen35b --agent-config "$QWEN_CAL_DIR/agent_config.yaml" --calibration-dir "$QWEN_CAL_DIR" --job-name tb1-qwen35b-native-p80-fc-run1 --run-num 1 --n-tasks 80 --n-concurrent 4 --skip-postprocess` | 80/80 collected and 27 resolved. `launcher.log` was last written at 22:43. The Qwen server was stopped afterwards (`kill -TERM <PID>`). | [launcher.log](../calibration_results/terminalbench/qwen35b_native_p80/launcher.log) |
| 09/11 00:52:26 | GLM Main resume | `HF_HUB_OFFLINE=1 GLM_CUDA_VISIBLE_DEVICES=0,1,2,3 GLM_TENSOR_PARALLEL_SIZE=4 GLM_MAX_MODEL_LEN=65536 bash scripts/start_vllm_glm47flash.sh`; `GLM_TB_LOG_FILE=... nohup setsid env N_CONCURRENT=4 bash scripts/run_glm_tb_main_with_slack.sh </dev/null >>"$GLM_TB_LOG_FILE" 2>&1 &` | Reached `di__b3k__trc-su` at 10:13:01. The log stops at about 11:21; history then records host checks (`nvidia-smi`, `ss -ltnp`, `free -h`). | [followup_tb_glm_main_20260911_005226.log:1](../logs/followup_tb_glm_main_20260911_005226.log#L1) |
| 09/11 17:59:18 | GLM Main resume script | `logs/resume_glm_main_20260911.sh` (waits for :8003, then runs `exec bash scripts/run_agent_models_expansion_tb.sh glm main`) | The GLM vLLM log restarts at 18:00:40 (`HF_HUB_OFFLINE=1 bash scripts/start_vllm_glm47flash.sh`). This run was superseded. | [followup_tb_glm_main_20260911_1758.log:3](../logs/followup_tb_glm_main_20260911_1758.log#L3) |
| 09/11 18:20:24 | GLM Main manual resume | `GLM_P_BUDGET=3000 N_CONCURRENT=4 nohup flock -n logs/glm_tb_main.lock bash scripts/run_agent_models_expansion_tb.sh glm main > logs/glm_main_manual_resume.log 2>&1 &` | Stopped with `kill -TERM %1` so it could be relaunched with Slack notification. | [glm_main_manual_resume.log:2](../logs/glm_main_manual_resume.log#L2) |
| 09/11 18:26:24 | GLM Main resume (Slack) | `GLM_TB_LOG_FILE="$PWD/logs/glm_main_slack_resume.log" N_CONCURRENT=4 nohup bash scripts/run_glm_tb_main_with_slack.sh > logs/glm_main_slack_resume.log 2>&1 &` | Complete at 09/12 12:34:28, with 1,560 planned runs. | [glm_main_slack_resume.log:2](../logs/glm_main_slack_resume.log#L2) |
| 09/11 20:36:35 | Re-verify verifier timeouts (evaluation only) | `scripts/replay_reverify_tb.py` (the invocation is not in history); afterwards `python3 scripts/audit_tb_verdicts.py`, `python3 analysis/aggregate_terminalbench_results.py`, `python3 analysis/aggregate_terminalbench2_results.py`, `python3 dashboard/build_coverage.py && python3 dashboard/build_dashboard.py` | Recovered the reward file for 17 trials, reducing `false_without_verdict` from 393 to 376. No new trials were run. | [candidates_20260911-203635.json](../logs/replay_reverify/candidates_20260911-203635.json) |
| 09/12 00:59:15 | Devstral / TB1 ablation P-15 | `DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 bash scripts/start_vllm_devstral.sh` (vLLM 00:57:19); `sed 's/main/ablation/g; s/Main/Ablation/g' scripts/run_devstral_tb_main_with_slack.sh > logs/run_devstral_tb_ablation_with_slack.sh`; `DEVSTRAL_A_BUDGET=3000 DEVSTRAL_P_BUDGET=4000 DEVSTRAL_B_BUDGET=7000 N_CONCURRENT=4 nohup setsid bash logs/run_devstral_tb_ablation_with_slack.sh </dev/null >"$DEVSTRAL_TB_LOG_FILE" 2>&1 &` | HEAD `ec1e42a`. Complete at 09/14 07:05:42 with 2,340 planned runs (52 cells). | [devstral_ablation_20260912_005915.log:1](../logs/devstral_ablation_20260912_005915.log#L1) |
| 09/12 13:38:47 | Qwen / TB1 ablation P-15 | Stop GLM vLLM after PID check; `QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3 QWEN_TENSOR_PARALLEL_SIZE=4 QWEN_VLLM_PORT=8000 bash scripts/start_vllm_qwen35.sh`; `sed -e 's/main/ablation/g' -e 's/Main/Ablation/g' -e 's/(3.a)/(3.b)/g' scripts/run_qwen_tb_main_with_slack.sh > logs/run_qwen_tb_ablation_with_slack.sh`; `QWEN_A_BUDGET=2000 QWEN_P_BUDGET=3000 QWEN_B_BUDGET=4000 N_CONCURRENT=4 PYTHONUNBUFFERED=1 nohup setsid bash logs/run_qwen_tb_ablation_with_slack.sh </dev/null >>"$QWEN_TB_LOG_FILE" 2>&1 &` | HEAD `ec1e42a`. Complete at 09/15 00:59:11 with 2,340 planned runs. This covers the partial ablation cells from September 3–4. The Qwen vLLM server was stopped afterwards. | [qwen_ablation_20260912_133847.log:1](../logs/qwen_ablation_20260912_133847.log#L1) |
| 09/16 15:01:16 | Two GLM vLLM servers (manual launch) | `CUDA_VISIBLE_DEVICES=0,1,2,3 nohup ./venv-glm-cu129-clean/bin/python3 -m vllm.entrypoints.openai.api_server --model zai-org/GLM-4.7-Flash --port 8003 --dtype auto --tensor-parallel-size 4 --max-model-len 65536 --max-num-seqs 64 --enable-prefix-caching > logs/vllm_glm_gpu0-3.log 2>&1 &` (and the same on GPUs 4–7 with `--port 8004`) | Both servers were stopped around 17:47. | [vllm_glm_gpu0-3.log](../logs/vllm_glm_gpu0-3.log), [vllm_glm_gpu4-7.log](../logs/vllm_glm_gpu4-7.log) |
| 09/16 15:13:43 | GLM / TB1 ablation P-15, split across two servers | `nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 > logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &`; `nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu4-7 > logs/followup_tb_glm_ablation_gpu4-7.nohup.log 2>&1 &` | gpu0-3 = `d03 d07` and gpu4-7 = `di d05`. Both were terminated around 17:46 to free GPUs for the summarizer ablation. Split support was committed after launch as `376f1df`. | [followup_tb_glm_ablation_gpu0-3.log:1](../logs/followup_tb_glm_ablation_gpu0-3.log#L1), [gpu4-7.nohup.log:2](../logs/followup_tb_glm_ablation_gpu4-7.nohup.log#L2) |
| 09/16 20:44:44 | Summarizer ablation smoke: Qwen3.5-9B | `bash scripts/start_vllm_qwen35.sh`; `bash scripts/start_vllm_qwen35_9b.sh`; `N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/run_qwen_tb_summarizer_ablation.sh` | 1 task × 1 run. Complete at 21:00:13. | [followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log:1](../logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log#L1) |
| 09/23 13:11:58 | Summarizer ablation: Qwen3.5-9B | Servers: agent Qwen3.5-35B at 13:08:03 on GPUs 0–3 (:8000) and summarizer 9B at 13:08:05 on GPUs 4–5 (:8001). `TB_TASKS_FILE=task_lists/tbench_abl15.json ICLR_MODEL=qwen35b-sum-qwen35-9b RUNS_PER_TASK=3 N_CONCURRENT=4 nohup bash scripts/run_qwen_tb_summarizer_ablation_with_slack.sh > logs/followup_tb_qwen_sumabl_qwen9b.nohup.log 2>&1 &` | HEAD `5ad3d7b`. 2 cells × 45 = 90 runs. Complete at 15:55:52. | [followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:1](../logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L1) |
| 09/23 16:25:42 | Summarizer ablation smoke: Gemma-4-12B | `bash scripts/stop_vllm.sh logs/vllm_qwen35_9b.pid`; `bash scripts/start_vllm_gemma4_12b.sh` (vLLM 16:14:40); `N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b-smoke bash scripts/run_qwen_tb_summarizer_ablation.sh` | Complete at 16:32:06. | [followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b-smoke.log:1](../logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b-smoke.log#L1) |
| 09/23 16:32:16 | Summarizer ablation: Gemma-4-12B | `TB_TASKS_FILE=task_lists/tbench_abl15.json SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b RUNS_PER_TASK=3 N_CONCURRENT=4 nohup bash scripts/run_qwen_tb_summarizer_ablation_with_slack.sh > logs/followup_tb_qwen_sumabl_gemma4-12b.nohup.log 2>&1 &` | 90 runs. Complete at 18:53:27. The Gemma config and start script were committed later as `4e25e6e`. | [followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:1](../logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L1) |
| 09/23 20:38:25 | Qwen / prefix-cache ablation (caching off), gpu0-3 half | `bash scripts/stop_vllm.sh logs/vllm_gemma4_12b.pid`; `bash scripts/stop_vllm.sh logs/vllm_qwen35.pid`; `bash scripts/start_vllm_qwen35_no_prefix_cache.sh` (vLLM 20:36:00, :8000); `nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu0-3 > logs/followup_tb_qwen_noprefixcache_gpu0-3.nohup.log 2>&1 &` | Covers 5 depth-tunable cells plus FC@∞ and OTRC@∞ (315 runs). Complete at 09/24 05:12:51 with `0 hit / 0 queried tokens`. | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:1](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L1) |
| 09/23 20:38:25 | Qwen / prefix-cache ablation (caching off), gpu4-7 half | `bash scripts/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh` (vLLM 20:36:02, :8002); `nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu4-7 > logs/followup_tb_qwen_noprefixcache_gpu4-7.nohup.log 2>&1 &` | Covers 6 depth-invariant cells (270 runs). Complete at 09/24 03:15:39. Split support was committed after launch as `4e25e6e`. | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:1](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L1) |
| 09/26 08:48:54 | GLM ablation resume, single server (default parts) | `mv logs/vllm_glm47flash.log logs/vllm_glm47flash_20260912.log`; `bash scripts/start_vllm_glm47flash.sh` (process start 08:44:53); `nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 >> logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &` | Ran only parts `d03 d07` and was replaced within minutes. HEAD `b45f8dc`. | [followup_tb_glm_ablation_gpu0-3.log:200](../logs/followup_tb_glm_ablation_gpu0-3.log#L200) |
| 09/26 08:53:24 | GLM ablation resume, all parts | `ABLATION_PARTS="d03 d07 di d05" nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 >> logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &` | Skipped the runs completed on September 16. **Complete at 09/28 21:22:41**, with 52 cells and 2,340 rows on disk. This is the last recorded experiment launch. | [followup_tb_glm_ablation_gpu0-3.log:221](../logs/followup_tb_glm_ablation_gpu0-3.log#L221) |

## Cell transitions within each launch (continued)

The table below continues the one above. It lists cell-start entries after the last row of that table, from the canonical launcher logs: `followup_tb_devstral.log`, `followup_tb_glm.log`, and `followup_tb_qwen.log` (all cumulative), plus the GLM ablation, summarizer ablation, and prefix-cache ablation logs. The `.nohup.log` mirrors and per-launch copies, such as `devstral_main_*.log` and `glm_main_slack_resume.log`, contain the same entries and are omitted. The earlier caveat still applies: cells entered within seconds during a resume are skips, not new trials. Rows dated 09/05–09/06 before 14:46 belong to the September 5 launches that were later archived.

| Start (CDT) | Cell | Source |
|---|---|---|
| 09/05 18:32:34 | `main/devstral24b/di__b4k__otrc-tr` | [followup_tb_devstral.log:4686](../logs/followup_tb_devstral.log#L4686) |
| 09/05 20:57:13 | `main/devstral24b/di__b4k__otrc-su-partial` | [followup_tb_devstral.log:4816](../logs/followup_tb_devstral.log#L4816) |
| 09/06 02:08:45 | `main/devstral24b/di__b4k__otrc-ss-partial` | [followup_tb_devstral.log:5464](../logs/followup_tb_devstral.log#L5464) |
| 09/06 06:13:09 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:1940](../logs/followup_tb_glm.log#L1940) |
| 09/06 07:43:30 | `main/devstral24b/di__binf__fc` | [followup_tb_devstral.log:6349](../logs/followup_tb_devstral.log#L6349) |
| 09/06 10:13:23 | `main/devstral24b/di__binf__otrc` | [followup_tb_devstral.log:6735](../logs/followup_tb_devstral.log#L6735) |
| 09/06 13:25:29 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:2872](../logs/followup_tb_glm.log#L2872) |
| 09/06 14:46:19 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:6915](../logs/followup_tb_devstral.log#L6915) |
| 09/06 14:46:19 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:6929](../logs/followup_tb_devstral.log#L6929) |
| 09/06 14:46:19 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:2877](../logs/followup_tb_glm.log#L2877) |
| 09/06 14:46:19 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:2891](../logs/followup_tb_glm.log#L2891) |
| 09/06 14:46:20 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:6943](../logs/followup_tb_devstral.log#L6943) |
| 09/06 14:46:20 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:2905](../logs/followup_tb_glm.log#L2905) |
| 09/06 14:46:21 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:6957](../logs/followup_tb_devstral.log#L6957) |
| 09/06 14:46:22 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:6971](../logs/followup_tb_devstral.log#L6971) |
| 09/06 14:46:23 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:6985](../logs/followup_tb_devstral.log#L6985) |
| 09/06 14:46:24 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:6999](../logs/followup_tb_devstral.log#L6999) |
| 09/06 14:46:24 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:7013](../logs/followup_tb_devstral.log#L7013) |
| 09/06 17:17:02 | `main/devstral24b/di__b4k__otrc-tr` | [followup_tb_devstral.log:7104](../logs/followup_tb_devstral.log#L7104) |
| 09/06 19:44:19 | `main/devstral24b/di__b4k__otrc-su-partial` | [followup_tb_devstral.log:7239](../logs/followup_tb_devstral.log#L7239) |
| 09/06 19:49:31 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:3030](../logs/followup_tb_glm.log#L3030) |
| 09/06 23:45:15 | `main/devstral24b/di__b4k__otrc-ss-partial` | [followup_tb_devstral.log:7370](../logs/followup_tb_devstral.log#L7370) |
| 09/07 00:29:45 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:3155](../logs/followup_tb_glm.log#L3155) |
| 09/07 04:30:22 | `main/devstral24b/di__binf__fc` | [followup_tb_devstral.log:7499](../logs/followup_tb_devstral.log#L7499) |
| 09/07 05:27:08 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:3282](../logs/followup_tb_glm.log#L3282) |
| 09/07 06:34:15 | `main/devstral24b/di__binf__otrc` | [followup_tb_devstral.log:7629](../logs/followup_tb_devstral.log#L7629) |
| 09/07 08:02:24 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:3425](../logs/followup_tb_glm.log#L3425) |
| 09/07 12:46:35 | `main/glm47flash/di__b3k__trc-ss` | [followup_tb_glm.log:3551](../logs/followup_tb_glm.log#L3551) |
| 09/07 17:12:03 | `main/glm47flash/di__b3k__otrc-tr` | [followup_tb_glm.log:3678](../logs/followup_tb_glm.log#L3678) |
| 09/07 17:49:54 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:7760](../logs/followup_tb_devstral.log#L7760) |
| 09/07 17:49:54 | `main/qwen35b/d05__b3k__tr` | [followup_tb_qwen.log:11564](../logs/followup_tb_qwen.log#L11564) |
| 09/07 17:49:55 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:7774](../logs/followup_tb_devstral.log#L7774) |
| 09/07 17:49:55 | `main/qwen35b/d05__b3k__su-full` | [followup_tb_qwen.log:11578](../logs/followup_tb_qwen.log#L11578) |
| 09/07 17:49:56 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:7788](../logs/followup_tb_devstral.log#L7788) |
| 09/07 17:49:57 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:7802](../logs/followup_tb_devstral.log#L7802) |
| 09/07 18:29:25 | `main/qwen35b/d05__b3k__su-partial` | [followup_tb_qwen.log:11701](../logs/followup_tb_qwen.log#L11701) |
| 09/07 19:16:58 | `main/qwen35b/d05__b3k__ss` | [followup_tb_qwen.log:11825](../logs/followup_tb_qwen.log#L11825) |
| 09/07 21:23:45 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:7935](../logs/followup_tb_devstral.log#L7935) |
| 09/07 22:12:00 | `main/qwen35b/d05__b3k__ss-partial` | [followup_tb_qwen.log:11950](../logs/followup_tb_qwen.log#L11950) |
| 09/08 00:02:08 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:8065](../logs/followup_tb_devstral.log#L8065) |
| 09/08 00:02:09 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:8079](../logs/followup_tb_devstral.log#L8079) |
| 09/08 00:02:10 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:8093](../logs/followup_tb_devstral.log#L8093) |
| 09/08 01:07:25 | `main/qwen35b/di__b3k__trc` | [followup_tb_qwen.log:12075](../logs/followup_tb_qwen.log#L12075) |
| 09/08 01:07:26 | `main/qwen35b/di__b3k__trc-su` | [followup_tb_qwen.log:12089](../logs/followup_tb_qwen.log#L12089) |
| 09/08 01:57:04 | `main/qwen35b/di__b3k__trc-ss` | [followup_tb_qwen.log:12205](../logs/followup_tb_qwen.log#L12205) |
| 09/08 03:00:45 | `main/devstral24b/di__b4k__otrc-tr` | [followup_tb_devstral.log:8222](../logs/followup_tb_devstral.log#L8222) |
| 09/08 03:00:46 | `main/devstral24b/di__b4k__otrc-su-partial` | [followup_tb_devstral.log:8236](../logs/followup_tb_devstral.log#L8236) |
| 09/08 03:00:47 | `main/devstral24b/di__b4k__otrc-ss-partial` | [followup_tb_devstral.log:8250](../logs/followup_tb_devstral.log#L8250) |
| 09/08 04:35:42 | `main/qwen35b/di__b3k__otrc-tr` | [followup_tb_qwen.log:12354](../logs/followup_tb_qwen.log#L12354) |
| 09/08 04:35:43 | `main/qwen35b/di__b3k__otrc-su-partial` | [followup_tb_qwen.log:12368](../logs/followup_tb_qwen.log#L12368) |
| 09/08 04:52:47 | `main/qwen35b/di__b3k__otrc-ss-partial` | [followup_tb_qwen.log:12455](../logs/followup_tb_qwen.log#L12455) |
| 09/08 05:43:43 | `main/devstral24b/di__binf__fc` | [followup_tb_devstral.log:8380](../logs/followup_tb_devstral.log#L8380) |
| 09/08 05:43:44 | `main/devstral24b/di__binf__otrc` | [followup_tb_devstral.log:8394](../logs/followup_tb_devstral.log#L8394) |
| 09/08 07:42:00 | `main/qwen35b/di__binf__fc` | [followup_tb_qwen.log:12580](../logs/followup_tb_qwen.log#L12580) |
| 09/08 07:42:01 | `main/qwen35b/di__binf__otrc` | [followup_tb_qwen.log:12594](../logs/followup_tb_qwen.log#L12594) |
| 09/08 10:37:39 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:3683](../logs/followup_tb_glm.log#L3683) |
| 09/08 10:37:39 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:3697](../logs/followup_tb_glm.log#L3697) |
| 09/08 11:18:07 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:3819](../logs/followup_tb_glm.log#L3819) |
| 09/08 11:18:08 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:3833](../logs/followup_tb_glm.log#L3833) |
| 09/08 13:28:15 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:3959](../logs/followup_tb_glm.log#L3959) |
| 09/08 16:26:16 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:4085](../logs/followup_tb_glm.log#L4085) |
| 09/08 16:26:17 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:4099](../logs/followup_tb_glm.log#L4099) |
| 09/08 17:05:50 | `main/glm47flash/di__b3k__trc-ss` | [followup_tb_glm.log:4215](../logs/followup_tb_glm.log#L4215) |
| 09/08 19:27:54 | `main/qwen35b/d05__b3k__tr` | [followup_tb_qwen.log:12610](../logs/followup_tb_qwen.log#L12610) |
| 09/08 19:27:55 | `main/qwen35b/d05__b3k__su-full` | [followup_tb_qwen.log:12624](../logs/followup_tb_qwen.log#L12624) |
| 09/08 22:41:38 | `main/qwen35b/d05__b3k__su-partial` | [followup_tb_qwen.log:12750](../logs/followup_tb_qwen.log#L12750) |
| 09/09 00:42:29 | `main/qwen35b/d05__b3k__ss` | [followup_tb_qwen.log:12875](../logs/followup_tb_qwen.log#L12875) |
| 09/09 01:36:55 | `main/qwen35b/d05__b3k__ss-partial` | [followup_tb_qwen.log:13000](../logs/followup_tb_qwen.log#L13000) |
| 09/09 01:43:24 | `main/qwen35b/di__b3k__trc` | [followup_tb_qwen.log:13050](../logs/followup_tb_qwen.log#L13050) |
| 09/09 01:43:24 | `main/qwen35b/di__b3k__trc-su` | [followup_tb_qwen.log:13064](../logs/followup_tb_qwen.log#L13064) |
| 09/09 04:41:39 | `main/qwen35b/di__b3k__trc-ss` | [followup_tb_qwen.log:13189](../logs/followup_tb_qwen.log#L13189) |
| 09/09 05:05:58 | `main/qwen35b/di__b3k__otrc-tr` | [followup_tb_qwen.log:13314](../logs/followup_tb_qwen.log#L13314) |
| 09/09 05:05:59 | `main/qwen35b/di__b3k__otrc-su-partial` | [followup_tb_qwen.log:13328](../logs/followup_tb_qwen.log#L13328) |
| 09/09 07:40:21 | `main/qwen35b/di__b3k__otrc-ss-partial` | [followup_tb_qwen.log:13456](../logs/followup_tb_qwen.log#L13456) |
| 09/09 07:47:05 | `main/qwen35b/di__binf__fc` | [followup_tb_qwen.log:13561](../logs/followup_tb_qwen.log#L13561) |
| 09/09 07:47:06 | `main/qwen35b/di__binf__otrc` | [followup_tb_qwen.log:13575](../logs/followup_tb_qwen.log#L13575) |
| 09/10 21:05:28 | `main/devstral24b/d05__b4k__tr` | [followup_tb_devstral.log:8410](../logs/followup_tb_devstral.log#L8410) |
| 09/10 21:05:29 | `main/devstral24b/d05__b4k__su-full` | [followup_tb_devstral.log:8424](../logs/followup_tb_devstral.log#L8424) |
| 09/10 23:57:43 | `main/devstral24b/d05__b4k__su-partial` | [followup_tb_devstral.log:8554](../logs/followup_tb_devstral.log#L8554) |
| 09/11 00:52:26 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:4291](../logs/followup_tb_glm.log#L4291) |
| 09/11 00:52:27 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:4305](../logs/followup_tb_glm.log#L4305) |
| 09/11 02:51:11 | `main/devstral24b/d05__b4k__ss` | [followup_tb_devstral.log:8685](../logs/followup_tb_devstral.log#L8685) |
| 09/11 03:34:42 | `main/devstral24b/d05__b4k__ss-partial` | [followup_tb_devstral.log:8810](../logs/followup_tb_devstral.log#L8810) |
| 09/11 03:47:17 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:4434](../logs/followup_tb_glm.log#L4434) |
| 09/11 03:57:07 | `main/devstral24b/di__b4k__trc` | [followup_tb_devstral.log:8932](../logs/followup_tb_devstral.log#L8932) |
| 09/11 03:57:07 | `main/devstral24b/di__b4k__trc-su` | [followup_tb_devstral.log:8946](../logs/followup_tb_devstral.log#L8946) |
| 09/11 06:54:24 | `main/devstral24b/di__b4k__trc-ss` | [followup_tb_devstral.log:9102](../logs/followup_tb_devstral.log#L9102) |
| 09/11 07:16:17 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:4562](../logs/followup_tb_glm.log#L4562) |
| 09/11 07:33:55 | `main/devstral24b/di__b4k__otrc-tr` | [followup_tb_devstral.log:9231](../logs/followup_tb_devstral.log#L9231) |
| 09/11 07:33:56 | `main/devstral24b/di__b4k__otrc-su-partial` | [followup_tb_devstral.log:9245](../logs/followup_tb_devstral.log#L9245) |
| 09/11 09:26:22 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:4690](../logs/followup_tb_glm.log#L4690) |
| 09/11 10:13:00 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:4813](../logs/followup_tb_glm.log#L4813) |
| 09/11 10:13:01 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:4827](../logs/followup_tb_glm.log#L4827) |
| 09/11 10:27:47 | `main/devstral24b/di__b4k__otrc-ss-partial` | [followup_tb_devstral.log:9375](../logs/followup_tb_devstral.log#L9375) |
| 09/11 10:46:47 | `main/devstral24b/di__binf__fc` | [followup_tb_devstral.log:9495](../logs/followup_tb_devstral.log#L9495) |
| 09/11 10:46:48 | `main/devstral24b/di__binf__otrc` | [followup_tb_devstral.log:9509](../logs/followup_tb_devstral.log#L9509) |
| 09/11 17:59:18 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:4867](../logs/followup_tb_glm.log#L4867) |
| 09/11 17:59:19 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:4881](../logs/followup_tb_glm.log#L4881) |
| 09/11 17:59:20 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:4895](../logs/followup_tb_glm.log#L4895) |
| 09/11 17:59:20 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:4909](../logs/followup_tb_glm.log#L4909) |
| 09/11 17:59:21 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:4923](../logs/followup_tb_glm.log#L4923) |
| 09/11 17:59:22 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:4937](../logs/followup_tb_glm.log#L4937) |
| 09/11 17:59:23 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:4951](../logs/followup_tb_glm.log#L4951) |
| 09/11 18:20:24 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:4971](../logs/followup_tb_glm.log#L4971) |
| 09/11 18:20:24 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:4985](../logs/followup_tb_glm.log#L4985) |
| 09/11 18:20:25 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:4999](../logs/followup_tb_glm.log#L4999) |
| 09/11 18:20:26 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:5013](../logs/followup_tb_glm.log#L5013) |
| 09/11 18:20:27 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:5027](../logs/followup_tb_glm.log#L5027) |
| 09/11 18:20:27 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:5041](../logs/followup_tb_glm.log#L5041) |
| 09/11 18:20:28 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:5055](../logs/followup_tb_glm.log#L5055) |
| 09/11 18:26:24 | `main/glm47flash/d05__b3k__tr` | [followup_tb_glm.log:5060](../logs/followup_tb_glm.log#L5060) |
| 09/11 18:26:25 | `main/glm47flash/d05__b3k__su-full` | [followup_tb_glm.log:5074](../logs/followup_tb_glm.log#L5074) |
| 09/11 18:26:26 | `main/glm47flash/d05__b3k__su-partial` | [followup_tb_glm.log:5088](../logs/followup_tb_glm.log#L5088) |
| 09/11 18:26:26 | `main/glm47flash/d05__b3k__ss` | [followup_tb_glm.log:5102](../logs/followup_tb_glm.log#L5102) |
| 09/11 18:26:27 | `main/glm47flash/d05__b3k__ss-partial` | [followup_tb_glm.log:5116](../logs/followup_tb_glm.log#L5116) |
| 09/11 18:26:28 | `main/glm47flash/di__b3k__trc` | [followup_tb_glm.log:5130](../logs/followup_tb_glm.log#L5130) |
| 09/11 18:26:29 | `main/glm47flash/di__b3k__trc-su` | [followup_tb_glm.log:5144](../logs/followup_tb_glm.log#L5144) |
| 09/11 20:23:15 | `main/glm47flash/di__b3k__trc-ss` | [followup_tb_glm.log:5233](../logs/followup_tb_glm.log#L5233) |
| 09/11 21:43:22 | `main/glm47flash/di__b3k__otrc-tr` | [followup_tb_glm.log:5361](../logs/followup_tb_glm.log#L5361) |
| 09/12 00:43:12 | `main/glm47flash/di__b3k__otrc-su-partial` | [followup_tb_glm.log:5491](../logs/followup_tb_glm.log#L5491) |
| 09/12 00:59:15 | `ablation/devstral24b/d05__b3k__tr` | [followup_tb_devstral.log:9525](../logs/followup_tb_devstral.log#L9525) |
| 09/12 01:46:08 | `ablation/devstral24b/d05__b3k__su-full` | [followup_tb_devstral.log:9656](../logs/followup_tb_devstral.log#L9656) |
| 09/12 02:56:33 | `ablation/devstral24b/d05__b3k__su-partial` | [followup_tb_devstral.log:9787](../logs/followup_tb_devstral.log#L9787) |
| 09/12 04:01:36 | `ablation/devstral24b/d05__b3k__ss` | [followup_tb_devstral.log:9921](../logs/followup_tb_devstral.log#L9921) |
| 09/12 04:30:05 | `main/glm47flash/di__b3k__otrc-ss-partial` | [followup_tb_glm.log:5625](../logs/followup_tb_glm.log#L5625) |
| 09/12 05:07:31 | `ablation/devstral24b/d05__b3k__ss-partial` | [followup_tb_devstral.log:10055](../logs/followup_tb_devstral.log#L10055) |
| 09/12 06:22:27 | `ablation/devstral24b/d05__b7k__tr` | [followup_tb_devstral.log:10192](../logs/followup_tb_devstral.log#L10192) |
| 09/12 07:09:55 | `ablation/devstral24b/d05__b7k__su-full` | [followup_tb_devstral.log:10320](../logs/followup_tb_devstral.log#L10320) |
| 09/12 07:48:07 | `main/glm47flash/di__binf__fc` | [followup_tb_glm.log:5756](../logs/followup_tb_glm.log#L5756) |
| 09/12 07:57:26 | `ablation/devstral24b/d05__b7k__su-partial` | [followup_tb_devstral.log:10448](../logs/followup_tb_devstral.log#L10448) |
| 09/12 08:58:01 | `ablation/devstral24b/d05__b7k__ss` | [followup_tb_devstral.log:10576](../logs/followup_tb_devstral.log#L10576) |
| 09/12 10:04:15 | `main/glm47flash/di__binf__otrc` | [followup_tb_glm.log:5891](../logs/followup_tb_glm.log#L5891) |
| 09/12 10:14:34 | `ablation/devstral24b/d05__b7k__ss-partial` | [followup_tb_devstral.log:10709](../logs/followup_tb_devstral.log#L10709) |
| 09/12 11:00:31 | `ablation/devstral24b/d03__b3k__tr` | [followup_tb_devstral.log:10844](../logs/followup_tb_devstral.log#L10844) |
| 09/12 11:52:58 | `ablation/devstral24b/d03__b3k__su-full` | [followup_tb_devstral.log:10975](../logs/followup_tb_devstral.log#L10975) |
| 09/12 12:45:22 | `ablation/devstral24b/d03__b3k__su-partial` | [followup_tb_devstral.log:11106](../logs/followup_tb_devstral.log#L11106) |
| 09/12 13:38:47 | `ablation/qwen35b/d05__b2k__tr` | [followup_tb_qwen.log:13591](../logs/followup_tb_qwen.log#L13591) |
| 09/12 13:38:48 | `ablation/qwen35b/d05__b2k__su-full` | [followup_tb_qwen.log:13605](../logs/followup_tb_qwen.log#L13605) |
| 09/12 13:43:43 | `ablation/devstral24b/d03__b3k__ss` | [followup_tb_devstral.log:11242](../logs/followup_tb_devstral.log#L11242) |
| 09/12 14:45:15 | `ablation/devstral24b/d03__b3k__ss-partial` | [followup_tb_devstral.log:11376](../logs/followup_tb_devstral.log#L11376) |
| 09/12 15:26:16 | `ablation/qwen35b/d05__b2k__su-partial` | [followup_tb_qwen.log:13730](../logs/followup_tb_qwen.log#L13730) |
| 09/12 15:58:02 | `ablation/devstral24b/d03__b4k__tr` | [followup_tb_devstral.log:11504](../logs/followup_tb_devstral.log#L11504) |
| 09/12 16:42:29 | `ablation/devstral24b/d03__b4k__su-full` | [followup_tb_devstral.log:11632](../logs/followup_tb_devstral.log#L11632) |
| 09/12 16:43:36 | `ablation/qwen35b/d05__b2k__ss` | [followup_tb_qwen.log:13855](../logs/followup_tb_qwen.log#L13855) |
| 09/12 17:52:32 | `ablation/devstral24b/d03__b4k__su-partial` | [followup_tb_devstral.log:11764](../logs/followup_tb_devstral.log#L11764) |
| 09/12 18:16:54 | `ablation/qwen35b/d05__b2k__ss-partial` | [followup_tb_qwen.log:13980](../logs/followup_tb_qwen.log#L13980) |
| 09/12 18:57:08 | `ablation/devstral24b/d03__b4k__ss` | [followup_tb_devstral.log:11892](../logs/followup_tb_devstral.log#L11892) |
| 09/12 19:52:10 | `ablation/qwen35b/d05__b4k__tr` | [followup_tb_qwen.log:14105](../logs/followup_tb_qwen.log#L14105) |
| 09/12 19:52:14 | `ablation/qwen35b/d05__b4k__su-full` | [followup_tb_qwen.log:14119](../logs/followup_tb_qwen.log#L14119) |
| 09/12 20:15:06 | `ablation/devstral24b/d03__b4k__ss-partial` | [followup_tb_devstral.log:12020](../logs/followup_tb_devstral.log#L12020) |
| 09/12 20:43:29 | `ablation/qwen35b/d05__b4k__su-partial` | [followup_tb_qwen.log:14247](../logs/followup_tb_qwen.log#L14247) |
| 09/12 21:17:21 | `ablation/devstral24b/d03__b7k__tr` | [followup_tb_devstral.log:12151](../logs/followup_tb_devstral.log#L12151) |
| 09/12 21:46:37 | `ablation/qwen35b/d05__b4k__ss` | [followup_tb_qwen.log:14372](../logs/followup_tb_qwen.log#L14372) |
| 09/12 22:03:34 | `ablation/devstral24b/d03__b7k__su-full` | [followup_tb_devstral.log:12282](../logs/followup_tb_devstral.log#L12282) |
| 09/12 22:45:40 | `ablation/qwen35b/d05__b4k__ss-partial` | [followup_tb_qwen.log:14504](../logs/followup_tb_qwen.log#L14504) |
| 09/12 23:00:15 | `ablation/devstral24b/d03__b7k__su-partial` | [followup_tb_devstral.log:12416](../logs/followup_tb_devstral.log#L12416) |
| 09/12 23:35:41 | `ablation/qwen35b/d03__b2k__tr` | [followup_tb_qwen.log:14632](../logs/followup_tb_qwen.log#L14632) |
| 09/13 00:09:39 | `ablation/devstral24b/d03__b7k__ss` | [followup_tb_devstral.log:12563](../logs/followup_tb_devstral.log#L12563) |
| 09/13 00:24:40 | `ablation/qwen35b/d03__b2k__su-full` | [followup_tb_qwen.log:14757](../logs/followup_tb_qwen.log#L14757) |
| 09/13 01:19:07 | `ablation/devstral24b/d03__b7k__ss-partial` | [followup_tb_devstral.log:12694](../logs/followup_tb_devstral.log#L12694) |
| 09/13 02:08:11 | `ablation/devstral24b/d07__b3k__tr` | [followup_tb_devstral.log:12829](../logs/followup_tb_devstral.log#L12829) |
| 09/13 02:08:42 | `ablation/qwen35b/d03__b2k__su-partial` | [followup_tb_qwen.log:14882](../logs/followup_tb_qwen.log#L14882) |
| 09/13 02:48:26 | `ablation/devstral24b/d07__b3k__su-full` | [followup_tb_devstral.log:12958](../logs/followup_tb_devstral.log#L12958) |
| 09/13 03:51:21 | `ablation/qwen35b/d03__b2k__ss` | [followup_tb_qwen.log:15007](../logs/followup_tb_qwen.log#L15007) |
| 09/13 04:08:42 | `ablation/devstral24b/d07__b3k__su-partial` | [followup_tb_devstral.log:13089](../logs/followup_tb_devstral.log#L13089) |
| 09/13 05:14:32 | `ablation/devstral24b/d07__b3k__ss` | [followup_tb_devstral.log:13224](../logs/followup_tb_devstral.log#L13224) |
| 09/13 05:16:24 | `ablation/qwen35b/d03__b2k__ss-partial` | [followup_tb_qwen.log:15132](../logs/followup_tb_qwen.log#L15132) |
| 09/13 06:45:35 | `ablation/devstral24b/d07__b3k__ss-partial` | [followup_tb_devstral.log:13354](../logs/followup_tb_devstral.log#L13354) |
| 09/13 06:50:50 | `ablation/qwen35b/d03__b3k__tr` | [followup_tb_qwen.log:15257](../logs/followup_tb_qwen.log#L15257) |
| 09/13 07:38:12 | `ablation/qwen35b/d03__b3k__su-full` | [followup_tb_qwen.log:15382](../logs/followup_tb_qwen.log#L15382) |
| 09/13 07:54:33 | `ablation/devstral24b/d07__b4k__tr` | [followup_tb_devstral.log:13487](../logs/followup_tb_devstral.log#L13487) |
| 09/13 08:43:21 | `ablation/qwen35b/d03__b3k__su-partial` | [followup_tb_qwen.log:15510](../logs/followup_tb_qwen.log#L15510) |
| 09/13 08:45:09 | `ablation/devstral24b/d07__b4k__su-full` | [followup_tb_devstral.log:13621](../logs/followup_tb_devstral.log#L13621) |
| 09/13 09:57:03 | `ablation/devstral24b/d07__b4k__su-partial` | [followup_tb_devstral.log:13754](../logs/followup_tb_devstral.log#L13754) |
| 09/13 10:12:49 | `ablation/qwen35b/d03__b3k__ss` | [followup_tb_qwen.log:15635](../logs/followup_tb_qwen.log#L15635) |
| 09/13 11:01:26 | `ablation/devstral24b/d07__b4k__ss` | [followup_tb_devstral.log:13889](../logs/followup_tb_devstral.log#L13889) |
| 09/13 11:03:13 | `ablation/qwen35b/d03__b3k__ss-partial` | [followup_tb_qwen.log:15760](../logs/followup_tb_qwen.log#L15760) |
| 09/13 12:15:28 | `ablation/qwen35b/d03__b4k__tr` | [followup_tb_qwen.log:15885](../logs/followup_tb_qwen.log#L15885) |
| 09/13 12:23:16 | `ablation/devstral24b/d07__b4k__ss-partial` | [followup_tb_devstral.log:14020](../logs/followup_tb_devstral.log#L14020) |
| 09/13 13:06:08 | `ablation/qwen35b/d03__b4k__su-full` | [followup_tb_qwen.log:16010](../logs/followup_tb_qwen.log#L16010) |
| 09/13 13:45:14 | `ablation/devstral24b/d07__b7k__tr` | [followup_tb_devstral.log:14174](../logs/followup_tb_devstral.log#L14174) |
| 09/13 14:07:55 | `ablation/qwen35b/d03__b4k__su-partial` | [followup_tb_qwen.log:16135](../logs/followup_tb_qwen.log#L16135) |
| 09/13 14:38:08 | `ablation/devstral24b/d07__b7k__su-full` | [followup_tb_devstral.log:14308](../logs/followup_tb_devstral.log#L14308) |
| 09/13 15:12:52 | `ablation/qwen35b/d03__b4k__ss` | [followup_tb_qwen.log:16260](../logs/followup_tb_qwen.log#L16260) |
| 09/13 15:52:19 | `ablation/devstral24b/d07__b7k__su-partial` | [followup_tb_devstral.log:14441](../logs/followup_tb_devstral.log#L14441) |
| 09/13 16:11:07 | `ablation/qwen35b/d03__b4k__ss-partial` | [followup_tb_qwen.log:16385](../logs/followup_tb_qwen.log#L16385) |
| 09/13 16:42:47 | `ablation/devstral24b/d07__b7k__ss` | [followup_tb_devstral.log:14572](../logs/followup_tb_devstral.log#L14572) |
| 09/13 17:19:48 | `ablation/qwen35b/d07__b2k__tr` | [followup_tb_qwen.log:16513](../logs/followup_tb_qwen.log#L16513) |
| 09/13 18:02:40 | `ablation/devstral24b/d07__b7k__ss-partial` | [followup_tb_devstral.log:14704](../logs/followup_tb_devstral.log#L14704) |
| 09/13 18:03:24 | `ablation/qwen35b/d07__b2k__su-full` | [followup_tb_qwen.log:16638](../logs/followup_tb_qwen.log#L16638) |
| 09/13 18:57:25 | `ablation/devstral24b/di__b3k__trc` | [followup_tb_devstral.log:14839](../logs/followup_tb_devstral.log#L14839) |
| 09/13 19:38:22 | `ablation/devstral24b/di__b3k__trc-su` | [followup_tb_devstral.log:14970](../logs/followup_tb_devstral.log#L14970) |
| 09/13 19:43:23 | `ablation/qwen35b/d07__b2k__su-partial` | [followup_tb_qwen.log:16763](../logs/followup_tb_qwen.log#L16763) |
| 09/13 20:41:08 | `ablation/devstral24b/di__b3k__trc-ss` | [followup_tb_devstral.log:15120](../logs/followup_tb_devstral.log#L15120) |
| 09/13 21:13:10 | `ablation/qwen35b/d07__b2k__ss` | [followup_tb_qwen.log:16888](../logs/followup_tb_qwen.log#L16888) |
| 09/13 21:49:32 | `ablation/devstral24b/di__b3k__otrc-tr` | [followup_tb_devstral.log:15248](../logs/followup_tb_devstral.log#L15248) |
| 09/13 22:41:24 | `ablation/qwen35b/d07__b2k__ss-partial` | [followup_tb_qwen.log:17013](../logs/followup_tb_qwen.log#L17013) |
| 09/13 22:50:17 | `ablation/devstral24b/di__b3k__otrc-su-partial` | [followup_tb_devstral.log:15378](../logs/followup_tb_devstral.log#L15378) |
| 09/14 00:04:34 | `ablation/qwen35b/d07__b3k__tr` | [followup_tb_qwen.log:17138](../logs/followup_tb_qwen.log#L17138) |
| 09/14 00:09:06 | `ablation/devstral24b/di__b3k__otrc-ss-partial` | [followup_tb_devstral.log:15509](../logs/followup_tb_devstral.log#L15509) |
| 09/14 00:49:25 | `ablation/qwen35b/d07__b3k__su-full` | [followup_tb_qwen.log:17266](../logs/followup_tb_qwen.log#L17266) |
| 09/14 01:21:03 | `ablation/devstral24b/di__b7k__trc` | [followup_tb_devstral.log:15639](../logs/followup_tb_devstral.log#L15639) |
| 09/14 02:10:44 | `ablation/devstral24b/di__b7k__trc-su` | [followup_tb_devstral.log:15768](../logs/followup_tb_devstral.log#L15768) |
| 09/14 02:14:50 | `ablation/qwen35b/d07__b3k__su-partial` | [followup_tb_qwen.log:17391](../logs/followup_tb_qwen.log#L17391) |
| 09/14 02:58:44 | `ablation/devstral24b/di__b7k__trc-ss` | [followup_tb_devstral.log:15899](../logs/followup_tb_devstral.log#L15899) |
| 09/14 03:31:08 | `ablation/qwen35b/d07__b3k__ss` | [followup_tb_qwen.log:17516](../logs/followup_tb_qwen.log#L17516) |
| 09/14 04:03:52 | `ablation/devstral24b/di__b7k__otrc-tr` | [followup_tb_devstral.log:16030](../logs/followup_tb_devstral.log#L16030) |
| 09/14 04:39:45 | `ablation/qwen35b/d07__b3k__ss-partial` | [followup_tb_qwen.log:17641](../logs/followup_tb_qwen.log#L17641) |
| 09/14 04:59:37 | `ablation/devstral24b/di__b7k__otrc-su-partial` | [followup_tb_devstral.log:16162](../logs/followup_tb_devstral.log#L16162) |
| 09/14 05:42:55 | `ablation/qwen35b/d07__b4k__tr` | [followup_tb_qwen.log:17766](../logs/followup_tb_qwen.log#L17766) |
| 09/14 05:54:59 | `ablation/devstral24b/di__b7k__otrc-ss-partial` | [followup_tb_devstral.log:16293](../logs/followup_tb_devstral.log#L16293) |
| 09/14 06:37:48 | `ablation/qwen35b/d07__b4k__su-full` | [followup_tb_qwen.log:17893](../logs/followup_tb_qwen.log#L17893) |
| 09/14 07:50:58 | `ablation/qwen35b/d07__b4k__su-partial` | [followup_tb_qwen.log:18018](../logs/followup_tb_qwen.log#L18018) |
| 09/14 09:04:56 | `ablation/qwen35b/d07__b4k__ss` | [followup_tb_qwen.log:18143](../logs/followup_tb_qwen.log#L18143) |
| 09/14 10:06:20 | `ablation/qwen35b/d07__b4k__ss-partial` | [followup_tb_qwen.log:18272](../logs/followup_tb_qwen.log#L18272) |
| 09/14 11:04:28 | `ablation/qwen35b/di__b2k__trc` | [followup_tb_qwen.log:18416](../logs/followup_tb_qwen.log#L18416) |
| 09/14 11:51:50 | `ablation/qwen35b/di__b2k__trc-su` | [followup_tb_qwen.log:18541](../logs/followup_tb_qwen.log#L18541) |
| 09/14 13:37:59 | `ablation/qwen35b/di__b2k__trc-ss` | [followup_tb_qwen.log:18666](../logs/followup_tb_qwen.log#L18666) |
| 09/14 15:04:11 | `ablation/qwen35b/di__b2k__otrc-tr` | [followup_tb_qwen.log:18791](../logs/followup_tb_qwen.log#L18791) |
| 09/14 16:01:37 | `ablation/qwen35b/di__b2k__otrc-su-partial` | [followup_tb_qwen.log:18919](../logs/followup_tb_qwen.log#L18919) |
| 09/14 17:21:40 | `ablation/qwen35b/di__b2k__otrc-ss-partial` | [followup_tb_qwen.log:19047](../logs/followup_tb_qwen.log#L19047) |
| 09/14 18:47:52 | `ablation/qwen35b/di__b4k__trc` | [followup_tb_qwen.log:19172](../logs/followup_tb_qwen.log#L19172) |
| 09/14 19:42:43 | `ablation/qwen35b/di__b4k__trc-su` | [followup_tb_qwen.log:19298](../logs/followup_tb_qwen.log#L19298) |
| 09/14 20:47:49 | `ablation/qwen35b/di__b4k__trc-ss` | [followup_tb_qwen.log:19424](../logs/followup_tb_qwen.log#L19424) |
| 09/14 21:51:24 | `ablation/qwen35b/di__b4k__otrc-tr` | [followup_tb_qwen.log:19549](../logs/followup_tb_qwen.log#L19549) |
| 09/14 22:49:52 | `ablation/qwen35b/di__b4k__otrc-su-partial` | [followup_tb_qwen.log:19674](../logs/followup_tb_qwen.log#L19674) |
| 09/14 23:57:17 | `ablation/qwen35b/di__b4k__otrc-ss-partial` | [followup_tb_qwen.log:19802](../logs/followup_tb_qwen.log#L19802) |
| 09/16 15:13:43 | `ablation/glm47flash/d03__b2k__tr` | [followup_tb_glm_ablation_gpu0-3.log:2](../logs/followup_tb_glm_ablation_gpu0-3.log#L2) |
| 09/16 15:13:43 | `ablation/glm47flash/di__b2k__trc` | [followup_tb_glm_ablation_gpu4-7.log:2](../logs/followup_tb_glm_ablation_gpu4-7.log#L2) |
| 09/16 16:20:41 | `ablation/glm47flash/di__b2k__trc-su` | [followup_tb_glm_ablation_gpu4-7.log:127](../logs/followup_tb_glm_ablation_gpu4-7.log#L127) |
| 09/16 16:21:16 | `ablation/glm47flash/d03__b2k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:127](../logs/followup_tb_glm_ablation_gpu0-3.log#L127) |
| 09/16 17:42:49 | `ablation/glm47flash/di__b2k__trc-ss` | [followup_tb_glm_ablation_gpu4-7.log:249](../logs/followup_tb_glm_ablation_gpu4-7.log#L249) |
| 09/16 20:44:44 | `model_ablation/qwen35b-sum-qwen35-9b-smoke/d05__b3k__su-full` | [followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log:3](../logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b-smoke.log#L3) |
| 09/23 13:11:58 | `model_ablation/qwen35b-sum-qwen35-9b/d05__b3k__su-full` | [followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:3](../logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L3) |
| 09/23 14:30:09 | `model_ablation/qwen35b-sum-qwen35-9b/di__b3k__trc-su` | [followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log:133](../logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log#L133) |
| 09/23 16:25:42 | `model_ablation/qwen35b-sum-gemma4-12b-smoke/d05__b3k__su-full` | [followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b-smoke.log:3](../logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b-smoke.log#L3) |
| 09/23 16:32:16 | `model_ablation/qwen35b-sum-gemma4-12b/d05__b3k__su-full` | [followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:3](../logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L3) |
| 09/23 17:42:40 | `model_ablation/qwen35b-sum-gemma4-12b/di__b3k__trc-su` | [followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log:130](../logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log#L130) |
| 09/23 20:38:25 | `prefix_cache_ablation/qwen35b-noprefixcache/d05__b3k__tr` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:4](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L4) |
| 09/23 20:38:25 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__trc` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:4](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L4) |
| 09/23 21:25:57 | `prefix_cache_ablation/qwen35b-noprefixcache/d05__b3k__su-full` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:132](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L132) |
| 09/23 21:30:13 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__trc-su` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:136](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L136) |
| 09/23 22:51:51 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__trc-ss` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:264](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L264) |
| 09/23 22:57:27 | `prefix_cache_ablation/qwen35b-noprefixcache/d05__b3k__su-partial` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:260](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L260) |
| 09/24 00:03:54 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__otrc-tr` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:392](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L392) |
| 09/24 00:08:25 | `prefix_cache_ablation/qwen35b-noprefixcache/d05__b3k__ss` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:388](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L388) |
| 09/24 00:55:01 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__otrc-su-partial` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:520](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L520) |
| 09/24 01:28:00 | `prefix_cache_ablation/qwen35b-noprefixcache/d05__b3k__ss-partial` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:516](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L516) |
| 09/24 02:09:06 | `prefix_cache_ablation/qwen35b-noprefixcache/di__b3k__otrc-ss-partial` | [followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log:648](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log#L648) |
| 09/24 02:46:53 | `prefix_cache_ablation/qwen35b-noprefixcache/di__binf__fc` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:644](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L644) |
| 09/24 04:01:54 | `prefix_cache_ablation/qwen35b-noprefixcache/di__binf__otrc` | [followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log:772](../logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log#L772) |
| 09/26 08:48:54 | `ablation/glm47flash/d03__b2k__tr` | [followup_tb_glm_ablation_gpu0-3.log:201](../logs/followup_tb_glm_ablation_gpu0-3.log#L201) |
| 09/26 08:48:55 | `ablation/glm47flash/d03__b2k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:217](../logs/followup_tb_glm_ablation_gpu0-3.log#L217) |
| 09/26 08:53:24 | `ablation/glm47flash/d03__b2k__tr` | [followup_tb_glm_ablation_gpu0-3.log:222](../logs/followup_tb_glm_ablation_gpu0-3.log#L222) |
| 09/26 08:53:25 | `ablation/glm47flash/d03__b2k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:238](../logs/followup_tb_glm_ablation_gpu0-3.log#L238) |
| 09/26 09:18:35 | `ablation/glm47flash/d03__b2k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:294](../logs/followup_tb_glm_ablation_gpu0-3.log#L294) |
| 09/26 10:45:03 | `ablation/glm47flash/d03__b2k__ss` | [followup_tb_glm_ablation_gpu0-3.log:421](../logs/followup_tb_glm_ablation_gpu0-3.log#L421) |
| 09/26 12:11:21 | `ablation/glm47flash/d03__b2k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:547](../logs/followup_tb_glm_ablation_gpu0-3.log#L547) |
| 09/26 13:32:07 | `ablation/glm47flash/d03__b3k__tr` | [followup_tb_glm_ablation_gpu0-3.log:675](../logs/followup_tb_glm_ablation_gpu0-3.log#L675) |
| 09/26 14:28:40 | `ablation/glm47flash/d03__b3k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:802](../logs/followup_tb_glm_ablation_gpu0-3.log#L802) |
| 09/26 15:47:47 | `ablation/glm47flash/d03__b3k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:938](../logs/followup_tb_glm_ablation_gpu0-3.log#L938) |
| 09/26 17:08:21 | `ablation/glm47flash/d03__b3k__ss` | [followup_tb_glm_ablation_gpu0-3.log:1071](../logs/followup_tb_glm_ablation_gpu0-3.log#L1071) |
| 09/26 18:24:19 | `ablation/glm47flash/d03__b3k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:1204](../logs/followup_tb_glm_ablation_gpu0-3.log#L1204) |
| 09/26 19:45:18 | `ablation/glm47flash/d03__b5k__tr` | [followup_tb_glm_ablation_gpu0-3.log:1331](../logs/followup_tb_glm_ablation_gpu0-3.log#L1331) |
| 09/26 20:41:01 | `ablation/glm47flash/d03__b5k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:1461](../logs/followup_tb_glm_ablation_gpu0-3.log#L1461) |
| 09/26 21:52:35 | `ablation/glm47flash/d03__b5k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:1588](../logs/followup_tb_glm_ablation_gpu0-3.log#L1588) |
| 09/26 23:08:36 | `ablation/glm47flash/d03__b5k__ss` | [followup_tb_glm_ablation_gpu0-3.log:1715](../logs/followup_tb_glm_ablation_gpu0-3.log#L1715) |
| 09/27 00:22:11 | `ablation/glm47flash/d03__b5k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:1845](../logs/followup_tb_glm_ablation_gpu0-3.log#L1845) |
| 09/27 01:44:25 | `ablation/glm47flash/d07__b2k__tr` | [followup_tb_glm_ablation_gpu0-3.log:1972](../logs/followup_tb_glm_ablation_gpu0-3.log#L1972) |
| 09/27 02:35:12 | `ablation/glm47flash/d07__b2k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:2099](../logs/followup_tb_glm_ablation_gpu0-3.log#L2099) |
| 09/27 04:06:37 | `ablation/glm47flash/d07__b2k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:2225](../logs/followup_tb_glm_ablation_gpu0-3.log#L2225) |
| 09/27 05:40:20 | `ablation/glm47flash/d07__b2k__ss` | [followup_tb_glm_ablation_gpu0-3.log:2352](../logs/followup_tb_glm_ablation_gpu0-3.log#L2352) |
| 09/27 07:07:28 | `ablation/glm47flash/d07__b2k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:2483](../logs/followup_tb_glm_ablation_gpu0-3.log#L2483) |
| 09/27 08:28:26 | `ablation/glm47flash/d07__b3k__tr` | [followup_tb_glm_ablation_gpu0-3.log:2613](../logs/followup_tb_glm_ablation_gpu0-3.log#L2613) |
| 09/27 09:17:18 | `ablation/glm47flash/d07__b3k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:2743](../logs/followup_tb_glm_ablation_gpu0-3.log#L2743) |
| 09/27 10:33:00 | `ablation/glm47flash/d07__b3k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:2873](../logs/followup_tb_glm_ablation_gpu0-3.log#L2873) |
| 09/27 11:49:08 | `ablation/glm47flash/d07__b3k__ss` | [followup_tb_glm_ablation_gpu0-3.log:3000](../logs/followup_tb_glm_ablation_gpu0-3.log#L3000) |
| 09/27 13:13:15 | `ablation/glm47flash/d07__b3k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:3126](../logs/followup_tb_glm_ablation_gpu0-3.log#L3126) |
| 09/27 14:29:27 | `ablation/glm47flash/d07__b5k__tr` | [followup_tb_glm_ablation_gpu0-3.log:3256](../logs/followup_tb_glm_ablation_gpu0-3.log#L3256) |
| 09/27 15:27:27 | `ablation/glm47flash/d07__b5k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:3383](../logs/followup_tb_glm_ablation_gpu0-3.log#L3383) |
| 09/27 16:45:05 | `ablation/glm47flash/d07__b5k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:3510](../logs/followup_tb_glm_ablation_gpu0-3.log#L3510) |
| 09/27 17:55:46 | `ablation/glm47flash/d07__b5k__ss` | [followup_tb_glm_ablation_gpu0-3.log:3637](../logs/followup_tb_glm_ablation_gpu0-3.log#L3637) |
| 09/27 19:21:04 | `ablation/glm47flash/d07__b5k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:3764](../logs/followup_tb_glm_ablation_gpu0-3.log#L3764) |
| 09/27 20:37:59 | `ablation/glm47flash/di__b2k__trc` | [followup_tb_glm_ablation_gpu0-3.log:3894](../logs/followup_tb_glm_ablation_gpu0-3.log#L3894) |
| 09/27 20:38:00 | `ablation/glm47flash/di__b2k__trc-su` | [followup_tb_glm_ablation_gpu0-3.log:3910](../logs/followup_tb_glm_ablation_gpu0-3.log#L3910) |
| 09/27 20:38:01 | `ablation/glm47flash/di__b2k__trc-ss` | [followup_tb_glm_ablation_gpu0-3.log:3926](../logs/followup_tb_glm_ablation_gpu0-3.log#L3926) |
| 09/27 22:03:51 | `ablation/glm47flash/di__b2k__otrc-tr` | [followup_tb_glm_ablation_gpu0-3.log:4051](../logs/followup_tb_glm_ablation_gpu0-3.log#L4051) |
| 09/27 23:14:19 | `ablation/glm47flash/di__b2k__otrc-su-partial` | [followup_tb_glm_ablation_gpu0-3.log:4178](../logs/followup_tb_glm_ablation_gpu0-3.log#L4178) |
| 09/28 00:43:40 | `ablation/glm47flash/di__b2k__otrc-ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:4307](../logs/followup_tb_glm_ablation_gpu0-3.log#L4307) |
| 09/28 02:21:22 | `ablation/glm47flash/di__b5k__trc` | [followup_tb_glm_ablation_gpu0-3.log:4434](../logs/followup_tb_glm_ablation_gpu0-3.log#L4434) |
| 09/28 03:14:00 | `ablation/glm47flash/di__b5k__trc-su` | [followup_tb_glm_ablation_gpu0-3.log:4561](../logs/followup_tb_glm_ablation_gpu0-3.log#L4561) |
| 09/28 04:33:25 | `ablation/glm47flash/di__b5k__trc-ss` | [followup_tb_glm_ablation_gpu0-3.log:4688](../logs/followup_tb_glm_ablation_gpu0-3.log#L4688) |
| 09/28 05:44:15 | `ablation/glm47flash/di__b5k__otrc-tr` | [followup_tb_glm_ablation_gpu0-3.log:4821](../logs/followup_tb_glm_ablation_gpu0-3.log#L4821) |
| 09/28 06:45:46 | `ablation/glm47flash/di__b5k__otrc-su-partial` | [followup_tb_glm_ablation_gpu0-3.log:4950](../logs/followup_tb_glm_ablation_gpu0-3.log#L4950) |
| 09/28 07:52:07 | `ablation/glm47flash/di__b5k__otrc-ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:5077](../logs/followup_tb_glm_ablation_gpu0-3.log#L5077) |
| 09/28 09:05:57 | `ablation/glm47flash/d05__b2k__tr` | [followup_tb_glm_ablation_gpu0-3.log:5210](../logs/followup_tb_glm_ablation_gpu0-3.log#L5210) |
| 09/28 10:06:35 | `ablation/glm47flash/d05__b2k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:5337](../logs/followup_tb_glm_ablation_gpu0-3.log#L5337) |
| 09/28 11:40:54 | `ablation/glm47flash/d05__b2k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:5465](../logs/followup_tb_glm_ablation_gpu0-3.log#L5465) |
| 09/28 13:09:58 | `ablation/glm47flash/d05__b2k__ss` | [followup_tb_glm_ablation_gpu0-3.log:5591](../logs/followup_tb_glm_ablation_gpu0-3.log#L5591) |
| 09/28 14:38:04 | `ablation/glm47flash/d05__b2k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:5719](../logs/followup_tb_glm_ablation_gpu0-3.log#L5719) |
| 09/28 16:06:47 | `ablation/glm47flash/d05__b5k__tr` | [followup_tb_glm_ablation_gpu0-3.log:5844](../logs/followup_tb_glm_ablation_gpu0-3.log#L5844) |
| 09/28 16:54:42 | `ablation/glm47flash/d05__b5k__su-full` | [followup_tb_glm_ablation_gpu0-3.log:5974](../logs/followup_tb_glm_ablation_gpu0-3.log#L5974) |
| 09/28 18:11:06 | `ablation/glm47flash/d05__b5k__su-partial` | [followup_tb_glm_ablation_gpu0-3.log:6104](../logs/followup_tb_glm_ablation_gpu0-3.log#L6104) |
| 09/28 19:10:16 | `ablation/glm47flash/d05__b5k__ss` | [followup_tb_glm_ablation_gpu0-3.log:6234](../logs/followup_tb_glm_ablation_gpu0-3.log#L6234) |
| 09/28 20:18:19 | `ablation/glm47flash/d05__b5k__ss-partial` | [followup_tb_glm_ablation_gpu0-3.log:6361](../logs/followup_tb_glm_ablation_gpu0-3.log#L6361) |

## Limits on timestamps and completion claims (09/06–09/28)

- Launch times come from log headers. Rows marked `(mtime)` or `(dir name)` use file or directory timestamps, or timestamps embedded in names, because those launchers do not print a start time. vLLM start times come from the first `INFO MM-DD HH:MM:SS` line of each server log. Server logs that were later overwritten (September 6–11) cannot be dated.
- The partial Qwen ablation from September 3 has no cell entries after `d05__b4k__ss-partial` (09/04 10:18). Its last Harbor batch (`qwen35b-structured-summarize-partial-r3`) started at 09/04 11:54:23. The cells were redone by the September 12 launch.
- The Main rows for the 09/05 Devstral and GLM launches in the first table said completion was not confirmed. The Devstral launch did log completion (09/06 13:07:48), but both launches used the wrong GPU assignment, and their results were archived (see [EXPERIMENT_LOG_TB.md §4(d)](EXPERIMENT_LOG_TB.md)).
- Final state on disk: Main has 13 cells and 1,560 rows per model (Qwen, Devstral, GLM). ablation has 52 cells and 2,340 rows per model. Summarizer ablation has 90 rows each for Qwen3.5-9B and Gemma-4-12B. Prefix-cache ablation has 13 cells and 585 rows. The `-smoke` result directories under `model_ablation/` still exist; the `rm -rf model_ablation/qwen35b-sum-gemma4-12b-smoke/` in history was run from a different directory.
- After 09/28 21:22:41, no new launch appears in the logs. `.bash_history` was last written on 09/27 03:51, so later shell commands, if any, are not recorded. As of 09/29 18:19, the only related process is the GLM vLLM server started on 09/26 08:44:53 (port 8003). Only `logs/dashboard-watch.log` is still being updated.
- Commands that do not run experiments are omitted from the table, except archive and re-verification steps that change aggregates. These include git commits and pushes, `analysis/aggregate_terminalbench_results.py`, `cp -r ICLR_results/terminalbench /home/rs67788/projects/agentCtx/ICLR_results/` (09/15), `ssh albus ... du -sh` (09/24), GPU/NIC/NUMA inspection (`lspci -tv`, `/proc/<pid>/environ`), and Podman service checks.
