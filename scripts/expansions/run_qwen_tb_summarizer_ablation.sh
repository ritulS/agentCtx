#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md §4.b: summarizer ablation on Terminal-Bench.
#   Agent      : Qwen3.5-35B-A3B  (scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh,    GPUs 0-3, :8000)
#   Summarizer : Qwen3.5-9B       (scripts/serving/start_vllm_qwen35_9b.sh, GPUs 4-5, :8001)
#   Cells      : d05__b3k__su-full (summarization, depth 0.5)
#                di__b3k__trc-su   (trc-su, depth-invariant)
# Results go to ICLR_results/terminalbench/model_ablation/<ICLR_MODEL>/<cell>
# (section + model dir both distinct from main/qwen35b), so the existing
# self-summarization baseline cells
# (ICLR_results/terminalbench/main/qwen35b/{d05__b3k__su-full,di__b3k__trc-su})
# are neither skipped-as-complete nor mixed with these runs.
# Start vLLM (both servers) and the Podman socket separately.
#
# Usage: nohup bash scripts/expansions/run_qwen_tb_summarizer_ablation.sh > logs/followup_tb_qwen_sumabl_qwen9b.nohup.log 2>&1 &
# Smoke test (1 task x 1 cell x 1 run into a throwaway model dir; delete it afterwards):
#   N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 \
#     ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/expansions/run_qwen_tb_summarizer_ablation.sh
# Overrides: SUMMARY_CONFIG, ICLR_SECTION, ICLR_MODEL, BUDGET, RUNS_PER_TASK, N_CONCURRENT,
#   N_TASKS (first N tasks of TB_TASKS_FILE), TB_TASKS_FILE, QWEN_AGENT_CONFIG,
#   QWEN_HEALTH_URL, SUMMARY_HEALTH_URL, CELLS.
# Completed task/condition/run keys are skipped on rerun.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/logpaths.sh"

PY="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
SUMMARY_CONFIG="${SUMMARY_CONFIG:-$WS/configs/config-summary-qwen35-9b.yaml}"
AGENT_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
SUMMARY_HEALTH_URL="${SUMMARY_HEALTH_URL:-http://localhost:8001/v1/models}"
# Baseline (self-summarization) cells are P-40 x 3 runs at 3k, so default to the
# same grid for a paired comparison. Set TB_TASKS_FILE / RUNS_PER_TASK to change.
TASKS_FILE="${TB_TASKS_FILE:-$WS/task_lists/tbench_p40.json}"
ICLR_SECTION="${ICLR_SECTION:-model_ablation}"     # main | ablation | model_ablation
ICLR_MODEL="${ICLR_MODEL:-qwen35b-sum-qwen35-9b}"   # lowercase/digits/hyphens only
BUDGET="${BUDGET:-3000}"
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
N_CONCURRENT="${N_CONCURRENT:-4}"
N_TASKS="${N_TASKS:-}"          # empty = every task in TB_TASKS_FILE
# "cell:condition:depth" triples; override CELLS to run a subset.
CELLS="${CELLS:-d05__b3k__su-full:summarization:0.5 di__b3k__trc-su:trc-su:0.5}"
LOG_FILE="${TB_SUMABL_LOG_FILE:-$(experiment_log "followup_tb_qwen_sumabl_${ICLR_MODEL}")}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$SUMMARY_CONFIG"; require_file "$TASKS_FILE"
[[ "$BUDGET" =~ ^[1-9][0-9]*000$ ]] || { echo "[ERROR] BUDGET must be a whole number of K tokens: $BUDGET" >&2; exit 1; }
budget_tag="b$((BUDGET / 1000))k"
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

exec 9>"$EXPERIMENT_LOG_DIR/qwen_tb_sumabl_${ICLR_MODEL}.lock"
flock -n 9 || { echo "Summarizer-ablation launcher for $ICLR_MODEL already running." >&2; exit 1; }

for url in "$AGENT_HEALTH_URL" "$SUMMARY_HEALTH_URL"; do
    curl -fsS --max-time 5 "$url" >/dev/null || {
        echo "[ERROR] vLLM server is not responding at $url" >&2; exit 1;
    }
done
# Guard against the summarizer YAML pointing at the agent server by mistake.
summary_api_base="$(sed -n 's/^[[:space:]]*api_base:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' "$SUMMARY_CONFIG" | head -1)"
agent_api_base="$(sed -n 's/^[[:space:]]*api_base:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' "$AGENT_CONFIG" | head -1)"
if [[ -n "$summary_api_base" && "$summary_api_base" == "$agent_api_base" ]]; then
    echo "[ERROR] summarizer api_base equals agent api_base ($agent_api_base); check $SUMMARY_CONFIG" >&2
    exit 1
fi

log() { echo "[$(date)] $*" | emit; }
log "=== Summarizer ablation (TB) | dest: $ICLR_SECTION/$ICLR_MODEL | agent: $AGENT_CONFIG | summarizer: $SUMMARY_CONFIG ==="
log "=== budget=$BUDGET runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} concurrency=$N_CONCURRENT ==="

for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    [[ "$cell" == *"__${budget_tag}__"* ]] || {
        echo "[ERROR] cell $cell does not match BUDGET=$BUDGET ($budget_tag)" >&2; exit 1;
    }
    log "--- $ICLR_SECTION/$ICLR_MODEL/$cell | condition=$condition budget=$BUDGET depth=$depth ---"
    "$PY" "$RUNNER" \
        --iclr-benchmark terminal-bench --iclr-section "$ICLR_SECTION" \
        --iclr-model "$ICLR_MODEL" --iclr-cell "$cell" \
        --benchmark terminal-bench --model-tag "$ICLR_MODEL" \
        --agent-config "$AGENT_CONFIG" --summary-config "$SUMMARY_CONFIG" \
        --budget "$BUDGET" --depth "$depth" --tasks-file "$TASKS_FILE" \
        --conditions "$condition" --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$N_CONCURRENT" "${EXTRA_ARGS[@]}" 2>&1 | emit
done
log "=== Summarizer ablation (TB) complete for $ICLR_MODEL ==="
