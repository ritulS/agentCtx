#!/usr/bin/env bash
# Run the canonical Terminal-Bench 1.0 FC@infinity run_1 calibration.
#
# Usage:
#   bash scripts/run_budget_calibration_tb.sh qwen
#   bash scripts/run_budget_calibration_tb.sh devstral
#   bash scripts/run_budget_calibration_tb.sh glm
#   bash scripts/run_budget_calibration_tb.sh all  # sequential
#
# Prerequisites:
#   1. Start the selected model's vLLM server.
#   2. Start a rootless Podman API service and export DOCKER_HOST, or use the
#      default unix:///run/user/$UID/podman/podman.sock.
#
# The Python launcher uses a stable Harbor job name, so rerunning this command
# resumes the same run_1 job instead of intentionally creating run_2.
set -euo pipefail

WORKSPACE="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${TB_PYTHON_BIN:-$WORKSPACE/venv-harbor/bin/python}"
HARBOR_BIN="${HARBOR_BIN:-$WORKSPACE/venv-harbor/bin/harbor}"
N_CONCURRENT="${N_CONCURRENT:-4}"
DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"
LAUNCHER="$WORKSPACE/scripts/run_budget_calibration_tb.py"
LOG_DIR="$WORKSPACE/logs"

export DOCKER_HOST
mkdir -p "$LOG_DIR"
cd "$WORKSPACE"

check_common_prerequisites() {
    for required_file in "$PYTHON_BIN" "$HARBOR_BIN" "$LAUNCHER"; do
        if [[ ! -f "$required_file" ]]; then
            echo "[ERROR] Required file not found: $required_file" >&2
            return 1
        fi
    done

    if ! docker info >/dev/null 2>&1; then
        echo "[ERROR] Rootless Podman is not reachable through $DOCKER_HOST" >&2
        echo "Start 'podman system service' first; see the instructions below." >&2
        return 1
    fi
}

run_one() {
    local model="$1"
    local model_key model_label agent_config health_url log_file

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
        *)
            echo "Usage: $0 {qwen|devstral|glm|all}" >&2
            return 2
            ;;
    esac

    if [[ ! -f "$agent_config" ]]; then
        echo "[ERROR] Agent config not found: $agent_config" >&2
        echo "Override it with the corresponding *_AGENT_CONFIG environment variable." >&2
        return 1
    fi
    if ! curl -fsS --max-time 5 "$health_url" >/dev/null; then
        echo "[ERROR] $model_label server is not responding at $health_url" >&2
        return 1
    fi

    log_file="$LOG_DIR/${model_key}_tb1_fc_run1.log"
    echo "[$(date)] === $model_label: Terminal-Bench 1.0, 80 tasks, FC@infinity, run_1 ===" \
        | tee -a "$log_file"

    "$PYTHON_BIN" "$LAUNCHER" \
        --model-key "$model_key" \
        --model-label "$model_label" \
        --agent-config "$agent_config" \
        --harbor-bin "$HARBOR_BIN" \
        --n-concurrent "$N_CONCURRENT" \
        --docker-host "$DOCKER_HOST" \
        2>&1 | tee -a "$log_file"

    echo "[$(date)] === $model_label DONE ===" | tee -a "$log_file"
}

check_common_prerequisites

selection="${1:-}"
case "$selection" in
    qwen|devstral|glm)
        run_one "$selection"
        ;;
    all)
        run_one qwen
        run_one devstral
        run_one glm
        ;;
    *)
        echo "Usage: $0 {qwen|devstral|glm|all}" >&2
        exit 2
        ;;
esac
