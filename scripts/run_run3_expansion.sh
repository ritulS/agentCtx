#!/bin/bash
# Runs/task: 2->3 expansion (exp_plans/SWE_EXPANSION.md, section "1. [Priority] Runs/task: 2->3").
#
# Adds run_3 for the 4 blocks below. 
#
#   Block 1: TR, SU-full, SU-partial, SS, SS-partial  @ depth 0.5,      10k/15k/20k -> P100
#   Block 2: same 5 primitives                        @ depth 0.3/0.7, 10k/15k/20k -> ABL-30
#   Block 3: TRC, TRC+SU, TRC+SS, OTRC+TR,
#            OTRC+SU-partial, OTRC+SS-partial          @ depth-invariant, 10k/15k/20k -> P100
#   Block 4: FC, OTRC                                  @ unlimited budget          -> P100


set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$WS"
LOG="$WS/logs/run3_expansion.log"
mkdir -p "$WS/logs"
PY="venv/bin/python3"
RPT=3   # target runs/task for this expansion

log() { echo "[$(date)] $*" | tee -a "$LOG"; }

# Compat symlinks (idempotent; safe to re-run)
mkdir -p results
ln -sfn ../data/swebench/ablations   results/ablations
ln -sfn ../data/swebench/tbench      results/tbench

ln -sfn ../source_runs/qwen3.5-35B-A3B_15k_Fullrun  data/swebench/ablations/qwen3.5-35B-A3B_15k_Fullrun
ln -sfn ../source_runs/qwen35-a3b_online-trc        data/swebench/ablations/qwen35-a3b_online-trc


ABL30="task_lists/ablation_30tasks.json"
NEW70="task_lists/p100_new_tasks.json"

run_cell() {
    local ablation="$1" budget="$2" depth="$3" tasksfile="$4" conds="$5"
    log "--- $ablation | budget=$budget depth=$depth | $conds ---"
    $PY scripts/run_experiment.py \
        --ablation      "$ablation" \
        --budget        "$budget" \
        --depth         "$depth" \
        --tasks-file    "$tasksfile" \
        --conditions    $conds \
        --runs-per-task "$RPT" \
        2>&1 | tee -a "$LOG"
    $PY scripts/run_experiment.py \
        --ablation      "$ablation" \
        --budget        "$budget" \
        --depth         "$depth" \
        --tasks-file    "$tasksfile" \
        --conditions    $conds \
        --runs-per-task "$RPT" \
        --eval-only \
        2>&1 | tee -a "$LOG"
}

SINGLES="truncation summarization summarization-partial structured-summarize structured-summarize-partial"

log "=== Block 1: singles @ depth 0.5 -> P100 ==="
for budget in 15000 10000 20000; do
    run_cell "p100-singles-${budget}" "$budget" 0.5 "$NEW70" "$SINGLES"
done
# ABL-30 side, split by which primitives share a source dir per budget
run_cell "timing-10k"  10000 0.5 "$ABL30" "truncation summarization"
run_cell "timing-20k"  20000 0.5 "$ABL30" "truncation summarization"
run_cell "partial-10000" 10000 0.5 "$ABL30" "summarization-partial structured-summarize-partial structured-summarize"
run_cell "partial-15000" 15000 0.5 "$ABL30" "summarization-partial structured-summarize-partial"
run_cell "partial-20000" 20000 0.5 "$ABL30" "summarization-partial structured-summarize-partial structured-summarize"
# ABL-30 gap: TR/SU-full/SS @ 15k canonical live in the Fullrun source, aliased above
run_cell "qwen3.5-35B-A3B_15k_Fullrun" 15000 0.5 "$ABL30" "truncation summarization structured-summarize"


log "=== Block 2: singles @ depth 0.3/0.7 -> ABL-30 ==="
for depth_tag_pair in "0.3:30" "0.7:70"; do
    depth="${depth_tag_pair%%:*}"; tag="${depth_tag_pair##*:}"
    for budget in 15000 10000 20000; do
        run_cell "p100-depth${tag}-singles-${budget}" "$budget" "$depth" "$ABL30" "$SINGLES"
    done
done


log "=== Block 3: TRC/TRC-stack/OTRC-stack -> P100 ==="
for budget in 15000 10000 20000; do
    run_cell "p100-trc-${budget}"   "$budget" 0.5 "$NEW70" "tool-result-clear trc-su trc-ss"
    run_cell "p100-otrc-${budget}"  "$budget" 0.5 "$NEW70" "otrc-tr otrc-su-partial otrc-ss-partial"
done
run_cell "timing-10k"          10000 0.5 "$ABL30" "tool-result-clear"
run_cell "timing-20k"          20000 0.5 "$ABL30" "tool-result-clear"
for budget in 15000 10000 20000; do
    run_cell "stacked-${budget}"       "$budget" 0.5 "$ABL30" "trc-su trc-ss"
    run_cell "otrc-stacked-${budget}"  "$budget" 0.5 "$ABL30" "otrc-tr otrc-su-partial otrc-ss-partial"
done
# ABL-30 gap: TRC (tool-result-clear) @ 15k canonical lives in the Fullrun source
run_cell "qwen3.5-35B-A3B_15k_Fullrun" 15000 0.5 "$ABL30" "tool-result-clear"


log "=== Block 4: FC/OTRC @ unlimited budget -> P100 ==="
run_cell "p100-inf" 999999999 0.5 "$NEW70" "full-context online-trc"
# ABL-30 gap: full-context lives in the Fullrun source (budget-independent condition);
# online-trc lives in the dedicated online-trc source. Both aliased above.
run_cell "qwen3.5-35B-A3B_15k_Fullrun" 999999999 0.5 "$ABL30" "full-context"
run_cell "qwen35-a3b_online-trc"       999999999 0.5 "$ABL30" "online-trc"

log "=== Runs/task 2->3 expansion complete ==="
