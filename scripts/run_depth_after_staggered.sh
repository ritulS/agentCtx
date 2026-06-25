#!/bin/bash
# Waits for the staggered pilot to finish, snapshots its results into
# Review1/raw/, then launches the depth-0.3 + 0.7 ablation (8 primitives @ 20k),
# and finally snapshots the full depth curve (30/40/50/60/70) into Review1/raw/.
#
# Designed to run unattended via nohup. Polls staggered PID every 30s.

set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/depth_chain.log"
mkdir -p "$WS/logs" "$WS/Review1/raw/staggered_runs" "$WS/Review1/raw/depth_runs"
echo "[$(date)] === depth-chain wrapper starting (PID $$) ===" | tee -a "$LOG"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Wait for the staggered pilot to finish
# ─────────────────────────────────────────────────────────────────────────────
if [ -f logs/staggered_pilot.pid ]; then
    STAG_PID=$(cat logs/staggered_pilot.pid)
    echo "[$(date)] Waiting for staggered PID $STAG_PID..." | tee -a "$LOG"
    while kill -0 "$STAG_PID" 2>/dev/null; do sleep 30; done
    echo "[$(date)] Staggered PID $STAG_PID exited." | tee -a "$LOG"
else
    echo "[$(date)] WARNING: logs/staggered_pilot.pid missing — assuming done." | tee -a "$LOG"
fi

# Sanity-check the staggered log for a clean completion marker.
if grep -q "=== Staggered pilot complete ===" logs/staggered_pilot.log 2>/dev/null; then
    echo "[$(date)] Staggered pilot completion marker found." | tee -a "$LOG"
else
    echo "[$(date)] WARNING: completion marker NOT found in staggered_pilot.log — proceeding anyway." | tee -a "$LOG"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Add staggered rows to Review1.csv + snapshot raw experiment_results.json
# ─────────────────────────────────────────────────────────────────────────────
echo "[$(date)] Building staggered rows in Review1.csv..." | tee -a "$LOG"
venv/bin/python3 Review1/build_review1.py staggered_alternate staggered_random 2>&1 | tee -a "$LOG"

for b in 10000 15000 20000; do
    src="results/ablations/staggered-pilot-$b/experiment_results.json"
    if [[ -f "$src" ]]; then
        cp "$src" "Review1/raw/staggered_runs/staggered-pilot-$b.json"
        echo "[$(date)] snapshot: Review1/raw/staggered_runs/staggered-pilot-$b.json" | tee -a "$LOG"
    else
        echo "[$(date)] WARNING: $src missing, skipping snapshot" | tee -a "$LOG"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# 3. Launch depth-0.3 + 0.7 ablation (8 primitives @ 20k)
# ─────────────────────────────────────────────────────────────────────────────
CONDS="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss"
echo "[$(date)] === depth-30+70 ablation starting ===" | tee -a "$LOG"

for depth in 0.3 0.7; do
    pct=$(printf "%.0f" "$(echo "$depth * 100" | bc)")
    name="depth-${pct}"
    echo "[$(date)] --- $name agent runs starting ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     20000     \
        --depth      "$depth"  \
        --conditions $CONDS    \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] --- $name agent runs done; eval ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     20000     \
        --depth      "$depth"  \
        --conditions $CONDS    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] --- $name COMPLETE ---" | tee -a "$LOG"
done

# ─────────────────────────────────────────────────────────────────────────────
# 4. Snapshot the full depth curve (existing 40/50/60 + freshly-run 30/70)
# ─────────────────────────────────────────────────────────────────────────────
echo "[$(date)] Snapshotting depth experiment_results.json files..." | tee -a "$LOG"
for d in 30 40 50 60 70; do
    src="results/ablations/depth-$d/experiment_results.json"
    if [[ -f "$src" ]]; then
        cp "$src" "Review1/raw/depth_runs/depth-$d.json"
        echo "[$(date)] snapshot: Review1/raw/depth_runs/depth-$d.json" | tee -a "$LOG"
    fi
done

echo "[$(date)] === depth-chain wrapper COMPLETE ===" | tee -a "$LOG"
