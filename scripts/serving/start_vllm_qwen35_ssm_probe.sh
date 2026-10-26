#!/usr/bin/env bash
# Qwen3.5-35B-A3B probe server for the prefix-cache / SSM-state-dtype probe
# (scripts/maintenance/run_prefix_cache_ssm_probe.sh, 2026-10-24).
#
# Same engine configuration as the sandbox / prefix-cache-ablation servers
# (dtype auto, 102400 context, 64 seqs, reasoning parser qwen3,
# --enable-prompt-tokens-details, KV-ownership trace) plus
#   --mamba-ssm-cache-dtype $SSM_DTYPE   (default float32; "auto" = bf16, the
#                                         production setting)
# and VLLM_SERVER_DEV_MODE=1, which exposes POST /reset_prefix_cache for the
# probe's --reset-cache control. Why: with prefix caching ON vLLM puts this
# hybrid (Gated DeltaNet + attention) model into Mamba cache mode "align",
# which splits every prefill at the 528-token block boundary and round-trips
# the fp32 recurrent state through the SSM cache dtype there, so with the
# default bf16 cache a caching-ON server computes differently from a
# caching-OFF one even with zero cache hits (probe of 2026-10-09: OFF vs ON
# identical 11/40). A float32 SSM cache makes that round trip lossless.
#
# Defaults: GPUs 2-3, TP=2, port 8012 (the agent port 8000 stays free).
#
#   PREFIX_CACHE=off bash scripts/serving/start_vllm_qwen35_ssm_probe.sh
#   PREFIX_CACHE=on  bash scripts/serving/start_vllm_qwen35_ssm_probe.sh
#   SSM_DTYPE=auto PREFIX_CACHE=on bash scripts/serving/start_vllm_qwen35_ssm_probe.sh   # bf16 control
#   bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_a3b_ssmfloat32_prefixcache.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_kv_trace.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_reasoning.sh"
reasoning_parser_args qwen3

MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-35B-A3B}"
# Log / pid names: vllm_qwen35_<tag>_ssm<dtype>_<prefixcache|noprefixcache>[_mbs<N>];
# tag "a3b" for the 35B-A3B (the names of 2026-10-24), else from the model id
# (Qwen/Qwen3.5-27B → 27b). QWEN_MODEL_TAG overrides.
if [[ -n "${QWEN_MODEL_TAG:-}" ]]; then MODEL_TAG="$QWEN_MODEL_TAG"
elif [[ "$MODEL" == "Qwen/Qwen3.5-35B-A3B" ]]; then MODEL_TAG=a3b
else MODEL_TAG="$(basename "$MODEL" | tr '[:upper:]' '[:lower:]' | sed -E 's/^qwen3\.5-//; s/[^a-z0-9]+/-/g')"; fi
PORT="${QWEN_VLLM_PORT:-8012}"
CUDA_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-2,3}"
TP_SIZE="${QWEN_TENSOR_PARALLEL_SIZE:-2}"
MAX_MODEL_LEN="${QWEN_MAX_MODEL_LEN:-102400}"
MAX_NUM_SEQS="${QWEN_MAX_NUM_SEQS:-64}"
SSM_DTYPE="${SSM_DTYPE:-float32}"
# MAMBA_BLOCK_SIZE=<tokens> adds --mamba-block-size (caching ON only; vLLM
# rounds the attention/mamba block up to a multiple of it). The default block
# (528 with a bf16 SSM cache, 1056 with float32) is not a multiple of the GDN
# kernel's 64-token chunk, so the align-mode prefill split re-partitions the
# chunks; 1024 → a 2048-token block keeps the partition identical.
MAMBA_BLOCK_SIZE="${MAMBA_BLOCK_SIZE:-}"
PYTHON_BIN="${QWEN_VLLM_PYTHON:-$WS/venv/bin/python3}"

case "${PREFIX_CACHE:-}" in
    off) CACHE_ARG=--no-enable-prefix-caching; CACHE_TAG=noprefixcache ;;
    on)  CACHE_ARG=--enable-prefix-caching;    CACHE_TAG=prefixcache ;;
    *) echo "[ERROR] PREFIX_CACHE must be on or off (got '${PREFIX_CACHE:-}')" >&2; exit 1 ;;
esac
case "$SSM_DTYPE" in
    auto|float32|float16|bfloat16) ;;
    *) echo "[ERROR] SSM_DTYPE must be auto|float32|float16|bfloat16 (got '$SSM_DTYPE')" >&2; exit 1 ;;
esac
BLOCK_ARGS=()
NAME="vllm_qwen35_${MODEL_TAG}_ssm${SSM_DTYPE}_${CACHE_TAG}"
if [[ -n "$MAMBA_BLOCK_SIZE" ]]; then
    [[ "$PREFIX_CACHE" == on ]] || { echo "[ERROR] MAMBA_BLOCK_SIZE needs PREFIX_CACHE=on" >&2; exit 1; }
    BLOCK_ARGS=(--mamba-block-size "$MAMBA_BLOCK_SIZE")
    NAME="${NAME}_mbs${MAMBA_BLOCK_SIZE}"
fi
PID_FILE="$SERVER_LOG_DIR/${NAME}.pid"

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
    echo "[ERROR] $NAME already running (pid $(cat "$PID_FILE")). Aborting." >&2
    exit 1
fi

LOG_FILE="$(server_log "$NAME")"
kv_trace_args "$LOG_FILE"
CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" VLLM_SERVER_DEV_MODE=1 \
  nohup setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    "${KV_TRACE_ARGS[@]}" \
    --model "$MODEL" \
    "${REASONING_ARGS[@]}" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size "$TP_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    "$CACHE_ARG" \
    "${BLOCK_ARGS[@]}" \
    --mamba-ssm-cache-dtype "$SSM_DTYPE" \
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

echo "[$(date)] vLLM $MODEL launched as PID $VLLM_PID on GPUs $CUDA_DEVICES (TP=$TP_SIZE), port $PORT, $CACHE_ARG ${BLOCK_ARGS[*]:-}, --mamba-ssm-cache-dtype $SSM_DTYPE"
echo "[$(date)] Log: $LOG_FILE"
echo "[$(date)] PID file: $PID_FILE"
echo "[$(date)] $(kv_trace_status)"
