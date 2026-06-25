#!/bin/bash
# Start vLLM serving for Devstral-Small-2-24B-Instruct-2512 on Dobby.
# 24B dense Mistral 3 architecture (full attention, sliding_window=null).
# TP=2 on 2x A100 80GB — leaves the other 2 free for a parallel pilot model
# or a second serving instance. Port 8002 (separate from Qwen 8000 / Llama 8001).
#
# NOTE: NOT using --tool-call-parser since mini-swe-agent talks to vLLM via
# litellm_textbased (raw completions), not OpenAI function-calling. Adding
# the parser flag changes generation behavior even in textbased mode.
#
# Usage:  bash scripts/start_vllm_devstral.sh
# Tail:   tail -f logs/vllm_devstral.log
# Stop:   kill $(cat logs/vllm_devstral.pid)
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
mkdir -p logs

# Refuse if port already in use.
if ss -ltnp 2>/dev/null | grep -q ':8002 '; then
    echo "[ERROR] Port 8002 already in use. Aborting." >&2
    ss -ltnp | grep ':8002 ' >&2
    exit 1
fi

# Refuse if Devstral vLLM already up.
if pgrep -f 'vllm.entrypoints.openai.api_server.*Devstral' >/dev/null; then
    echo "[ERROR] vLLM Devstral already running. Aborting." >&2
    pgrep -af 'vllm.entrypoints.openai.api_server.*Devstral' >&2
    exit 1
fi

# TP=4 across all 4 A100 80GB so we can run max-model-len=65536 with
# headroom for 64 concurrent seqs. Smaller TP truncates the FC peak
# distribution (32k cap caused BadRequestError on ~40% of FC@∞ pilot runs).
CUDA_VISIBLE_DEVICES=0,1,2,3 \
  nohup venv/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model mistralai/Devstral-Small-2-24B-Instruct-2512 \
    --port 8002 \
    --dtype auto \
    --tensor-parallel-size 4 \
    --max-model-len 65536 \
    --max-num-seqs 64 \
    > logs/vllm_devstral.log 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > logs/vllm_devstral.pid
echo "[$(date)] vLLM Devstral-Small-2-24B-2512 launched as PID $VLLM_PID"
echo "[$(date)] Log: logs/vllm_devstral.log"
echo "[$(date)] PID file: logs/vllm_devstral.pid"
echo ""
echo "Wait for 'Uvicorn running on http://0.0.0.0:8002' (typically 30-90s),"
echo "then verify with:"
echo "  curl -s http://localhost:8002/v1/models | python3 -m json.tool"
