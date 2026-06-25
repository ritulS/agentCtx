#!/bin/bash
# Start vLLM serving for Llama 3.3 70B Instruct on Dobby.
# 4x A100 80GB PCIe -> TP=4. Port 8001 (matches config-llama33-vllm.yaml).
# Weights are already cached at ~/.cache/huggingface/hub/models--meta-llama--Llama-3.3-70B-Instruct
#
# Usage:  bash scripts/start_vllm_llama33_70b.sh
# Tail:   tail -f logs/vllm_llama33_70b.log
# Stop:   pkill -f 'vllm.entrypoints.openai.api_server.*Llama-3.3-70B'
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
mkdir -p logs

# Safety: refuse to start if anything is already on port 8001.
if ss -ltnp 2>/dev/null | grep -q ':8001 '; then
    echo "[ERROR] Port 8001 already in use. Aborting." >&2
    ss -ltnp | grep ':8001 ' >&2
    exit 1
fi

# Safety: refuse to start if vLLM is already serving Llama 70B.
if pgrep -f 'vllm.entrypoints.openai.api_server.*Llama-3.3-70B' >/dev/null; then
    echo "[ERROR] vLLM Llama-3.3-70B already running. Aborting." >&2
    pgrep -af 'vllm.entrypoints.openai.api_server.*Llama-3.3-70B' >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES=0,1,2,3 \
  nohup venv/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.3-70B-Instruct \
    --port 8001 \
    --dtype auto \
    --tensor-parallel-size 4 \
    --max-model-len 32768 \
    --max-num-seqs 64 \
    --enable-auto-tool-choice \
    --tool-call-parser llama3_json \
    > logs/vllm_llama33_70b.log 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > logs/vllm_llama33_70b.pid
echo "[$(date)] vLLM Llama-3.3-70B launched as PID $VLLM_PID"
echo "[$(date)] Log: logs/vllm_llama33_70b.log"
echo "[$(date)] PID file: logs/vllm_llama33_70b.pid"
echo ""
echo "Wait for the line 'Uvicorn running on http://0.0.0.0:8001' (typically 60-120s),"
echo "then verify with:"
echo "  curl -s http://localhost:8001/v1/models | python3 -m json.tool"
