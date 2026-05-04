# Full-task expansion: extend Review1 from 30 → 100 tasks

Self-contained launch plan for a fresh chat. Owner: ritul@utexas.edu.
Created 2026-04-30. Workspace: `/home/rs67788/projects/agentCtx`.

---

## 0. Goal

Right now `Review1/Review1.csv` covers 30 tasks × 35 cells × 2 runs = 2 100 rows.
We want to extend it to **100 tasks × 35 cells × 2 runs = 7 000 rows** so we can rerun:

- `Review1/sanity.py`
- `Review1/paired_analysis.py`
- `Review1/routing_evidence.py` (oracle-of-k)
- `Review1/predictability_sprint.py` (the n=15-19 per-class sample sizes are too small at 30; predictability verdict at 100 will be definitive)

The 100-task list is `/home/rs67788/projects/agentCtx/task_lists/selected_tasks.json` (already pinned).
The 70 new tasks = `selected_tasks.json` minus the 30 currently in `Review1/Review1.csv`.

35 cells:
- 11 primitives × 3 budgets: `truncation, summarization-full, summarization-partial, structured-summarize, structured-summarize-partial, tool-result-clear, trc-su, trc-ss, otrc-tr, otrc-su-partial, otrc-ss-partial` × {10000, 15000, 20000}
- 2 ∞-budget primitives: `full-context`, `online-trc`

---

## 1. Pre-flight checklist (run BEFORE launching)

```bash
cd /home/rs67788/projects/agentCtx

# 1. vLLM model server up?
curl -s http://localhost:8000/v1/models | head -1   # expect a JSON model list

# 2. Disk space ≥150 GB free?
df -h /home/rs67788/projects/agentCtx

# 3. Active runs file empty?
head -10 Active_runs.md

# 4. venv usable?
venv/bin/python3 -c "import pandas, numpy; print('ok')"

# 5. Git status clean for tracked files?  (untracked OK)
git status -s | grep -E '^[ MD]' | head
```

If any of (1)–(4) fails, stop and fix before continuing. (5) is informational.

---

## 2. Generate the new-task list and coverage inventory

This step (a) produces the 70-task list and (b) detects the 448 existing runs that don't need re-running.

Save as `/home/rs67788/projects/agentCtx/scripts/p100_inventory.py`:

```python
"""Phase-100 inventory.

Outputs:
  task_lists/p100_new_tasks.json        — the 70 new tasks (selected_tasks.json minus Review1's 30)
  scripts/p100_existing_runs.json    — for each (cond, budget): list of (task, run_num) already on disk
  scripts/p100_seed_dir.sh           — bash script that symlinks existing trajectory files into the
                                       new ablation dirs so run_experiment.py auto-skips them
"""
import json, re, pathlib
from collections import defaultdict

ROOT = pathlib.Path('/home/rs67788/projects/agentCtx')

# 1) New tasks
full = json.load(open(ROOT / 'task_lists' / 'selected_tasks.json'))
import pandas as pd
df = pd.read_csv(ROOT / 'Review1/Review1.csv')
cur = set(df.task_name.unique())
new_tasks = [t for t in full if t['instance_id'] not in cur]
assert len(new_tasks) == 70
(ROOT / 'task_lists' / 'p100_new_tasks.json').write_text(json.dumps(new_tasks, indent=2))
print(f'wrote task_lists/p100_new_tasks.json  ({len(new_tasks)} tasks)')

# 2) Slug → (condition string used by run_experiment.py, primitive label, budget rule)
SLUG_TO_COND = {
    'truncation':                       'truncation',
    'summarization':                    'summarization-full',
    'summarization-partial':            'summarization-partial',
    'structured-summarize':             'structured-summarize',
    'structured-summarize-partial':     'structured-summarize-partial',
    'tool-result-clear':                'tool-result-clear',
    'trc-su':                           'trc-su',
    'trc-summarize':                    'trc-su',
    'trc-ss':                           'trc-ss',
    'trc-structured-summarize':         'trc-ss',
    'full-context':                     'full-context',
    'online-trc':                       'online-trc',
    'online_trc':                       'online-trc',
    'otrc-tr':                          'otrc-tr',
    'otrc-truncation':                  'otrc-tr',
    'otrc-su-partial':                  'otrc-su-partial',
    'otrc-summarization-partial':       'otrc-su-partial',
    'otrc-ss-partial':                  'otrc-ss-partial',
    'otrc-structured-summarize-partial':'otrc-ss-partial',
}

def budget_from_dir(d: pathlib.Path):
    n = d.name.lower()
    if '20000' in n or '_20k' in n: return 20000
    if '15000' in n or '_15k' in n: return 15000
    if '10000' in n or '_10k' in n: return 10000
    if 'fullrun' in n: return 15000
    return None

new_ids = {t['instance_id'] for t in new_tasks}
existing = defaultdict(list)   # (cond, budget) → [(task, run, src_traj_path, src_token_log, src_eval_dir, src_agent_log)]

# Layout A: results/<exp_dir>/eval/<prefix>.<task>__<slug>__r<n>.json
for p in (ROOT / 'results').rglob('*.json'):
    s = str(p)
    if '/eval/' not in s or 'Llama' in s: continue
    m = re.search(r'\.((?:django__django|sympy__sympy|scikit-learn__scikit-learn)-\d+)__([a-z0-9_-]+)__r(\d)\.json', s)
    if not m: continue
    tid, slug, run = m.group(1), m.group(2), int(m.group(3))
    if tid not in new_ids: continue
    cond = SLUG_TO_COND.get(slug)
    if not cond: continue
    if cond in ('full-context', 'online-trc'):
        budget = 999999999
    else:
        budget = budget_from_dir(p.parent.parent)
        if budget is None: continue
    existing[(cond, budget)].append((tid, run, str(p)))

# Layout B: results/ablations/<exp>/<task>/<slug>/run_<k>/trajectory.json
for traj in (ROOT / 'results/ablations').rglob('trajectory.json'):
    parts = traj.parts
    try:
        i = parts.index('ablations')
        exp, task, slug = parts[i+1], parts[i+2], parts[i+3]
        run = int(parts[i+4].split('_')[1])
    except (ValueError, IndexError): continue
    if task not in new_ids: continue
    cond = SLUG_TO_COND.get(slug)
    if not cond: continue
    if cond in ('full-context', 'online-trc'):
        budget = 999999999
    else:
        budget = budget_from_dir(ROOT / 'results/ablations' / exp)
        if budget is None: continue
    existing[(cond, budget)].append((task, run, str(traj)))

# Print summary
print()
print(f'{"cell":<40} {"existing":>10}')
print('-'*52)
for (cond, b), entries in sorted(existing.items()):
    print(f'{cond+"@"+str(b):<40} {len(entries):>10}')
print(f'\nTotal existing runs to reuse: {sum(len(v) for v in existing.values())}')

(ROOT / 'scripts/p100_existing_runs.json').write_text(
    json.dumps({f'{c}|{b}': v for (c, b), v in existing.items()}, indent=2))
print('wrote scripts/p100_existing_runs.json')
```

Run it:

```bash
cd /home/rs67788/projects/agentCtx
venv/bin/python3 scripts/p100_inventory.py
```

Expected output: `~448 total existing runs to reuse`, plus `task_lists/p100_new_tasks.json` with 70 entries.

---

## 3. Seed the new ablation dirs from existing runs

This step produces a script that puts each existing trajectory + eval JSON into the new ablation dir under the layout `run_experiment.py` expects, so its `load_existing_results()` will mark them done and skip re-running.

Save as `/home/rs67788/projects/agentCtx/scripts/p100_seed.py`:

```python
"""Seed new ablation dirs from existing runs so run_experiment.py auto-skips them.

For each (cond, budget, task, run) in scripts/p100_existing_runs.json:
  1. Determine target ablation dir name (see PHASE_MAP below).
  2. Symlink the source trajectory.json + token_log.json + agent.log into
     results/ablations/<target>/<task>/<cond>/run_<n>/
  3. Append a row to <target>/experiment_results.json so load_existing_results
     marks the run done.
  4. Symlink/copy the source eval JSON into <target>/eval/.
"""
import json, os, pathlib, re, shutil

ROOT = pathlib.Path('/home/rs67788/projects/agentCtx')

# Map (cond, budget) → target ablation dir name. Keep budget in name.
def target_ablation(cond: str, budget: int) -> str:
    if budget >= 999999998:
        return 'p100-inf'                 # FC and OTRC share the same dir
    if cond in ('truncation', 'summarization-full', 'summarization-partial',
                'structured-summarize', 'structured-summarize-partial'):
        return f'p100-singles-{budget}'
    if cond in ('tool-result-clear', 'trc-su', 'trc-ss'):
        return f'p100-trc-{budget}'
    if cond in ('otrc-tr', 'otrc-su-partial', 'otrc-ss-partial'):
        return f'p100-otrc-{budget}'
    raise ValueError(cond)

existing = json.loads((ROOT / 'scripts/p100_existing_runs.json').read_text())

seeded = 0
for cell, entries in existing.items():
    cond, budget = cell.split('|')
    budget = int(budget)
    target = target_ablation(cond, budget)
    tdir   = ROOT / 'results/ablations' / target
    (tdir / 'eval').mkdir(parents=True, exist_ok=True)

    rows_path = tdir / 'experiment_results.json'
    rows = json.loads(rows_path.read_text()) if rows_path.exists() else []
    keys = {r['key'] for r in rows}

    for task, run, src in entries:
        key = f'{task}__{cond}__r{run}'
        if key in keys: continue
        run_dir = tdir / task / cond / f'run_{run}'
        run_dir.mkdir(parents=True, exist_ok=True)

        src_path = pathlib.Path(src)
        # Detect layout: eval JSON vs trajectory.json
        if src_path.name == 'trajectory.json':
            traj_src = src_path
            tlog_src = src_path.parent / 'token_log.json'
            alog_src = src_path.parent / 'agent.log'
            # eval JSON is usually colocated in <exp>/eval/<prefix>.<task>__<slug>__r<n>.json
            # — search for it
            eval_candidates = list((src_path.parents[3] / 'eval').glob(f'*.{task}__*__r{run}.json'))
            eval_src = eval_candidates[0] if eval_candidates else None
        else:
            # eval JSON path; trajectory lives in trajectories/<task>/<slug>/run_<n>/
            traj_src = src_path.parent.parent / 'trajectories' / task / cond / f'run_{run}' / 'trajectory.json'
            if not traj_src.exists():
                # try alternative
                cand = list(src_path.parents[1].rglob(f'{task}/{cond}/run_{run}/trajectory.json'))
                traj_src = cand[0] if cand else None
            tlog_src = traj_src.parent / 'token_log.json' if traj_src else None
            alog_src = traj_src.parent / 'agent.log' if traj_src else None
            eval_src = src_path

        # Symlink files
        for srcf, name in [(traj_src, 'trajectory.json'),
                           (tlog_src, 'token_log.json'),
                           (alog_src, 'agent.log')]:
            if srcf and srcf.exists() and not (run_dir / name).exists():
                os.symlink(srcf, run_dir / name)

        if eval_src and eval_src.exists():
            dst_eval = tdir / 'eval' / f'qwen35-a3b.{task}__{cond}__r{run}.json'
            if not dst_eval.exists():
                os.symlink(eval_src, dst_eval)

        # Append to experiment_results.json (minimal fields run_experiment.py checks)
        rows.append({'key': key, 'instance_id': task, 'condition': cond, 'run_num': run,
                     'budget': budget, 'seeded_from': str(src_path)})
        keys.add(key)
        seeded += 1

    rows_path.write_text(json.dumps(rows, indent=2))

print(f'seeded {seeded} runs across {len(existing)} cells')
```

Run it:

```bash
venv/bin/python3 scripts/p100_seed.py
```

After this, the new ablation dirs (`p100-singles-*`, `p100-trc-*`, `p100-otrc-*`, `p100-inf`) contain symlinks for the 448 reusable runs.

---

## 4. Wrapper scripts (one chain, three phases)

### 4.1 `scripts/run_p100_phase1.sh` — singles + ∞ baselines

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase1.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 1: singles + ∞ baselines on 70 new tasks ===" | tee -a "$LOG"

CONDS_BUDGETED="truncation summarization-full summarization-partial structured-summarize structured-summarize-partial"
CONDS_INF="full-context online-trc"

# 15k → 10k → 20k for budgeted
for budget in 15000 10000 20000; do
    name="p100-singles-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

# Infinite-budget conditions, single dir
echo "[$(date)] --- p100-inf ---" | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-inf \
    --budget     999999999 \
    --tasks-file task_lists/p100_new_tasks.json \
    --conditions $CONDS_INF \
    2>&1 | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation   p100-inf \
    --budget     999999999 \
    --tasks-file task_lists/p100_new_tasks.json \
    --conditions $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Phase 1 done — chaining to phase 2 ===" | tee -a "$LOG"
exec "$WS/scripts/run_p100_phase2.sh"
```

### 4.2 `scripts/run_p100_phase2.sh` — TRC stack

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase2.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 2: TRC stack ===" | tee -a "$LOG"

CONDS="tool-result-clear trc-su trc-ss"

for budget in 15000 10000 20000; do
    name="p100-trc-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Phase 2 done — chaining to phase 3 ===" | tee -a "$LOG"
exec "$WS/scripts/run_p100_phase3.sh"
```

### 4.3 `scripts/run_p100_phase3.sh` — OTRC stack

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/p100_phase3.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Phase 3: OTRC stack ===" | tee -a "$LOG"

CONDS="otrc-tr otrc-su-partial otrc-ss-partial"

for budget in 15000 10000 20000; do
    name="p100-otrc-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --budget     "$budget" \
        --tasks-file task_lists/p100_new_tasks.json \
        --conditions $CONDS \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === ALL P100 PHASES COMPLETE ===" | tee -a "$LOG"
```

### 4.4 Master launcher `scripts/run_p100_chain.sh`

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"
mkdir -p "$WS/logs"

# Pre-flight: all wrappers exist and are executable
for s in run_p100_phase1.sh run_p100_phase2.sh run_p100_phase3.sh; do
    test -x "$WS/scripts/$s" || { echo "missing or non-exec: $s"; exit 1; }
done

# Inventory + seed (idempotent — re-running is safe)
venv/bin/python3 scripts/p100_inventory.py
venv/bin/python3 scripts/p100_seed.py

# Hand off to phase 1; phase 1 execs phase 2 execs phase 3
exec "$WS/scripts/run_p100_phase1.sh"
```

Make all four executable:

```bash
chmod +x scripts/run_p100_phase{1,2,3}.sh scripts/run_p100_chain.sh
```

---

## 5. Launch + monitor

```bash
cd /home/rs67788/projects/agentCtx
nohup scripts/run_p100_chain.sh > logs/p100_chain.out 2>&1 &
echo $! > logs/p100_chain.pid
disown
```

**Update `Active_runs.md`** immediately (move any prior "Currently Running" rows to "Recently Completed" first):

```markdown
## Currently Running

### P100 expansion: 70 new tasks × 35 cells × 2 runs (4 452 new runs)
- **Status:** RUNNING
- **Started:** YYYY-MM-DD HH:MM CDT
- **PID:** <pid from logs/p100_chain.pid>
- **Workers:** 16
- **Phases:** 1 (singles+∞) → 2 (TRC stack) → 3 (OTRC stack), chained via exec
- **Logs:** `logs/p100_chain.out`, `logs/p100_phase{1,2,3}.log`
- **Output dirs:** `results/ablations/p100-singles-{10000,15000,20000}/`, `p100-trc-*`, `p100-otrc-*`, `p100-inf/`
- **ETA:** ~65h wall-clock (theoretical 41h × 1.6× wrapper overhead). Aim end ~3 days.
```

**Monitor cadence:**
```bash
# every few hours
tail -n 30 /home/rs67788/projects/agentCtx/logs/p100_chain.out
ls /home/rs67788/projects/agentCtx/results/ablations/p100-* 2>/dev/null
ps -p $(cat /home/rs67788/projects/agentCtx/logs/p100_chain.pid) -o pid,etime,cmd
nvidia-smi
```

**On phase completion** (look for `=== Phase N done ===` in the log), append a row to `Active_runs.md`. **On full completion** (look for `=== ALL P100 PHASES COMPLETE ===`), move the entry from "Currently Running" to "Recently Completed".

---

## 6. Post-run rebuild + re-analyse

Once all three phases are done:

```bash
cd /home/rs67788/projects/agentCtx

# 6.1 Rebuild Review1.csv from all 35 cells × 100 tasks.
# build_review1.py already supports incremental fills; run it for each primitive.
# (See its CLI: python3 Review1/build_review1.py --help)
venv/bin/python3 Review1/build_review1.py   # without args = rebuild all

# 6.2 Sanity check
venv/bin/python3 Review1/sanity.py
# → Review1/sanity_report.md  (expect 35 cells × 100 tasks × 2 runs = 7000 rows)

# 6.3 Paired analysis (CIs should tighten substantially: ~12pp → ~6pp)
venv/bin/python3 Review1/paired_analysis.py
# → Review1/paired_analysis_report.md

# 6.4 Routing evidence (oracle-of-k, will tell us if k=2 still saturates at n=100)
venv/bin/python3 Review1/routing_evidence.py
# → Review1/figures/fig_M{1,2,3}_*.png + report

# 6.5 Predictability sprint (the actual reason we're scaling up)
venv/bin/python3 Review1/predictability_sprint.py
# → Review1/predictability_report.md
# At n=100, the per-class samples should be ~30-50 per class for 15k pair —
# enough to tell if features genuinely separate or not.
```

---

## 7. Decision points after the run

These don't need executing; just be ready:

| if predictability_report.md says... | paper move |
|---|---|
| LOO accuracy ≥ baseline + 10pp on the 15k pair | routing is buildable — keep the routing section, draft a controller |
| LOO accuracy ≈ baseline ± 5pp | headroom is unrecoverable from observables — drop routing, lead with "pick the average winner" + the two robust effects (SU-partial fix, FC vs TRC+SS@20k) |
| oracle k=2 no longer saturates at 87/87/90% | routing structure changed at n=100 — re-examine M3 |

Whichever path: update `PaperSections/` after consulting Ritul (do not write to `PaperSections/` without showing draft content first — see `feedback_paper_edits.md`).

---

## 8. If something breaks

- **vLLM dies mid-run**: phase wrapper will fail; `experiment_results.json` retains progress. Restart by re-running `scripts/run_p100_chain.sh` — inventory + seed steps are idempotent and `run_experiment.py` skips completed keys.
- **One condition crashes systematically**: pull it out of the `CONDS` line in the failing phase wrapper, finish, then re-run that condition standalone.
- **Disk fills up**: delete intermediate `results/ablations/{depth,timing,timing-10k,timing-20k}/` if confirmed unused (these are pre-Review1 ablations) — but check with Ritul first.
- **Need to abort cleanly**: `kill $(cat logs/p100_chain.pid)`. Trajectories on disk are kept; restart later.

---

## 9. Files this plan creates

- `scripts/p100_inventory.py`              (created in §2)
- `scripts/p100_seed.py`                   (created in §3)
- `task_lists/p100_new_tasks.json`            (created by inventory)
- `scripts/p100_existing_runs.json`        (created by inventory)
- `scripts/run_p100_phase1.sh`             (created in §4.1)
- `scripts/run_p100_phase2.sh`             (created in §4.2)
- `scripts/run_p100_phase3.sh`             (created in §4.3)
- `scripts/run_p100_chain.sh`              (created in §4.4)
- `logs/p100_chain.out`, `logs/p100_phase{1,2,3}.log`, `logs/p100_chain.pid`
- `results/ablations/p100-singles-{10k,15k,20k}/`
- `results/ablations/p100-trc-{10k,15k,20k}/`
- `results/ablations/p100-otrc-{10k,15k,20k}/`
- `results/ablations/p100-inf/`
- ~70 new entries × 35 cells × 2 runs of trajectory + token_log + agent.log + eval JSON

Approximate disk: 4 452 runs × ~10 MB/run ≈ 45 GB.
