#!/usr/bin/env bash
# Notify Slack around FOLLOWUP_EXPERIMENTS (3.a); start vLLM/Podman separately.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs
exec 9>logs/glm_tb_main.lock
flock -n 9 || { echo 'GLM TB Main launcher already running.' >&2; exit 1; }
: "${SLACK_WEBHOOK_URL:?Export SLACK_WEBHOOK_URL before launching}"
PY="$WS/venv-harbor/bin/python"
LOG_FILE="${GLM_TB_LOG_FILE:-$WS/logs/followup_tb_glm_main.nohup.log}"
UNIT=glm-terminal-bench-main
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

export GLM_P_BUDGET=3000
export N_CONCURRENT="${N_CONCURRENT:-4}"
bash scripts/run_agent_models_expansion_tb.sh glm main
