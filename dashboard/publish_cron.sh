#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname -- "$SCRIPT_DIR")"
PYTHON="$PROJECT_DIR/venv/bin/python"
PUBLISHER="$SCRIPT_DIR/publish.py"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/dashboard-pages.log"
LOCK_FILE="/tmp/agentctx-dashboard-pages.lock"

mkdir -p "$LOG_DIR"

{
    printf '\n[%s] Starting dashboard publication\n' "$(date --iso-8601=seconds)"

    if [[ ! -x "$PYTHON" ]]; then
        printf 'ERROR: Python executable not found: %s\n' "$PYTHON"
        exit 1
    fi

    # Cron does not provide an interactive terminal. Fail immediately rather
    # than waiting for an SSH password/passphrase prompt during git push.
    export GIT_SSH_COMMAND="ssh -o BatchMode=yes"

    /usr/bin/flock -n -E 75 "$LOCK_FILE" \
        "$PYTHON" "$PUBLISHER"
    status=$?

    if [[ $status -eq 75 ]]; then
        printf 'Skipped: another dashboard publication is already running.\n'
        exit 0
    elif [[ $status -ne 0 ]]; then
        printf 'ERROR: dashboard publication failed with status %d.\n' "$status"
        exit "$status"
    fi

    printf '[%s] Dashboard publication finished\n' "$(date --iso-8601=seconds)"
} >> "$LOG_FILE" 2>&1
