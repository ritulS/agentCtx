#!/usr/bin/env bash
# Request-level KV ownership tracing (src/agentctx/KV_CACHE_TRACE.md), on by
# default. Source after WS is set and logpaths.sh is sourced, then call
#
#   kv_trace_args "$LOG_FILE"
#
# once the server log exists. It fills KV_TRACE_ARGS for the vLLM command line
# and exports AGENTCTX_KV_TRACE_DIR, by default logs/kv-cache/<server log name>,
# e.g. logs/servers/vllm_qwen35_a3b_20261003_120000.log traces into
# logs/kv-cache/vllm_qwen35_a3b_20261003_120000/.
#   AGENTCTX_KV_TRACE=0          serve without tracing
#   AGENTCTX_KV_TRACE_DIR=<dir>  trace into <dir> instead
KV_TRACE_ARGS=()

kv_trace_args() {
    local server_log="$1"
    KV_TRACE_ARGS=()
    if [[ "${AGENTCTX_KV_TRACE:-1}" == "0" ]]; then
        unset AGENTCTX_KV_TRACE_DIR
        return 0
    fi
    if [[ -z "${AGENTCTX_KV_TRACE_DIR:-}" ]]; then
        AGENTCTX_KV_TRACE_DIR="$LOG_ROOT/kv-cache/$(basename "$server_log" .log)"
    fi
    mkdir -p "$AGENTCTX_KV_TRACE_DIR"
    AGENTCTX_KV_TRACE_DIR="$(cd "$AGENTCTX_KV_TRACE_DIR" && pwd)"
    export AGENTCTX_KV_TRACE_DIR
    export PYTHONPATH="$WS/src${PYTHONPATH:+:$PYTHONPATH}"
    KV_TRACE_ARGS=(--scheduler-cls agentctx.vllm_kv_trace.TracingScheduler)
}

# For the launcher's closing summary.
kv_trace_status() {
    if [[ ${#KV_TRACE_ARGS[@]} -gt 0 ]]; then
        echo "KV ownership trace: $AGENTCTX_KV_TRACE_DIR"
    else
        echo "KV ownership trace: OFF (AGENTCTX_KV_TRACE=0)"
    fi
}
