#!/bin/bash
# Devstral-Small-2-24B-Instruct-2512  §c: 11 budgeted prims × 3 calibrated
# budgets at depth=0.5. Budgets locked from FC §a calibration on n=60:
#   TIGHT  = 15000  (98.3% trigger rate)
#   MEDIUM = 20000  (90.0% trigger rate)
#   LOOSE  = 24000  (~75% trigger rate; matches Qwen3.5 LOOSE target)
#
# 11 prims × 3 budgets × 30 tasks × 2 runs = 1,980 runs at canonical depth.
# Output dirs: results/ablations/devstral-2-budgeted-{15000,20000,24000}/
#
# Usage:  nohup bash scripts/run_devstral_budgeted_canonical.sh > logs/devstral_2_canonical.out 2>&1 &
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/devstral_2_canonical.log"
mkdir -p "$WS/logs"

TIGHT_BUDGET=15000
MEDIUM_BUDGET=20000
LOOSE_BUDGET=24000

echo "[$(date)] === Devstral §c: canonical-depth budgeted sweep ===" | tee -a "$LOG"
echo "[$(date)] Budgets: T=$TIGHT_BUDGET  M=$MEDIUM_BUDGET  L=$LOOSE_BUDGET" | tee -a "$LOG"

if ! curl -sf http://localhost:8002/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM Devstral not responding on port 8002. Run scripts/start_vllm_devstral.sh first." | tee -a "$LOG"
    exit 1
fi

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

# Run order: MEDIUM first, then TIGHT, then LOOSE (Dobby convention).
for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
    name="devstral-2-budgeted-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"

    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    devstral-2 \
        --agent-config configs/config-devstral-vllm.yaml \
        --otrc-config  configs/config-online-trc-devstral.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"

    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    devstral-2 \
        --agent-config configs/config-devstral-vllm.yaml \
        --otrc-config  configs/config-online-trc-devstral.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Devstral §c DONE ===" | tee -a "$LOG"
echo "[$(date)] Next: sanity-check canonical numbers; if OK, launch scripts/run_devstral_tail_depths.sh" | tee -a "$LOG"
