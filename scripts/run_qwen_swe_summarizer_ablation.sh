#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md §4.a: summarizer ablation on SWE-Bench.
#   Agent      : Qwen3.5-35B-A3B  (scripts/start_vllm_qwen35_swe_summarizer_ablation.sh,                :8000, GPUs 0-3 @0.70)
#   Summarizer : Qwen3.5-9B       (scripts/start_vllm_summarizer.sh qwen35-9b, :8001, GPUs 0-3 @0.15)
#                Gemma-4-12B: SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b
#   Cells      : d05__b15k__su-full (summarization, depth 0.5)
#                di__b15k__trc-su   (trc-su, depth-invariant)
#   Tasks      : ABL-25 x 3 runs (paired with the self-summarization baseline
#                cells ICLR_results/swebench/{main,ablation}/qwen35b/*__b15k__*).
# Results go to ICLR_results/swebench/model_ablation/<ICLR_MODEL>/<cell>
# (section + model dir both distinct from main/qwen35b), so the existing
# self-summarization cells are neither skipped-as-complete nor mixed with these
# runs. Start both vLLM servers and the Podman socket separately.
#
# Usage: nohup bash scripts/run_qwen_swe_summarizer_ablation.sh > logs/followup_sb_qwen_sumabl_qwen9b.nohup.log 2>&1 &
# Smoke test (1 task x 1 cell x 1 run into a throwaway model dir; delete it afterwards —
# "-smoke" model dirs are ignored by build_coverage.py and aggregate_benchmark_results.py):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 CELLS=d05__b15k__su-full:summarization:0.5 \
#     ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/run_qwen_swe_summarizer_ablation.sh
# Overrides: SUMMARY_CONFIG, ICLR_SECTION, ICLR_MODEL, BUDGET, RUNS_PER_TASK, MAX_WORKERS,
#   N_TASKS (first N tasks of TASKS_FILE), TASKS_FILE, QWEN_AGENT_CONFIG, RUN_EVAL,
#   QWEN_HEALTH_URL, SUMMARY_HEALTH_URL, CELLS.
# Completed task/condition/run keys are skipped on rerun.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
DEFAULT_SUMMARY_CONFIG="$WS/configs/config-summary-qwen35-9b.yaml"
DEFAULT_ICLR_MODEL="qwen35b-sum-qwen35-9b"
SUMMARY_CONFIG="${SUMMARY_CONFIG:-$DEFAULT_SUMMARY_CONFIG}"
AGENT_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
SUMMARY_HEALTH_URL="${SUMMARY_HEALTH_URL:-http://localhost:8001/v1/models}"
TASKS_FILE="${TASKS_FILE:-$WS/task_lists/ablation_25tasks.json}"
ICLR_SECTION="${ICLR_SECTION:-model_ablation}"     # main | ablation | model_ablation
ICLR_MODEL="${ICLR_MODEL:-$DEFAULT_ICLR_MODEL}"   # <agent>-sum-<summarizer>; lowercase/digits/hyphens
BUDGET="${BUDGET:-15000}"
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
MAX_WORKERS="${MAX_WORKERS:-16}"
RUN_EVAL="${RUN_EVAL:-1}"
N_TASKS="${N_TASKS:-}"          # empty = every task in TASKS_FILE
# "cell:condition:depth" triples; override CELLS to run a subset.
CELLS="${CELLS:-d05__b15k__su-full:summarization:0.5 di__b15k__trc-su:trc-su:0.5}"
LOG_FILE="${SB_SUMABL_LOG_FILE:-$WS/logs/followup_sb_qwen_sumabl_${ICLR_MODEL}.log}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$SUMMARY_CONFIG"; require_file "$TASKS_FILE"
[[ "$ICLR_MODEL" == *-sum-* ]] || {
    echo "[ERROR] ICLR_MODEL must be named <agent>-sum-<summarizer> (got $ICLR_MODEL)" >&2; exit 1;
}
# The destination encodes the summarizer: a different SUMMARY_CONFIG must go to
# a different model dir, otherwise completed keys of the default summarizer are
# skipped and the remaining ones are filled with another model. (The runner
# also refuses a summarizer mismatch against the runs already in the cell.)
if [[ "$(readlink -f "$SUMMARY_CONFIG")" != "$(readlink -f "$DEFAULT_SUMMARY_CONFIG")" \
      && "$ICLR_MODEL" == "$DEFAULT_ICLR_MODEL" ]]; then
    echo "[ERROR] SUMMARY_CONFIG=$SUMMARY_CONFIG differs from the default but ICLR_MODEL is still" \
         "$DEFAULT_ICLR_MODEL; set ICLR_MODEL=<agent>-sum-<summarizer> for this summarizer" >&2
    exit 1
fi
[[ "$BUDGET" =~ ^[1-9][0-9]*000$ ]] || { echo "[ERROR] BUDGET must be a whole number of K tokens: $BUDGET" >&2; exit 1; }
budget_tag="b$((BUDGET / 1000))k"
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

exec 9>"logs/qwen_sb_sumabl_${ICLR_MODEL}.lock"
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

log() { echo "[$(date)] $*" | tee -a "$LOG_FILE"; }
log "=== Summarizer ablation (SWE-Bench) | dest: $ICLR_SECTION/$ICLR_MODEL | agent: $AGENT_CONFIG | summarizer: $SUMMARY_CONFIG ==="
log "=== budget=$BUDGET runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} workers=$MAX_WORKERS eval=$RUN_EVAL ==="

run_runner() {
    "$PY" "$RUNNER" \
        --iclr-section "$ICLR_SECTION" --iclr-model "$ICLR_MODEL" --iclr-cell "$1" \
        --ablation "iclr-${ICLR_MODEL}-${ICLR_SECTION}-$1" \
        --model-tag "$ICLR_MODEL" \
        --agent-config "$AGENT_CONFIG" --summary-config "$SUMMARY_CONFIG" \
        --budget "$BUDGET" --depth "$3" --tasks-file "$TASKS_FILE" \
        --conditions "$2" --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$MAX_WORKERS" "${EXTRA_ARGS[@]}" "${@:4}" 2>&1 | tee -a "$LOG_FILE"
}

for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    [[ "$cell" == *"__${budget_tag}__"* ]] || {
        echo "[ERROR] cell $cell does not match BUDGET=$BUDGET ($budget_tag)" >&2; exit 1;
    }
    log "--- $ICLR_SECTION/$ICLR_MODEL/$cell | condition=$condition budget=$BUDGET depth=$depth ---"
    run_runner "$cell" "$condition" "$depth"
    if [[ "$RUN_EVAL" == 1 ]]; then
        run_runner "$cell" "$condition" "$depth" --eval-only
    fi
done
log "=== Summarizer ablation (SWE-Bench) complete for $ICLR_MODEL ==="
