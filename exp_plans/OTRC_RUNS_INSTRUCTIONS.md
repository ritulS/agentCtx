# OTRC stacked ablation launch plan

Goal: produce data for **OTRC+TR**, **OTRC+SU-partial**, **OTRC+SS-partial** on the 30-task ablation set across 10k / 15k / 20k budgets.

Total: **540 runs** (3 conditions × 3 budgets × 30 tasks × 2 runs). Estimated wall-time at 16 workers: **~10–11 h**.

**Run only after the partial-summary ablation (`PARTIAL_RUNS_INSTRUCTIONS.md`) completes.** Do not launch concurrently — both consume all 16 workers and the same vLLM endpoint.

---

## 0 — Design context (read before launch)

The three OTRC variants are stage-1 + stage-2 stacks:
- **Stage 1 (every step)**: OTRC freeze-window clears `messages[-9]` (result from step n−5). Runs unconditionally for all OTRC family primitives.
- **Stage 2 (budget-triggered)**: when `count_tokens(messages) > budget`, a fallback fires:
  - `otrc-tr` → `truncate()` (drops oldest messages from the front)
  - `otrc-su-partial` → `summarize_partial()` (summarizes head, keeps budget-fitting tail verbatim)
  - `otrc-ss-partial` → `structured_summarize_partial()` (same, with structured schema)

**SU-full and SS-full are deliberately not run as OTRC fallbacks** — they collapse the freeze window and break OTRC's recency contract. Partial variants compose coherently; full variants would be a dishonest comparison.

All three conditions reuse `config-online-trc.yaml` (agent prompts expect cleared-tool stubs).

---

## 1 — Pre-implementation already in place (verify, don't redo)

The following code changes were made and validated in the prior chat. Sanity-check before launching.

### a) Partial-summary primitives in `memory.py` (from earlier today)
```bash
grep -nE "^def (_fit_tail|summarize_partial|structured_summarize_partial)\(" memory.py
```
Expect three matches.

### b) OTRC freeze-window guard in `default.py`
```bash
grep -nE "_OTRC_FAMILY" mini-swe-agent/src/minisweagent/agents/default.py
```
Expect 2 matches: the tuple definition and the guard `if _primitive in _OTRC_FAMILY`.

### c) New OTRC dispatch branches in `default.py`
```bash
grep -nE 'elif _primitive == "online_trc_(summarize_partial|structured_summarize_partial)"' \
     mini-swe-agent/src/minisweagent/agents/default.py
```
Expect 2 matches.

### d) New CONDITIONS in `run_experiment.py`
```bash
grep -nE '"(otrc-tr|otrc-su-partial|otrc-ss-partial)"' scripts/run_experiment.py
```
Expect 3 matches in the `CONDITIONS = [ ... ]` list, each with `"config": WORKSPACE_ROOT / "config-online-trc.yaml"`.

### e) Functional smoke test (covers OTRC family + new dispatch)
```bash
venv/bin/python3 - <<'PY'
import re
src = open("mini-swe-agent/src/minisweagent/agents/default.py").read()

m = re.search(r'_OTRC_FAMILY\s*=\s*\((.*?)\)', src, re.DOTALL)
assert m, "OTRC_FAMILY tuple missing"
fam = m.group(1)
for name in ("online_trc",
             "online_trc_summarize_partial",
             "online_trc_structured_summarize_partial"):
    assert name in fam, f"missing {name} in _OTRC_FAMILY"
    if name != "online_trc":
        assert f'_primitive == "{name}"' in src, f"missing dispatch branch for {name}"

import memory as m2
class Fake:
    def query(self, p): return {"content":"summary " * 50,
        "extra":{"response":{"usage":{"prompt_tokens":200,"completion_tokens":100}}}}
    def format_message(self, role, content): return {"role":role, "content":content}

msgs = [{"role":"system","content":"sys " * 50},
        {"role":"user",  "content":"task " * 100}]
for i in range(20):
    msgs.append({"role":"assistant","content":f"a{i} " + "w " * 200})
    msgs.append({"role":"user",     "content":f"u{i} " + "o " * 300})

new, saved, *_ = m2.summarize_partial(msgs, Fake(), 8000)
assert m2.count_tokens(new) <= 8000 and saved > 0
new, saved, *_ = m2.structured_summarize_partial(msgs, Fake(), 8000)
assert m2.count_tokens(new) <= 8000 and saved > 0
print("OK")
PY
```
Must print `OK`. If it fails, **stop** and inspect — do not launch.

---

## 2 — Pre-flight

1. **Confirm partial ablation completed** — `Active_runs.md` should show its entry as `DONE` and the partial result dirs should exist:
   ```bash
   ls results/ablations/partial-{10000,15000,20000}/experiment_results.json 2>&1
   ```
   All three should exist. If any are missing, the partial run did not finish; address that first.

2. **vLLM server**:
   ```bash
   grep -E "url|model" config-online-trc.yaml | head -5
   curl -s "$(grep -oP 'url:\s*\K\S+' config-online-trc.yaml)/models" | head -c 200
   ```

3. **Worker count**: confirm no other large run is active.
   ```bash
   ps -ef | grep -E "run_experiment|swebench_single" | grep -v grep | wc -l
   ```
   Should be 0.

4. **Disk**: ~12 GB free under `results/ablations/`.
   ```bash
   df -h results/
   ```

---

## 3 — Active_runs.md: update on launch (REQUIRED — standing rule)

Append to `Active_runs.md`:

```markdown
### OTRC stacked ablation (OTRC+TR + OTRC+SU-partial + OTRC+SS-partial)
- **Status:** RUNNING
- **Started:** <YYYY-MM-DD HH:MM>
- **PID:** <fill in after launch>
- **Workers:** 16
- **Total runs:** 540 (30 tasks × 2 runs × 3 conditions × 3 budgets)
- **Output dirs:**
  - `results/ablations/otrc-stacked-10000/`  (180 runs)
  - `results/ablations/otrc-stacked-15000/`  (180 runs)
  - `results/ablations/otrc-stacked-20000/`  (180 runs)
- **Conditions:** otrc-tr, otrc-su-partial, otrc-ss-partial (all use config-online-trc.yaml)
- **Log:** `logs/otrc_stacked_ablation.log`
- **ETA:** ~10–11h from start
```

Update on **kill** (status → KILLED with reason) and on **completion** (status → DONE, end time, summary stats).

---

## 4 — Launch script

Create `scripts/run_otrc_stacked_ablation.sh`:

```bash
#!/bin/bash
set -euo pipefail
WS="/home/rs67788/projects/agentCtx"
cd "$WS"

LOG="$WS/logs/otrc_stacked_ablation.log"
mkdir -p "$WS/logs"
echo "[$(date)] Starting OTRC stacked ablation (otrc-tr, otrc-su-partial, otrc-ss-partial)" | tee -a "$LOG"

CONDS="otrc-tr otrc-su-partial otrc-ss-partial"

# Run order: 15k first (intermediate, fastest path through the data), then 10k, then 20k
for budget in 15000 10000 20000; do
    name="otrc-stacked-${budget}"
    echo "[$(date)] === Starting $name with conditions: $CONDS ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $CONDS    \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === $name agent runs done — starting eval ===" | tee -a "$LOG"
    python3 scripts/run_experiment.py \
        --ablation   "$name"   \
        --budget     "$budget" \
        --conditions $CONDS    \
        --eval-only            \
        2>&1 | tee -a "$LOG"
    echo "[$(date)] === Done with $name ===" | tee -a "$LOG"
done

echo "[$(date)] All OTRC stacked ablation runs complete" | tee -a "$LOG"
```

Make executable and launch:
```bash
chmod +x scripts/run_otrc_stacked_ablation.sh
nohup bash scripts/run_otrc_stacked_ablation.sh > logs/otrc_stacked_ablation.stdout 2>&1 &
echo $! > logs/otrc_stacked_ablation.pid
echo "Launched with PID $(cat logs/otrc_stacked_ablation.pid)"
```

**Immediately update `Active_runs.md` with the PID.**

---

## 5 — Monitor progress

```bash
# Tail the log
tail -f logs/otrc_stacked_ablation.log

# Per-budget progress (each maxes at 180 run dirs)
ls results/ablations/otrc-stacked-15000/*/run_*/  2>/dev/null | wc -l
ls results/ablations/otrc-stacked-10000/*/run_*/  2>/dev/null | wc -l
ls results/ablations/otrc-stacked-20000/*/run_*/  2>/dev/null | wc -l

# Confirm vLLM is healthy
curl -s "$(grep -oP 'url:\s*\K\S+' config-online-trc.yaml)/models" | head -c 100
```

If vLLM dies: kill the runner, restart vLLM, re-launch — runs are idempotent (already-completed (task,cond,run) tuples are skipped on re-launch).

---

## 6 — Post-run verification

```bash
venv/bin/python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter

ROOT = Path("/home/rs67788/projects/agentCtx")
abl  = set(t["instance_id"] for t in json.load(open(ROOT/"results/ablations/tasks.json")))

for budget in (10000, 15000, 20000):
    p = ROOT / f"results/ablations/otrc-stacked-{budget}/experiment_results.json"
    if not p.exists():
        print(f"{budget}: MISSING {p}"); continue
    runs = json.load(open(p))
    rs   = [r for r in runs if r.get("instance_id") in abl]
    print(f"\n=== otrc-stacked-{budget} ===  total runs in ablation set: {len(rs)}")
    by_cond = Counter(r["condition"] for r in rs)
    for cond, n in by_cond.items():
        cond_rs = [r for r in rs if r["condition"] == cond]
        resolved = sum(1 for r in cond_rs if r.get("resolved") is True)
        uniq     = len(set(r["instance_id"] for r in cond_rs))
        otrc_clears = [r.get("online_trc_clears", 0) for r in cond_rs]
        print(f"  {cond:<22} n={n:>3}  uniq_tasks={uniq:>2}/30  resolved={resolved:>2} ({resolved/n*100:.0f}%)  "
              f"otrc_clears median={sorted(otrc_clears)[len(otrc_clears)//2]}")
PY
```

Expected coverage per budget: 3 conditions × 30 tasks × 2 runs = **180 runs**, 30 unique tasks each. The median `otrc_clears` should be > 0 (proves the freeze-window hook fired).

If counts are short, re-launch the script — it skips completed runs.

---

## 7 — On completion: update Active_runs.md (REQUIRED)

```markdown
- **Status:** DONE
- **Ended:** <YYYY-MM-DD HH:MM>
- **Wall-time:** ~Xh Ym
- **Verified:** all 540 runs present, eval results present, OTRC clears > 0
- **Brief result table:** (resolve % per condition × budget — fill in from step 6 output)
```

If killed mid-run, set Status → KILLED with reason and which budgets completed.

---

## 8 — After verification: extend Review1.csv

In a new chat, point to this file plus `Review1/build_review1.py` and ask the assistant to add `fill_otrc_tr()`, `fill_otrc_su_partial()`, `fill_otrc_ss_partial()` analogous to `fill_trc_su()` / `fill_trc_ss()`. Sources will be:

- `results/ablations/otrc-stacked-{10000,15000,20000}/experiment_results.json`, filtered by:
  - `condition == "otrc-tr"` → primitive label `OTRC+TR`
  - `condition == "otrc-su-partial"` → primitive label `OTRC+SU-partial`
  - `condition == "otrc-ss-partial"` → primitive label `OTRC+SS-partial`

Each fills 60 rows × 3 budgets = **180 rows per condition, 540 rows total** appended to `Review1/Review1.csv`.

---

## Risk notes

- **vLLM throughput**: prior stacked ablation hit ~50 runs/h at 16 workers. 540 runs ≈ 10.8 h. If actual throughput drops below ~40/h, suspect a degraded vLLM and restart it.
- **`patches/default_memory_hook.patch` in the repo is stale** relative to the in-place edits. Do **not** re-apply it — it will overwrite the OTRC family guard and the new dispatch branches. If you need to reset agent code from a clean state, regenerate the patch first with `git diff mini-swe-agent/src/minisweagent/agents/default.py > patches/default_memory_hook.patch`.
- **Idempotency**: re-running the launch script is safe — the runner skips (task, condition, run_num) tuples already present in `experiment_results.json`. Use this if anything dies mid-run.
- **OTRC freeze-window hook fires inside `query()`** — if the runner crashes between the hook firing and the LLM call returning, the cleared message is persisted in `self.messages` but the step counter advances on the next call, so re-running picks up cleanly.
