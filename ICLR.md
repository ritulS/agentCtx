# ICLR 2027 — current target and source of truth

**Last verified** 2026-09-12. Abstract due Sept 18 2026, paper due Sept 25
2026, 9 pages of main text.

**Precedence.** This file wins over every other doc in the repo. Code and data
win over this file. When two sources disagree, say so rather than quietly
picking one.

## Framing of record

- `paper_sections_ICLR/Sec1_introduction.md` and `Sec2_CompDesignSpace.md`
  carry the framing. Compression is an execution policy. Policies trade task
  success against token cost and latency, and no single policy dominates.
- `paper_sections_ICLR/Paper_skeleton.md` is the section plan. It was written
  2026-08-26, before the current framing, and still points at a deleted spine
  and at EMNLP drafts. Trust Sec1 and Sec2 where they disagree.
- `paper_sections_ICLR/agent_compression_survey.md` holds the related-work
  notes on how deployed agents compress context.
- `paper_sections_ICLR/abstract.md` and `paper_sections_ICLR/Paper_spine.md`
  were deleted 2026-09-11. The cost-lever and audit-first framing they carried
  is retired. Do not reinstate it, and do not re-create those files. (A
  different, older `abstract.md` still sits at the repo root. See the sunset
  section.)
- Paper drafts live only in `/home/rs67788/projects/agentCtx` and are
  gitignored, so Akiho's clone does not have them.
- Show draft prose in chat before writing to any file in
  `paper_sections_ICLR/`.

## Source of truth by topic

| Topic | Where |
|---|---|
| Experiment grid and status | `ICLR_analysis/exp_grid.md` |
| Experiment plan | `ICLR_analysis/exp_grid.md` is the plan of record. `exp_plans/FOLLOWUP_EXPERIMENTS.md` is the Aug 24 background write-up and predates the ABL-25 switch. |
| Run data (canonical) | `/home/ak58925/agentCtx/ICLR_results/<bench>/<track>/<model>/<cell>/`, layout in `ICLR_results/README.md` |
| Run history | `ICLR_results/EXPERIMENT_LOG.md`, `ICLR_results/EXPERIMENT_TIMELINE_DETAIL_SWE.md` |
| Budget calibration | `ICLR_results/budget_calibration_swe.md` |
| Known data problems | `ICLR_results/issue/` |
| What runs exist (SWE-bench) | `analysis/outcomes/swebench_outcomes.csv`, built by `analysis/aggregate_benchmark_results.py` (see `analysis/README.md`) |
| Cell coverage | `COVERAGE.csv` via `dashboard/build_coverage.py`. **The committed copy is stale** — it dates from 2026-08-28 and has no Devstral or GLM rows. Regenerate before trusting it, or use the outcomes CSV. |
| Live run status | `Active_runs.md`, where Akiho's clone holds the live copy |
| Terminal-Bench data | Produced on Albus, see "Terminal-Bench runs on Albus" below |
| Run launchers | `scripts/run_experiment_iclr.py`, `scripts/run_agent_models_expansion.sh`, `scripts/run_budget_calibration_{sb,tb}.py` |
| Cost and latency framing | `exp_plans/FRAMING_cost_latency.md` (local to Ritul's clone) |
| Paper prose | `paper_sections_ICLR/` (local to Ritul's clone) |

## Setup at a glance

- Models. Qwen3.5-35B-A3B is the main agent model, with
  Devstral-Small-2-24B and GLM-4.7-Flash alongside it. The agent model is its
  own summarizer unless a summarizer-ablation cell says otherwise.
- Benchmarks. SWE-bench Verified uses P100 for main runs and ABL-25 for
  ablations. Terminal-Bench uses P40 for main runs and P15 for ablations, with
  room to expand later.
- Budgets are calibrated per model. Qwen uses 10K/15K/20K, Devstral uses
  17K/21K/24K, GLM uses 10K/13K/15K.
- Cells are named `{depth}__{budget}__{primitive}`, for example
  `d05__b15k__su-partial` and `di__binf__fc`. GLM cells use `bA`, `bP` and
  `bB` for its lower, primary and upper budgets rather than a token count, so
  a search for `b13k` finds nothing.
- Terminal-Bench cohorts have three spellings for the same sets. Ritul says
  P40 and P15, `ICLR_analysis/exp_grid.md` says ABL-15 and ABL-20, and
  `dashboard/build_coverage.py` says TB-40, TB-15 and TB-20. Settle this when
  TB analysis starts.
- 3 runs per task everywhere, except the Terminal-Bench summarizer ablation at
  5.

## Where new work goes

- Analysis code and its reports go in `ICLR_analysis/`, named after the
  question they answer, for example `ICLR_analysis/latency_decomposition.py`
  and `ICLR_analysis/latency_decomposition.md`. Do not extend `Review1/`,
  which analyses the older data.
- Generated figures go in `ICLR_analysis/figures/`, which `.gitignore`
  already excludes, so they stay local and regenerable.
- Paper prose goes in `paper_sections_ICLR/`, and only after the draft has
  been shown in chat.
- Read run data through `analysis/outcomes/*.csv` rather than walking
  `ICLR_results/` by hand, unless you need the raw trajectories.

## Terminal-Bench runs on Albus

Terminal-Bench runs on **Albus** (8× A6000), not on Dobby. Neither clone here
has an `ICLR_results/terminalbench/` tree, and the local `COVERAGE_TB.csv` is
header-only, so an empty file here is not evidence that the runs are missing.

TB analysis has not started. The mismatches below are known and deliberately
parked until then.

- Coverage of record is the `COVERAGE_TB.csv` on branch
  `origin/akiho-expansion-terminalbench-0829-data`, refreshed by cron. Read it
  with
  `git fetch origin && git show origin/akiho-expansion-terminalbench-0829-data:COVERAGE_TB.csv`.
  It runs ahead of `exp_grid.md`, which a person updates by hand, so cells the
  grid calls "in progress" may already be complete. Trust the CSV.
- The TB task files named in the grid (`task_lists/tbench_p40.json`,
  `task_lists/tbench_abl15.json`) live with the runs, not here. The
  `tbench_*.json` files in this clone are the older EMNLP-era sets.
- `dashboard/README.md` explains how TB coverage reaches the dashboard.

Before making a Terminal-Bench claim, get the data from that branch or ask
Akiho. Do not infer TB status from this filesystem.

## Read before making any claim from the data

- **Timeout confound.** `AGENT_TIMEOUT = 1500` in `scripts/run_experiment.py`
  kills long runs and labels them `silent_crash`. It hit summarization
  conditions hardest in the older Qwen data.
- **Summarizer parser loop.** The summarizer reply was parsed as an agent
  action, so a prose summary retried invisibly until the kill. Fixed in
  `memory.py` at commit f669241. Runs made before that fix carry it, which is
  why the summary-bug reruns exist.
- **Qwen prefix caching was off** in the production Qwen runs, a vLLM default
  for hybrid models. Other models had it on. Any cache or prefill claim has to
  account for this.
- **Some verdicts are under re-evaluation.** `ICLR_results/issue/` holds the
  candidate lists, currently for qwen35b and glm47flash main runs (dated
  2026-09-10) plus a resume audit. Check it before trusting a resolve rate.
- **Group the outcomes CSV by `model_key`, not `model`.** The 200 `di__binf__fc`
  baseline rows carry display names (`Devstral-Small-2-24B`) while every other
  row carries a key (`devstral24b`), so grouping on `model` splits the
  baseline away from its own model.

## EMNLP is sunset

The EMNLP submission is not the current direction. Read these only as
reference, and never as current framing.

- `paper_layout_EMNLP/` holds the old drafts and figures.
- `Review1/` holds the analysis pipeline over the older Qwen data in `data/`.
- `Review1/Emnlp_reviews/` holds the submission, the reviews and the rebuttal
  checklist.
- `abstract.md` at the repo root is an April 2026 draft from a still older
  framing ("No Free Compression"). It is not the ICLR abstract, and there is
  no current abstract file.

Worth carrying over. The axis taxonomy, now cut to three axes. The finding
that different policies solve different tasks. The latency trade behind the
cost leg. Check the caveat first. `Review1/execution_policy_report.md` reports
that the timing claim as worded does not survive a noise null, and that
9 to 28 of 100 tasks flip between reruns.
