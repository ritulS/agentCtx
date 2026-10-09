#!/usr/bin/env bash
# r2 extension campaign on SWE-Bench: the two uniform primitive orders, each on
# the tasks Qwen3.5-35B-A3B usually resolves under that very primitive.
#
#   1. R2_SECTION=p100_su_free_majority, pattern sss: SU-free chosen at every
#      compression event (through the runner's adaptive condition and
#      configs/adaptive/never7_prefix3/sss.json) on the first N_TASKS (default 5)
#      of task_lists/swe_verified/p100_qwen35b_su-free_majority_resolved.json
#      -> data/r2/swebench/p100_su_free_majority/<R2_MODEL>/d05__b15k__adaptive-prefix3-sss
#   2. R2_SECTION=p100_tr_majority, pattern ttt: TR at every event
#      (configs/adaptive/never7_prefix3/ttt.json) on the first N_TASKS (default 5)
#      of task_lists/swe_verified/p100_qwen35b_tr_majority_resolved.json
#      -> data/r2/swebench/p100_tr_majority/<R2_MODEL>/d05__b15k__adaptive-prefix3-ttt
#
# Both steps are scripts/expansions/run_r2_swe_never7_adaptive.sh with that
# section (same agent, summarizer = agent model, budget 15k, depth 0.5, runner
# default limits 300 steps / 5400 s, RUNS_PER_TASK default 15, evaluation after
# each cell), so every override of that launcher applies here too: N_TASKS
# (N_TASKS=all for every task of both lists), RUNS_PER_TASK, MAX_WORKERS,
# R2_MODEL, RUN_EVAL, STEP_LIMIT, AGENT_TIMEOUT, QWEN_* ... PATTERNS and
# TASKS_FILE are owned by the sections and must not be set.
# SECTIONS picks a subset / order (default "p100_su_free_majority p100_tr_majority").
# On Albus: AGENTCTX_PROFILE=albus-swe (scripts/lib/profiles.sh) makes the
# server script take all 8 GPUs and this chain run 8 workers (MAX_WORKERS wins).
#
# Usage: bash scripts/notify_run.sh --unit r2/swebench/majority_uniform/qwen35b \
#            -- bash scripts/expansions/run_r2_swe_majority_uniform.sh
# Albus:  AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_qwen35_prefix_cache.sh
#         AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_uniform/qwen35b \
#            -- bash scripts/expansions/run_r2_swe_majority_uniform.sh
#   (default: 5 tasks x 15 runs x 1 cell per section = 150 runs)
# Smoke test (1 task x 1 run per section, no eval, throwaway model dir; delete it afterwards):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 RUN_EVAL=0 R2_MODEL=qwen35b-smoke \
#     bash scripts/expansions/run_r2_swe_majority_uniform.sh
# Completed task/run keys are skipped on rerun (resume), so raising N_TASKS or
# RUNS_PER_TASK later only adds the missing runs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$WS"
source "$SCRIPT_DIR/../lib/logpaths.sh"

LAUNCHER="$SCRIPT_DIR/run_r2_swe_never7_adaptive.sh"   # sibling of this file
R2_MODEL="${R2_MODEL:-qwen35b}"
SECTIONS="${SECTIONS:-p100_su_free_majority p100_tr_majority}"
[[ -f "$LAUNCHER" ]] || { echo "[ERROR] Required file not found: $LAUNCHER" >&2; exit 1; }
for var in PATTERNS TASKS_FILE R2_SECTION; do
    [[ -z "${!var:-}" ]] || { echo "[ERROR] $var is chosen per section by this script; unset it" >&2; exit 1; }
done
for section in $SECTIONS; do
    case "$section" in
        p100_su_free_majority|p100_tr_majority) ;;
        *) echo "[ERROR] SECTIONS entry '$section' is not p100_su_free_majority | p100_tr_majority" >&2; exit 1 ;;
    esac
done

# One log for the whole chain: this script's (or, under notify_run.sh, the
# wrapper's); the per-section launcher is told it is owned and writes to stdout only.
LOG_FILE="$(experiment_log "r2_sb_majority_uniform_${R2_MODEL}")"
exec 8>"$EXPERIMENT_LOG_DIR/r2_sb_majority_uniform_${R2_MODEL}.lock"
flock -n 8 || { echo "r2 majority-uniform chain for $R2_MODEL already running." >&2; exit 1; }

log() { echo "[$(date)] $*" | emit; }
log "=== r2 SWE-Bench majority-uniform chain | model: $R2_MODEL | sections: $SECTIONS | n_tasks=${N_TASKS:-5 (section default)} runs/task=${RUNS_PER_TASK:-15 (section default)} ==="
for section in $SECTIONS; do
    log "--- section $section ---"
    AGENTCTX_LOG_FILE="$LOG_FILE" R2_SECTION="$section" R2_MODEL="$R2_MODEL" bash "$LAUNCHER" 2>&1 | emit
done
log "=== r2 SWE-Bench majority-uniform chain complete for $R2_MODEL ==="
