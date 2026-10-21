#!/usr/bin/env bash
# Devstral-Small-2507 sandbox cells on the first 20 P30S tasks: SU-free and TR,
# 3 runs/task, against the prefix-caching-ON Devstral server on port 8000.
#
# A thin wrapper over scripts/expansions/run_r2_swe_p30s.sh (same runner, same
# section, same cell names as the Qwen P30S cells), with these defaults:
#   R2_MODEL          devstral2507      -> data/r2/swebench/p30s/devstral2507/<cell>/
#   QWEN_AGENT_CONFIG configs/config-devstral2507-vllm.yaml (port 8000, max_tokens
#                     4096, timeout 600, temperature 0; agent = summarizer)
#   QWEN_TAG          devstral-small-2507 (SWE-bench eval model_name_or_path)
#   N_TASKS           20 (first 20 of task_lists/swe_verified/p30_stratified.json)
#   RUNS_PER_TASK     3
#   CELLS             di__b15k__su-free:summarization-free:0.5 d05__b15k__tr:truncation:0.5
#                     (SU-free first, then TR; 15k budget = the P30S section budget)
#   MAX_WORKERS       from AGENTCTX_PROFILE (albus-swe: 8)
# Every one of them can still be overridden by env, e.g. CELLS="d05__b15k__tr:truncation:0.5".
#
# Before starting it checks that the server on port 8000 serves
# mistralai/Devstral-Small-2507 and that its /metrics report prefix caching in
# the state REQUIRE_PREFIX_CACHE asks for (default on; off | any). Caching ON is
# the deliberate choice for this model: the probe of 2026-10-17
# (scripts/maintenance/probe_prefix_cache_effect.py, data/r2/probes/
# prefix_cache_effect_devstral2507/) showed the caching-ON engine with no cache
# hit is bit-identical to caching OFF, and cache hits perturb the numerics no
# more than a server restart does.
#
# Server:  AGENTCTX_PROFILE=albus-swe PREFIX_CACHE=on bash scripts/serving/start_vllm_devstral2507_sandbox.sh
# Launch:  AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh \
#              --unit r2/swebench/p30s/devstral2507 \
#              -- bash scripts/expansions/run_r2_swe_p30s_devstral2507.sh
# Log:     logs/experiments/r2_swebench_p30s_devstral2507_<timestamp>.log (notify_run)
#          and logs/experiments/r2_sb_p30s_devstral2507_<timestamp>.log (launcher)
# Est.:    ~2.5 h SU-free + ~2 h TR incl. eval at 8 workers (60 runs each).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

export R2_SECTION="${R2_SECTION:-p30s}"
export R2_MODEL="${R2_MODEL:-devstral2507}"
export QWEN_AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-devstral2507-vllm.yaml}"
export QWEN_TAG="${QWEN_TAG:-devstral-small-2507}"
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
export N_TASKS="${N_TASKS:-20}"
export RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
export CELLS="${CELLS:-di__b15k__su-free:summarization-free:0.5 d05__b15k__tr:truncation:0.5}"
EXPECTED_MODEL="${EXPECTED_MODEL:-mistralai/Devstral-Small-2507}"
REQUIRE_PREFIX_CACHE="${REQUIRE_PREFIX_CACHE:-on}"

served="$(curl -fsS --max-time 5 "$QWEN_HEALTH_URL" | "$WS/venv/bin/python3" -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null || true)"
if [[ "$served" != "$EXPECTED_MODEL" ]]; then
    echo "[ERROR] expected $EXPECTED_MODEL on $QWEN_HEALTH_URL, got '${served:-no answer}'." >&2
    echo "        Start it with: AGENTCTX_PROFILE=albus-swe PREFIX_CACHE=on bash scripts/serving/start_vllm_devstral2507_sandbox.sh" >&2
    exit 1
fi
metrics_url="${QWEN_HEALTH_URL%/v1/models}/metrics"
cache_flag="$(curl -fsS --max-time 10 "$metrics_url" | grep -o 'enable_prefix_caching="[A-Za-z]*"' | head -1 || true)"
case "$REQUIRE_PREFIX_CACHE" in
    on)  [[ "$cache_flag" == 'enable_prefix_caching="True"' ]]  || { echo "[ERROR] server reports $cache_flag; this launcher wants prefix caching ON (REQUIRE_PREFIX_CACHE=off|any overrides)" >&2; exit 1; } ;;
    off) [[ "$cache_flag" == 'enable_prefix_caching="False"' ]] || { echo "[ERROR] server reports $cache_flag; REQUIRE_PREFIX_CACHE=off wants it OFF" >&2; exit 1; } ;;
    any) ;;
    *) echo "[ERROR] REQUIRE_PREFIX_CACHE must be on | off | any" >&2; exit 1 ;;
esac
echo "[$(date)] server $served, $cache_flag; dest data/r2/swebench/$R2_SECTION/$R2_MODEL, first $N_TASKS tasks x $RUNS_PER_TASK runs, cells: $CELLS"

# The preset argument is irrelevant once CELLS is set; "free" keeps the parent's
# argument check happy.
exec bash "$SCRIPT_DIR/run_r2_swe_p30s.sh" free
