# Stacked Primitive Runs: TRC+SU, TRC+TR, TRC+SS at 10k / 15k / 20k
## Overview

Three stacked conditions, three budgets, 99 tasks each = **3 × 3 × 99 × 2 = 1782 new agent runs**.

**What "stacking" means here (cascade / sequential):**
When the context exceeds the budget:
1. **Stage 1**: TRC fires first — clears tool outputs oldest-first, preserving the last KEEP_RECENT=3 tool-result turns.
2. **Stage 2**: If context is still over budget after TRC, the fallback primitive fires on the already-cleaned context.

| Condition | Stage 1 | Stage 2 (fallback) | New? |
|---|---|---|---|
| `trc-tr`  | TRC | Truncation | No — identical to existing `tool-result-clear` |
| `trc-su`  | TRC | Summarization | **Yes — new** |
| `trc-ss`  | TRC | Structured-summarize | **Yes — new** |

**TRC+TR does NOT need new runs.** Use `results/qwen3.5-35B-A3B_15k_Fullrun/` (condition `tool-result-clear`)
for 15k, and `results/qwen35-a3b_10k/` / `results/qwen35-a3b_20k/` for 10k/20k (after fill runs complete).

---

## Prerequisites

1. **Working directory**: `/home/rs67788/projects/agentCtx`
2. **Code changes already applied** (do not redo):
   - `memory.py`: `tool_result_clear` now accepts `fallback_truncate=False`
   - `default.py`: handlers for `trc_summarize` and `trc_structured_summarize` added
   - `run_experiment.py`: `trc-su` and `trc-ss` conditions added to `CONDITIONS`
3. **vLLM server** on `http://localhost:8000` serving `Qwen/Qwen3.5-35B-A3B`
4. **Podman socket** running for SWE-bench eval

---

## Step 1: TRC+SU and TRC+SS at 15k (99 tasks)

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_15k \
    --budget     15000 \
    --conditions trc-su trc-ss
```

- Results go to `results/qwen35-a3b_stacked_15k/`
- 99 tasks × 2 conditions × 2 runs = **396 agent runs**
- Uses `selected_tasks.json` (the full 99-task set)

---

## Step 2: TRC+SU and TRC+SS at 10k (99 tasks)

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_10k \
    --budget     10000 \
    --conditions trc-su trc-ss
```

- Results go to `results/qwen35-a3b_stacked_10k/`
- 99 tasks × 2 conditions × 2 runs = **396 agent runs**

---

## Step 3: TRC+SU and TRC+SS at 20k (99 tasks)

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_20k \
    --budget     20000 \
    --conditions trc-su trc-ss
```

- Results go to `results/qwen35-a3b_stacked_20k/`
- 99 tasks × 2 conditions × 2 runs = **396 agent runs**

---

## Step 4: Evaluate all three budgets

Run each eval after the corresponding agent step completes (or all three after all agents finish).

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_15k \
    --budget     15000 \
    --conditions trc-su trc-ss \
    --eval-only

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_10k \
    --budget     10000 \
    --conditions trc-su trc-ss \
    --eval-only

python3 scripts/run_experiment.py \
    --model-tag  qwen35-a3b_stacked_20k \
    --budget     20000 \
    --conditions trc-su trc-ss \
    --eval-only
```

---

## Verification

After all steps, run this to confirm counts and resolve rates:

```bash
python3 << 'EOF'
import json, os
from collections import defaultdict

dirs = {
    '10k_stacked': 'results/qwen35-a3b_stacked_10k/experiment_results.json',
    '15k_stacked': 'results/qwen35-a3b_stacked_15k/experiment_results.json',
    '20k_stacked': 'results/qwen35-a3b_stacked_20k/experiment_results.json',
}

for tag, path in dirs.items():
    if not os.path.exists(path):
        print(f"{tag}: NOT FOUND")
        continue
    with open(path) as f:
        data = json.load(f)
    runs = data if isinstance(data, list) else data.get('results', [])
    cond_runs = defaultdict(list)
    for r in runs:
        cond_runs[r.get('condition')].append(r)
    print(f"\n=== {tag} ({len(runs)} total) ===")
    for cond in ['trc-su', 'trc-ss']:
        rs = cond_runs.get(cond, [])
        tasks = set(r.get('instance_id') for r in rs)
        resolve = sum(1 for r in rs if r.get('resolved')) / len(rs) * 100 if rs else 0
        print(f"  {cond:<10} n={len(rs):4d}  tasks={len(tasks):3d}  resolve={resolve:.1f}%")
EOF
```

**Expected per budget:** `trc-su` n=198 tasks=99, `trc-ss` n=198 tasks=99

---

## Notes

- Steps 1–3 can run in parallel if GPU memory allows (they share the same vLLM server).
- If interrupted, re-run the same command — the runner resumes from existing results.
- `trc-tr` comparison data comes from the existing `tool-result-clear` condition in the
  main experiment results — no new runs needed.
- The `full-context` baseline for these comparisons comes from the main experiment results.
