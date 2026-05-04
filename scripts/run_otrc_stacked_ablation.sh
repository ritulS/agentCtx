#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

LOG="$WS/logs/otrc_stacked_ablation.log"
mkdir -p "$WS/logs"
echo "[$(date)] Starting OTRC stacked ablation (otrc-tr, otrc-su-partial, otrc-ss-partial)" | tee -a "$LOG"

CONDS="otrc-tr otrc-su-partial otrc-ss-partial"

# Run order: 15k first (intermediate, fastest path through the data), then 10k, then 20k
for budget in 15000 10000 20000; do
    name="otrc-stacked-${budget}"
    echo "[$(date)] === Starting $name with conditions: $CONDS ===" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $CONDS    \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === $name agent runs done — starting eval ===" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $CONDS    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Done with $name ===" | tee -a "$LOG"
done

echo "[$(date)] All OTRC stacked ablation runs complete" | tee -a "$LOG"
