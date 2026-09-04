#!/usr/bin/env bash
# Run the Qwen Terminal-Bench expansion and report its lifecycle to Slack.
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_FILE="${QWEN_TB_LOG_FILE:-$WS/logs/followup_tb_qwen_main.nohup.log}"
NOTIFIER="$WS/dashboard/notify_slack.py"
UNIT="qwen-terminal-bench-expansion"

notify() {
    "$WS/venv-harbor/bin/python" "$NOTIFIER" "$@" || \
        echo "[$(date)] Slack notification failed; experiment status is unchanged." >&2
}

on_exit() {
    local status="$1" result="failed"
    (( status == 0 )) && result="success"
    notify stop "$UNIT" "$result" "$status" "$LOG_FILE"
    exit "$status"
}

trap 'on_exit $?' EXIT

if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
    echo "[ERROR] Set SLACK_WEBHOOK_URL before launching this wrapper." >&2
    exit 2
fi

notify start "$UNIT"
cd "$WS"
bash scripts/run_agent_models_expansion_tb.sh qwen both >>"$LOG_FILE" 2>&1
