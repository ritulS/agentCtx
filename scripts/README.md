# Scripts

Run the examples below from the repository root. Shared Python implementation
lives in `src/agentctx/`; this directory contains command-line entry points and
operational launchers.

| Location | Purpose |
| --- | --- |
| `run_experiment.py` | General SWE-Bench / Terminal-Bench experiment CLI (`agentctx.experiments.runner`). |
| `run_experiment_iclr.py` | Run a cell in the canonical ICLR results tree (`agentctx.experiments.iclr`). |
| `swebench_eval_wrapper.py` | SWE-bench harness wrapper the SWE-bench adapter launches for evaluation (thread cap inside eval containers). |
| `notify_run.sh` | Run any launcher with Slack start / completion / failure notices (see below). |
| `calibration/` | Collect full-context trajectories and calibrate token budgets. |
| `expansions/` | Launch model grids, additional repetitions and the summarizer / prefix-cache ablations. |
| `serving/` | Start and stop model-specific vLLM servers. |
| `harbor/` | Prebuild Terminal-Bench images, configure Harbor tasks, check worker cancellation. |
| `maintenance/` | Audit, re-evaluate, repair and archive existing results. |

## Calibration

- `run_budget_calibration_sb.py` / `.sh`: canonical SWE-Bench P100 FC run_1.
- `run_budget_calibration_tb.py` / `.sh`: canonical Terminal-Bench 1.0 FC runs,
  including rootless and subuid subsets, and isolated native-context
  collections (`--calibration-dir`; see `DEVSTRAL_TB_NATIVE_CALIBRATION.md`,
  `GLM_TB_NATIVE_CALIBRATION.md`).
- `run_budget_calibration_tb2.sh`: Terminal-Bench 2.0 FC runs through the same
  Python launcher; `prepare_tb2_fc_resume.py` lists the tasks left for a resume.
- `run_model_budget_calibration.sh`: earlier 60-trajectory calibration using
  ABL-30 and reference trigger rates; distinct from the canonical P100 workflow.
- `log_vllm_prefix_cache.py`: vLLM `/metrics` prefix-cache recorder used by the
  isolated calibration mode.

```bash
bash scripts/calibration/run_budget_calibration_sb.sh devstral
bash scripts/calibration/run_budget_calibration_tb.sh qwen-rootless
```

## Expansions

- `run_agent_models_expansion.sh`: SWE-Bench Qwen / Devstral / GLM grids.
- `run_agent_models_expansion_tb.sh`: Terminal-Bench Qwen / Devstral / GLM grids.
- `run_glm_tb_ablation_split.sh {gpu0-3|gpu4-7}`: the GLM Terminal-Bench
  ablation split across two vLLM servers (sets `ABLATION_PARTS`, config and
  health URL per half, then launches through `notify_run.sh`).
- `run_terminalbench_rootless_fc_expansion.sh`: FC run_2 through run_5 on the
  Terminal-Bench rootless subset.
- `run_qwen_{swe,tb}_summarizer_ablation.sh`: summarizer-model ablation
  (`--summary-config`, `model_ablation` section).
- `run_qwen_{swe,tb}_prefix_cache_ablation.sh`: vLLM prefix-caching ablation
  (`prefix_cache_ablation` section).

```bash
bash scripts/expansions/run_agent_models_expansion.sh devstral
bash scripts/expansions/run_agent_models_expansion_tb.sh qwen both
```

### Slack notices: `notify_run.sh`

Every launcher above is plain; wrap it in `scripts/notify_run.sh` to run it
in the background with a start notice, a completion / failure notice with the
exit status and log path, signal forwarding (HUP / INT / TERM stop the
launcher and everything it spawned before the notice goes out) and an
optional per-experiment lock. The wrapper validates its arguments, takes the
lock and checks the webhook, then detaches (nohup + setsid) and prints the
wrapper PID; `kill <PID>` stops the run and posts a "killed" notice. The
launcher's stdout / stderr are appended to `--log` (default
`logs/<unit>.log`). Environment overrides of the launcher pass through
unchanged. `--foreground` keeps the run attached to the terminal (smoke
tests, sequential chains).

```bash
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'   # or ALLOW_NO_SLACK=1

# Terminal-Bench main grid (previously run_qwen_tb_main_with_slack.sh)
bash scripts/notify_run.sh --unit qwen-terminal-bench-main --lock qwen_tb_main \
    -- bash scripts/expansions/run_agent_models_expansion_tb.sh qwen main

# SWE-Bench model grid (previously run_agent_models_expansion_notified.sh)
MAX_WORKERS=16 RUN_EVAL=1 bash scripts/notify_run.sh --unit agent-model-expansion/glm \
    --log logs/followup_agent_models_glm_launcher.log \
    -- bash scripts/expansions/run_agent_models_expansion.sh glm

# Summarizer / prefix-cache ablations (previously *_notified.sh / *_with_slack.sh)
SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b \
    bash scripts/notify_run.sh --unit summarizer-ablation/swebench/qwen35b-sum-gemma4-12b \
    -- bash scripts/expansions/run_qwen_swe_summarizer_ablation.sh
bash scripts/notify_run.sh --unit qwen-terminal-bench-prefix-cache-ablation --lock qwen_tb_noprefixcache \
    -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh

# Attached, e.g. a one-task smoke test
bash scripts/notify_run.sh --foreground --unit smoke -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh
```

`--on-success '<command>'` runs a follow-up (for example a results summary)
after a clean exit; `--pid-file` records the launched command's PID for
chained scripts. `dashboard/notify_slack.py` is the notifier it calls
(`start <unit>` / `stop <unit> <result> <status> <log>`); `python3
dashboard/notify_slack.py test` checks the webhook. `tests/test_notify_run.py`
covers the wrapper.

## Serving and Harbor setup

`serving/start_vllm_{qwen35_prefix_cache_ablation,qwen35_prefix_cache,qwen35_no_prefix_cache,qwen35_9b,qwen35_swe_summarizer_ablation,devstral,glm47flash,summarizer}.sh`
start the selected model; `serving/stop_vllm.sh <pid file>` stops a server with
its process group. Check each script's environment overrides and GPU
requirements before use.

`harbor/tb_harbor_prebuild_images.sh` builds Terminal-Bench 1.0 task images and
calls `harbor/configure_tb_harbor_prebuilt.py` to update task and Compose
configuration; `harbor/tb2_harbor_prebuild_images.sh` does the same for
Terminal-Bench 2.0. `harbor/check_vllm_cancellation.py` exercises the Harbor
worker cancellation path against an idle vLLM server (`HARBOR_CANCELLATION.md`).

```bash
bash scripts/serving/start_vllm_devstral.sh
bash scripts/harbor/tb_harbor_prebuild_images.sh hello-world
```

## Maintenance

Post-hoc tools for existing result trees; none of them launches new agent runs
except the re-verification replays.

- `audit_tb_verdicts.py`, `replay_reverify_tb.py`: Terminal-Bench verdict audit
  and command-replay re-verification (`agentctx.benchmarks.replay_agent`).
- `build_reevaluation_candidates.py`, `reevaluate_swebench_candidates.py`:
  re-evaluate saved SWE-bench patches with stale or errored verdicts.
- `repair_token_log_transcription.py`: refresh result rows from their token logs.
- `archive_devstral_fc_r23.py`, `archive_qwen_ablation_seeded.sh`,
  `reuse_qwen_main_for_ablation.py`: archive or seed result cells.

The grouped scripts previously lived directly under `scripts/`; the Python
modules they import moved from `scripts/bench_adapters/`, `memory.py`,
`summary_config.py` and `tbench/` into `src/agentctx/` (a root-level
`memory.py` alias remains for the pinned mini-swe-agent commit). Use the new paths in
local launch commands and any external job definitions. Arguments, environment
overrides, and result locations are unchanged (`tests/` verifies this against
the pre-reorganization branch).
