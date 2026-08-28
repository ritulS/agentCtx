#!/usr/bin/env bash
# Collect 60 full-context trajectories and calibrate A/P/B token budgets.
#
# Usage:
#   bash scripts/run_model_budget_calibration.sh devstral
#   bash scripts/run_model_budget_calibration.sh glm
#
# The run is resumable: run_experiment.py skips completed keys. Calibration
# uses each trajectory's peak step_prompt_tokens and matches Qwen3.5's
# reference trigger rates (97% / 88% / 76%). SWE-bench patch evaluation is not
# needed because only context-growth measurements are used.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"

MODEL="${1:-}"
PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/scripts/run_experiment.py"
CALIBRATOR="$WS/Review1/calibrate_budgets.py"
TASKS="$WS/task_lists/ablation_30tasks.json"
MAX_WORKERS="${MAX_WORKERS:-32}"
INF_BUDGET=999999999

case "$MODEL" in
    devstral)
        MODEL_TAG="${MODEL_TAG:-devstral-2}"
        AGENT_CONFIG="${AGENT_CONFIG:-$WS/configs/config-devstral-vllm.yaml}"
        HEALTH_URL="${HEALTH_URL:-http://localhost:8002/v1/models}"
        ;;
    glm)
        MODEL_TAG="${MODEL_TAG:-glm47-flash}"
        AGENT_CONFIG="${AGENT_CONFIG:-$WS/configs/config-glm47-flash-vllm.yaml}"
        HEALTH_URL="${HEALTH_URL:-http://localhost:8003/v1/models}"
        ;;
    *)
        echo "Usage: $0 {devstral|glm}" >&2
        exit 2
        ;;
esac

ABLATION_NAME="${MODEL_TAG}-inf"
LOG="$WS/logs/${MODEL_TAG}_budget_calibration.log"
mkdir -p "$WS/logs"

for required in "$PY" "$RUNNER" "$CALIBRATOR" "$TASKS" "$AGENT_CONFIG"; do
    if [[ ! -f "$required" ]]; then
        echo "[ERROR] Required file not found: $required" >&2
        exit 1
    fi
done

if ! curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[ERROR] Model server is not responding at $HEALTH_URL" >&2
    exit 1
fi

echo "[$(date)] === $MODEL_TAG FC budget calibration: 30 tasks x 2 runs ===" | tee -a "$LOG"
"$PY" "$RUNNER" \
    --ablation "$ABLATION_NAME" \
    --model-tag "$MODEL_TAG" \
    --agent-config "$AGENT_CONFIG" \
    --budget "$INF_BUDGET" \
    --tasks-file "$TASKS" \
    --conditions full-context \
    --runs-per-task 2 \
    --max-workers "$MAX_WORKERS" \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Computing A/P/B budgets from FC peaks ===" | tee -a "$LOG"
"$PY" "$CALIBRATOR" --model-tag "$MODEL_TAG" 2>&1 | tee -a "$LOG"

BUDGETS_FILE="$WS/logs/${MODEL_TAG}_calibrated_budgets.sh"
echo "[$(date)] Review before launch: $BUDGETS_FILE" | tee -a "$LOG"
echo "[$(date)] Do not launch the budgeted grid unless ALL_WITHIN_TOLERANCE=true." | tee -a "$LOG"
