#!/usr/bin/env bash
# Run a command with Slack start / completion / failure notices.
#
# Usage:
#   bash scripts/notify_run.sh --unit <name> [--log <file>] [--lock <name>]
#                              [--pid-file <file>] [--on-success <command>]
#                              -- <command> [args...]
#
#   --unit NAME        label shown in the Slack notices (required)
#   --log FILE         the command's stdout/stderr are appended here and the path is
#                      quoted in the completion notice (default: logs/<unit>.log,
#                      with "/" in the unit replaced by "_")
#   --lock NAME        refuse to start while logs/NAME.lock is held by another
#                      notify_run.sh (flock); the lock is released when the
#                      command and the wrapper have both exited
#   --pid-file FILE    write the command's PID here while it runs
#   --on-success CMD   run `bash -c CMD` after the completion notice when the
#                      command exited 0 (UNIT and LOG_FILE are exported to it)
#
# Environment:
#   SLACK_WEBHOOK_URL   incoming-webhook URL (required unless ALLOW_NO_SLACK=1;
#                       with ALLOW_NO_SLACK=1 and no URL, notices are skipped)
#   NOTIFY_PYTHON       interpreter for dashboard/notify_slack.py (default: python3)
#   AGENTCTX_WS         repository root (default: derived from this file)
#
# The command runs in its own session (setsid), so HUP / INT / TERM sent to the
# wrapper are forwarded to the whole process group and the completion notice is
# posted after the command has actually stopped. The exit status of the wrapper
# is the exit status of the command (129 / 130 / 143 when it was signalled).
#
# Example:
#   SLACK_WEBHOOK_URL=... nohup bash scripts/notify_run.sh \
#       --unit qwen-terminal-bench-main --lock qwen_tb_main \
#       -- bash scripts/expansions/run_agent_models_expansion_tb.sh qwen main \
#       > logs/followup_tb_qwen_main.nohup.log 2>&1 &
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"

usage() {
    sed -n '2,/^set -uo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//' >&2
    exit 2
}

UNIT=""
LOG_FILE=""
LOCK_NAME=""
PID_FILE=""
ON_SUCCESS=""
while (( $# )); do
    case "$1" in
        --unit)        UNIT="${2:-}"; shift 2 ;;
        --log)         LOG_FILE="${2:-}"; shift 2 ;;
        --lock)        LOCK_NAME="${2:-}"; shift 2 ;;
        --pid-file)    PID_FILE="${2:-}"; shift 2 ;;
        --on-success)  ON_SUCCESS="${2:-}"; shift 2 ;;
        --) shift; break ;;
        -h|--help) usage ;;
        *) echo "notify_run.sh: unknown option: $1" >&2; usage ;;
    esac
done
(( $# )) || { echo "notify_run.sh: no command given after --" >&2; usage; }
[[ -n "$UNIT" ]] || { echo "notify_run.sh: --unit is required" >&2; usage; }
[[ -n "$LOG_FILE" ]] || LOG_FILE="logs/${UNIT//\//_}.log"
mkdir -p logs "$(dirname "$LOG_FILE")"

if [[ -n "$LOCK_NAME" ]]; then
    exec 9>"logs/${LOCK_NAME}.lock"
    flock -n 9 || { echo "notify_run.sh: '$LOCK_NAME' is already running (logs/${LOCK_NAME}.lock)." >&2; exit 1; }
fi

if [[ -z "${SLACK_WEBHOOK_URL:-}" && "${ALLOW_NO_SLACK:-0}" != "1" ]]; then
    echo "notify_run.sh: export SLACK_WEBHOOK_URL before launching (or ALLOW_NO_SLACK=1 to run silently)." >&2
    exit 2
fi

PY="${NOTIFY_PYTHON:-python3}"
NOTIFIER="$WS/dashboard/notify_slack.py"
notify() {
    [[ -n "${SLACK_WEBHOOK_URL:-}" ]] || return 0
    "$PY" "$NOTIFIER" "$@" || echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Slack notification failed; experiment status is unchanged." >&2
}

child_pid=""
result="failed"

on_exit() {
    local status=$?
    trap - EXIT
    [[ -n "$PID_FILE" ]] && rm -f "$PID_FILE"
    (( status == 0 )) && result="success"
    notify stop "$UNIT" "$result" "$status" "$LOG_FILE"
    if (( status == 0 )) && [[ -n "$ON_SUCCESS" ]]; then
        UNIT="$UNIT" LOG_FILE="$LOG_FILE" bash -c "$ON_SUCCESS" || \
            echo "notify_run.sh: --on-success command failed (exit $?)." >&2
    fi
    exit "$status"
}

handle_signal() {
    local status="$1"
    result="killed"
    trap - HUP INT TERM
    if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
        kill -TERM -- "-$child_pid" 2>/dev/null || kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
    fi
    exit "$status"
}

trap on_exit EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

notify start "$UNIT"
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] notify_run.sh: unit=$UNIT log=$LOG_FILE command: $*" | tee -a "$LOG_FILE"

# Own session/process group so a stop signal reaches the command and everything
# it spawned. The process substitution keeps $! pointing at the command (whose
# PID is its group id) rather than at tee.
setsid "$@" > >(tee -a "$LOG_FILE") 2>&1 &
child_pid=$!
[[ -n "$PID_FILE" ]] && echo "$child_pid" > "$PID_FILE"
wait "$child_pid"
status=$?
exit "$status"
