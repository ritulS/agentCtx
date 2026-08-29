#!/usr/bin/env bash
# Start vLLM serving for GLM-4.7-Flash on 4x A100 80GB GPUs.
#
# This server is consumed by configs/config-glm47flash-vllm.yaml and the
# SWE-Bench calibration launcher. mini-swe-agent uses raw text generation,
# so vLLM tool-call/reasoning parsers are intentionally not enabled here.
#
# Usage:  bash scripts/start_vllm_glm47flash.sh
# Tail:   tail -f logs/vllm_glm47flash.log
# Stop:   kill -TERM "$(cat logs/vllm_glm47flash.pid)"
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/start_vllm_glm47flash.sh"
    exit 0
fi
if (( $# != 0 )); then
    echo "[ERROR] This script takes no arguments." >&2
    echo "Usage: bash scripts/start_vllm_glm47flash.sh" >&2
    exit 2
fi

WORKSPACE="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${GLM_VLLM_PORT:-8003}"
MODEL="${GLM_MODEL:-zai-org/GLM-4.7-Flash}"
CUDA_DEVICES="${GLM_CUDA_VISIBLE_DEVICES:-0,1,2,3}"
TENSOR_PARALLEL_SIZE="${GLM_TENSOR_PARALLEL_SIZE:-4}"
MAX_MODEL_LEN="${GLM_MAX_MODEL_LEN:-65536}"
MAX_NUM_SEQS="${GLM_MAX_NUM_SEQS:-64}"

LOG_FILE="$WORKSPACE/logs/vllm_glm47flash.log"
PID_FILE="$WORKSPACE/logs/vllm_glm47flash.pid"
PYTHON_BIN="${PYTHON_BIN:-$WORKSPACE/venv-glm-cu129-clean/bin/python3}"

cd "$WORKSPACE"
mkdir -p logs

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    echo "[ERROR] Port $PORT is already in use. Aborting." >&2
    ss -ltnp 2>/dev/null | grep ":${PORT} " >&2 || true
    exit 1
fi

if pgrep -f "vllm.entrypoints.openai.api_server.*GLM-4.7-Flash" >/dev/null; then
    echo "[ERROR] GLM-4.7-Flash vLLM is already running. Aborting." >&2
    pgrep -af "vllm.entrypoints.openai.api_server.*GLM-4.7-Flash" >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    > "$LOG_FILE" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$PID_FILE"

echo "[$(date)] vLLM GLM-4.7-Flash launched as PID $VLLM_PID"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo
echo "The first launch may need time to download the model. Follow progress with:"
echo "  tail -f logs/vllm_glm47flash.log"
echo
echo "When startup completes, verify the server with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
echo
echo "Then start the SWE-Bench FC@infinity calibration with:"
echo "  bash scripts/run_budget_calibration_sb.sh glm"
