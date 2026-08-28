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

Calibrate each model independently from context growth in **100 uncompressed
trajectories** (SB:P100 × run_1). These are stored directly as the FC run_1
portion of experiment 2.a/2.b, so calibration does not duplicate agent runs.
For every trajectory, take
`max(step_prompt_tokens)`, then choose `A/P/B` thresholds whose compression
trigger rates match the Qwen3.5 reference rates `97% / 88% / 76%` within ±5pp.
The calculation and 1K rounding are implemented in
`Review1/calibrate_budgets.py`.

1. Start the model server and verify its `/v1/models` endpoint.
2. Collect FC trajectories and calculate budgets (resumable):

   ```bash
   # Devstral (also produces experiment 2.a FC run_1)
   setsid venv/bin/python scripts/run_budget_calibration_sb.py \
     --model-key devstral24b \
     --agent-config configs/config-devstral-vllm.yaml \
     > logs/devstral_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/devstral_budget_calibration.pid

   # GLM (also produces experiment 2.b FC run_1; after its config exists)
   setsid venv/bin/python scripts/run_budget_calibration_sb.py \
     --model-key glm47flash \
     --agent-config configs/config-glm47flash-vllm.yaml \
     > logs/glm_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/glm_budget_calibration.pid
   ```

3. Inspect the generated file and require `ALL_WITHIN_TOLERANCE=true`:

   ```bash
   cat ICLR_results/swebench/main/devstral24b/di__binf__fc/calibrated_budgets.sh
   cat ICLR_results/swebench/main/glm47flash/di__binf__fc/calibrated_budgets.sh
   ```

   The earlier ABL-30 × 2 Devstral estimate was `A/P/B = 15000/20000/24000`.
   Treat it as a comparison point, not a required result: the canonical P100 ×
   run_1 distribution may differ. If a value collides after rounding or falls
   outside tolerance, stop for manual review; do not silently substitute Qwen
   budgets.

4. Pass the approved values to the expansion launcher. Devstral already uses
   the calibrated values as defaults; GLM remains explicit:

   ```bash
   source ICLR_results/swebench/main/glm47flash/di__binf__fc/calibrated_budgets.sh
   GLM_A_BUDGET="$TIGHT_BUDGET" \
   GLM_P_BUDGET="$MEDIUM_BUDGET" \
   GLM_B_BUDGET="$LOOSE_BUDGET" \
     setsid bash scripts/run_agent_models_expansion.sh glm \
     > logs/agent_models_glm.out 2>&1 &
   echo $! > logs/agent_models_glm.pid
   ```

Artifacts to retain for provenance:

- `ICLR_results/swebench/main/<model>/di__binf__fc/experiment_results.json`
- `ICLR_results/swebench/main/<model>/di__binf__fc/<instance>/full-context/run_1/`
- `ICLR_results/swebench/main/<model>/di__binf__fc/fc_context_distribution.json`
- `ICLR_results/swebench/main/<model>/di__binf__fc/{calibration_report.txt,calibrated_budgets.sh}`
- the launch PID, code version, model ID, context-window setting, and approval
  decision recorded below

The reusable FC launcher below collects exactly `run_1` for every selected
task and writes it directly into the canonical ICLR cell. It then calculates
the percentile report and rebuilds `COVERAGE.csv` and `DASHBOARD.html`.

```bash
# SWE-Bench P100 (counts as the FC run_1 portion of 2.a or 2.b)
venv/bin/python scripts/run_budget_calibration_sb.py \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --tasks-file task_lists/p100_all_100_tasks.json

# GLM (after adding its model config)
venv/bin/python scripts/run_budget_calibration_sb.py \
  --model-key glm47flash \
  --agent-config configs/config-glm47flash-vllm.yaml \
  --tasks-file task_lists/p100_all_100_tasks.json
```

Outputs are stored under
`ICLR_results/swebench/main/<model>/di__binf__fc/`, including
`experiment_results.json` (all per-step prompt-token arrays), raw per-task
artifacts, `fc_context_distribution.json`, `calibration_report.txt`, and
`calibrated_budgets.sh`. FC never
invokes a summarizer, so only the agent model is configured for this stage.
The calibration report explicitly filters `run_num == 1`, so adding run_2 and
run_3 to the same canonical FC cell later cannot change the saved calibration
distribution.
SWE-Bench patch evaluation is enabled by default so these are complete
experimental run_1 records; pass `--skip-eval` only when evaluation will be
resumed separately later.

- [TODO] Start Devstral: `bash scripts/start_vllm_devstral.sh`.
- [TODO] Run the Devstral P100/run_1 calibration, compare it with the earlier
  `15K/20K/24K` estimate, and record the reviewed decision.
- [TODO] Launch Devstral: `setsid bash scripts/run_agent_models_expansion.sh devstral > logs/agent_models_devstral.out 2>&1 &`.
- [TODO] Create the GLM agent/OTRC configs and vLLM launcher, then calibrate its `A/P/B` budgets with the protocol above.
- [TODO] Start and verify the GLM vLLM server on the configured endpoint.
- [TODO] Launch GLM: `GLM_A_BUDGET=<A> GLM_P_BUDGET=<P> GLM_B_BUDGET=<B> setsid bash scripts/run_agent_models_expansion.sh glm > logs/agent_models_glm.out 2>&1 &`.
- [TODO] Record the start time, code version, PID, calibrated budgets, and runtime log paths here.
