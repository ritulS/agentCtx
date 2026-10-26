#!/usr/bin/env bash
# Qwen3.5-35B-A3B isolated cells on the 4 P30S tasks that qwen35b resolved in
# >=2 of 3 full-context runs but in only 1 of 3 SU-free runs in r2
# (task_lists/swe_verified/p30s_qwen35b_fc_majority_su-free_minority.json:
# django-12304, sklearn-25232, sympy-14531, sympy-18211; see task_lists/README.md).
#
# Three cells, 2 runs per task, one request at a time: a fresh vLLM server and
# container generation per run (scripts/expansions/run_r2_swe_sandbox_isolated.sh,
# INNER=p30s, SERVER_LIFECYCLE=per-run, MAX_WORKERS=1), prefix caching ON with a
# float32 SSM cache (--mamba-ssm-cache-dtype float32), temperature 0:
#   di__binf__fc       full-context           (no compression, unlimited budget)
#   di__binf__oce      online-claude-extract  (Claude rewrites the history after
#                      system + task before every agent call; no budget; needs
#                      ANTHROPIC_API_KEY or ~/.config/agentctx/anthropic_api_key;
#                      MSWEA_EXTRACT_MODEL / _EFFORT / _EVERY / _KEEP_RECENT pass
#                      through, defaults claude-opus-5-5 / medium)
#   di__b15k__su-free  summarization-free at 15k (summarizer = the agent model)
#   di__binf__ocs      online-claude-select   (optional, add to CELLS: Claude picks
#                      which original messages / output lines of the complete
#                      history to keep, ids + line ranges only; same key)
# Plan order: run-major inside each cell, cells in CELLS order -> 3 x (4 tasks x
# 2 runs) = 24 cycles. Keys are <task>__<condition>__r<n>; recorded keys are
# skipped, so rerunning with the same settings resumes.
#
# Server: scripts/serving/start_vllm_qwen35_ssm_probe.sh with PREFIX_CACHE=on
# and SSM_DTYPE=float32 (default here; SSM_DTYPE=auto = the bf16 production
# cache): the production engine arguments (dtype auto, 102400 context, 64 seqs,
# reasoning parser, KV trace) + --enable-prefix-caching
# --mamba-ssm-cache-dtype float32, moved to the agent port (QWEN_VLLM_PORT,
# default 8002: another user's service holds 8000 on Dobby since 2026-10-25) on
# GPUs 0-3, TP=4 (QWEN_CUDA_VISIBLE_DEVICES / QWEN_TENSOR_PARALLEL_SIZE override; the
# probe script has no AGENTCTX_PROFILE handling, so set them by hand on Albus).
# Why float32: with caching ON vLLM runs this hybrid model in Mamba cache mode
# "align", which round-trips the recurrent state through the SSM cache dtype at
# every block boundary; the probe of 2026-10-24 (Active_runs.md) showed a
# float32 SSM cache makes a prefix-cache hit lossless (cold = warm 40/40) where
# bf16 does not (block 1056 tokens instead of 528). Pid file
# logs/servers/vllm_qwen35_a3b_ssm<dtype>_prefixcache.pid. The driver starts
# and stops the server per cycle: do not start one.
# Agent config: configs/config-qwen-vllm-temp0-8002.yaml (config-qwen-vllm.yaml
# with temperature 0 and api_base on the server port; step limit 300, max_tokens
# 32768, thinking ON); configs/config-qwen-vllm-temp0.yaml when QWEN_VLLM_PORT=8000.
# Dest: data/r2/swebench/p30s/qwen35b-iso-fcmaj4-ssmfp32/<cell>/ (SSM_DTYPE=auto
# -> qwen35b-iso-fcmaj4; R2_MODEL overrides; keep it apart from the 16-worker
# reference dir qwen35b and keep ON/OFF + SSM dtype constant within a compared set).
# Eval after every run, every container of this user's podman removed after
# every run (PURGE_CONTAINERS=all), as in the Devstral isolated cells.
#
# Overrides: CELLS ("cell:condition:depth ..."), RUNS_PER_TASK, TASKS_FILE,
# R2_MODEL, SSM_DTYPE (float32 | auto), QWEN_VLLM_PORT, QWEN_AGENT_CONFIG, CYCLE_ORDER, RUN_EVAL,
# and the driver's VLLM_* / DOCKER_* / PURGE_CONTAINERS / BUSY_PATTERN.
#
# Usage (Dobby; needs the rootless podman socket up and no other r2 launcher running):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_qwen35b_fcmaj4.sh
#   SLACK_WEBHOOK_URL="$(cat ~/.config/agentctx/slack_webhook)" bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-qwen35b-iso-fcmaj4 \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_qwen35b_fcmaj4.sh
#   One cell only:  CELLS="di__binf__oce:online-claude-extract:0.5" bash scripts/expansions/run_r2_swe_sandbox_isolated_qwen35b_fcmaj4.sh
#   bf16 SSM cache: SSM_DTYPE=auto bash scripts/expansions/run_r2_swe_sandbox_isolated_qwen35b_fcmaj4.sh   (dest qwen35b-iso-fcmaj4)
#   Albus:          AGENTCTX_PROFILE=albus-swe QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 QWEN_TENSOR_PARALLEL_SIZE=8 bash scripts/notify_run.sh --unit ... -- bash ...
# Cost: 24 cycles x (server start ~3-5 min + agent run, r2 reference mean ~5 min
# per run on these tasks at 16 workers, less alone + eval and purge ~1-2 min)
# -> roughly 4-5 h; the OCE cell adds one Claude call per agent step.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
source "$SCRIPT_DIR/../lib/logpaths.sh"

export INNER=p30s
export SECTIONS=p30s
export SERVER_LIFECYCLE="${SERVER_LIFECYCLE:-per-run}"
export CYCLE_ORDER="${CYCLE_ORDER:-run-major}"
export CELLS="${CELLS:-di__binf__fc:full-context:0.5 di__binf__oce:online-claude-extract:0.5 di__b15k__su-free:summarization-free:0.5}"
export TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/p30s_qwen35b_fc_majority_su-free_minority.json}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-2}"
export SSM_DTYPE="${SSM_DTYPE:-float32}"
case "$SSM_DTYPE" in
    float32) default_model=qwen35b-iso-fcmaj4-ssmfp32 ;;
    auto)    default_model=qwen35b-iso-fcmaj4 ;;
    *) echo "[ERROR] SSM_DTYPE must be float32 | auto (got '$SSM_DTYPE')" >&2; exit 1 ;;
esac
export R2_MODEL="${R2_MODEL:-$default_model}"
# Port: 8002 by default since 2026-10-25 (another user's FastAPI service holds
# 127.0.0.1:8000 on Dobby; vLLM's port check aborts the start). The agent
# config must point at the same port: configs/config-qwen-vllm-temp0.yaml for
# 8000, configs/config-qwen-vllm-temp0-<port>.yaml otherwise (8002 exists).
export QWEN_VLLM_PORT="${QWEN_VLLM_PORT:-8002}"
[[ "$QWEN_VLLM_PORT" =~ ^[0-9]+$ ]] || { echo "[ERROR] QWEN_VLLM_PORT must be a port number (got '$QWEN_VLLM_PORT')" >&2; exit 1; }
if [[ "$QWEN_VLLM_PORT" == 8000 ]]; then default_cfg="$WS/configs/config-qwen-vllm-temp0.yaml"
else default_cfg="$WS/configs/config-qwen-vllm-temp0-$QWEN_VLLM_PORT.yaml"; fi
export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$default_cfg}"
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:$QWEN_VLLM_PORT/v1/models}"
# Caching ON + float32 SSM cache server in place of the driver's caching-OFF
# sandbox default: the probe server script, moved to the agent port / all 4 GPUs.
export PREFIX_CACHE=on
export QWEN_CUDA_VISIBLE_DEVICES="${QWEN_CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export QWEN_TENSOR_PARALLEL_SIZE="${QWEN_TENSOR_PARALLEL_SIZE:-4}"
export VLLM_START_SCRIPT="${VLLM_START_SCRIPT:-$SCRIPT_DIR/../serving/start_vllm_qwen35_ssm_probe.sh}"
export VLLM_PID_FILE="${VLLM_PID_FILE:-$SERVER_LOG_DIR/vllm_qwen35_a3b_ssm${SSM_DTYPE}_prefixcache.pid}"
[[ "${QWEN_HEALTH_URL}" == *":${QWEN_VLLM_PORT}/"* ]] || { echo "[ERROR] QWEN_HEALTH_URL ($QWEN_HEALTH_URL) does not use QWEN_VLLM_PORT ($QWEN_VLLM_PORT)" >&2; exit 1; }
if ss -ltn 2>/dev/null | grep -q ":${QWEN_VLLM_PORT} "; then
    echo "[ERROR] port $QWEN_VLLM_PORT is already in use (the server start would abort every cycle); pick another with QWEN_VLLM_PORT=<port> and a matching configs/config-qwen-vllm-temp0-<port>.yaml:" >&2
    ss -ltnp 2>/dev/null | grep ":${QWEN_VLLM_PORT} " >&2; exit 1
fi

[[ -f "$TASKS_FILE" ]] || { echo "[ERROR] task list not found: $TASKS_FILE" >&2; exit 1; }
[[ -f "$QWEN_AGENT_CONFIG" ]] || { echo "[ERROR] agent config not found: $QWEN_AGENT_CONFIG" >&2; exit 1; }

# The online-claude-extract cell calls Claude from inside every agent run; fail
# here rather than 24 cycles in. Same lookup as claude_extract.resolve_api_key.
if [[ " $CELLS " == *":online-claude-extract:"* || " $CELLS " == *":online-claude-select:"* ]]; then
    key_file="${AGENTCTX_ANTHROPIC_API_KEY_FILE:-$HOME/.config/agentctx/anthropic_api_key}"
    if [[ -z "${ANTHROPIC_API_KEY:-}" && ! -s "$key_file" ]]; then
        echo "[ERROR] CELLS includes online-claude-extract/-select but ANTHROPIC_API_KEY is unset and $key_file is missing/empty." >&2
        echo "        Put the key in that file (chmod 600) or export ANTHROPIC_API_KEY; check with:" >&2
        echo "        venv/bin/python scripts/maintenance/probe_claude_extract.py" >&2
        exit 1
    fi
fi

exec bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated.sh"
