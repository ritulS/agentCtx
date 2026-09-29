#!/usr/bin/env bash
# Optional request-level KV ownership tracing. Source after WS is set.
KV_TRACE_ARGS=()
if [[ -n "${AGENTCTX_KV_TRACE_DIR:-}" ]]; then
    mkdir -p "$AGENTCTX_KV_TRACE_DIR"
    AGENTCTX_KV_TRACE_DIR="$(cd "$AGENTCTX_KV_TRACE_DIR" && pwd)"
    export AGENTCTX_KV_TRACE_DIR
    export PYTHONPATH="$WS/src${PYTHONPATH:+:$PYTHONPATH}"
    KV_TRACE_ARGS=(--scheduler-cls agentctx.vllm_kv_trace.TracingScheduler)
fi
