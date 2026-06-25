#!/bin/bash
# Start vLLM serving for Qwen2.5-Coder-32B-Instruct on Dobby.
# 32B dense Qwen2 architecture (full attention, no SWA confound).
# TP=4 across all 4 A100 80GB. Port 8003 (separate from prior models).
#
# Usage:  bash scripts/start_vllm_qwen25_coder_32b.sh
# Tail:   tail -f logs/vllm_qwen25_coder_32b.log
# Stop:   kill $(cat logs/vllm_qwen25_coder_32b.pid)
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
mkdir -p logs

if ss -ltnp 2>/dev/null | grep -q ':8003 '; then
    echo "[ERROR] Port 8003 already in use." >&2
    ss -ltnp | grep ':8003 ' >&2
    exit 1
fi

if pgrep -f 'vllm.entrypoints.openai.api_server.*Qwen2.5-Coder-32B' >/dev/null; then
    echo "[ERROR] vLLM Qwen2.5-Coder-32B already running." >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES=0,1,2,3 \
  nohup venv/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-Coder-32B-Instruct \
    --port 8003 \
    --dtype auto \
    --tensor-parallel-size 4 \
    --max-model-len 32768 \
    --max-num-seqs 64 \
    > logs/vllm_qwen25_coder_32b.log 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > logs/vllm_qwen25_coder_32b.pid
echo "[$(date)] vLLM Qwen2.5-Coder-32B launched as PID $VLLM_PID"
echo "[$(date)] Log: logs/vllm_qwen25_coder_32b.log"
echo ""
echo "Wait for 'Uvicorn running on http://0.0.0.0:8003' then verify with:"
echo "  curl -s http://localhost:8003/v1/models | python3 -m json.tool"
