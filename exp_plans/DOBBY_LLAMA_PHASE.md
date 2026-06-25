# Dobby — Llama 3.3 70B model-expansion phase

**Scope:** Mirror Qwen2.5-7B Phase 1 — the full 3,900-run grid on ABL-30:
- 2,700 depth-tunable (5 prims × 3 budgets × 3 depths × 30 tasks × 2 runs)
- 1,080 depth-invariant (6 prims × 3 budgets × 1 depth × 30 × 2)
- 120 ∞-budget baselines (FC + OTRC × 30 × 2)

**Where:** Dobby (4× A100 80GB PCIe, TP=4). Llama 3.3 70B weights already
cached in `~/.cache/huggingface/hub/models--meta-llama--Llama-3.3-70B-Instruct`.
No vLLM currently running on Dobby — clean slate.

**Why on Dobby instead of Albus:** explicit user direction (this turn).
Original ALBUS_PLAN §2 had this on Albus, but Albus is now hosting other
work; main-model runs on Dobby are complete (since 2026-05-15), so Dobby's
A100s are free.

**Run grid identical to Qwen2.5-7B** — see [project_runs_checklist.md](../project_runs_checklist.md)
"Qwen2.5-7B" section for the cohort/depth/budget structure that this phase
replicates. Only differences: model identity, calibrated-budget values
(TBD), and the serving host.

---

## Pre-launch checklist (do before §a)

### 0.1 — Patch run_experiment.py for per-model OTRC config (5 min, code change)

`scripts/run_experiment.py` hardcodes `config-online-trc.yaml` for the
OTRC conditions (`online-trc`, `otrc-tr`, `otrc-su-partial`,
`otrc-ss-partial`). That YAML points at Qwen3.5-A3B port 8000. Without a
patch, those 4 conditions will hit the wrong model during Llama runs.

**Minimal fix:** add a CLI flag `--otrc-config PATH` that overrides the
hardcoded `config-online-trc.yaml` per run. Pass
`--otrc-config config-online-trc-llama33.yaml` from the Llama launcher
scripts. ~10-line change in `run_experiment.py` (parse flag, override the
4 hardcoded paths at startup).

**Alternative if minimal-fix is too invasive:** rename
`config-online-trc.yaml` → `config-online-trc-qwen.yaml`, symlink
`config-online-trc.yaml` → `config-online-trc-llama33.yaml` during Llama
runs and back after. Fragile; flag-based is cleaner.

### 0.2 — Pre-flight pilot (10 min)

Once vLLM is up (§1), run a 5-task FC pilot to validate median per-run
latency before committing the FC + OTRC ∞ baselines (Llama 70B is much
slower than Qwen2.5-7B; expect 800-1500s/run not 300-500s).

```bash
venv/bin/python3 scripts/run_experiment.py \
    --ablation     llama33-70b-pilot \
    --model-tag    llama33-70b \
    --agent-config config-llama33-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --n-tasks      5 \
    --conditions   full-context \
    | tee logs/llama33_70b_pilot.log
```

If median per-run latency is >2500s, post a warning to `Active_runs.md`
and revisit before launching §a.

### 0.3 — Disk space

3,900 runs × ~100KB trajectory = ~400MB. Plus eval snapshots = ~600MB
total. Negligible — Dobby has TB-scale `results/`.

---

## §1 — vLLM serving setup (~5 min for serving startup, model already on disk)

`scripts/start_vllm_llama33_70b.sh` brings up Llama 3.3 70B on port 8001
with TP=4 spanning Dobby's 4× A100 80GB. Logs to
`logs/vllm_llama33_70b.log`. Verify with a single completion request
before launching §a.

Port 8001 (not 8000) is the convention from `config-llama33-vllm.yaml`.
If Qwen3.5-A3B is ever brought back up on Dobby it can coexist on port 8000.

---

## §2.a — FC + OTRC ∞ baselines (estimated ~30-50h)

Wall-clock estimate uses Albus's §2.2a estimate (30-40h on 8× A6000)
adjusted for Dobby's smaller TP and the larger model — net assume 30-50h.

`scripts/run_llama_inf.sh`:
- Runs `full-context` and `online-trc` at `--budget 999999999`, depth=0.5,
  ABL-30, 2 runs/task.
- Output dir: `results/ablations/llama33-70b-inf/`.
- 120 runs total (2 prims × 30 × 2).
- Uses `--with-eval` so eval runs immediately after agent run completes
  per condition (no eval backlog).

Update `Active_runs.md` on launch. Do NOT auto-chain into §2.c — wait
for calibration approval.

---

## §2.b — Calibration (5 min, no GPU)

After §a writes `experiment_results.json`, compute the FC peak-token
distribution and propose budgets:

```bash
bash scripts/calibrate_llama_budgets.sh
```

This is the exact recipe from ALBUS_PLAN §1.3b adapted for Llama: reads
`results/ablations/llama33-70b-inf/experiment_results.json`, filters to
`condition == 'full-context'`, computes the max-step-prompt-tokens
distribution, and prints trigger rates at candidate budgets.

**Budget proposal anchor:** mirror Qwen3.5-35B-A3B's trigger rates
(97% / 88% / 76% for tight / medium / loose) within ~5pp. Llama 3.3 70B
has a tighter peak distribution than Qwen3.5 on preliminary data
(predicted median peak ~6k vs Qwen3.5's ~27k), so budgets will likely
land in the 3-8k range — same order of magnitude as Qwen2.5-7B's
4k/8k/12k.

Paste the calibration output back to chat. **Wait for explicit user
approval of TIGHT / MEDIUM / LOOSE values before §c.**

---

## §2.c — Canonical-depth budgeted sweep (estimated ~50-70h)

Once budgets are locked, fill `TIGHT_BUDGET`, `MEDIUM_BUDGET`,
`LOOSE_BUDGET` in `scripts/run_llama_budgeted_canonical.sh` and launch.

- 11 budgeted prims (5 depth-tunable + 6 depth-invariant) × 3 budgets ×
  30 tasks × 2 runs = **1,980 runs** at depth=0.5.
- Output dirs: `results/ablations/llama33-70b-budgeted-{TIGHT,MEDIUM,LOOSE}/`.
- Run order: MEDIUM → TIGHT → LOOSE (matches Dobby convention from §1.3c).

Update `Active_runs.md` on launch. **Do NOT auto-chain into §d** — sanity
on the canonical numbers before committing 1,800 more runs.

---

## §2.d — Tail-depth runs (estimated ~50-70h)

5 depth-tunable prims (`truncation`, `summarization`,
`summarization-partial`, `structured-summarize`,
`structured-summarize-partial`) × 3 budgets × 2 tail depths (0.3, 0.7) ×
30 tasks × 2 runs = **1,800 runs**.

`scripts/run_llama_tail_depths.sh` launches 6 ablations:
- `llama33-70b-budgeted-{TIGHT,MEDIUM,LOOSE}-d030/`
- `llama33-70b-budgeted-{TIGHT,MEDIUM,LOOSE}-d070/`

Run order: same MEDIUM → TIGHT → LOOSE per depth; 0.3 layer first, then
0.7 (matches what Qwen2.5-7B produced).

---

## §3 — Followup (post-§d)

1. Update `project_runs_checklist.md` — flip Llama Phase 2 row to
   `complete on Dobby`, move from "not yet launched" to "complete".
2. Update `Active_runs.md` — move entry from Currently Running to
   Recently Completed; record actual wall-clock.
3. Trigger the `Review1/build_review1.py` extension already specified in
   [albus-to-dobby-transfer plan](~/.claude/plans/albus-to-dobby-transfer.md):
   add a `_LLAMA33_70B_SOURCES` map mirroring the Qwen2.5-7B structure
   pointing at `results/ablations/llama33-70b-*` (no rsync needed — data
   is already on Dobby disk).
4. Rebuild `Review1.csv`; verify row count grew by exactly 3,900.

---

## Total wall-clock estimate

| sub | est wall-clock | notes |
|---|---|---|
| §0 pre-launch | ~30 min | run_experiment.py patch + pilot + verify serving |
| §1 vLLM startup | ~5 min | model already cached |
| §a FC + OTRC ∞ | 30-50h | 120 runs, agent + eval per cond |
| §b calibration | 5 min | no GPU |
| §c canonical budgeted | 50-70h | 1,980 runs |
| §d tail depths | 50-70h | 1,800 runs |
| **total** | **~130-190h** | **5.5-8 days end-to-end** |

Estimate is rough — first concrete read after the §0.2 pilot. If pilot
returns latency >2x estimate, revisit scope.

---

## Critical files

**To create:**
- `exp_plans/DOBBY_LLAMA_PHASE.md` (this file)
- `config-online-trc-llama33.yaml` — Llama variant of OTRC agent config
- `scripts/start_vllm_llama33_70b.sh` — vLLM TP=4 startup
- `scripts/run_llama_inf.sh` — §a launcher (120 runs)
- `scripts/calibrate_llama_budgets.sh` — §b helper
- `scripts/run_llama_budgeted_canonical.sh` — §c launcher (template; fill budgets)
- `scripts/run_llama_tail_depths.sh` — §d launcher (template; fill budgets)

**To patch:**
- `scripts/run_experiment.py` — add `--otrc-config PATH` flag (§0.1)

**To update on launch:**
- `Active_runs.md` — Currently Running entry per phase
- `project_runs_checklist.md` — status per phase

**Reused without change:**
- `config-llama33-vllm.yaml` — already exists (port 8001)
- `task_lists/ablation_30tasks.json` — ABL-30 cohort
- `scripts/run_experiment.py` aside from the OTRC patch
- `mini-swe-agent/` submodule — model-agnostic

---

## Excluded from this plan

- Cross-model paired analysis vs Qwen3.5-A3B / Qwen2.5-7B — that's §5.4
  paper work, separate from data collection.
- Adding `model` column to `Review1.csv` — covered by the
  [albus-to-dobby-transfer plan](~/.claude/plans/albus-to-dobby-transfer.md);
  do that once and Llama data benefits automatically.
- Albus Phase 3 quantization sweep transfer — separate plan
  (already covered in `albus-to-dobby-transfer.md`).
