# GLM-4.7-Flash TB Main: Backup of Results After the 2026-09-05 Afternoon Resume

## Resume Information

- **Experiment launcher resumed:** 2026-09-05 14:57:12 CDT (UTC-05:00)
- **First Harbor job after the resume:** `glm47flash-summarization-partial-r1-1788638234822` (14:57:14.822 CDT)
- **Evidence:** beginning of `evidence/followup_tb_glm_main.nohup.log`
- `truncation` and `summarization` were already complete and skipped; execution resumed from **`summarization-partial` run 1**.

Job start times were verified by cross-checking the aggregation-row timestamps, `harbor_result.json` `started_at`, and the job start times under `config.trials_dir`. **File modification timestamps were not used.**

## Backed-Up Results

- **240 aggregated results** were backed up: **40 tasks × 2 conditions × 3 runs**, including both successful and failed results.
- The entire interrupted **`structured-summarize-partial` run 1** Harbor job was also backed up.
  - Trial directories exist for **11 of 40 planned tasks**; none of these 11 have been aggregated into `experiment_results.json`.
  - A `result.json` does **not** necessarily indicate normal completion or success. See `partial_tasks.tsv` for details.
  - No trial directories exist for the remaining **29 tasks**.
- **Total backup:** 240 aggregated run directories + **7 raw Harbor jobs** (6 aggregated + 1 interrupted/incomplete).

## Canonical Results and Re-Execution State

- Canonical aggregate: **480 → 240 results**.
- The retained 240 results are **120 `truncation` + 120 `summarization`**.
- The earlier **`summarization-partial` run 1** job started at **05:17:43 before the resume** remains in the original `logs` as interruption history and was **not restored into the aggregate**.
- The original `experiment_results.json` files for the **two backed-up conditions** are now empty arrays. Therefore, their **240 results will be treated as not yet executed** on rerun.
- The subsequently interrupted condition is also unaggregated and will therefore be an execution target.

## Backup Notes

- Original repository-relative paths are preserved.
- `before/`: aggregate JSON files before modification.
- `evidence/`: copies of the original logs and metadata retained as evidence.
- `run_info` is **historical information**, not the current completed-run count.
- Absolute paths in raw logs are preserved as they were at execution time.
- Derived reports such as **COVERAGE CSVs were not updated**; regenerate them from the canonical results if needed.

## Process Status

Before the backup, no experiment runner or Harbor processes were found running. **No processes were stopped as part of this operation.**

<br>

**Condition / Run / Number of Aggregated Results:**

- structured-summarize	run_1	40
- structured-summarize	run_2	40
- structured-summarize	run_3	40
- summarization-partial	run_1	40
- summarization-partial	run_2	40
- summarization-partial	run_3	40

<br>

**40 aggregated tasks (each task corresponds to the six combinations above):**

- blind-maze-explorer-5x5
- blind-maze-explorer-algorithm
- cartpole-rl-training
- count-dataset-tokens
- crack-7z-hash.hard
- csv-to-parquet
- decommissioning-service-with-sensitive-data
- download-youtube
- eval-mteb
- eval-mteb.hard
- extract-moves-from-video
- fibonacci-server
- fix-git
- fix-pandas-version
- fix-permissions
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


<br>

**11 tasks from the interrupted job (`structured-summarize-partial` run 1, not aggregated):**

- count-dataset-tokens
- fibonacci-server
- fix-permissions
- incompatible-python-fasttext
- path-tracing-reverse
- prove-plus-comm
- pytorch-model-cli.hard
- raman-fitting.easy
- solana-data
- sqlite-with-gcov
- tmux-advanced-workflow

<br>

**Detailed lists:** `tasks.tsv` (240 entries), `partial_tasks.tsv` (11 entries).

**Verification:** Confirmed that 240 + 240 = 480, that the key set for each cell was preserved, and that the destination paths for all 240 run directories and 7 raw jobs exist.

