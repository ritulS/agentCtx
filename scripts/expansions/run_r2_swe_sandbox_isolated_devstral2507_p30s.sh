#!/usr/bin/env bash
# Devstral-Small-2507 isolated cell on ALL 30 P30S tasks
# (task_lists/swe_verified/p30_stratified.json), 3 runs per task, one request
# at a time: a fresh vLLM server and container generation per run, MAX_WORKERS=1.
#
# This is scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh with
# three defaults changed and nothing else:
#   TASKS_FILE     task_lists/swe_verified/p30_stratified.json (30 tasks; the
#                  Devstral wrapper's default is its 6-task sandbox cohort)
#   RUNS_PER_TASK  3  (the P30S section's run count; the wrapper's default is 10)
#   R2_MODEL       devstral2507-iso-p30s -> data/r2/swebench/p30s/devstral2507-iso-p30s/<cell>/
#                  A separate dir from devstral2507-iso (the 6-task cohort at
#                  10 runs/task) so this cell is a clean 30 x 3 grid; set
#                  R2_MODEL=devstral2507-iso to resume into that dir instead
#                  (the 6 tasks' r1-r3 are then skipped as already recorded).
# Everything else is the Devstral wrapper's: SERVER_LIFECYCLE=per-run (fresh
# server per run), PREFIX_CACHE=on, cell di__b15k__su-free (summarizer = the
# agent model; CELLS="di__b15k__su-free:summarization-free:0.5 d05__b15k__tr:truncation:0.5"
# adds TR), run-major order, agent config configs/config-devstral2507-vllm.yaml
# (temperature 0, max_tokens 4096), eval after every run, containers purged
# after every run, DRY_RUN=1 prints the 90-key plan. Resume: rerun with the same
# settings; recorded keys are skipped.
#
# Usage (Albus; the driver starts and stops the server itself, do not start one):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso-p30s \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh
# Cost: 90 cycles x ~8.7 min (measured 2026-10-17/18 on the 6-task cell: 5.8 min
# agent e2e + ~60 s server start + eval and purge) = ~13 h for the SU-free cell.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

export TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/p30_stratified.json}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
export R2_MODEL="${R2_MODEL:-devstral2507-iso-p30s}"
exec bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated_devstral2507.sh"
