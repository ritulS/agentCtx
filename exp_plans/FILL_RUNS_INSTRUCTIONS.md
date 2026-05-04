# Fill Runs: 10k and 20k Budget Completion
## Goal
Bring the 10k and 20k budget runs from 30 tasks/condition up to 99 tasks/condition,
matching the 15k full run. Each fill adds 70 tasks × 5 conditions × 2 runs = **700 new agent runs per budget**.

---

## Prerequisites

1. **Working directory**: `/home/rs67788/projects/agentCtx`
2. **vLLM server must be running** on `http://localhost:8000` serving `Qwen/Qwen3.5-35B-A3B`
3. **Podman socket** must be running for SWE-bench eval (check: `ls /run/user/$(id -u)/podman/podman.sock`)
4. **Fill task files already created** (do not recreate them):
   - `selected_tasks_10k_fill.json` — 70 tasks (django=24, sympy=24, scikit-learn=22)
   - `selected_tasks_20k_fill.json` — identical 70 tasks

---

## Step 1: Run the 10k fill (700 agent runs)

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag      qwen35-a3b_10k \
    --tasks-file     selected_tasks_10k_fill.json \
    --budget         10000 \
    --conditions     full-context truncation summarization structured-summarize tool-result-clear
```

**What this does:**
- Results go into `results/qwen35-a3b_10k/` (same dir as existing 30-task results)
- The runner loads existing 150 runs, skips them (different task IDs), runs the 70 new tasks
- 3 warnings about repo task counts are **expected and harmless** (e.g. "only 24 tasks for django (need 34)")
- Each run: 125-step limit, 2 runs/task, 8 concurrent workers
- Saves incrementally to `results/qwen35-a3b_10k/experiment_results.json`

**Expected output count when complete:** 150 (existing) + 700 (new) = **850 runs total**

---

## Step 2: Evaluate the 10k fill patches

After Step 1 completes:

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag      qwen35-a3b_10k \
    --tasks-file     selected_tasks_10k_fill.json \
    --budget         10000 \
    --conditions     full-context truncation summarization structured-summarize tool-result-clear \
    --eval-only
```

This runs SWE-bench evaluation on all patches with `resolved=null`. Safe to re-run if interrupted.

---

## Step 3: Run the 20k fill (700 agent runs)

Can run **in parallel with Step 1 or 2** if GPU memory allows. Otherwise run after.

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag      qwen35-a3b_20k \
    --tasks-file     selected_tasks_20k_fill.json \
    --budget         20000 \
    --conditions     full-context truncation summarization structured-summarize tool-result-clear
```

**What this does:** Same as Step 1 but targets `results/qwen35-a3b_20k/` and budget=20000.

**Expected output count when complete:** 150 (existing) + 700 (new) = **850 runs total**

---

## Step 4: Evaluate the 20k fill patches

```bash
cd /home/rs67788/projects/agentCtx

python3 scripts/run_experiment.py \
    --model-tag      qwen35-a3b_20k \
    --tasks-file     selected_tasks_20k_fill.json \
    --budget         20000 \
    --conditions     full-context truncation summarization structured-summarize tool-result-clear \
    --eval-only
```

---

## Verification

After all steps complete, run this to confirm counts and resolve rates:

```bash
python3 << 'EOF'
import json
from collections import defaultdict

for tag, path in [
    ('10k', 'results/qwen35-a3b_10k/experiment_results.json'),
    ('15k', 'results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json'),
    ('20k', 'results/qwen35-a3b_20k/experiment_results.json'),
]:
    with open(path) as f:
        data = json.load(f)
    runs = data if isinstance(data, list) else data.get('results', [])
    cond_runs = defaultdict(list)
    for r in runs:
        cond_runs[r.get('condition')].append(r)
    print(f"\n=== {tag} ({len(runs)} total runs) ===")
    for prim in ['full-context','truncation','summarization','structured-summarize','tool-result-clear']:
        rs = cond_runs.get(prim, [])
        tasks = set(r.get('instance_id') for r in rs)
        resolve = sum(1 for r in rs if r.get('resolved')) / len(rs) * 100 if rs else 0
        print(f"  {prim:<25} n={len(rs):4d}  tasks={len(tasks):3d}  resolve={resolve:.1f}%")
EOF
```

**Expected after completion:**
- 10k: 5 conditions × 99 tasks × 2 runs = **990 runs** (same as 15k)
- 20k: 5 conditions × 99 tasks × 2 runs = **990 runs** (same as 15k)

Note: The 30 tasks already run at 10k/20k used the same task IDs as the 15k run,
so the combined dataset is consistent across all three budgets.

---

## If a run is interrupted

The runner saves results incrementally after every completed run. Simply re-run the
exact same command — it will load existing results, skip completed keys, and
continue from where it left off.

---

## Notes

- The `--conditions` flag explicitly excludes `online-trc` from these runs. Online-TRC
  is a separate system and is handled independently.
- Do **not** use `--with-eval` during agent runs — run eval separately after all agents
  complete to avoid eval bottlenecking agent throughput.
- The fill task files (`selected_tasks_10k_fill.json`, `selected_tasks_20k_fill.json`)
  are identical — the 69 tasks missing from both budgets are the same set.
