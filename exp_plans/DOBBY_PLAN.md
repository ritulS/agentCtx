# Dobby — execution plan (post-P100)

Owner: ritul@utexas.edu. Created 2026-05-03.
Workspace: `/home/rs67788/projects/agentCtx`.
Model: Qwen3.5-35B-A3B (continuous serving — no swaps in this queue).

---

## Queue

After P100 finishes (Phase 2 in progress; ~30h remaining as of 2026-05-03), Dobby runs three experiments **in this exact order**:

1. **Staggered pilot** (24 runs + ~half-day implementation gated on design approval)
2. **Depth ablation 0.3 + 0.7** (Scope B: 8 primitives × 30 tasks × 2 runs × 2 depths = 960 runs, ~16h)
3. **5k budget expansion** (11 primitives × 30 tasks × 2 runs = 660 runs, ~11h)

**Wall-clock total (post-P100)**: ~28h GPU + 0.5d eng = **~2 days** of GPU work.

---

## 0. Pre-flight (immediately after P100 phase 3 completes)

```bash
cd /home/rs67788/projects/agentCtx

# 1. Confirm P100 done
grep '=== ALL P100 PHASES COMPLETE ===' logs/p100_chain.out

# 2. Confirm Review1 rebuild ran cleanly
ls -la Review1/Review1.csv  # should be ~7000 rows after P100 build
venv/bin/python3 -c "import pandas; print(len(pandas.read_csv('Review1/Review1.csv')))"

# 3. vLLM still up
curl -s http://localhost:8000/v1/models | head -1

# 4. Active_runs.md — move P100 to "Recently Completed"
```

---

## 1. Staggered pilot (24 runs)

### 1.1 Implementation (gated on design approval — see exp_plans/STAGGERED_DESIGN.md once written)

Files to modify:
- `memory.py` — add `staggered_alternate` and `staggered_random` primitives (~50 lines)
- `mini-swe-agent/src/minisweagent/agents/default.py` — add dispatch branches (~10 lines)
- `scripts/run_experiment.py` — register `staggered-alternate` and `staggered-random` as conditions
- `Review1/build_review1.py` — add `staggered_primitive_sequence` and `staggered_strategy` columns

Estimated implementation effort: ~4h (~half-day).

### 1.2 Pick the 6 tasks

```bash
# Find the 6 tasks where most primitives struggle.
venv/bin/python3 -c "
import pandas as pd
df = pd.read_csv('Review1/Review1.csv')
df['r'] = df['resolved'].astype(str) == 'True'
score = df.groupby('task_name').r.sum().sort_values()
hardest_6 = score.head(6).index.tolist()
print(hardest_6)
" > task_lists/staggered_pilot_tasks.txt
```

Convert to JSON in the canonical task-list format:

```bash
venv/bin/python3 - <<EOF
import json, pathlib
hardest = [t.strip() for t in pathlib.Path('task_lists/staggered_pilot_tasks.txt').read_text().strip('[]').replace("'","").split(",")]
def repo_of(t):
    if t.startswith('django'): return 'django'
    if t.startswith('sympy'): return 'sympy'
    if t.startswith('scikit-learn'): return 'scikit-learn'
    raise ValueError(t)
tasks = [{'instance_id': t, 'repo': repo_of(t)} for t in hardest]
pathlib.Path('task_lists/staggered_pilot.json').write_text(json.dumps(tasks, indent=2))
print(f'wrote {len(tasks)} tasks to task_lists/staggered_pilot.json')
EOF
```

### 1.3 Wrapper script — `scripts/run_staggered_pilot.sh`

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/staggered_pilot.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Staggered pilot starting ===" | tee -a "$LOG"

CONDS="staggered-alternate staggered-random"

venv/bin/python3 scripts/run_experiment.py \
    --ablation   staggered-pilot \
    --budget     20000 \
    --tasks-file task_lists/staggered_pilot.json \
    --conditions $CONDS \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation   staggered-pilot \
    --budget     20000 \
    --tasks-file task_lists/staggered_pilot.json \
    --conditions $CONDS \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Staggered pilot done ===" | tee -a "$LOG"
```

`chmod +x scripts/run_staggered_pilot.sh`

### 1.4 Run + monitor

```bash
nohup scripts/run_staggered_pilot.sh > logs/staggered_pilot.out 2>&1 &
echo $! > logs/staggered_pilot.pid
disown
```

**Update Active_runs.md** — add to "Currently Running":

```markdown
### Staggered compression pilot (TRC+SS ↔ OTRC+SS-partial, 6 hard tasks @ 20k)
- **Status:** RUNNING
- **Started:** YYYY-MM-DD HH:MM CDT
- **PID:** see logs/staggered_pilot.pid
- **Workers:** 16
- **Conditions:** staggered-alternate, staggered-random
- **Tasks:** 6 (the hardest by total resolves on Review1.csv)
- **Total runs:** 24
- **ETA:** ~25 minutes wall-clock
- **Output:** `results/ablations/staggered-pilot/`
- **Log:** `logs/staggered_pilot.log`
```

When `=== Staggered pilot done ===` appears, move entry to "Recently Completed".

### 1.5 Post-run analysis

```bash
# Add staggered runs to Review1.csv
venv/bin/python3 Review1/build_review1.py staggered-alternate staggered-random

# Quick check: did any of the 6 hard tasks resolve?
venv/bin/python3 -c "
import pandas as pd
df = pd.read_csv('Review1/Review1.csv')
sub = df[df.primitive.isin(['staggered-alternate', 'staggered-random'])]
print(sub.groupby(['task_name','primitive']).resolved.value_counts())
"
```

If any task resolves under either strategy that doesn't resolve under any single primitive in Review1.csv → that's the headline pilot result.

---

## 2. Depth ablation 0.3 + 0.7 (Scope B, 960 runs)

### 2.1 Scope

8 primitives × 30 tasks × 2 runs × 2 depths = 960 runs at 20k budget.

Primitives:
- TR (truncation)
- SU-full (summarization)
- SU-partial (summarization-partial)
- SS (structured-summarize)
- SS-partial (structured-summarize-partial)
- TRC (tool-result-clear)
- TRC+SU (trc-su)
- TRC+SS (trc-ss)

Skipped (depth doesn't apply): FC, OTRC, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial.

### 2.2 Wrapper script — `scripts/run_depth_30_70.sh`

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/depth_30_70.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Depth 0.3 + 0.7 ablation starting ===" | tee -a "$LOG"

CONDS="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss"

# Use the 30-task ablation set (results/ablations/tasks.json)
for depth in 0.3 0.7; do
    pct=$(printf "%.0f" "$(echo "$depth * 100" | bc)")
    name="depth-${pct}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     20000 \
        --depth      "$depth" \
        --conditions $CONDS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     20000 \
        --depth      "$depth" \
        --conditions $CONDS \
        --eval-only \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] --- $name done ---" | tee -a "$LOG"
done

echo "[$(date)] === Depth 0.3 + 0.7 ablation complete — chaining to 5k budget ===" | tee -a "$LOG"
exec "$WS/scripts/run_5k_budget.sh"
```

### 2.3 Run + monitor

```bash
nohup scripts/run_depth_30_70.sh > logs/depth_30_70.out 2>&1 &
echo $! > logs/depth_30_70.pid
disown
```

**Active_runs.md update** at launch:

```markdown
### Depth ablation 0.3 + 0.7 (Scope B: 8 primitives @ 20k, 30 tasks)
- **Status:** RUNNING
- **PID:** see logs/depth_30_70.pid
- **Total runs:** 960
- **ETA:** ~16h
- **Output:** `results/ablations/depth-30/`, `results/ablations/depth-70/` (note: depth-70 already exists with TR/SU/TRC; new run extends to 8 primitives)
- **Log:** `logs/depth_30_70.log`
- **Chains to:** 5k budget
```

**Note**: `results/ablations/depth-70/` already has TR, SU, TRC data. Either (a) re-run those cells (cheap, 180 runs duplicated), or (b) add a `--skip-existing` flag and skip them. The wrapper as written re-runs them — accepted because run_experiment.py's `load_existing_results()` will detect the duplicates within the same ablation and skip.

### 2.4 Post-run analysis

After both phases complete:

```bash
# Build a depth-extended Review1
venv/bin/python3 Review1/build_review1.py truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss
# (with --depth-source flag if added; otherwise depth column distinguishes rows)

# Or write a separate depth_table.py that reads from results/ablations/depth-{30,40,50,60,70}/experiment_results.json
```

Per-budget dose-response figure:

```bash
venv/bin/python3 Review1/plot_depth_dose_response.py
# (to be written; produces fig_M_depth_dose_response.png with 5 depth points × 8 primitives)
```

---

## 3. 5k budget expansion (660 runs)

### 3.1 Feasibility check (BEFORE launching)

5k × 0.5 (depth=0.5) = 2.5k tokens after compression. Confirm this is above the system-prompt + initial-task floor:

```bash
venv/bin/python3 -c "
# Count tokens in the system prompt + a typical SWE-bench problem statement
import json
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.swebench import SWEBenchTask
# Or: just check the first few step_prompt_tokens from any prior 10k run
import pandas as pd
df = pd.read_csv('Review1/Review1.csv')
sub = df[(df.token_budget == 10000) & (df.primitive.isin(['TR','TRC']))]
import json
# step_prompt_tokens is a list-as-string in CSV; check the floor
floor = sub.total_prompt_tokens.min() / sub.step_count.max()
print(f'Approximate per-step token floor: {floor:.0f}')
"
```

If the per-step floor is > 2.5k, 5k is below the working floor and most cells will silent_crash. In that case, drop 5k and run only the originally planned 11 primitives at 5k as a "feasibility study" rather than full Pareto.

### 3.2 Wrapper script — `scripts/run_5k_budget.sh`

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/5k_budget.log"
mkdir -p "$WS/logs"
echo "[$(date)] === 5k budget expansion starting ===" | tee -a "$LOG"

CONDS="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-singles-5000 \
    --budget     5000 \
    --conditions $CONDS \
    2>&1 | tee -a "$LOG"

venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-singles-5000 \
    --budget     5000 \
    --conditions $CONDS \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === 5k budget done — Dobby queue complete ===" | tee -a "$LOG"
```

### 3.3 Run + monitor

Already chained from depth wrapper; if running standalone:

```bash
nohup scripts/run_5k_budget.sh > logs/5k_budget.out 2>&1 &
echo $! > logs/5k_budget.pid
disown
```

### 3.4 Post-run analysis

```bash
# Add 5k cells to Review1.csv
venv/bin/python3 Review1/build_review1.py
venv/bin/python3 Review1/sanity.py    # verify 5k cells aren't all silent_crash
```

If 5k cells show >50% silent_crash, the budget is below the working floor — report the floor as a finding ("compression breaks below 5k"), don't include in main paper figures.

---

## 4. Final Active_runs.md update

When the chain finishes (look for `=== 5k budget done — Dobby queue complete ===`):

- Move all three "Currently Running" entries to "Recently Completed"
- Set Dobby queue status to "idle, awaiting next assignment"

---

## 5. Failure recovery

- vLLM dies → restart it; re-run the wrapper. `load_existing_results()` skips completed keys.
- One condition systematically crashes → pull it out of the `CONDS` line; finish the rest; re-run that condition standalone.
- Disk fills → delete `results/ablations/{depth-40,depth-50,depth-60,depth-70}/` if confirmed unused (only TR/SU/TRC data; the depth-30 + depth-70 v2 will replace) — but check first.

---

## 6. Single-PID chain (preferred launch method)

After staggered pilot is confirmed-working manually, chain depth → 5k as a single PID:

```bash
# scripts/run_dobby_tail.sh
exec scripts/run_depth_30_70.sh   # which execs run_5k_budget.sh
```

```bash
nohup scripts/run_dobby_tail.sh > logs/dobby_tail.out 2>&1 &
echo $! > logs/dobby_tail.pid
disown
```

This way Dobby's tail (~27h) is one process, one log to monitor.
