# SWE-bench verdict re-evaluation (Qwen3.5-35B-A3B) — what was wrong and what changed

Status as of 2026-09-24 (main-track re-evaluation applied). Written so that
another person (or an agent) can pick this up without the chat history. Paths
are relative to the repository root.

## TL;DR

- A subset of Qwen SWE-bench attempts in the canonical results were recorded as
  `resolved = False` **without ever having been graded**: the SWE-bench harness
  produced no report for them, and the missing verdict was stored as False.
- Re-running the official harness on the *same saved patches* flips 60 of
  those attempts to True (0 flip True→False). All 60 are Qwen main-track cells:
  FC +12, TRC 15K +14, TR 15K +13, SS 15K +8, SU 15K +8, plus 5 in 20K/SU-p cells.
- Applied on 2026-09-24: `reevaluate_swebench_candidates.py apply --write`
  updated the canonical `ICLR_results/swebench/main/qwen35b/*/experiment_results.json`
  (each changed row carries a `reevaluation` provenance block; the previous
  files are backed up under the re-evaluation directory's `backups/` and in
  `archive/`), and `analysis/outcomes/swebench_outcomes.csv` was rebuilt from
  them. The interim copy `ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv`
  is now identical to the canonical table and no longer needed.
- Effect on the paper: FC on P100 goes 49.0% → 53.0% (attempt level) and
  46 → 53 tasks (majority of 3). No policy beats FC on SWE-bench any more
  (best: TRC +0.7 pp, not significant). Cost/latency/token numbers are
  unchanged. Terminal-Bench, Devstral and GLM are unchanged.
- The ablation track (10K/20K, D=0.3/0.7 cells) has the same class of
  problem in 155 attempts on ABL-25 and has **not** been re-evaluated yet
  (candidate list prepared, see "Pending").

## 1. What was wrong

### Symptom

In `ICLR_results/swebench/main/qwen35b/<cell>/experiment_results.json`, 60
attempts have `patch_generated = True`, a saved `submission`, and
`resolved = False`, but no evaluation evidence anywhere: no per-run harness
report (`<cell>/eval/qwen35-a3b.<key>.json`), no `report.json` under
`eval/logs/run_evaluation/`, and no aggregate report listing the instance.
The 2026-09-10 audit (`ICLR_results/issue/qwen_main_20260910/`, category
`legacy_evaluation_reports_missing`) found exactly these 60.

They are not random:

- 8 tasks only: django-13012, scikit-learn-13328, -14496, -15100, -26323,
  sympy-15017, -19637, -24443 (heavy test suites).
- runs 1 and 2 only, never run 3.
- the 5 cells that were generated and graded in the same week
  (2026-03-30..04-09): `di__binf__fc`, `d05__b15k__tr`, `di__b15k__trc`,
  `d05__b15k__ss`, `d05__b15k__su-full`.
- run 3 of the same tasks/cells, graded in Aug–Sep 2026 with the fixed
  harness, all have complete reports.

### Cause (best-supported explanation)

The grading code in force at the time (`scripts/run_experiment.py`, commits
`f064da2` 2026-03-15 … `dfda60c` 2026-05-03; later moved to
`scripts/bench_adapters/swe_bench.py`) called
`swebench.harness.run_evaluation` with:

- a **600 s subprocess timeout covering image pull/build *and* the tests**,
- no harness-side `--timeout`,
- no OpenMP/BLAS thread cap inside the container (128 host cores → small-data
  test suites spend their time in thread synchronisation and never finish),
- the default cache level (instance image deleted after every run and
  re-pulled next time).

When the subprocess was killed the harness wrote nothing, the code returned
`None` ("ERROR"), and somewhere in the later eval-only/consolidation passes
the missing verdict was stored as `False`. The exact step that wrote False
cannot be reconstructed: the March launcher logs are gone and the pre-merge
source index (`data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/`)
already carries False.

The fix on 2026-09-11 (`34ac3cb`, "make SWE-bench evaluation verdicts
trustworthy and cap container threads") addresses exactly this: harness
`--timeout 1800` (later 600), `SWEBENCH_EVAL_THREADS=8` via
`scripts/swebench_eval_wrapper.py`, `--cache_level instance`, and a verdict
of `None` (retry) instead of False when no report exists.

Attempts that *were* graded were graded correctly: of the audit rows with a
report, none flipped on re-evaluation, and harness-error rows (patch apply
failures etc.) stayed False.

## 2. What the re-evaluation did

`scripts/reevaluate_swebench_candidates.py run` re-runs the official
SWE-bench harness (SWE-bench_Verified, `--cache_level instance`,
thread cap 8, test timeout 600 s) on the **saved submission patch** of each
candidate. It never launches an agent or an LLM, and it writes only under
`ICLR_results/ICLR_reeval/<run>/`. Patch identity is checked by SHA-256
(`manifest.json`: `patch_sha256`, `generation_sha256`).

Run of 2026-09-24 (`ICLR_results/ICLR_reeval/qwen35b_main_review253_20260923/`):

- input: the 253 `review` rows of the 2026-09-10 main-track audit
  (`ICLR_results/issue/reeval_candidates_qwen35b_review253_20260923/candidates.csv`).
- result: 253/253 verified; vs the current index **60 False→True, 0 True→False**
  (`verdict_comparison.csv`, columns `resolved_index_now`,
  `resolved_reeval_20260923`). 140 rows already re-evaluated on 09-11
  reproduced exactly.
- flips by cell: `di__b15k__trc` 14, `d05__b15k__tr` 13, `di__binf__fc` 12,
  `d05__b15k__ss` 8, `d05__b15k__su-full` 8, `d05__b20k__ss-partial` 2,
  `d05__b15k__su-partial` 1, `d05__b20k__su-partial` 1, `d05__b20k__su-full` 1.
- by run: run 1: 24, run 2: 29, run 3: 7. Run 3 is not the problem.

`apply --write` was run on 2026-09-24 after a preview (253 verified, 60
resolved values changing). It backs up every touched `experiment_results.json`
before writing and records `changes.json` next to the backup.

## 3. Outcomes table

`analysis/outcomes/swebench_outcomes.csv` (in git) was rebuilt with
`analysis/aggregate_benchmark_results.py --benchmark swebench` after the
apply step; relative to the previous version only `resolved` and the derived
`failure_mode` (`submitted_unresolved` → `resolved`) differ, in 60 rows
(29,527 rows in total). Before the apply, the same table was produced as a
non-canonical copy by `analysis/apply_reeval_outcomes.py`; that script now
stops with an error because the canonical verdicts no longer equal
`resolved_index_now`, which is the intended guard.

## 4. What changes in the paper numbers (Qwen, SWE-bench only)

Computed with the paper's own definitions (paired task bootstrap, B=5000,
seed 0; task map = ≥2 of 3 uncapped resolved attempts). Everything about
token usage, latency, billed cost, Terminal-Bench, Devstral and GLM is
identical before and after.

P100, primary threshold (Figures 1/2, 4, 5a):

| policy | resolve now → reeval | success vs FC (pp) now → reeval |
|---|---|---|
| FC | 49.0 → 53.0 | — |
| TR | 40.0 → 44.3 | −9.0 → −8.7 [−14.7, −3.0] |
| TRC | 49.0 → 53.7 | 0.0 → +0.7 [−4.0, +5.0] |
| SU | 39.3 → 42.0 | −9.7 → −11.0 [−16.0, −6.3] |
| SS | 40.3 → 43.0 | −8.7 → −10.0 [−15.0, −5.0] |
| SU-p | 48.7 → 49.0 | −0.3 → −4.0 [−9.3, +1.3] |
| SS-p, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-p, OTRC+SS-p, OTRC | unchanged | shift by −4.0 |

- No policy is above FC after the re-evaluation; TRC+SU goes from +3.0 to
  −1.0 pp. Seven policies are within CI of FC, five are significantly below.
- Task map (P100): FC solves 53 (was 46), misses 47 (was 54). Gains range
  2–7 (was 2–14), losses 6–14 (unchanged). TRC+SU: +7/−8, total 52 (< FC 53).
  SS-p: +7/−9, total 51. TR: +3/−14, total 42.
- Figure 5a Qwen column: TRC is now the best resolve (53.7%) and already has
  the lowest cost (0.71×) and latency (0.79×). OTRC vs TR: +7.0 pp (was +11.3).
- Figure 5b Qwen: SS-p−SS +6.7* (was +9.3*), TRC+SS−SS +7.7* (was +10.3*),
  OTRC−TRC −2.3 n.s. (was +2.3 n.s.), OTRC+SS-p−OTRC −4.3 (unchanged).
- Figure 3 (ABL-25 knob table): only the D=0.5/15K cells and the FC header
  move: FC 53.3 → 65.3%, TR 36.0 → 46.7, SU 42.7 → 53.3, SS 45.3 → 54.7,
  SU-p 60.0 → 61.3. The 10K/20K and D=0.3/0.7 cells are ablation-track and
  untouched (but see "Pending").
- Text: the only bold takeaway that changes is Observation #5
  ("...similar or improves" → "...similar"). Observation #1's "some even
  improve it" example and Observation #6's "TRC+SU best for Qwen" need
  rewording; see the chat-derived notes in the LaTeX comments.

Appendix figures: `appendix_knob_overview.py` and `appendix_task_map.py`
now read the corrected canonical table by default. The `*_reeval.py`
wrappers only matter if the interim copy is used again.

## 5. Pending: ablation track

The 2026-09-10 audit covered only the main track. The same check on the
ablation track (`ICLR_results/swebench/ablation/qwen35b/`, ABL-25, runs 1–3)
finds **155 attempts with a saved patch, `resolved = False`, and no
evaluation report anywhere** (mostly 20K DI cells and 10K TRC; tasks
sympy-17630/-13091/-13031, scikit-learn-11310, sympy-15017, django-14999, …;
dated 2026-04-20..08-28, i.e. before the harness fix). If the main-track flip
rate holds (53/60), applying main only would leave FC and the primary cells
inflated relative to the 10K/20K/D=0.3/0.7 cells.

Candidate list (validated with `plan`):
`ICLR_results/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv`.

Run (CPU/podman only, ~1.5 h):

```
nohup venv/bin/python scripts/reevaluate_swebench_candidates.py run \
  --candidates ICLR_results/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv \
  --output-dir ICLR_results/ICLR_reeval/qwen35b_ablation_abl25_155_20260924 \
  --model-tag qwen35-a3b --continue-on-error \
  > logs/reeval_qwen35b_ablation155_20260924.log 2>&1 &
```

Afterwards: preview and `apply --write` that run the same way, rebuild
`analysis/outcomes/swebench_outcomes.csv` with
`aggregate_benchmark_results.py --benchmark swebench`, rerun
`scripts/build_coverage.py`, and regenerate the appendix figures and Ritul's
Figure 1/3/4/5 exports (`q1_frontier.py`, `token_cost_ledger.py`,
`q1_knob_execution.py`, Q3), which read verdicts from the raw
`experiment_results.json`.

## 6. Files

| Path | Role |
|---|---|
| `ICLR_results/issue/qwen_main_20260910/` | audit that found the 253 review rows (`README.md`, `evaluation_classification.csv`, `audit_evaluation.py`) |
| `ICLR_results/ICLR_reeval/qwen35b_main_review253_20260923/` | re-evaluation evidence: `manifest.json`, `results.json`, `verdict_comparison.csv` (`jobs/` gitignored) |
| `scripts/reevaluate_swebench_candidates.py` | `plan` / `run` / `apply` harness (apply not used) |
| `analysis/apply_reeval_outcomes.py` | wrote the interim corrected copy before the apply (now guarded off) |
| `analysis/outcomes/swebench_outcomes.csv` | canonical outcomes table, rebuilt after the apply |
| `ICLR_analysis/appendix_knob_overview.py`, `appendix_task_map.py` | appendix figures; `--outcomes` selects the table |
| `ICLR_analysis/appendix_depth_trigger_ablation_reeval.py`, `appendix_task_map_reeval.py` | wrappers that use the corrected table |
| `ICLR_results/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv` | pending ablation-track candidates |
| `Active_runs.md` ("Recently Completed") | launch/completion record of the re-evaluation run |
