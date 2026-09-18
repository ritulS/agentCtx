#!/usr/bin/env bash
# Run the SWE-Bench summarizer ablation (scripts/run_qwen_swe_summarizer_ablation.sh)
# with Slack start/completion/failure notices, like run_agent_models_expansion_notified.sh.
#
# Prerequisite:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#
# Usage (Qwen3.5-9B summarizer, defaults of the underlying launcher):
#   nohup bash scripts/run_qwen_swe_summarizer_ablation_notified.sh \
#     > logs/followup_sb_qwen_sumabl_qwen9b.nohup.log 2>&1 &
# Gemma-4-12B summarizer:
#   nohup env SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b \
#     bash scripts/run_qwen_swe_summarizer_ablation_notified.sh \
#     > logs/followup_sb_qwen_sumabl_gemma12b.nohup.log 2>&1 &
# Every environment override of the underlying launcher (SUMMARY_CONFIG, ICLR_MODEL,
# CELLS, N_TASKS, RUNS_PER_TASK, MAX_WORKERS, RUN_EVAL, ...) passes through unchanged.
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PY="${PYTHON:-$WS/venv/bin/python3}"
NOTIFIER="$WS/dashboard/notify_slack.py"
RUNNER="$WS/scripts/run_qwen_swe_summarizer_ablation.sh"
ICLR_MODEL="${ICLR_MODEL:-qwen35b-sum-qwen35-9b}"   # same default as the launcher
UNIT="summarizer-ablation/swebench/$ICLR_MODEL"
LOG_PATH="logs/followup_sb_qwen_sumabl_${ICLR_MODEL}_launcher.log"

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
# The launcher's own output is duplicated into LOG_PATH for the Slack notice.
setsid bash "$RUNNER" 2>&1 | tee -a "$LOG_PATH" &
child_pid=$!
wait "$child_pid"
status=${PIPESTATUS[0]:-$?}
exit "$status"
