#!/usr/bin/env bash
# r2 extension campaign on SWE-Bench: adaptive primitive-order cells on the
# 7 P30S tasks Qwen3.5-35B-A3B never resolved under any fixed primitive
# (task_lists/swe_verified/p30s_qwen35b_never_resolved.json).
#
# Every cell is the runner's dedicated `adaptive` condition driven by a JSON
# schedule from configs/adaptive/never7_prefix3/<pattern>.json: the primitive
# fired at compression events 1, 2, 3 (t = TR, s = SU-free; the last entry is
# held for later events). See that directory's README.md.
#
# Mirrors scripts/expansions/run_r2_swe_p30s.sh:
#   Agent      : Qwen3.5-35B-A3B, configs/config-qwen-vllm.yaml, :8000
#   Summarizer : the agent model itself (no --summary-config, no second server)
#   Cells      : d05__b15k__adaptive-prefix3-<pattern>, one per PATTERNS entry
#                (default: the six mixed patterns tts tst tss stt sts sst)
#   Tasks      : never7 x RUNS_PER_TASK runs (default 3) -> 6 cells x 7 x 3 = 126 runs
# Results go to data/r2/swebench/p30s_never7/<R2_MODEL>/<cell>/ (gitignored; see DATA.md).
#
# Usage: bash scripts/notify_run.sh --unit r2/swebench/p30s_never7/qwen35b \
#            -- bash scripts/expansions/run_r2_swe_never7_adaptive.sh
# One pattern only:
#   PATTERNS=tss bash scripts/expansions/run_r2_swe_never7_adaptive.sh
# Smoke test (1 task x 1 pattern x 1 run into a throwaway model dir; delete it afterwards —
# "-smoke" model dirs are ignored by build_coverage.py and aggregate_benchmark_results.py):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 PATTERNS=sts RUN_EVAL=0 \
#     R2_MODEL=qwen35b-smoke bash scripts/expansions/run_r2_swe_never7_adaptive.sh
# Overrides: R2_MODEL, RUNS_PER_TASK, MAX_WORKERS, N_TASKS (first N tasks of
#   TASKS_FILE), TASKS_FILE, SCHEDULE_DIR, PATTERNS, QWEN_AGENT_CONFIG,
#   QWEN_OTRC_CONFIG, QWEN_TAG, RUN_EVAL, QWEN_HEALTH_URL.
# Completed task/run keys are skipped on rerun; a different schedule in an
# existing cell is refused by the runner (use a new cell or model dir).
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"

PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/scripts/run_experiment_r2.py"
AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
OTRC_CONFIG="${QWEN_OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
MODEL_TAG="${QWEN_TAG:-qwen35-a3b}"                 # same tag as the ICLR Qwen runs
AGENT_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/p30s_qwen35b_never_resolved.json}"
SCHEDULE_DIR="${SCHEDULE_DIR:-$WS/configs/adaptive/never7_prefix3}"
R2_SECTION="p30s_never7"                            # data/r2/swebench/p30s_never7/
R2_MODEL="${R2_MODEL:-qwen35b}"                     # lowercase/digits/hyphens
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"          # override: RUNS_PER_TASK=<n> bash ...
MAX_WORKERS="${MAX_WORKERS:-16}"
RUN_EVAL="${RUN_EVAL:-1}"
N_TASKS="${N_TASKS:-}"          # empty = every task in TASKS_FILE
PATTERNS="${PATTERNS:-tts tst tss stt sts sst}"
LOG_FILE="${R2_NEVER7_LOG_FILE:-$(experiment_log "r2_sb_${R2_SECTION}_${R2_MODEL}")}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$OTRC_CONFIG"; require_file "$TASKS_FILE"
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

# Validate every pattern before the first run, so a typo in PATTERNS cannot
# stop the chain hours in. Patterns are lowercase letters/digits (cell tags).
for pat in $PATTERNS; do
    [[ "$pat" =~ ^[a-z0-9]+$ ]] || { echo "[ERROR] malformed PATTERNS entry: $pat" >&2; exit 1; }
    require_file "$SCHEDULE_DIR/$pat.json"
done

exec 9>"$EXPERIMENT_LOG_DIR/r2_sb_${R2_SECTION}_${R2_MODEL}.lock"
flock -n 9 || { echo "r2 $R2_SECTION launcher for $R2_MODEL already running." >&2; exit 1; }

curl -fsS --max-time 5 "$AGENT_HEALTH_URL" >/dev/null || {
    echo "[ERROR] vLLM server is not responding at $AGENT_HEALTH_URL" >&2; exit 1;
}
# The agent YAML must talk to the server that was just checked.
agent_api_base="$(sed -n 's/^[[:space:]]*api_base:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' "$AGENT_CONFIG" | head -1)"
[[ "$AGENT_HEALTH_URL" == "${agent_api_base%/}/models" ]] || {
    echo "[ERROR] agent api_base ($agent_api_base) does not match QWEN_HEALTH_URL ($AGENT_HEALTH_URL)" >&2; exit 1;
}

log() { echo "[$(date)] $*" | emit; }
log "=== r2 SWE-Bench $R2_SECTION | dest: data/r2/swebench/$R2_SECTION/$R2_MODEL | patterns: $PATTERNS | schedules: $SCHEDULE_DIR | agent: $AGENT_CONFIG | summarizer: agent model ==="
log "=== runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} workers=$MAX_WORKERS eval=$RUN_EVAL ==="

# run_runner <cell> <schedule.json> [extra runner args]
# No --budget / --depth: the adaptive condition takes both from the schedule
# entries, and the r2 launcher checks them against the cell name.
run_runner() {
    "$PY" "$RUNNER" \
        --r2-section "$R2_SECTION" --r2-model "$R2_MODEL" --r2-cell "$1" \
        --ablation "r2-${R2_MODEL}-${R2_SECTION}-$1" \
        --model-tag "$MODEL_TAG" \
        --agent-config "$AGENT_CONFIG" --otrc-config "$OTRC_CONFIG" \
        --tasks-file "$TASKS_FILE" \
        --conditions adaptive --adaptive-schedule "$2" \
        --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$MAX_WORKERS" "${EXTRA_ARGS[@]}" "${@:3}" 2>&1 | emit
}

for pat in $PATTERNS; do
    cell="d05__b15k__adaptive-prefix3-$pat"
    schedule="$SCHEDULE_DIR/$pat.json"
    log "--- $R2_SECTION/$R2_MODEL/$cell | schedule=$schedule ---"
    run_runner "$cell" "$schedule"
    if [[ "$RUN_EVAL" == 1 ]]; then
        run_runner "$cell" "$schedule" --eval-only
    fi
done
log "=== r2 SWE-Bench $R2_SECTION complete for $R2_MODEL ==="
