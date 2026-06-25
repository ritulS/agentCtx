#!/bin/bash
# Sequential podman pull of all 100 task images for the depth-grid expansion.
# Sequential to avoid the cold-pull cascade incident from 2026-05-06.
set -uo pipefail
cd /home/rs67788/projects/agentCtx
LOG=logs/depth_grid_image_prewarm.log
mkdir -p logs

echo "[$(date)] Starting prewarm of depth-grid task images" | tee -a "$LOG"

PODMAN="$HOME/.local/bin/podman"
[ -x "$PODMAN" ] || PODMAN=podman

ok=0
fail=0
skip=0
total=0
while read task; do
    [ -z "$task" ] && continue
    total=$((total+1))
    owner="${task%%__*}"
    repo_part="${task#*__}"
    image="docker.io/swebench/sweb.eval.x86_64.${owner}_1776_${repo_part}:latest"
    if "$PODMAN" image exists "$image" 2>/dev/null; then
        skip=$((skip+1))
        echo "[$(date +%T)] skip (cached) $task" >> "$LOG"
        continue
    fi
    echo "[$(date +%T)] pull $image" | tee -a "$LOG"
    if "$PODMAN" pull --quiet "$image" >> "$LOG" 2>&1; then
        ok=$((ok+1))
    else
        fail=$((fail+1))
        echo "[$(date +%T)] FAIL $image" | tee -a "$LOG"
    fi
done < scripts/depth_grid_images.txt

echo "[$(date)] PREWARM DONE — total=$total ok=$ok skip=$skip fail=$fail" | tee -a "$LOG"
