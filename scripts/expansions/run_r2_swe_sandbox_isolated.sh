#!/usr/bin/env bash
# Isolated serial driver for the controlled-sandbox pilot
# (scripts/expansions/run_r2_swe_majority_capped_pilot.sh): ONE agent run per
# vLLM server lifetime and per container generation, so no two runs can share
# server state (KV cache, scheduler, batching neighbours) or container state.
#
# For every (section, prefix-3 order, task, run number) of the plan that is not
# yet recorded in the cell's experiment_results.json, in that order:
#   1. start a fresh caching-OFF server (VLLM_START_SCRIPT, default
#      scripts/serving/start_vllm_qwen35_sandbox.sh; AGENTCTX_PROFILE=albus-swe
#      -> all 8 GPUs, TP=8) and wait until QWEN_HEALTH_URL answers
#      (VLLM_READY_TIMEOUT_S, default 1800 s)
#   2. run the capped pilot on a one-task list with RUNS_PER_TASK=<run number>
#      and MAX_WORKERS=1: recorded keys are skipped, so exactly this run
#      executes. With RUN_EVAL=1 (default) its patch is graded right away
#      (the harness needs containers, not the server).
#   3. stop the server (VLLM_STOP_SCRIPT, default scripts/serving/stop_vllm.sh:
#      the whole process group, EngineCore and TP workers included)
#   4. remove every container of this user's podman (DOCKER_HOST, default the
#      rootless socket the SWE-bench adapter uses; PURGE_CONTAINERS=all) or only
#      the agent / harness ones, minisweagent-* and sweb.eval.* (PURGE_CONTAINERS=
#      experiment). Images stay: the harness reuses the instance images
#      (--cache_level instance) and the agent pulls none.
#   5. check that the run's key is now recorded; otherwise stop.
# The same stop + purge runs before the first cycle and on every exit (trap,
# including Ctrl-C / TERM). The pilot's process group is stopped before
# server/container cleanup, including leftover agent/eval children. Cleanup
# failures stop the driver with a nonzero status. Traps cannot run on SIGKILL
# or OOM of the driver, so a watchdog in its own session (started after the
# guards, stopped first on a clean exit) watches the driver's pid and, once it
# is gone, kills the pilot's process group, stops the server and purges the
# containers itself. Only killing driver and watchdog together, or power loss,
# leaves work behind.
# A server on the port that was not started by the sandbox script
# (no pid file) is an error: stop it by hand first. The driver refuses to
# start while another r2 launcher or runner is running (BUSY_PATTERN; empty
# disables), because stopping the server would kill its runs.
#
# Everything about the runs themselves (configs, summarizer, limits, dest cell,
# task lists, eval) is the capped pilot's; this script only serialises them.
# INNER=p30s swaps the capped pilot for scripts/expansions/run_r2_swe_p30s.sh
# (plain ICLR-grid cells such as di__b15k__su-free / d05__b15k__tr, summarizer =
# the agent model, the agent config from QWEN_AGENT_CONFIG): the plan is then
# (section, CELLS entry "cell:condition:depth", task, run), keys are
# <task>__<condition>__r<n> and the dest cell is data/r2/swebench/<section>/<R2_MODEL>/<cell>/.
# In that mode SECTIONS is p30s | p100_minus_p30s, CELLS and R2_MODEL are
# required (no derived name), TASKS_FILE defaults to the section's list, and
# PATTERNS / SUMMARIZER / NOTHINK / SUMMARY_MAX_ATTEMPTS must stay unset.
# scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh is the
# Devstral-Small-2507 wrapper that uses it.
# SERVER_LIFECYCLE=persistent changes only the server part of the cycle: the
# server is started once before the first cycle and stopped once on exit, and
# every cycle is still one run with MAX_WORKERS=1 followed by the container
# purge. Runs then share the live server (KV/prefix cache, scheduler, compiled
# state) but never run concurrently; the driver stops if the server dies
# between cycles (it is never restarted mid-plan). Keep a separate R2_MODEL
# from the per-run rows.
# KV_FLUSH=prefix-cache (persistent only) POSTs vLLM's /reset_prefix_cache
# after every cycle's container purge, so the next run starts from an empty
# prefix cache on the same live server (the run's own self-hits remain). The
# server must be started with VLLM_SERVER_DEV_MODE=1 (the endpoint is 404
# otherwise); the driver requires HTTP success and, when the server log
# (<pid file minus .pid>.latest.log) exists, a new "Successfully reset prefix
# cache" line in it, and stops otherwise.
# Resume: rerun with the same settings; recorded (task, run) keys are skipped
# without a server restart. Note that run_info.json describes the latest cycle
# (n_tasks 1, runs_per_task = that run number); use the rows for comparisons.
#
#   INNER         : pilot (default) | p30s (see above)
#   SERVER_LIFECYCLE : per-run (default: fresh server for every run) | persistent (see above)
#   KV_FLUSH      : none (default) | prefix-cache (persistent only; see above)
#   SECTIONS      : default p100_su_free_majority (also p100_tr_majority, p100_fc_only4);
#                   with INNER=p30s: p30s | p100_minus_p30s (no default)
#   PATTERNS      : default the section's (sss / ttt / the eight orders); INNER=pilot only
#   CELLS         : "cell:condition:depth ..." as run_r2_swe_p30s.sh takes them; INNER=p30s only
#   CYCLE_ORDER   : task-major (default: every run of task 1, then task 2, ...) |
#                   run-major (run 1 of every task, then run 2, ...) within each pattern / cell
#   TASKS_FILE    : default the pilot's (the 4 sandbox tasks for the majority
#                   sections; p100_fc_only4's own list);  N_TASKS: first N (default all)
#   RUNS_PER_TASK : default the section's (15; p100_fc_only4 10; INNER=p30s 3)
#   SUMMARIZER, NOTHINK, SUMMARY_CONFIG, SUMMARY_MAX_ATTEMPTS, AGENT_TIMEOUT, STEP_LIMIT,
#   RUN_EVAL      : passed to the pilot unchanged. SUMMARIZER defaults to nothink here
#                   (summarizer-only thinking OFF with the 2048-token reply cap; the
#                   pilot itself defaults to agent) and SUMMARY_MAX_ATTEMPTS to 5 (the
#                   primitive default; the pilot's nothink recipe lowers it to 2), so
#                   the isolated rows are the 2048-cap recipe with the full retry budget.
#                   With ISO_SUFFIX="" they would land beside the 2-attempt rows of
#                   qwen35b-cap4k-sumnothink; keep a separate dir unless that is intended.
#   R2_MODEL      : (INNER=pilot) default the pilot's dest for these settings plus ISO_SUFFIX
#                   (default "-iso": qwen35b-cap4k-sumnothink-iso, qwen35b-cap4k-iso, ...)
#                   so the isolated rows never mix with the 3-worker cells;
#                   ISO_SUFFIX="" resumes into the pilot's own dir
#   MAX_WORKERS   : must be 1 (or unset)
#   DRY_RUN=1     : print the plan (recorded / pending per key) and exit
#   VLLM_START_SCRIPT, VLLM_STOP_SCRIPT, VLLM_PID_FILE, VLLM_READY_TIMEOUT_S,
#   QWEN_HEALTH_URL, DOCKER_HOST, DOCKER_BIN, PURGE_CONTAINERS, BUSY_PATTERN,
#   ISOLATED_TASKS_DIR (one-task JSON lists; default logs/experiments/isolated_tasks/<R2_MODEL>/)
#
# Usage (Albus; the server is started and stopped by this script, do not start one):
#   AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/qwen35b-cap4k-sumnothink-iso \
#       -- bash scripts/expansions/run_r2_swe_sandbox_isolated.sh
#   DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated.sh
#   SECTIONS=p100_fc_only4 N_TASKS=2 RUNS_PER_TASK=15 PATTERNS="tts sst" ...   (SUMMARIZER=nothink4k / agent for the other recipes)
# Cost: one server start (several minutes) per run on top of the run itself.
# Scope: resets live inference and container writable state, not the host disk.
# Results/logs, model/dataset/compilation caches and immutable images remain.
# Default agent configs mount no host directories or named volumes. Custom
# mounts or an external SUMMARY_CONFIG server need their own isolation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${AGENTCTX_WS:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$WS"
source "$SCRIPT_DIR/../lib/logpaths.sh"

PILOT="$SCRIPT_DIR/run_r2_swe_majority_capped_pilot.sh"
P30S_LAUNCHER="$SCRIPT_DIR/run_r2_swe_p30s.sh"
INNER="${INNER:-pilot}"
CYCLE_ORDER="${CYCLE_ORDER:-task-major}"
SERVER_LIFECYCLE="${SERVER_LIFECYCLE:-per-run}"
KV_FLUSH="${KV_FLUSH:-none}"
VLLM_START_SCRIPT="${VLLM_START_SCRIPT:-$SCRIPT_DIR/../serving/start_vllm_qwen35_sandbox.sh}"
VLLM_STOP_SCRIPT="${VLLM_STOP_SCRIPT:-$SCRIPT_DIR/../serving/stop_vllm.sh}"
VLLM_PID_FILE="${VLLM_PID_FILE:-$SERVER_LOG_DIR/vllm_qwen35_a3b_noprefixcache.pid}"
VLLM_READY_TIMEOUT_S="${VLLM_READY_TIMEOUT_S:-1800}"
export QWEN_HEALTH_URL="${QWEN_HEALTH_URL:-http://localhost:8000/v1/models}"
export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"
DOCKER_BIN="${DOCKER_BIN:-docker}"
PURGE_CONTAINERS="${PURGE_CONTAINERS:-all}"
BUSY_PATTERN="${BUSY_PATTERN-run_r2_swe_(majority_capped_pilot|never7_adaptive|sandbox_chain|majority_uniform|p30s)\.sh|run_experiment(_r2|_iclr)?\.py}"
PY3="${PYTHON3:-python3}"
RUN_EVAL="${RUN_EVAL:-1}"
SCHEDULE_DIR="${SCHEDULE_DIR:-$WS/configs/adaptive/never7_prefix3}"
die() { echo "[ERROR] $*" >&2; exit 1; }
require_file() { [[ -f "$1" ]] || die "Required file not found: $1"; }
log() { echo "[$(date)] isolated: $*"; }

case "$INNER" in
    pilot)
        INNER_SCRIPT="$PILOT"
        SECTIONS="${SECTIONS:-p100_su_free_majority}"
        SUMMARIZER="${SUMMARIZER:-nothink}"
        export SUMMARIZER
        export SUMMARY_MAX_ATTEMPTS="${SUMMARY_MAX_ATTEMPTS:-5}"
        [[ "$SUMMARY_MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] || die "SUMMARY_MAX_ATTEMPTS must be a positive integer: $SUMMARY_MAX_ATTEMPTS"
        [[ -z "${QWEN_AGENT_CONFIG:-}" ]] || die "QWEN_AGENT_CONFIG is chosen by the capped pilot (NOTHINK=0/1); unset it"
        [[ -z "${CELLS:-}" ]] || die "CELLS is for INNER=p30s; the capped pilot takes PATTERNS"
        ;;
    p30s)
        INNER_SCRIPT="$P30S_LAUNCHER"
        [[ -n "${SECTIONS:-}" ]] || die "SECTIONS is required with INNER=p30s (p30s | p100_minus_p30s)"
        [[ -n "${CELLS:-}" ]] || die "CELLS (\"cell:condition:depth ...\") is required with INNER=p30s"
        [[ -n "${R2_MODEL:-}" ]] || die "R2_MODEL is required with INNER=p30s (no derived name; keep it apart from the multi-worker dirs, e.g. <model>-iso)"
        [[ -z "${PATTERNS:-}" ]] || die "PATTERNS is for INNER=pilot; INNER=p30s takes CELLS"
        [[ -z "${SUMMARIZER:-}${NOTHINK:-}${SUMMARY_MAX_ATTEMPTS:-}" ]] || die "SUMMARIZER / NOTHINK / SUMMARY_MAX_ATTEMPTS are capped-pilot settings; run_r2_swe_p30s.sh summarises with the agent model"
        ;;
    *) die "INNER must be pilot | p30s (got '$INNER')" ;;
esac
case "$CYCLE_ORDER" in task-major|run-major) ;; *) die "CYCLE_ORDER must be task-major | run-major (got '$CYCLE_ORDER')" ;; esac
case "$SERVER_LIFECYCLE" in per-run|persistent) ;; *) die "SERVER_LIFECYCLE must be per-run | persistent (got '$SERVER_LIFECYCLE')" ;; esac
case "$KV_FLUSH" in none|prefix-cache) ;; *) die "KV_FLUSH must be none | prefix-cache (got '$KV_FLUSH')" ;; esac
[[ "$KV_FLUSH" == none || "$SERVER_LIFECYCLE" == persistent ]] || die "KV_FLUSH=$KV_FLUSH needs SERVER_LIFECYCLE=persistent (a per-run server starts empty anyway)"

for f in "$INNER_SCRIPT" "$VLLM_START_SCRIPT" "$VLLM_STOP_SCRIPT"; do require_file "$f"; done
[[ -z "${MAX_WORKERS:-}" || "$MAX_WORKERS" == 1 ]] || die "MAX_WORKERS must be 1 for the isolated driver (got $MAX_WORKERS)"
export MAX_WORKERS=1
case "$PURGE_CONTAINERS" in all|experiment) ;; *) die "PURGE_CONTAINERS must be all | experiment (got '$PURGE_CONTAINERS')" ;; esac
for section in $SECTIONS; do
    case "$INNER:$section" in
        pilot:p100_su_free_majority|pilot:p100_tr_majority|pilot:p100_fc_only4) ;;
        pilot:*) die "SECTIONS entry '$section' is not p100_su_free_majority | p100_tr_majority | p100_fc_only4" ;;
        p30s:p30s|p30s:p100_minus_p30s) ;;
        p30s:*) die "SECTIONS entry '$section' is not p30s | p100_minus_p30s (INNER=p30s)" ;;
    esac
done

# Dest model dir: the capped pilot's choice for these settings plus ISO_SUFFIX
# (INNER=p30s: the explicit R2_MODEL).
if [[ -z "${R2_MODEL:-}" ]]; then
    base="qwen35b-cap4k"; [[ "${NOTHINK:-0}" != 1 ]] || base="qwen35b-cap4k-nothink"
    case "$SUMMARIZER" in
        agent) ;;
        nothink|nothink4k) base="$base-sum$SUMMARIZER" ;;
        *) die "SUMMARIZER must be agent | nothink | nothink4k (got '$SUMMARIZER')" ;;
    esac
    R2_MODEL="$base${ISO_SUFFIX--iso}"
fi
export R2_MODEL
TASKS_DIR="${ISOLATED_TASKS_DIR:-$EXPERIMENT_LOG_DIR/isolated_tasks/$R2_MODEL}"

# Own the log unless an outer wrapper (notify_run.sh) already does.
if [[ -z "${AGENTCTX_LOG_FILE:-}" ]]; then
    LOG_FILE="$(experiment_log "r2_sb_isolated_${R2_MODEL}")"
    export AGENTCTX_LOG_FILE="$LOG_FILE"
    exec > >(tee -a "$LOG_FILE") 2>&1
    log "log: $LOG_FILE"
fi

# ── Plan: the capped pilot's task lists, orders and run counts per section ───
section_patterns() {
    case "$1" in
        p100_su_free_majority) echo "sss" ;;
        p100_tr_majority)      echo "ttt" ;;
        p100_fc_only4)         echo "ttt tts tst tss stt sts sst sss" ;;
    esac
}
section_runs() { case "$INNER:$1" in p30s:*) echo 3 ;; pilot:p100_fc_only4) echo 10 ;; *) echo 15 ;; esac; }
section_tasks_file() {
    if [[ -n "${TASKS_FILE:-}" ]]; then echo "$TASKS_FILE"
    elif [[ "$1" == p100_fc_only4 ]]; then echo "$WS/task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json"
    elif [[ "$1" == p30s ]]; then echo "$WS/task_lists/swe_verified/p30_stratified.json"
    elif [[ "$1" == p100_minus_p30s ]]; then echo "$WS/task_lists/swe_verified/p100_minus_p30s.json"
    else echo "$WS/task_lists/swe_verified/sandbox_su_free_compressing4.json"; fi
}
# The plan's second field is a prefix-3 pattern (INNER=pilot) or a CELLS entry
# "cell:condition:depth" (INNER=p30s); these map it to the recorded key and cell.
plan_key() {   # <pattern|cell spec> <instance> <run>
    if [[ "$INNER" == pilot ]]; then echo "${2}__adaptive__r$3"
    else local condition="${1#*:}"; echo "${2}__${condition%%:*}__r$3"; fi
}
check_variant() {   # <pattern|cell spec>
    if [[ "$INNER" == pilot ]]; then
        [[ "$1" =~ ^[a-z0-9]+$ ]] || die "malformed PATTERNS entry: $1"
        require_file "$SCHEDULE_DIR/$1.json"
    else
        [[ "$1" =~ ^[A-Za-z0-9_-]+__(b[1-9][0-9]*k|binf)__[A-Za-z0-9_-]+:[a-z0-9-]+:[0-9.]+$ ]] \
            || die "malformed CELLS entry (want cell:condition:depth with a b<N>k / binf budget tag): $1"
    fi
}
task_ids() {   # <tasks.json> <n|all> -> instance ids, one per line, list order
    "$PY3" - "$1" "$2" <<'PYEOF'
import json, sys
tasks = json.load(open(sys.argv[1]))
if sys.argv[2] != "all":
    tasks = tasks[: int(sys.argv[2])]
for task in tasks:
    print(task["instance_id"])
PYEOF
}
write_single_task() {   # <tasks.json> <instance id> <out.json>
    "$PY3" - "$1" "$2" "$3" <<'PYEOF'
import json, sys
src, instance, out = sys.argv[1:4]
tasks = [t for t in json.load(open(src)) if t["instance_id"] == instance]
assert len(tasks) == 1, f"{instance}: {len(tasks)} entries in {src}"
json.dump(tasks, open(out, "w"), indent=2)
PYEOF
}
key_recorded() {   # <experiment_results.json> <key>
    [[ -f "$1" ]] || return 1
    "$PY3" - "$1" "$2" <<'PYEOF'
import json, sys
rows = json.load(open(sys.argv[1]))
sys.exit(0 if any(r.get("key") == sys.argv[2] for r in rows) else 1)
PYEOF
}
cell_results() {   # <section> <pattern|cell spec>
    if [[ "$INNER" == pilot ]]; then echo "$WS/data/r2/swebench/$1/$R2_MODEL/d05__b15k__adaptive-prefix3-$2/experiment_results.json"
    else echo "$WS/data/r2/swebench/$1/$R2_MODEL/${2%%:*}/experiment_results.json"; fi
}

N_TASKS="${N_TASKS:-all}"
[[ "$N_TASKS" == all || "$N_TASKS" =~ ^[1-9][0-9]*$ ]] || die "N_TASKS must be a positive integer or all: $N_TASKS"
[[ -z "${RUNS_PER_TASK:-}" || "$RUNS_PER_TASK" =~ ^[1-9][0-9]*$ ]] || die "RUNS_PER_TASK must be a positive integer: $RUNS_PER_TASK"
PLAN=()      # "section pattern instance run tasks_file"
PENDING=()
for section in $SECTIONS; do
    tasks_file="$(section_tasks_file "$section")"; require_file "$tasks_file"
    runs="${RUNS_PER_TASK:-$(section_runs "$section")}"
    mapfile -t ids < <(task_ids "$tasks_file" "$N_TASKS")
    (( ${#ids[@]} > 0 )) || die "no tasks in $tasks_file"
    if [[ "$INNER" == pilot ]]; then variants="${PATTERNS:-$(section_patterns "$section")}"; else variants="$CELLS"; fi
    for pat in $variants; do
        check_variant "$pat"
        if [[ "$CYCLE_ORDER" == task-major ]]; then
            for instance in "${ids[@]}"; do
                for ((r = 1; r <= runs; r++)); do PLAN+=("$section $pat $instance $r $tasks_file"); done
            done
        else
            for ((r = 1; r <= runs; r++)); do
                for instance in "${ids[@]}"; do PLAN+=("$section $pat $instance $r $tasks_file"); done
            done
        fi
    done
done
for entry in "${PLAN[@]}"; do
    read -r section pat instance r _ <<<"$entry"
    if key_recorded "$(cell_results "$section" "$pat")" "$(plan_key "$pat" "$instance" "$r")"; then
        [[ "${DRY_RUN:-0}" != 1 ]] || echo "  recorded  $section $pat $instance r$r"
    else
        PENDING+=("$entry")
        [[ "${DRY_RUN:-0}" != 1 ]] || echo "  pending   $section $pat $instance r$r"
    fi
done
if [[ "$INNER" == pilot ]]; then recipe="SUMMARIZER=$SUMMARIZER (max attempts $SUMMARY_MAX_ATTEMPTS)"
else recipe="cells: $CELLS | agent config: ${QWEN_AGENT_CONFIG:-configs/config-qwen-vllm.yaml (launcher default)}"; fi
log "plan: ${#PLAN[@]} keys, $(( ${#PLAN[@]} - ${#PENDING[@]} )) recorded, ${#PENDING[@]} pending | inner: $INNER | server: $SERVER_LIFECYCLE$([[ "$KV_FLUSH" == none ]] || echo " (flush: $KV_FLUSH)") | order: $CYCLE_ORDER | sections: $SECTIONS${PATTERNS:+ | patterns: $PATTERNS} | R2_MODEL=$R2_MODEL | $recipe | eval=$RUN_EVAL | purge=$PURGE_CONTAINERS | profile: ${AGENTCTX_PROFILE:-unset} | server: $VLLM_START_SCRIPT"
if [[ "${DRY_RUN:-0}" == 1 ]]; then
    log "DRY_RUN=1: nothing started"
    exit 0
fi

# ── Guards ───────────────────────────────────────────────────────────────────
# Shared across model/section variants; the pilot's per-cell lock is too late
# to protect the server and containers. FD 8 is closed in detached children.
mkdir -p "$EXPERIMENT_LOG_DIR"
exec 8>"$EXPERIMENT_LOG_DIR/r2_sb_sandbox_isolated.lock"
flock -n 8 || die "another isolated driver owns the server/container lifecycle"
command -v setsid >/dev/null || die "setsid is required to isolate the pilot process group"
if [[ -n "$BUSY_PATTERN" ]]; then
    busy="$(pgrep -u "$(id -u)" -f "$BUSY_PATTERN" | grep -vx -e "$$" -e "$PPID" || true)"
    [[ -z "$busy" ]] || die "another launcher / runner is running (pids: $(echo $busy | tr '\n' ' ')); stopping the server would kill its runs"
fi
if [[ ! -f "$VLLM_PID_FILE" ]] && curl -fsS --max-time 5 "$QWEN_HEALTH_URL" >/dev/null 2>&1; then
    die "a server answers at $QWEN_HEALTH_URL but $VLLM_PID_FILE does not exist (not started by the sandbox script); stop it by hand first"
fi

# ── Server and container lifecycle ───────────────────────────────────────────
start_vllm() {
    log "starting the server ($VLLM_START_SCRIPT)"
    bash "$VLLM_START_SCRIPT" 8>&-
    [[ -f "$VLLM_PID_FILE" ]] || die "the start script left no pid file at $VLLM_PID_FILE"
}
wait_ready() {
    local waited=0 pid
    pid="$(tr -d '[:space:]' < "$VLLM_PID_FILE")"
    until curl -fsS --max-time 5 "$QWEN_HEALTH_URL" >/dev/null 2>&1; do
        kill -0 "$pid" 2>/dev/null || die "the server (pid $pid) exited before becoming ready; see logs/servers/"
        (( waited < VLLM_READY_TIMEOUT_S )) || die "the server did not answer at $QWEN_HEALTH_URL within ${VLLM_READY_TIMEOUT_S}s"
        (( waited % 120 != 0 )) || log "waiting for the server (${waited}s)"
        sleep 10; waited=$(( waited + 10 ))
    done
    log "server ready after ${waited}s"
}
server_alive() {   # persistent mode: the one server must still be the one we started
    local pid
    [[ -f "$VLLM_PID_FILE" ]] || { echo "[ERROR] the server pid file $VLLM_PID_FILE is gone" >&2; return 1; }
    pid="$(tr -d '[:space:]' < "$VLLM_PID_FILE")"
    kill -0 "$pid" 2>/dev/null || { echo "[ERROR] the server (pid $pid) is no longer running" >&2; return 1; }
    curl -fsS --max-time 5 "$QWEN_HEALTH_URL" >/dev/null 2>&1 || { echo "[ERROR] the server (pid $pid) does not answer at $QWEN_HEALTH_URL" >&2; return 1; }
}
flush_prefix_cache() {   # persistent + KV_FLUSH=prefix-cache: empty the prefix cache between cycles
    local url="${QWEN_HEALTH_URL%/v1/models}/reset_prefix_cache" srvlog="${VLLM_PID_FILE%.pid}.latest.log" before=0 after i
    [[ ! -e "$srvlog" ]] || before="$(grep -ac "Successfully reset prefix cache" "$srvlog" || true)"
    curl -fsS --max-time 30 -X POST "$url" >/dev/null 2>&1 || {
        echo "[ERROR] POST $url failed (server started without VLLM_SERVER_DEV_MODE=1?)" >&2; return 1;
    }
    if [[ -e "$srvlog" ]]; then
        for ((i = 0; i < 20; i++)); do
            after="$(grep -ac "Successfully reset prefix cache" "$srvlog" || true)"
            (( after > before )) && break
            sleep 0.5
        done
        (( after > before )) || { echo "[ERROR] the server did not log a successful prefix-cache reset (blocks still in use?)" >&2; return 1; }
    fi
    log "prefix cache reset ($url)"
}
stop_vllm() {
    if [[ -f "$VLLM_PID_FILE" ]]; then
        log "stopping the server ($VLLM_PID_FILE)"
        bash "$VLLM_STOP_SCRIPT" "$VLLM_PID_FILE" 8>&- || return 1
    else
        log "no server pid file; nothing to stop"
    fi
    if curl -fsS --max-time 5 "$QWEN_HEALTH_URL" >/dev/null 2>&1; then
        echo "[ERROR] server still answers at $QWEN_HEALTH_URL after stop" >&2
        return 1
    fi
}
list_containers() {   # id name status, one per line, filtered by PURGE_CONTAINERS
    local listing
    listing="$("$DOCKER_BIN" ps -a --format '{{.ID}} {{.Names}} {{.Status}}')" || {
        echo "[ERROR] cannot list containers (DOCKER_HOST=$DOCKER_HOST)" >&2; return 1;
    }
    if [[ "$PURGE_CONTAINERS" == experiment ]]; then
        grep -E '^[^ ]+ (minisweagent-|sweb\.eval\.)' <<<"$listing" || true
    else
        echo "$listing"
    fi
}
purge_containers() {
    local listing
    listing="$(list_containers)" || return 1
    if [[ -z "$listing" ]]; then
        log "containers: none to remove"
        return 0
    fi
    log "removing $(wc -l <<<"$listing") container(s) ($PURGE_CONTAINERS):"
    sed 's/^/    /' <<<"$listing"
    # -v also removes anonymous volumes; named volumes/bind mounts are not used
    # by the default configs and must never be globally pruned here.
    local ids
    ids="$(awk '{print $1}' <<<"$listing")"
    "$DOCKER_BIN" rm -f -v $ids >/dev/null || return 1
    listing="$(list_containers)" || return 1
    [[ -z "$listing" ]] || {
        echo "[ERROR] containers survived the purge: $(echo "$listing" | tr '\n' ';')" >&2; return 1;
    }
    reap_conmon $ids
}
reap_conmon() {   # <container id>...: podman's per-exec conmon monitors of a container
    # removed while agent commands were still running are re-parented to init
    # and never exit (seen 2026-10-17: 74 of them after a TERM mid-run). They
    # hold no container, so terminate them; they are this user's processes only.
    local id pids
    for id in "$@"; do
        pids="$(pgrep -u "$(id -u)" -f "conmon .* -c $id" || true)"
        [[ -n "$pids" ]] || continue
        log "terminating $(wc -w <<<"$pids") orphaned conmon process(es) of removed container ${id:0:12}"
        kill -TERM $pids 2>/dev/null || true
        sleep 2
        pids="$(pgrep -u "$(id -u)" -f "conmon .* -c $id" || true)"
        [[ -z "$pids" ]] || kill -KILL $pids 2>/dev/null || true
    done
}
gpu_status() {
    command -v nvidia-smi >/dev/null 2>&1 || return 0
    log "GPU memory used (MiB): $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')"
}

OWNS_MACHINE=0
PILOT_PGID=""
PGID_FILE="$EXPERIMENT_LOG_DIR/r2_sb_sandbox_isolated.pilot_pgid"
WATCHDOG_PID=""
# The watchdog runs these in its own bash (export -f below), so they must only
# use exported variables.
export VLLM_PID_FILE VLLM_STOP_SCRIPT DOCKER_BIN PURGE_CONTAINERS PGID_FILE
watchdog_main() {   # <driver pid>: act only once the driver is gone
    local driver="$1" pgid i failed=0
    # The sleeper must not inherit the lock fd or the log pipe: it can outlive
    # the watchdog by up to 2 s after a clean driver exit.
    while kill -0 "$driver" 2>/dev/null; do sleep 2 8>&- >/dev/null 2>&1; done
    log "watchdog: the driver (pid $driver) is gone without cleaning up; cleaning up now"
    pgid="$(cat "$PGID_FILE" 2>/dev/null || true)"
    if [[ -n "$pgid" ]] && kill -0 -- "-$pgid" 2>/dev/null; then
        log "watchdog: stopping pilot/agent/eval process group $pgid"
        kill -TERM -- "-$pgid" 2>/dev/null || true
        for ((i = 0; i < 10; i++)); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 1; done
        kill -KILL -- "-$pgid" 2>/dev/null || true
    fi
    rm -f "$PGID_FILE"
    stop_vllm || failed=1
    purge_containers || failed=1
    if (( failed )); then log "watchdog: cleanup FAILED; inspect remaining processes/containers before restarting"
    else log "watchdog: clean"; fi
}
start_watchdog() {
    export -f log stop_vllm list_containers purge_containers reap_conmon watchdog_main
    # Own session: a TERM to the driver's group does not reach it, and it keeps
    # the launcher lock (fd 8) until it has cleaned up after a dead driver.
    setsid bash -c 'watchdog_main "$@"' isolated-watchdog "$$" </dev/null &
    WATCHDOG_PID=$!
    log "watchdog pid $WATCHDOG_PID"
}
stop_watchdog() {
    [[ -n "$WATCHDOG_PID" ]] || return 0
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
    WATCHDOG_PID=""
}
pilot_members() {
    # Orphan zombies cannot issue requests or create containers; only their
    # parent/init can reap them, so do not wait on them here.
    ps -eo pid=,pgid=,stat= | awk -v g="$PILOT_PGID" '$2 == g && $3 !~ /^Z/ {print $1}'
}
stop_pilot() {
    [[ -n "$PILOT_PGID" ]] || return 0
    local i
    if [[ -n "$(pilot_members)" ]]; then
        log "stopping pilot/agent/eval process group $PILOT_PGID"
        kill -TERM -- "-$PILOT_PGID" 2>/dev/null || true
        for ((i=0; i<10; i++)); do
            [[ -n "$(pilot_members)" ]] || break
            sleep 1
        done
        if [[ -n "$(pilot_members)" ]]; then
            kill -KILL -- "-$PILOT_PGID" 2>/dev/null || true
            for ((i=0; i<5; i++)); do
                [[ -n "$(pilot_members)" ]] || break
                sleep 1
            done
        fi
        [[ -z "$(pilot_members)" ]] || {
            echo "[ERROR] pilot children survived cleanup (group $PILOT_PGID)" >&2; return 1;
        }
    fi
    wait "$PILOT_PGID" 2>/dev/null || true
    PILOT_PGID=""
    rm -f "$PGID_FILE"
}
cleanup() {
    local failed=0
    # Attempt all three even if one fails; never proceed to the next cycle
    # unless all three succeeded.
    stop_pilot || failed=1
    stop_vllm || failed=1
    purge_containers || failed=1
    return "$failed"
}
cleanup_keep_server() {   # persistent mode, between cycles: pilot and containers only (+ optional cache flush)
    local failed=0
    stop_pilot || failed=1
    purge_containers || failed=1
    if [[ "$KV_FLUSH" == prefix-cache ]] && (( failed == 0 )); then flush_prefix_cache || failed=1; fi
    return "$failed"
}
on_exit() {
    local rc=$?
    trap - EXIT
    trap '' INT TERM HUP
    stop_watchdog
    if (( OWNS_MACHINE )); then
        log "exit $rc: final server stop + container purge"
        if ! cleanup; then
            echo "[ERROR] final cleanup failed; inspect remaining processes/containers before restarting" >&2
            (( rc != 0 )) || rc=1
        fi
    fi
    exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

run_cycle() {   # <section> <pattern> <instance> <run> <tasks_file>
    local section="$1" pat="$2" instance="$3" r="$4" tasks_file="$5"
    local key single="$TASKS_DIR/$instance.json" rc=0
    key="$(plan_key "$pat" "$instance" "$r")"
    write_single_task "$tasks_file" "$instance" "$single"
    if [[ "$SERVER_LIFECYCLE" == per-run ]]; then
        start_vllm
        wait_ready
    else
        server_alive || die "the persistent server is gone before $key; stopping (it is never restarted mid-plan)"
    fi
    log ">>> $key | $(dirname "$(cell_results "$section" "$pat")" | sed "s#^$WS/data/r2/swebench/##")"
    if [[ "$INNER" == pilot ]]; then
        SECTIONS="$section" PATTERNS="$pat" TASKS_FILE="$single" N_TASKS=all RUNS_PER_TASK="$r" \
            MAX_WORKERS=1 R2_MODEL="$R2_MODEL" RUN_EVAL="$RUN_EVAL" setsid bash "$PILOT" 8>&- &
    else
        # One cell, one task, RUNS_PER_TASK=<run number>: recorded keys are skipped,
        # so exactly this run executes (N_TASKS empty = the whole one-task list).
        R2_SECTION="$section" CELLS="$pat" TASKS_FILE="$single" N_TASKS= RUNS_PER_TASK="$r" \
            MAX_WORKERS=1 R2_MODEL="$R2_MODEL" RUN_EVAL="$RUN_EVAL" setsid bash "$P30S_LAUNCHER" 8>&- &
    fi
    PILOT_PGID=$!
    echo "$PILOT_PGID" > "$PGID_FILE"
    # Waiting on an asynchronous child lets bash handle TERM/INT immediately.
    wait "$PILOT_PGID" || rc=$?
    if [[ "$SERVER_LIFECYCLE" == per-run ]]; then
        cleanup || die "cleanup failed after $key; stopping"
    else
        cleanup_keep_server || die "cleanup failed after $key; stopping"
    fi
    gpu_status
    (( rc == 0 )) || die "the inner launcher ($INNER) exited $rc on $key; stopping"
    key_recorded "$(cell_results "$section" "$pat")" "$key" || die "$key is not recorded in $(cell_results "$section" "$pat"); stopping"
    log "<<< $key done"
}

OWNS_MACHINE=1
mkdir -p "$TASKS_DIR"
start_watchdog
log "initial clean-up"
cleanup || die "initial cleanup failed; stopping"
if [[ "$SERVER_LIFECYCLE" == persistent && ${#PENDING[@]} -gt 0 ]]; then
    log "persistent server: started once for all ${#PENDING[@]} cycle(s), stopped on exit"
    start_vllm
    wait_ready
fi
n=0
for entry in "${PENDING[@]}"; do
    n=$(( n + 1 ))
    log "=== cycle $n/${#PENDING[@]} ==="
    read -r section pat instance r tasks_file <<<"$entry"
    run_cycle "$section" "$pat" "$instance" "$r" "$tasks_file"
done
log "complete: ${#PENDING[@]} run(s) executed into data/r2/swebench/<section>/$R2_MODEL/"
