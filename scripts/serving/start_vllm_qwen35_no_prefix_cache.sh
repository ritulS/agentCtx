#!/usr/bin/env bash
# Start vLLM serving for Qwen3.5-35B-A3B with the production Terminal-Bench
# serving configuration, minus prefix caching (dashboard 5.b).
#
# The production Qwen Terminal-Bench runs were served by
# scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh, which passes --enable-prefix-caching
# (logs/servers/vllm_qwen35_<ts>.log: enable_prefix_caching=True). This is that same script
# with --no-enable-prefix-caching as the only changed argument — the mirror
# image of scripts/serving/start_vllm_qwen35_prefix_cache.sh, which turns caching ON
# for SWE-Bench, whose production runs had it off.
#
# Every other serving argument is pinned to the production default on purpose:
# the QWEN_* overrides of start_vllm_qwen35_prefix_cache_ablation.sh are refused here, so the two
# serving conditions cannot drift apart through a stray environment variable.
#
# Usage:  bash scripts/serving/start_vllm_qwen35_no_prefix_cache.sh
# Tail:   tail -f logs/servers/vllm_qwen35_noprefixcache.latest.log
# Check:  grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/servers/vllm_qwen35_noprefixcache.latest.log | tail -1
# Stop:   bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35.pid
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

for var in QWEN_VLLM_PORT QWEN_MODEL QWEN_CUDA_VISIBLE_DEVICES \
           QWEN_TENSOR_PARALLEL_SIZE QWEN_MAX_MODEL_LEN QWEN_MAX_NUM_SEQS; do
    if [[ -n "${!var:-}" ]]; then
        echo "[ERROR] $var is set; the prefix-cache ablation server must use the" \
             "production defaults of scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh. Unset it." >&2
        exit 1
    fi
done

QWEN_PREFIX_CACHING=0 exec bash "$WS/scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh"
