# devstral24b: rerun targets (summary_failure_accounting, summary_related_response, tb_erasure_possible, tb_unverifiable) archived on 2026-09-08 19:14:03 CDT

Source list: `/home/ak58925/agentCtx/archives/summary_bug_rerun_tooling_20260907_175359_CDT/rerun_list/rerun_runs.csv` (copied to `rerun_source/`). Selected rows: `rerun_source/selected_rows.csv`.
Selection: cohort_model_path=devstral24b, rerun_reason in [summary_failure_accounting, summary_related_response, tb_erasure_possible, tb_unverifiable].

## Why

These runs recorded FormatErrors on responses containing summary markers:
the pre-fix memory.py passed summary prompts through the agent model's `_parse_actions`.
This does not mean every summary call failed; some runs also recorded successful compression.
The summary-response format check was fixed in commit cd1716f
(`query_summary`). The runs are archived so that the same launcher re-executes them.

## What was done

- 407 runs across 8 cells; recorded rows 960 -> 553.
- Each run directory and its raw Harbor trial directory were moved here under the same
  path relative to the workspace root. Other trials of the same Harbor job stayed in place.
- Each `ICLR_results/.../experiment_results.json` here holds only the archived rows;
  `before/` holds the complete pre-modification files. The archived keys were removed
  from the canonical files, so the runner treats them as not yet executed.
- `run_info.json`/`run_info.md` are historical copies; the launcher rewrites them on rerun.
- Derived reports (COVERAGE*.csv) were not updated; regenerate after the rerun.

## Rerun

Before launching, make sure the runtime tree's `memory.py` contains the cd1716f fix
(`query_summary`); the agent imports `memory` from the workspace root on PYTHONPATH.
Then run the usual launcher, e.g. `bash scripts/run_agent_models_expansion_tb.sh devstral main`
(or the Slack wrapper). Completed keys are skipped; only the archived keys are re-executed.

## Counts (cell / condition / run / n)

- d05__b4k__ss	structured-summarize	run_1	2
- d05__b4k__ss	structured-summarize	run_2	3
- d05__b4k__ss	structured-summarize	run_3	3
- d05__b4k__ss-partial	structured-summarize-partial	run_1	4
- d05__b4k__ss-partial	structured-summarize-partial	run_2	4
- d05__b4k__ss-partial	structured-summarize-partial	run_3	2
- d05__b4k__su-full	summarization	run_1	34
- d05__b4k__su-full	summarization	run_2	31
- d05__b4k__su-full	summarization	run_3	29
- d05__b4k__su-partial	summarization-partial	run_1	31
- d05__b4k__su-partial	summarization-partial	run_2	32
- d05__b4k__su-partial	summarization-partial	run_3	33
- di__b4k__otrc-ss-partial	otrc-ss-partial	run_1	1
- di__b4k__otrc-ss-partial	otrc-ss-partial	run_2	2
- di__b4k__otrc-ss-partial	otrc-ss-partial	run_3	4
- di__b4k__otrc-su-partial	otrc-su-partial	run_1	31
- di__b4k__otrc-su-partial	otrc-su-partial	run_2	29
- di__b4k__otrc-su-partial	otrc-su-partial	run_3	29
- di__b4k__trc-ss	trc-ss	run_1	7
- di__b4k__trc-ss	trc-ss	run_2	5
- di__b4k__trc-ss	trc-ss	run_3	5
- di__b4k__trc-su	trc-su	run_1	27
- di__b4k__trc-su	trc-su	run_2	30
- di__b4k__trc-su	trc-su	run_3	29

## Tasks

- blind-maze-explorer-5x5
- blind-maze-explorer-algorithm
- cartpole-rl-training
- count-dataset-tokens
- crack-7z-hash.hard
- csv-to-parquet
- download-youtube
- eval-mteb
- eval-mteb.hard
- extract-moves-from-video
- fibonacci-server
- fix-git
- git-workflow-hack
- gpt2-codegolf
- heterogeneous-dates
- hf-model-inference
- incompatible-python-fasttext
- intrusion-detection
- modernize-fortran-build
- new-encrypt-command
- password-recovery
- path-tracing-reverse
- processing-pipeline
- prove-plus-comm
- pytorch-model-cli.hard
- qemu-alpine-ssh
- qemu-startup
- raman-fitting.easy
- sanitize-git-repo
- sanitize-git-repo.hard
- solana-data
- sqlite-with-gcov
- super-benchmark-upet
- swe-bench-astropy-2
- swe-bench-fsspec
- tmux-advanced-workflow
- write-compressor

Details: `tasks.tsv`, `manifest.json`, `move_plan.json`, `moves_completed.jsonl`.
Verification: 553 + 407 = 960; per-cell key sets preserved;
all 814 destinations exist and sources are gone.
