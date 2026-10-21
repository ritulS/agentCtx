#!/usr/bin/env bash
# Devstral-Small-2507 isolated cells: ONE agent run per fresh vLLM server and
# container generation, 1 worker, on the 6-task Devstral sandbox cohort
# (task_lists/swe_verified/sandbox_devstral2507_sufree3_never3.json: the 3 tasks
# resolved in >=2 of 3 SU-free runs and 3 of the tasks resolved 0/3 under both
# SU-free and TR in data/r2/swebench/p30s/devstral2507/, 2026-10-17), 10 runs
# per task, cell di__b15k__su-free (budget 15k, depth 0.5, summarizer = the
# agent model; TR was dropped by the user on 2026-10-17 — add
# d05__b15k__tr:truncation:0.5 to CELLS to run it too).
#
# SERVER_LIFECYCLE=persistent (default per-run) keeps ONE server up for the
# whole plan instead of restarting it for every run; runs are still serial
# (MAX_WORKERS=1) and containers are still purged after every run. This is the
# "shared live server, no concurrency" contrast to the per-run rows and goes to
# its own model dir (devstral2507-serial; -serial-nocache with PREFIX_CACHE=off).
# With caching ON, run k of a task hits the prefix blocks run k-1 left behind.
# KV_FLUSH=prefix-cache (with persistent) keeps the one server but POSTs
# /reset_prefix_cache after every run, so each run starts from an empty prefix
# cache (self-hits within the run remain); the server is then started with
# VLLM_SERVER_DEV_MODE=1, which exposes that endpoint. Dest devstral2507-serial-flush.
#
# Same recipe as the 20-task cells otherwise: agent config
# configs/config-devstral2507-vllm.yaml (temperature 0, max_tokens 4096, step
# limit 300), model tag devstral-small-2507, runner defaults (agent timeout
# 5400 s), eval after every run. Prefix caching ON by default (the probe in
# Active_runs.md: ON with no hit is bit-identical to OFF, and with a fresh
# server per run the only hits are the run's own prefixes); PREFIX_CACHE=off
# serves caching OFF into a separate model dir.
#
# Output: data/r2/swebench/p30s/devstral2507-iso/<cell>/ (PREFIX_CACHE=off:
# devstral2507-iso-nocache; SERVER_LIFECYCLE=persistent: devstral2507-serial /
# devstral2507-serial-nocache). The section stays p30s because the 6 tasks are a
# subset of P30S; the model dir keeps these rows apart from the 8-worker
# devstral2507 cells.
#
# This script only fixes the defaults below and hands over to
# scripts/expansions/run_r2_swe_sandbox_isolated.sh with INNER=p30s, which owns
# the server and container lifecycle (start scripts/serving/start_vllm_devstral2507_sandbox.sh,
# wait, run scripts/expansions/run_r2_swe_p30s.sh on a one-task list with
# RUNS_PER_TASK=<run number> and MAX_WORKERS=1, stop the server, remove every
# container), the guards, resume (recorded keys are skipped) and DRY_RUN.
# Order: CYCLE_ORDER=run-major (run 1 of all 6 tasks, then run 2, ...) within
# each cell, so an early stop still leaves every task with the same run count.
#   CELLS, TASKS_FILE, N_TASKS, RUNS_PER_TASK, R2_MODEL, CYCLE_ORDER, RUN_EVAL,
#   PREFIX_CACHE (on|off), SERVER_LIFECYCLE (per-run|persistent), KV_FLUSH (none|prefix-cache), QWEN_AGENT_CONFIG,
#   QWEN_TAG, PURGE_CONTAINERS, DRY_RUN=1
# override by env. A Devstral server already running from the sandbox start
# script with the same PREFIX_CACHE setting (its pid file) is stopped by the
# driver's initial clean-up; any other server on :8000 must be stopped by hand.
#
# Usage (Albus; the driver starts and stops the server itself, do not start one):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh
#   SERVER_LIFECYCLE=persistent AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh
#   CELLS="di__b15k__su-free:summarization-free:0.5 d05__b15k__tr:truncation:0.5" ...   (TR as well)
#   KV_FLUSH=prefix-cache SERVER_LIFECYCLE=persistent TASKS_FILE=$PWD/task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json \
#       AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial-flush \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh      (one task, flushed persistent server)
# Cost (measured 2026-10-17/18, per-run servers, SU-free, 59 cycles): 8.7 min per
# cycle = 5.8 min agent e2e (median 3.5, max 29) + ~60 s server start + eval and
# purge; 8 h 35 min for the cell. Persistent server: ~7 h.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
source "$SCRIPT_DIR/../lib/logpaths.sh"

export PREFIX_CACHE="${PREFIX_CACHE:-on}"
export SERVER_LIFECYCLE="${SERVER_LIFECYCLE:-per-run}"
export KV_FLUSH="${KV_FLUSH:-none}"
case "$SERVER_LIFECYCLE" in
    per-run)    default_model=devstral2507-iso ;;
    persistent) default_model=devstral2507-serial ;;
    *) echo "[ERROR] SERVER_LIFECYCLE must be per-run | persistent (got '$SERVER_LIFECYCLE')" >&2; exit 1 ;;
esac
case "$KV_FLUSH" in
    none) ;;
    prefix-cache) default_model="$default_model-flush"; export VLLM_SERVER_DEV_MODE=1 ;;   # exposes /reset_prefix_cache
    *) echo "[ERROR] KV_FLUSH must be none | prefix-cache (got '$KV_FLUSH')" >&2; exit 1 ;;
esac
case "$PREFIX_CACHE" in
    on)  pid_name=vllm_devstral2507_prefixcache ;;
    off) pid_name=vllm_devstral2507_noprefixcache; default_model="$default_model-nocache" ;;
    *) echo "[ERROR] PREFIX_CACHE must be on | off (got '$PREFIX_CACHE')" >&2; exit 1 ;;
esac

export INNER=p30s
export SECTIONS="${SECTIONS:-p30s}"
export CELLS="${CELLS:-di__b15k__su-free:summarization-free:0.5}"
export TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/sandbox_devstral2507_sufree3_never3.json}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-10}"
export R2_MODEL="${R2_MODEL:-$default_model}"
export CYCLE_ORDER="${CYCLE_ORDER:-run-major}"
export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-devstral2507-vllm.yaml}"
export QWEN_TAG="${QWEN_TAG:-devstral-small-2507}"
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
export VLLM_START_SCRIPT="${VLLM_START_SCRIPT:-$SCRIPT_DIR/../serving/start_vllm_devstral2507_sandbox.sh}"
export VLLM_PID_FILE="${VLLM_PID_FILE:-$SERVER_LOG_DIR/$pid_name.pid}"
exec bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated.sh"
