#!/bin/bash
# Wait for image prewarm to finish, verify cache, then launch the depth-grid master orchestrator.
set -uo pipefail
cd /home/rs67788/projects/agentCtx
LOG=logs/depth_grid_chain.log
mkdir -p logs
echo "[$(date)] === depth-grid chain wrapper starting (PID $$) ===" | tee -a "$LOG"

# 1. Wait for prewarm
if [ -f logs/depth_grid_image_prewarm.pid ]; then
    PWP=$(cat logs/depth_grid_image_prewarm.pid)
    echo "[$(date)] Waiting for prewarm PID $PWP..." | tee -a "$LOG"
    while kill -0 "$PWP" 2>/dev/null; do sleep 30; done
    echo "[$(date)] Prewarm PID $PWP exited." | tee -a "$LOG"
fi

# Sanity-check completion marker
if grep -q "PREWARM DONE" logs/depth_grid_image_prewarm.log 2>/dev/null; then
    tail -1 logs/depth_grid_image_prewarm.log | tee -a "$LOG"
else
    echo "[$(date)] WARN: PREWARM DONE marker NOT found in prewarm log — proceeding anyway" | tee -a "$LOG"
fi

# 2. Verify cache: re-run check (informational)
echo "[$(date)] Verifying image cache..." | tee -a "$LOG"
venv/bin/python3 scripts/check_image_cache.py task_lists/p100_all_100_tasks.json 2>&1 | tee -a "$LOG" || true

# 3. Launch master orchestrator under nohup
echo "[$(date)] === launching master orchestrator ===" | tee -a "$LOG"
nohup venv/bin/python3 scripts/run_depth_grid_p100.py > logs/depth_grid_p100.out 2>&1 &
MASTER_PID=$!
echo "$MASTER_PID" > logs/depth_grid_p100.pid
echo "[$(date)] Master orchestrator PID $MASTER_PID. Log: logs/depth_grid_p100.out" | tee -a "$LOG"
echo "[$(date)] === chain wrapper done ===" | tee -a "$LOG"
