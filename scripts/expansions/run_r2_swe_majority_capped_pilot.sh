#!/usr/bin/env bash
# Controlled-sandbox pilot: the r2 majority sections of
# scripts/expansions/run_r2_swe_never7_adaptive.sh (what the majority-uniform
# chain runs) on the tasks that actually compress, with the runaway-generation
# guards of configs/config-qwen-vllm-cap4k.yaml (max_tokens 4096, litellm timeout
# 600 s), at most 3 model-call attempts per step (MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=3,
# default 10), 3 concurrent runs instead of the albus-swe profile's 8, a 7200 s
# agent wall-clock limit, and a server WITHOUT prefix caching
# (scripts/serving/start_vllm_qwen35_sandbox.sh). Caching OFF is not optional:
# scripts/maintenance/probe_prefix_cache_effect.py (2026-10-09) showed that
# --enable-prefix-caching changes this hybrid model's greedy generations
# (29/40 replayed prompts diverge, median at token 30, even with no cache hit;
# within-server noise floor 1/40). Without the cache every call re-prefills the
# whole context (p50/p90/p99 16/54/236 s per call at 6 workers), hence the few
# workers and the long timeouts: the first attempt (6 workers, 180 s) lost
# 14/32 runs to the client timeout.
# Tasks: task_lists/swe_verified/sandbox_su_free_compressing4.json, the four of
# the SU-free majority first-5 whose every run compressed in the 2026-10-08 cell
# (django-11299, sklearn-25102, sklearn-10908, sklearn-11310; 49/82/27/49 events
# over 15 runs). django-11292 (15/15 resolved, compression in 6/15 runs) and
# django-11066 (0 compression events) are left out: a run that never compresses
# does not test a compression strategy. Everything else (section, 15 runs/task,
# budget, depth, schedule, summarizer = agent model, eval) is the section's own,
# so the result is directly comparable, task by task, with
# data/r2/swebench/<section>/qwen35b/ (2026-10-08/09, uncapped, prefix caching
# ON, 8 workers: 40/120 SU-free runs hit a >=600 s call or a 32768-token reply;
# 12 runs timed out). Dest: .../<section>/<R2_MODEL>/<cell>/. Afterwards, tag
# the runs with scripts/maintenance/tag_run_failures.py <cell>.
#
# The launcher refuses to start while the server on QWEN_HEALTH_URL reports
# enable_prefix_caching=True (vllm:cache_config_info on /metrics); set
# SANDBOX_ALLOW_PREFIX_CACHE=1 to run against such a server anyway.
#
#   default      : R2_MODEL=qwen35b-cap4k,         agent config ...-cap4k.yaml
#   NOTHINK=1    : R2_MODEL=qwen35b-cap4k-nothink, agent config ...-cap4k-nothink.yaml
#                  (thinking OFF as well; only if the capped run still fluctuates)
#   SUMMARIZER=nothink
#                : R2_MODEL=qwen35b-cap4k-sumnothink; the agent keeps the cap4k
#                  config (thinking ON) and only summary requests go through
#                  configs/config-summary-qwen35-35b-nothink.yaml (same model and
#                  server, thinking OFF, max_tokens 2048) with at most
#                  SUMMARY_MAX_ATTEMPTS=2 tries per event (MSWEA_SUMMARY_MAX_ATTEMPTS,
#                  default 5). Motivation: in qwen35b-cap4k the summarizer took 22%
#                  of the wall-clock (median 40 s per ~500-token summary) and the
#                  "truncated" fallbacks were 13-16k-char summaries filling the
#                  4096 cap. Not combinable with NOTHINK=1 (that config already
#                  turns thinking off for both). SUMMARY_CONFIG=<yaml> overrides
#                  the file. Measure first with
#                  scripts/maintenance/probe_summarizer_thinking.py.
#   SUMMARIZER=nothink4k
#                : R2_MODEL=qwen35b-cap4k-sumnothink4k; as nothink but with
#                  configs/config-summary-qwen35-35b-nothink-4k.yaml (reply cap
#                  4096) and the primitive's default 5 attempts
#                  (SUMMARY_MAX_ATTEMPTS overrides). Follow-up to the
#                  2026-10-11 sumnothink cell: 12/28 fallbacks were replies cut
#                  at 2048 tokens, none recovered on the single retry, and most
#                  >2048-token summaries in the earlier cells completed below
#                  4096. Same NOTHINK=1 restriction as nothink.
#   SECTIONS     : default "p100_su_free_majority" (p100_tr_majority runs ttt on the same tasks)
#   TASKS_FILE   : default task_lists/swe_verified/sandbox_su_free_compressing4.json
#   N_TASKS      : default all tasks of TASKS_FILE (the section's own default is 5)
#   MAX_WORKERS  : default 3 (overrides the albus-swe profile's 8)
#   AGENT_TIMEOUT: default 7200 s (runner default 5400; calls are slow without the cache)
#   R2_MODEL, RUNS_PER_TASK, RUN_EVAL, STEP_LIMIT
#                : passed through to the section launcher as usual
#
# Usage (Albus):
#   bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_a3b.pid        # if the caching-ON server is up
#   AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_qwen35_sandbox.sh   # TP=8, prefix caching OFF
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k \
#       -- bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink \
#       -- env SUMMARIZER=nothink bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink4k \
#       -- env SUMMARIZER=nothink4k bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh
# Smoke (1 task x 1 run, 4 steps, no eval; delete the model dir afterwards):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 RUN_EVAL=0 STEP_LIMIT=4 R2_MODEL=qwen35b-cap4k-smoke \
#       SANDBOX_ALLOW_PREFIX_CACHE=1 bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$WS"

[[ -z "${QWEN_AGENT_CONFIG:-}" ]] || { echo "[ERROR] QWEN_AGENT_CONFIG is chosen by this script (NOTHINK=0/1); unset it" >&2; exit 1; }
R2_MODEL_EXPLICIT="${R2_MODEL:-}"   # an explicit R2_MODEL is kept verbatim, whatever SUMMARIZER is
if [[ "${NOTHINK:-0}" == 1 ]]; then
    export QWEN_AGENT_CONFIG="$WS/configs/config-qwen-vllm-cap4k-nothink.yaml"
    export R2_MODEL="${R2_MODEL:-qwen35b-cap4k-nothink}"
else
    export QWEN_AGENT_CONFIG="$WS/configs/config-qwen-vllm-cap4k.yaml"
    export R2_MODEL="${R2_MODEL:-qwen35b-cap4k}"
fi
export MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT="${MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT:-3}"
SUMMARIZER="${SUMMARIZER:-agent}"
case "$SUMMARIZER" in
    agent) ;;
    nothink|nothink4k)
        [[ "${NOTHINK:-0}" != 1 ]] || { echo "[ERROR] SUMMARIZER=$SUMMARIZER is redundant with NOTHINK=1 (thinking is already off for both)" >&2; exit 1; }
        if [[ "$SUMMARIZER" == nothink ]]; then
            export SUMMARY_CONFIG="${SUMMARY_CONFIG:-$WS/configs/config-summary-qwen35-35b-nothink.yaml}"
            export MSWEA_SUMMARY_MAX_ATTEMPTS="${SUMMARY_MAX_ATTEMPTS:-2}"
        else
            export SUMMARY_CONFIG="${SUMMARY_CONFIG:-$WS/configs/config-summary-qwen35-35b-nothink-4k.yaml}"
            export MSWEA_SUMMARY_MAX_ATTEMPTS="${SUMMARY_MAX_ATTEMPTS:-5}"
        fi
        [[ -n "${R2_MODEL_EXPLICIT:-}" ]] || export R2_MODEL="${R2_MODEL%-sum*}-sum$SUMMARIZER" ;;
    *) echo "[ERROR] SUMMARIZER must be agent | nothink | nothink4k (got '$SUMMARIZER')" >&2; exit 1 ;;
esac
SECTIONS="${SECTIONS:-p100_su_free_majority}"
export MAX_WORKERS="${MAX_WORKERS:-3}"
export AGENT_TIMEOUT="${AGENT_TIMEOUT:-7200}"
export TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/sandbox_su_free_compressing4.json}"
export N_TASKS="${N_TASKS:-all}"
LAUNCHER="$SCRIPT_DIR/run_r2_swe_never7_adaptive.sh"
for f in "$QWEN_AGENT_CONFIG" "$TASKS_FILE" "$LAUNCHER" ${SUMMARY_CONFIG:+"$SUMMARY_CONFIG"}; do
    [[ -f "$f" ]] || { echo "[ERROR] Required file not found: $f" >&2; exit 1; }
done
for section in $SECTIONS; do
    case "$section" in
        p100_su_free_majority|p100_tr_majority) ;;
        *) echo "[ERROR] SECTIONS entry '$section' is not p100_su_free_majority | p100_tr_majority" >&2; exit 1 ;;
    esac
done

# The sandbox serving condition is prefix caching OFF; refuse a caching-ON server
# unless explicitly allowed, so the two cells cannot be mixed by accident.
metrics_url="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"; metrics_url="${metrics_url%/v1/models}/metrics"
prefix_state="$(curl -s --max-time 10 "$metrics_url" | grep -a -o 'enable_prefix_caching="[A-Za-z]*"' | head -1 || true)"
case "$prefix_state" in
    *False*) echo "[$(date)] server prefix caching: OFF ($prefix_state)" ;;
    *True*)
        if [[ "${SANDBOX_ALLOW_PREFIX_CACHE:-0}" == 1 ]]; then
            echo "[$(date)] WARNING: server prefix caching is ON; continuing because SANDBOX_ALLOW_PREFIX_CACHE=1"
        else
            echo "[ERROR] the server at $metrics_url reports $prefix_state; the sandbox expects prefix caching OFF" \
                 "(scripts/serving/start_vllm_qwen35_sandbox.sh). Set SANDBOX_ALLOW_PREFIX_CACHE=1 to override." >&2
            exit 1
        fi ;;
    *) echo "[$(date)] WARNING: could not read enable_prefix_caching from $metrics_url; continuing" ;;
esac

echo "[$(date)] capped pilot | agent config: $QWEN_AGENT_CONFIG | summarizer: ${SUMMARY_CONFIG:-agent model}${MSWEA_SUMMARY_MAX_ATTEMPTS:+ (max attempts $MSWEA_SUMMARY_MAX_ATTEMPTS)} | R2_MODEL=$R2_MODEL | retry attempts: $MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT | workers: $MAX_WORKERS | agent timeout: ${AGENT_TIMEOUT}s | tasks: $TASKS_FILE (n_tasks=$N_TASKS) | sections: $SECTIONS"
for section in $SECTIONS; do
    echo "[$(date)] --- section $section ---"
    R2_SECTION="$section" R2_MODEL="$R2_MODEL" bash "$LAUNCHER"
done
echo "[$(date)] capped pilot complete for $R2_MODEL"
