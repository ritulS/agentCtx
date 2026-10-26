#!/usr/bin/env bash
# Does a float32 SSM cache make vLLM prefix caching numerics-only for Qwen3.5?
#
# Runs scripts/maintenance/probe_prefix_cache_effect.py against four serving
# conditions of Qwen3.5-35B-A3B on GPUs 2-3 (TP=2, port 8012), one after the
# other, each server started by scripts/serving/start_vllm_qwen35_ssm_probe.sh
# with --mamba-ssm-cache-dtype $SSM_DTYPE (default float32):
#   off      caching OFF
#   off2     caching OFF, a second fresh server      (process-to-process noise)
#   on_cold  caching ON, /reset_prefix_cache before every request (0 hits)
#   on       caching ON, warm (pass 2 hits the full prefix)
# then prints the comparisons. Verdict rule (same as the Devstral probe of
# 2026-10-17): if off2 vs on_cold agrees as well as off vs off2, the cache no
# longer changes the computation (2026-10-09, bf16 SSM cache: OFF vs ON 11/40,
# ON cold vs warm 9/9).
#
# Output: data/r2/probes/prefix_cache_effect_ssm<dtype>/{prompts,off,off2,on_cold,on}.json
# and compare_*.txt / rows_*.csv next to them. The 40 prompts are the 2026-10-09
# set (data/r2/probes/prefix_cache_effect/prompts.json, copied from Albus).
#
#   SLACK_WEBHOOK_URL="$(cat ~/.config/agentctx/slack_webhook)" bash scripts/notify_run.sh \
#       --unit r2/probes/prefix_cache_effect_ssmfloat32 -- bash scripts/maintenance/run_prefix_cache_ssm_probe.sh
#   SSM_DTYPE=auto ...   # bf16 control on the same GPUs / TP
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source scripts/lib/logpaths.sh

export SSM_DTYPE="${SSM_DTYPE:-float32}"
export QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-35B-A3B}"
# same tag rule as start_vllm_qwen35_ssm_probe.sh (a3b for the 35B-A3B, else from the model id)
if [[ -n "${QWEN_MODEL_TAG:-}" ]]; then MODEL_TAG="$QWEN_MODEL_TAG"
elif [[ "$QWEN_MODEL" == "Qwen/Qwen3.5-35B-A3B" ]]; then MODEL_TAG=a3b
else MODEL_TAG="$(basename "$QWEN_MODEL" | tr '[:upper:]' '[:lower:]' | sed -E 's/^qwen3\.5-//; s/[^a-z0-9]+/-/g')"; fi
export QWEN_MODEL_TAG="$MODEL_TAG"
export QWEN_VLLM_PORT="${QWEN_VLLM_PORT:-8012}"
export QWEN_CUDA_VISIBLE_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-2,3}"
export QWEN_TENSOR_PARALLEL_SIZE="${QWEN_TENSOR_PARALLEL_SIZE:-2}"
API_BASE="http://127.0.0.1:${QWEN_VLLM_PORT}/v1"
PROMPTS="${PROMPTS:-$WS/data/r2/probes/prefix_cache_effect/prompts.json}"
if [[ "$MODEL_TAG" == a3b ]]; then OUT_DEFAULT="$WS/data/r2/probes/prefix_cache_effect_ssm${SSM_DTYPE}"
else OUT_DEFAULT="$WS/data/r2/probes/prefix_cache_effect_ssm${SSM_DTYPE}_qwen35_${MODEL_TAG}"; fi
OUT="${OUT:-$OUT_DEFAULT}"
PY="$WS/venv/bin/python3"
PROBE="$WS/scripts/maintenance/probe_prefix_cache_effect.py"
READY_TIMEOUT_S="${READY_TIMEOUT_S:-1800}"
LOG_FILE="$(experiment_log "prefix_cache_ssm_probe_${MODEL_TAG}_${SSM_DTYPE}")"

[[ -f "$PROMPTS" ]] || { echo "[ERROR] prompt set missing: $PROMPTS" >&2; exit 1; }
mkdir -p "$OUT"

log() { echo "[$(date)] $*" | emit; }

pid_file() {  # $1 = on|off
    local tag; [[ "$1" == on ]] && tag=prefixcache || tag=noprefixcache
    echo "$SERVER_LOG_DIR/vllm_qwen35_${MODEL_TAG}_ssm${SSM_DTYPE}_${tag}.pid"
}

start_server() {  # $1 = on|off
    log "starting caching-$1 server (SSM cache dtype $SSM_DTYPE)"
    PREFIX_CACHE="$1" bash scripts/serving/start_vllm_qwen35_ssm_probe.sh 2>&1 | emit
    local pf; pf="$(pid_file "$1")"
    local pid; pid="$(cat "$pf")"
    local t=0
    while ! curl -sf -m 5 "$API_BASE/models" >/dev/null 2>&1; do
        if ! kill -0 "$pid" 2>/dev/null; then
            log "[ERROR] server pid $pid exited before becoming ready; last log lines:"
            tail -n 30 "${pf%.pid}.latest.log" | emit
            exit 1
        fi
        if (( t >= READY_TIMEOUT_S )); then
            log "[ERROR] server not ready after ${READY_TIMEOUT_S}s"; exit 1
        fi
        sleep 10; t=$((t + 10))
    done
    log "server ready after ${t}s: $(curl -s "$API_BASE/models" | $PY -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')"
    curl -s "${API_BASE%/v1}/metrics" | grep -o 'vllm:cache_config_info{[^}]*}' | head -1 | cut -c1-300 | emit
}

stop_server() {  # $1 = on|off
    log "stopping caching-$1 server"
    bash scripts/serving/stop_vllm.sh "$(pid_file "$1")" 2>&1 | emit
}

collect() {  # $1 = label, rest = extra probe args
    local label="$1"; shift
    log "collect --label $label $*"
    "$PY" "$PROBE" --out "$OUT" collect --label "$label" --api-base "$API_BASE" \
        --prompts-from "$PROMPTS" "$@" 2>&1 | emit
}

cleanup() {
    for m in on off; do
        local pf; pf="$(pid_file "$m")"
        if [[ -f "$pf" ]] && kill -0 "$(cat "$pf")" 2>/dev/null; then
            log "cleanup: stopping leftover caching-$m server"
            bash scripts/serving/stop_vllm.sh "$pf" 2>&1 | emit || true
        fi
    done
}
trap cleanup EXIT

log "prefix-cache SSM-dtype probe: MODEL=$QWEN_MODEL (tag $MODEL_TAG) SSM_DTYPE=$SSM_DTYPE GPUs=$QWEN_CUDA_VISIBLE_DEVICES TP=$QWEN_TENSOR_PARALLEL_SIZE port=$QWEN_VLLM_PORT out=$OUT"
log "prompts: $PROMPTS ($($PY -c "import json;print(len(json.load(open('$PROMPTS'))))" ) prompts)"

if [[ ! -f "$OUT/off.json" ]]; then
    start_server off; collect off; stop_server off
else log "off.json exists, skipping"; fi

if [[ ! -f "$OUT/off2.json" ]]; then
    start_server off; collect off2; stop_server off
else log "off2.json exists, skipping"; fi

if [[ ! -f "$OUT/on_cold.json" || ! -f "$OUT/on.json" ]]; then
    start_server on
    [[ -f "$OUT/on_cold.json" ]] || collect on_cold --reset-cache
    [[ -f "$OUT/on.json" ]] || collect on
    stop_server on
else log "on_cold.json and on.json exist, skipping"; fi

# ON process-to-process control (added 2026-10-24 after the 35B-A3B run): a
# second fresh caching-ON server, cache reset before every request.
if [[ "${ON2:-1}" == 1 && ! -f "$OUT/on_cold2.json" ]]; then
    start_server on; collect on_cold2 --reset-cache; stop_server on
else log "on_cold2.json exists or ON2=0, skipping"; fi

log "comparisons"
PAIRS=("off off2" "off2 on_cold" "on_cold on" "off on" "off on_cold")
[[ -f "$OUT/on_cold2.json" ]] && PAIRS+=("on_cold on_cold2" "off on_cold2")
for pair in "${PAIRS[@]}"; do
    set -- $pair
    log "== compare $1 vs $2"
    "$PY" "$PROBE" --out "$OUT" compare "$1" "$2" --csv "$OUT/rows_${1}_vs_${2}.csv" 2>&1 | tee "$OUT/compare_${1}_vs_${2}.txt" | emit
done
log "done; results under $OUT"
