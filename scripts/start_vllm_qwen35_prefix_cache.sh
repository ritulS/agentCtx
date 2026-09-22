#!/usr/bin/env bash
# Start vLLM serving for Qwen3.5-35B-A3B with the production SWE-bench serving
# configuration, plus prefix caching.
#
# The production Qwen runs (logs/vllm_qwen35_a3b.log, 08-23 .. 09-14) were
# served by a hand-typed command without --enable-prefix-caching. vLLM 0.17.1
# defaults prefix caching off for this hybrid (mamba + attention) model, so
# every startup there logged enable_prefix_caching=False and a 0.0% hit rate.
#
# This script is that same command with --enable-prefix-caching as the only
# added argument. Every other serving argument is pinned to the production
# value on purpose: no env overrides, and no --gpu-memory-utilization or
# --served-model-name (production left both at the vLLM default). Use
# scripts/start_vllm_qwen35.sh instead when sharing the GPUs with a summarizer.
#
# Usage:  bash scripts/start_vllm_qwen35_prefix_cache.sh
# Tail:   tail -f logs/vllm_qwen35_a3b.log
# Check:  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/vllm_qwen35_a3b.log | tail -1
# Stop:   bash scripts/stop_vllm.sh logs/vllm_qwen35_a3b.pid
set -euo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"
mkdir -p logs

PORT=8000
PYTHON_BIN="$WS/venv/bin/python3"
LOG_FILE="$WS/logs/vllm_qwen35_a3b.log"
PID_FILE="$WS/logs/vllm_qwen35_a3b.pid"

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

# Appends to the log, as the production command did, so the OFF and ON
# startups stay in one file; each startup records its own engine config.
CUDA_VISIBLE_DEVICES=0,1,2,3 \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3.5-35B-A3B \
    --host 127.0.0.1 \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size 4 \
    --max-model-len 102400 \
    --max-num-seqs 64 \
    --enable-prefix-caching \
    </dev/null >> "$LOG_FILE" 2>&1 &

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

echo "[$(date)] vLLM Qwen3.5-35B-A3B launched as PID $VLLM_PID on GPUs 0,1,2,3, port $PORT, prefix caching ON"
echo "[$(date)] Log: $LOG_FILE (appended)"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "Follow startup with:"
echo "  tail -f logs/vllm_qwen35_a3b.log"
echo "Confirm prefix caching once the engine config line is logged:"
echo "  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/vllm_qwen35_a3b.log | tail -1"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
