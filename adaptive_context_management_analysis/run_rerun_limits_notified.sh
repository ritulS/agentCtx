#!/usr/bin/env bash
# Launch one phase of the raised-limit re-run (rerun_limit_failures.py) with
# Slack start / completion / failure notices (through scripts/notify_run.sh) and
# an outcome summary (post_rerun_summary.py) after a successful run.
#
# Qwen3.5-35B / full-context runs that hit the 1500 s timeout or the 125 step
# limit, split by SWE-bench Verified difficulty; hardest first within a phase.
#   Phase 1 (default): "15 min - 1 hour"        (55 runs)
#   Phase 2:           "1-4 hours" + ">4 hours" (17 runs)
#   Phase 3:           "<15 min fix"            (10 runs)
#
# Prerequisites:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#   vLLM Qwen3.5-35B-A3B serving on :8000 (logs/servers/vllm_qwen35_a3b.pid)
#   rootless podman API socket up (SWE-bench containers + evaluation)
#   an entry in Active_runs.md for this launch
#
# Usage:
#   DRY_RUN=1 bash adaptive_context_management_analysis/run_rerun_limits_notified.sh     # plan only, no Slack
#   bash adaptive_context_management_analysis/run_rerun_limits_notified.sh               # phase 1, detaches
#   PHASE=2 bash adaptive_context_management_analysis/run_rerun_limits_notified.sh
#   PHASE=3 ... (same, "<15 min fix")
# The launch detaches into the background (scripts/notify_run.sh) and prints the
# wrapper PID; FOREGROUND=1 keeps it attached (used by run_rerun_limits_overnight.sh).
#
# Overrides (environment): PHASE=1|2|3, STEP_LIMIT=200, TIMEOUT=3600, MAX_WORKERS=8,
#   ORDER=hard-first, WITH_EVAL=1, DIFFICULTY="u15 15m1h" (replaces the phase preset),
#   EXTRA_ARGS="--limit 4" (appended verbatim), ALLOW_NO_SLACK=1 (run without a webhook),
#   FOREGROUND=1 (do not detach).
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
source "$WS/scripts/lib/logpaths.sh"

PHASE="${PHASE:-1}"
case "$PHASE" in
    1) DEFAULT_DIFFICULTY="15m1h" ;;
    2) DEFAULT_DIFFICULTY="1to4h gt4h" ;;
    3) DEFAULT_DIFFICULTY="u15" ;;
    *) echo "[ERROR] PHASE must be 1, 2 or 3 (got '$PHASE')" >&2; exit 2 ;;
esac
DIFFICULTY="${DIFFICULTY:-$DEFAULT_DIFFICULTY}"
STEP_LIMIT="${STEP_LIMIT:-200}"
TIMEOUT="${TIMEOUT:-3600}"
MAX_WORKERS="${MAX_WORKERS:-8}"
ORDER="${ORDER:-hard-first}"
WITH_EVAL="${WITH_EVAL:-1}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
DRY_RUN="${DRY_RUN:-0}"

PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/adaptive_context_management_analysis/rerun_limit_failures.py"
QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
PODMAN_SOCK="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"

UNIT="adaptive-context-management/rerun-qwen35b-fc-limits-phase${PHASE}"
PID_PATH="$EXPERIMENT_LOG_DIR/rerun_qwen35b_fc_limits_phase${PHASE}.pid"

# shellcheck disable=SC2206
RUNNER_ARGS=(--step-limit "$STEP_LIMIT" --timeout "$TIMEOUT" --max-workers "$MAX_WORKERS"
             --order "$ORDER" --difficulty $DIFFICULTY)
if [[ "$WITH_EVAL" == "1" ]]; then RUNNER_ARGS+=(--with-eval); fi
# shellcheck disable=SC2206
if [[ -n "$EXTRA_ARGS" ]]; then RUNNER_ARGS+=($EXTRA_ARGS); fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"; }

# ── Plan only ──────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY RUN: phase=$PHASE unit=$UNIT"
    log "would run: $PY $RUNNER ${RUNNER_ARGS[*]}"
    exec "$PY" "$RUNNER" "${RUNNER_ARGS[@]}" --dry-run
fi

# ── Preflight ──────────────────────────────────────────────────────────────────
fail=0
if [[ -z "${SLACK_WEBHOOK_URL:-}" && "${ALLOW_NO_SLACK:-0}" != "1" ]]; then
    echo "[ERROR] SLACK_WEBHOOK_URL is not set (export it, or ALLOW_NO_SLACK=1 to run silently)" >&2; fail=1
fi
if [[ ! -x "$PY" ]]; then echo "[ERROR] python not found: $PY" >&2; fail=1; fi
if [[ ! -f "$RUNNER" ]]; then echo "[ERROR] runner not found: $RUNNER" >&2; fail=1; fi
if ! curl -sf "$QWEN_HEALTH_URL" 2>/dev/null | grep -q 'Qwen3.5-35B-A3B'; then
    echo "[ERROR] vLLM Qwen3.5-35B-A3B is not responding at $QWEN_HEALTH_URL" >&2
    echo "        (Devstral/GLM on another port does not count; start the Qwen server first)" >&2; fail=1
fi
if [[ "$PODMAN_SOCK" == unix://* && ! -S "${PODMAN_SOCK#unix://}" ]]; then
    echo "[ERROR] podman socket not found: ${PODMAN_SOCK#unix://}" >&2; fail=1
fi
if (( fail )); then exit 1; fi

# Other runners on the shared server inflate per-step latency, which is exactly
# what produced the original timeouts. Warn, do not refuse.
others="$(pgrep -af 'run_experiment(_iclr)?\.py|rerun_limit_failures\.py' | grep -v "$$" || true)"
if [[ -n "$others" ]]; then
    log "WARNING: other experiment runners are alive on this machine:"
    echo "$others"
fi
log "REMINDER: add/update the Active_runs.md entry for unit $UNIT"

# ── Slack-wrapped launch ───────────────────────────────────────────────────────
LOG_PATH="$(experiment_log "rerun_qwen35b_fc_limits_phase${PHASE}")"
log "phase=$PHASE  difficulty='$DIFFICULTY'  step_limit=$STEP_LIMIT  timeout=${TIMEOUT}s  workers=$MAX_WORKERS  order=$ORDER  with_eval=$WITH_EVAL"
log "command: $PY $RUNNER ${RUNNER_ARGS[*]}"
log "runner log: $LOG_PATH"

# notify_run.sh owns the lock (one launcher per phase), the PID file the
# overnight chain polls, the signal forwarding and the start/stop notices; the
# outcome summary is posted after a clean exit.
summary_cmd="$(printf '%q ' "$PY" "$WS/adaptive_context_management_analysis/post_rerun_summary.py" "$UNIT" "${RUNNER_ARGS[@]}")"
exec bash "$WS/scripts/notify_run.sh" ${FOREGROUND:+--foreground} \
    --unit "$UNIT" \
    --log "$LOG_PATH" \
    --lock "rerun_qwen35b_fc_limits_phase${PHASE}" \
    --pid-file "$PID_PATH" \
    --on-success "$summary_cmd" \
    -- "$PY" "$RUNNER" "${RUNNER_ARGS[@]}"
