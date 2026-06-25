#!/bin/bash
# Detached watcher: blocks until the canonical-sweep parent bash exits,
# then exec's into the tail-depths sweep. Survives terminal disconnects.
#
# Launched by: scripts/start_devstral_chain_watcher.sh (which detaches it
# via nohup + setsid).
#
# Polling interval: 120s (canonical sweep has ~12-14h remaining, so this is
# cheap and gives modest log granularity).
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/devstral_chain_watcher.log"
exec >> "$LOG" 2>&1

# The canonical-sweep parent bash PID at the time the watcher was launched.
# This is the script driver, not any single python subprocess.
TARGET_PID="${1:-91607}"

echo "[$(date)] Chain watcher started (PID $$, watching $TARGET_PID)"
while kill -0 "$TARGET_PID" 2>/dev/null; do
    sleep 120
done

echo "[$(date)] §c parent (PID $TARGET_PID) exited. Tail of canonical log:"
tail -5 logs/devstral_2_canonical.log
echo ""
echo "[$(date)] Launching §d tail-depths sweep..."
exec bash scripts/run_devstral_tail_depths.sh
