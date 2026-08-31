#!/usr/bin/env bash
# Run the canonical Terminal-Bench 1.0 FC@infinity run_1 calibration.
#
# Usage:
#   bash scripts/run_budget_calibration_tb.sh qwen
#   bash scripts/run_budget_calibration_tb.sh qwen-rootless
#   bash scripts/run_budget_calibration_tb.sh qwen-subuid
#   bash scripts/run_budget_calibration_tb.sh devstral
#   bash scripts/run_budget_calibration_tb.sh devstral-rootless
#   bash scripts/run_budget_calibration_tb.sh devstral-subuid
#   bash scripts/run_budget_calibration_tb.sh glm
#   bash scripts/run_budget_calibration_tb.sh glm-rootless
#   bash scripts/run_budget_calibration_tb.sh glm-subuid
#   bash scripts/run_budget_calibration_tb.sh all  # sequential
#   bash scripts/run_budget_calibration_tb.sh all-rootless  # sequential
#   bash scripts/run_budget_calibration_tb.sh all-subuid  # sequential
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
P80_ROOTLESS_TASKS_FILE="${P80_ROOTLESS_TASKS_FILE:-$WORKSPACE/task_lists/tbench_p80_rootless.json}"
P80_SUBUID_TASKS_FILE="${P80_SUBUID_TASKS_FILE:-$WORKSPACE/task_lists/tbench_p80_subuid_required.json}"

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
    local phase="${2:-all}"
    local model_key model_label agent_config health_url log_file job_name task_scope
    local -a subset_args=()

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
            echo "[ERROR] Unknown model: $model" >&2
            return 2
            ;;
    esac

    case "$phase" in
        all)
            task_scope="P-80"
            job_name="tb1-${model_key}-fc-run1"
            ;;
        rootless)
            if [[ ! -f "$P80_ROOTLESS_TASKS_FILE" ]]; then
                echo "[ERROR] P-80-rootless task list not found: $P80_ROOTLESS_TASKS_FILE" >&2
                return 1
            fi
            task_scope="P-80-rootless"
            job_name="tb1-${model_key}-p80-rootless-fc-run1"
            subset_args+=(
                --tasks-file "$P80_ROOTLESS_TASKS_FILE"
                --result-scope p80_rootless
            )
            ;;
        subuid)
            if [[ ! -f "$P80_SUBUID_TASKS_FILE" ]]; then
                echo "[ERROR] P-80-subuid-required task list not found: $P80_SUBUID_TASKS_FILE" >&2
                return 1
            fi
            task_scope="P-80-subuid-required"
            job_name="tb1-${model_key}-p80-subuid-required-fc-run1"
            subset_args+=(
                --tasks-file "$P80_SUBUID_TASKS_FILE"
                --result-scope p80_subuid_required
            )
            ;;
        *)
            echo "[ERROR] Unknown task scope: $phase" >&2
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
    echo "[$(date)] === $model_label: Terminal-Bench 1.0, $task_scope, FC@infinity, run_1 ===" \
        | tee -a "$log_file"

    "$PYTHON_BIN" "$LAUNCHER" \
        --model-key "$model_key" \
        --model-label "$model_label" \
        --agent-config "$agent_config" \
        --harbor-bin "$HARBOR_BIN" \
        --n-concurrent "$N_CONCURRENT" \
        --docker-host "$DOCKER_HOST" \
        --job-name "$job_name" \
        "${subset_args[@]}" \
        2>&1 | tee -a "$log_file"

    echo "[$(date)] === $model_label DONE ===" | tee -a "$log_file"
}

check_common_prerequisites

selection="${1:-}"
case "$selection" in
    qwen|devstral|glm)
        run_one "$selection"
        ;;
    qwen-rootless|devstral-rootless|glm-rootless)
        run_one "${selection%-rootless}" rootless
        ;;
    qwen-subuid|devstral-subuid|glm-subuid)
        run_one "${selection%-subuid}" subuid
        ;;
    all)
        run_one qwen
        run_one devstral
        run_one glm
        ;;
    all-rootless)
        run_one qwen rootless
        run_one devstral rootless
        run_one glm rootless
        ;;
    all-subuid)
        run_one qwen subuid
        run_one devstral subuid
        run_one glm subuid
        ;;
    *)
        echo "Usage: $0 {qwen|qwen-rootless|qwen-subuid|devstral|devstral-rootless|devstral-subuid|glm|glm-rootless|glm-subuid|all|all-rootless|all-subuid}" >&2
        exit 2
        ;;
esac
