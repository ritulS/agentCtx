#!/usr/bin/env bash
# Devstral-Small-2-24B-Instruct-2512 isolated cells on the 4 P30S tasks that
# qwen35b resolved in >=2 of 3 full-context runs but in only 1 of 3 SU-free runs
# (task_lists/swe_verified/p30s_qwen35b_fc_majority_su-free_minority.json:
# django-12304, sklearn-25232, sympy-14531, sympy-18211).
#
# Two phases, each one invocation of the isolated driver
# (scripts/expansions/run_r2_swe_sandbox_isolated.sh, INNER=p30s,
# SERVER_LIFECYCLE=per-run: a fresh vLLM server and container generation per
# run, MAX_WORKERS=1), run-major inside each cell, cells in CELLS order:
#   phase A  RUNS_PER_TASK=2   di__binf__fc        full-context (no compression)
#                              d05__b21k__su-full  summarization at Devstral's primary
#                                                  budget 21k (ICLR calibration),
#                                                  summarizer = the agent model
#   phase B  RUNS_PER_TASK=1   di__binf__ocs       online-claude-select (Claude picks
#                                                  which original messages / output
#                                                  lines of the complete history to
#                                                  keep; needs ANTHROPIC_API_KEY or
#                                                  ~/.config/agentctx/anthropic_api_key)
# = 8 + 8 + 4 = 20 cycles. Keys are <task>__<condition>__r<n>; recorded keys are
# skipped, so rerunning resumes (phase A is skipped entirely once complete).
#
# Server: scripts/serving/start_vllm_devstral.sh (the ICLR serving command:
# port 8002, TP=4, 65536 context, 64 seqs, prefix caching ON, KV trace), on GPUs
# 0-3 here (DEVSTRAL_CUDA_VISIBLE_DEVICES; the script's default 4-7 is Albus's),
# pid file logs/servers/vllm_devstral.pid. The driver starts and stops it per
# cycle: do not start one. Agent config configs/config-devstral-vllm-temp0.yaml
# (config-devstral-vllm.yaml with temperature 0; step limit 300, max_tokens 4096).
# The agent system prompt is the benchmark default in every cell (the OCS
# condition carries no prompt delta).
# Dest: data/r2/swebench/p30s/devstral24b-iso-fcmaj4/<cell>/ (R2_MODEL overrides).
# Eval after every run, every container of this user's podman removed after
# every run (PURGE_CONTAINERS=all).
#
# Overrides: PHASES ("A B", default both), CELLS_A / RUNS_A, CELLS_B / RUNS_B,
# TASKS_FILE, R2_MODEL, QWEN_AGENT_CONFIG, CYCLE_ORDER, RUN_EVAL,
# DEVSTRAL_CUDA_VISIBLE_DEVICES, and the driver's VLLM_* / DOCKER_* /
# PURGE_CONTAINERS / BUSY_PATTERN.
#
# Usage (Dobby; the rootless podman socket must be up, no other r2 launcher running):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fcmaj4.sh
#   SLACK_WEBHOOK_URL="$(cat ~/.config/agentctx/slack_webhook)" bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral24b-iso-fcmaj4 \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fcmaj4.sh
#   Phase B only:  PHASES=B bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fcmaj4.sh
# Cost (estimate 2026-10-25): ICLR FC / SU-full runs on these tasks took 3-10 min
# at 16 workers (sympy-14531 FC r1: 25 min); alone, plus ~2-3 min server start
# and ~1-2 min eval + purge per cycle -> phase A ~1.5-3 h; phase B adds one
# Claude call per agent step (~4 s) -> ~10-30 min per run, ~1-2 h; total ~3-5 h.
# Claude usage for phase B: ~$1.5-5 per run at cache-read rates, up to ~$15 for
# a run that reaches the 300-step limit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
source "$SCRIPT_DIR/../lib/logpaths.sh"

PHASES="${PHASES:-A B}"
CELLS_A="${CELLS_A:-di__binf__fc:full-context:0.5 d05__b21k__su-full:summarization:0.5}"
RUNS_A="${RUNS_A:-2}"
CELLS_B="${CELLS_B:-di__binf__ocs:online-claude-select:0.5}"
RUNS_B="${RUNS_B:-1}"

export INNER=p30s
export SECTIONS=p30s
export SERVER_LIFECYCLE="${SERVER_LIFECYCLE:-per-run}"
export CYCLE_ORDER="${CYCLE_ORDER:-run-major}"
export TASKS_FILE="${TASKS_FILE:-$WS/task_lists/swe_verified/p30s_qwen35b_fc_majority_su-free_minority.json}"
export R2_MODEL="${R2_MODEL:-devstral24b-iso-fcmaj4}"
export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-devstral-vllm-temp0.yaml}"
export QWEN_TAG="${QWEN_TAG:-devstral-2}"             # the ICLR Devstral-24B model tag
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8002/v1/models}"
export DEVSTRAL_CUDA_VISIBLE_DEVICES="${DEVSTRAL_CUDA_VISIBLE_DEVICES:-0,1,2,3}"
export VLLM_START_SCRIPT="${VLLM_START_SCRIPT:-$SCRIPT_DIR/../serving/start_vllm_devstral.sh}"
export VLLM_PID_FILE="${VLLM_PID_FILE:-$SERVER_LOG_DIR/vllm_devstral.pid}"

[[ -f "$TASKS_FILE" ]] || { echo "[ERROR] task list not found: $TASKS_FILE" >&2; exit 1; }
[[ -f "$QWEN_AGENT_CONFIG" ]] || { echo "[ERROR] agent config not found: $QWEN_AGENT_CONFIG" >&2; exit 1; }
if ss -ltn 2>/dev/null | grep -q ':8002 '; then
    echo "[ERROR] port 8002 is already in use (the Devstral server start would abort every cycle):" >&2
    ss -ltnp 2>/dev/null | grep ':8002 ' >&2; exit 1
fi
# Phase B calls Claude from inside every agent run; fail before phase A rather than hours in.
# MSWEA_EXTRACT_PROVIDER=openrouter (with MSWEA_EXTRACT_MODEL=<vendor/model>) routes the
# same selector prompts through OpenRouter; only the key lookup differs here.
if [[ " $PHASES " == *" B "* ]] && [[ " $CELLS_B " == *":online-claude-"* ]]; then
    if [[ "${MSWEA_EXTRACT_PROVIDER:-anthropic}" == "openrouter" ]]; then
        key_file="${AGENTCTX_OPENROUTER_API_KEY_FILE:-$HOME/.config/agentctx/openrouter_api_key}"
        if [[ -z "${OPENROUTER_API_KEY:-}" && ! -s "$key_file" ]]; then
            echo "[ERROR] phase B with MSWEA_EXTRACT_PROVIDER=openrouter needs OPENROUTER_API_KEY or $key_file (chmod 600)." >&2
            exit 1
        fi
        if [[ -z "${MSWEA_EXTRACT_MODEL:-}" ]]; then
            echo "[ERROR] MSWEA_EXTRACT_PROVIDER=openrouter needs MSWEA_EXTRACT_MODEL=<vendor/model> (OpenRouter model id)." >&2
            exit 1
        fi
    else
        key_file="${AGENTCTX_ANTHROPIC_API_KEY_FILE:-$HOME/.config/agentctx/anthropic_api_key}"
        if [[ -z "${ANTHROPIC_API_KEY:-}" && ! -s "$key_file" ]]; then
            echo "[ERROR] phase B needs an Anthropic key: export ANTHROPIC_API_KEY or write it to $key_file (chmod 600);" >&2
            echo "        check with: venv/bin/python scripts/maintenance/probe_claude_select.py" >&2
            exit 1
        fi
    fi
fi

# Own the log unless an outer wrapper (notify_run.sh) already does; the driver
# then appends to it (AGENTCTX_LOG_FILE) instead of opening its own.
if [[ -z "${AGENTCTX_LOG_FILE:-}" ]]; then
    LOG_FILE="$(experiment_log "r2_sb_isolated_${R2_MODEL}")"
    export AGENTCTX_LOG_FILE="$LOG_FILE"
    exec > >(tee -a "$LOG_FILE") 2>&1
    echo "[$(date)] devstral24b-fcmaj4: log: $LOG_FILE"
fi

for phase in $PHASES; do
    case "$phase" in
        A) cells="$CELLS_A"; runs="$RUNS_A" ;;
        B) cells="$CELLS_B"; runs="$RUNS_B" ;;
        *) echo "[ERROR] PHASES entries must be A | B (got '$phase')" >&2; exit 1 ;;
    esac
    echo "[$(date)] devstral24b-fcmaj4: === phase $phase: CELLS=\"$cells\" RUNS_PER_TASK=$runs ==="
    CELLS="$cells" RUNS_PER_TASK="$runs" bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated.sh"
done
echo "[$(date)] devstral24b-fcmaj4: all phases done"
