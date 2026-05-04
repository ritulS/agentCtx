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
- **Albus** (6× A6000): hosts model-expansion runs (Qwen2.5-7B, Llama 3.3 70B)
  and the quantization sweep. Different model serving per phase.

**Sync discipline**: at task boundaries — finishing one experiment phase or
moving from analysis to runs — push commits from whichever machine you edited
on, then pull on the other. Don't let a code change live on one machine for
more than half a day without pushing. Code goes through git; experiment
results (`results/ablations/*`) and logs are gitignored (too large) and
transferred via rsync if needed for cross-machine analysis.

Per-machine queues live in [exp_plans/DOBBY_PLAN.md](exp_plans/DOBBY_PLAN.md)
and [exp_plans/ALBUS_PLAN.md](exp_plans/ALBUS_PLAN.md).

## Where things live

- `memory.py` — compression primitive functions (`truncate`, `summarize`,
  `summarize_partial`, `structured_summarize`, `tool_result_clear`, etc.).
- `mini-swe-agent/` — submodule, fork at `github.com/ritulS/mini-swe-agent`,
  branch `agentctx-customizations`. The dispatch chain in
  `src/minisweagent/agents/default.py` calls primitives based on
  `MSWEA_PRIMITIVE` env var.
- `scripts/run_experiment.py` — main run harness. Conditions defined in the
  `CONDITIONS` list; `--ablation`, `--budget`, `--tasks-file`, `--conditions`
  control a single sweep.
- `Review1/` — analysis suite. `Review1.csv` is the central data file. Scripts:
  `sanity.py`, `paired_analysis.py`, `routing_evidence.py`,
  `predictability_sprint.py`, `winners_table.py`, `plot_review1.py`,
  `plot_depth_outcomes.py`.
- `task_lists/` — pinned task JSONs (the 100-task set, the 6-task staggered
  pilot, etc.).
- `exp_plans/` — DOBBY_PLAN, ALBUS_PLAN, plus per-ablation handoff docs.
- `Active_runs.md` — live status of long-running experiments. Update on
  launch/kill/completion.

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
