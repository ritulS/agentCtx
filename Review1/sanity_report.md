# Review1 sanity report


## F1 — New primitive correctness invariants

✅  SU-partial: 509/600 runs (85%) had summarization_prompt_tokens > 0
✅  SS-partial: 490/600 runs (82%) had summarization_prompt_tokens > 0
❌  OTRC+SU-partial: 226/600 runs (38%) had summarization_prompt_tokens > 0
❌  OTRC+SS-partial: 195/600 runs (32%) had summarization_prompt_tokens > 0
✅  OTRC: 200/200 runs (100%) had online_trc_clears > 0
✅  OTRC+TR: 600/600 runs (100%) had online_trc_clears > 0
✅  OTRC+SU-partial: 600/600 runs (100%) had online_trc_clears > 0
✅  OTRC+SS-partial: 600/600 runs (100%) had online_trc_clears > 0
✅  TRC+SU: 0/600 runs had trc_fallback_events > 0  (should always be 0)
✅  TRC+SS: 0/600 runs had trc_fallback_events > 0  (should always be 0)
✅  FC: 0/200 runs had compression_events > 0  (budget=∞ → should be 0)
✅  OTRC: 0/200 runs had compression_events > 0  (budget=∞ → should be 0)

## F2 — Cell completeness

❌  STAG-alt@10000: 12 rows (expected 200)
❌  STAG-alt@10000: 6/100 unique tasks
❌  STAG-alt@15000: 12 rows (expected 200)
❌  STAG-alt@15000: 6/100 unique tasks
❌  STAG-alt@20000: 12 rows (expected 200)
❌  STAG-alt@20000: 6/100 unique tasks
❌  STAG-rand@10000: 12 rows (expected 200)
❌  STAG-rand@10000: 6/100 unique tasks
❌  STAG-rand@15000: 12 rows (expected 200)
❌  STAG-rand@15000: 6/100 unique tasks
❌  STAG-rand@20000: 12 rows (expected 200)
❌  STAG-rand@20000: 6/100 unique tasks
✅  0 rows with step_count=0, 0 rows with total_tokens=0

## F3 — Eval-result self-consistency

✅  0 rows have resolved=None but patch_generated=True
❌  21 rows have exit_status='Submitted' but patch_generated=False
   sample tasks: {'sympy__sympy-13031': 6, 'scikit-learn__scikit-learn-13142': 3, 'scikit-learn__scikit-learn-14629': 2, 'django__django-15278': 2, 'django__django-12304': 1}
✅  0 rows have resolved=True but patch_generated=False

## F4 — Cross-validation against earlier numbers

✅  TR@15000: source=20, csv(ABL only)=20
✅  SU-full@15000: source=14, csv(ABL only)=14
✅  TRC@15000: source=31, csv(ABL only)=31
✅  SS@15000: source=18, csv(ABL only)=18
✅  FC@∞: source=23, csv(ABL only)=23
✅  TR@10000: source=29, csv(ABL only)=29
✅  TR@20000: source=36, csv(ABL only)=36
✅  TRC+SU@10000: source=33, csv(ABL only)=33
✅  TRC+SS@15000: source=35, csv(ABL only)=35
✅  SU-partial@15000: source=34, csv(ABL only)=34
✅  OTRC+SU-partial@15000: source=39, csv(ABL only)=39
✅  OTRC@∞: source=37, csv(ABL only)=37

**Overall F4: PASS** — Review1.csv matches source experiment_results.json

## F5 — Step count definition

LimitsExceeded runs: 975 total
  step_count distribution: min=125, max=125, median=125.0
  step_count ≥ 100: 975/975 runs

Silent-crash runs: 1680 total
  step_count distribution: min=5, max=124, median=74.0
  early-exit (<10 steps): 30 | mid (10-49): 393 | late (≥50): 1257

## F6 — Token accounting consistency

✅  0 rows have summarization_prompt_tokens > total_prompt_tokens
✅  0 rows where total_tokens != prompt + completion

## F8 — Bootstrap 95% CI per (primitive, budget) cell


```
primitive           budget  resolve%  95% CI              halfwidth (pp)
------------------------------------------------------------------------
OTRC+SS-partial      10000     29.0%  [22.5, 35.5]                  6.5
OTRC+SS-partial      15000     42.0%  [35.5, 49.0]                  6.8
OTRC+SS-partial      20000     47.0%  [40.0, 54.0]                  7.0
OTRC+SU-partial      10000     33.5%  [27.0, 40.5]                  6.8
OTRC+SU-partial      15000     39.5%  [32.5, 46.0]                  6.8
OTRC+SU-partial      20000     43.5%  [37.0, 50.5]                  6.8
OTRC+TR              10000     34.5%  [28.0, 41.0]                  6.5
OTRC+TR              15000     44.5%  [38.0, 51.5]                  6.8
OTRC+TR              20000     46.0%  [38.5, 52.5]                  7.0
SS                   10000     26.5%  [21.0, 32.5]                  5.8
SS                   15000     36.0%  [29.5, 43.0]                  6.8
SS                   20000     43.5%  [37.0, 50.0]                  6.5
SS-partial           10000     33.5%  [27.5, 40.0]                  6.2
SS-partial           15000     38.0%  [31.5, 45.0]                  6.8
SS-partial           20000     48.0%  [41.0, 55.0]                  7.0
STAG-alt             10000      0.0%  [0.0, 0.0]                    0.0
STAG-alt             15000      0.0%  [0.0, 0.0]                    0.0
STAG-alt             20000      8.3%  [0.0, 25.0]                  12.5
STAG-rand            10000      0.0%  [0.0, 0.0]                    0.0
STAG-rand            15000      0.0%  [0.0, 0.0]                    0.0
STAG-rand            20000      8.3%  [0.0, 25.0]                  12.5
SU-full              10000     32.5%  [26.5, 39.0]                  6.3
SU-full              15000     29.0%  [23.0, 35.5]                  6.2
SU-full              20000     38.5%  [32.0, 45.0]                  6.5
SU-partial           10000     35.0%  [28.5, 42.0]                  6.8
SU-partial           15000     43.5%  [37.0, 50.5]                  6.8
SU-partial           20000     47.5%  [40.5, 54.5]                  7.0
TR                   10000     39.5%  [33.0, 46.5]                  6.8
TR                   15000     38.5%  [32.0, 45.5]                  6.8
TR                   20000     43.5%  [37.0, 50.5]                  6.8
TRC                  10000     39.5%  [33.0, 46.5]                  6.8
TRC                  15000     45.5%  [38.5, 52.5]                  7.0
TRC                  20000     51.5%  [44.5, 58.5]                  7.0
TRC+SS               10000     44.0%  [37.0, 50.5]                  6.8
TRC+SS               15000     45.0%  [38.5, 52.0]                  6.8
TRC+SS               20000     53.0%  [46.0, 60.0]                  7.0
TRC+SU               10000     44.0%  [37.0, 51.0]                  7.0
TRC+SU               15000     47.0%  [40.0, 54.0]                  7.0
TRC+SU               20000     50.5%  [44.0, 57.5]                  6.7
FC                       ∞     43.0%  [36.0, 50.0]                  7.0
OTRC                     ∞     51.5%  [44.5, 58.5]                  7.0
```

Mean CI half-width across cells: **±6.4pp**. Differences smaller than 2× this width are within sampling noise.

## F9 — Per-task resolve rate (across all primitives × budgets × runs)

Tasks with 100% resolve rate (universally easy): 0
Tasks with 0% resolve rate (universally hard): 20
Tasks with < 10% resolve: 32
Tasks with > 90% resolve: 6

Top-5 easiest:
  django__django-11066                              98.6%
  sympy__sympy-24213                                98.6%
  django__django-12143                              97.1%
  django__django-14915                              95.7%
  sympy__sympy-19954                                95.7%

Top-5 hardest:
  sympy__sympy-13798                                 0.0%
  sympy__sympy-19040                                 0.0%
  sympy__sympy-18199                                 0.0%
  sympy__sympy-17630                                 0.0%
  sympy__sympy-20438                                 0.0%

Task-level resolve rate variance: σ = 35.6pp
Coefficient of variation: 0.86

## F11 — Repo as confounder


Resolve rate by repo (all primitives × budgets × runs pooled):

```
repo                                 n  resolved  resolve%  mean steps  mean tokens (k)
django                            2392       872     36.5%        68.4           601.6
scikit-learn                      2252      1012     44.9%        66.3           578.1
sympy                             2428      1012     41.7%        67.9           553.5
```

Per-primitive resolve rate by repo at 15k:

```
repo_full        django  scikit-learn  sympy
primitive                                   
OTRC+SS-partial    35.0          45.0   46.0
OTRC+SU-partial    40.0          44.0   35.0
OTRC+TR            37.0          55.0   43.0
SS                 38.0          33.0   37.0
SS-partial         31.0          39.0   44.0
STAG-alt            0.0           0.0    0.0
STAG-rand           0.0           0.0    0.0
SU-full            26.0          30.0   31.0
SU-partial         37.0          53.0   41.0
TR                 31.0          42.0   43.0
TRC                49.0          50.0   38.0
TRC+SS             41.0          53.0   41.0
TRC+SU             44.0          48.0   49.0
```

## F13 — Run-number bias (run_1 vs run_2)


run_num=1: 1455/3536 = 41.1%
run_num=2: 1441/3536 = 40.8%
Difference: +0.4pp
(if non-zero with high magnitude, indicates ordering effects in the runner)

## F14 — Task-selection provenance

Cohort = 30 ABL_TASKS (FC-stratified, original sprint) ∪ 70 P100_NEW_TASKS
(scaled-up cohort, drawn from broader SWE-bench Verified at expansion time).

**Implications:**
- Original 30 tasks remain FC-biased (selected for FC ≥ 0.5, stratified on compression outcome).
- 70 new tasks were added without the FC-success filter, so the 100-task cohort includes
  genuinely FC-fail cases — paired comparisons against FC are now less FC-favored.
- Result generalizes to: "100-task SWE-bench Verified subset spanning django, scikit-learn, sympy".
- Does NOT generalize to: full SWE-bench Verified across all repos.

FC-success split by cohort:
  ABL_TASKS (n=30):    FC ≥ 1/2 runs = 15/30, FC = 0/2 = 15/30
  P100_NEW (n=70):     FC ≥ 1/2 runs = 38/70, FC = 0/2 = 32/70