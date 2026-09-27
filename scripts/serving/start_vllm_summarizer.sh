#!/usr/bin/env bash
# Start a vLLM *summarizer* server on port 8001 for the summarizer ablation
# (FOLLOWUP_EXPERIMENTS.md §4), sharing GPUs 0-3 with the Qwen3.5-35B-A3B agent
# server (scripts/serving/start_vllm_qwen35_swe_summarizer_ablation.sh, :8000). Consumed by
# configs/config-summary-<name>.yaml.
#
#   qwen35-9b    Qwen/Qwen3.5-9B        default venv (vLLM 0.17)
#   gemma4-12b   google/gemma-4-12B-it  public on HF (Apache 2.0); needs
#                vLLM >= 0.27, so it runs from venv-glm-cu129-clean (vLLM 0.28)
#
# GPU memory: both servers take an explicit --gpu-memory-utilization share of
# the same GPUs (agent 0.70 + summarizer 0.15 by default). vLLM checks free
# memory at startup, so start the agent server first. Only one summarizer runs
# at a time (both presets use port 8001).
#
# Usage:  bash scripts/serving/start_vllm_summarizer.sh qwen35-9b
#         bash scripts/serving/start_vllm_summarizer.sh gemma4-12b
# Tail:   tail -f logs/servers/vllm_summarizer_<name>.latest.log
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_summarizer_<name>.pid
#         (a plain `kill <pid>` can leave EngineCore/Worker processes holding GPU memory)
# Overrides: SUMMARIZER_VLLM_PORT, SUMMARIZER_CUDA_VISIBLE_DEVICES, SUMMARIZER_TENSOR_PARALLEL_SIZE,
#   SUMMARIZER_MAX_MODEL_LEN (or "native"), SUMMARIZER_MAX_NUM_SEQS,
#   SUMMARIZER_GPU_MEMORY_UTILIZATION, SUMMARIZER_VLLM_PYTHON, SUMMARIZER_MODEL.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"

NAME="${1:-}"
case "$NAME" in
    qwen35-9b)
        DEFAULT_MODEL="Qwen/Qwen3.5-9B"
        DEFAULT_PYTHON="$WS/venv/bin/python3"
        ;;
    gemma4-12b)
        DEFAULT_MODEL="google/gemma-4-12B-it"
        DEFAULT_PYTHON="$WS/venv-glm-cu129-clean/bin/python3"
        ;;
    *) echo "Usage: $0 {qwen35-9b|gemma4-12b}" >&2; exit 2 ;;
esac

PORT="${SUMMARIZER_VLLM_PORT:-8001}"
MODEL="${SUMMARIZER_MODEL:-$DEFAULT_MODEL}"
SERVED_NAME="$MODEL"     # must match model_name in configs/config-summary-<name>.yaml
CUDA_DEVICES="${SUMMARIZER_CUDA_VISIBLE_DEVICES:-0,1,2,3}"
TP_SIZE="${SUMMARIZER_TENSOR_PARALLEL_SIZE:-4}"
# Summarizer inputs are the compressed slice (budget-sized) plus the summary
# prompt, so a 32k window is ample and keeps KV memory small.
MAX_MODEL_LEN="${SUMMARIZER_MAX_MODEL_LEN:-32768}"
CONTEXT_ARGS=()
if [[ "$MAX_MODEL_LEN" != "native" ]]; then
    CONTEXT_ARGS+=(--max-model-len "$MAX_MODEL_LEN")
fi
MAX_NUM_SEQS="${SUMMARIZER_MAX_NUM_SEQS:-64}"
GPU_MEM_UTIL="${SUMMARIZER_GPU_MEMORY_UTILIZATION:-0.15}"
PYTHON_BIN="${SUMMARIZER_VLLM_PYTHON:-$DEFAULT_PYTHON}"
LOG_FILE="$(server_log "vllm_summarizer_${NAME}")"
PID_FILE="$SERVER_LOG_DIR/vllm_summarizer_${NAME}.pid"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi
# vLLM refuses to start when less than its share is free. Report who holds the
# memory up front (typically orphaned workers of a previous summarizer) instead
# of failing minutes later inside the engine.
first_gpu="${CUDA_DEVICES%%,*}"
read -r free_mib total_mib < <(nvidia-smi -i "$first_gpu" --query-gpu=memory.free,memory.total --format=csv,noheader,nounits | tr -d ',')
need_mib="$(awk -v t="$total_mib" -v u="$GPU_MEM_UTIL" 'BEGIN {printf "%d", t * u}')"
if (( free_mib < need_mib )); then
    echo "[ERROR] GPU $first_gpu has ${free_mib} MiB free but gpu-memory-utilization $GPU_MEM_UTIL needs ${need_mib} MiB." >&2
    echo "        Processes holding GPU memory (stop leftovers with scripts/serving/stop_vllm.sh <pid file>):" >&2
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader >&2
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
    --gpu-memory-utilization "$GPU_MEM_UTIL" \
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

echo "[$(date)] vLLM ${SERVED_NAME} (summarizer) launched as PID $VLLM_PID on GPUs $CUDA_DEVICES, port $PORT, gpu-memory-utilization $GPU_MEM_UTIL"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "The first launch may download the model and take several minutes."
echo "Follow startup with:"
echo "  tail -f $LOG_FILE"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
