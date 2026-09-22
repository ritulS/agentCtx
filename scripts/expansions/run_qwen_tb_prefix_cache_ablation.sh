#!/usr/bin/env bash
# Prefix-caching ablation on Terminal-Bench (dashboard 5.b): rerun the
# Qwen3.5-35B-A3B primitives against a vLLM server started WITHOUT prefix caching.
#
# The production Qwen runs (ICLR_results/terminalbench/{main,ablation}/qwen35b)
# were served with prefix caching on (scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh passes
# --enable-prefix-caching; logs/vllm_qwen35.log: enable_prefix_caching=True).
# This launcher repeats the 3K / canonical-depth grid and the unlimited-budget
# baselines with caching off, everything else unchanged — the mirror image of
# scripts/expansions/run_qwen_swe_prefix_cache_ablation.sh (5.a), which turns caching ON
# for SWE-Bench, whose production runs had it off:
#   Agent      : Qwen3.5-35B-A3B, configs/config-qwen-vllm.yaml, :8000
#                server: bash scripts/serving/start_vllm_qwen35_no_prefix_cache.sh
#                (the production serving command with --no-enable-prefix-caching)
#   Summarizer : the agent model itself (no --summary-config, no second server)
#   Cells      : d05__b3k__{tr,su-full,su-partial,ss,ss-partial}            (depth 0.5)
#                di__b3k__{trc,trc-su,trc-ss,otrc-tr,otrc-su-partial,otrc-ss-partial}
#                di__binf__{fc,otrc}                          (baselines, unlimited budget)
#   Tasks      : TB:ABL-15 x 3 runs  ->  13 cells x 15 x 3 = 585 runs
#                (paired with the caching-on cells main/qwen35b/{*__b3k__*,di__binf__*},
#                which hold P-40; ABL-15 is a subset of it).
# Results go to ICLR_results/terminalbench/prefix_cache_ablation/qwen35b-noprefixcache/<cell>.
# The section keeps these runs out of main/ and ablation/, so the caching-on
# cells are neither skipped-as-complete nor mixed with them; the model dir also
# differs from qwen35b because analysis/aggregate_terminalbench_results.py
# exposes it as model_key, and it doubles as the model tag so the Harbor job
# directories (logs/harbor_jobs/terminalbench/<tag>) stay apart as well.
#
# The launcher refuses to start unless the process listening on the agent port
# was started with --no-enable-prefix-caching, logs the server's prefix-cache
# counters (vLLM /metrics) over each cell, and stops the grid if any cell
# records a cache hit. Start vLLM and the Podman socket separately.
#
# Usage: nohup bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh > logs/followup_tb_qwen_noprefixcache.nohup.log 2>&1 &
# Smoke test (1 task x 1 cell x 1 run into a throwaway model dir; delete it afterwards —
# "-smoke" model dirs are ignored by build_coverage.py and aggregate_terminalbench_results.py):
#   N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 \
#     ICLR_MODEL=qwen35b-noprefixcache-smoke bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh
# Overrides: ICLR_MODEL, RUNS_PER_TASK, N_CONCURRENT, N_TASKS (first N tasks of
#   TB_TASKS_FILE), TB_TASKS_FILE, QWEN_AGENT_CONFIG, QWEN_OTRC_CONFIG,
#   QWEN_HEALTH_URL, CELLS.
# Completed task/condition/run keys are skipped on rerun.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$WS"
mkdir -p logs

PY="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
OTRC_CONFIG="${QWEN_OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
AGENT_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
TASKS_FILE="${TB_TASKS_FILE:-$WS/task_lists/tbench_abl15.json}"
ICLR_SECTION="prefix_cache_ablation"                # ICLR_results/terminalbench/prefix_cache_ablation/
ICLR_MODEL="${ICLR_MODEL:-qwen35b-noprefixcache}"   # lowercase/digits/hyphens
INF_BUDGET=999999999
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
N_CONCURRENT="${N_CONCURRENT:-4}"                   # same as the production main grid
N_TASKS="${N_TASKS:-}"          # empty = every task in TB_TASKS_FILE
# "cell:condition:depth" triples; override CELLS to run a subset. The budget
# comes from the cell name: b3k -> 3000, binf -> unlimited.
CELLS="${CELLS:-d05__b3k__tr:truncation:0.5 \
d05__b3k__su-full:summarization:0.5 \
d05__b3k__su-partial:summarization-partial:0.5 \
d05__b3k__ss:structured-summarize:0.5 \
d05__b3k__ss-partial:structured-summarize-partial:0.5 \
di__b3k__trc:tool-result-clear:0.5 \
di__b3k__trc-su:trc-su:0.5 \
di__b3k__trc-ss:trc-ss:0.5 \
di__b3k__otrc-tr:otrc-tr:0.5 \
di__b3k__otrc-su-partial:otrc-su-partial:0.5 \
di__b3k__otrc-ss-partial:otrc-ss-partial:0.5 \
di__binf__fc:full-context:0.5 \
di__binf__otrc:online-trc:0.5}"
LOG_FILE="${TB_PREFIXCACHE_LOG_FILE:-$WS/logs/followup_tb_qwen_${ICLR_MODEL}.log}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$OTRC_CONFIG"; require_file "$TASKS_FILE"
# The destination encodes the serving condition; qwen35b is the model_key of
# the caching-on runs.
[[ "$ICLR_MODEL" == qwen35b-noprefixcache* ]] || {
    echo "[ERROR] ICLR_MODEL must start with qwen35b-noprefixcache (got $ICLR_MODEL)" >&2; exit 1;
}
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

exec 9>"logs/qwen_tb_${ICLR_MODEL}.lock"
flock -n 9 || { echo "Prefix-cache ablation launcher for $ICLR_MODEL already running." >&2; exit 1; }

curl -fsS --max-time 5 "$AGENT_HEALTH_URL" >/dev/null || {
    echo "[ERROR] vLLM server is not responding at $AGENT_HEALTH_URL" >&2; exit 1;
}
# The agent YAML must talk to the server that is checked below.
agent_api_base="$(sed -n 's/^[[:space:]]*api_base:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' "$AGENT_CONFIG" | head -1)"
[[ "$AGENT_HEALTH_URL" == "${agent_api_base%/}/models" ]] || {
    echo "[ERROR] agent api_base ($agent_api_base) does not match QWEN_HEALTH_URL ($AGENT_HEALTH_URL)" >&2; exit 1;
}

# Prefix caching OFF is the whole point of this grid, and vLLM 0.17.1 does not
# export its cache config on /metrics, so inspect the command line of the
# process that owns the agent port. The explicit --no-enable-prefix-caching is
# required: a missing flag only means "off" while vLLM's default for this
# model stays off.
port="$(sed -n 's#^[a-z]*://[^:/]*:\([0-9][0-9]*\)/.*#\1#p' <<<"$AGENT_HEALTH_URL")"
[[ -n "$port" ]] || { echo "[ERROR] cannot read a port from QWEN_HEALTH_URL=$AGENT_HEALTH_URL" >&2; exit 1; }
server_pid="$(ss -ltnpH "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)"
[[ -n "$server_pid" && -r "/proc/$server_pid/cmdline" ]] || {
    echo "[ERROR] cannot find a local process of this user listening on port $port;" \
         "the vLLM server must run on this machine so its arguments can be checked" >&2
    exit 1
}
server_cmdline="$(tr '\0' ' ' < "/proc/$server_pid/cmdline")"
if [[ " $server_cmdline " != *" --no-enable-prefix-caching "* || " $server_cmdline " == *" --enable-prefix-caching "* ]]; then
    echo "[ERROR] the vLLM server on port $port (PID $server_pid) was not started with --no-enable-prefix-caching:" >&2
    echo "  $server_cmdline" >&2
    echo "Restart it with: bash scripts/serving/stop_vllm.sh logs/vllm_qwen35.pid &&" \
         "bash scripts/serving/start_vllm_qwen35_no_prefix_cache.sh" >&2
    exit 1
fi

log() { echo "[$(date)] $*" | tee -a "$LOG_FILE"; }

# "queries hits" token counters of the server's prefix cache (vLLM /metrics).
# With caching off the hit counter must not move.
METRICS_URL="${AGENT_HEALTH_URL%/v1/models}/metrics"
prefix_cache_counters() {
    curl -fsS --max-time 5 "$METRICS_URL" 2>/dev/null | awk '
        /^vllm:prefix_cache_queries_total/ { q += $NF }
        /^vllm:prefix_cache_hits_total/    { h += $NF }
        END { printf "%.0f %.0f\n", q, h }' || echo "0 0"
}
# log_prefix_cache_delta <label> <queries before> <hits before>; returns 1 on a cache hit.
log_prefix_cache_delta() {
    local label="$1" q0="$2" h0="$3" q1 h1
    read -r q1 h1 <<<"$(prefix_cache_counters)"
    log "prefix cache over $label: $((h1 - h0)) hit / $((q1 - q0)) queried tokens (expected 0 hit)"
    (( h1 - h0 == 0 ))
}

log "=== Prefix-cache ablation (TB) | dest: $ICLR_SECTION/$ICLR_MODEL | agent: $AGENT_CONFIG | summarizer: agent model ==="
log "=== budgets=3000/inf runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} concurrency=$N_CONCURRENT ==="
log "=== vLLM server PID $server_pid on port $port: $server_cmdline==="

# Validate every cell before the first run, so a typo in CELLS cannot stop the
# grid hours in.
for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    case "$cell" in
        *__b3k__*|*__binf__*) ;;
        *) echo "[ERROR] cell $cell is neither a 3K-budget nor an unlimited-budget cell" >&2; exit 1 ;;
    esac
    [[ -n "$condition" && -n "$depth" ]] || { echo "[ERROR] malformed CELLS entry: $spec" >&2; exit 1; }
done

read -r total_q0 total_h0 <<<"$(prefix_cache_counters)"
for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    budget=3000
    [[ "$cell" == *"__binf__"* ]] && budget="$INF_BUDGET"
    log "--- $ICLR_SECTION/$ICLR_MODEL/$cell | condition=$condition budget=$budget depth=$depth ---"
    read -r cell_q0 cell_h0 <<<"$(prefix_cache_counters)"
    "$PY" "$RUNNER" \
        --iclr-benchmark terminal-bench --iclr-section "$ICLR_SECTION" \
        --iclr-model "$ICLR_MODEL" --iclr-cell "$cell" \
        --benchmark terminal-bench --model-tag "$ICLR_MODEL" \
        --agent-config "$AGENT_CONFIG" --otrc-config "$OTRC_CONFIG" \
        --budget "$budget" --depth "$depth" --tasks-file "$TASKS_FILE" \
        --conditions "$condition" --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$N_CONCURRENT" "${EXTRA_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
    log_prefix_cache_delta "$cell" "$cell_q0" "$cell_h0" || {
        log "[ERROR] the server recorded prefix-cache hits during $cell: it is not serving with caching off."
        log "[ERROR] Stopping the grid; the runs of $cell are not valid caching-off runs."
        exit 1
    }
done
log_prefix_cache_delta "the whole grid" "$total_q0" "$total_h0" || true
log "=== Prefix-cache ablation (TB) complete for $ICLR_MODEL ==="
