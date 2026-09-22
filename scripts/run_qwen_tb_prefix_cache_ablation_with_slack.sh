#!/usr/bin/env bash
# Terminal-Bench prefix-caching ablation (dashboard 5.b) with Slack
# start/completion/failure notices (same pattern as run_qwen_tb_main_with_slack.sh).
# Wraps scripts/run_qwen_tb_prefix_cache_ablation.sh; start vLLM with caching OFF
# (bash scripts/start_vllm_qwen35_no_prefix_cache.sh) and the Podman socket separately.
#
# Usage:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#   nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh \
#     > logs/followup_tb_qwen_noprefixcache.nohup.log 2>&1 &
# Every environment override of the underlying launcher (ICLR_MODEL, CELLS,
# TB_TASKS_FILE, N_TASKS, RUNS_PER_TASK, N_CONCURRENT, ...) passes through
# unchanged. Completed task/condition/run keys are skipped on rerun.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs
ICLR_MODEL="${ICLR_MODEL:-qwen35b-noprefixcache}"   # same default as the launcher
exec 9>"logs/qwen_tb_${ICLR_MODEL}_with_slack.lock"
flock -n 9 || { echo "Qwen TB prefix-cache-ablation launcher for $ICLR_MODEL already running." >&2; exit 1; }
: "${SLACK_WEBHOOK_URL:?Export SLACK_WEBHOOK_URL before launching}"
PY="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
LOG_FILE="${TB_PREFIXCACHE_LOG_FILE:-$WS/logs/followup_tb_qwen_${ICLR_MODEL}.log}"
UNIT="qwen-terminal-bench-prefix-cache-ablation/$ICLR_MODEL"
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
