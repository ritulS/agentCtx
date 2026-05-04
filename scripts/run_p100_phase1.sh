#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase1.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 1: singles + ∞ baselines on 70 new tasks ===" | tee -a "$LOG"

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial"
CONDS_INF="full-context online-trc"

# 15k → 10k → 20k for budgeted
for budget in 15000 10000 20000; do
    name="p100-singles-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

# Infinite-budget conditions, single dir
echo "[$(date)] --- p100-inf ---" | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-inf \
    --budget     999999999 \
    --tasks-file task_lists/p100_new_tasks.json \
    --conditions $CONDS_INF \
    2>&1 | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-inf \
    --budget     999999999 \
    --tasks-file task_lists/p100_new_tasks.json \
    --conditions $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Phase 1 done — chaining to phase 2 ===" | tee -a "$LOG"
exec "$WS/scripts/run_p100_phase2.sh"
