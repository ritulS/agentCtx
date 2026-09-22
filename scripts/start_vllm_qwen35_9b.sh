#!/usr/bin/env bash
# Start vLLM serving for Qwen3.5-9B on port 8001 as the *summarizer* model for
# the summarizer ablation (FOLLOWUP_EXPERIMENTS.md §4). TP=2 across GPUs 4-5,
# leaving GPUs 0-3 for the Qwen3.5-35B-A3B agent server
# (scripts/start_vllm_qwen35_prefix_cache_ablation.sh). Consumed by configs/config-summary-qwen35-9b.yaml.
#
# Usage:  bash scripts/start_vllm_qwen35_9b.sh
# Tail:   tail -f logs/vllm_qwen35_9b.log
# Stop:   kill "$(cat logs/vllm_qwen35_9b.pid)"
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PORT="${QWEN9B_VLLM_PORT:-8001}"
MODEL="${QWEN9B_MODEL:-Qwen/Qwen3.5-9B}"
SERVED_NAME="${QWEN9B_SERVED_NAME:-Qwen/Qwen3.5-9B}"
CUDA_DEVICES="${QWEN9B_CUDA_VISIBLE_DEVICES:-4,5}"
TP_SIZE="${QWEN9B_TENSOR_PARALLEL_SIZE:-2}"
# Summarizer inputs are the compressed slice (budget-sized) plus the summary
# prompt, so a 32k window is ample and keeps KV memory small.
MAX_MODEL_LEN="${QWEN9B_MAX_MODEL_LEN:-32768}"
CONTEXT_ARGS=()
if [[ "$MAX_MODEL_LEN" != "native" ]]; then
    CONTEXT_ARGS+=(--max-model-len "$MAX_MODEL_LEN")
fi
MAX_NUM_SEQS="${QWEN9B_MAX_NUM_SEQS:-64}"
PYTHON_BIN="${QWEN9B_VLLM_PYTHON:-$WS/venv/bin/python3}"
LOG_FILE="$WS/logs/vllm_qwen35_9b.log"
PID_FILE="$WS/logs/vllm_qwen35_9b.pid"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

if ss -ltnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[ERROR] Port $PORT already in use. Aborting." >&2
    ss -ltnp | grep ":${PORT} " >&2
    exit 1
fi

if pgrep -f "vllm.entrypoints.openai.api_server.*--served-model-name ${SERVED_NAME}( |$)" >/dev/null; then
    echo "[ERROR] vLLM ${SERVED_NAME} already running. Aborting." >&2
    pgrep -af "vllm.entrypoints.openai.api_server.*--served-model-name ${SERVED_NAME}( |$)" >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name "$SERVED_NAME" \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    "${CONTEXT_ARGS[@]}" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --enable-prefix-caching \
    </dev/null > "$LOG_FILE" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$PID_FILE"

# Detach from this shell's job table and controlling terminal so closing the
# SSH/IDE terminal does not stop the server.
disown || true

# Catch immediate failures such as invalid arguments or missing CUDA devices.
sleep 2
if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "[ERROR] vLLM exited during startup. Last log lines:" >&2
    tail -n 40 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
fi

echo "[$(date)] vLLM ${SERVED_NAME} (summarizer) launched as PID $VLLM_PID on GPUs $CUDA_DEVICES, port $PORT"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "The first launch may download the model and take several minutes."
echo "Follow startup with:"
echo "  tail -f logs/vllm_qwen35_9b.log"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
