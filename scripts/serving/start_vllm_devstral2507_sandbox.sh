#!/usr/bin/env bash
# Start vLLM serving for Devstral-Small-2507 (Devstral Small 1.1, 24B dense,
# bf16 checkpoint, full attention, no thinking) for the controlled sandbox:
# the Devstral counterpart of scripts/serving/start_vllm_qwen35_sandbox.sh.
#
# PREFIX_CACHE=off (default) serves with --no-enable-prefix-caching, the
# sandbox setting; PREFIX_CACHE=on serves the same command with
# --enable-prefix-caching, for scripts/maintenance/probe_prefix_cache_effect.py
# (does the cache change greedy generations?). Both use port 8000 (the sandbox
# agent port), dtype auto, 131072 context (the model's native 128k), 64 seqs,
# --enable-prompt-tokens-details (cached_tokens in usage), the KV-ownership
# trace and AGENTCTX_PROFILE handling (albus-swe: GPUs 0-7, TP=8; unset: Dobby
# GPUs 0-3, TP=4). No reasoning parser (the chat template has no think tags)
# and no tool-call parser (mini-swe-agent uses litellm_textbased).
#
# The HF repo ships tekken.json only (no tokenizer.json), so vLLM selects the
# mistral tokenizer mode itself; the HF-format shards (model-*.safetensors)
# are what scripts/maintenance downloads, the duplicate consolidated.safetensors
# is not needed.
#
# VLLM_SERVER_DEV_MODE=1 (vLLM's own switch) additionally exposes
# POST /reset_prefix_cache, which the probe's --reset-cache control needs.
#
# Usage:  AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_devstral2507_sandbox.sh
#         AGENTCTX_PROFILE=albus-swe PREFIX_CACHE=on bash scripts/serving/start_vllm_devstral2507_sandbox.sh
# Tail:   tail -f logs/servers/vllm_devstral2507_noprefixcache.latest.log   (or ..._prefixcache.latest.log)
# Check:  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/servers/vllm_devstral2507_noprefixcache.latest.log | tail -1
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_devstral2507_noprefixcache.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_kv_trace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/profiles.sh"
agentctx_profile

MODEL="mistralai/Devstral-Small-2507"
PORT="${DEVSTRAL_PORT:-8000}"
CUDA_DEVICES="${PROFILE_CUDA_DEVICES:-0,1,2,3}"
TP_SIZE="${PROFILE_TP_SIZE:-4}"
MAX_MODEL_LEN="${DEVSTRAL_MAX_MODEL_LEN:-131072}"
MAX_NUM_SEQS="${DEVSTRAL_MAX_NUM_SEQS:-64}"
PYTHON_BIN="$WS/venv/bin/python3"

case "${PREFIX_CACHE:-off}" in
    off) CACHE_ARG=--no-enable-prefix-caching; NAME=vllm_devstral2507_noprefixcache; CACHE_LABEL="OFF (sandbox)" ;;
    on)  CACHE_ARG=--enable-prefix-caching;    NAME=vllm_devstral2507_prefixcache;   CACHE_LABEL="ON" ;;
    *)   echo "[ERROR] PREFIX_CACHE must be off or on, got '${PREFIX_CACHE}'" >&2; exit 2 ;;
esac
PID_FILE="$SERVER_LOG_DIR/$NAME.pid"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi
if ss -ltnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[ERROR] Port $PORT already in use. Aborting." >&2
    ss -ltnp | grep ":${PORT} " >&2
    exit 1
fi
if pgrep -f 'vllm.entrypoints.openai.api_server.*Devstral-Small-2507' >/dev/null; then
    echo "[ERROR] vLLM Devstral-Small-2507 already running. Aborting." >&2
    pgrep -af 'vllm.entrypoints.openai.api_server.*Devstral-Small-2507' >&2
    exit 1
fi

# Timestamped log per startup (records its own engine config); <NAME>.latest.log
# points at the newest one, and the .latest.log + .pid pair is what the resource
# monitor's serving_info discovery expects.
LOG_FILE="$(server_log "$NAME")"
kv_trace_args "$LOG_FILE"
CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    "${KV_TRACE_ARGS[@]}" \
    --model "$MODEL" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    "$CACHE_ARG" \
    --enable-prompt-tokens-details \
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

echo "[$(date)] vLLM $MODEL launched as PID $VLLM_PID on GPUs $CUDA_DEVICES (TP=$TP_SIZE, $(profile_status)), port $PORT, prefix caching $CACHE_LABEL"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] $(kv_trace_status)"
echo "[$(date)] PID file: $PID_FILE"
echo ""
echo "Follow startup with:   tail -f logs/servers/$NAME.latest.log"
echo "Confirm the cache flag: grep -a -o 'enable_prefix_caching=[A-Za-z]*' $LOG_FILE | tail -1"
echo "Verify when ready:      curl -s http://localhost:${PORT}/v1/models | python3 -m json.tool"
