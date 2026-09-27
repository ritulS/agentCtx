#!/usr/bin/env bash
# Terminal-Bench prefix-cache ablation (dashboard 5.b) split across two
# caching-off Qwen3.5-35B-A3B servers so both halves run at once. Start vLLM
# and the Podman socket separately:
#   GPUs 0-3 -> port 8000 (configs/config-qwen-vllm.yaml)
#               bash scripts/serving/start_vllm_qwen35_no_prefix_cache.sh
#   GPUs 4-7 -> port 8002 (configs/config-qwen-vllm-8002.yaml)
#               bash scripts/serving/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh
#
# Usage: SLACK_WEBHOOK_URL=... bash scripts/expansions/run_qwen_tb_prefix_cache_ablation_split.sh {gpu0-3|gpu4-7}
#   (detaches into the background; FOREGROUND=1 keeps it attached)
#   gpu0-3 : depth-tunable @ 0.5 (5 cells) + FC / OTRC @ inf (2 cells) = 7 x 15 x 3 = 315 runs
#   gpu4-7 : depth-invariant (6 cells)                                = 6 x 15 x 3 = 270 runs
# A group only sets defaults for CELLS, QWEN_AGENT_CONFIG and QWEN_HEALTH_URL;
# every other override of scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh
# (ICLR_MODEL, TB_TASKS_FILE, N_TASKS, RUNS_PER_TASK, N_CONCURRENT, ...) passes
# through unchanged. Both halves write into the same model dir; completed
# task/condition/run keys are skipped on rerun. Slack notices, the per-group
# lock, the timestamped log under logs/experiments/ and the backgrounding come
# from scripts/notify_run.sh. Until 2026-09-26 this was
# scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh {gpu0-3|gpu4-7}.
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"

group="${1:-}"
case "$group" in
    gpu0-3)
        export CELLS="${CELLS:-d05__b3k__tr:truncation:0.5 \
d05__b3k__su-full:summarization:0.5 \
d05__b3k__su-partial:summarization-partial:0.5 \
d05__b3k__ss:structured-summarize:0.5 \
d05__b3k__ss-partial:structured-summarize-partial:0.5 \
di__binf__fc:full-context:0.5 \
di__binf__otrc:online-trc:0.5}"
        export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
        export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}" ;;
    gpu4-7)
        export CELLS="${CELLS:-di__b3k__trc:tool-result-clear:0.5 \
di__b3k__trc-su:trc-su:0.5 \
di__b3k__trc-ss:trc-ss:0.5 \
di__b3k__otrc-tr:otrc-tr:0.5 \
di__b3k__otrc-su-partial:otrc-su-partial:0.5 \
di__b3k__otrc-ss-partial:otrc-ss-partial:0.5}"
        export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm-8002.yaml}"
        export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8002/v1/models}" ;;
    *) echo "Usage: $0 {gpu0-3|gpu4-7}" >&2; exit 2 ;;
esac
export LAUNCH_GROUP="$group"
ICLR_MODEL="${ICLR_MODEL:-qwen35b-noprefixcache}"   # same default as the launcher

exec bash scripts/notify_run.sh ${FOREGROUND:+--foreground} \
    --unit "qwen-terminal-bench-prefix-cache-ablation/${ICLR_MODEL}/${group}" \
    --lock "qwen_tb_${ICLR_MODEL}_${group}" ${TB_PREFIXCACHE_LOG_FILE:+--log "$TB_PREFIXCACHE_LOG_FILE"} \
    -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh
