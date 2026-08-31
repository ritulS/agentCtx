#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md section 2: SWE-Bench "Add 2 agent models".
#
# Implements the complete 3-runs/task grid for:
#   2.a/2.c Devstral-Small-2-24B (P100 main + ABL-30 ablation)
#   2.b/2.d GLM-4.7-Flash       (P100 main + ABL-30 ablation)
#
# Output follows ICLR_results/README.md exactly. Each primitive gets one cell:
#   ICLR_results/swebench/{main|ablation}/{model}/{depth}__{budget}__{primitive}/
# Safe to re-run: the underlying runner skips completed task/condition/run keys.
# Run after the current experiment has finished; this script does not stop or
# wait for an existing experiment automatically.
#
# Usage:
#   bash scripts/run_agent_models_expansion.sh devstral
#   bash scripts/run_agent_models_expansion.sh glm
#
# Optional environment overrides:
#   AGENTCTX_WS=/path/to/agentCtx MAX_WORKERS=16 RUN_EVAL=0 bash ...
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"

MODEL="${1:-}"
case "$MODEL" in
    devstral|glm) ;;
    *) echo "Usage: $0 {devstral|glm}" >&2; exit 2 ;;
esac

PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
P100="$WS/task_lists/p100_all_100_tasks.json"
ABL30="$WS/task_lists/ablation_30tasks.json"
RUNS_PER_TASK=3
MAX_WORKERS="${MAX_WORKERS:-16}"
RUN_EVAL="${RUN_EVAL:-1}"
INF_BUDGET=999999999

# Calibrated from the SWE-Bench P100 FC run_1 peak step-prompt-token
# distribution (n=100): A/P/B use P5/P15/P25, rounded to the nearest 1K.
# They can also be overridden without editing:
#   DEVSTRAL_A_BUDGET=... DEVSTRAL_P_BUDGET=... DEVSTRAL_B_BUDGET=... bash ...
DEVSTRAL_A_BUDGET="${DEVSTRAL_A_BUDGET:-17000}"
DEVSTRAL_P_BUDGET="${DEVSTRAL_P_BUDGET:-21000}"
DEVSTRAL_B_BUDGET="${DEVSTRAL_B_BUDGET:-24000}"

# Calibrated GLM budgets. Override via GLM_{A,P,B}_BUDGET if needed.
GLM_A_BUDGET="${GLM_A_BUDGET:-10000}"
GLM_P_BUDGET="${GLM_P_BUDGET:-13000}"
GLM_B_BUDGET="${GLM_B_BUDGET:-15000}"

DEVSTRAL_TAG="devstral-2"
DEVSTRAL_CONFIG="$WS/configs/config-devstral-vllm.yaml"
DEVSTRAL_OTRC_CONFIG="${DEVSTRAL_OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
DEVSTRAL_HEALTH_URL="http://localhost:8002/v1/models"

GLM_TAG="${GLM_TAG:-glm47-flash}"
GLM_CONFIG="${GLM_CONFIG:-$WS/configs/config-glm47flash-vllm.yaml}"
GLM_OTRC_CONFIG="${GLM_OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
GLM_HEALTH_URL="${GLM_HEALTH_URL:-http://localhost:8003/v1/models}"

LOG="$WS/logs/followup_agent_models_${MODEL}.log"
mkdir -p "$WS/logs"

SINGLES=(truncation summarization summarization-partial structured-summarize structured-summarize-partial)
INVARIANT=(tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial)
BASELINES=(full-context online-trc)

primitive_name() {
    case "$1" in
        truncation) echo tr ;;
        summarization) echo su-full ;;
        summarization-partial) echo su-partial ;;
        structured-summarize) echo ss ;;
        structured-summarize-partial) echo ss-partial ;;
        tool-result-clear) echo trc ;;
        trc-su) echo trc-su ;;
        trc-ss) echo trc-ss ;;
        otrc-tr) echo otrc-tr ;;
        otrc-su-partial) echo otrc-su-partial ;;
        otrc-ss-partial) echo otrc-ss-partial ;;
        full-context) echo fc ;;
        online-trc) echo otrc ;;
        *) echo "[ERROR] No ICLR primitive name for condition: $1" >&2; return 1 ;;
    esac
}

numeric_budget_tag() {
    local budget="$1"
    if (( budget % 1000 != 0 )); then
        echo "[ERROR] ICLR numeric budget naming requires a whole number of K tokens: $budget" >&2
        return 1
    fi
    echo "b$((budget / 1000))k"
}

log() { echo "[$(date)] $*" | tee -a "$LOG"; }

require_file() {
    if [[ ! -f "$1" ]]; then
        echo "[ERROR] Required file not found: $1" >&2
        exit 1
    fi
}

validate_ordered_budgets() {
    local label="$1" a_budget="$2" p_budget="$3" b_budget="$4"
    local value
    for value in "$a_budget" "$p_budget" "$b_budget"; do
        if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
            echo "[ERROR] $label budgets must be positive integer token counts." >&2
            exit 1
        fi
    done
    if ! (( a_budget < p_budget && p_budget < b_budget )); then
        echo "[ERROR] Expected $label budgets to satisfy A < P < B." >&2
        exit 1
    fi
}

run_cell() {
    local tag="$1" model_dir="$2" config="$3" otrc_config="$4" section="$5"
    local depth_tag="$6" budget_tag="$7" budget="$8" depth="$9" tasks_file="${10}"
    shift 10
    local conditions=("$@")

    local condition primitive cell
    for condition in "${conditions[@]}"; do
        primitive="$(primitive_name "$condition")"
        cell="${depth_tag}__${budget_tag}__${primitive}"
        log "--- $section/$model_dir/$cell | budget=$budget depth=$depth tasks=$(basename "$tasks_file") ---"
        "$PY" "$RUNNER" \
            --iclr-section "$section" \
            --iclr-model "$model_dir" \
            --iclr-cell "$cell" \
            --ablation "iclr-${model_dir}-${section}-${cell}" \
            --model-tag "$tag" \
            --agent-config "$config" \
            --otrc-config "$otrc_config" \
            --budget "$budget" \
            --depth "$depth" \
            --tasks-file "$tasks_file" \
            --conditions "$condition" \
            --runs-per-task "$RUNS_PER_TASK" \
            --max-workers "$MAX_WORKERS" \
            2>&1 | tee -a "$LOG"

        if [[ "$RUN_EVAL" == 1 ]]; then
            "$PY" "$RUNNER" \
                --iclr-section "$section" \
                --iclr-model "$model_dir" \
                --iclr-cell "$cell" \
                --ablation "iclr-${model_dir}-${section}-${cell}" \
                --model-tag "$tag" \
                --agent-config "$config" \
                --otrc-config "$otrc_config" \
                --budget "$budget" \
                --depth "$depth" \
                --tasks-file "$tasks_file" \
                --conditions "$condition" \
                --runs-per-task "$RUNS_PER_TASK" \
                --max-workers "$MAX_WORKERS" \
                --eval-only \
                2>&1 | tee -a "$LOG"
        fi
    done
}

run_model() {
    local label="$1" tag="$2" model_dir="$3" config="$4" otrc_config="$5" health_url="$6"
    local a_budget="$7" p_budget="$8" b_budget="$9"
    local a_tag="${10}" p_tag="${11}" b_tag="${12}"

    require_file "$config"
    require_file "$otrc_config"
    if ! curl -sf "$health_url" >/dev/null 2>&1; then
        echo "[ERROR] $label server is not responding at $health_url" >&2
        exit 1
    fi

    log "=== $label: section 2 main (P100) ==="
    run_cell "$tag" "$model_dir" "$config" "$otrc_config" main d05 "$p_tag" \
        "$p_budget" 0.5 "$P100" "${SINGLES[@]}"
    run_cell "$tag" "$model_dir" "$config" "$otrc_config" main di "$p_tag" \
        "$p_budget" 0.5 "$P100" "${INVARIANT[@]}"
    run_cell "$tag" "$model_dir" "$config" "$otrc_config" main di binf \
        "$INF_BUDGET" 0.5 "$P100" "${BASELINES[@]}"

    log "=== $label: section 2 ablation (ABL-30) ==="
    # Tail depths use A/P/B: 5 * 2 * 3 * 30 * 3 = 2,700 runs.
    local depth depth_tag budget budget_tag pair
    for depth in 0.3 0.7; do
        depth_tag="d${depth/./}"
        for pair in "$a_budget:$a_tag" "$p_budget:$p_tag" "$b_budget:$b_tag"; do
            budget="${pair%%:*}"
            budget_tag="${pair##*:}"
            run_cell "$tag" "$model_dir" "$config" "$otrc_config" ablation \
                "$depth_tag" "$budget_tag" "$budget" "$depth" "$ABL30" "${SINGLES[@]}"
        done
    done
    # Canonical depth and invariant arms use A/B only: 900 + 1,080 runs.
    for pair in "$a_budget:$a_tag" "$b_budget:$b_tag"; do
        budget="${pair%%:*}"
        budget_tag="${pair##*:}"
        run_cell "$tag" "$model_dir" "$config" "$otrc_config" ablation \
            d05 "$budget_tag" "$budget" 0.5 "$ABL30" "${SINGLES[@]}"
        run_cell "$tag" "$model_dir" "$config" "$otrc_config" ablation \
            di "$budget_tag" "$budget" 0.5 "$ABL30" "${INVARIANT[@]}"
    done
    log "=== $label complete: 8,580 planned runs ==="
}

require_file "$PY"
require_file "$RUNNER"
require_file "$P100"
require_file "$ABL30"

if [[ "$MODEL" == devstral ]]; then
    validate_ordered_budgets "Devstral" "$DEVSTRAL_A_BUDGET" \
        "$DEVSTRAL_P_BUDGET" "$DEVSTRAL_B_BUDGET"
    DEVSTRAL_A_TAG="$(numeric_budget_tag "$DEVSTRAL_A_BUDGET")"
    DEVSTRAL_P_TAG="$(numeric_budget_tag "$DEVSTRAL_P_BUDGET")"
    DEVSTRAL_B_TAG="$(numeric_budget_tag "$DEVSTRAL_B_BUDGET")"
    run_model "Devstral-Small-2-24B" "$DEVSTRAL_TAG" devstral24b "$DEVSTRAL_CONFIG" \
        "$DEVSTRAL_OTRC_CONFIG" "$DEVSTRAL_HEALTH_URL" \
        "$DEVSTRAL_A_BUDGET" "$DEVSTRAL_P_BUDGET" "$DEVSTRAL_B_BUDGET" \
        "$DEVSTRAL_A_TAG" "$DEVSTRAL_P_TAG" "$DEVSTRAL_B_TAG"
fi

if [[ "$MODEL" == glm ]]; then
    validate_ordered_budgets "GLM" "$GLM_A_BUDGET" "$GLM_P_BUDGET" "$GLM_B_BUDGET"
    run_model "GLM-4.7-Flash" "$GLM_TAG" glm47flash "$GLM_CONFIG" \
        "$GLM_OTRC_CONFIG" "$GLM_HEALTH_URL" \
        "$GLM_A_BUDGET" "$GLM_P_BUDGET" "$GLM_B_BUDGET" bA bP bB
fi

log "=== Requested follow-up model experiments complete ==="
