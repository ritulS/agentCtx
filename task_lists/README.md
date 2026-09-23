# task_lists — pinned cohorts

Every experiment cohort is pinned to a file here so a run and an analysis can
agree on what was attempted. Files are tracked in git and identical in both
clones. **Do not rename or edit these files** — live scripts and the coverage
builder reference them by path, and editing one silently changes the meaning of
data already collected. To change a cohort, add a new file.

## SWE-bench Verified

Schema is a JSON list of `{"instance_id", "repo"}`.

| File | n | Cohort | Relation | Status |
|---|---|---|---|---|
| `p100_all_100_tasks.json` | 100 | **P100** | the main-track cohort | current |
| `ablation_25tasks.json` | 25 | **ABL-25** | ⊂ ABL-30 ⊂ P100 | **current ablation cohort** |
| `ablation_30tasks.json` | 30 | ABL-30 | ⊂ P100 | superseded, still the cohort most ablation runs were launched on |
| `p100_new_tasks.json` | 70 | NEW-70 | P100 ∖ ABL-30 | historical, used by `Review1/` |
| `selected_tasks.json` | 100 | alias of P100 | byte-content identical to `p100_all_100_tasks.json` | keep — it is the default `--tasks-file` in `scripts/run_experiment.py` |

### The ABL-25 rule

ABL-30 was reduced to ABL-25 for time. Most ablation runs on disk were launched
against ABL-30, so `ICLR_experiments/swebench/ablation/` contains 30 tasks per cell.

**Analysis filters to `ablation_25tasks.json`.** ABL-25 is a strict subset, so
this is a filter and not a data problem. `dashboard/build_coverage.py` already
treats ABL-25 as the cohort of record and reports extras as `ABL-25 (+N)`. The
5 tasks dropped in the reduction are `django__django-17087`,
`scikit-learn__scikit-learn-25747`, `scikit-learn__scikit-learn-26323`,
`sympy__sympy-24066` and `sympy__sympy-24443`.

Ablation cells are still filling. As of 2026-09-13, 32 of 52 qwen35b cells and
15 of 52 devstral24b cells are complete on all 25 tasks. Report the completeness
filter with any ablation table.

## Terminal-Bench

Schema differs — a JSON object with `dataset`, a provenance note, and a `tasks`
list of task names.

| File | n | Status |
|---|---|---|
| `tbench_tasks.json` | 20 | EMNLP-era, stratified selection from terminal-bench-core 0.1.1 |
| `tbench_pilot_tasks.json` | 18 | EMNLP-era pilot pool |
| `tbench_fc_char_batch2.json` | 17 | EMNLP-era FC characterization batch |

**None of these are the ICLR cohorts.** `ICLR_experiments/exp_grid.md` names
`tbench_p40.json` and `tbench_abl15.json`, which live with the runs on Albus and
are not in this repo. Copy them here before TB analysis starts, and record the
cohort-name mismatch noted in `/ICLR.md`.

## Adding a list

Name it after the cohort, not the experiment. Keep the schema of its benchmark.
Add a row above with its size, its relation to an existing cohort, and its
status. Commit it in the same change as the first run that uses it.
