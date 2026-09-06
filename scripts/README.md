# Scripts

Run the examples below from the repository root. Shared Python implementation
lives in `src/agentctx/`; this directory contains command-line entry points and
operational launchers.

| Location | Purpose |
| --- | --- |
| `run_experiment.py` | General SWE-Bench / Terminal-Bench experiment CLI. |
| `run_experiment_iclr.py` | Run a cell in the canonical ICLR results tree. |
| `calibration/` | Collect full-context trajectories and calibrate token budgets. |
| `expansions/` | Launch model grids and additional repetitions. |
| `serving/` | Start model-specific vLLM servers. |
| `harbor/` | Prebuild Terminal-Bench images and configure Harbor tasks. |

## Calibration

- `run_budget_calibration_sb.py` / `.sh`: canonical SWE-Bench P100 FC run_1.
- `run_budget_calibration_tb.py` / `.sh`: canonical Terminal-Bench FC runs,
  including rootless and subuid subsets.
- `run_model_budget_calibration.sh`: earlier 60-trajectory calibration using
  ABL-30 and reference trigger rates; distinct from the canonical P100 workflow.

```bash
bash scripts/calibration/run_budget_calibration_sb.sh devstral
bash scripts/calibration/run_budget_calibration_tb.sh qwen-rootless
```

## Expansions

- `run_agent_models_expansion.sh`: SWE-Bench Devstral / GLM grids.
- `run_agent_models_expansion_notified.sh`: the same launcher with Slack notices.
- `run_agent_models_expansion_tb.sh`: Terminal-Bench Qwen / Devstral / GLM grids.
- `run_qwen_tb_with_slack.sh`: Qwen Terminal-Bench grid with Slack notices.
- `run_terminalbench_rootless_fc_expansion.sh`: FC run_2 through run_5 on the
  Terminal-Bench rootless subset.

```bash
bash scripts/expansions/run_agent_models_expansion.sh devstral
bash scripts/expansions/run_agent_models_expansion_tb.sh qwen both
```

## Serving and Harbor setup

`serving/start_vllm_{qwen35,devstral,glm47flash}.sh` starts the selected model.
Check each script's environment overrides and GPU requirements before use.

`harbor/tb_harbor_prebuild_images.sh` builds task images and calls
`harbor/configure_tb_harbor_prebuilt.py` to update task and Compose configuration.

```bash
bash scripts/serving/start_vllm_devstral.sh
bash scripts/harbor/tb_harbor_prebuild_images.sh hello-world
```

The grouped scripts previously lived directly under `scripts/`. Use their new
paths in local launch commands and any external job definitions. Arguments,
environment overrides, and result locations are unchanged.
