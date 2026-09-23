#!/usr/bin/env bash
# FOLLOWUP_EXPERIMENTS.md (3.b): GLM-4.7-Flash TB ablation (P-15), split across two
# vLLM servers so both halves run concurrently. Start vLLM/Podman separately:
#   GPUs 0-3 -> port 8003 (configs/config-glm47flash-vllm.yaml)
#   GPUs 4-7 -> port 8004 (configs/config-glm47flash-vllm-8004.yaml)
#
# Usage: SLACK_WEBHOOK_URL=... bash scripts/expansions/run_glm_tb_ablation_split.sh {gpu0-3|gpu4-7}
#   (detaches into the background; FOREGROUND=1 keeps it attached)
#   gpu0-3 : depth-tunable singles @ depth 0.3 + depth 0.7 (A/P/B each)      = 1,350 runs
#   gpu4-7 : depth-invariant @ 0.5 (A/B) + depth-tunable singles @ 0.5 (A/B) =   990 runs
# Override the split with ABLATION_PARTS (subset of "d05 d03 d07 di"); all other
# settings match run_agent_models_expansion_tb.sh exactly. Completed runs are skipped.
# Slack notices, the per-group lock, the timestamped log under logs/experiments/ and
# the backgrounding come from scripts/notify_run.sh.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"

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
export N_CONCURRENT="${N_CONCURRENT:-4}"

exec bash scripts/notify_run.sh ${FOREGROUND:+--foreground} \
    --unit "glm-terminal-bench-ablation-${group}" \
    --lock "glm_tb_ablation_${group}" ${GLM_TB_LOG_FILE:+--log "$GLM_TB_LOG_FILE"} \
    -- bash scripts/expansions/run_agent_models_expansion_tb.sh glm ablation
