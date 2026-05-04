#!/usr/bin/env bash
# clean_results.sh — safely wipe experiment results and running processes
#
# Usage:
#   bash scripts/clean_results.sh          # interactive (asks before deleting)
#   bash scripts/clean_results.sh --force  # no prompts
#   bash scripts/clean_results.sh --dry-run

set -euo pipefail

FORCE=false
DRY=false
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=true ;;
    --dry-run) DRY=true ;;
    *) echo "Unknown arg: $arg. Use --force or --dry-run."; exit 1 ;;
  esac
done

RESULTS_DIR="$(cd "$(dirname "$0")/.." && pwd)/results"
LOG="$(cd "$(dirname "$0")/.." && pwd)/logs/experiment.log"

# ── 1. Show what is running ────────────────────────────────────────────────────
echo "=== Running experiment processes ==="
PIDS=$(pgrep -f "run_experiment\|swebench_single\|minisweagent" 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  echo "  (none)"
else
  for pid in $PIDS; do
    cmdline=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' | cut -c1-80 || true)
    budget=$(cat /proc/$pid/environ 2>/dev/null | tr '\0' '\n' | grep MSWEA_TOKEN_BUDGET || true)
    echo "  PID $pid  $budget  ${cmdline}"
  done
fi

# ── 2. Show current results summary ───────────────────────────────────────────
echo ""
echo "=== Current results ==="
if [ -f "$RESULTS_DIR/experiment_results.json" ]; then
  python3 -c "
import json
data = json.load(open('$RESULTS_DIR/experiment_results.json'))
patches = sum(1 for r in data if r.get('patch_generated'))
print(f'  {len(data)} runs recorded  |  {patches} patches generated')
trajs = __import__('glob').glob('$RESULTS_DIR/**/trajectory.json', recursive=True)
print(f'  {len(trajs)} trajectory files on disk')
disk = __import__('subprocess').check_output(['du','-sh','$RESULTS_DIR']).decode().split()[0]
print(f'  Disk usage: {disk}')
"
else
  echo "  (no results yet)"
fi

# ── 3. Confirm ────────────────────────────────────────────────────────────────
echo ""
if [ "$DRY" = true ]; then
  echo "[DRY RUN] Would kill processes and delete $RESULTS_DIR"
  exit 0
fi

if [ "$FORCE" = false ]; then
  read -r -p "Kill all processes and delete results/? [y/N] " confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
fi

# ── 4. Kill processes ─────────────────────────────────────────────────────────
echo ""
echo "Killing experiment processes..."
pkill -9 -f "run_experiment" 2>/dev/null && echo "  run_experiment killed" || true
pkill -9 -f "swebench_single" 2>/dev/null && echo "  swebench_single killed" || true
pkill -9 -f "minisweagent" 2>/dev/null && echo "  minisweagent killed" || true
sleep 2

# Verify
REMAINING=$(pgrep -f "run_experiment\|swebench_single\|minisweagent" 2>/dev/null | wc -l || true)
REMAINING=${REMAINING:-0}
if [ "${REMAINING}" -gt 0 ] 2>/dev/null; then
  echo "  WARNING: $REMAINING process(es) still alive — may need manual kill"
else
  echo "  All processes stopped."
fi

# ── 5. Clear results ──────────────────────────────────────────────────────────
echo "Clearing $RESULTS_DIR ..."
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR"
echo "  Done."

# ── 6. Optionally rotate log ──────────────────────────────────────────────────
if [ -f "$LOG" ] && [ "$FORCE" = false ]; then
  read -r -p "Also clear experiment.log? [y/N] " logconfirm
  if [[ "$logconfirm" =~ ^[Yy]$ ]]; then
    > "$LOG" && echo "  experiment.log cleared."
  fi
elif [ "$FORCE" = true ] && [ -f "$LOG" ]; then
  > "$LOG" && echo "  experiment.log cleared."
fi

echo ""
echo "Ready. To restart:"
echo "  source venv/bin/activate && nohup python scripts/run_experiment.py >> logs/experiment.log 2>&1 &"
