#!/bin/bash
# Qwen2.5-Coder-32B-Instruct model-expansion phase on Dobby.
# Reduced scope (decided 2026-05-22): §a + §c @ 15k only = 780 runs total.
#
# §a inf baselines (FC + OTRC) at depth=0.5 = 120 runs
# §c canonical @ 15k (11 prims) at depth=0.5 = 660 runs
#
# Output dirs:
#   results/ablations/qwen25-coder-32b-inf/         (120 records)
#   results/ablations/qwen25-coder-32b-budgeted-15000/  (660 records)
#
# Prereq: vLLM Qwen2.5-Coder-32B serving on port 8003 (scripts/start_vllm_qwen25_coder_32b.sh)
#
# Usage:  nohup bash scripts/run_qwen25_coder_32b_phase.sh > logs/qwen25_coder_32b_phase.out 2>&1 &
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_coder_32b_phase.log"
mkdir -p "$WS/logs"

echo "[$(date)] === Qwen2.5-Coder-32B phase: §a + §c @ 15k ===" | tee -a "$LOG"

if ! curl -sf http://localhost:8003/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM Qwen2.5-Coder not responding on port 8003." | tee -a "$LOG"
    exit 1
fi

# === §a inf baselines: FC + OTRC ===
echo "[$(date)] --- §a: FC + OTRC @ ∞ (120 runs) ---" | tee -a "$LOG"

CONDS_INF="full-context online-trc"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-coder-32b-inf \
    --model-tag    qwen25-coder-32b \
    --agent-config config-qwen25-coder-32b-vllm.yaml \
    --otrc-config  config-online-trc-qwen25-coder-32b.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-coder-32b-inf \
    --model-tag    qwen25-coder-32b \
    --agent-config config-qwen25-coder-32b-vllm.yaml \
    --otrc-config  config-online-trc-qwen25-coder-32b.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] §a DONE" | tee -a "$LOG"

# === §c canonical budgeted @ 15k ===
echo "[$(date)] --- §c canonical @ 15k (11 prims × 30 × 2 = 660 runs) ---" | tee -a "$LOG"

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-coder-32b-budgeted-15000 \
    --model-tag    qwen25-coder-32b \
    --agent-config config-qwen25-coder-32b-vllm.yaml \
    --otrc-config  config-online-trc-qwen25-coder-32b.yaml \
    --budget       15000 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_BUDGETED \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-coder-32b-budgeted-15000 \
    --model-tag    qwen25-coder-32b \
    --agent-config config-qwen25-coder-32b-vllm.yaml \
    --otrc-config  config-online-trc-qwen25-coder-32b.yaml \
    --budget       15000 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_BUDGETED \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Qwen2.5-Coder-32B phase DONE — 780 runs complete ===" | tee -a "$LOG"
