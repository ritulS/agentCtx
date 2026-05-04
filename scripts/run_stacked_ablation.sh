#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

LOG="$WS/logs/stacked_ablation.log"
echo "[$(date)] Starting stacked ablation runs (TRC+SU, TRC+SS) at 10k/15k/20k" | tee -a "$LOG"

for budget in 15000 10000 20000; do
    name="stacked-${budget}"
    echo "[$(date)] === Starting $name ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --conditions trc-su trc-ss \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Finished $name agent runs, starting eval ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --conditions trc-su trc-ss \
        --eval-only \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Done with $name ===" | tee -a "$LOG"
done

echo "[$(date)] All stacked ablation runs complete" | tee -a "$LOG"
