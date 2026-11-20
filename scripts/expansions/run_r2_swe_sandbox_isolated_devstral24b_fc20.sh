#!/usr/bin/env bash
# Devstral-Small-2-24B-Instruct-2512 isolated cells on the 20 P100 tasks it
# resolved in 3/3 (10) or exactly 2/3 (10) of the ICLR full-context runs
# (task_lists/swe_verified/p100_devstral24b_fc_3of3_10_2of3_10.json; 15 of
# them are P30S members, 5 are in P100 \ P30S).
#
# One invocation of the isolated driver (scripts/expansions/run_r2_swe_sandbox_isolated.sh,
# INNER=p30s, SERVER_LIFECYCLE=per-run: a fresh vLLM server and container
# generation for every run, MAX_WORKERS=1, eval after every run, every container
# of this user's podman removed after every run). Cells by preset (first argument):
#   ocs      (default)  di__binf__ocs       online-claude-select: the selector picks
#                                           which original messages / output lines of
#                                           the complete history to keep; selector =
#                                           an OpenRouter model (see below)
#   ocsa                di__binf__ocsa      online-claude-select-anchored (added 2026-10-27):
#                                           the same selector, but every history message is
#                                           tagged with whether it was in the agent's context
#                                           at the previous step and the selector starts from
#                                           that selection, and the selected history must fit
#                                           30000 tokens (over-budget replies are corrected and
#                                           re-queried; src/agentctx/experiments/conditions.py).
#                                           Answer to the plain cell's step-to-step volatility
#                                           and its 65k-context overflows. Not part of `all`;
#                                           run it with the preset or add it to CELLS.
#   su-free             di__b21k__su-free   length-free summarization at Devstral's
#                                           primary ICLR budget 21k, summarizer = the
#                                           agent model
#   fc                  di__binf__fc        full context (no compression)
#   all                 ocs su-free fc      (in that order; CELLS overrides any preset)
# Default scope is the SMOKE CHECK the list was built for: the first task only
# (N_TASKS=1, django__django-14915) with one run (RUNS_PER_TASK=1). The full
# campaign is the same script with N_TASKS=all RUNS_PER_TASK=3 (and a preset).
# Keys are <task>__<condition>__r<n>; recorded keys are skipped, so rerunning
# resumes, and the smoke run is reused by the full campaign (same cell dir).
#
# Task set (TASK_SET, added 2026-11-07): `fc20` (default) = the 25-task list
# above. The `ocsi10` / `ocst4` presets went with the ocsi / ocst cells (removed
# 2026-11-19); their lists stay in task_lists/swe_verified/ and can be run via
# TASKS_FILE, which overrides any set.
#
# Selector (ocs): MSWEA_EXTRACT_PROVIDER=openrouter with the free Nemotron 3 Ultra
# (MSWEA_EXTRACT_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free; effort medium,
# MSWEA_EXTRACT_MAX_TOKENS 6000 and MSWEA_EXTRACT_PREFILL=1, chosen after the
# 2026-10-26 smoke run: at effort low the model answered the second call as the
# agent (THOUGHT + command + fabricated observations) up to the 16000-token cap,
# 150 s per attempt; with the reply prefilled at the "[CONTEXT SELECTION]" line it
# answers with directives at every effort, and a 6000-token cap (reasoning
# included; a 150-message selection with its drop lines ran past 3000) makes a
# stray reply fail in under a minute; temperature 0 = the openrouter default of
# MSWEA_EXTRACT_TEMPERATURE, so the selector is greedy like the agent; all
# overridable; MSWEA_EXTRACT_KEEP_RECENT=3 keeps the 2 newest turns verbatim,
# see below; MSWEA_EXTRACT_PROVIDER=anthropic switches back to Claude and
# takes no prefill). Needs
# OPENROUTER_API_KEY or ~/.config/agentctx/openrouter_api_key (chmod 600). The
# :free variants are capped per OpenRouter account at 20 requests/min and
# 1000/day (50/day before 10 credits have been bought); the selector is called
# once per agent step, so a run is ~70 calls at the median and up to ~300 at the
# 300-step limit, and a run that hits the cap dies after
# MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS (3) failed selector calls. With a :free
# selector the driver's quota gate is therefore ON by default
# (OPENROUTER_QUOTA_GATE=1): an OCS key starts only while the account has
# >= OPENROUTER_MIN_REMAINING (320) free-model requests left in the current UTC
# day (GET /api/v1/key); otherwise it is deferred while the su-free / fc keys of
# the plan run, and when only deferred keys remain the driver sleeps until the
# reset at 00:00 UTC (19:00 CDT / 18:00 CST) + 5 min. ~680 OCS calls per day
# -> ~9-10 median-length OCS runs per day; the full OCS cell (20 x 3) takes
# ~6-7 days, the other cells fill the GPU time in between.
#
# Server: scripts/serving/start_vllm_devstral.sh (ICLR serving: port 8002, 65536
# context, 64 seqs, prefix caching ON, KV trace) on ALL 8 GPUs with TP=8
# (DEVSTRAL_CUDA_VISIBLE_DEVICES=0-7, DEVSTRAL_TENSOR_PARALLEL_SIZE=8; the user's
# choice 2026-10-26 so that nothing else can share the machine while a run is
# up and one kill clears every GPU. The ICLR and fcmaj4 Devstral cells were
# served with TP=4 on GPUs 4-7; TP changes the reduction order, so greedy
# outputs are not bit-comparable with those runs. Set both variables to 4,5,6,7
# / 4 for the ICLR serving layout), pid file logs/servers/vllm_devstral.pid. The driver starts and stops it per run: do not
# start one. Agent config configs/config-devstral-vllm-temp0.yaml (ICLR
# config-devstral-vllm.yaml with temperature 0; step limit 300, max_tokens 4096).
# The agent system prompt is the benchmark default in every cell.
# Dest: data/r2/swebench/p30s/devstral24b-iso-fc20/<cell>/ (R2_MODEL overrides).
# NOTE: "p30s" is only the section directory the isolated driver accepts
# (p30s | p100_minus_p30s); the cohort is the 20-task list above, 5 of whose
# tasks are outside P30S. The R2_MODEL dir keeps these rows apart from every
# real P30S cell.
#
# Overrides: CELLS, N_TASKS, RUNS_PER_TASK, TASK_SET, TASKS_FILE, R2_MODEL, QWEN_AGENT_CONFIG,
# CYCLE_ORDER (run-major default: within each cell run 1 of every task, then run 2, then
# run 3, so every task has one run early; task-major = all runs of task 1 first), RUN_EVAL,
# AGENT_TIMEOUT (14400 s default, see below) / STEP_LIMIT, DEVSTRAL_CUDA_VISIBLE_DEVICES /
# DEVSTRAL_TENSOR_PARALLEL_SIZE,
# MSWEA_EXTRACT_{PROVIDER,MODEL,EFFORT,EVERY,KEEP_RECENT}, OPENROUTER_QUOTA_GATE /
# OPENROUTER_MIN_REMAINING, and the driver's VLLM_* / DOCKER_* / PURGE_CONTAINERS /
# BUSY_PATTERN.
#
# Usage (Albus; the rootless podman socket must be up, no other r2 launcher running):
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh
#   venv/bin/python scripts/maintenance/probe_claude_select.py          # selector smoke test first
#   SLACK_WEBHOOK_URL="$(cat ~/.config/agentctx/slack_webhook)" bash scripts/notify_run.sh \
#       --unit r2/swebench/sandbox_isolated/p30s-devstral24b-iso-fc20 \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh
#   Full campaign:  N_TASKS=all RUNS_PER_TASK=3 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh all
# Cost: per cycle ~2-3 min server start + the run + ~1-2 min eval and purge;
# ICLR FC runs on these tasks took 3-25 min at 16 workers. OCS adds one selector
# call per step (free model: no credits, but latency of several seconds each).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
source "$SCRIPT_DIR/../lib/logpaths.sh"

PRESET="${1:-ocs}"
CELL_OCS="di__binf__ocs:online-claude-select:0.5"
CELL_OCSA="di__binf__ocsa:online-claude-select-anchored:0.5"
CELL_SUFREE="di__b21k__su-free:summarization-free:0.5"
CELL_FC="di__binf__fc:full-context:0.5"
case "$PRESET" in
    ocs)     default_cells="$CELL_OCS" ;;
    ocsa)    default_cells="$CELL_OCSA" ;;
    su-free) default_cells="$CELL_SUFREE" ;;
    fc)      default_cells="$CELL_FC" ;;
    all)     default_cells="$CELL_OCS $CELL_SUFREE $CELL_FC" ;;
    *) echo "[ERROR] preset must be ocs | ocsa | su-free | fc | all (got '$PRESET'); or set CELLS" >&2; exit 1 ;;
esac
export CELLS="${CELLS:-$default_cells}"
export N_TASKS="${N_TASKS:-1}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-1}"

export INNER=p30s
export SECTIONS=p30s
export SERVER_LIFECYCLE="${SERVER_LIFECYCLE:-per-run}"
export CYCLE_ORDER="${CYCLE_ORDER:-run-major}"      # run 1 of every task, then run 2, ... (per cell)
TASK_SET="${TASK_SET:-fc20}"
case "$TASK_SET" in
    fc20)   default_tasks="$WS/task_lists/swe_verified/p100_devstral24b_fc_3of3_10_2of3_10.json" ;;
    *) echo "[ERROR] TASK_SET must be fc20 (got '$TASK_SET'); or set TASKS_FILE" >&2; exit 1 ;;
esac
export TASKS_FILE="${TASKS_FILE:-$default_tasks}"
export R2_MODEL="${R2_MODEL:-devstral24b-iso-fc20}"
export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-devstral-vllm-temp0.yaml}"
export QWEN_TAG="${QWEN_TAG:-devstral-2}"             # the ICLR Devstral-24B model tag
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8002/v1/models}"
export DEVSTRAL_CUDA_VISIBLE_DEVICES="${DEVSTRAL_CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
export DEVSTRAL_TENSOR_PARALLEL_SIZE="${DEVSTRAL_TENSOR_PARALLEL_SIZE:-8}"
export VLLM_START_SCRIPT="${VLLM_START_SCRIPT:-$SCRIPT_DIR/../serving/start_vllm_devstral.sh}"
export VLLM_PID_FILE="${VLLM_PID_FILE:-$SERVER_LOG_DIR/vllm_devstral.pid}"

# Selector settings for the OCS cell (exported so the driver -> p30s launcher ->
# runner -> agent subprocess chain inherits them).
export MSWEA_EXTRACT_PROVIDER="${MSWEA_EXTRACT_PROVIDER:-openrouter}"
if [[ "$MSWEA_EXTRACT_PROVIDER" == openrouter ]]; then
    export MSWEA_EXTRACT_MODEL="${MSWEA_EXTRACT_MODEL:-nvidia/nemotron-3-ultra-550b-a55b:free}"
fi
# Selector defaults by model (2026-10-27 probes on real histories):
#   nvidia/nemotron-*  effort medium, max_tokens 6000, PREFILL=1 (without the prefill it
#                      answered as the agent from the second call on; with it 10/10 first-try)
#   anything else      effort low, max_tokens 12000, PREFILL=0 (DeepSeek V4.1 Flash 1017
#                      with a prefill returned safety-classifier preambles, empty bodies
#                      and stray tags, 4 of 5 probes rejected; without it 1st-try accepts,
#                      and its reasoning at effort low can exceed 6000 tokens)
if [[ "${MSWEA_EXTRACT_MODEL:-}" == nvidia/nemotron* ]]; then
    export MSWEA_EXTRACT_EFFORT="${MSWEA_EXTRACT_EFFORT:-medium}"
    export MSWEA_EXTRACT_MAX_TOKENS="${MSWEA_EXTRACT_MAX_TOKENS:-6000}"
    [[ "$MSWEA_EXTRACT_PROVIDER" != openrouter ]] || export MSWEA_EXTRACT_PREFILL="${MSWEA_EXTRACT_PREFILL:-1}"
else
    export MSWEA_EXTRACT_EFFORT="${MSWEA_EXTRACT_EFFORT:-low}"
    export MSWEA_EXTRACT_MAX_TOKENS="${MSWEA_EXTRACT_MAX_TOKENS:-12000}"
    [[ "$MSWEA_EXTRACT_PROVIDER" != openrouter ]] || export MSWEA_EXTRACT_PREFILL="${MSWEA_EXTRACT_PREFILL:-0}"
fi
# The newest 3 messages stay verbatim, widened to the turn that opened them =
# the 2 newest turns (the primitive default 1 keeps 1 turn; 2 would be the same
# as 1). The user's choice 2026-10-26 after the smoke run, where 21 of 101
# selections kept under 15% of the history and the agent then re-read the
# lines it had just displayed. Recorded per event as keep_recent in
# compression_events.jsonl; the cell name does not carry it.
export MSWEA_EXTRACT_KEEP_RECENT="${MSWEA_EXTRACT_KEEP_RECENT:-3}"
# Per-run wall-clock timeout for every cell (runner default 5400 s): OCS steps
# cost 13-42 s here (selector call + a context rebuilt every step, so no vLLM
# prefix-cache hits) against ~3 s under FC, and sympy-15345's OCS run was cut
# at 90 min on step 129 while finishing; no FC / SU-free run of this campaign
# came within 100 s of 5400 s, so 4 h changes nothing for them. The 300-step
# limit stays the binding cap. The user's choice 2026-10-27.
export AGENT_TIMEOUT="${AGENT_TIMEOUT:-14400}"
# Free-model quota gate (driver, see the header): on by default for a :free selector.
if [[ "$MSWEA_EXTRACT_PROVIDER" == openrouter && "${MSWEA_EXTRACT_MODEL:-}" == *:free ]]; then
    export OPENROUTER_QUOTA_GATE="${OPENROUTER_QUOTA_GATE:-1}"
    # Start a selector run only with this many free-model requests left in the
    # UTC day. Lowered from the driver's 320 to 200 (the user's choice 2026-10-27):
    # the six campaign runs so far used 52-149 calls; with the 4 h timeout a run
    # can reach the 300-step limit, and such a run started with ~200 left dies at
    # the cap (3 consecutive selector errors) and is rerun on resume.
    export OPENROUTER_MIN_REMAINING="${OPENROUTER_MIN_REMAINING:-200}"
else
    export OPENROUTER_QUOTA_GATE="${OPENROUTER_QUOTA_GATE:-0}"
fi
# Paid-credit gate (driver, see the header): on by default for a paid OpenRouter
# selector; a key starts only while >= OPENROUTER_MIN_CREDITS USD can still be spent
# (account credits and the key's own limit). Added 2026-10-31 after 9 runs died
# mid-run on 402 (credits) / 403 (key limit).
if [[ "$MSWEA_EXTRACT_PROVIDER" == openrouter && "${MSWEA_EXTRACT_MODEL:-}" != *:free ]]; then
    export OPENROUTER_CREDIT_GATE="${OPENROUTER_CREDIT_GATE:-1}"
    export OPENROUTER_MIN_CREDITS="${OPENROUTER_MIN_CREDITS:-10}"
else
    export OPENROUTER_CREDIT_GATE="${OPENROUTER_CREDIT_GATE:-0}"
fi

[[ -f "$TASKS_FILE" ]] || { echo "[ERROR] task list not found: $TASKS_FILE" >&2; exit 1; }
[[ -f "$QWEN_AGENT_CONFIG" ]] || { echo "[ERROR] agent config not found: $QWEN_AGENT_CONFIG" >&2; exit 1; }
if ss -ltn 2>/dev/null | grep -q ':8002 '; then
    echo "[ERROR] port 8002 is already in use (the Devstral server start would abort every cycle):" >&2
    ss -ltnp 2>/dev/null | grep ':8002 ' >&2; exit 1
fi

# The OCS cell calls the selector from inside every agent run: check the key
# before the first server start rather than minutes in. Skipped for DRY_RUN=1
# (the plan can be printed on a machine without the key).
# The selector model's key is needed by every online-claude-select cell.
needs_extractor=0
for cell in $CELLS; do
    case "$cell" in
        *:online-claude-*)      needs_extractor=1 ;;
    esac
done
if [[ "$needs_extractor" == 1 && "${DRY_RUN:-0}" != 1 ]]; then
    if [[ "$MSWEA_EXTRACT_PROVIDER" == openrouter ]]; then
        key_file="${AGENTCTX_OPENROUTER_API_KEY_FILE:-$HOME/.config/agentctx/openrouter_api_key}"
        if [[ -z "${OPENROUTER_API_KEY:-}" && ! -s "$key_file" ]]; then
            echo "[ERROR] MSWEA_EXTRACT_PROVIDER=openrouter needs OPENROUTER_API_KEY or $key_file (chmod 600)." >&2
            echo "        check with: MSWEA_EXTRACT_PROVIDER=openrouter MSWEA_EXTRACT_MODEL=$MSWEA_EXTRACT_MODEL venv/bin/python scripts/maintenance/probe_claude_select.py" >&2
            exit 1
        fi
    else
        key_file="${AGENTCTX_ANTHROPIC_API_KEY_FILE:-$HOME/.config/agentctx/anthropic_api_key}"
        if [[ -z "${ANTHROPIC_API_KEY:-}" && ! -s "$key_file" ]]; then
            echo "[ERROR] the OCS cell needs an Anthropic key: export ANTHROPIC_API_KEY or write it to $key_file (chmod 600);" >&2
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
    echo "[$(date)] devstral24b-fc20: log: $LOG_FILE"
fi

echo "[$(date)] devstral24b-fc20: preset=$PRESET CELLS=\"$CELLS\" task_set=$TASK_SET tasks=$TASKS_FILE N_TASKS=$N_TASKS RUNS_PER_TASK=$RUNS_PER_TASK | selector: provider=$MSWEA_EXTRACT_PROVIDER model=${MSWEA_EXTRACT_MODEL:-<provider default>} effort=$MSWEA_EXTRACT_EFFORT${MSWEA_EXTRACT_EVERY:+ every=$MSWEA_EXTRACT_EVERY}${MSWEA_EXTRACT_KEEP_RECENT:+ keep_recent=$MSWEA_EXTRACT_KEEP_RECENT} max_tokens=$MSWEA_EXTRACT_MAX_TOKENS prefill=${MSWEA_EXTRACT_PREFILL:-0} | agent_timeout=${AGENT_TIMEOUT}s | quota gate=$OPENROUTER_QUOTA_GATE | credit gate=$OPENROUTER_CREDIT_GATE${OPENROUTER_CREDIT_GATE:+ (min \$${OPENROUTER_MIN_CREDITS:-})} | GPUs $DEVSTRAL_CUDA_VISIBLE_DEVICES TP=$DEVSTRAL_TENSOR_PARALLEL_SIZE"
bash "$SCRIPT_DIR/run_r2_swe_sandbox_isolated.sh"
echo "[$(date)] devstral24b-fc20: done"
