#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase2.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 2: TRC stack ===" | tee -a "$LOG"

CONDS="tool-result-clear trc-su trc-ss"

for budget in 15000 10000 20000; do
    name="p100-trc-${budget}"
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

echo "[$(date)] === Phase 2 done — chaining to phase 3 ===" | tee -a "$LOG"
exec "$WS/scripts/run_p100_phase3.sh"
