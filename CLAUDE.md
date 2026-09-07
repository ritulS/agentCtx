# agentCtx — project context

## What this project is

Empirical study of context-compression strategies for LLM agents on SWE-bench
Verified. The agent (`mini-swe-agent`) runs a tool-use loop, accumulating
trajectory tokens; a compression primitive fires when the token budget is
exceeded. Primitives include single-strategy (TR, SU-full, SU-partial, SS,
SS-partial, TRC), threshold-stacked (TRC+SU, TRC+SS), online (OTRC and
OTRC-stacked variants), and the new staggered ones that alternate or randomize
between two primitives at compression-event time.

Data flows: `results/ablations/<exp>/<task>/<condition>/run_<n>/trajectory.json`
→ `Review1/build_review1.py` → `Review1/Review1.csv` → analysis scripts in
`Review1/`. Paper spine: "compression beyond the budget" — even at unlimited
budget, no-compression resolves fewer tasks than compressed strategies on a
deployment-class agent. Online clearing wins on token cost; threshold stacking
wins on resolve rate.

## Two-machine workflow

This project is worked on across two machines:

- **Dobby** (primary): development, P100 expansion runs, depth/budget
  ablations, the staggered pilot. Serves Qwen3.5-35B-A3B continuously.
- **Albus** (8× A6000): hosts model-expansion runs (Qwen2.5-7B, Llama 3.3 70B)
  and the quantization sweep. Different model serving per phase.

**Sync discipline**: at task boundaries — finishing one experiment phase or
moving from analysis to runs — push commits from whichever machine you edited
on, then pull on the other. Don't let a code change live on one machine for
more than half a day without pushing. Code goes through git; experiment
results and logs are gitignored (too large) and transferred via rsync if
needed for cross-machine analysis. All collected run data lives in `data/`
(see `data/README.md`); `results/ablations`, `results/tbench`, and
`Review1/raw` are compatibility symlinks into it.

Per-machine queues live in [exp_plans/DOBBY_PLAN.md](exp_plans/DOBBY_PLAN.md)
and [exp_plans/ALBUS_PLAN.md](exp_plans/ALBUS_PLAN.md).

## Where things live

- `src/agentctx/compression/primitives.py` — compression primitive functions (`truncate`, `summarize`,
  `summarize_partial`, `structured_summarize`, `tool_result_clear`, etc.).
- `mini-swe-agent/` — submodule, fork at `github.com/ritulS/mini-swe-agent`,
  branch `agentctx-customizations`. The dispatch chain in
  `src/minisweagent/agents/default.py` calls primitives based on
  `MSWEA_PRIMITIVE` env var.
- `src/agentctx/` — shared Python package. `compression/` (primitives),
  `benchmarks/` (SWE-Bench and Terminal-Bench/Harbor adapters plus result
  conversion), `experiments/` (`conditions.py`, `runner.py`, `iclr.py`).
  `WORKSPACE_ROOT` and the `INFINITE_BUDGET` sentinel for uncompressed
  baselines are defined once in `src/agentctx/__init__.py`.
- `scripts/run_experiment.py` — CLI entry point for
  `src/agentctx/experiments/runner.py`. Conditions defined in
  `src/agentctx/experiments/conditions.py`; `--ablation`, `--budget`, `--tasks-file`, `--conditions`
  control a single sweep. `scripts/run_experiment_iclr.py` runs one cell of
  the canonical ICLR results tree. Launchers are grouped under
  `scripts/{calibration,expansions,serving,harbor}/`; see `scripts/README.md`.
- `Review1/` — analysis suite. `Review1.csv` is the central data file. Scripts:
  `sanity.py`, `paired_analysis.py`, `routing_evidence.py`,
  `predictability_sprint.py`, `winners_table.py`, `plot_review1.py`,
  `plot_depth_outcomes.py`.
- `task_lists/` — pinned task JSONs (the 100-task set, the 6-task staggered
  pilot, etc.).
- `exp_plans/` — HANDOFF_COHERENCE (current direction), PRIOR_WORK_MLSys,
  DOBBY_PLAN, ALBUS_PLAN, CHARACTERIZATION_PAPER_PLAN_100tasks. Retired plans
  live in git history or `~/agentCtx_attic/exp_plans/`.
- `Active_runs.md` — live status of long-running experiments. Update on
  launch/kill/completion.
- `COVERAGE.csv` — auto-generated cell-coverage sheet (one row per
  observed benchmark × model × primitive × budget × depth, with scope and
  status. Dirty/archived data is excluded; fresh Terminal-Bench data is read
  from its canonical path. Regenerate with
  `python dashboard/build_coverage_sb.py` (then `build_coverage_tb.py` and
  `build_dashboard.py`) after any run completes or Review1.csv is rebuilt.

## Vocabulary

Use these terms when discussing experimental coverage and depth runs.

**Primitive families** (mechanistic split by whether `compression_ratio` engages):

- **depth-tunable** — TR, SU-full, SU-partial, SS, SS-partial. The 5
  primitives whose behavior is a function of `compression_ratio`. Studied at
  all 3 depths.
- **depth-invariant** — TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial,
  OTRC+SS-partial. The 6 primitives where `compression_ratio` doesn't engage
  meaningfully. Studied at canonical depth only.

**Depths:**

- **canonical depth** = 0.5 (default; the only depth in scope for
  depth-invariant primitives).
- **tail depths** = 0.3, 0.7 (studied for depth-tunable primitives only).
- **depth grid** = {0.3, 0.5, 0.7} (the symmetric 3-point set).

**Cohorts:**

- **ABL-30** — original 30 FC-stratified ablation tasks
  (`results/ablations/tasks.json`).
- **NEW-70** — the 70 added tasks (`task_lists/p100_new_tasks.json`).
- **P100** — full cohort = ABL-30 ∪ NEW-70
  (`task_lists/p100_all_100_tasks.json`).

**Scope rule** (main model = Qwen3.5-35B-A3B) for whether a
`(primitive, budget, depth, cohort)` cell is in-scope for the paper:

- `depth-tunable` × `depth grid` × cohort ⊇ {P100 if budget=15k, ABL-30 if
  budget ∈ {10k, 20k}}.
- `depth-invariant` × `canonical depth` × **P100 at every budget**.

Any other `(primitive, depth, budget, cohort)` combination is **out-of-scope**
and not run. Model-expansion runs on Albus (Qwen2.5-7B, Llama 3.3 70B) follow
their own reduced-cohort scopes documented in `exp_plans/ALBUS_PLAN.md`.

## Critical rules

- **Never commit** `results/`, `logs/`, `archive/`, `temp/`, `Review1/raw/`,
  `PaperSections/`, `figures/`, `Review1/figures/` — all gitignored.
- **Always update** `Active_runs.md` when launching or killing a long-running
  experiment.
- **Submodule updates**: `cd mini-swe-agent`, commit + push there first
  (branch `agentctx-customizations`), then `git add mini-swe-agent` in parent
  to record the new pointer.
- **Don't write to `PaperSections/`** files without showing the user the draft
  content in chat first.
- **Don't propose routing/cascade as a paper direction** — user has called
  these dead ends.
