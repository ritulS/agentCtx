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
  The root-level `memory.py` is only an alias to this module: the pinned
  mini-swe-agent commit (dec8de2) still does `import memory` from its
  compression hook. Remove the alias once the submodule is bumped to a commit
  that imports `agentctx.compression.primitives` directly (90624a1 exists
  locally; it needs push rights on ritulS/mini-swe-agent).
- `mini-swe-agent/` — submodule, fork at `github.com/ritulS/mini-swe-agent`,
  branch `agentctx-customizations`. The dispatch chain in
  `src/minisweagent/agents/default.py` calls primitives based on
  `MSWEA_PRIMITIVE` env var.
- `src/agentctx/` — shared Python package. `compression/` (primitives),
  `benchmarks/` (SWE-Bench and Terminal-Bench/Harbor adapters, verdict
  handling in `tb_verdict.py`, shared result conversion in
  `harbor_results.py` / `results.py`, the replay agent), `experiments/`
  (`conditions.py`, `runner.py`, `iclr.py`) and `summary_config.py`
  (summarizer-model overrides). `WORKSPACE_ROOT` and the `INFINITE_BUDGET`
  sentinel for uncompressed baselines are defined once in
  `src/agentctx/__init__.py`.
- `scripts/run_experiment.py` — CLI entry point for
  `src/agentctx/experiments/runner.py`. Conditions defined in
  `src/agentctx/experiments/conditions.py`; `--ablation`, `--budget`,
  `--tasks-file`, `--conditions`, `--summary-config` control a single sweep;
  the runner selects a benchmark adapter with `--benchmark`.
  `scripts/run_experiment_iclr.py` runs one cell of the canonical ICLR
  results tree. Launchers are grouped under
  `scripts/{calibration,expansions,serving,harbor,maintenance}/`; see
  `scripts/README.md`.
- `tests/` — runner-equivalence suite: runs `scripts/run_experiment.py`,
  `scripts/run_experiment_iclr.py` and the calibration launchers from the
  working tree and from the reference branch (`origin/akiho-clean-20260921`,
  the pre-reorganization tree) against deterministic fakes and diffs
  everything they write, plus unit tests for verdicts, the summarizer guard
  and the ablation launcher. `uvx --with pyyaml pytest`; see
  `tests/README.md`. Run it after touching `src/agentctx/experiments/` or
  `src/agentctx/benchmarks/`.
- `Review1/` — analysis suite. `Review1.csv` is the central data file. Scripts:
  `sanity.py`, `paired_analysis.py`, `routing_evidence.py`,
  `predictability_sprint.py`, `winners_table.py`, `plot_review1.py`,
  `plot_depth_outcomes.py`.
- `task_lists/` — pinned task JSONs (the 100-task set, the 6-task staggered
  pilot, etc.).
- `exp_plans/` — HANDOFF_COHERENCE (current direction), PRIOR_WORK_MLSys,
  DOBBY_PLAN, ALBUS_PLAN, CHARACTERIZATION_PAPER_PLAN_100tasks. Retired plans
  live in git history or `~/agentCtx_attic/exp_plans/`.
- `logs/` — gitignored. Shell launchers write
  `logs/experiments/<name>_<timestamp>.log` (+ `<name>.latest.log` symlink,
  locks, pid files) and vLLM servers write `logs/servers/vllm_<name>_<timestamp>.log`
  (+ `vllm_<name>.pid`); the outermost script owns the file through
  `scripts/lib/logpaths.sh` (`experiment_log`, `emit`, `AGENTCTX_LOG_FILE`).
  `scripts/notify_run.sh` wraps any launcher with Slack notices and
  detaches by default. Data directories under `logs/` (`harbor_jobs/`, ...)
  are separate.
- `Active_runs.md` — live status of long-running experiments. Update on
  launch/kill/completion.
- `COVERAGE.csv` — auto-generated cell-coverage sheet (one row per
  observed benchmark × model × primitive × budget × depth, with scope and
  status. Dirty/archived data is excluded; fresh Terminal-Bench data is read
  from its canonical path. Regenerate with
  `python dashboard/build_coverage.py` (then `dashboard/build_dashboard.py`)
  after any run completes or Review1.csv is rebuilt.

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
