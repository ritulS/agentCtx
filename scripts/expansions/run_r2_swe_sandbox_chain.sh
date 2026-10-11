#!/usr/bin/env bash
# Overnight sandbox chain (Albus, caching-OFF server): two capped-pilot cells
# back to back under the summarizer-only thinking-OFF / 4096-cap / 5-attempt
# settings (SUMMARIZER=nothink4k, scripts/expansions/run_r2_swe_majority_capped_pilot.sh):
#
#   step 1  p100_su_free_majority, sss, the 4 sandbox tasks x 15 runs
#           -> data/r2/swebench/p100_su_free_majority/qwen35b-cap4k-sumnothink4k/
#   step 2  p100_fc_only4, all eight prefix-3 orders (ttt tts tst tss stt sts sst
#           sss; the primitive at compression events 1-3, the third held after),
#           the first 2 tasks of its list (django-11433, sklearn-13124) x 15 runs
#           -> data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink4k/<cell>/
#           (8 cells x 2 tasks x 15 = 240 runs; section limits 400 steps / 7200 s)
#
# Each step is the capped pilot launcher, so completed (task, run) keys are
# skipped on rerun and the chain can be restarted. If a capped pilot is already
# running when the chain starts (e.g. step 1 was launched by hand), the chain
# waits for it to finish before starting (WAIT_FOR_PATTERN, polled every
# WAIT_POLL_S seconds), then runs its steps; a finished step 1 is then a quick
# no-op (nothing to run, nothing to evaluate).
#
#   SKIP_STEP1=1        : only step 2
#   SKIP_STEP2=1        : only step 1
#   RUNS_PER_TASK_STEP2 : default 15;  N_TASKS_STEP2: default 2;  PATTERNS_STEP2: default the
#                         section's eight orders
#   SUMMARIZER          : default nothink4k (agent | nothink | nothink4k); R2_MODEL follows it
#   anything else (MAX_WORKERS, AGENT_TIMEOUT, RUN_EVAL, ...) passes through to the pilot
#
# Usage (Albus):
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_chain/qwen35b-cap4k-sumnothink4k \
#       -- bash scripts/expansions/run_r2_swe_sandbox_chain.sh
# Smoke (fake-free, 1 run x 4 steps per step, no eval; delete the -smoke dirs afterwards):
#   RUNS_PER_TASK=1 RUNS_PER_TASK_STEP2=1 N_TASKS=1 N_TASKS_STEP2=1 PATTERNS_STEP2=tts MAX_WORKERS=1 \
#       RUN_EVAL=0 STEP_LIMIT=4 R2_MODEL=qwen35b-cap4k-sumnothink4k-smoke \
#       bash scripts/expansions/run_r2_swe_sandbox_chain.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$WS"
PILOT="$SCRIPT_DIR/run_r2_swe_majority_capped_pilot.sh"
[[ -f "$PILOT" ]] || { echo "[ERROR] Required file not found: $PILOT" >&2; exit 1; }
export SUMMARIZER="${SUMMARIZER:-nothink4k}"
WAIT_FOR_PATTERN="${WAIT_FOR_PATTERN:-run_r2_swe_majority_capped_pilot.sh}"
WAIT_POLL_S="${WAIT_POLL_S:-60}"
[[ -z "${SECTIONS:-}" && -z "${PATTERNS:-}" ]] || { echo "[ERROR] SECTIONS / PATTERNS are chosen per step by this chain; unset them (PATTERNS_STEP2 sets step 2's)" >&2; exit 1; }

log() { echo "[$(date)] sandbox chain: $*"; }

# Wait for a capped pilot launched outside this chain (its process tree is not ours).
if [[ -n "$WAIT_FOR_PATTERN" ]]; then
    waited=0
    while pgrep -f "$WAIT_FOR_PATTERN" -u "$(id -u)" >/dev/null 2>&1; do
        running="$(pgrep -f "$WAIT_FOR_PATTERN" -u "$(id -u)" | grep -vx "$$" || true)"
        [[ -n "$running" ]] || break
        (( waited % 1800 == 0 )) && log "waiting for a running capped pilot (pids: $(echo $running | tr '\n' ' '))"
        sleep "$WAIT_POLL_S"; waited=$(( waited + WAIT_POLL_S ))
    done
    (( waited == 0 )) || log "the running capped pilot finished after ${waited}s of waiting"
fi

if [[ "${SKIP_STEP1:-0}" != 1 ]]; then
    log "=== step 1: p100_su_free_majority sss x sandbox 4 tasks (SUMMARIZER=$SUMMARIZER) ==="
    SECTIONS=p100_su_free_majority bash "$PILOT"
    log "=== step 1 done ==="
fi
if [[ "${SKIP_STEP2:-0}" != 1 ]]; then
    log "=== step 2: p100_fc_only4, patterns ${PATTERNS_STEP2:-section default (8 orders)}, first ${N_TASKS_STEP2:-2} tasks x ${RUNS_PER_TASK_STEP2:-15} runs (SUMMARIZER=$SUMMARIZER) ==="
    step2_env=(SECTIONS=p100_fc_only4 N_TASKS="${N_TASKS_STEP2:-2}" RUNS_PER_TASK="${RUNS_PER_TASK_STEP2:-15}")
    [[ -z "${PATTERNS_STEP2:-}" ]] || step2_env+=(PATTERNS="$PATTERNS_STEP2")
    env -u TASKS_FILE "${step2_env[@]}" bash "$PILOT"
    log "=== step 2 done ==="
fi
log "chain complete"
