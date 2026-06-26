#!/bin/bash
# Llama 3.3 70B  §c: 11 budgeted prims x 3 calibrated budgets at depth=0.5.
# 11 prims x 3 budgets x 30 tasks x 2 runs = 1,980 runs at canonical depth.
# Output dirs: results/ablations/llama33-70b-budgeted-{TIGHT,MEDIUM,LOOSE}/
#
# Prerequisites:
#  - §a (run_llama_inf.sh) complete
#  - §b (calibrate_llama_budgets.sh) output reviewed and approved in chat
#  - TIGHT_BUDGET / MEDIUM_BUDGET / LOOSE_BUDGET filled in below
#
# Usage:  nohup bash scripts/run_llama_budgeted_canonical.sh > logs/llama33_70b_canonical.out 2>&1 &
#         echo $! > logs/llama33_70b_canonical.pid
# Tail:   tail -f logs/llama33_70b_canonical.log
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/llama33_70b_canonical.log"
mkdir -p "$WS/logs"

# === FILL THESE FROM §b CALIBRATION OUTPUT ===
TIGHT_BUDGET=____
MEDIUM_BUDGET=____
LOOSE_BUDGET=____

# Refuse to run with placeholder values.
for v in "$TIGHT_BUDGET" "$MEDIUM_BUDGET" "$LOOSE_BUDGET"; do
    if [ "$v" = "____" ]; then
        echo "[ERROR] Budget placeholders not filled. See §b calibration output." >&2
        exit 1
    fi
done

echo "[$(date)] === Llama-3.3-70B §c: canonical-depth budgeted sweep ===" | tee -a "$LOG"
echo "[$(date)] Budgets: T=$TIGHT_BUDGET  M=$MEDIUM_BUDGET  L=$LOOSE_BUDGET" | tee -a "$LOG"

# Pre-flight: vLLM must be up on port 8001.
if ! curl -sf http://localhost:8001/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM not responding on port 8001. Run scripts/start_vllm_llama33_70b.sh first." | tee -a "$LOG"
    exit 1
fi

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

# Run order: MEDIUM first, then TIGHT, then LOOSE (matches Dobby convention from §1.3c).
for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
    name="llama33-70b-budgeted-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"

    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    llama33-70b \
        --agent-config configs/config-llama33-vllm.yaml \
        --otrc-config  configs/config-online-trc-llama33.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"

    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    llama33-70b \
        --agent-config configs/config-llama33-vllm.yaml \
        --otrc-config  configs/config-online-trc-llama33.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Llama-3.3-70B §c DONE ===" | tee -a "$LOG"
echo "[$(date)] Next: sanity-check canonical numbers; if OK, launch scripts/run_llama_tail_depths.sh" | tee -a "$LOG"
