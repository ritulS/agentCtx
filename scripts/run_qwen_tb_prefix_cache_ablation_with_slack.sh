#!/usr/bin/env bash
# Terminal-Bench prefix-caching ablation (dashboard 5.b) with Slack
# start/completion/failure notices (same pattern as run_qwen_tb_main_with_slack.sh).
# Wraps scripts/run_qwen_tb_prefix_cache_ablation.sh; start vLLM with caching OFF
# (bash scripts/start_vllm_qwen35_no_prefix_cache.sh) and the Podman socket separately.
#
# Usage (single server, all 13 cells):
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#   nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh \
#     > logs/followup_tb_qwen_noprefixcache.nohup.log 2>&1 &
# Split grid (two caching-off servers, both halves at once):
#   gpu0-3 : depth-tunable @ 0.5 (5 cells) + FC / OTRC @ inf (2 cells) = 7 x 15 x 3 = 315 runs
#            server: bash scripts/start_vllm_qwen35_no_prefix_cache.sh          (:8000)
#   gpu4-7 : depth-invariant (6 cells)                                = 6 x 15 x 3 = 270 runs
#            server: bash scripts/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh   (:8002)
#   nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu0-3 \
#     > logs/followup_tb_qwen_noprefixcache_gpu0-3.nohup.log 2>&1 &
#   nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu4-7 \
#     > logs/followup_tb_qwen_noprefixcache_gpu4-7.nohup.log 2>&1 &
# Every environment override of the underlying launcher (ICLR_MODEL, CELLS,
# TB_TASKS_FILE, N_TASKS, RUNS_PER_TASK, N_CONCURRENT, ...) passes through
# unchanged; a group only sets defaults for CELLS, QWEN_AGENT_CONFIG and
# QWEN_HEALTH_URL. Completed task/condition/run keys are skipped on rerun.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs
ICLR_MODEL="${ICLR_MODEL:-qwen35b-noprefixcache}"   # same default as the launcher
group="${1:-}"
case "$group" in
    "") ;;   # single server, every cell (the launcher's default CELLS)
    gpu0-3)
        export CELLS="${CELLS:-d05__b3k__tr:truncation:0.5 \
d05__b3k__su-full:summarization:0.5 \
d05__b3k__su-partial:summarization-partial:0.5 \
d05__b3k__ss:structured-summarize:0.5 \
d05__b3k__ss-partial:structured-summarize-partial:0.5 \
di__binf__fc:full-context:0.5 \
di__binf__otrc:online-trc:0.5}"
        export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
        export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}" ;;
    gpu4-7)
        export CELLS="${CELLS:-di__b3k__trc:tool-result-clear:0.5 \
di__b3k__trc-su:trc-su:0.5 \
di__b3k__trc-ss:trc-ss:0.5 \
di__b3k__otrc-tr:otrc-tr:0.5 \
di__b3k__otrc-su-partial:otrc-su-partial:0.5 \
di__b3k__otrc-ss-partial:otrc-ss-partial:0.5}"
        export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm-8002.yaml}"
        export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8002/v1/models}" ;;
    *) echo "Usage: $0 [gpu0-3|gpu4-7]" >&2; exit 2 ;;
esac
export LAUNCH_GROUP="$group"
GROUP_SUFFIX="${group:+_$group}"
exec 9>"logs/qwen_tb_${ICLR_MODEL}${GROUP_SUFFIX}_with_slack.lock"
flock -n 9 || { echo "Qwen TB prefix-cache-ablation launcher for $ICLR_MODEL${group:+ ($group)} already running." >&2; exit 1; }
: "${SLACK_WEBHOOK_URL:?Export SLACK_WEBHOOK_URL before launching}"
PY="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
LOG_FILE="${TB_PREFIXCACHE_LOG_FILE:-$WS/logs/followup_tb_qwen_${ICLR_MODEL}${GROUP_SUFFIX}.log}"
UNIT="qwen-terminal-bench-prefix-cache-ablation/$ICLR_MODEL${group:+/$group}"
notify() {
    "$PY" dashboard/notify_slack.py "$@" || echo 'Slack notification failed.' >&2
}
on_exit() {
    local status=$? result=failed
    trap - EXIT
    (( status == 0 )) && result=success
    notify stop "$UNIT" "$result" "$status" "$LOG_FILE"
    exit "$status"
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
notify start "$UNIT"

export ICLR_MODEL
bash scripts/run_qwen_tb_prefix_cache_ablation.sh
