#!/bin/bash
# Waits for the online-trc full run (PID 1188003) to complete, then launches
# TRC-20k fill run for the 70 tasks not covered by results/qwen35-a3b_20k/.

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
ONLINE_TRC_PID=1188003
ONLINE_TRC_RESULTS="$WORKSPACE/results/qwen35-a3b_online-trc/experiment_results.json"
EXPECTED_RUNS=198
LOG="$WORKSPACE/logs/trc20k_fill_launch.log"

mkdir -p "$WORKSPACE/logs"

echo "[$(date)] Watcher started. Waiting for online-trc run (PID $ONLINE_TRC_PID) to complete..." | tee -a "$LOG"

# Wait for process to exit, then confirm result count
while kill -0 "$ONLINE_TRC_PID" 2>/dev/null; do
    sleep 60
done

echo "[$(date)] PID $ONLINE_TRC_PID exited. Checking results..." | tee -a "$LOG"

# Give a short grace period for the final file write
sleep 10

N=$(python3 -c "import json; d=json.load(open('$ONLINE_TRC_RESULTS')); print(len(d))" 2>/dev/null || echo 0)
echo "[$(date)] online-trc results: $N / $EXPECTED_RUNS runs recorded." | tee -a "$LOG"

echo "[$(date)] Launching TRC-20k fill run (70 tasks)..." | tee -a "$LOG"

cd "$WORKSPACE"
python3 scripts/run_experiment.py \
    --model-tag      qwen35-a3b_trc20k-fill \
    --tasks-file     selected_tasks_trc20k_fill.json \
    --conditions     tool-result-clear \
    --budget         20000 \
    2>&1 | tee -a "$LOG"

echo "[$(date)] TRC-20k fill run complete." | tee -a "$LOG"
