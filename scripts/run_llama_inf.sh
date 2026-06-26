#!/bin/bash
# Llama 3.3 70B  §a: FC + OTRC infinite-budget baselines on ABL-30 (depth=0.5).
# 2 prims (full-context, online-trc) x 30 tasks x 2 runs = 120 runs total.
# Output dir: results/ablations/llama33-70b-inf/
#
# Prerequisites:
#  - vLLM Llama-3.3-70B serving on port 8001 (scripts/start_vllm_llama33_70b.sh)
#  - run_experiment.py patched with --otrc-config flag (see DOBBY_LLAMA_PHASE.md §0.1)
#  - 5-task pilot ran cleanly (DOBBY_LLAMA_PHASE.md §0.2)
#
# Usage:  nohup bash scripts/run_llama_inf.sh > logs/llama33_70b_inf.out 2>&1 &
#         echo $! > logs/llama33_70b_inf.pid
# Tail:   tail -f logs/llama33_70b_inf.log
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/llama33_70b_inf.log"
mkdir -p "$WS/logs"

echo "[$(date)] === Llama-3.3-70B §a: FC + OTRC inf baselines ===" | tee -a "$LOG"

# Pre-flight: vLLM must be up on port 8001.
if ! curl -sf http://localhost:8001/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM not responding on port 8001. Run scripts/start_vllm_llama33_70b.sh first." | tee -a "$LOG"
    exit 1
fi

CONDS_INF="full-context online-trc"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     llama33-70b-inf \
    --model-tag    llama33-70b \
    --agent-config configs/config-llama33-vllm.yaml \
    --otrc-config  configs/config-online-trc-llama33.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     llama33-70b-inf \
    --model-tag    llama33-70b \
    --agent-config configs/config-llama33-vllm.yaml \
    --otrc-config  configs/config-online-trc-llama33.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Llama-3.3-70B §a DONE — now run scripts/calibrate_llama_budgets.sh ===" | tee -a "$LOG"
