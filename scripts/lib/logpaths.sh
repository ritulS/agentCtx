#!/usr/bin/env bash
# Shared log-file conventions for the shell launchers. Source it after setting
# WS (or WORKSPACE); it never changes the current directory.
#
#   logs/experiments/<name>_<YYYYmmdd_HHMMSS>.log   launcher / experiment output
#   logs/experiments/<name>.latest.log              symlink to the newest one
#   logs/experiments/<name>.{lock,pid}              locks and PID files of runs
#   logs/servers/vllm_<name>_<YYYYmmdd_HHMMSS>.log  vLLM output (+ .latest.log)
#   logs/servers/vllm_<name>.pid                    vLLM process-group id
#
# Functions:
#   new_log_file <dir> <name>   create <dir>/<name>_<timestamp>.log, refresh the
#                               <name>.latest.log symlink, print the path
#   experiment_log <name>       the log this launcher should write to: the one
#                               an outer wrapper already owns (AGENTCTX_LOG_FILE)
#                               or a new file under logs/experiments/
#   server_log <name>           a new file under logs/servers/
#   emit [file]                 stdin -> stdout, and appended to <file>
#                               (default $LOG_FILE) unless stdout already flows
#                               into that file because the outer wrapper owns it
#
# The outermost script owns the log: it creates the file and exports
# AGENTCTX_LOG_FILE, and every launcher underneath writes to stdout only, so
# nothing is logged twice.

_logpaths_ws="${WS:-${WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}}"
LOG_ROOT="${AGENTCTX_LOG_ROOT:-$_logpaths_ws/logs}"
EXPERIMENT_LOG_DIR="$LOG_ROOT/experiments"
SERVER_LOG_DIR="$LOG_ROOT/servers"
unset _logpaths_ws

log_timestamp() { date '+%Y%m%d_%H%M%S'; }

new_log_file() {
    local dir="$1" name="$2" path
    mkdir -p "$dir"
    path="$dir/${name}_$(log_timestamp).log"
    : >> "$path"
    ln -sfn "$(basename "$path")" "$dir/${name}.latest.log"
    echo "$path"
}

experiment_log() {
    if [[ -n "${AGENTCTX_LOG_FILE:-}" ]]; then
        echo "$AGENTCTX_LOG_FILE"
    else
        new_log_file "$EXPERIMENT_LOG_DIR" "$1"
    fi
}

server_log() { new_log_file "$SERVER_LOG_DIR" "$1"; }

emit() {
    local file="${1:-${LOG_FILE:-}}"
    if [[ -z "$file" || "$file" == "${AGENTCTX_LOG_FILE:-}" ]]; then
        cat
    else
        tee -a "$file"
    fi
}
