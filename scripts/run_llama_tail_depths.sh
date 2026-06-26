#!/bin/bash
# Llama 3.3 70B  §d: 5 depth-tunable prims x 3 calibrated budgets x 2 tail depths (0.3, 0.7).
# 5 prims x 3 budgets x 2 depths x 30 tasks x 2 runs = 1,800 runs.
# Output dirs: results/ablations/llama33-70b-budgeted-{TIGHT,MEDIUM,LOOSE}-d{030,070}/
#
# Prerequisites:
#  - §c (run_llama_budgeted_canonical.sh) complete and sanity-checked
#  - Same TIGHT/MEDIUM/LOOSE budget values as §c (filled below)
#
# Usage:  nohup bash scripts/run_llama_tail_depths.sh > logs/llama33_70b_tail.out 2>&1 &
#         echo $! > logs/llama33_70b_tail.pid
# Tail:   tail -f logs/llama33_70b_tail.log
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/llama33_70b_tail.log"
mkdir -p "$WS/logs"

# === FILL THESE — must match §c budgets exactly ===
TIGHT_BUDGET=____
MEDIUM_BUDGET=____
LOOSE_BUDGET=____

for v in "$TIGHT_BUDGET" "$MEDIUM_BUDGET" "$LOOSE_BUDGET"; do
    if [ "$v" = "____" ]; then
        echo "[ERROR] Budget placeholders not filled. Copy values from run_llama_budgeted_canonical.sh." >&2
        exit 1
    fi
done

echo "[$(date)] === Llama-3.3-70B §d: tail-depth sweep (d=0.3, 0.7) ===" | tee -a "$LOG"
echo "[$(date)] Budgets: T=$TIGHT_BUDGET  M=$MEDIUM_BUDGET  L=$LOOSE_BUDGET" | tee -a "$LOG"

# Pre-flight: vLLM must be up on port 8001.
if ! curl -sf http://localhost:8001/v1/models >/dev/null 2>&1; then
    echo "[ERROR] vLLM not responding on port 8001. Run scripts/start_vllm_llama33_70b.sh first." | tee -a "$LOG"
    exit 1
fi

# Only the 5 depth-tunable primitives — depth-invariant prims stay at d=0.5.
CONDS_DEPTH_TUNABLE="truncation summarization summarization-partial structured-summarize structured-summarize-partial"

# Run order: d=0.3 layer first (M, T, L), then d=0.7 layer (M, T, L). Matches Qwen2.5-7B pattern.
for depth_label in d030 d070; do
    case "$depth_label" in
        d030) DEPTH=0.3 ;;
        d070) DEPTH=0.7 ;;
    esac
    for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
        name="llama33-70b-budgeted-${budget}-${depth_label}"
        echo "[$(date)] --- $name (depth=$DEPTH) ---" | tee -a "$LOG"

        venv/bin/python3 scripts/run_experiment.py \
            --ablation     "$name" \
            --model-tag    llama33-70b \
            --agent-config configs/config-llama33-vllm.yaml \
            --otrc-config  configs/config-online-trc-llama33.yaml \
            --budget       "$budget" \
            --depth        "$DEPTH" \
            --tasks-file   task_lists/ablation_30tasks.json \
            --conditions   $CONDS_DEPTH_TUNABLE \
            2>&1 | tee -a "$LOG"

        venv/bin/python3 scripts/run_experiment.py \
            --ablation     "$name" \
            --model-tag    llama33-70b \
            --agent-config configs/config-llama33-vllm.yaml \
            --otrc-config  configs/config-online-trc-llama33.yaml \
            --budget       "$budget" \
            --depth        "$DEPTH" \
            --tasks-file   task_lists/ablation_30tasks.json \
            --conditions   $CONDS_DEPTH_TUNABLE \
            --eval-only \
            2>&1 | tee -a "$LOG"
    done
done

echo "[$(date)] === Llama-3.3-70B §d DONE — full 3,900-run grid complete ===" | tee -a "$LOG"
echo "[$(date)] Followup: see exp_plans/DOBBY_LLAMA_PHASE.md §3 (Review1 ingest + checklist update)" | tee -a "$LOG"
