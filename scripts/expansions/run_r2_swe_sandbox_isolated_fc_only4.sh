#!/usr/bin/env bash
# Isolated cell (one agent run per fresh caching-OFF vLLM server and container
# generation, 1 worker) on the four p100_fc_only4 tasks: django-11433,
# sklearn-13124, sklearn-14983, sympy-17318 (resolved under full context but
# never under fixed TR / SU-free; task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json).
#
# Same recipe as the sandbox isolated cell qwen35b-cap4k-sumnothink-iso on the
# four sandbox tasks: cap4k agent config, SUMMARIZER=nothink (summarizer-only
# thinking OFF, reply cap 2048), SUMMARY_MAX_ATTEMPTS=5, adaptive-prefix3-sss,
# budget 15k, depth 0.5, prefix caching OFF (scripts/serving/start_vllm_qwen35_sandbox.sh,
# TP=8 with AGENTCTX_PROFILE=albus-swe). The section's own run limits apply
# (400 LLM calls / 7200 s per run, set by run_r2_swe_never7_adaptive.sh for
# p100_fc_only4 instead of the sandbox sections' 300 / 7200).
#
# Output: data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink-iso/d05__b15k__adaptive-prefix3-sss/
# (a different section dir from the sandbox isolated cell, so the rows never mix).
#
# This script only fixes the defaults below and hands over to
# scripts/expansions/run_r2_swe_sandbox_isolated.sh, which owns the server and
# container lifecycle, the guards, resume (recorded keys skipped) and DRY_RUN.
#   SECTIONS=p100_fc_only4  PATTERNS=sss  RUNS_PER_TASK=10  (N_TASKS=all)
# Override any of them by env (e.g. RUNS_PER_TASK=15 to match the sandbox iso
# cell, PATTERNS="sss ttt" for both uniform orders).
#
# Usage (Albus; the driver starts and stops the server itself, do not start one):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p100_fc_only4-qwen35b-cap4k-sumnothink-iso \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh
# Cost: the 3-worker rows of these tasks took 61 min mean e2e (ttt cell) and the
# isolated sandbox rows ran at ~0.7x of their 3-worker time, so expect ~45 min
# per cycle including the server start (~100 s) and eval: ~30 h for 4 x 10 runs,
# ~45 h with RUNS_PER_TASK=15.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SECTIONS="${SECTIONS:-p100_fc_only4}"
export PATTERNS="${PATTERNS:-sss}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-10}"
exec bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated.sh"
