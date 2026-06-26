#!/bin/bash
# §1.3a — FC + OTRC for Qwen2.5-7B-Instruct
# 2 conditions × 30 tasks × 2 runs = 120 runs, ~6-8h.
# Output: results/ablations/qwen25-7b-inf/
# After completion, STOP — run §1.3b calibration before launching §1.3c.
#
# Launch via:  setsid bash scripts/run_qwen25_7b_step1.sh > logs/albus_chain.out 2>&1 &
#              echo $! > logs/albus_chain.pid; disown
# Kill the whole tree:  kill -- -$(cat logs/albus_chain.pid)
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_7b_step1.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Qwen2.5-7B §1.3a: FC + OTRC ===  PGID=$$" | tee -a "$LOG"

CONDS_INF="full-context online-trc"
WORKERS=32  # DP=8 vLLM server can absorb this; lower if oversubscribed

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-7b-inf \
    --model-tag    qwen25-7b \
    --agent-config configs/config-qwen25-7b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --max-workers  $WORKERS \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-7b-inf \
    --model-tag    qwen25-7b \
    --agent-config configs/config-qwen25-7b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --max-workers  $WORKERS \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === aggregating into Review1 ===" | tee -a "$LOG"
venv/bin/python3 Review1/build_review1_albus.py --model-tag qwen25-7b 2>&1 | tee -a "$LOG"

echo "[$(date)] === §1.3a done — STOP, run §1.3b calibration before continuing ===" | tee -a "$LOG"
