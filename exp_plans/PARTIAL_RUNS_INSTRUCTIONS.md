# Partial-summary ablation launch plan

Goal: produce data for **SU-partial**, **SS-partial**, and the **SS gap-fill at 10k/20k** on the 30-task ablation set.

Total: **480 runs** (30 tasks × 2 runs/task × across budgets/conditions). Estimated wall-time at 16 workers: **~9–10 h**, similar in shape to the prior stacked ablation.

---

## 1 — Pre-implementation already in place (verify, don't redo)

The following code changes were made and validated in the prior chat. Sanity-check before launching.

### a) New primitives in `memory.py`
Run:
```bash
grep -nE "^def (_fit_tail|summarize_partial|structured_summarize_partial)\(" memory.py
```
Expect three matches. If missing, re-implement per the prior session's smoke-tested code.

### b) New dispatch branches in `mini-swe-agent/src/minisweagent/agents/default.py`
```bash
grep -nE 'elif _primitive == "(summarization_partial|structured_summarize_partial)"' \
     mini-swe-agent/src/minisweagent/agents/default.py
```
Expect two matches.

### c) New CONDITIONS in `scripts/run_experiment.py`
```bash
grep -nE '"(summarization-partial|structured-summarize-partial)"' scripts/run_experiment.py
```
Expect two matches in the `CONDITIONS = [ ... ]` list.

### d) Quick functional smoke test
```bash
venv/bin/python3 - <<'PY'
import memory as m
msgs = [{"role":"system","content":"sys "*50},
        {"role":"user","content":"task "*100}]
for i in range(20):
    msgs.append({"role":"assistant","content":f"a{i} "+"w "*200})
    msgs.append({"role":"user",     "content":f"u{i} "+"o "*300})

class Fake:
    def query(self, p): return {"content":"summary "*50,
        "extra":{"response":{"usage":{"prompt_tokens":200,"completion_tokens":100}}}}
    def format_message(self, role, content): return {"role":role,"content":content}

new, saved, *_ = m.summarize_partial(msgs, Fake(), 8000)
assert m.count_tokens(new) <= 8000 and saved > 0
new, saved, *_ = m.structured_summarize_partial(msgs, Fake(), 8000)
assert m.count_tokens(new) <= 8000 and saved > 0
print("OK")
PY
```
Must print `OK`. If it fails, **stop** and inspect — do not launch.

---

## 2 — Pre-flight

1. **vLLM server**: confirm Qwen3.5-35B-A3B vLLM endpoint is up (it's referenced from `config-qwen-vllm.yaml`).  Quick check:
   ```bash
   grep -E "url|model" config-qwen-vllm.yaml | head -5
   curl -s "$(grep -oP 'url:\s*\K\S+' config-qwen-vllm.yaml)/models" | head -c 200
   ```
   Expect a JSON response listing the model.

2. **Worker count**: `MAX_WORKERS` in `scripts/run_experiment.py` is 16.  Confirm no other large run is consuming workers:
   ```bash
   ps -ef | grep -E "run_experiment|swebench_single" | grep -v grep | wc -l
   ```
   Should be 0 (or only your own monitoring).

3. **Disk**: each run writes ~5–20 MB of trajectory.  Need ~10 GB free under `results/ablations/`.
   ```bash
   df -h results/
   ```

---

## 3 — Active_runs.md: update on launch (REQUIRED — standing rule)

**Before** kicking off the runs, append an entry to `Active_runs.md`:

```markdown
### Partial-summary ablation (SU-partial + SS-partial + SS gap-fill)
- **Status:** RUNNING
- **Started:** <YYYY-MM-DD HH:MM>
- **PID:** <fill in after launch>
- **Workers:** 16
- **Total runs:** 480 (30 tasks × 2 runs × {SU-partial × 3 budgets, SS-partial × 3 budgets, SS @ 10k+20k})
- **Output dirs:**
  - `results/ablations/partial-10k/`  (SU-partial, SS-partial, SS — 180 runs)
  - `results/ablations/partial-15k/`  (SU-partial, SS-partial — 120 runs)
  - `results/ablations/partial-20k/`  (SU-partial, SS-partial, SS — 180 runs)
- **Log:** `logs/partial_ablation.log`
- **ETA:** ~9–10h from start
```

You must also update this file on **kill** (status → KILLED with reason) and on **completion** (status → DONE, end time, summary stats).

---

## 4 — Launch script

Create `scripts/run_partial_ablation.sh`:

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

LOG="$WS/logs/partial_ablation.log"
mkdir -p "$WS/logs"
echo "[$(date)] Starting partial-summary ablation (SU-partial, SS-partial, SS gap-fill)" | tee -a "$LOG"

# Per-budget condition list:
#   10k & 20k: include SS to fill the gap (timing-10k/20k didn't run SS)
#   15k:        SS already covered by qwen3.5-35B-A3B_15k_Fullrun, only run partials
declare -A CONDS=(
    [10000]="summarization-partial structured-summarize-partial structured-summarize"
    [15000]="summarization-partial structured-summarize-partial"
    [20000]="summarization-partial structured-summarize-partial structured-summarize"
)

# Run order: 15k first (smallest, fastest), then 10k, then 20k
for budget in 15000 10000 20000; do
    name="partial-${budget}"
    conds="${CONDS[$budget]}"
    echo "[$(date)] === Starting $name with conditions: $conds ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $conds    \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === $name agent runs done — starting eval ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $conds    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Done with $name ===" | tee -a "$LOG"
done

echo "[$(date)] All partial-summary ablation runs complete" | tee -a "$LOG"
```

Make it executable:
```bash
chmod +x scripts/run_partial_ablation.sh
```

Launch in the background and capture the PID:
```bash
nohup bash scripts/run_partial_ablation.sh > logs/partial_ablation.stdout 2>&1 &
echo $! > logs/partial_ablation.pid
echo "Launched with PID $(cat logs/partial_ablation.pid)"
```

**Immediately update `Active_runs.md` with the PID.**

---

## 5 — Monitor progress

```bash
# Tail the log
tail -f logs/partial_ablation.log

# Periodic progress check (counts completed runs)
ls results/ablations/partial-15k/*/run_*/  2>/dev/null | wc -l   # max 120
ls results/ablations/partial-10k/*/run_*/  2>/dev/null | wc -l   # max 180
ls results/ablations/partial-20k/*/run_*/  2>/dev/null | wc -l   # max 180

# Check vLLM is still healthy
curl -s "$(grep -oP 'url:\s*\K\S+' config-qwen-vllm.yaml)/models" | head -c 100
```

If vLLM dies: kill the runner, restart vLLM, re-launch — runs are idempotent (already-completed (task,cond,run) tuples are skipped on re-launch).

---

## 6 — Post-run verification

After completion, run:

```bash
venv/bin/python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter

ROOT = Path("/home/rs67788/projects/agentCtx")
abl  = set(t["instance_id"] for t in json.load(open(ROOT/"results/ablations/tasks.json")))

for budget in (10000, 15000, 20000):
    p = ROOT / f"results/ablations/partial-{budget}/experiment_results.json"
    if not p.exists():
        print(f"{budget}: MISSING {p}"); continue
    runs = json.load(open(p))
    rs   = [r for r in runs if r.get("instance_id") in abl]
    print(f"\n=== partial-{budget} ===  total runs in ablation set: {len(rs)}")
    by_cond = Counter(r["condition"] for r in rs)
    for cond, n in by_cond.items():
        cond_rs = [r for r in rs if r["condition"] == cond]
        resolved = sum(1 for r in cond_rs if r.get("resolved") is True)
        uniq     = len(set(r["instance_id"] for r in cond_rs))
        print(f"  {cond:<32} n={n:>3}  uniq_tasks={uniq:>2}/30  resolved={resolved:>2} ({resolved/n*100:.0f}%)")
PY
```

Expected coverage:
- `partial-10k`: 3 conditions × 30 tasks × 2 runs = **180 runs**, 30 unique tasks each
- `partial-15k`: 2 conditions × 30 tasks × 2 runs = **120 runs**
- `partial-20k`: 3 conditions × 30 tasks × 2 runs = **180 runs**

If counts are short, look at the agent log for `LimitsExceeded` / vLLM disconnects and re-launch — the runner skips completed runs.

---

## 7 — On completion: update Active_runs.md (REQUIRED)

Append to the entry created in step 3:

```markdown
- **Status:** DONE
- **Ended:** <YYYY-MM-DD HH:MM>
- **Wall-time:** ~Xh Ym
- **Verified:** all 480 runs present, eval results present
- **Brief result table:** (resolve % per condition × budget — fill in from step 6 output)
```

If you killed it instead, update Status → KILLED with reason and which budgets completed.

---

## 8 — After verification: extend Review1.csv

Once the data is in, in a new chat, point to this file plus `Review1/build_review1.py` and ask the assistant to add the `fill_su_partial()`, `fill_ss_partial()`, and `fill_ss()` functions analogous to the existing `fill_su_full()`. Sources will be:

- SU-partial: `results/ablations/partial-{10,15,20}k/experiment_results.json`
- SS-partial: same files (filter by `condition == "structured-summarize-partial"`)
- SS at 10k/20k: `results/ablations/partial-{10,20}k/experiment_results.json` (filter by `condition == "structured-summarize"`)
- SS at 15k: `results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json` (already complete)

Each will append 60 rows × 3 budgets = 180 rows to Review1.csv (or 120 for SS — already 60 from 15k Fullrun).

---

## Risk notes

- **vLLM throughput**: prior stacked ablation hit ~50 runs/h at 16 workers.  At 480 runs that's 9.6 h.  If actual throughput drops below ~40/h sustainably, suspect a degraded vLLM (memory pressure, KV cache overflow) — restart it.
- **patches/default_memory_hook.patch** in the repo is **out of date** relative to the in-place edits. Do **not** re-apply the patch over the live `default.py` — it will overwrite the new dispatch branches. If you need to reset the agent code from a clean state, regenerate the patch first with `git diff mini-swe-agent/src/minisweagent/agents/default.py > patches/default_memory_hook.patch`.
- **Idempotency**: re-running the launch script is safe — the runner skips (task, condition, run_num) tuples already present in `experiment_results.json`.  Use this if anything dies mid-run.
