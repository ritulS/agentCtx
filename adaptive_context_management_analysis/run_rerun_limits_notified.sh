#!/usr/bin/env bash
# Launch one phase of the raised-limit re-run (rerun_limit_failures.py) with
# Slack start / completion / failure notices, in the same style as
# scripts/expansions/run_agent_models_expansion_notified.sh.
#
# Qwen3.5-35B / full-context runs that hit the 1500 s timeout or the 125 step
# limit, split by SWE-bench Verified difficulty; hardest first within a phase.
#   Phase 1 (default): "15 min - 1 hour"        (55 runs)
#   Phase 2:           "1-4 hours" + ">4 hours" (17 runs)
#   Phase 3:           "<15 min fix"            (10 runs)
#
# Prerequisites:
#   export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
#   vLLM Qwen3.5-35B-A3B serving on :8000 (logs/vllm_qwen35_a3b.pid)
#   rootless podman API socket up (SWE-bench containers + evaluation)
#   an entry in Active_runs.md for this launch
#
# Usage:
#   DRY_RUN=1 bash adaptive_context_management_analysis/run_rerun_limits_notified.sh     # plan only, no Slack
#   nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh \
#       > logs/rerun_qwen35b_fc_limits_phase1_launcher.log 2>&1 &
#   PHASE=2 nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh \
#       > logs/rerun_qwen35b_fc_limits_phase2_launcher.log 2>&1 &
#   PHASE=3 ... (same, "<15 min fix")
#
# Overrides (environment): PHASE=1|2|3, STEP_LIMIT=200, TIMEOUT=3600, MAX_WORKERS=8,
#   ORDER=hard-first, WITH_EVAL=1, DIFFICULTY="u15 15m1h" (replaces the phase preset),
#   EXTRA_ARGS="--limit 4" (appended verbatim), ALLOW_NO_SLACK=1 (run without a webhook).
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

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
NOTIFIER="$WS/dashboard/notify_slack.py"
RUNNER="$WS/adaptive_context_management_analysis/rerun_limit_failures.py"
QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
PODMAN_SOCK="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"

UNIT="adaptive-context-management/rerun-qwen35b-fc-limits-phase${PHASE}"
LOG_PATH="logs/rerun_qwen35b_fc_limits_phase${PHASE}.log"
PID_PATH="logs/rerun_qwen35b_fc_limits_phase${PHASE}.pid"

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
if [[ -f "$PID_PATH" ]] && kill -0 "$(cat "$PID_PATH" 2>/dev/null)" 2>/dev/null; then
    echo "[ERROR] phase $PHASE already running (PID $(cat "$PID_PATH"), $PID_PATH)" >&2; fail=1
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
child_pid=""
exit_code="exited"

post_summary() {
    # Best-effort outcome summary of the new results file, posted after the runner.
    "$PY" - "$UNIT" "${RUNNER_ARGS[@]}" <<'PYEOF' || true
import json, re, sys, subprocess
from collections import Counter
from pathlib import Path
sys.path.insert(0, "dashboard")
from notify_slack import post_to_slack
unit, runner_args = sys.argv[1], sys.argv[2:]
plan = subprocess.run([sys.executable, "adaptive_context_management_analysis/rerun_limit_failures.py",
                       *[a for a in runner_args if a not in ("--with-eval",)], "--dry-run"],
                      capture_output=True, text=True).stdout
m = re.search(r"Output dir\s*:\s*(\S+)", plan)
if not m:
    raise SystemExit("could not find output dir in plan")
out = Path(m.group(1))
res_path = out / "experiment_results.json"
if not res_path.exists():
    raise SystemExit(f"no results at {res_path}")
rows = json.loads(res_path.read_text())
def outcome(r):
    if r.get("returncode") == -1: return "timeout"
    if r.get("exit_status") == "LimitsExceeded": return "step_limit"
    if r.get("exit_status") == "Submitted":
        return {True: "resolved", False: "submitted_unresolved", None: "submitted_uneval"}[r.get("resolved")]
    return f"other:{r.get('exit_status') or 'none'}"
c = Counter(outcome(r) for r in rows)
lines = "\n".join(f"• {k}: `{v}`" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))
post_to_slack(f"📊 *Raised-limit re-run summary* (`{unit}`)\n• runs recorded: `{len(rows)}`\n{lines}\n• results: `{res_path.relative_to(Path.cwd())}`")
PYEOF
}

notify_stop() {
    local status=$?
    local result="failed"
    trap - EXIT
    rm -f "$PID_PATH"
    if (( status == 0 )); then result="success"; fi
    "$PY" "$NOTIFIER" stop "$UNIT" "$result" "$exit_code" "$status" "$LOG_PATH" || true
    if (( status == 0 )); then post_summary; fi
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
log "phase=$PHASE  difficulty='$DIFFICULTY'  step_limit=$STEP_LIMIT  timeout=${TIMEOUT}s  workers=$MAX_WORKERS  order=$ORDER  with_eval=$WITH_EVAL"
log "command: $PY $RUNNER ${RUNNER_ARGS[*]}"
log "runner log: $LOG_PATH"

# Own process group so a stop signal terminates the runner and its agent
# subprocesses together before the Slack notice goes out.
setsid "$PY" "$RUNNER" "${RUNNER_ARGS[@]}" > "$LOG_PATH" 2>&1 &
child_pid=$!
echo "$child_pid" > "$PID_PATH"
wait "$child_pid"
status=$?
exit "$status"
