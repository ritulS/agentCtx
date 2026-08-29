#!/usr/bin/env bash
# Add Terminal-Bench FC@infinity run_2..run_5 on the 42-task rootless subset.
#
# The budget-calibration launch already supplies run_1. This launcher preserves
# it and fills the remaining four repetitions in the same canonical cell:
#   ICLR_results/terminalbench/main/p80_rootless/<model>/di__binf__fc/
#
# Usage:
#   bash scripts/run_terminalbench_rootless_fc_expansion.sh qwen
#   bash scripts/run_terminalbench_rootless_fc_expansion.sh devstral
#   bash scripts/run_terminalbench_rootless_fc_expansion.sh glm
#   bash scripts/run_terminalbench_rootless_fc_expansion.sh all
#
# Optional overrides:
#   START_RUN=2 END_RUN=5 N_CONCURRENT=4 RUN_POSTPROCESS=1 bash ...
set -euo pipefail

WORKSPACE="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${TB_PYTHON_BIN:-$WORKSPACE/venv-harbor/bin/python}"
HARBOR_BIN="${HARBOR_BIN:-$WORKSPACE/venv-harbor/bin/harbor}"
LAUNCHER="$WORKSPACE/scripts/run_budget_calibration_tb.py"
TASKS_FILE="${P80_ROOTLESS_TASKS_FILE:-$WORKSPACE/task_lists/tbench_p80_rootless.json}"
N_CONCURRENT="${N_CONCURRENT:-4}"
START_RUN="${START_RUN:-2}"
END_RUN="${END_RUN:-5}"
RUN_POSTPROCESS="${RUN_POSTPROCESS:-1}"
DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"
LOG_DIR="$WORKSPACE/logs"

export DOCKER_HOST
mkdir -p "$LOG_DIR"
cd "$WORKSPACE"

if [[ ! "$START_RUN" =~ ^[2-5]$ || ! "$END_RUN" =~ ^[2-5]$ ]] || (( START_RUN > END_RUN )); then
    echo "[ERROR] Expected 2 <= START_RUN <= END_RUN <= 5." >&2
    exit 2
fi

for required_file in "$PYTHON_BIN" "$HARBOR_BIN" "$LAUNCHER" "$TASKS_FILE"; do
    if [[ ! -f "$required_file" ]]; then
        echo "[ERROR] Required file not found: $required_file" >&2
        exit 1
    fi
done
if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Rootless Podman is not reachable through $DOCKER_HOST" >&2
    exit 1
fi

run_model() {
    local model="$1" model_key model_label agent_config health_url
    case "$model" in
        qwen)
            model_key="qwen35b"
            model_label="Qwen3.5-35B-A3B"
            agent_config="${QWEN_AGENT_CONFIG:-$WORKSPACE/configs/config-qwen-vllm.yaml}"
            health_url="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
            ;;
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
        *) echo "Usage: $0 {qwen|devstral|glm|all}" >&2; return 2 ;;
    esac

    if [[ ! -f "$agent_config" ]]; then
        echo "[ERROR] Agent config not found: $agent_config" >&2
        return 1
    fi
    if ! curl -fsS --max-time 5 "$health_url" >/dev/null; then
        echo "[ERROR] $model_label server is not responding at $health_url" >&2
        return 1
    fi

    local run_num log_file skip_postprocess=()
    log_file="$LOG_DIR/${model_key}_tb1_p80_rootless_fc_runs${START_RUN}-${END_RUN}.log"
    for ((run_num=START_RUN; run_num<=END_RUN; run_num++)); do
        skip_postprocess=(--skip-postprocess)
        if [[ "$RUN_POSTPROCESS" == 1 && "$run_num" == "$END_RUN" ]]; then
            skip_postprocess=()
        fi
        echo "[$(date)] === $model_label: TB P-80-rootless FC@infinity run_$run_num ===" \
            | tee -a "$log_file"
        "$PYTHON_BIN" "$LAUNCHER" \
            --model-key "$model_key" \
            --model-label "$model_label" \
            --run-num "$run_num" \
            --agent-config "$agent_config" \
            --harbor-bin "$HARBOR_BIN" \
            --n-concurrent "$N_CONCURRENT" \
            --docker-host "$DOCKER_HOST" \
            --tasks-file "$TASKS_FILE" \
            --result-scope p80_rootless \
            --job-name "tb1-${model_key}-p80-rootless-fc-run${run_num}" \
            "${skip_postprocess[@]}" \
            2>&1 | tee -a "$log_file"
    done
}

selection="${1:-}"
case "$selection" in
    qwen|devstral|glm) run_model "$selection" ;;
    all)
        run_model qwen
        run_model devstral
        run_model glm
        ;;
    *) echo "Usage: $0 {qwen|devstral|glm|all}" >&2; exit 2 ;;
esac
