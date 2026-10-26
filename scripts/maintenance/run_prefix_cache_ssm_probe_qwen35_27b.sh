#!/usr/bin/env bash
# Qwen3.5-27B (dense, bf16) version of the prefix-cache / SSM-dtype probe of
# 2026-10-24: download the weights, then run run_prefix_cache_ssm_probe.sh with
# a float32 SSM cache (off, off2, on_cold, on, on_cold2) and again with the
# default bf16 ("auto") SSM cache. GPUs 2-3, TP=2, port 8012. Same 40 prompts.
#   SLACK_WEBHOOK_URL=... bash scripts/notify_run.sh --unit r2/probes/prefix_cache_effect_qwen35_27b \
#       -- bash scripts/maintenance/run_prefix_cache_ssm_probe_qwen35_27b.sh
set -euo pipefail
WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
export QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-27B}"
echo "[$(date)] downloading $QWEN_MODEL"
venv/bin/hf download "$QWEN_MODEL" --exclude '*.pt' --exclude '*.bin' 2>&1 | tail -n 3
echo "[$(date)] download done: $(du -sh ~/.cache/huggingface/hub/models--${QWEN_MODEL//\//--} | cut -f1)"
for dtype in float32 auto; do
    echo "[$(date)] ===== SSM_DTYPE=$dtype ====="
    SSM_DTYPE="$dtype" bash scripts/maintenance/run_prefix_cache_ssm_probe.sh
done
echo "[$(date)] all done"
