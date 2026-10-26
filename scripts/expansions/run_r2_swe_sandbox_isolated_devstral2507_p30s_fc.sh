#!/usr/bin/env bash
# Devstral-Small-2507 isolated FULL-CONTEXT cell on ALL 30 P30S tasks
# (task_lists/swe_verified/p30_stratified.json), 3 runs per task, one request
# at a time: a fresh vLLM server and container generation per run, MAX_WORKERS=1.
#
# This is scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh
# with ONE default changed and nothing else:
#   CELLS  di__binf__fc:full-context:0.5  (no compression, unlimited budget;
#          the p30s wrapper's default is di__b15k__su-free). The cell name
#          carries the budget tag `binf`, which the inner launcher maps to the
#          INFINITE_BUDGET sentinel (999999999), as in run_r2_swe_p30s.sh fc.
#          Depth 0.5 is a placeholder (full-context never compresses).
# Everything else is the P30S wrapper's: 30 tasks x 3 runs = 90 cycles,
# run-major order, per-run server, PREFIX_CACHE=on, agent config
# configs/config-devstral2507-vllm.yaml (temperature 0, max_tokens 4096, step
# limit 300), eval after every run, containers purged after every run.
# Dest: the SAME model dir as the SU-free cell, a separate cell dir:
#   Dobby (no AGENTCTX_PROFILE): data/r2/swebench/p30s/devstral2507-iso-p30s-dobby/di__binf__fc/
#                                 (server on GPUs 2-3, TP=2; DEVSTRAL_CUDA_DEVICES / DEVSTRAL_TP_SIZE override)
#   Albus (AGENTCTX_PROFILE=albus-swe): data/r2/swebench/p30s/devstral2507-iso-p30s/di__binf__fc/
# so the FC rows sit next to the SU-free rows of the same machine. Resume: rerun
# with the same settings; recorded keys are skipped.
# Note: the context is unbounded, so long runs grow towards the server's
# 131072-token max-model-len; a run whose prompt no longer fits ends with a
# context-length error from vLLM and is recorded as such (not resolved).
#
# Usage (the driver starts and stops the server itself, do not start one):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s_fc.sh
#   Dobby (GPUs 2-3):
#   bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso-p30s-dobby-fc \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s_fc.sh
#   Albus (all 8 GPUs):
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso-p30s-fc \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s_fc.sh
# Cost: the SU-free cell took 11.2 h for 90 cycles on Dobby (2026-10-21/22:
# agent e2e mean 6.1 min + ~7 min server start on GPUs 2-3 for the first cycle,
# ~1-2 min after + eval and purge). FC runs have longer prompts (no compression)
# so expect ~12-15 h.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CELLS="${CELLS:-di__binf__fc:full-context:0.5}"
exec bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh"
