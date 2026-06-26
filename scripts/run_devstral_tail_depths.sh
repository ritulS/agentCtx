#!/bin/bash
# Devstral-Small-2-24B-Instruct-2512  §d: 5 depth-tunable prims × 3 calibrated
# budgets × 2 tail depths (0.3, 0.7) × ABL-30 × 2 runs = 1,800 runs.
# Output dirs: results/ablations/devstral-2-budgeted-{15000,20000,24000}-d{030,070}/
#
# Budgets locked from FC §a calibration (must match §c):
#   TIGHT  = 15000   MEDIUM = 20000   LOOSE = 24000
#
# Usage:  nohup bash scripts/run_devstral_tail_depths.sh > logs/devstral_2_tail.out 2>&1 &
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/devstral_2_tail.log"
mkdir -p "$WS/logs"

TIGHT_BUDGET=15000
MEDIUM_BUDGET=20000
LOOSE_BUDGET=24000

echo "[$(date)] === Devstral §d: tail-depth sweep (d=0.3, 0.7) ===" | tee -a "$LOG"
echo "[$(date)] Budgets: T=$TIGHT_BUDGET  M=$MEDIUM_BUDGET  L=$LOOSE_BUDGET" | tee -a "$LOG"

if ! curl -sf http://localhost:8002/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM Devstral not responding on port 8002. Run scripts/start_vllm_devstral.sh first." | tee -a "$LOG"
    exit 1
fi

CONDS_DEPTH_TUNABLE="truncation summarization summarization-partial structured-summarize structured-summarize-partial"

# Run order: d=0.3 layer first (M, T, L), then d=0.7 layer.
for depth_label in d030 d070; do
    case "$depth_label" in
        d030) DEPTH=0.3 ;;
        d070) DEPTH=0.7 ;;
    esac
    for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
        name="devstral-2-budgeted-${budget}-${depth_label}"
        echo "[$(date)] --- $name (depth=$DEPTH) ---" | tee -a "$LOG"

        venv/bin/python3 scripts/run_experiment.py \
            --ablation     "$name" \
            --model-tag    devstral-2 \
            --agent-config configs/config-devstral-vllm.yaml \
            --otrc-config  configs/config-online-trc-devstral.yaml \
            --budget       "$budget" \
            --depth        "$DEPTH" \
            --tasks-file   task_lists/ablation_30tasks.json \
            --conditions   $CONDS_DEPTH_TUNABLE \
            2>&1 | tee -a "$LOG"

        venv/bin/python3 scripts/run_experiment.py \
            --ablation     "$name" \
            --model-tag    devstral-2 \
            --agent-config configs/config-devstral-vllm.yaml \
            --otrc-config  configs/config-online-trc-devstral.yaml \
            --budget       "$budget" \
            --depth        "$DEPTH" \
            --tasks-file   task_lists/ablation_30tasks.json \
            --conditions   $CONDS_DEPTH_TUNABLE \
            --eval-only \
            2>&1 | tee -a "$LOG"
    done
done

echo "[$(date)] === Devstral §d DONE — full 3,900-run grid complete ===" | tee -a "$LOG"
