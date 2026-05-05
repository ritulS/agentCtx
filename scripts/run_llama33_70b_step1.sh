#!/bin/bash
# §2.2a — FC + OTRC for Llama 3.3 70B Instruct
# 2 conditions × 30 tasks × 2 runs = 120 runs, ~30-40h.
# Output: results/ablations/llama33-70b-inf/
# After completion, STOP — run §2.2b calibration before launching §2.2c.
# This script chains from run_qwen25_7b_step3.sh via exec; or can be invoked manually.
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/llama33_70b_step1.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Llama 3.3 70B §2.2a setup: starting vLLM ===" | tee -a "$LOG"

# Boot Llama 3.3 70B vLLM on TP=8
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  nohup venv/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --port 8000 \
  --dtype auto \
  --tensor-parallel-size 8 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json \
  > logs/vllm_llama33_70b.log 2>&1 &
disown
VLLM_LAUNCH_PID=$(pgrep -f "vllm.entrypoints.openai.api_server" | head -1)
echo "$VLLM_LAUNCH_PID" > logs/vllm_llama33_70b.pid
echo "[$(date)] vLLM Llama launch PID: $VLLM_LAUNCH_PID — waiting for endpoint" | tee -a "$LOG"

# Wait up to 30 min for endpoint (model weights ~140GB if not cached)
for i in $(seq 1 180); do
    if curl -s --max-time 5 http://localhost:8000/v1/models > /dev/null 2>&1; then
        echo "[$(date)] vLLM Llama ready after ${i}×10s" | tee -a "$LOG"; break
    fi
    if ! pgrep -f "vllm.entrypoints.openai.api_server" > /dev/null; then
        echo "[$(date)] ERROR: vLLM Llama died during startup" | tee -a "$LOG"
        tail -40 logs/vllm_llama33_70b.log | tee -a "$LOG"
        exit 1
    fi
    sleep 10
done

# Build config-llama33-70b-vllm.yaml if missing
if [[ ! -f config-llama33-70b-vllm.yaml ]]; then
    sed 's|Qwen/Qwen2.5-7B-Instruct|meta-llama/Llama-3.3-70B-Instruct|' \
        config-qwen25-7b-vllm.yaml > config-llama33-70b-vllm.yaml
    echo "[$(date)] generated config-llama33-70b-vllm.yaml" | tee -a "$LOG"
fi

echo "[$(date)] === §2.2a: FC + OTRC ===" | tee -a "$LOG"
CONDS_INF="full-context online-trc"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     llama33-70b-inf \
    --model-tag    llama33-70b \
    --agent-config config-llama33-70b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --max-workers  16 \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     llama33-70b-inf \
    --model-tag    llama33-70b \
    --agent-config config-llama33-70b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --max-workers  16 \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === aggregating into Review1 ===" | tee -a "$LOG"
venv/bin/python3 Review1/build_review1_albus.py --model-tag llama33-70b 2>&1 | tee -a "$LOG"

echo "[$(date)] === §2.2a done — STOP, run §2.2b calibration before continuing ===" | tee -a "$LOG"
