#!/usr/bin/env bash
# Second Qwen3.5-35B-A3B vLLM server WITHOUT prefix caching, on GPUs 4-7 and
# port 8002, so the Terminal-Bench prefix-cache ablation (dashboard 5.b) can run
# as two halves at once (scripts/expansions/run_qwen_tb_prefix_cache_ablation_split.sh
# {gpu0-3|gpu4-7}). The first half uses the production port 8000 server from
# scripts/serving/start_vllm_qwen35_no_prefix_cache.sh (GPUs 0-3).
#
# Every serving argument other than the port and the GPU set is the production
# default of scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh (TP=4, 102400 context, 64 seqs), with
# --no-enable-prefix-caching as the only changed flag, so both halves are served
# under the same condition. Consumed by configs/config-qwen-vllm-8002.yaml.
#
# Usage:  bash scripts/serving/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh
# Tail:   tail -f logs/servers/vllm_qwen35_noprefixcache_gpu4-7.latest.log
# Check:  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/servers/vllm_qwen35_noprefixcache_gpu4-7.latest.log | tail -1
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_gpu4-7.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"

PORT=8002
MODEL="Qwen/Qwen3.5-35B-A3B"
CUDA_DEVICES="4,5,6,7"
TP_SIZE=4
MAX_MODEL_LEN=102400
MAX_NUM_SEQS=64
PYTHON_BIN="$WS/venv/bin/python3"
LOG_FILE="$(server_log vllm_qwen35_noprefixcache_gpu4-7)"
PID_FILE="$SERVER_LOG_DIR/vllm_qwen35_gpu4-7.pid"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

if ss -ltnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[ERROR] Port $PORT already in use. Aborting." >&2
    ss -ltnp | grep ":${PORT} " >&2
    exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[ERROR] A server from $PID_FILE (PID $(cat "$PID_FILE")) is still running. Aborting." >&2
    exit 1
fi

CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name Qwen/Qwen3.5-35B-A3B \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --no-enable-prefix-caching \
    </dev/null > "$LOG_FILE" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$PID_FILE"
disown || true

sleep 2
if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "[ERROR] vLLM exited during startup. Last log lines:" >&2
    tail -n 40 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
fi

echo "[$(date)] vLLM Qwen3.5-35B-A3B (--no-enable-prefix-caching) launched as PID $VLLM_PID on GPUs $CUDA_DEVICES, port $PORT"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "Follow startup with:"
echo "  tail -f $LOG_FILE"
echo "Confirm the prefix-caching setting once the engine config line is logged:"
echo "  grep -a -o 'enable_prefix_caching=[A-Za-z]*' $LOG_FILE | tail -1"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
