#!/usr/bin/env bash
# Run a command in the background with Slack start / completion / failure notices.
#
# Usage:
#   bash scripts/notify_run.sh --unit <name> [--log <file>] [--lock <name>]
#                              [--pid-file <file>] [--on-success <command>]
#                              [--foreground] -- <command> [args...]
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
#   --foreground       stay attached: run the command in this terminal, mirror
#                      its output to stdout and return its exit status
#
# By default the wrapper validates its arguments, takes the lock, checks the
# webhook, then detaches itself (nohup + setsid, output to --log) and returns
# at once, printing the wrapper PID and the log path. The detached wrapper
# survives the terminal closing; `kill <wrapper PID>` stops the command and
# posts a "killed" notice. Sequential drivers (overnight chains) and dry runs
# should pass --foreground.
#
# Environment:
#   SLACK_WEBHOOK_URL   incoming-webhook URL (required unless ALLOW_NO_SLACK=1;
#                       with ALLOW_NO_SLACK=1 and no URL, notices are skipped)
#   NOTIFY_PYTHON       interpreter for dashboard/notify_slack.py (default: python3)
#   AGENTCTX_WS         repository root (default: derived from this file)
#
# The command runs in its own session (setsid), so HUP / INT / TERM sent to the
# wrapper are forwarded to the whole process group and the completion notice is
# posted after the command has actually stopped. In --foreground mode the exit
# status of the wrapper is the exit status of the command (129 / 130 / 143 when
# it was signalled).
#
# Examples:
#   SLACK_WEBHOOK_URL=... bash scripts/notify_run.sh \
#       --unit qwen-terminal-bench-main --lock qwen_tb_main \
#       -- bash scripts/expansions/run_agent_models_expansion_tb.sh qwen main
#   bash scripts/notify_run.sh --foreground --unit smoke -- bash scripts/... 
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
FOREGROUND=0
while (( $# )); do
    case "$1" in
        --unit)        UNIT="${2:-}"; shift 2 ;;
        --log)         LOG_FILE="${2:-}"; shift 2 ;;
        --lock)        LOCK_NAME="${2:-}"; shift 2 ;;
        --pid-file)    PID_FILE="${2:-}"; shift 2 ;;
        --on-success)  ON_SUCCESS="${2:-}"; shift 2 ;;
        --foreground)  FOREGROUND=1; shift ;;
        --) shift; break ;;
        -h|--help) usage ;;
        *) echo "notify_run.sh: unknown option: $1" >&2; usage ;;
    esac
done
(( $# )) || { echo "notify_run.sh: no command given after --" >&2; usage; }
[[ -n "$UNIT" ]] || { echo "notify_run.sh: --unit is required" >&2; usage; }
[[ -n "$LOG_FILE" ]] || LOG_FILE="logs/${UNIT//\//_}.log"
mkdir -p logs "$(dirname "$LOG_FILE")"

# NOTIFY_RUN_DETACHED=1 marks the re-executed background copy: it inherits the
# lock on fd 9 from the parent below and must not open it again.
DETACHED="${NOTIFY_RUN_DETACHED:-0}"
if [[ -n "$LOCK_NAME" && "$DETACHED" != "1" ]]; then
    exec 9>"logs/${LOCK_NAME}.lock"
    flock -n 9 || { echo "notify_run.sh: '$LOCK_NAME' is already running (logs/${LOCK_NAME}.lock)." >&2; exit 1; }
fi

if [[ -z "${SLACK_WEBHOOK_URL:-}" && "${ALLOW_NO_SLACK:-0}" != "1" ]]; then
    echo "notify_run.sh: export SLACK_WEBHOOK_URL before launching (or ALLOW_NO_SLACK=1 to run silently)." >&2
    exit 2
fi

stamp() { date '+%Y-%m-%d %H:%M:%S %Z'; }

if (( ! FOREGROUND )) && [[ "$DETACHED" != "1" ]]; then
    # Re-run this script detached from the terminal; fd 9 (the lock) is inherited.
    NOTIFY_RUN_DETACHED=1 nohup setsid bash "${BASH_SOURCE[0]}" \
        --unit "$UNIT" --log "$LOG_FILE" ${LOCK_NAME:+--lock "$LOCK_NAME"} \
        ${PID_FILE:+--pid-file "$PID_FILE"} ${ON_SUCCESS:+--on-success "$ON_SUCCESS"} \
        -- "$@" >>"$LOG_FILE" 2>&1 </dev/null &
    wrapper_pid=$!
    echo "notify_run.sh: started '$UNIT' in the background (wrapper PID $wrapper_pid)."
    echo "  log:  $LOG_FILE"
    echo "  stop: kill $wrapper_pid"
    exit 0
fi

PY="${NOTIFY_PYTHON:-python3}"
NOTIFIER="$WS/dashboard/notify_slack.py"
notify() {
    [[ -n "${SLACK_WEBHOOK_URL:-}" ]] || return 0
    "$PY" "$NOTIFIER" "$@" || echo "[$(stamp)] Slack notification failed; experiment status is unchanged." >&2
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
header="[$(stamp)] notify_run.sh: unit=$UNIT log=$LOG_FILE wrapper=$$ command: $*"

# Own session/process group so a stop signal reaches the command and everything
# it spawned. Detached: stdout is already the log file. Foreground: the process
# substitution mirrors the output and keeps $! pointing at the command (whose
# PID is its group id) rather than at tee.
if [[ "$DETACHED" == "1" ]]; then
    echo "$header"
    setsid "$@" >>"$LOG_FILE" 2>&1 &
else
    echo "$header" | tee -a "$LOG_FILE"
    setsid "$@" > >(tee -a "$LOG_FILE") 2>&1 &
fi
child_pid=$!
[[ -n "$PID_FILE" ]] && echo "$child_pid" > "$PID_FILE"
wait "$child_pid"
status=$?
exit "$status"
