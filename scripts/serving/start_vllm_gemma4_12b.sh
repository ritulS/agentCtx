#!/usr/bin/env bash
# Start vLLM serving for Gemma-4-12B (google/gemma-4-12B-it) on port 8001 as
# the *summarizer* model for the summarizer ablation (FOLLOWUP_EXPERIMENTS.md
# §4.c/4.d). TP=2 across GPUs 4-5, leaving GPUs 0-3 for the Qwen3.5-35B-A3B
# agent server (scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh). Consumed by
# configs/config-summary-gemma4-12b.yaml.
#
# Gemma 4 (Gemma4UnifiedForConditionalGeneration) is not in vLLM 0.17.1
# (venv/), so this server runs from venv-glm-cu129-clean (vLLM 0.28.0), the
# same environment that serves GLM-4.7-Flash. The model is multimodal; image
# and audio inputs are disabled so no vision/audio memory is profiled or
# reserved. Its chat template defaults to thinking OFF, so no reasoning
# parser is needed.
#
# The shared-GPU alternative is scripts/serving/start_vllm_summarizer.sh gemma4-12b
# (GPUs 0-3 with the agent, --gpu-memory-utilization share).
#
# Usage:  bash scripts/serving/start_vllm_gemma4_12b.sh
# Tail:   tail -f logs/servers/vllm_gemma4_12b.latest.log
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_gemma4_12b.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_kv_trace.sh"

PORT="${GEMMA_VLLM_PORT:-8001}"
MODEL="${GEMMA_MODEL:-google/gemma-4-12B-it}"
SERVED_NAME="${GEMMA_SERVED_NAME:-google/gemma-4-12B-it}"
CUDA_DEVICES="${GEMMA_CUDA_VISIBLE_DEVICES:-4,5}"
TP_SIZE="${GEMMA_TENSOR_PARALLEL_SIZE:-2}"
# Summarizer inputs are the compressed slice (budget-sized) plus the summary
# prompt, so a 32k window is ample and keeps KV memory small.
MAX_MODEL_LEN="${GEMMA_MAX_MODEL_LEN:-32768}"
CONTEXT_ARGS=()
if [[ "$MAX_MODEL_LEN" != "native" ]]; then
    CONTEXT_ARGS+=(--max-model-len "$MAX_MODEL_LEN")
fi
MAX_NUM_SEQS="${GEMMA_MAX_NUM_SEQS:-64}"
PYTHON_BIN="${GEMMA_VLLM_PYTHON:-$WS/venv-glm-cu129-clean/bin/python3}"
LOG_FILE="$(server_log vllm_gemma4_12b)"
PID_FILE="$SERVER_LOG_DIR/vllm_gemma4_12b.pid"

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

kv_trace_args "$LOG_FILE"
CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    "${KV_TRACE_ARGS[@]}" \
    --model "$MODEL" \
    --served-model-name "$SERVED_NAME" \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    "${CONTEXT_ARGS[@]}" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
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
echo "[$(date)] $(kv_trace_status)"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "The first launch downloads the model (~24 GB) and takes several minutes."
echo "Follow startup with:"
echo "  tail -f $LOG_FILE"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
