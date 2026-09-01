# ICLR 2027 Experiment Log
Experiment Plan → [exp_plans/FOLLOWUP_EXPERIMENTS.md](../exp_plans/FOLLOWUP_EXPERIMENTS.md)

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

The Devstral SB:P100 budget calibration was run with code from commit
`0d42a9b4c9a9706e0b05eb3c1128d9b117369414` (calibration artifacts completed
2026-08-28 14:06 CDT).

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

4. Review the calibration output, record the final adopted values, and pass
   them to the expansion launcher. Devstral uses the finalized
   `A/P/B = 17000/21000/24000` defaults; GLM remains explicit:

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

### Devstral (2.a)/(2.c) launch commands

The Devstral (2.a)/(2.c) expansion was initially launched with code from
commit `20df6a5362a3611add3991d3a07aa4fd5b87437a` on 2026-08-29 00:30 CDT.
It was resumed on 2026-08-31 02:34:19 CDT with launcher PID `2882597`;
`logs/followup_agent_models_devstral_launcher.log` begins this resume at the
`main/devstral24b/d05__b21k__tr` cell. The launcher and experiment logs were
still being updated on 2026-08-31 13:37 CDT.

The experiment worker concurrency is fixed at **16**. The vLLM
`--max-num-seqs 64` setting is the server-side capacity, not the experiment
worker concurrency.

```bash
cd /home/ak58925/agentCtx

# Inspect the existing experiment and model-server processes.
pgrep -af 'run_agent_models_expansion|run_experiment_iclr|swebench_single|minisweagent'
pgrep -af 'vllm.entrypoints.openai.api_server'
nvidia-smi
ss -ltnp | grep -E ':8000|:8001|:8002|:8003' || true

# Stop the previous GLM-4.7-Flash vLLM server found on port 8003.
# Process at inspection time:
# 3783208 .../venv-glm-cu129-clean/bin/python -m
# vllm.entrypoints.openai.api_server --model zai-org/GLM-4.7-Flash
# --port 8003 ...
kill -TERM 3783208

# Wait for and verify shutdown.
for i in $(seq 1 30); do
    kill -0 3783208 2>/dev/null || break
    sleep 2
done
ps -fp 3783208
pgrep -af 'vllm.entrypoints.openai.api_server' || echo 'vLLM stopped'
nvidia-smi

# Start Devstral-Small-2-24B-Instruct-2512 on GPUs 0,1,2,3 / port 8002.
bash scripts/start_vllm_devstral.sh

# Inspect startup. Exit tail with Ctrl-C after the server is ready.
tail -f logs/vllm_devstral.log

# Verify the model endpoint and process.
curl -fsS http://localhost:8002/v1/models | python3 -m json.tool
ps -fp "$(cat logs/vllm_devstral.pid)"
nvidia-smi

# Launch both (2.a) P100 main and (2.c) ABL-30 ablation, with concurrency 16.
nohup env MAX_WORKERS=16 RUN_EVAL=1 \
    bash scripts/run_agent_models_expansion.sh devstral \
    > logs/followup_agent_models_devstral_launcher.log 2>&1 &
echo $! | tee logs/followup_agent_models_devstral_launcher.pid

# Verify that the runner received --max-workers 16.
ps -fp "$(cat logs/followup_agent_models_devstral_launcher.pid)"
pgrep -af 'run_experiment_iclr.py'

# Monitor experiment and launcher logs.
tail -f logs/followup_agent_models_devstral.log
tail -f logs/followup_agent_models_devstral_launcher.log
```

The launcher runs (2.a) first and then (2.c), and skips completed
task/condition/run keys when resumed.

#### Devstral status — 2026-08-31 13:45 CDT

- Calibration completed 2026-08-28 14:06 CDT from 100 FC run_1 trajectories.
  The trigger-rate-matching report produced the reference values
  `A/P/B = 16000/19000/23000`, trigger rates `96%/90%/77%`, and
  `ALL_WITHIN_TOLERANCE=true`. After review, the experiment's final adopted
  budgets were `A/P/B = 17000/21000/24000` using the P5/P15/P25 rule.
- The initial launch used commit
  `20df6a5362a3611add3991d3a07aa4fd5b87437a`; the current resume began at
  2026-08-31 02:34:19 CDT with launcher PID `2882597`.
- Runtime logs: `logs/followup_agent_models_devstral_launcher.log` and
  `logs/followup_agent_models_devstral.log`; model-server log and recorded PID:
  `logs/vllm_devstral.log` and `logs/vllm_devstral.pid` (`2253428`).
- Current P100 coverage snapshot: FC, OTRC, TR@21k, and SU-full@21k are
  complete at 300/300 runs each. SU-partial@21k is in progress (108/300 rows
  on disk, 37/100 tasks represented in the latest `COVERAGE.csv`). The ABL-30
  phase has not started because the launcher runs it after the P100 phase.
- **Final budget decision:** Devstral runs use `17000/21000/24000`. P100 main
  uses the 21k medium budget; the later ABL-30 phase uses all three budgets.
  The launcher changes were uncommitted when the 2026-08-31 02:34 resume began
  and were later committed unchanged as
  `7b4bbe407a05c769d495af2219e9110c10d02c53` (`fix: FIX BUDGETS`) at 13:44
  CDT. Existing 21k results are therefore part of the intended grid and do not
  require replacement or backfill at 19k.
- [TODO] Record final completion status and end time after the launcher exits.
- [TODO] Create the GLM agent/OTRC configs and vLLM launcher, then calibrate its `A/P/B` budgets with the protocol above.
- [TODO] Start and verify the GLM vLLM server on the configured endpoint.
- [TODO] Launch GLM: `GLM_A_BUDGET=<A> GLM_P_BUDGET=<P> GLM_B_BUDGET=<B> setsid bash scripts/run_agent_models_expansion.sh glm > logs/agent_models_glm.out 2>&1 &`.
- [TODO] Record the start time, code version, PID, calibrated budgets, and runtime log paths here.
