#!/bin/bash
# Wait for partial-summary ablation (PID 1904105) to finish, then launch OTRC stacked ablation.
# Aborts if the partial run did not produce all 3 expected result files.
set -uo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

WAIT_LOG="$WS/logs/otrc_stacked_ablation.wait.log"
PARTIAL_PID=1904105

mkdir -p "$WS/logs"
echo "[$(date)] Waiting for partial-summary ablation (PID $PARTIAL_PID) to exit..." | tee -a "$WAIT_LOG"

# Poll until the partial-summary master process exits.
while ps -p "$PARTIAL_PID" > /dev/null 2>&1; do
    sleep 60
done
echo "[$(date)] PID $PARTIAL_PID has exited." | tee -a "$WAIT_LOG"

# Verify partial-summary ablation produced its result files (per §2 step 1).
MISSING=0
for budget in 10000 15000 20000; do
    f="$WS/results/ablations/partial-${budget}/experiment_results.json"
    if [[ ! -f "$f" ]]; then
        echo "[$(date)] ABORT: missing $f — partial run did not finish cleanly." | tee -a "$WAIT_LOG"
        MISSING=1
    fi
done
if [[ "$MISSING" -ne 0 ]]; then
    exit 1
fi

# Confirm vLLM is still up before launching.
if ! curl -s --max-time 5 http://localhost:8000/v1/models | grep -q "Qwen3.5-35B-A3B"; then
    echo "[$(date)] ABORT: vLLM not responding at http://localhost:8000/v1/models" | tee -a "$WAIT_LOG"
    exit 1
fi

# Confirm no other workers are active.
N_WORKERS=$(ps -ef | grep -E "run_experiment|swebench_single" | grep -v grep | grep -v wait_then_run_otrc | wc -l)
if [[ "$N_WORKERS" -ne 0 ]]; then
    echo "[$(date)] ABORT: $N_WORKERS run_experiment/swebench_single processes still active." | tee -a "$WAIT_LOG"
    exit 1
fi

echo "[$(date)] Pre-flight passed — launching OTRC stacked ablation." | tee -a "$WAIT_LOG"

# Hand off to the OTRC launch script. We exec so the OTRC script becomes the same PID.
exec bash "$WS/scripts/run_otrc_stacked_ablation.sh" >> "$WS/logs/otrc_stacked_ablation.stdout" 2>&1
