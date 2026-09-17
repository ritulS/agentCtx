# Outcome analysis

`aggregate_benchmark_results.py` aggregates canonical experiment records into
one CSV per benchmark:

- `outcomes/swebench_outcomes.csv`
- `outcomes/terminalbench_outcomes.csv` (created only after TB inputs exist)

Each row represents one task / primitive / run, with model, budget, depth, the
normalized outcome (`resolved` and `failure_mode`), and operational metrics.

`step_prompt_tokens` and `step_completion_tokens` contain the complete recorded
per-step arrays as JSON in a single CSV cell each, preserving their original
order and length. Decode these cells with `json.loads` after reading the CSV.
Missing or null arrays are blank; recorded empty arrays are `[]`.

Execution validity is recorded separately from task success:

- `execution_state`: `agent_started`, `pre_agent_failure`,
  `seeded_placeholder`, or `zero_step_unknown`.
- `agent_started`: whether the agent made at least one call or consumed tokens.
- `pre_agent_failure`: a recorded non-zero return code before agent activity.
- `returncode` and `seeded_from`: raw evidence for auditing the classification.

`seeded_placeholder` is not an unsuccessful agent attempt; it is a pointer to
a source result that is absent from the canonical cell.

`submission_generated` is only recorded by the devstral24b runner; it's blank
(not `False`) for every other model, meaning "not recorded" rather than "no
submission". Don't treat a blank there as a negative signal.

Summarizer provenance (summarizer ablation, FOLLOWUP_EXPERIMENTS.md §4) is
recorded per row:

- `agent_model_key`: `model_key` minus any `-sum-<summarizer>` suffix, so
  rows under `model_ablation/<agent>-sum-<summarizer>/<cell>` join with the
  self-summarization baseline under `main/<agent>`.
- `summarizer_model` / `summarizer_source`: from the run's own
  `summarization_model` record (written at generation time), falling back to
  the cell's `run_info.json` only for runs without one. `agent_model` means
  the agent summarized for itself; runs with neither record (archived copies,
  runs made before the override existed) are always `agent_model` with a
  blank `summarizer_model`.
- Model directories ending in `-smoke` (launcher smoke tests) are skipped.

Run both aggregations:

```bash
python3 analysis/aggregate_benchmark_results.py
```

Terminal-Bench results made elsewhere should be copied under
`ICLR_results/terminalbench/` (preserving the canonical result tree), then the
same command rebuilds `terminalbench_outcomes.csv`.  To aggregate a copied tree
without first placing it there:

```bash
python3 analysis/aggregate_benchmark_results.py \
  --benchmark terminalbench \
  --source-root /path/to/terminalbench-results
```

The generated CSVs are checked into Git (same treatment as `Review1/Review1.csv`)
so they stay in sync across machines without a rebuild; re-run the builder and
commit the refreshed CSV after new results land.
If an input benchmark directory is absent, the builder skips it and leaves any
existing CSV untouched.
