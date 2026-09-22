#!/usr/bin/env bash
# Start vLLM serving for Qwen3.5-35B-A3B on port 8000.
# TP=4 across GPUs 0-3. The 102400-token context matches the prior
# Terminal-Bench full-context serving setup used in this repository.
#
# GPU memory share: QWEN_GPU_MEMORY_UTILIZATION (default 0.70) leaves room on
# the same GPUs for a summarizer server (scripts/start_vllm_summarizer.sh,
# default 0.15) used by the summarizer ablation. vLLM checks free memory at
# startup, so start this server first. Set 0.90 to reclaim the GPUs when no
# summarizer is needed.
#
# Usage:  bash scripts/start_vllm_qwen35_swe_summarizer_ablation.sh
# Native context: QWEN_MAX_MODEL_LEN=native bash scripts/start_vllm_qwen35_swe_summarizer_ablation.sh
# Tail:   tail -f logs/vllm_qwen35.log
# Stop:   bash scripts/stop_vllm.sh logs/vllm_qwen35.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PORT="${QWEN_VLLM_PORT:-8000}"
MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-35B-A3B}"
CUDA_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-0,1,2,3}"
TP_SIZE="${QWEN_TENSOR_PARALLEL_SIZE:-4}"
MAX_MODEL_LEN="${QWEN_MAX_MODEL_LEN:-102400}"
CONTEXT_ARGS=()
if [[ "$MAX_MODEL_LEN" != "native" ]]; then
    CONTEXT_ARGS+=(--max-model-len "$MAX_MODEL_LEN")
fi
MAX_NUM_SEQS="${QWEN_MAX_NUM_SEQS:-64}"
GPU_MEM_UTIL="${QWEN_GPU_MEMORY_UTILIZATION:-0.70}"
PYTHON_BIN="${QWEN_VLLM_PYTHON:-$WS/venv/bin/python3}"
LOG_FILE="$WS/logs/vllm_qwen35.log"
PID_FILE="$WS/logs/vllm_qwen35.pid"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

if ss -ltnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[ERROR] Port $PORT already in use. Aborting." >&2
    ss -ltnp | grep ":${PORT} " >&2
    exit 1
fi

if pgrep -f 'vllm.entrypoints.openai.api_server.*Qwen3.5-35B-A3B' >/dev/null; then
    echo "[ERROR] vLLM Qwen3.5-35B-A3B already running. Aborting." >&2
    pgrep -af 'vllm.entrypoints.openai.api_server.*Qwen3.5-35B-A3B' >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name Qwen/Qwen3.5-35B-A3B \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    "${CONTEXT_ARGS[@]}" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --gpu-memory-utilization "$GPU_MEM_UTIL" \
    --enable-prefix-caching \
    </dev/null > "$LOG_FILE" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$PID_FILE"

# Detach the server from this shell's job table as well as its controlling
# terminal, so closing an SSH/IDE terminal does not terminate it.
disown || true

# Catch immediate failures such as invalid arguments or missing CUDA devices.
sleep 2
if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "[ERROR] vLLM exited during startup. Last log lines:" >&2
    tail -n 40 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
fi

echo "[$(date)] vLLM Qwen3.5-35B-A3B launched as PID $VLLM_PID on GPUs $CUDA_DEVICES, port $PORT, gpu-memory-utilization $GPU_MEM_UTIL"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "The first launch may download the model and take several minutes."
echo "Follow startup with:"
echo "  tail -f logs/vllm_qwen35.log"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
