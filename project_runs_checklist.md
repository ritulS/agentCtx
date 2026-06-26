# Project runs checklist

This file is the **first place to check** when asking what runs are needed,
what we already have, or whether a particular cell is covered. Organized
per-model. Always verify against disk (`results/ablations/` and
`Review1/Review1.csv`) before acting on outdated entries.

## Vocabulary (use these terms going forward)

The agentCtx project studies compression primitives along several axes; the
following terms keep cell-coverage discussions precise.

**Primitive families** (split by whether `compression_ratio` engages):

- **depth-tunable** — TR, SU-full, SU-partial, SS, SS-partial. The 5
  primitives whose behavior is a function of `compression_ratio`. Studied at
  all 3 depths.
- **depth-invariant** — TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial,
  OTRC+SS-partial. The 6 primitives where `compression_ratio` either doesn't
  engage at all (TRC clears tool results) or has been deemed not worth
  studying at off-canonical depths. Studied at canonical depth only.

**Depths:**

- **canonical depth** = 0.5 (default; the only depth in scope for
  depth-invariant primitives).
- **tail depths** = 0.3 and 0.7 (only studied for depth-tunable primitives).
- **depth grid** = {0.3, 0.5, 0.7} (the symmetric 3-point set).

**Cohorts** (task subsets):

- **ABL-30** — original 30 FC-stratified ablation tasks
  (`results/ablations/tasks.json`).
- **NEW-70** — the 70 added tasks (`task_lists/p100_new_tasks.json`).
- **P100** — full cohort = ABL-30 ∪ NEW-70
  (`task_lists/p100_all_100_tasks.json`). ABL-30 ⊂ P100, so any P100 cell
  satisfies an ABL-30 requirement.

**Scope rule** for whether a `(primitive, budget, depth, cohort)` cell is
in-scope for the paper (main model only — model-expansion runs follow their
own reduced scopes):

- `depth-tunable` × `depth grid` × cohort ⊇ {**P100** if budget=15k, **ABL-30**
  if budget ∈ {10k, 20k}}.
- `depth-invariant` × `canonical depth` × **P100 at every budget**.

Any other `(primitive, budget, depth, cohort)` combination is **out-of-scope**
and not run. "Over-scope" cells (e.g., P100 where ABL-30 is required) are
fine — keep the data, no action needed.

---

## Qwen3.5-35B-A3B (main model, served on Dobby)

This is the primary model for all paper claims. P100 coverage at the canonical
budget (15k) and depth, plus depth-grid coverage on the 5 depth-tunable
primitives.

### Coverage matrix (last verified 2026-05-14)

#### depth-tunable family (5 primitives) — needs full depth grid

| budget | depth=0.3 | depth=0.5 | depth=0.7 | required cohort | status |
|---|---|---|---|---|---|
| 10k | ✅ P100 (over-scope, ABL-30 ⊂) | ✅ P100 | ✅ ABL-30 (backfilled 2026-05-15) | ABL-30 | complete |
| 15k | ✅ P100 | ✅ P100 | ✅ P100 | P100 | complete |
| 20k | ✅ ABL-30 | ✅ P100 (over-scope) | ✅ ABL-30 | ABL-30 | complete |

#### depth-invariant family (6 primitives) — canonical depth only, P100 at every budget

| budget | depth=0.5 | required | status |
|---|---|---|---|
| 10k | ✅ P100 | P100 | complete |
| 15k | ✅ P100 | P100 | complete |
| 20k | ✅ P100 | P100 | complete |

#### ∞-budget baselines (FC, OTRC) — P100 at canonical depth

| primitive | depth=0.5 | required | status |
|---|---|---|---|
| FC (full-context) | ✅ P100 | P100 | complete |
| OTRC | ✅ P100 | P100 | complete |

### Outstanding gaps (Qwen3.5-35B-A3B)

**None.** All in-scope cells for the main model are complete as of 2026-05-15.

The depth=0.7 × 10k × ABL-30 backfill (300 runs) finished at 05:23 CDT
2026-05-15 (wall-time ~5h53m, eval exit=0). See Active_runs.md for details.

### Source dirs (where the data lives on disk)

- depth-tunable @ depth grid @ 15k @ P100:
  `results/ablations/p100-depth{30,70}-singles-15000/` and
  `results/ablations/p100-singles-15000/` for canonical depth.
- depth-tunable @ tail depths @ 20k @ ABL-30: `results/ablations/depth-30/` and
  `results/ablations/depth-70/` (8-condition legacy ABL chain dirs;
  split-by-group views in `p100-depth30-singles-20000/` etc.).
- depth-tunable @ depth=0.3 @ 10k @ P100: `p100-depth30-singles-10000/`
  (bonus from prior aborted orchestrator run).
- depth-tunable @ depth=0.7 @ 10k @ ABL-30: `p100-depth70-singles-10000/`
  (backfill 2026-05-15; 300 runs).
- depth-invariant @ canonical @ P100 @ all budgets:
  `p100-{trc,otrc}-{10000,15000,20000}/` plus the n=30 `partial-*`,
  `stacked-*`, `otrc-stacked-*` dirs that filled the ABL portion.
- ∞ baselines: `p100-inf/` (FC + OTRC at P100).

### How depth gets into the CSV

`Review1/build_review1.py` reads the per-record `compression_ratio` field
into the `depth` column. Existing analyses (sanity, paired, routing,
predictability, winners, plot_review1) filter to `depth == 0.5` to preserve
their semantics. New `Review1/depth_analysis.py` uses the depth column to do
paired across-depth comparisons.

---

## Model-expansion runs (Qwen2.5-7B, Llama 3.3 70B)

These two models share an identical required-coverage matrix. Cohort is
**ABL-30 in every cell** (no NEW-70 / no P100). Budgets are
**per-model-calibrated** (TIGHT / MEDIUM / LOOSE from the FC peak distribution
on ABL-30, per `exp_plans/ALBUS_PLAN.md` §1.3b and §2.2b), not the main
model's 10k/15k/20k.

The depth-tunable / depth-invariant family split and the depth grid are the
same as for the main model — depth-tunable studied across the full grid
{0.3, 0.5, 0.7}; depth-invariant studied at canonical depth only;
∞-budget baselines (FC, OTRC) at canonical depth only.

Run-count accounting per model:

- depth-tunable: 5 prims × 3 budgets × 3 depths × 30 tasks × 2 runs = **2,700**
- depth-invariant: 6 prims × 3 budgets × 1 depth × 30 × 2 = **1,080**
- ∞ baselines (FC + OTRC): 2 prims × 1 depth × 30 × 2 = **120**
- **Total per model: 3,900 runs.**

The current `exp_plans/ALBUS_PLAN.md` Phase 1 / Phase 2 scopes describe only
the **canonical-depth slice** (35 cells = 5 + 6 prims × 3 budgets + 2 ∞ = 2,100
runs per model). Adding the tail-depth rows for the depth-tunable family is
an additional 5 × 3 × 2 × 30 × 2 = **1,800 runs per model** on top of that.

### Qwen2.5-7B (Albus Phase 1) — ✅ COMPLETE (3,900 / 3,900 on Albus disk)

Calibrated budgets resolved to **TIGHT=4k / MEDIUM=8k / LOOSE=12k** per
ALBUS_PLAN §1.3b. All data lives under `results/ablations/` on Albus (not yet
transferred to Dobby — see "Pending: Albus → Dobby transfer" below).

#### depth-tunable family (5 primitives) — needs full depth grid

| budget       | depth=0.3 | depth=0.5 | depth=0.7 | required cohort | status   |
|--------------|-----------|-----------|-----------|-----------------|----------|
| TIGHT  = 4k  | ✅ ABL-30 | ✅ ABL-30 | ✅ ABL-30 | ABL-30          | complete |
| MEDIUM = 8k  | ✅ ABL-30 | ✅ ABL-30 | ✅ ABL-30 | ABL-30          | complete |
| LOOSE  = 12k | ✅ ABL-30 | ✅ ABL-30 | ✅ ABL-30 | ABL-30          | complete |

Subtotal: 5 × 3 × 3 × 60 = 2,700 runs. ✅ on disk.

#### depth-invariant family (6 primitives) — canonical depth only

| budget       | depth=0.5 | required cohort | status   |
|--------------|-----------|-----------------|----------|
| TIGHT  = 4k  | ✅ ABL-30 | ABL-30          | complete |
| MEDIUM = 8k  | ✅ ABL-30 | ABL-30          | complete |
| LOOSE  = 12k | ✅ ABL-30 | ABL-30          | complete |

Subtotal: 6 × 3 × 60 = 1,080 runs. ✅ on disk.

#### ∞-budget baselines (FC, OTRC) — canonical depth, ABL-30

| primitive         | depth=0.5 | required cohort | status   |
|-------------------|-----------|-----------------|----------|
| FC (full-context) | ✅ ABL-30 | ABL-30          | complete |
| OTRC              | ✅ ABL-30 | ABL-30          | complete |

Subtotal: 2 × 60 = 120 runs. ✅ on disk.

**Qwen2.5-7B total: 3,900 / 3,900 runs complete on Albus.**

#### Source dirs on Albus (`results/ablations/`)

| dir                                  |   n | scope                                       |
|--------------------------------------|----:|---------------------------------------------|
| `qwen25-7b-inf/`                     | 120 | ∞-budget × d=0.5 (FC + OTRC)                |
| `qwen25-7b-budgeted-4000/`           | 660 | 11 prims × d=0.5 @ TIGHT                    |
| `qwen25-7b-budgeted-8000/`           | 660 | 11 prims × d=0.5 @ MEDIUM                   |
| `qwen25-7b-budgeted-12000/`          | 660 | 11 prims × d=0.5 @ LOOSE (recovery rerun)   |
| `qwen25-7b-budgeted-4000-d030/`      | 300 | 5 depth-tunable × d=0.3 @ TIGHT             |
| `qwen25-7b-budgeted-8000-d030/`      | 300 | 5 depth-tunable × d=0.3 @ MEDIUM            |
| `qwen25-7b-budgeted-12000-d030/`     | 300 | 5 depth-tunable × d=0.3 @ LOOSE             |
| `qwen25-7b-budgeted-4000-d070/`      | 300 | 5 depth-tunable × d=0.7 @ TIGHT             |
| `qwen25-7b-budgeted-8000-d070/`      | 300 | 5 depth-tunable × d=0.7 @ MEDIUM            |
| `qwen25-7b-budgeted-12000-d070/`     | 300 | 5 depth-tunable × d=0.7 @ LOOSE             |

Bucket check: 120 + 1,080 (6 depth-invariant × 3 budgets × d=0.5)
+ 2,700 (5 depth-tunable × 3 budgets × 3 depths) = 3,900. ✓

### Llama 3.3 70B Instruct (Dobby Phase) — ❌ ABANDONED 2026-05-18

**Status:** abandoned at pilot stage. FC@∞ on ABL-30 resolved 2/60 = 3.3%
(vs Qwen3.5-A3B 43%). Llama submitted prematurely (median 9 LLM calls,
min 4) producing shallow `sed`-style patches. Diagnosed as harness mismatch:
Llama 3.3 was post-trained for explicit JSON tool-calling but mini-swe-agent
uses raw bash-block prompting via `litellm_textbased`. Even if we got Llama
to 10-15% baseline through investigation, paired primitive comparisons would
be too noisy.

**Retained artifacts** (do not run, kept for posterity):
- `exp_plans/DOBBY_LLAMA_PHASE.md`
- `scripts/start_vllm_llama33_70b.sh`, `scripts/run_llama_*.sh`,
  `scripts/calibrate_llama_budgets.sh`
- `configs/config-llama33-vllm.yaml`, `configs/config-online-trc-llama33.yaml`
- `results/ablations/llama33-70b-inf/` — 60 FC @ ∞ records (3.3% resolve,
  documented as the Llama-on-mini-swe-agent baseline)

### Devstral-Small-2-24B-Instruct-2512 (Dobby Phase 2 replacement) — 🟡 RUNNING

**Status:** §a OTRC in progress; FC §a done (60 records, 71.7% resolve).
Selected 2026-05-18 after Llama pivot. Mistral 3 architecture
(`sliding_window: null`, full dense attention — no model-level confound for
the compression study). Weights downloaded to
`~/.cache/huggingface/hub/models--mistralai--Devstral-Small-2-24B-Instruct-2512`.

**Calibrated budgets** (locked from FC §a, n=60, peak median 27,496):

| budget | value  | trigger rate | match to Qwen3.5 target |
|--------|-------:|-------------:|-------------------------|
| TIGHT  | 15,000 |   98.3%      | 97% target (within 1.3pp) |
| MEDIUM | 20,000 |   90.0%      | 88% target (within 2.0pp) |
| LOOSE  | 24,000 |   ~75%       | 76% target (within 1pp)   |

**Required-coverage matrix is identical to Qwen2.5-7B** — same conditions,
same ABL-30 cohort, same 11 prims × 3 budgets × {1,3} depths × 30 × 2 grid.

#### depth-tunable family (5 primitives) — needs full depth grid

| budget       | depth=0.3 | depth=0.5 | depth=0.7 | required cohort | status   |
|--------------|-----------|-----------|-----------|-----------------|----------|
| TIGHT  = 15k | pending   | pending   | pending   | ABL-30          | queued   |
| MEDIUM = 20k | pending   | pending   | pending   | ABL-30          | queued   |
| LOOSE  = 24k | pending   | pending   | pending   | ABL-30          | queued   |

Subtotal: 5 × 3 × 3 × 60 = 2,700 runs (1,800 tail-depth + 900 canonical-depth slice).

#### depth-invariant family (6 primitives) — canonical depth only

| budget       | depth=0.5 | required cohort | status   |
|--------------|-----------|-----------------|----------|
| TIGHT  = 15k | pending   | ABL-30          | queued   |
| MEDIUM = 20k | pending   | ABL-30          | queued   |
| LOOSE  = 24k | pending   | ABL-30          | queued   |

Subtotal: 6 × 3 × 60 = 1,080 runs.

#### ∞-budget baselines (FC, OTRC) — canonical depth, ABL-30

| primitive         | depth=0.5         | required cohort | status            |
|-------------------|-------------------|-----------------|-------------------|
| FC (full-context) | ✅ 43/60 = 71.7%  | ABL-30          | complete          |
| OTRC              | 🔄 in progress    | ABL-30          | running (§a OTRC) |

Subtotal: 2 × 60 = 120 runs (60 done, 60 in flight).

**Devstral-2 total: 60 / 3,900 runs complete; 60 in flight; 3,780 queued.**

#### Output dirs on Dobby (`results/ablations/`)

| dir                                            |    n | scope                              | status     |
|------------------------------------------------|-----:|------------------------------------|------------|
| `devstral-2-inf/` (FC half)                    |   60 | FC × d=0.5                         | ✅ on disk |
| `devstral-2-inf/` (OTRC half, appended)        |   60 | OTRC × d=0.5                       | 🔄 running |
| `devstral-2-budgeted-15000/`                   |  660 | 11 prims × d=0.5 @ TIGHT           | queued     |
| `devstral-2-budgeted-20000/`                   |  660 | 11 prims × d=0.5 @ MEDIUM          | queued     |
| `devstral-2-budgeted-24000/`                   |  660 | 11 prims × d=0.5 @ LOOSE           | queued     |
| `devstral-2-budgeted-15000-d030/`              |  300 | 5 depth-tunable × d=0.3 @ TIGHT    | queued     |
| `devstral-2-budgeted-20000-d030/`              |  300 | 5 depth-tunable × d=0.3 @ MEDIUM   | queued     |
| `devstral-2-budgeted-24000-d030/`              |  300 | 5 depth-tunable × d=0.3 @ LOOSE    | queued     |
| `devstral-2-budgeted-15000-d070/`              |  300 | 5 depth-tunable × d=0.7 @ TIGHT    | queued     |
| `devstral-2-budgeted-20000-d070/`              |  300 | 5 depth-tunable × d=0.7 @ MEDIUM   | queued     |
| `devstral-2-budgeted-24000-d070/`              |  300 | 5 depth-tunable × d=0.7 @ LOOSE    | queued     |

Bucket check: 120 + 1,980 + 1,800 = 3,900. ✓

### Combined model-expansion run budget

| model                 | depth-tunable | depth-invariant | ∞ baselines |      total | status                          |
|-----------------------|--------------:|----------------:|------------:|-----------:|---------------------------------|
| Qwen2.5-7B (Albus)    |         2,700 |           1,080 |         120 |      3,900 | ✅ complete on Albus             |
| Devstral-Small-2-24B  |         2,700 |           1,080 |         120 |      3,900 | 🟡 60 done, 60 running, 3,780 queued |
| Llama 3.3 70B         |             — |               — |          60 |         60 | ❌ abandoned at pilot (3.3% baseline) |
| **combined (target)** |     **5,400** |       **2,160** |     **240** |  **7,800** | 50% on disk + Devstral in flight |

**Qwen2.5-7B (Phase 1):** finished on Albus, all 3,900 runs on disk. Tail-depth
rows for the depth-tunable family were run despite not being formally authorized
in the original ALBUS_PLAN §1 scope (the plan covers the canonical-depth slice
of 2,100 runs/model). The extra 1,800 tail-depth runs were executed under the
revised checklist scope. Data has not yet been transferred from Albus to Dobby
(see "Pending: Albus → Dobby transfer" below).

**Devstral-Small-2-24B (Phase 2):** selected 2026-05-18 after Llama 3.3 70B
was abandoned. FC §a confirmed 71.7% resolve (Qwen3.5-A3B = 43%, Llama 3.3 =
3.3%); Mistral 3 architecture has no SWA so no compression-study confound.
Wall-clock estimate ~30-40h end-to-end at observed ~120 runs/hr throughput.
OTRC §a in flight; will chain to canonical-budgeted (§c, 1,980 runs) then
tail-depths (§d, 1,800 runs).

---

## Qwen3-30B-A3B quantization sweep (ALBUS_PLAN Phase 3) — ✅ COMPLETE (960 / 960)

**Scope:** precision axis only. Single budget (20k), canonical depth (0.5),
4 conditions (FC, TR, SU, TRC+SS), 4 quantizations, ABL-30 cohort × 2 runs.
**No depth axis** was run for Phase 3.

**Run accounting:** 4 quants × 4 conditions × 30 tasks × 2 runs = **960 runs**.

| quantization | model identifier                                  | depth=0.5 @ 20k | runs | status                                |
|--------------|---------------------------------------------------|-----------------|-----:|---------------------------------------|
| FP16         | `Qwen/Qwen3-30B-A3B-Instruct-2507`                | ✅ ABL-30       |  240 | complete                              |
| FP8 W8A8     | official `...-FP8`                                | ✅ ABL-30       |  240 | complete                              |
| AWQ-int4     | community `cpatonn/...-AWQ-4bit`                  | ✅ ABL-30       |  240 | complete                              |
| GPTQ-int4    | community `btbtyler09/...-gptq-4bit` (`--enforce-eager`) | ✅ ABL-30 |  240 | complete (clean rerun 2026-05-12)     |

**Total: 960 / 960 runs complete on Albus.**

#### Source dirs on Albus (`results/ablations/`)

| dir                                              |   n | scope                                       |
|--------------------------------------------------|----:|---------------------------------------------|
| `qwen3-30b-a3b-fp16/`                            | 240 | FP16                                        |
| `qwen3-30b-a3b-fp8/`                             | 240 | FP8 W8A8 (official)                         |
| `qwen3-30b-a3b-awq-int4/`                        | 240 | AWQ-4bit (community)                        |
| `qwen3-30b-a3b-gptq-int4/`                       | 240 | GPTQ-4bit (clean rerun 2026-05-12)          |
| `qwen3-30b-a3b-gptq-int4-failed-2026-05-07/`     | 124 | **preserved failure evidence** — inductor-Triton collapse, do not use in analysis |

Per-quant cell count: 4 conds × 30 tasks × 2 runs = 60 per (quant × cond),
×4 conds = 240 per quant. ✓

---

## Pending: Albus → Dobby transfer

All Albus-side runs (Qwen2.5-7B Phase 1 + Qwen3-30B-A3B Phase 3) live only on
Albus disk so far. They are required on Dobby for inclusion in `Review1.csv`
and downstream analyses. To plan in the next step:

- **Volume:** Qwen2.5-7B (3,900 runs across 10 dirs) + Qwen3-30B-A3B quant
  sweep (960 runs across 4 dirs + 1 preserved-failure dir) = 14 (+1) source
  dirs to rsync.
- **Destination layout:** decide whether to mirror dir names verbatim under
  `results/ablations/` on Dobby, or namespace under `results/ablations/albus/`.
- **`build_review1.py`:** add per-model source-map blocks; the current map
  is Qwen3.5-35B-A3B only. Decide whether to keep one `Review1.csv` with a
  `model` column (preferred), or separate CSVs per model.
- **Downstream analyses:** existing scripts (sanity, paired, routing,
  predictability, winners, plot_review1, depth_analysis) filter on the main
  model implicitly; need either an explicit `--model` filter argument or a
  per-model output-path convention.

(Llama 3.3 70B Phase 2 has nothing to transfer yet — that phase is unstarted.)
