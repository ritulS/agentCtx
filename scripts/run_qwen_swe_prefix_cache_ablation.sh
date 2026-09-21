#!/usr/bin/env bash
# Prefix-caching ablation on SWE-Bench: rerun the Qwen3.5-35B-A3B primitives
# against a vLLM server started WITH --enable-prefix-caching.
#
# The production Qwen runs (ICLR_results/swebench/{main,ablation}/qwen35b) were
# served with prefix caching off (vLLM default for this hybrid model; see
# ICLR.md "Qwen prefix caching was off"). This launcher repeats the 15K /
# canonical-depth grid and the unlimited-budget baselines with caching on,
# everything else unchanged:
#   Agent      : Qwen3.5-35B-A3B, configs/config-qwen-vllm.yaml, :8000
#                server: bash scripts/start_vllm_qwen35_prefix_cache.sh
#                (the production serving command + --enable-prefix-caching)
#   Summarizer : the agent model itself (no --summary-config, no second server)
#   Cells      : d05__b15k__{tr,su-full,su-partial,ss,ss-partial}           (depth 0.5)
#                di__b15k__{trc,trc-su,trc-ss,otrc-tr,otrc-su-partial,otrc-ss-partial}
#                di__binf__{fc,otrc}                          (baselines, unlimited budget)
#   Tasks      : ABL-25 x 3 runs  ->  13 cells x 25 x 3 = 975 runs (dashboard 5.a)
#                (paired with the caching-off cells main/qwen35b/{*__b15k__*,di__binf__*}).
# Results go to ICLR_results/swebench/prefix_cache_ablation/qwen35b-prefixcache/<cell>.
# The section keeps these runs out of main/ and ablation/, so the caching-off
# cells are neither skipped-as-complete nor mixed with them; the model dir also
# differs from qwen35b because analysis/aggregate_benchmark_results.py exposes
# it as model_key, which downstream scripts group by without the section.
#
# The launcher refuses to start unless the process listening on the agent port
# was started with --enable-prefix-caching, and logs the server's prefix-cache
# hit rate (vLLM /metrics counters) over each cell.
#
# Usage: nohup bash scripts/run_qwen_swe_prefix_cache_ablation.sh > logs/followup_sb_qwen_prefixcache.nohup.log 2>&1 &
# Baselines only (the 15K cells are complete; this also avoids re-running their eval pass):
#   nohup env CELLS="di__binf__fc:full-context:0.5 di__binf__otrc:online-trc:0.5" \
#     bash scripts/run_qwen_swe_prefix_cache_ablation.sh > logs/followup_sb_qwen_prefixcache.nohup.log 2>&1 &
# Smoke test (1 task x 1 cell x 1 run into a throwaway model dir; delete it afterwards —
# "-smoke" model dirs are ignored by build_coverage.py and aggregate_benchmark_results.py):
#   N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 CELLS=d05__b15k__su-full:summarization:0.5 \
#     ICLR_MODEL=qwen35b-prefixcache-smoke bash scripts/run_qwen_swe_prefix_cache_ablation.sh
# Overrides: ICLR_MODEL, RUNS_PER_TASK, MAX_WORKERS, N_TASKS (first N
#   tasks of TASKS_FILE), TASKS_FILE, QWEN_AGENT_CONFIG, QWEN_OTRC_CONFIG, QWEN_TAG,
#   RUN_EVAL, QWEN_HEALTH_URL, CELLS.
# Completed task/condition/run keys are skipped on rerun.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
mkdir -p logs

PY="${PYTHON:-$WS/venv/bin/python3}"
RUNNER="$WS/scripts/run_experiment_iclr.py"
AGENT_CONFIG="${QWEN_AGENT_CONFIG:-$WS/configs/config-qwen-vllm.yaml}"
OTRC_CONFIG="${QWEN_OTRC_CONFIG:-$WS/configs/config-online-trc.yaml}"
MODEL_TAG="${QWEN_TAG:-qwen35-a3b}"                 # same tag as the caching-off runs
AGENT_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
TASKS_FILE="${TASKS_FILE:-$WS/task_lists/ablation_25tasks.json}"
ICLR_SECTION="prefix_cache_ablation"                # ICLR_results/swebench/prefix_cache_ablation/
ICLR_MODEL="${ICLR_MODEL:-qwen35b-prefixcache}"     # lowercase/digits/hyphens
INF_BUDGET=999999999
RUNS_PER_TASK="${RUNS_PER_TASK:-3}"
MAX_WORKERS="${MAX_WORKERS:-16}"
RUN_EVAL="${RUN_EVAL:-1}"
N_TASKS="${N_TASKS:-}"          # empty = every task in TASKS_FILE
# "cell:condition:depth" triples; override CELLS to run a subset. The budget
# comes from the cell name: b15k -> 15000, binf -> unlimited.
CELLS="${CELLS:-d05__b15k__tr:truncation:0.5 \
d05__b15k__su-full:summarization:0.5 \
d05__b15k__su-partial:summarization-partial:0.5 \
d05__b15k__ss:structured-summarize:0.5 \
d05__b15k__ss-partial:structured-summarize-partial:0.5 \
di__b15k__trc:tool-result-clear:0.5 \
di__b15k__trc-su:trc-su:0.5 \
di__b15k__trc-ss:trc-ss:0.5 \
di__b15k__otrc-tr:otrc-tr:0.5 \
di__b15k__otrc-su-partial:otrc-su-partial:0.5 \
di__b15k__otrc-ss-partial:otrc-ss-partial:0.5 \
di__binf__fc:full-context:0.5 \
di__binf__otrc:online-trc:0.5}"
LOG_FILE="${SB_PREFIXCACHE_LOG_FILE:-$WS/logs/followup_sb_qwen_${ICLR_MODEL}.log}"

require_file() { [[ -f "$1" ]] || { echo "[ERROR] Required file not found: $1" >&2; exit 1; }; }
require_file "$PY"; require_file "$RUNNER"; require_file "$AGENT_CONFIG"
require_file "$OTRC_CONFIG"; require_file "$TASKS_FILE"
# The destination encodes the serving condition; qwen35b is the model_key of
# the caching-off runs.
[[ "$ICLR_MODEL" == qwen35b-prefixcache* ]] || {
    echo "[ERROR] ICLR_MODEL must start with qwen35b-prefixcache (got $ICLR_MODEL)" >&2; exit 1;
}
EXTRA_ARGS=()
if [[ -n "$N_TASKS" ]]; then
    [[ "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] N_TASKS must be a positive integer: $N_TASKS" >&2; exit 1; }
    EXTRA_ARGS+=(--n-tasks "$N_TASKS")
fi

exec 9>"logs/qwen_sb_${ICLR_MODEL}.lock"
flock -n 9 || { echo "Prefix-cache ablation launcher for $ICLR_MODEL already running." >&2; exit 1; }

curl -fsS --max-time 5 "$AGENT_HEALTH_URL" >/dev/null || {
    echo "[ERROR] vLLM server is not responding at $AGENT_HEALTH_URL" >&2; exit 1;
}
# The agent YAML must talk to the server that is checked below.
agent_api_base="$(sed -n 's/^[[:space:]]*api_base:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' "$AGENT_CONFIG" | head -1)"
[[ "$AGENT_HEALTH_URL" == "${agent_api_base%/}/models" ]] || {
    echo "[ERROR] agent api_base ($agent_api_base) does not match QWEN_HEALTH_URL ($AGENT_HEALTH_URL)" >&2; exit 1;
}

# Prefix caching is the whole point of this grid, and vLLM 0.17.1 does not
# export its cache config on /metrics, so inspect the command line of the
# process that owns the agent port.
port="$(sed -n 's#^[a-z]*://[^:/]*:\([0-9][0-9]*\)/.*#\1#p' <<<"$AGENT_HEALTH_URL")"
[[ -n "$port" ]] || { echo "[ERROR] cannot read a port from QWEN_HEALTH_URL=$AGENT_HEALTH_URL" >&2; exit 1; }
server_pid="$(ss -ltnpH "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)"
[[ -n "$server_pid" && -r "/proc/$server_pid/cmdline" ]] || {
    echo "[ERROR] cannot find a local process of this user listening on port $port;" \
         "the vLLM server must run on this machine so its arguments can be checked" >&2
    exit 1
}
server_cmdline="$(tr '\0' ' ' < "/proc/$server_pid/cmdline")"
if [[ " $server_cmdline " != *" --enable-prefix-caching "* || " $server_cmdline " == *" --no-enable-prefix-caching "* ]]; then
    echo "[ERROR] the vLLM server on port $port (PID $server_pid) was not started with --enable-prefix-caching:" >&2
    echo "  $server_cmdline" >&2
    echo "Restart it with: bash scripts/start_vllm_qwen35_prefix_cache.sh" >&2
    exit 1
fi

log() { echo "[$(date)] $*" | tee -a "$LOG_FILE"; }

# "queries hits" token counters of the server's prefix cache (vLLM /metrics).
METRICS_URL="${AGENT_HEALTH_URL%/v1/models}/metrics"
prefix_cache_counters() {
    curl -fsS --max-time 5 "$METRICS_URL" 2>/dev/null | awk '
        /^vllm:prefix_cache_queries_total/ { q += $NF }
        /^vllm:prefix_cache_hits_total/    { h += $NF }
        END { printf "%.0f %.0f\n", q, h }' || echo "0 0"
}
log_prefix_cache_delta() {
    local label="$1" q0="$2" h0="$3" q1 h1
    read -r q1 h1 <<<"$(prefix_cache_counters)"
    awk -v l="$label" -v q="$((q1 - q0))" -v h="$((h1 - h0))" 'BEGIN {
        printf "prefix cache over %s: %d hit / %d queried tokens (%s)\n", l, h, q,
               (q > 0 ? sprintf("%.1f%%", 100 * h / q) : "n/a") }' |
        while IFS= read -r line; do log "$line"; done
}

log "=== Prefix-cache ablation (SWE-Bench) | dest: $ICLR_SECTION/$ICLR_MODEL | agent: $AGENT_CONFIG | summarizer: agent model ==="
log "=== budgets=15000/inf runs/task=$RUNS_PER_TASK tasks=$(basename "$TASKS_FILE")${N_TASKS:+ (first $N_TASKS)} workers=$MAX_WORKERS eval=$RUN_EVAL ==="
log "=== vLLM server PID $server_pid on port $port: $server_cmdline==="

# run_runner <cell> <condition> <depth> <budget> [extra runner args]
run_runner() {
    "$PY" "$RUNNER" \
        --iclr-section "$ICLR_SECTION" --iclr-model "$ICLR_MODEL" --iclr-cell "$1" \
        --ablation "iclr-${ICLR_MODEL}-${ICLR_SECTION}-$1" \
        --model-tag "$MODEL_TAG" \
        --agent-config "$AGENT_CONFIG" --otrc-config "$OTRC_CONFIG" \
        --budget "$4" --depth "$3" --tasks-file "$TASKS_FILE" \
        --conditions "$2" --runs-per-task "$RUNS_PER_TASK" \
        --max-workers "$MAX_WORKERS" "${EXTRA_ARGS[@]}" "${@:5}" 2>&1 | tee -a "$LOG_FILE"
}

# Validate every cell before the first run, so a typo in CELLS cannot stop the
# grid hours in.
for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    case "$cell" in
        *__b15k__*|*__binf__*) ;;
        *) echo "[ERROR] cell $cell is neither a 15K-budget nor an unlimited-budget cell" >&2; exit 1 ;;
    esac
    [[ -n "$condition" && -n "$depth" ]] || { echo "[ERROR] malformed CELLS entry: $spec" >&2; exit 1; }
done

read -r total_q0 total_h0 <<<"$(prefix_cache_counters)"
for spec in $CELLS; do
    IFS=: read -r cell condition depth <<<"$spec"
    budget=15000
    [[ "$cell" == *"__binf__"* ]] && budget="$INF_BUDGET"
    log "--- $ICLR_SECTION/$ICLR_MODEL/$cell | condition=$condition budget=$budget depth=$depth ---"
    read -r cell_q0 cell_h0 <<<"$(prefix_cache_counters)"
    run_runner "$cell" "$condition" "$depth" "$budget"
    log_prefix_cache_delta "$cell" "$cell_q0" "$cell_h0"
    if [[ "$RUN_EVAL" == 1 ]]; then
        run_runner "$cell" "$condition" "$depth" "$budget" --eval-only
    fi
done
log_prefix_cache_delta "the whole grid" "$total_q0" "$total_h0"
log "=== Prefix-cache ablation (SWE-Bench) complete for $ICLR_MODEL ==="
