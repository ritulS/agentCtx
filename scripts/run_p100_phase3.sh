#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase3.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 3: OTRC stack ===" | tee -a "$LOG"

CONDS="otrc-tr otrc-su-partial otrc-ss-partial"

for budget in 15000 10000 20000; do
    name="p100-otrc-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === ALL P100 PHASES COMPLETE ===" | tee -a "$LOG"
