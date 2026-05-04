#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
mkdir -p "$WS/logs"

# Pre-flight: all wrappers exist and are executable
for s in run_p100_phase1.sh run_p100_phase2.sh run_p100_phase3.sh; do
    test -x "$WS/scripts/$s" || { echo "missing or non-exec: $s"; exit 1; }
done

# Inventory + seed (idempotent — re-running is safe)
venv/bin/python3 scripts/p100_inventory.py
venv/bin/python3 scripts/p100_seed.py

# Hand off to phase 1; phase 1 execs phase 2 execs phase 3
exec "$WS/scripts/run_p100_phase1.sh"
