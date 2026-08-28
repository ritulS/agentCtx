#!/usr/bin/env bash
# Run the canonical SWE-Bench P100 FC@infinity run_1 calibration.
#
# Usage:
#   bash scripts/run_budget_calibration_sb.sh devstral
#   bash scripts/run_budget_calibration_sb.sh glm
#   bash scripts/run_budget_calibration_sb.sh all  # sequential
#
# Prerequisite: start the selected model's vLLM server before this script.
# The Python launcher is resumable and skips run_1 records already on disk.
set -euo pipefail

WORKSPACE="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$WORKSPACE/venv/bin/python}"
TASKS_FILE="${TASKS_FILE:-$WORKSPACE/task_lists/p100_all_100_tasks.json}"
MAX_WORKERS="${MAX_WORKERS:-16}"
LAUNCHER="$WORKSPACE/scripts/run_budget_calibration_sb.py"
LOG_DIR="$WORKSPACE/logs"

mkdir -p "$LOG_DIR"
cd "$WORKSPACE"

run_one() {
    local model="$1"
    local model_key model_label agent_config health_url log_file

    case "$model" in
        devstral)
            model_key="devstral24b"
            model_label="Devstral-Small-2-24B"
            agent_config="${DEVSTRAL_AGENT_CONFIG:-$WORKSPACE/configs/config-devstral-vllm.yaml}"
            health_url="${DEVSTRAL_HEALTH_URL:-http://localhost:8002/v1/models}"
            ;;
        glm)
            model_key="glm47flash"
            model_label="GLM-4.7-Flash"
            agent_config="${GLM_AGENT_CONFIG:-$WORKSPACE/configs/config-glm47flash-vllm.yaml}"
            health_url="${GLM_HEALTH_URL:-http://localhost:8003/v1/models}"
            ;;
        *)
            echo "Usage: $0 {devstral|glm|all}" >&2
            return 2
            ;;
    esac

    for required_file in "$PYTHON_BIN" "$TASKS_FILE" "$LAUNCHER" "$agent_config"; do
        if [[ ! -f "$required_file" ]]; then
            echo "[ERROR] Required file not found: $required_file" >&2
            return 1
        fi
    done

    if ! curl -fsS --max-time 5 "$health_url" >/dev/null; then
        echo "[ERROR] $model_label server is not responding at $health_url" >&2
        return 1
    fi

    log_file="$LOG_DIR/${model_key}_sb_fc_run1.log"
    echo "[$(date)] === $model_label: SWE-Bench P100, FC@infinity, run_1 ===" | tee -a "$log_file"

    "$PYTHON_BIN" "$LAUNCHER" \
        --model-key "$model_key" \
        --model-label "$model_label" \
        --agent-config "$agent_config" \
        --tasks-file "$TASKS_FILE" \
        --max-workers "$MAX_WORKERS" \
        2>&1 | tee -a "$log_file"

    echo "[$(date)] === $model_label DONE ===" | tee -a "$log_file"
}

selection="${1:-}"
case "$selection" in
    devstral|glm)
        run_one "$selection"
        ;;
    all)
        run_one devstral
        run_one glm
        ;;
    *)
        echo "Usage: $0 {devstral|glm|all}" >&2
        exit 2
        ;;
esac
