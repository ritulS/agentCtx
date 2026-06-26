#!/bin/bash
# §2.2c — 11 budgeted primitives × 3 calibrated budgets for Llama 3.3 70B Instruct
# Output: results/ablations/llama33-70b-budgeted-{tight,medium,loose}/
# Chains to Phase 3 (quantization sweep) at the end.
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/llama33_70b_step3.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Llama 3.3 70B §2.2c: budgeted cells ===" | tee -a "$LOG"

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

# Source calibrated budgets (written by Review1/calibrate_budgets.py or manually).
BUDGETS_FILE="$WS/logs/llama33-70b_calibrated_budgets.sh"
if [[ ! -f "$BUDGETS_FILE" ]]; then
    echo "ERROR: $BUDGETS_FILE not found. Run §2.2b calibration first." | tee -a "$LOG"
    exit 1
fi
# shellcheck disable=SC1090
source "$BUDGETS_FILE"
if [[ -z "${TIGHT_BUDGET:-}" || -z "${MEDIUM_BUDGET:-}" || -z "${LOOSE_BUDGET:-}" ]]; then
    echo "ERROR: budgets not set in $BUDGETS_FILE" | tee -a "$LOG"
    exit 1
fi
echo "[$(date)] using budgets: TIGHT=$TIGHT_BUDGET MEDIUM=$MEDIUM_BUDGET LOOSE=$LOOSE_BUDGET" | tee -a "$LOG"

for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
    name="llama33-70b-budgeted-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    llama33-70b \
        --agent-config configs/config-llama33-70b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --max-workers  16 \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    llama33-70b \
        --agent-config configs/config-llama33-70b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --max-workers  16 \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === aggregating into Review1 ===" | tee -a "$LOG"
venv/bin/python3 Review1/build_review1_albus.py --model-tag llama33-70b 2>&1 | tee -a "$LOG"

echo "[$(date)] === Llama 3.3 70B done — Phase 2 complete ===" | tee -a "$LOG"
echo "[$(date)] === Stopping here — Phase 3 (quantization) is a separate launch ===" | tee -a "$LOG"
pkill -f vllm.entrypoints.openai.api_server || true
