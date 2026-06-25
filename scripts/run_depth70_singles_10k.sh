#!/bin/bash
# Backfill the one missing cell in the Qwen3.5-35B-A3B coverage:
#   depth-tunable × depth=0.7 × budget=10k × ABL-30
# 5 conds × 30 tasks × 2 runs = 300 runs, ~5 h at observed throughput.
#
# Sequence:
#   1. Prewarm the 30 ABL task images (sequential podman pull; cached pulls are skipped)
#   2. Agent loop on the 5 depth-tunable singles at depth=0.7 / budget=10000 / ABL tasks
#   3. Eval pass on the same cell
set -uo pipefail
cd /home/rs67788/projects/agentCtx
LOG=logs/depth70_singles_10k.out
mkdir -p logs

PODMAN="$HOME/.local/bin/podman"
[ -x "$PODMAN" ] || PODMAN=podman

echo "[$(date)] === depth70-singles-10k backfill starting (PID $$) ===" | tee -a "$LOG"

# 1. Prewarm
echo "[$(date)] Prewarming ABL-30 task images sequentially..." | tee -a "$LOG"
ok=0; fail=0; skip=0; total=0
while read task; do
    [ -z "$task" ] && continue
    total=$((total+1))
    owner="${task%%__*}"
    repo_part="${task#*__}"
    image="docker.io/swebench/sweb.eval.x86_64.${owner}_1776_${repo_part}:latest"
    if "$PODMAN" image exists "$image" 2>/dev/null; then
        skip=$((skip+1))
        continue
    fi
    if "$PODMAN" pull --quiet "$image" >> "$LOG" 2>&1; then
        ok=$((ok+1))
    else
        fail=$((fail+1))
        echo "[$(date +%T)] FAIL $image" | tee -a "$LOG"
    fi
done < scripts/abl30_images.txt
echo "[$(date)] PREWARM DONE — total=$total ok=$ok skip=$skip fail=$fail" | tee -a "$LOG"
if [ "$fail" -gt 0 ]; then
    echo "[$(date)] aborting: $fail image pulls failed" | tee -a "$LOG"
    exit 1
fi

# 2. Agent loop
ARGS=(
    --ablation   p100-depth70-singles-10000
    --budget     10000
    --depth      0.7
    --tasks-file results/ablations/tasks.json
    --conditions truncation summarization summarization-partial structured-summarize structured-summarize-partial
)

echo "[$(date)] === AGENT phase ===" | tee -a "$LOG"
START_AGENT=$(date +%s)
venv/bin/python3 scripts/run_experiment.py "${ARGS[@]}" 2>&1 | tee -a "$LOG"
echo "[$(date)] AGENT exit=$? duration=$(( ($(date +%s) - START_AGENT) / 60 ))min" | tee -a "$LOG"

# 3. Eval pass
echo "[$(date)] === EVAL phase ===" | tee -a "$LOG"
START_EVAL=$(date +%s)
venv/bin/python3 scripts/run_experiment.py "${ARGS[@]}" --eval-only 2>&1 | tee -a "$LOG"
echo "[$(date)] EVAL exit=$? duration=$(( ($(date +%s) - START_EVAL) / 60 ))min" | tee -a "$LOG"

# 4. Snapshot
SNAP=Review1/raw/depth_p100_runs/p100-depth70-singles-10000.json
SRC=results/ablations/p100-depth70-singles-10000/experiment_results.json
if [ -f "$SRC" ]; then
    cp -p "$SRC" "$SNAP"
    echo "[$(date)] snapshot → $SNAP" | tee -a "$LOG"
else
    echo "[$(date)] WARN: $SRC not found, no snapshot" | tee -a "$LOG"
fi

echo "[$(date)] === depth70-singles-10k backfill DONE ===" | tee -a "$LOG"
