#!/bin/bash
# Devstral-Small-2-24B-Instruct-2512  §a (OTRC half): online-trc at ∞ budget.
# FC half is already on disk in results/ablations/devstral-2-inf/ (60 records).
# This adds the OTRC condition to complete the ∞-baseline pair.
# 1 prim (online-trc) × 30 tasks × 2 runs = 60 runs total.
# Output dir: results/ablations/devstral-2-inf/ (appended).
#
# Usage:  nohup bash scripts/run_devstral_otrc_inf.sh > logs/devstral_2_inf_otrc.out 2>&1 &
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/devstral_2_inf_otrc.log"
mkdir -p "$WS/logs"

echo "[$(date)] === Devstral §a (OTRC half): online-trc inf baseline ===" | tee -a "$LOG"

if ! curl -sf http://localhost:8002/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM Devstral not responding on port 8002. Run scripts/start_vllm_devstral.sh first." | tee -a "$LOG"
    exit 1
fi

venv/bin/python3 scripts/run_experiment.py \
    --ablation     devstral-2-inf \
    --model-tag    devstral-2 \
    --agent-config config-devstral-vllm.yaml \
    --otrc-config  config-online-trc-devstral.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   online-trc \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     devstral-2-inf \
    --model-tag    devstral-2 \
    --agent-config config-devstral-vllm.yaml \
    --otrc-config  config-online-trc-devstral.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   online-trc \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Devstral §a (OTRC half) DONE — ∞ baselines complete ===" | tee -a "$LOG"
