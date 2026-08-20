# Expanding SWE-Bench
Last update: August 20 by Akiho


Experiments env: Dobby (GPU: 4* A100 80GB)

## Expansion 1: Runs/task: 2->3
- ETA: (8-)13 days
- Model: Qwen3.5-35B-A3B-Instruct
- Task: P100 (100 tasks)
- Context budget: 10K, 15K, 20K
- Runs/task : **3 (Additional 1 run/task** mostly)
- Metrics: resolve rate, token cost, latency, compression behavior


| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant | 

## Expansion 2: Add 2 models
- ETA: depending on models
- Model: **TBD**, **TBD**
- Task: P100 (100 tasks)
- Context budget: 10K, 15K, 20K
- Runs/task : 3
- Metrics: resolve rate, token cost, latency, compression behavior

| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant | 

## Expansion 3: Add ACON
- ETA: TBD
- Model: Qwen3.5-35B-A3B-Instruct (agent, AND judge/optimizer — see below)
- Task: P100 (100 tasks), reserve a small holdout subset from P100 for Stage 2
  validation rounds (size TBD)
- Context budget: 10K, 15K, 20K
- Runs/task : 3
- New primitive: `acon_summarize`, classified **depth-invariant** (canonical
  depth 0.5 only, all 3 budgets, P100) — same scope rule as TRC/TRC+SU/TRC+SS.

Source: ACON (arXiv 2510.00615), reference implementation
`github.com/microsoft/acon`. Porting the algorithm/prompt structure, not the
AppWorld-specific Python modules (Azure OpenAI client, AppWorld trajectory
format) — those don't apply to mini-swe-agent/SWE-bench.

ACON is two layers:
- **A) inference-time primitive** (`HistoryOptimizer` in the reference repo):
  summarize on a token threshold using an external **jinja prompt template**
  (not a hardcoded string), with a `preserve_last_k_turns` tail-keep. Same
  shape as our `summarize()`/`structured_summarize()`.
- **B) offline prompt-optimization loop** (the actual ACON contribution):
  iteratively rewrites that jinja template by having an LLM diagnose
  baseline-success/current-template-failure task pairs, then having an LLM
  rewrite the template to fix the diagnosed failure patterns. Produces
  `best_improved_history_prompt_samples.yaml`-equivalent per round.

### Stage 1 — primitive wiring (same effort as any existing primitive)
- `memory.py`: add `acon_summarize(messages, model, target_tokens, template_path)`
  — Jinja2-render an external `.jinja` template (`{{task}}`, `{{prev_summary}}`,
  `{{history}}`), reuse `_fit_tail`/`KEEP_RECENT` for the tail-keep behavior.
- `mini-swe-agent/.../default.py` (submodule, branch `agentctx-customizations`):
  one new `elif _primitive == "acon_summarize"` branch, dispatching on a new
  `MSWEA_ACON_TEMPLATE_PATH` env var.
- `run_experiment.py`: new `CONDITIONS` entry `acon-summarize` +
  `--acon-template` CLI override (same pattern as `--otrc-config`).
- Initial (round-0, un-optimized) template: adapt ACON's AppWorld
  `prompt_history_v2.jinja` structure to a coding agent — same information
  categories `structured_summarize()` already covers (Files Modified/Examined,
  Execution Anchors, Current State), just expressed as a `.jinja` file instead
  of hardcoded.

### Stage 2 — offline optimization loop (the ACON contribution proper)
- Judge/optimizer model = **Qwen3.5-35B-A3B (same as the agent, run locally
  via vLLM)** — no external API dependency, at the cost of possibly weaker
  diagnosis quality than the reference repo's o3/gpt-4.1 judge. Revisit if
  candidate templates don't show measurable improvement over round 0.
- ACON's two jinja meta-prompts (`history_regression_prompt.jinja`,
  `history_prompt_optimizer_prompt_by_samples.jinja`) are domain-agnostic in
  their field names — portable with minimal changes.
- New script `scripts/acon_optimize.py`:
  1. **analysis**: from `experiment_results.json` (`resolved` field) +
     `trajectory.json`, find task pairs where a baseline condition resolved
     and the current-round `acon-summarize` template did not; feed each pair's
     flattened history to the judge LLM → structured diagnosis JSON
     (missing/distorted facts, lost state vars, remediation recommendations)
     → `aggregated_history_regressions.json`.
  2. **update**: sample diagnoses, feed + current template to the optimizer
     LLM → N candidate templates for the next round.
  3. Run each candidate via `run_experiment.py --conditions acon-summarize
     --acon-template <candidate> --tasks-file <holdout>`, evaluate, pick best
     by resolve rate (tie-break: token cost) → becomes next round's template.
- Open items to resolve during implementation: holdout split size, number of
  rounds, convergence/stopping criterion.

| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC, acon_summarize | depth invariant | 