#!/usr/bin/env bash
# Overnight chain for the Qwen3.5-35B / full-context raised-limit re-runs.
# First waits for any running phase-3 runner (logs/rerun_qwen35b_fc_limits_phase3.pid)
# to exit, then runs two launches of run_rerun_limits_notified.sh back to back
# (never in parallel: concurrent runners on the shared vLLM inflate per-step
# latency, which is what produced the original timeouts):
#   A. phase 2  — "1-4 hours" + ">4 hours"       (17 runs)  at P2_STEP_LIMIT /
#                 P2_TIMEOUT (default 200 / 3600; set 300 / 7200 to match B)
#   B. again-19 — the 19 phase-1 runs that hit the raised limits again,
#                 at AGAIN_STEP_LIMIT / AGAIN_TIMEOUT (default 300 / 7200)
# Each stage keeps its own Slack unit, log and results dir.  A failed stage
# does not stop the chain.  Skip a stage with SKIP_PHASE2=1 / SKIP_AGAIN=1.
#
# Usage:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'   # or ALLOW_NO_SLACK=1
#   nohup bash adaptive_context_management_analysis/run_rerun_limits_overnight.sh \
#       > logs/rerun_qwen35b_fc_limits_overnight.log 2>&1 &
set -uo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"
W="adaptive_context_management_analysis/run_rerun_limits_notified.sh"
AGAIN_CSV="adaptive_context_management_analysis/results/model=qwen35b__primitive=fc/failure_causes_p1_again19.csv"
P2_STEP_LIMIT="${P2_STEP_LIMIT:-200}"
P2_TIMEOUT="${P2_TIMEOUT:-3600}"
AGAIN_STEP_LIMIT="${AGAIN_STEP_LIMIT:-300}"
AGAIN_TIMEOUT="${AGAIN_TIMEOUT:-7200}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"; }

# Do not overlap with a phase-3 runner that is still alive.
P3_PID="logs/rerun_qwen35b_fc_limits_phase3.pid"
if [[ -f "$P3_PID" ]] && kill -0 "$(cat "$P3_PID" 2>/dev/null)" 2>/dev/null; then
    log "phase 3 runner (PID $(cat "$P3_PID")) still alive; waiting for it to exit"
    while [[ -f "$P3_PID" ]] && kill -0 "$(cat "$P3_PID" 2>/dev/null)" 2>/dev/null; do sleep 60; done
    log "phase 3 runner exited"
fi

if [[ "${SKIP_PHASE2:-0}" != "1" ]]; then
    log "=== stage A: phase 2 at ${P2_STEP_LIMIT} steps / ${P2_TIMEOUT} s ==="
    PHASE=2 STEP_LIMIT="$P2_STEP_LIMIT" TIMEOUT="$P2_TIMEOUT" \
    bash "$W" > logs/rerun_qwen35b_fc_limits_phase2_launcher.log 2>&1
    log "stage A exit=$?"
fi
if [[ "${SKIP_AGAIN:-0}" != "1" ]]; then
    log "=== stage B: phase-1 again-19 at ${AGAIN_STEP_LIMIT} steps / ${AGAIN_TIMEOUT} s ==="
    PHASE=1 STEP_LIMIT="$AGAIN_STEP_LIMIT" TIMEOUT="$AGAIN_TIMEOUT" \
    EXTRA_ARGS="--causes-csv $AGAIN_CSV --name qwen35b__di__binf__fc__step_limit+timeout__step${AGAIN_STEP_LIMIT}__t${AGAIN_TIMEOUT}__p1again19" \
    bash "$W" > logs/rerun_qwen35b_fc_limits_p1again19_launcher.log 2>&1
    log "stage B exit=$?"
fi
log "=== overnight chain finished ==="
