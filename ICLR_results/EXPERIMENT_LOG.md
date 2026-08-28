# ICLR 2027 Experiment Log
Experiment Plam → [exp_plans/FOLLOWUP_EXPERIMENTS.md](../exp_plans/FOLLOWUP_EXPERIMENTS.md)

## Follow-up 1 — Runs/task 2 → 3
- Started: 2026-08-23 17:24:53 CDT
- Code version used:  `27606ac14f4ff4bb96caf429984ad8fd26325cba`
    - Provenance note: The experiment was launched before this change was
    committed. At launch, HEAD was `f8cd6f9`; the relevant working-tree changes
    were committed unchanged as `27606ac`.
- Results root: `results/ablations/`
    - Canonical location: `data/swebench/ablations/`
    - `results/ablations/` is a symlink to the canonical location above.
    - Each experiment cell stores its aggregate metadata in
      `<results-root>/<cell>/experiment_results.json` and per-task artifacts in
      `<results-root>/<cell>/<instance_id>/<condition>/run_3/`.
    - The same cell directories also contain the earlier `run_1` and `run_2`;
      this follow-up experiment adds the `run_3` artifacts.
- Experiment cell directories:
    - P100: `p100-singles-{10000,15000,20000}`,
      `p100-trc-{10000,15000,20000}`,
      `p100-otrc-{10000,15000,20000}`, and `p100-inf`
    - ABL-30 depth ablations: `p100-depth{30,70}-singles-{10000,15000,20000}`
    - ABL-30 existing/canonical cells: `timing-{10k,20k}`,
      `partial-{10000,15000,20000}`, `stacked-{10000,15000,20000}`,
      `otrc-stacked-{10000,15000,20000}`,
      `qwen3.5-35B-A3B_15k_Fullrun`, and `qwen35-a3b_online-trc`
- Runtime logs: `logs/run3_expansion.log` and
  `logs/run3_expansion.nohup.log` (local, gitignored)
- [DONE] 2026-08-28: Ran `scripts/archive_and_organize_qwen35b_swebench.py`
  (HEAD `cb5d3771791cbca0e05f1ff1f71177ec4e902051`, script last changed in
  `8f9a50bf8fe7943059148af11cc09525453a0eed`) to copy the result files under
  `ICLR_results/`:
  ```bash
  python3 scripts/archive_and_organize_qwen35b_swebench.py \
    --backup-root /home/ak58925/agentCtx_backups/run3-complete-2026-08-28
  ```
  All 65 cells (`main/qwen35b`: 35, `ablation/qwen35b`: 30) reported COMPLETE.

## Follow-up 2 — Agent model expansion

### Budget calibration protocol

Calibrate each model independently from context growth in **60 uncompressed
trajectories** (ABL-30 × 2 runs). For every trajectory, take
`max(step_prompt_tokens)`, then choose `A/P/B` thresholds whose compression
trigger rates match the Qwen3.5 reference rates `97% / 88% / 76%` within ±5pp.
The calculation and 1K rounding are implemented in
`Review1/calibrate_budgets.py`; patch evaluation is not required.

1. Start the model server and verify its `/v1/models` endpoint.
2. Collect FC trajectories and calculate budgets (resumable):

   ```bash
   # Devstral reproduction/verification
   setsid bash scripts/run_model_budget_calibration.sh devstral \
     > logs/devstral_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/devstral_budget_calibration.pid

   # GLM calibration (after its configs and server launcher exist)
   setsid bash scripts/run_model_budget_calibration.sh glm \
     > logs/glm_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/glm_budget_calibration.pid
   ```

3. Inspect the generated file and require `ALL_WITHIN_TOLERANCE=true`:

   ```bash
   cat logs/devstral-2_calibrated_budgets.sh
   cat logs/glm47-flash_calibrated_budgets.sh
   ```

   Expected Devstral reproduction: `A/P/B = 15000/20000/24000`, corresponding
   to approximately `98.3%/90.0%/75%` trigger rates. If a value collides after
   rounding or falls outside tolerance, stop for manual review; do not silently
   substitute Qwen budgets.

4. Pass the approved values to the expansion launcher. Devstral already uses
   the calibrated values as defaults; GLM remains explicit:

   ```bash
   source logs/glm47-flash_calibrated_budgets.sh
   GLM_A_BUDGET="$TIGHT_BUDGET" \
   GLM_P_BUDGET="$MEDIUM_BUDGET" \
   GLM_B_BUDGET="$LOOSE_BUDGET" \
     setsid bash scripts/run_agent_models_expansion.sh glm \
     > logs/agent_models_glm.out 2>&1 &
   echo $! > logs/agent_models_glm.pid
   ```

Artifacts to retain for provenance:

- `results/ablations/<model-tag>-inf/experiment_results.json`
- `logs/<model-tag>_budget_calibration.log`
- `logs/<model-tag>_calibrated_budgets.sh`
- the launch PID, code version, model ID, context-window setting, and approval
  decision recorded below

The reusable FC launcher below collects exactly `run_1` for every selected
task and writes it directly into the canonical ICLR cell. It then calculates
the percentile report and rebuilds `COVERAGE.csv` and `DASHBOARD.html`.

```bash
# SWE-Bench P100 (counts as the FC run_1 portion of 2.a or 2.b)
venv/bin/python scripts/run_budget_calibration.py \
  --benchmark swebench \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --tasks-file task_lists/p100_all_100_tasks.json

# Terminal-Bench (counts as 3.a only when this file is the frozen P80 cohort)
venv/bin/python scripts/run_budget_calibration.py \
  --benchmark terminalbench \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --tasks-file task_lists/<frozen-p80-tasks>.json
```

Outputs are stored under
`ICLR_results/{swebench|terminalbench}/main/<model>/di__binf__fc/`, including
`experiment_results.json` (all per-step prompt-token arrays), raw per-task
artifacts, `calibration_report.txt`, and `calibrated_budgets.sh`. FC never
invokes a summarizer, so only the agent model is configured for this stage.
The currently checked-in `task_lists/tbench_tasks.json` contains the older
20-task cohort; it is useful for calibration but does not by itself satisfy
the planned TB:P80 coverage for 3.a.

- [TODO] Start Devstral: `bash scripts/start_vllm_devstral.sh`.
- [TODO] Run the Devstral calibration reproduction and confirm `A/P/B = 15K/20K/24K`.
- [TODO] Launch Devstral: `setsid bash scripts/run_agent_models_expansion.sh devstral > logs/agent_models_devstral.out 2>&1 &`.
- [TODO] Create the GLM agent/OTRC configs and vLLM launcher, then calibrate its `A/P/B` budgets with the protocol above.
- [TODO] Start and verify the GLM vLLM server on the configured endpoint.
- [TODO] Launch GLM: `GLM_A_BUDGET=<A> GLM_P_BUDGET=<P> GLM_B_BUDGET=<B> setsid bash scripts/run_agent_models_expansion.sh glm > logs/agent_models_glm.out 2>&1 &`.
- [TODO] Record the start time, code version, PID, calibrated budgets, and runtime log paths here.
