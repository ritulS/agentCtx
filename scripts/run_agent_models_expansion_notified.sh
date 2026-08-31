#!/usr/bin/env bash
# Run the agent-model expansion with Slack start/completion/failure notices.
#
# Prerequisite:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#
# Usage:
#   nohup env MAX_WORKERS=16 RUN_EVAL=1 \
#     bash scripts/run_agent_models_expansion_notified.sh glm \
#     > logs/followup_agent_models_glm_launcher.log 2>&1 &
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"

MODEL="${1:-}"
case "$MODEL" in
    devstral|glm) ;;
    *) echo "Usage: $0 {devstral|glm}" >&2; exit 2 ;;
esac

PY="${PYTHON:-$WS/venv/bin/python3}"
NOTIFIER="$WS/dashboard/notify_slack.py"
RUNNER="$WS/scripts/run_agent_models_expansion.sh"
UNIT="agent-model-expansion/$MODEL"
LOG_PATH="logs/followup_agent_models_${MODEL}_launcher.log"

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
# runner and its current Python worker together before the Slack notice is sent.
setsid bash "$RUNNER" "$MODEL" &
child_pid=$!
wait "$child_pid"
status=$?
exit "$status"
