# ICLR 2027 Experiment Log — Terminal-Bench 2.0

Recorded: 2026-09-05. Experiments executed: 2026-09-04. Execution times below use CDT (UTC−05:00), as explicitly recorded in the shell logs.

## 1. Experiment and current results

FC@∞ `run_1` was attempted on all 89 Terminal-Bench 2.0 tasks with Qwen3.5-35B-A3B. Results from the initial execution, partial resume, and single-task retry were saved in the same result cell.

| Item | Verified value |
|---|---|
| Dataset | `terminal-bench@2.0`, 89 tasks |
| Model | `hosted_vllm/Qwen/Qwen3.5-35B-A3B` |
| Agent | `tbench.harbor_adapter:CompressionAgent` |
| GPU host | `albus` (experimenter-reported) |
| GPUs | 4 GPUs, configured as `0,1,2,3`; vLLM tensor parallelism = 4 |
| Runtime | Rootless Podman, with Harbor flags `--env docker --cpus ignore` |
| Condition | `full-context`, `run_num=1`, `budget=999999999` (implementation value for ∞) |
| Result cell | `ICLR_results/terminalbench2/main/qwen35b/di__binf__fc/` |
| Saved results | One row per task, 89 rows, no duplicate keys |
| Successes in saved results | `resolved=true`: 27/89 (30.34%) |
| Compression | `compression_events=0` in all 89 rows |

The initial run used 2× agent timeouts. We retained 24 trials—23 completed within the standard 1× limit and one timed out at 2×—and reran the remaining 65 tasks at 1×. Caffe was then retried separately.

## 2. Code provenance

| Purpose | Reference commit | Files |
|---|---|---|
| TB2 execution, partial resume, and image preparation | `8949b42` (2026-09-05 18:17 CDT) | — |
| Resume and retry task lists | `894a907` (2026-09-05 18:18 CDT) | `task_lists/tbench2_qwen_fc_run1_remaining.json`, `task_lists/tbench2_caffe_retry.json` |
| TB2 CSV aggregation and the 89-row CSV | `aee5728` (2026-09-04 22:13 CDT) | `analysis/outcomes/terminalbench2_outcomes.csv` |

- **Code:** `8949b42` was committed after execution; launch-time HEAD/hashes are unavailable.
- **Execution:** Harbor uses `tbench/harbor_adapter.py` directly; the `9523ef0` shutdown workaround is unused.
- **Dataset:** Local source and working copy are at `2fd12b8`. Execution used the prebuild-modified copy; per-trial `task_checksum` values are saved.

## 3. Image preparation

- **Process:** `tb2_harbor_prebuild_images.sh` calls the shared prebuild script and configures a working copy to use `localhost/tb2-<task>-<service>:latest` images.
- **Result:** All 89 tasks prebuilt successfully (September 4, 10:43–11:36 CDT). The logged failure was the non-task `.git` directory.
- **Runtime:** Rootless Podman, `apt-only (ownership semantics preserved)`.

**Reconstructed command** (the original outer shell invocation was not verified):

```bash
cd /home/ak58925/agentCtx
TB2_HARBOR_SOURCE_DATASET="$PWD/data/terminal-bench-2-source" \
TB2_HARBOR_WORK_DATASET="$PWD/data/tb2-harbor-prebuilt-2.0" \
  bash scripts/tb2_harbor_prebuild_images.sh
```

Evidence: [prebuild log](../logs/tb2_harbor_prebuild.log), [launcher log](../logs/tb2_harbor_prebuild_launcher.log).

## 4. FC@∞ execution history and commands

- **Commits:** `8949b42` (execution/resume scripts; committed after execution), `894a907` (task lists).
- **Commands:** Reconstructed from saved Harbor arguments; logged commands are in the appendix.
- **Prerequisites:** Qwen vLLM at `http://localhost:8000/v1` and a running Rootless Podman API.
- **GPU setup:** [Qwen launcher](../scripts/start_vllm_qwen35.sh) defaults to GPUs `0–3`; [vLLM log](../logs/vllm_qwen35.log) confirms `tensor_parallel_size=4`.
- **Configs:** `configs/config-qwen-vllm.yaml` and `configs/config-tbench.yaml`.
- **Environment:**

    ```text
    MSWEA_PRIMITIVE=truncation
    MSWEA_TOKEN_BUDGET=999999999
    MSWEA_COMPRESSION_RATIO=0.5
    MSWEA_COST_TRACKING=ignore_errors
    COMPOSE_BAKE=false
    ```

### 4.1 Initial execution: 89 tasks, 2× agent timeouts

Started September 4 at 13:33:38, with concurrency 4 and agent timeout multiplier **2.0**.

```bash
cd /home/ak58925/agentCtx
N_CONCURRENT=4 AGENT_TIMEOUT_MULTIPLIER=2.0 \
  bash scripts/run_budget_calibration_tb2.sh qwen
```

Job name: `tb2-qwen35b-fc-run1`. Its `finished_at` remains `null`. There are 30 saved individual trials: 24 without a Harbor exception, one `AgentTimeoutError`, one `AddTestsDirError`, and four `CancelledError` trials. This was not a successfully completed 89-trial job.

Evidence: [initial execution log](../logs/tb2_qwen35b_fc_run1.nohup.log), [initial job directory](../logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc/tb2-qwen35b-fc-run1/).

### 4.2 Preserving results and resuming 65 tasks

- **Keep:** Trials completed without exceptions within the 1× limit (+5 s tolerance), plus `AgentTimeoutError` trials.
- **Rerun:** Remaining 65 tasks at 1×, concurrency 4.
- **Task list:** `task_lists/tbench2_qwen_fc_run1_remaining.json`.

**Prepare the task list** (reconstructed command; execution stdout unavailable):

```bash
venv-harbor/bin/python scripts/prepare_tb2_fc_resume.py
```

**Resume:**

```bash
N_CONCURRENT=4 AGENT_TIMEOUT_MULTIPLIER=1.0 \
TB2_JOB_NAME=tb2-qwen35b-fc-run1-resume-1x \
  bash scripts/run_budget_calibration_tb2.sh qwen \
    task_lists/tbench2_qwen_fc_run1_remaining.json
```

- **Launches:** September 4, 14:57:01 and 14:57:03 CDT, both using the same job name; 130 trial files remain.
- **Collection:** Results were saved before the trial-count check failed (129/130 found, 65 expected).
- **Duplicates:** Rows with the same `(task, run_num)` are replaced in path order, without prioritizing recency or success.

```text
Harbor produced 129 trial results, expected 65
Harbor produced 130 trial results, expected 65
```

Evidence: [shared execution log](../logs/qwen35b_tb2_fc_run1.log), [resume launcher log](../logs/tb2_qwen35b_fc_run1_resume_1x.nohup.log), [resume job directory](../logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc/tb2-qwen35b-fc-run1-resume-1x/).

### 4.3 Single-task retry: caffe-cifar-10

- **Time:** September 4, 18:53:19–18:59:31 CDT.
- **Settings:** `caffe-cifar-10` only, 1× time limit, concurrency 1.

```bash
N_CONCURRENT=1 AGENT_TIMEOUT_MULTIPLIER=1.0 \
TB2_JOB_NAME=tb2-qwen35b-fc-run1-caffe-retry-20260904-185318 \
  bash scripts/run_budget_calibration_tb2.sh qwen \
    task_lists/tbench2_caffe_retry.json
```

- **Result:** `AddTestsDirError` again when copying verifier tests; `verifier_result=null`.
- **Collection:** Retry result saved, then task-name validation failed: selected `caffe-cifar-10`, returned `terminal-bench/caffe-cifar-10`.

```text
Harbor job contains tasks outside the selected task scope: terminal-bench/caffe-cifar-10
```

Evidence: [caffe retry log](../logs/tb2_caffe_retry.nohup.log), [caffe job directory](../logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc/tb2-qwen35b-fc-run1-caffe-retry-20260904-185318/).

## 5. Provenance and interpretation of saved results

Trial IDs in the saved `harbor_result.json` files were matched against the job results.

| Source job | Rows in the final 89-row aggregate | Agent timeout multiplier |
|---|---:|---:|
| `tb2-qwen35b-fc-run1` | 24 | 2.0 |
| `tb2-qwen35b-fc-run1-resume-1x` | 64 | 1.0 |
| `tb2-qwen35b-fc-run1-caffe-retry-20260904-185318` | 1 | 1.0 |

The retained 2× timeout was `adaptive-rejection-sampler`: 1,800 seconds against a standard limit of 900 seconds. Its verifier returned reward=1 after timeout, so the saved 27 successes include this trial.

Across the final 89 trials, 71 have no Harbor exception, 17 have `AgentTimeoutError`, and one has `AddTestsDirError`. Exceptions and success are separate attributes: a trial with a positive reward is marked `resolved=true` even if it timed out.

The saved CSV has the following classifications. These are the aggregation script's categories and differ from the Harbor exception counts.

| `failure_mode` | Count |
|---|---:|
| `resolved` | 27 |
| `submitted_unresolved` | 27 |
| `incomplete` | 16 |
| `limits_exceeded` | 15 |
| `agent_error` | 4 |

## 6. Artifacts and aggregation

- [Normalized 89-row JSON](terminalbench2/main/qwen35b/di__binf__fc/experiment_results.json)
- Per-task directory `terminalbench2/main/qwen35b/di__binf__fc/terminal-bench/<task>/full-context/run_1/`: `harbor_result.json`, `trajectory.json`, `token_log.json`, `exit_info.json`, and other files available in the source trial
- [TB2 outcome CSV](../analysis/outcomes/terminalbench2_outcomes.csv): committed in `aee5728`
- [TB2 aggregation script](../analysis/aggregate_terminalbench2_results.py)

The command to generate the CSV is shown below. The existing CSV and corresponding script were verified, but a historical execution log for this aggregation command was not.

```bash
python3 analysis/aggregate_terminalbench2_results.py
```

The TB2 launcher passes `--skip-postprocess`, so CSV aggregation is a separate step. The aggregator reads all rows in the TB2 result tree without filtering through TB1 task lists.

## Appendix: Harbor commands recorded in the logs

The following commands reproduce the shared execution log’s `+ /.../harbor run` lines with line breaks added and arguments unchanged. The resume command appears twice in that log. These lines do not include environment variables.

### Initial execution (2× timeouts, 89 tasks)

```bash
/home/ak58925/agentCtx/venv-harbor/bin/harbor run \
  --agent tbench.harbor_adapter:CompressionAgent \
  --model hosted_vllm/Qwen/Qwen3.5-35B-A3B \
  --path /home/ak58925/agentCtx/data/tb2-harbor-prebuilt-2.0 \
  --n-attempts 1 \
  --n-tasks 89 \
  --n-concurrent 4 \
  --agent-timeout-multiplier 2.0 \
  --env docker \
  --cpus ignore \
  --jobs-dir /home/ak58925/agentCtx/logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc \
  --job-name tb2-qwen35b-fc-run1 \
  --yes
```

### Resume (1× timeouts, 65 tasks; identical command recorded twice)

```bash
/home/ak58925/agentCtx/venv-harbor/bin/harbor run \
  --agent tbench.harbor_adapter:CompressionAgent \
  --model hosted_vllm/Qwen/Qwen3.5-35B-A3B \
  --path /home/ak58925/agentCtx/data/tb2-harbor-prebuilt-2.0 \
  --n-attempts 1 \
  --n-tasks 65 \
  --n-concurrent 4 \
  --agent-timeout-multiplier 1.0 \
  --env docker \
  --cpus ignore \
  --jobs-dir /home/ak58925/agentCtx/logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc \
  --job-name tb2-qwen35b-fc-run1-resume-1x \
  --yes \
  --include-task-name build-cython-ext \
  --include-task-name build-pmars \
  --include-task-name caffe-cifar-10 \
  --include-task-name cancel-async-tasks \
  --include-task-name chess-best-move \
  --include-task-name cobol-modernization \
  --include-task-name code-from-image \
  --include-task-name compile-compcert \
  --include-task-name configure-git-webserver \
  --include-task-name constraints-scheduling \
  --include-task-name crack-7z-hash \
  --include-task-name db-wal-recovery \
  --include-task-name distribution-search \
  --include-task-name dna-assembly \
  --include-task-name dna-insert \
  --include-task-name extract-elf \
  --include-task-name extract-moves-from-video \
  --include-task-name feal-differential-cryptanalysis \
  --include-task-name feal-linear-cryptanalysis \
  --include-task-name filter-js-from-html \
  --include-task-name financial-document-processor \
  --include-task-name fix-code-vulnerability \
  --include-task-name fix-git \
  --include-task-name fix-ocaml-gc \
  --include-task-name git-multibranch \
  --include-task-name gpt2-codegolf \
  --include-task-name hf-model-inference \
  --include-task-name install-windows-3.11 \
  --include-task-name large-scale-text-editing \
  --include-task-name largest-eigenval \
  --include-task-name llm-inference-batching-scheduler \
  --include-task-name log-summary-date-ranges \
  --include-task-name make-doom-for-mips \
  --include-task-name make-mips-interpreter \
  --include-task-name mcmc-sampling-stan \
  --include-task-name merge-diff-arc-agi-task \
  --include-task-name model-extraction-relu-logits \
  --include-task-name mteb-leaderboard \
  --include-task-name mteb-retrieve \
  --include-task-name multi-source-data-merger \
  --include-task-name nginx-request-logging \
  --include-task-name openssl-selfsigned-cert \
  --include-task-name overfull-hbox \
  --include-task-name password-recovery \
  --include-task-name path-tracing \
  --include-task-name polyglot-c-py \
  --include-task-name polyglot-rust-c \
  --include-task-name portfolio-optimization \
  --include-task-name pytorch-model-cli \
  --include-task-name pytorch-model-recovery \
  --include-task-name qemu-alpine-ssh \
  --include-task-name qemu-startup \
  --include-task-name query-optimize \
  --include-task-name regex-log \
  --include-task-name reshard-c4-data \
  --include-task-name rstan-to-pystan \
  --include-task-name sam-cell-seg \
  --include-task-name sanitize-git-repo \
  --include-task-name schemelike-metacircular-eval \
  --include-task-name sqlite-db-truncate \
  --include-task-name torch-tensor-parallelism \
  --include-task-name train-fasttext \
  --include-task-name vulnerable-secret \
  --include-task-name winning-avg-corewars \
  --include-task-name write-compressor
```

### Caffe retry (1× timeouts, one task)

```bash
/home/ak58925/agentCtx/venv-harbor/bin/harbor run \
  --agent tbench.harbor_adapter:CompressionAgent \
  --model hosted_vllm/Qwen/Qwen3.5-35B-A3B \
  --path /home/ak58925/agentCtx/data/tb2-harbor-prebuilt-2.0 \
  --n-attempts 1 \
  --n-tasks 1 \
  --n-concurrent 1 \
  --agent-timeout-multiplier 1.0 \
  --env docker \
  --cpus ignore \
  --jobs-dir /home/ak58925/agentCtx/logs/harbor_jobs/terminalbench2/main/qwen35b/di__binf__fc \
  --job-name tb2-qwen35b-fc-run1-caffe-retry-20260904-185318 \
  --yes \
  --include-task-name caffe-cifar-10
```
