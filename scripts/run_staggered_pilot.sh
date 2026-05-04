#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/staggered_pilot.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Staggered pilot starting ===" | tee -a "$LOG"

CONDS="staggered-alternate staggered-random"

# 6 hardest tasks × 2 strategies × 3 budgets × 2 runs = 72 runs
for budget in 15000 10000 20000; do
    name="staggered-pilot-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --tasks-file task_lists/staggered_pilot.json \
        --conditions $CONDS    \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --tasks-file task_lists/staggered_pilot.json \
        --conditions $CONDS    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] --- $name done ---" | tee -a "$LOG"
done

echo "[$(date)] === Staggered pilot complete ===" | tee -a "$LOG"
