# Devstral TB Main: Backup of Results After the 2026-09-05 Afternoon Resume

## Resume Information

- **vLLM started:** around 14:52 CDT on 2026-09-05.
- **Experiment launcher resumed:** 2026-09-05 14:56:30 CDT (UTC-05:00).
- **First Harbor job after the resume:** `devstral24b-trc-ss-r2-1788638197266` (14:56:37.266 CDT).
- **Evidence:** beginning of `evidence/followup_tb_devstral_main.nohup.log`, together with each run's `harbor_result.json`, `config.trials_dir`, and `started_at`.

Row timestamps represent **trial start times**; file modification timestamps were not used. All **680 results** were verified to belong to the **17 jobs started after the resume**.

## Backed-Up Results

- **680 task-condition-run results** were backed up, covering **40 distinct tasks across 17 Harbor jobs**, regardless of success or failure.
- Canonical results: **1560 → 880 results**.
- The retained 880 results consist of **`trc-ss` run 1** and **120 results for each of the seven preceding conditions**.
- The affected run directories and raw Harbor jobs were moved under this backup directory while preserving their **original repository-relative paths**.

## Canonical Results and Re-Execution State

- Each `experiment_results.json` contains only the rows selected for backup.
- `before/` contains the complete pre-modification JSON for the **six affected cells**.
- The backed-up keys were removed from the original `experiment_results.json` files. Therefore, rerunning the same main command will treat all **680 results as not yet executed**.
- The earlier **`trc-ss` run 2** job started at **10:26 before the resume** remains in the original `logs` as interruption history and was **not restored into the results**.

## Backup Notes

- `evidence/` contains copies of the original logs; the originals remain in place.
- `run_info` was copied as **historical information** and does not represent the current number of completed runs.
- Existing derived reports such as **COVERAGE CSVs were not updated**; regenerate them from the current canonical results when aggregating.
- Absolute paths in raw logs remain unchanged from execution time. The backed-up files are now located under **this directory + their original repository-relative paths**.

<br>

**Condition / Run / Count:**

- full-context	run_1	40
- full-context	run_2	40
- full-context	run_3	40
- online-trc	run_1	40
- online-trc	run_2	40
- online-trc	run_3	40
- otrc-ss-partial	run_1	40
- otrc-ss-partial	run_2	40
- otrc-ss-partial	run_3	40
- otrc-su-partial	run_1	40
- otrc-su-partial	run_2	40
- otrc-su-partial	run_3	40
- otrc-tr	run_1	40
- otrc-tr	run_2	40
- otrc-tr	run_3	40
- trc-ss	run_2	40
- trc-ss	run_3	40

<br>

**All affected tasks (each task corresponds to all 17 combinations above):**

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

**Details for all 680 entries:** `tasks.tsv`. **Machine-readable manifest:** `manifest.json`.

**Verification:** Confirmed that 880 + 680 = 1560, that the key set for each cell was preserved, and that the destination paths for all 680 run directories and 17 raw jobs exist.

