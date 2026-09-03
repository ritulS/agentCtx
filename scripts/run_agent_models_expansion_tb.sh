#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md (3.a/3.b): Terminal-Bench P-40 main and P-15 ablation grids.
# Usage: bash scripts/run_agent_models_expansion_tb.sh {qwen|devstral|glm|all} [main|ablation|both]
# The section defaults to both. Completed task/condition/run keys are skipped on rerun.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
PY="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
P40="${TB_P40_TASKS_FILE:-$WS/task_lists/tbench_p40.json}"
ABL15="${TB_ABL15_TASKS_FILE:-$WS/task_lists/tbench_abl15.json}"
RUNS_PER_TASK=3
N_CONCURRENT="${N_CONCURRENT:-4}"
INF_BUDGET=999999999

# Terminal-Bench calibrated A/P/B budgets (all values may be overridden).
QWEN_A_BUDGET="${QWEN_A_BUDGET:-2000}"
QWEN_P_BUDGET="${QWEN_P_BUDGET:-3000}"
QWEN_B_BUDGET="${QWEN_B_BUDGET:-4000}"
DEVSTRAL_A_BUDGET="${DEVSTRAL_A_BUDGET:-3000}"
DEVSTRAL_P_BUDGET="${DEVSTRAL_P_BUDGET:-4000}"
DEVSTRAL_B_BUDGET="${DEVSTRAL_B_BUDGET:-7000}"
GLM_A_BUDGET="${GLM_A_BUDGET:-2000}"
GLM_P_BUDGET="${GLM_P_BUDGET:-3000}"
GLM_B_BUDGET="${GLM_B_BUDGET:-5000}"

SINGLES=(truncation summarization summarization-partial structured-summarize structured-summarize-partial)
INVARIANT=(tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial)
BASELINES=(full-context online-trc)
mkdir -p "$WS/logs"

usage() { echo "Usage: $0 {qwen|devstral|glm|all} [main|ablation|both]" >&2; }
require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }

primitive_name() {
    case "$1" in
        truncation) echo tr ;; summarization) echo su-full ;;
        summarization-partial) echo su-partial ;; structured-summarize) echo ss ;;
        structured-summarize-partial) echo ss-partial ;; tool-result-clear) echo trc ;;
        trc-su|trc-ss|otrc-tr|otrc-su-partial|otrc-ss-partial) echo "$1" ;;
        full-context) echo fc ;; online-trc) echo otrc ;;
        *) echo "[ERROR] Unknown condition: $1" >&2; return 1 ;;
    esac
}

budget_tag() {
    [[ "$1" =~ ^[1-9][0-9]*000$ ]] || {
        echo "[ERROR] Budget must be a positive whole number of K tokens: $1" >&2; return 1;
    }
    echo "b$(($1 / 1000))k"
}

validate_budgets() {
    local label="$1" a="$2" p="$3" b="$4"
    budget_tag "$a" >/dev/null; budget_tag "$p" >/dev/null; budget_tag "$b" >/dev/null
    (( a < p && p < b )) || { echo "[ERROR] $label budgets must satisfy A < P < B." >&2; return 1; }
}

run_model() {
    local model="$1" model_key model_label config health_url a_budget p_budget b_budget
    case "$model" in
        qwen)
            model_key=qwen35b; model_label=Qwen3.5-35B-A3B
            config="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
            health_url="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
            a_budget="$QWEN_A_BUDGET"; p_budget="$QWEN_P_BUDGET"; b_budget="$QWEN_B_BUDGET" ;;
        devstral)
            model_key=devstral24b; model_label=Devstral-Small-2-24B
            config="${DEVSTRAL_AGENT_CONFIG:-$WS/configs/config-devstral-vllm.yaml}"
            health_url="${DEVSTRAL_HEALTH_URL:-http://localhost:8002/v1/models}"
            a_budget="$DEVSTRAL_A_BUDGET"; p_budget="$DEVSTRAL_P_BUDGET"; b_budget="$DEVSTRAL_B_BUDGET" ;;
        glm)
            model_key=glm47flash; model_label=GLM-4.7-Flash
            config="${GLM_AGENT_CONFIG:-$WS/configs/config-glm47flash-vllm.yaml}"
            health_url="${GLM_HEALTH_URL:-http://localhost:8003/v1/models}"
            a_budget="$GLM_A_BUDGET"; p_budget="$GLM_P_BUDGET"; b_budget="$GLM_B_BUDGET" ;;
    esac

    local otrc_config="${OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
    local log_file="$WS/logs/followup_tb_${model}.log"
    require_file "$config"; require_file "$otrc_config"
    validate_budgets "$model_label" "$a_budget" "$p_budget" "$b_budget"
    curl -fsS --max-time 5 "$health_url" >/dev/null || {
        echo "[ERROR] $model_label server is not responding at $health_url" >&2; return 1;
    }

    log() { echo "[$(date)] $*" | tee -a "$log_file"; }
    run_cell() {
        local cell_section="$1" tasks_file="$2" depth_tag="$3" budget="$4" depth="$5"
        shift 5
        local condition primitive cell tag
        if (( budget == INF_BUDGET )); then tag=binf; else tag="$(budget_tag "$budget")"; fi
        for condition in "$@"; do
            primitive="$(primitive_name "$condition")"
            cell="${depth_tag}__${tag}__${primitive}"
            log "--- $cell_section/$model_key/$cell | budget=$budget depth=$depth tasks=$(basename "$tasks_file") ---"
            "$PY" "$RUNNER" \
                --iclr-benchmark terminal-bench --iclr-section "$cell_section" \
                --iclr-model "$model_key" --iclr-cell "$cell" \
                --benchmark terminal-bench --model-tag "$model_key" \
                --agent-config "$config" --otrc-config "$otrc_config" \
                --budget "$budget" --depth "$depth" --tasks-file "$tasks_file" \
                --conditions "$condition" --runs-per-task "$RUNS_PER_TASK" \
                --max-workers "$N_CONCURRENT" 2>&1 | tee -a "$log_file"
        done
    }

    if [[ "$section" == main || "$section" == both ]]; then
        log "=== $model_label: TB (3.a) main, P-40 ==="
        run_cell main "$P40" d05 "$p_budget" 0.5 "${SINGLES[@]}"
        run_cell main "$P40" di "$p_budget" 0.5 "${INVARIANT[@]}"
        run_cell main "$P40" di "$INF_BUDGET" 0.5 "${BASELINES[@]}"
        log "=== TB (3.a) complete for $model_label: 1,560 planned runs ==="
    fi

    if [[ "$section" == ablation || "$section" == both ]]; then
        log "=== $model_label: TB (3.b) ablation, P-15 ==="
        local depth depth_tag budget
        for budget in "$a_budget" "$b_budget"; do
            run_cell ablation "$ABL15" d05 "$budget" 0.5 "${SINGLES[@]}"
        done
        for depth in 0.3 0.7; do
            depth_tag="d${depth/./}"
            for budget in "$a_budget" "$p_budget" "$b_budget"; do
                run_cell ablation "$ABL15" "$depth_tag" "$budget" "$depth" "${SINGLES[@]}"
            done
        done
        for budget in "$a_budget" "$b_budget"; do
            run_cell ablation "$ABL15" di "$budget" 0.5 "${INVARIANT[@]}"
        done
        log "=== TB (3.b) complete for $model_label: 2,340 planned runs ==="
    fi
}

selection="${1:-qwen}"
section="${2:-both}"
case "$selection" in qwen|devstral|glm|all) ;; *) usage; exit 2 ;; esac
case "$section" in main|ablation|both) ;; *) usage; exit 2 ;; esac
require_file "$PY"; require_file "$RUNNER"; require_file "$P40"; require_file "$ABL15"

if [[ "$selection" == all ]]; then
    run_model qwen; run_model devstral; run_model glm
else
    run_model "$selection"
fi
