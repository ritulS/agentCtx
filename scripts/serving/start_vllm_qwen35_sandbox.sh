#!/usr/bin/env bash
# Start vLLM serving for Qwen3.5-35B-A3B for the controlled-sandbox runs:
# scripts/serving/start_vllm_qwen35_prefix_cache.sh with prefix caching OFF.
#
# Same model, port 8000, dtype auto, 102400 context, 64 seqs, reasoning parser,
# KV-ownership trace and AGENTCTX_PROFILE handling (albus-swe: GPUs 0-7, TP=8;
# unset: Dobby GPUs 0-3, TP=4) as that script; --no-enable-prefix-caching is the
# only changed engine argument. This is the production Dobby setting for this
# hybrid (mamba + attention) model, for which vLLM 0.17.1 defaults caching off,
# so the sandbox pilot (scripts/expansions/run_r2_swe_majority_capped_pilot.sh)
# cannot be confused by cache-state effects. The launcher checks the server's
# vllm:cache_config_info label before starting.
#
# Usage:  AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_qwen35_sandbox.sh
# Tail:   tail -f logs/servers/vllm_qwen35_a3b_noprefixcache.latest.log
# Check:  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/servers/vllm_qwen35_a3b_noprefixcache.latest.log | tail -1
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_a3b_noprefixcache.pid
# (Stop a caching-ON server first: bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_a3b.pid)
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_kv_trace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_reasoning.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/profiles.sh"
reasoning_parser_args qwen3
agentctx_profile

PORT=8000
CUDA_DEVICES="${PROFILE_CUDA_DEVICES:-0,1,2,3}"
TP_SIZE="${PROFILE_TP_SIZE:-4}"
PYTHON_BIN="$WS/venv/bin/python3"
PID_FILE="$SERVER_LOG_DIR/vllm_qwen35_a3b_noprefixcache.pid"

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

# Each startup gets its own timestamped log (it records its own engine config);
# vllm_qwen35_a3b_noprefixcache.latest.log points at the newest one. The name
# keeps the vllm_*.latest.log + .pid pair the resource monitor's serving_info
# discovery expects.
LOG_FILE="$(server_log vllm_qwen35_a3b_noprefixcache)"
kv_trace_args "$LOG_FILE"
CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    "${KV_TRACE_ARGS[@]}" \
    --model Qwen/Qwen3.5-35B-A3B \
    "${REASONING_ARGS[@]}" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    --max-model-len 102400 \
    --max-num-seqs 64 \
    --no-enable-prefix-caching \
    --enable-prompt-tokens-details \
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

echo "[$(date)] vLLM Qwen3.5-35B-A3B launched as PID $VLLM_PID on GPUs $CUDA_DEVICES (TP=$TP_SIZE, $(profile_status)), port $PORT, prefix caching OFF (sandbox)"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] $(kv_trace_status)"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "Follow startup with:"
echo "  tail -f logs/servers/vllm_qwen35_a3b_noprefixcache.latest.log"
echo "Confirm prefix caching is off once the engine config line is logged:"
echo "  grep -a -o 'enable_prefix_caching=[A-Za-z]*' $LOG_FILE | tail -1"
echo "Verify when ready with:"
echo "  curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
