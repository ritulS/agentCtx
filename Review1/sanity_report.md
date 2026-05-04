# Review1 sanity report


## F1 — New primitive correctness invariants

✅  SU-partial: 149/180 runs (83%) had summarization_prompt_tokens > 0
✅  SS-partial: 139/180 runs (77%) had summarization_prompt_tokens > 0
❌  OTRC+SU-partial: 51/180 runs (28%) had summarization_prompt_tokens > 0
❌  OTRC+SS-partial: 50/180 runs (28%) had summarization_prompt_tokens > 0
✅  OTRC: 60/60 runs (100%) had online_trc_clears > 0
✅  OTRC+TR: 180/180 runs (100%) had online_trc_clears > 0
✅  OTRC+SU-partial: 180/180 runs (100%) had online_trc_clears > 0
✅  OTRC+SS-partial: 180/180 runs (100%) had online_trc_clears > 0
✅  TRC+SU: 0/180 runs had trc_fallback_events > 0  (should always be 0)
✅  TRC+SS: 0/180 runs had trc_fallback_events > 0  (should always be 0)
✅  FC: 0/60 runs had compression_events > 0  (budget=∞ → should be 0)
✅  OTRC: 0/60 runs had compression_events > 0  (budget=∞ → should be 0)

## F2 — Cell completeness

✅  All 35 cells (11×3 budget + 2 ∞) have exactly 60 unique (task, run) rows on the 30 ablation tasks
✅  0 rows with step_count=0, 0 rows with total_tokens=0

## F3 — Eval-result self-consistency

❌  1 rows have resolved=None but patch_generated=True
   sample:
         task_name       primitive  token_budget exit_status
sympy__sympy-19637 OTRC+SU-partial         20000   Submitted
❌  6 rows have exit_status='Submitted' but patch_generated=False
   sample tasks: {'sympy__sympy-13031': 5, 'scikit-learn__scikit-learn-11310': 1}
✅  0 rows have resolved=True but patch_generated=False

## F4 — Cross-validation against earlier numbers

✅  TR@15000: source=20, csv=20
✅  SU-full@15000: source=14, csv=14
✅  TRC@15000: source=31, csv=31
✅  SS@15000: source=18, csv=18
✅  FC@∞: source=23, csv=23
✅  TR@10000: source=29, csv=29
✅  TR@20000: source=36, csv=36
✅  TRC+SU@10000: source=33, csv=33
✅  TRC+SS@15000: source=35, csv=35
✅  SU-partial@15000: source=34, csv=34
✅  OTRC+SU-partial@15000: source=39, csv=39
✅  OTRC@∞: source=37, csv=37

**Overall F4: PASS** — Review1.csv matches source experiment_results.json

## F5 — Step count definition

LimitsExceeded runs: 281 total
  step_count distribution: min=125, max=125, median=125.0
  step_count ≥ 100: 281/281 runs

Silent-crash runs: 372 total
  step_count distribution: min=7, max=124, median=73.0
  early-exit (<10 steps): 5 | mid (10-49): 82 | late (≥50): 285

## F6 — Token accounting consistency

✅  0 rows have summarization_prompt_tokens > total_prompt_tokens
✅  0 rows where total_tokens != prompt + completion

## F8 — Bootstrap 95% CI per (primitive, budget) cell


```
primitive           budget  resolve%  95% CI              halfwidth (pp)
------------------------------------------------------------------------
OTRC+SS-partial      10000     38.3%  [26.7, 50.0]                 11.7
OTRC+SS-partial      15000     51.7%  [40.0, 63.3]                 11.7
OTRC+SS-partial      20000     65.0%  [53.3, 76.7]                 11.7
OTRC+SU-partial      10000     48.3%  [36.7, 61.7]                 12.5
OTRC+SU-partial      15000     65.0%  [51.7, 76.7]                 12.5
OTRC+SU-partial      20000     61.7%  [50.0, 73.3]                 11.7
OTRC+TR              10000     46.7%  [35.0, 60.0]                 12.5
OTRC+TR              15000     55.0%  [41.7, 68.3]                 13.3
OTRC+TR              20000     66.7%  [55.0, 78.3]                 11.7
SS                   10000     35.0%  [23.3, 46.7]                 11.7
SS                   15000     30.0%  [18.3, 41.7]                 11.7
SS                   20000     61.7%  [48.3, 73.3]                 12.5
SS-partial           10000     36.7%  [23.3, 50.0]                 13.3
SS-partial           15000     53.3%  [41.7, 66.7]                 12.5
SS-partial           20000     65.0%  [53.3, 76.7]                 11.7
SU-full              10000     31.7%  [20.0, 43.3]                 11.7
SU-full              15000     23.3%  [13.3, 35.0]                 10.8
SU-full              20000     56.7%  [43.3, 68.3]                 12.5
SU-partial           10000     40.0%  [28.3, 53.3]                 12.5
SU-partial           15000     56.7%  [43.3, 70.0]                 13.3
SU-partial           20000     61.7%  [48.3, 73.3]                 12.5
TR                   10000     48.3%  [36.7, 61.7]                 12.5
TR                   15000     33.3%  [21.7, 45.0]                 11.7
TR                   20000     60.0%  [48.3, 71.7]                 11.7
TRC                  10000     46.7%  [33.3, 60.0]                 13.3
TRC                  15000     51.7%  [38.3, 65.0]                 13.3
TRC                  20000     71.7%  [60.0, 83.3]                 11.7
TRC+SS               10000     60.0%  [48.3, 73.3]                 12.5
TRC+SS               15000     58.3%  [46.7, 70.0]                 11.7
TRC+SS               20000     76.7%  [66.7, 86.7]                 10.0
TRC+SU               10000     55.0%  [41.7, 68.3]                 13.3
TRC+SU               15000     65.0%  [53.3, 76.7]                 11.7
TRC+SU               20000     66.7%  [55.0, 78.3]                 11.7
FC                       ∞     38.3%  [26.7, 50.0]                 11.7
OTRC                     ∞     61.7%  [50.0, 73.3]                 11.7
```

Mean CI half-width across cells: **±12.1pp**. Differences smaller than 2× this width are within sampling noise.

## F9 — Per-task resolve rate (across all primitives × budgets × runs)

Tasks with 100% resolve rate (universally easy): 0
Tasks with 0% resolve rate (universally hard): 2
Tasks with < 10% resolve: 5
Tasks with > 90% resolve: 2

Top-5 easiest:
  django__django-11066                              98.6%
  django__django-14915                              95.7%
  sympy__sympy-11618                                84.3%
  scikit-learn__scikit-learn-15100                  84.3%
  django__django-11292                              82.9%

Top-5 hardest:
  sympy__sympy-13031                                 4.3%
  scikit-learn__scikit-learn-25747                   4.3%
  sympy__sympy-13091                                 2.9%
  django__django-12273                               0.0%
  sympy__sympy-17630                                 0.0%

Task-level resolve rate variance: σ = 31.1pp
Coefficient of variation: 0.59

## F11 — Repo as confounder


Resolve rate by repo (all primitives × budgets × runs pooled):

```
repo                                 n  resolved  resolve%  mean steps  mean tokens (k)
django                             700       396     56.6%        61.7           527.0
scikit-learn                       700       393     56.1%        65.5           578.6
sympy                              700       317     45.3%        66.9           537.0
```

Per-primitive resolve rate by repo at 15k:

```
repo_full        django  scikit-learn  sympy
primitive                                   
OTRC+SS-partial    45.0          65.0   45.0
OTRC+SU-partial    75.0          75.0   45.0
OTRC+TR            50.0          70.0   45.0
SS                 45.0          35.0   10.0
SS-partial         50.0          55.0   55.0
SU-full            30.0          15.0   25.0
SU-partial         55.0          75.0   40.0
TR                 40.0          30.0   30.0
TRC                75.0          50.0   30.0
TRC+SS             70.0          70.0   35.0
TRC+SU             80.0          60.0   55.0
```

## F13 — Run-number bias (run_1 vs run_2)


run_num=1: 555/1050 = 52.9%
run_num=2: 551/1050 = 52.5%
Difference: +0.4pp
(if non-zero with high magnitude, indicates ordering effects in the runner)

## F14 — Task-selection provenance

From `results/ablations/ablation_index.md`:

> Selection criteria: tasks where full-context (FC) patches (majority vote across 2 runs ≥ 0.5), stratified by compression outcome — 5 all-succeed + 5 mixed per repo (django, scikit-learn), 7 all-succeed + 3 mixed for sympy (only 3 mixed available). Seed=42.

**Implications:**
- Tasks are NOT a random SWE-bench sample — they were selected on FC ≥ 0.5.
- Tasks are stratified on compression outcome from prior runs at 15k.
- Result generalizes to: "tasks where FC succeeds and compression matters".
- Does NOT generalize to: full SWE-bench Verified, or to tasks where FC already fails.

**Repo coverage:** django, scikit-learn, sympy (3 of 12 SWE-bench Verified repos).

Verifying FC-success criterion in current data:
  Tasks where FC resolved ≥ 1 of 2 runs: 15/30
  Tasks where FC resolved 0 of 2 runs:   15/30  (should be 0 if criterion held)