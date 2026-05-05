#!/bin/bash
# §1.3c — 11 budgeted primitives × 3 calibrated budgets for Qwen2.5-7B-Instruct
# 11 conditions × 3 budgets × 30 tasks × 2 runs = 1980 runs, ~18-20h.
# Output: results/ablations/qwen25-7b-budgeted-{tight,medium,loose}/
# After completion, exec into the Llama 70B serving setup script.
#
# Launch via:  setsid bash scripts/run_qwen25_7b_step3.sh > logs/albus_chain.out 2>&1 &
#              echo $! > logs/albus_chain.pid; disown
# Kill the whole tree:  kill -- -$(cat logs/albus_chain.pid)
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_7b_step3.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Qwen2.5-7B §1.3c: budgeted cells ===  PGID=$$" | tee -a "$LOG"

WORKERS=32  # DP=8 vLLM server can absorb this; lower if oversubscribed

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

# FILL THESE FROM §1.3b CALIBRATION
TIGHT_BUDGET=____
MEDIUM_BUDGET=____
LOOSE_BUDGET=____

if [[ "$TIGHT_BUDGET" == "____" || "$MEDIUM_BUDGET" == "____" || "$LOOSE_BUDGET" == "____" ]]; then
    echo "ERROR: budgets not filled in. Edit this script before launching." | tee -a "$LOG"
    exit 1
fi

# Run order: medium first, then tight, then loose (matches Dobby convention)
for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
    name="qwen25-7b-budgeted-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    qwen25-7b \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --max-workers  $WORKERS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    qwen25-7b \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --max-workers  $WORKERS \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Qwen2.5-7B done — switching to Llama 3.3 70B ===" | tee -a "$LOG"

# Stop vLLM, switch to Llama 70B setup
pkill -f vllm.entrypoints.openai.api_server || true
sleep 30
exec "$WS/scripts/run_llama33_70b_step1.sh"
