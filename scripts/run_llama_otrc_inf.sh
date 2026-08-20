#!/bin/bash
# Complete the missing Llama-3.3-70B OTRC infinite-budget arm.
# FC is already present in llama33-70b-inf.
set -euo pipefail

AGENTCTX_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$AGENTCTX_DIR"
RUN_LOG="$AGENTCTX_DIR/logs/llama33_70b_otrc_inf.log"
mkdir -p "$AGENTCTX_DIR/logs"

echo "[$(date)] === Llama-3.3-70B OTRC inf arm ===" | tee -a "$RUN_LOG"

if ! curl -sf http://localhost:8001/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM is not responding on port 8001." | tee -a "$RUN_LOG"
    exit 1
fi

venv/bin/python3 scripts/run_experiment.py \
    --ablation llama33-70b-inf \
    --model-tag llama33-70b \
    --agent-config configs/config-llama33-vllm.yaml \
    --otrc-config configs/config-online-trc-llama33.yaml \
    --budget 999999999 \
    --tasks-file task_lists/ablation_30tasks.json \
    --conditions online-trc \
    2>&1 | tee -a "$RUN_LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation llama33-70b-inf \
    --model-tag llama33-70b \
    --agent-config configs/config-llama33-vllm.yaml \
    --otrc-config configs/config-online-trc-llama33.yaml \
    --budget 999999999 \
    --tasks-file task_lists/ablation_30tasks.json \
    --conditions online-trc \
    --eval-only \
    2>&1 | tee -a "$RUN_LOG"

echo "[$(date)] === Llama-3.3-70B OTRC inf arm complete ===" | tee -a "$RUN_LOG"
