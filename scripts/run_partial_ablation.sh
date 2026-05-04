#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

LOG="$WS/logs/partial_ablation.log"
mkdir -p "$WS/logs"
echo "[$(date)] Starting partial-summary ablation (SU-partial, SS-partial, SS gap-fill)" | tee -a "$LOG"

# Per-budget condition list:
#   10k & 20k: include SS to fill the gap (timing-10k/20k didn't run SS)
#   15k:        SS already covered by qwen3.5-35B-A3B_15k_Fullrun, only run partials
declare -A CONDS=(
    [10000]="summarization-partial structured-summarize-partial structured-summarize"
    [15000]="summarization-partial structured-summarize-partial"
    [20000]="summarization-partial structured-summarize-partial structured-summarize"
)

# Run order: 15k first (smallest, fastest), then 10k, then 20k
for budget in 15000 10000 20000; do
    name="partial-${budget}"
    conds="${CONDS[$budget]}"
    echo "[$(date)] === Starting $name with conditions: $conds ===" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $conds    \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === $name agent runs done — starting eval ===" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $conds    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Done with $name ===" | tee -a "$LOG"
done

echo "[$(date)] All partial-summary ablation runs complete" | tee -a "$LOG"
