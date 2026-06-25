#!/bin/bash
# Detached autochain for Qwen2.5-Coder-32B model expansion:
#   pilot (in-flight) → sanity gate → §a + §c@15k (780 runs)
# Survives session disconnect (launched via setsid + nohup).
#
# Sanity gate: pilot must show >=5/10 Submitted exit status. If <5,
# halts and writes a failure marker; doesn't burn GPU on a broken setup.
#
# Logs to logs/qwen25_coder_32b_autochain.log
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_coder_32b_autochain.log"
exec >> "$LOG" 2>&1

PILOT_RESULTS="$WS/results/ablations/qwen25-coder-32b-pilot/experiment_results.json"

echo ""
echo "[$(date)] ============================================================"
echo "[$(date)] Qwen2.5-Coder-32B autochain started (this script PID $$)"
echo "[$(date)] ============================================================"

# Find the pilot's run_experiment.py process by command-line match.
PILOT_PID=$(pgrep -f 'run_experiment.py.*qwen25-coder-32b-pilot' | head -1 || true)

if [ -n "$PILOT_PID" ]; then
    echo "[$(date)] Waiting for pilot PID $PILOT_PID to exit..."
    while kill -0 "$PILOT_PID" 2>/dev/null; do
        sleep 60
    done
    echo "[$(date)] Pilot PID $PILOT_PID exited."
else
    echo "[$(date)] Pilot PID not found by name; will poll for results file."
    for _ in $(seq 1 120); do  # up to 2h wait
        [ -f "$PILOT_RESULTS" ] && break
        sleep 60
    done
fi

# Wait an extra 60s for filesystem to settle.
sleep 60

if [ ! -f "$PILOT_RESULTS" ]; then
    echo "[$(date)] FATAL: pilot results file missing at $PILOT_RESULTS. Halting."
    echo "QWEN25_CODER_32B_AUTOCHAIN_FAILED_PILOT_MISSING" > logs/qwen25_coder_32b_autochain.STATUS
    exit 1
fi

# Sanity gate: count Submitted exits.
N_SUB=$(venv/bin/python3 -c "
import json
rows = json.load(open('$PILOT_RESULTS'))
n_sub = sum(1 for r in rows if r.get('exit_status')=='Submitted')
print(n_sub)
")
N_TOT=$(venv/bin/python3 -c "
import json
print(len(json.load(open('$PILOT_RESULTS'))))
")

echo "[$(date)] Pilot results: $N_SUB / $N_TOT Submitted"

if [ "$N_SUB" -lt 5 ]; then
    echo "[$(date)] FATAL: pilot sanity gate failed (need >=5/10 Submitted, got $N_SUB)."
    echo "[$(date)] Halting; full phase script NOT launched."
    echo "QWEN25_CODER_32B_AUTOCHAIN_FAILED_SANITY:${N_SUB}_of_${N_TOT}_Submitted" > logs/qwen25_coder_32b_autochain.STATUS
    exit 1
fi

echo "[$(date)] ============================================================"
echo "[$(date)] Pilot PASS ($N_SUB/$N_TOT Submitted). Launching phase script."
echo "[$(date)] ============================================================"
echo "QWEN25_CODER_32B_AUTOCHAIN_PHASE_STARTED_$(date +%Y%m%d_%H%M%S)" > logs/qwen25_coder_32b_autochain.STATUS

# Hand off: exec replaces this process so the phase script becomes the lifespan owner.
exec bash scripts/run_qwen25_coder_32b_phase.sh
