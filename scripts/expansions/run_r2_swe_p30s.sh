#!/usr/bin/env bash
# r2 extension campaign on SWE-Bench: the Qwen3.5-35B-A3B compression grid on
# the 30-task stratified cohort (P30S, task_lists/swe_verified/p30_stratified.json).
#
# Mirrors scripts/expansions/run_qwen_swe_prefix_cache_ablation.sh, minus the
# prefix-cache checks, and drives scripts/run_experiment_r2.py instead of the
# ICLR launcher:
#   Agent      : Qwen3.5-35B-A3B, configs/config-qwen-vllm.yaml, :8000
#   Summarizer : the agent model itself (no --summary-config, no second server)
#   Cells      : chosen by the first argument (a preset), default "free":
#                  free       di__b15k__{su-free,ss-free}  (length-free summaries)
#                  su-free    di__b15k__su-free
#                  ss-free    di__b15k__ss-free
#                  fc         di__binf__fc    (full context, unlimited budget)
#                  otrc       di__binf__otrc  (online TRC, unlimited budget)
#                  baselines  di__binf__{fc,otrc}
#                CELLS="cell:condition:depth ..." overrides the preset for any
#                other cell of the ICLR grid.
#   Tasks      : P30S x RUNS_PER_TASK runs (default 3) -> "free": 2 cells x 30 x 3 = 180 runs
# Results go to data/r2/swebench/p30s/<R2_MODEL>/<cell>/ (gitignored; see DATA.md).
# The p30s section keeps these runs apart from the ICLR tree and from any other
# r2 cohort, so completed keys of one cohort are never skipped-as-complete for
# another.
#
# Usage: bash scripts/notify_run.sh --unit r2/swebench/p30s/qwen35b \
#            -- bash scripts/expansions/run_r2_swe_p30s.sh [PRESET]
#   or:  nohup bash scripts/expansions/run_r2_swe_p30s.sh [PRESET] > logs/r2_sb_p30s.nohup.log 2>&1 &
# Full context only:
#   bash scripts/expansions/run_r2_swe_p30s.sh fc
# Other runs/task count (default 3):
#   RUNS_PER_TASK=5 bash scripts/expansions/run_r2_swe_p30s.sh
# Other cells ("cell:condition:depth" triples, space-separated):
#   CELLS="d05__b15k__tr:truncation:0.5 di__b15k__trc:tool-result-clear:0.5 di__binf__fc:full-context:0.5" \
#     bash scripts/expansions/run_r2_swe_p30s.sh
# Smoke test (1 task x 1 cell x 1 run into a throwaway model dir; delete it afterwards —
# "-smoke" model dirs are ignored by build_coverage.py and aggregate_benchmark_results.py):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 CELLS=di__b15k__su-free:summarization-free:0.5 \
#     R2_MODEL=qwen35b-smoke bash scripts/expansions/run_r2_swe_p30s.sh
# The other 70 P100 tasks (task_lists/swe_verified/p100_minus_p30s.json), kept in
# their own section data/r2/swebench/p100_minus_p30s/:
#   R2_SECTION=p100_minus_p30s bash scripts/expansions/run_r2_swe_p30s.sh
# Overrides: R2_SECTION (p30s | p100_minus_p30s; also picks the default TASKS_FILE),
#   R2_MODEL, RUNS_PER_TASK, MAX_WORKERS, N_TASKS (first N tasks of
#   TASKS_FILE), TASKS_FILE, QWEN_AGENT_CONFIG, QWEN_OTRC_CONFIG, QWEN_TAG,
#   RUN_EVAL, QWEN_HEALTH_URL, CELLS.
# Completed task/condition/run keys are skipped on rerun.
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
R2_SECTION="${R2_SECTION:-p30s}"                    # data/r2/swebench/<section>/
case "$R2_SECTION" in
    p30s)            DEFAULT_TASKS="p30_stratified.json" ;;
    p100_minus_p30s) DEFAULT_TASKS="p100_minus_p30s.json" ;;
    *) echo "[ERROR] unknown R2_SECTION '$R2_SECTION'; use p30s | p100_minus_p30s" >&2; exit 1 ;;
esac
TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/$DEFAULT_TASKS}"
R2_MODEL="${R2_MODEL:-qwen35b}"                     # lowercase/digits/hyphens
INF_BUDGET=999999999
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"          # override: RUNS_PER_TASK=<n> bash ...
MAX_WORKERS="${MAX_WORKERS:-16}"
RUN_EVAL="${RUN_EVAL:-1}"
N_TASKS="${N_TASKS:-}"          # empty = every task in TASKS_FILE
# "cell:condition:depth" triples, from the PRESET argument unless CELLS is set.
# The budget comes from the cell name: b<N>k -> N000, binf -> unlimited.
PRESET="${1:-free}"
case "$PRESET" in
    free)      PRESET_CELLS="di__b15k__su-free:summarization-free:0.5 di__b15k__ss-free:structured-summarize-free:0.5" ;;
    su-free)   PRESET_CELLS="di__b15k__su-free:summarization-free:0.5" ;;
    ss-free)   PRESET_CELLS="di__b15k__ss-free:structured-summarize-free:0.5" ;;
    fc)        PRESET_CELLS="di__binf__fc:full-context:0.5" ;;
    otrc)      PRESET_CELLS="di__binf__otrc:online-trc:0.5" ;;
    baselines) PRESET_CELLS="di__binf__fc:full-context:0.5 di__binf__otrc:online-trc:0.5" ;;
    *) echo "[ERROR] unknown preset '$PRESET'; use free | su-free | ss-free | fc | otrc | baselines (or set CELLS)" >&2; exit 1 ;;
esac
CELLS="${CELLS:-$PRESET_CELLS}"
LOG_FILE="${R2_P30S_LOG_FILE:-$(experiment_log "r2_sb_${R2_SECTION}_${R2_MODEL}")}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$OTRC_CONFIG"; require_file "$TASKS_FILE"
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

# budget_of <cell>: the token budget encoded in the cell name.
budget_of() {
    case "$1" in
        *__binf__*) echo "$INF_BUDGET" ;;
        *__b[1-9]*k__*)
            local tag="${1#*__b}"; tag="${tag%%k__*}"
            [[ "$tag" =~ ^[1-9][0-9]*$ ]] || return 1
            echo $((tag * 1000)) ;;
        *) return 1 ;;
    esac
}

# Validate every cell before the first run, so a typo in CELLS cannot stop the
# grid hours in.
for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    [[ -n "$cell" && -n "$condition" && -n "$depth" ]] || { echo "[ERROR] malformed CELLS entry: $spec" >&2; exit 1; }
    budget_of "$cell" >/dev/null || { echo "[ERROR] cell $cell has no b<N>k / binf budget tag" >&2; exit 1; }
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
log "=== r2 SWE-Bench $R2_SECTION | dest: data/r2/swebench/$R2_SECTION/$R2_MODEL | preset: $PRESET | agent: $AGENT_CONFIG | summarizer: agent model ==="
log "=== runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} workers=$MAX_WORKERS eval=$RUN_EVAL ==="

# run_runner <cell> <condition> <depth> <budget> [extra runner args]
run_runner() {
    "$PY" "$RUNNER" \
        --r2-section "$R2_SECTION" --r2-model "$R2_MODEL" --r2-cell "$1" \
        --ablation "r2-${R2_MODEL}-${R2_SECTION}-$1" \
        --model-tag "$MODEL_TAG" \
        --agent-config "$AGENT_CONFIG" --otrc-config "$OTRC_CONFIG" \
        --budget "$4" --depth "$3" --tasks-file "$TASKS_FILE" \
        --conditions "$2" --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$MAX_WORKERS" "${EXTRA_ARGS[@]}" "${@:5}" 2>&1 | emit
}

for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    budget="$(budget_of "$cell")"
    log "--- $R2_SECTION/$R2_MODEL/$cell | condition=$condition budget=$budget depth=$depth ---"
    run_runner "$cell" "$condition" "$depth" "$budget"
    if [[ "$RUN_EVAL" == 1 ]]; then
        run_runner "$cell" "$condition" "$depth" "$budget" --eval-only
    fi
done
log "=== r2 SWE-Bench $R2_SECTION complete for $R2_MODEL ==="
