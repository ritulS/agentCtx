#!/usr/bin/env bash
# Run the SWE-Bench prefix-caching ablation (scripts/run_qwen_swe_prefix_cache_ablation.sh)
# with Slack start/completion/failure notices, like run_agent_models_expansion_notified.sh.
#
# Prerequisites:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#   bash scripts/start_vllm_qwen35_prefix_cache.sh     # Qwen3.5-35B-A3B, prefix caching ON
#
# Usage:
#   nohup bash scripts/run_qwen_swe_prefix_cache_ablation_notified.sh \
#     > logs/followup_sb_qwen_prefixcache.nohup.log 2>&1 &
# Every environment override of the underlying launcher (ICLR_MODEL, CELLS, N_TASKS,
# RUNS_PER_TASK, MAX_WORKERS, RUN_EVAL, ...) passes through unchanged.
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PY="${PYTHON:-$WS/venv/bin/python3}"
NOTIFIER="$WS/dashboard/notify_slack.py"
RUNNER="$WS/scripts/run_qwen_swe_prefix_cache_ablation.sh"
ICLR_MODEL="${ICLR_MODEL:-qwen35b-prefixcache}"   # same default as the launcher
UNIT="prefix-cache-ablation/swebench/$ICLR_MODEL"
LOG_PATH="logs/followup_sb_qwen_${ICLR_MODEL}_launcher.log"

child_pid=""
exit_code="exited"

notify_stop() {
    local status=$?
    local result="failed"
    trap - EXIT

    if (( status == 0 )); then
        result="success"
    fi

    "$PY" "$NOTIFIER" stop "$UNIT" "$result" "$exit_code" "$status" \
        "$LOG_PATH" || true
    exit "$status"
}

handle_signal() {
    local status="$1"
    exit_code="killed"
    trap - HUP INT TERM

    if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
        kill -TERM -- "-$child_pid" 2>/dev/null || kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
    fi
    exit "$status"
}

trap notify_stop EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

"$PY" "$NOTIFIER" start "$UNIT" || true

# Give the experiment its own process group so a stop signal can terminate the
# launcher and its current Python worker together before the Slack notice is sent.
# The launcher's own output is duplicated into LOG_PATH for the Slack notice; the
# process substitution keeps $! pointing at the launcher (whose PID is its group
# id) rather than at tee, so both the signal and the exit status reach it.
setsid bash "$RUNNER" > >(tee -a "$LOG_PATH") 2>&1 &
child_pid=$!
wait "$child_pid"
status=$?
exit "$status"
