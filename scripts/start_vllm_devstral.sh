#!/bin/bash
# Start vLLM serving for Devstral-Small-2-24B-Instruct-2512 on Dobby.
# 24B dense Mistral 3 architecture (full attention, sliding_window=null).
# TP=4 on GPUs 4-7 by default. Port 8002 (separate from Qwen / GLM).
#
# NOTE: NOT using --tool-call-parser since mini-swe-agent talks to vLLM via
# litellm_textbased (raw completions), not OpenAI function-calling. Adding
# the parser flag changes generation behavior even in textbased mode.
#
# Usage:  bash scripts/start_vllm_devstral.sh
# Native context: DEVSTRAL_MAX_MODEL_LEN=native bash scripts/start_vllm_devstral.sh
# Tail:   tail -f logs/vllm_devstral.log
# Stop:   kill $(cat logs/vllm_devstral.pid)
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/start_vllm_devstral.sh"
    echo "DEVSTRAL_MAX_MODEL_LEN=native omits --max-model-len (default: 65536)."
    echo "DEVSTRAL_CUDA_VISIBLE_DEVICES defaults to 4,5,6,7; TP=4."
    exit 0
fi
if (( $# != 0 )); then
    echo "[ERROR] This script takes no arguments; use environment variables." >&2
    exit 2
fi

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${DEVSTRAL_VLLM_PYTHON:-$WS/venv/bin/python3}"
MAX_MODEL_LEN="${DEVSTRAL_MAX_MODEL_LEN:-65536}"
MAX_NUM_SEQS="${DEVSTRAL_MAX_NUM_SEQS:-64}"
CONTEXT_ARGS=()
if [[ "$MAX_MODEL_LEN" != "native" ]]; then
    CONTEXT_ARGS+=(--max-model-len "$MAX_MODEL_LEN")
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi
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

# Keep the existing dtype/KV-cache precision; native only removes the context cap.
CUDA_VISIBLE_DEVICES="${DEVSTRAL_CUDA_VISIBLE_DEVICES:-4,5,6,7}" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model mistralai/Devstral-Small-2-24B-Instruct-2512 \
    --port 8002 \
    --dtype auto \
    --tensor-parallel-size 4 \
    "${CONTEXT_ARGS[@]}" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --enable-prefix-caching \
    < /dev/null > logs/vllm_devstral.log 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > logs/vllm_devstral.pid
disown || true
echo "[$(date)] vLLM Devstral-Small-2-24B-2512 launched as PID $VLLM_PID"
echo "[$(date)] Log: logs/vllm_devstral.log"
echo "[$(date)] PID file: logs/vllm_devstral.pid"
echo ""
echo "Wait for 'Uvicorn running on http://0.0.0.0:8002' (typically 30-90s),"
echo "then verify with:"
echo "  curl -s http://localhost:8002/v1/models | python3 -m json.tool"
