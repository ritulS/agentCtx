#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md (3.b): GLM-4.7-Flash TB ablation (P-15), split across two
# vLLM servers so both halves run concurrently. Start vLLM/Podman separately:
#   GPUs 0-3 -> port 8003 (configs/config-glm47flash-vllm.yaml)
#   GPUs 4-7 -> port 8004 (configs/config-glm47flash-vllm-8004.yaml)
#
# Usage: SLACK_WEBHOOK_URL=... nohup bash scripts/run_glm_tb_ablation_with_slack.sh {gpu0-3|gpu4-7} &
#   gpu0-3 : depth-tunable singles @ depth 0.3 + depth 0.7 (A/P/B each)      = 1,350 runs
#   gpu4-7 : depth-invariant @ 0.5 (A/B) + depth-tunable singles @ 0.5 (A/B) =   990 runs
# Override the split with ABLATION_PARTS (subset of "d05 d03 d07 di"); all other
# settings match run_agent_models_expansion_tb.sh exactly. Completed runs are skipped.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

group="${1:-}"
case "$group" in
    gpu0-3)
        export ABLATION_PARTS="${ABLATION_PARTS:-d03 d07}"
        export GLM_AGENT_CONFIG="${GLM_AGENT_CONFIG:-$WS/configs/config-glm47flash-vllm.yaml}"
        export GLM_HEALTH_URL="${GLM_HEALTH_URL:-http://localhost:8003/v1/models}" ;;
    gpu4-7)
        export ABLATION_PARTS="${ABLATION_PARTS:-di d05}"
        export GLM_AGENT_CONFIG="${GLM_AGENT_CONFIG:-$WS/configs/config-glm47flash-vllm-8004.yaml}"
        export GLM_HEALTH_URL="${GLM_HEALTH_URL:-http://localhost:8004/v1/models}" ;;
    *) echo "Usage: $0 {gpu0-3|gpu4-7}" >&2; exit 2 ;;
esac
export TB_LOG_SUFFIX="ablation_${group}"

exec 9>"logs/glm_tb_ablation_${group}.lock"
flock -n 9 || { echo "GLM TB ablation launcher for $group already running." >&2; exit 1; }
: "${SLACK_WEBHOOK_URL:?Export SLACK_WEBHOOK_URL before launching}"
PY="$WS/venv-harbor/bin/python"
LOG_FILE="${GLM_TB_LOG_FILE:-$WS/logs/followup_tb_glm_ablation_${group}.nohup.log}"
UNIT="glm-terminal-bench-ablation-${group}"
notify() {
    "$PY" dashboard/notify_slack.py "$@" || echo 'Slack notification failed.' >&2
}
on_exit() {
    local status=$? result=failed
    trap - EXIT
    (( status == 0 )) && result=success
    notify stop "$UNIT" "$result" "$status" "$LOG_FILE"
    exit "$status"
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
notify start "$UNIT"

export GLM_A_BUDGET="${GLM_A_BUDGET:-2000}"
export GLM_P_BUDGET="${GLM_P_BUDGET:-3000}"
export GLM_B_BUDGET="${GLM_B_BUDGET:-5000}"
export N_CONCURRENT="${N_CONCURRENT:-4}"
bash scripts/run_agent_models_expansion_tb.sh glm ablation
