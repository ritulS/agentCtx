# ICLR 2027 Experiment Log — Terminal-Bench

Experiment Plan → [FOLLOWUP_EXPERIMENTS.md](../exp_plans/FOLLOWUP_EXPERIMENTS.md)

Code provenance below identifies commits containing the relevant implementation.
A workspace HEAD at launch does not identify executed code when the working tree
has uncommitted changes. For those runs, a later commit is a reconstruction
reference; establishing an exact match requires a run-time snapshot or recorded
file hashes/diff. The historical mappings below are recorded provenance, not an
independent verification of that match.

# Follow-up 4 — Terminal-Bench 1.0 evaluation

**Contents**

- [1. Image Prebuild](#image-prebuild)
- [2. FC calibration on the 42/38 split](#fc-calibration)
- [3. FC@∞ repetitions on the 42-task subset](#fc-repetitions)
- [4. Production experiments — Main and ablation](#production-experiments)
- [5. September 8–12 — Second rerun selection and Main completion](#main-completion)
- [6. P-15 ablation (3.b)](#ablation)
- [7. Summarizer ablation on Terminal-Bench](#summarizer-ablation)
- [8. Prefix-cache ablation on Terminal-Bench](#prefix-cache-ablation)

<a id="image-prebuild"></a>

## 1. Image Prebuild

### Summary

| Item | Value |
|---|---|
| Status | **Complete: 80/80 images** |
| Dataset | Terminal-Bench Core 1.0 / `terminal-bench-core@0.1.1` |
| Dataset source commit | `91e1045` |
| Prebuild implementation | `77b6da5` |
| Runtime | Rootless Podman |
| Build log | `logs/tb1_harbor_prebuild.log` |

The 80 tasks were split by the user-namespace setup required to prebuild them:

| Subset | Tasks | Rootless configuration | Completed | Prebuild implementation commit |
|---|---:|---|---|---|
| `P-80-rootless` | 42 | Single UID/GID; no subuid/subgid | 2026-08-29 16:10 CDT | `77b6da5` |
| `P-80-subuid-required` | 38 | Subordinate UID/GID mapping and `uidmap` | 2026-08-30 19:57 CDT | `77b6da5` |

Both subsets use the same Terminal-Bench source commit (`91e1045`) and the
same prebuild implementation (`77b6da5`). The difference is only the
rootless Podman user-namespace configuration.

<details>
<summary>Why prebuild was needed</summary>

- Docker Compose v5/buildx could not run its privileged BuildKit container
  under rootless Podman.
- Native sequential Podman builds avoided that limitation.
- `uv` was baked into each main task image so verifier setup is not included
  in experimental runtime.
- Multi-service task images were also prebuilt and referenced from the
  migrated Compose files.
- `ROOTLESS_CHOWN_WORKAROUND=1` was **not** used; normal ownership semantics
  were preserved.
</details>

<br>
Image build time is excluded from `agent_latency_s`, `llm_latency_s`, and
`e2e_latency_s`. All models and repetitions reuse these images.

### Prebuild results

| Phase | Result | Task list |
|---|---|---|
| Single-UID rootless | 42 succeeded, 38 failed on ownership operations | `task_lists/tbench_p80_rootless.json` |
| Rootless with subuid/subgid | Remaining 38 succeeded | `task_lists/tbench_p80_subuid_required.json` |
| Final | **80 succeeded, 0 failed** | `logs/tb1_harbor_prebuild.log` |

The complete host setup, subordinate-ID mapping, validation, and rollback
procedure for the 38-task phase is documented in
[tb_prebuild.md](./tb_prebuild.md).

### Reproduce or validate

  ```bash
  cd /home/ak58925/agentCtx
  export PATH="/home/rs67788/.local/bin:/usr/bin:$PATH"
  export TB_PODMAN=/home/rs67788/.local/bin/podman
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  ```

Resume the prebuild in the background; existing images are skipped:

  ```bash
  nohup setsid bash scripts/tb_harbor_prebuild_images.sh \
    > logs/tb1_harbor_prebuild_driver.log 2>&1 < /dev/null &
  echo $! > logs/tb1_harbor_prebuild.pid
  ```

Check the partition and final result:

  ```bash
  jq '.tasks | length' task_lists/tbench_p80_rootless.json
  jq '.tasks | length' task_lists/tbench_p80_subuid_required.json
  grep -E 'prebuilt OK \(|failed \(' logs/tb1_harbor_prebuild.log | tail
  ```

Expected: task-list sizes `42` and `38`; final prebuild result
`prebuilt OK (80)` and `failed (0)`.

<a id="fc-calibration"></a>

## 2. FC calibration on the 42/38 split

Code references for `run_1`:

- **Rootless (42 tasks):** Qwen — `77b6da5`; Devstral and GLM — `6042415`.
- **Subuid (38 tasks):** all three models — `55d9ea5`.

Each vLLM server uses all four GPUs. **Run one model at a time:** start one
server, run that model's experiments, stop it, and then switch models.

### Start one model

Run exactly one of these profiles before using the common workflow below:

  ```bash
  # Qwen3.5-35B-A3B
  MODEL=qwen
  MODEL_KEY=qwen35b
  START_SCRIPT=scripts/start_vllm_qwen35.sh   # since 2026-09-21: scripts/start_vllm_qwen35_prefix_cache_ablation.sh
  PORT=8000
  PID_FILE=logs/vllm_qwen35.pid
  ```

  ```bash
  # Devstral-Small-2-24B
  MODEL=devstral
  MODEL_KEY=devstral24b
  START_SCRIPT=scripts/start_vllm_devstral.sh
  PORT=8002
  PID_FILE=logs/vllm_devstral.pid
  ```

  ```bash
  # GLM-4.7-Flash
  MODEL=glm
  MODEL_KEY=glm47flash
  START_SCRIPT=scripts/start_vllm_glm47flash.sh
  PORT=8003
  PID_FILE=logs/vllm_glm47flash.pid
  ```

### Common workflow

1. Start the selected model and wait for its API:

    ```bash
    cd /home/ak58925/agentCtx
    bash "$START_SCRIPT"

    until curl -fsS "http://localhost:${PORT}/v1/models" >/dev/null; do
      echo "Waiting for $MODEL vLLM..."
      sleep 10
    done
    ```

2. Configure Podman and run the 42- and 38-task `run_1` calibrations:

    ```bash
    export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
    export N_CONCURRENT=4

    bash scripts/run_budget_calibration_tb.sh "${MODEL}-rootless"
    bash scripts/run_budget_calibration_tb.sh "${MODEL}-subuid"
    ```

3. Stop vLLM before selecting the next model:

    ```bash
    VLLM_PID=$(cat "$PID_FILE")
    ps -fp "$VLLM_PID"
    kill -TERM "$VLLM_PID"

    while kill -0 "$VLLM_PID" 2>/dev/null; do
      sleep 5
    done
    ```

Repeat these three steps for Qwen, Devstral, and GLM. Canonical outputs are:

```text
ICLR_results/terminalbench/main/p80_rootless/<model-key>/di__binf__fc/
ICLR_results/terminalbench/main/p80_subuid_required/<model-key>/di__binf__fc/
```

The model keys are `qwen35b`, `devstral24b`, and `glm47flash`.

<a id="fc-repetitions"></a>

## 3. FC@∞ repetitions on the 42-task subset

The initial calibration supplied `run_1`. The remaining four repetitions
(`run_2`–`run_5`) were then run for all three models on `P-80-rootless`.

Code reference for these repetitions: `6042415`.

#### Commands used

For each model, after starting its vLLM server with the common workflow above:

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
export N_CONCURRENT=4

bash scripts/run_terminalbench_rootless_fc_expansion.sh "$MODEL"
```

The server was stopped before selecting and running the next model.

- The GLM launcher was interrupted after `run_2`; the remaining runs were
resumed with:

    ```bash
    START_RUN=3 END_RUN=5 \
      bash scripts/run_terminalbench_rootless_fc_expansion.sh glm
    ```

Final aggregate size for each model: **42 tasks × 5 runs = 210 rows**.

<a id="production-experiments"></a>

## 4. Production experiments — Main and ablation

All timestamps below are **CDT (UTC−5)**, from the experiment logs.
Commands were recovered from shell history; that history has no timestamps.
Workspace HEADs are reconstructed from the local reflog. These commands
document historical launches, including resumes that skip existing results.

### Code references and scope

| Component | Commit containing the implementation |
|---|---|
| Terminal-Bench adapter for the experiment harness | `5b2c07e` |
| P-40 Main / P-15 ablation task lists | `13e750b` |
| `run_agent_models_expansion_tb.sh` and Terminal-Bench output routing in `run_experiment_iclr.py` | `9db3edb` |
| Qwen notification wrapper, `run_qwen_tb_with_slack.sh` | `9a024e7` |

The Main grid is **40 tasks × 13 conditions × 3 repetitions = 1,560
planned runs per model**. The primary budgets are Qwen **3K**, Devstral
**4K**, and GLM **3K**; FC and OTRC use an effectively unlimited budget.
The five depth-tunable primitives use depth 0.5; the six remaining finite-budget
primitives and the two baselines are recorded as depth-invariant cells.
Outputs are under `ICLR_results/terminalbench/main/<model-key>/<cell>/`.

### (a) Qwen — P-40 Main, then P-15 ablation

- Before switching to P-40, Qwen ran part of an **80-task, 3K-budget** grid
starting on **2026-08-31 09:53:32**. Workspace HEAD was `55d9ea5`; the
P-80 launcher was uncommitted, with no exact committed version identified.

    ```bash
    nohup env DOCKER_HOST="$DOCKER_HOST" QWEN_P_BUDGET=3000 N_CONCURRENT=4 \
      bash scripts/run_agent_models_expansion_tb.sh qwen \
      > logs/run_agent_models_expansion_tb_qwen_b3k.nohup.log 2>&1 < /dev/null &
    ```

    Results were written under `ICLR_results/terminalbench/main/qwen35b/`, to
    `d05__b3k__tr/` and `d05__b3k__su-full/` (the latter was interrupted).
    These directories were subsequently reused by P-40 Main.

<br>
| Event | Timestamp | Workspace HEAD | Relevant code reference |
|---|---|---|---|
| Main first launch | 2026-08-31 18:26:18 | `13e750b` | `9db3edb` (later commit of the corresponding launcher/output-routing implementation) |
| Main resume through notification wrapper | 2026-09-03 12:48:48 | `14f1f1f` | `9db3edb`; wrapper later committed as `9a024e7` |
| Main completion / ablation start | 2026-09-03 14:32:50 | `14f1f1f` | Same resumed launcher |

First Main launch (Qwen vLLM on port 8000 and Podman API already available):

```bash
cd /home/ak58925/agentCtx
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"

nohup bash scripts/run_agent_models_expansion_tb.sh qwen main \
  > logs/followup_tb_qwen_main.nohup.log 2>&1 &
```

September 3 resume (notification credentials supplied through the environment):

```bash
nohup env \
  PATH="$PATH" XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
  DOCKER_HOST="$DOCKER_HOST" SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
  N_CONCURRENT=4 \
  bash scripts/run_qwen_tb_with_slack.sh \
  >> logs/followup_tb_qwen_main.nohup.log 2>&1 &
```

The wrapper runs `qwen both`: Main completion was logged on **September 3
at 14:32:50**, followed by P-15 ablation. Ablation was stopped before full
completion; outputs are in `ICLR_results/terminalbench/ablation/qwen35b/`.

### (b) Devstral — P-40 Main

- **First launch:** 2026-09-03 22:56:29.
- **Workspace HEAD:** `9a024e7`.
- **Experiment launcher/output-routing reference:** `9db3edb`.
- **Budget:** 4K; outputs: `ICLR_results/terminalbench/main/devstral24b/`.
- **Log:** [followup_tb_devstral.log](../logs/followup_tb_devstral.log).

The serving command in shell history used GPUs `4,5,6,7`, port 8002,
tensor parallelism 4, and `--max-model-len 65536`. Qwen ablation and
Devstral Main therefore overlap in the recorded timeline.

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
export N_CONCURRENT=4

setsid bash scripts/run_agent_models_expansion_tb.sh devstral main \
  > logs/followup_tb_devstral_main.nohup.log 2>&1 &
```

Two further Main starts are recorded on **2026-09-05 10:26:25** and
**14:56:30**, with workspace HEAD `aee5728`:

```bash
# 10:26 resume; log: logs/followup_tb_devstral_resume_20260905_102625.log
nohup env PYTHONUNBUFFERED=1 TB_REAP_FINISHED_HARBOR=1 N_CONCURRENT=4 \
  bash scripts/run_agent_models_expansion_tb.sh devstral main \
  > logs/followup_tb_devstral_resume_20260905_102625.log 2>&1 < /dev/null &

# 14:56 resume
N_CONCURRENT=4 nohup bash scripts/run_agent_models_expansion_tb.sh devstral main \
  > logs/followup_tb_devstral_main.nohup.log 2>&1 &
```

These resumes pass existing cells and reach TRC+SS. The recovery setting
`TB_REAP_FINISHED_HARBOR=1` belongs to local changes in
`scripts/bench_adapters/terminal_bench.py`, which remain uncommitted at the
time of this entry. Thus `aee5728` is the workspace HEAD, **not an exact
commit for the recovered runtime**. No full Main completion line is recorded.

### (c) GLM — P-40 Main

- **First launch:** 2026-09-04 20:14:24.
- **Workspace HEAD:** `9b1ce3c`.
- **Experiment launcher/output-routing reference:** `9db3edb`.
- **Budget:** 3K; outputs: `ICLR_results/terminalbench/main/glm47flash/`.
- **Log:** [followup_tb_glm.log](../logs/followup_tb_glm.log).

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
export N_CONCURRENT=4

nohup setsid bash scripts/run_glm_tb_main_with_slack.sh \
  < /dev/null >> logs/followup_tb_glm_main.nohup.log 2>&1 &
```

The wrapper invokes `bash scripts/run_agent_models_expansion_tb.sh glm main`
with `GLM_P_BUDGET=3000`. It requires notification credentials in the
environment. `scripts/run_glm_tb_main_with_slack.sh` remains **untracked**;
there is no committed reference for that wrapper.

A further Main start is recorded on **2026-09-05 14:57:12**, with workspace
HEAD `aee5728`, using the same wrapper command. Existing TR/SU-full cells
are passed and SU-partial is reached. As with the Devstral recovery,
uncommitted adapter changes prevent identifying the entire runtime by
HEAD alone. No full Main completion line is recorded.

For the broader command chronology, including TB2 prebuild and FC trials,
see [EXPERIMENT_TIMELINE_20260830.md](EXPERIMENT_TIMELINE_20260830.md).

### (d) September 6 — GPU correction, archive, and restart

All times below are **CDT (UTC−05:00)**. The September 5 afternoon runs
(approximately 14:55) used the wrong GPU assignment: **Devstral 0–3 / GLM 4–7**.
Results from the following starts were withdrawn from the canonical aggregates
and archived for re-execution:

| Model | Withdrawn from | Archived results | Archive directory / notes |
|---|---|---|---|
| Devstral | 2026-09-05 14:56:30 | 680 task-condition-run results | [archives/devstral_since_20260905_145630_CDT](../archives/devstral_since_20260905_145630_CDT/README.md) |
| GLM | 2026-09-05 14:57:12 | 240 results + 11 unaggregated trials | [archives/glm_since_20260905_145712_CDT](../archives/glm_since_20260905_145712_CDT/README.md) |

Both Main launchers restarted at **2026-09-06 14:46:19**, with the corrected
assignment **Devstral 4–7 / GLM 0–3**:

| Model | Re-execution starts at | Previously completed results retained |
|---|---|---|
| Devstral | `trc-ss`, run 2 (cell entered at 14:46:24) | 880 |
| GLM | `summarization-partial`, run 1 (cell entered at 14:46:20) | 240 |

Archived tasks restart from the beginning; retained results are skipped.
The restart-time workspace HEAD was **`3fe6fc4`** (inferred from the local
Git reflog), including the timeout/worker cancellation fix **`93f7409`**.
This identifies HEAD, not a snapshot of uncommitted changes.
Archive READMEs and task lists were committed afterward as **`103a011`**
(2026-09-06 15:05:17).

Evidence: [Devstral launcher log](../logs/followup_tb_devstral_main.nohup.log),
[GLM launcher log](../logs/followup_tb_glm_main.nohup.log), and the archive notes above.

### (e) September 7 — Summary bug fix and rerun

Summary calls in mini-swe-agent 2.2.6 passed through `_parse_actions`, so a
summary response without a bash command raised a `FormatError`. Affected
results with reason `summary_marker_error` were archived and removed from
the canonical aggregates for rerun: **324 Devstral Main, 396 Qwen Main,
157 Qwen ablation, and 224 GLM Main runs**. The normal launcher skips retained
results and re-executes the archived runs as it reaches them.

Devstral Main and Qwen Main restarted at **2026-09-07 17:49:54 CDT** in
`/home/ak58925/agentCtx`. The restart-time workspace HEAD was
**`6b45448`** (`fix: fix requiring command in summary`), confirmed by the local reflog.
This includes the `query_summary` fix originating in `agentCtx-summarization`
commit `cd1716f`. HEAD identifies the committed code, not a snapshot of any
uncommitted changes.

Rerun launcher invocations recorded in the archive log (shell backgrounding,
redirection, and environment settings are not recorded there):

```bash
cd /home/ak58925/agentCtx
bash scripts/run_agent_models_expansion_tb.sh devstral main
bash scripts/run_agent_models_expansion_tb.sh qwen main
```

These were separate concurrent launches:

| Rerun | First cell reached | Launcher log |
|---|---|---|
| Devstral Main | `d05__b4k__ss` | `logs/followup_tb_devstral_main.nohup.log` |
| Qwen Main | `d05__b3k__su-full` | `logs/followup_tb_qwen_main.nohup.log` |

This entry records the Devstral Main and Qwen Main rerun launches, not
completion. GLM Main and Qwen ablation rerun launch times and commands have
not been independently verified for this entry; the archive log's 17:53 CDT
status is a historical snapshot, not a current status report.
Only `summary_marker_error` results were archived;
`summary_failure_accounting` and `summary_related_response` were not included
in this rerun selection.

For the affected cells, selection lists, archive operations, and detailed
status, see [Summary-bug rerun: tooling and archive log](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md).

<a id="main-completion"></a>

## 5. September 8–12 — Second rerun selection and Main completion

All timestamps are **CDT (UTC−5)**, from the launcher logs. Commands are from
shell history (no timestamps). Workspace HEADs are reconstructed from the local
reflog and identify committed code, not uncommitted changes. Host for every entry
from here on: Albus (`ece-a63825`, 8× A6000).

### (a) September 8 — second summary-bug rerun selection (`rerun2`)

The September 7 selection covered only `summary_marker_error`. On September 8
the rerun list was extended from agent logs (1,874 → 2,492 rows) and the
remaining reasons were archived for rerun: `summary_failure_accounting`,
`summary_related_response`, `tb_erasure_possible`, `tb_unverifiable`.

| Archive (2026-09-08 19:14 CDT) | Runs | Cells | Result rows |
|---|---:|---:|---|
| `archives/devstral24b_summary_bug_rerun2_20260908_191403_CDT` | 407 | 8 | 960 → 553 |
| `archives/glm47flash_summary_bug_rerun2_20260908_191403_CDT` | 407 | 6 | 698 → 291 |
| `archives/qwen35b_summary_bug_rerun2_20260908_191404_CDT` (main + ablation) | 577 | 16 | 1,148 → 571 |

Code: **`26d5fbc`** (`fix: expand TB summary-bug rerun candidates and archive
targets`, 2026-09-08 19:21); `archive_rerun_targets.py` unchanged since
`f64dbe6`; runtime fix for the reruns remains `6b45448`.

```bash
cd /home/ak58925/agentCtx
T=archives/summary_bug_rerun_tooling_20260907_175359_CDT
python3 $T/scripts/append_rerun_additions.py --rerun-list $T/rerun_list/rerun_runs.csv \
  --additions $T/erasure-terminalbench/rerun_runs_tb_additions.csv --label tb-erasure
for c in devstral24b glm47flash qwen35b; do
  python3 $T/scripts/archive_rerun_targets.py --rerun-csv $T/rerun_list/rerun_runs.csv \
    --cohort-model-path $c \
    --rerun-reason summary_failure_accounting summary_related_response tb_erasure_possible tb_unverifiable \
    --archive-name ${c}_summary_bug_rerun2_$(date +%Y%m%d_%H%M%S)_CDT --execute
done
```

The GLM Main resume that had been running since **2026-09-08 10:37:39**
(`logs/followup_tb_glm_main_20260908_103738.log`, HEAD `df7cb96`, launched via
`scripts/run_glm_tb_main_with_slack.sh` with `GLM_TB_LOG_FILE` set) was
terminated at about 19:05 for this archive step; it had reached `di__b3k__trc-ss`.

### (b) Qwen — Main completion

- **Relaunch:** 2026-09-08 19:27:54, HEAD **`26d5fbc`**. Qwen vLLM on GPUs 0–3,
  port 8000 (`scripts/start_vllm_qwen35.sh`, prefix caching on).
- **Completion:** **2026-09-09 07:47:07** — `TB (3.a) complete for
  Qwen3.5-35B-A3B: 1,560 planned runs`.
- Log: `logs/followup_tb_qwen_main.nohup.log`.

```bash
cd /home/ak58925/agentCtx
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
export SLACK_WEBHOOK_URL=...
nohup setsid env N_CONCURRENT=4 bash scripts/run_qwen_tb_main_with_slack.sh \
  </dev/null >>logs/followup_tb_qwen_main.nohup.log 2>&1 &
echo $! > logs/followup_tb_qwen_main.pid
```

Wrapper `scripts/run_qwen_tb_main_with_slack.sh` is committed as `a2fc04b`.

### (c) September 9 — native-context FC re-collection for budget calibration

Devstral and GLM FC@∞ run_1 were re-collected with vLLM at the model's native
context length (the 8/30–31 collection had `--max-model-len 65536`). Qwen was
also started at native (262K) for a re-collection. Code: **`469708b`**
(`feat(tb): isolated calibration runs, prefix-cache metrics, native-context
vLLM launchers`). Outputs go to `calibration_results/terminalbench/<model>_native_p80/`,
not to `ICLR_results/`. Distributions and adopted budgets are in
[budget_calibration_tb.md](budget_calibration_tb.md); procedures in
`scripts/GLM_TB_NATIVE_CALIBRATION.md` and `scripts/DEVSTRAL_TB_NATIVE_CALIBRATION.md`.

```bash
GLM_MAX_MODEL_LEN=native bash scripts/start_vllm_glm47flash.sh
DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 DEVSTRAL_MAX_MODEL_LEN=native DEVSTRAL_MAX_NUM_SEQS=4 \
  bash scripts/start_vllm_devstral.sh
nohup venv-harbor/bin/python -u scripts/run_budget_calibration_tb.py \
  --model-key glm47flash --agent-config configs/config-glm47flash-vllm.yaml \
  --calibration-dir calibration_results/terminalbench/glm47flash_native_p80 \
  --job-name tb1-glm47flash-native-p80-fc-run1 --run-num 1 --n-tasks 80 --n-concurrent 4 \
  > calibration_results/terminalbench/glm47flash_native_p80/launcher.log 2>&1 < /dev/null &
# devstral24b / qwen35b: same form with --model-key, --agent-config and --calibration-dir swapped
```

### (d) Devstral — Main completion

- **Relaunch:** 2026-09-10 21:05:28, HEAD **`26d5fbc`**. Devstral vLLM on
  GPUs 4–7, port 8002, `--max-model-len 65536`
  (`DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 DEVSTRAL_MAX_MODEL_LEN=65536 bash scripts/start_vllm_devstral.sh`).
- **Completion:** **2026-09-11 10:46:48** — `TB (3.a) complete for
  Devstral-Small-2-24B: 1,560 planned runs`.
- Log: `logs/devstral_main_20260910_210528.log`.

```bash
export DEVSTRAL_TB_LOG_FILE="$PWD/logs/devstral_main_$(date +%Y%m%d_%H%M%S).log"
nohup setsid env N_CONCURRENT=4 PYTHONUNBUFFERED=1 bash scripts/run_devstral_tb_main_with_slack.sh \
  > "$DEVSTRAL_TB_LOG_FILE" 2>&1 < /dev/null &
echo $! > logs/followup_tb_devstral_main.pid
```

### (e) GLM — Main completion

GLM vLLM on GPUs 0–3, port 8003, `--max-model-len 65536`
(`HF_HUB_OFFLINE=1 GLM_CUDA_VISIBLE_DEVICES=0,1,2,3 GLM_TENSOR_PARALLEL_SIZE=4 GLM_MAX_MODEL_LEN=65536 bash scripts/start_vllm_glm47flash.sh`).
All launches below at HEAD **`26d5fbc`**.

| Launch | Command | Log | Outcome |
|---|---|---|---|
| 2026-09-11 00:52:26 | `run_glm_tb_main_with_slack.sh` with `GLM_TB_LOG_FILE` | `logs/followup_tb_glm_main_20260911_005226.log` | reached `di__b3k__trc-su`; stopped ~11:21 |
| 2026-09-11 17:59:18 | `logs/resume_glm_main_20260911.sh` (waits for :8003, then `exec bash scripts/run_agent_models_expansion_tb.sh glm main`) | `logs/followup_tb_glm_main_20260911_1758.log` | superseded |
| 2026-09-11 18:20:24 | `GLM_P_BUDGET=3000 N_CONCURRENT=4 nohup flock -n logs/glm_tb_main.lock bash scripts/run_agent_models_expansion_tb.sh glm main` | `logs/glm_main_manual_resume.log` | killed (`kill -TERM %1`) to restore Slack notification |
| 2026-09-11 18:26:24 | `GLM_TB_LOG_FILE="$PWD/logs/glm_main_slack_resume.log" N_CONCURRENT=4 nohup bash scripts/run_glm_tb_main_with_slack.sh > logs/glm_main_slack_resume.log 2>&1 &` | `logs/glm_main_slack_resume.log` | **complete 2026-09-12 12:34:28** — `TB (3.a) complete for GLM-4.7-Flash: 1,560 planned runs` |

`scripts/run_glm_tb_main_with_slack.sh` is committed as `3fe6fc4`.

### (f) September 11 — verifier-timeout re-verification (evaluation only, no new runs)

17 trials whose verifier had timed out were re-verified by recovering the reward
file (`method: reward_file`); their verdicts were rewritten in place in
`experiment_results.json`. Code: **`195a299`** (trustworthy verdicts) and
**`02e4712`** (`scripts/replay_reverify_tb.py`), committed 2026-09-11 20:53.
Manifest: `logs/replay_reverify/recover_20260911-203635/manifest.json`
(`items: 17`; backups under `backups/`). Check afterwards:

```bash
python3 scripts/audit_tb_verdicts.py   # false_without_verdict 393 -> 376
python3 analysis/aggregate_terminalbench_results.py
grep -c verifier_reward_file analysis/outcomes/terminalbench_outcomes.csv   # 17
```

Final Main aggregate size per model: **13 cells × 40 tasks × 3 runs = 1,560 rows**
(`main/qwen35b/` additionally keeps the pre-P-40 `d05__b27k__tr/` cell).

<a id="ablation"></a>

## 6. P-15 ablation (3.b)

Grid per model: **52 cells = 2,340 runs** on `task_lists/tbench_abl15.json`
(15 tasks × 3 runs): depth-tunable singles at 0.5 × budgets A/B (450), at
0.3 and 0.7 × A/P/B (675 each), depth-invariant primitives at A/B (540).
Budgets A/P/B: Qwen 2K/3K/4K, Devstral 3K/4K/7K, GLM 2K/3K/5K (launcher
defaults in `scripts/run_agent_models_expansion_tb.sh`). Outputs:
`ICLR_results/terminalbench/ablation/<model-key>/<cell>/`.

### (a) Devstral — complete

- **Launch:** 2026-09-12 00:59:15, HEAD **`ec1e42a`** (2026-09-11 20:53).
  Devstral vLLM on GPUs 4–7, port 8002.
- **Completion:** **2026-09-14 07:05:42** — `TB (3.b) complete for
  Devstral-Small-2-24B: 2,340 planned runs`. On disk: 52 cells, 2,340 rows.
- Log: `logs/devstral_ablation_20260912_005915.log`.

The Slack wrapper was a `sed` copy of the Main wrapper written to `logs/`
(**untracked**; equivalent to `run_devstral_tb_main_with_slack.sh` with
`ablation` in place of `main`):

```bash
sed 's/main/ablation/g; s/Main/Ablation/g' scripts/run_devstral_tb_main_with_slack.sh \
  > logs/run_devstral_tb_ablation_with_slack.sh
export N_CONCURRENT=4 DEVSTRAL_A_BUDGET=3000 DEVSTRAL_P_BUDGET=4000 DEVSTRAL_B_BUDGET=7000
export DEVSTRAL_TB_LOG_FILE="$PWD/logs/devstral_ablation_$(date +%Y%m%d_%H%M%S).log"
nohup setsid bash logs/run_devstral_tb_ablation_with_slack.sh </dev/null >"$DEVSTRAL_TB_LOG_FILE" 2>&1 &
echo $! > logs/devstral_tb_ablation_launcher.pid
```

### (b) Qwen — complete

- **Launch:** 2026-09-12 13:38:47 (after GLM Main finished and its server was
  stopped), HEAD **`ec1e42a`**. Qwen vLLM on GPUs 0–3, port 8000
  (`QWEN_CUDA_VISIBLE_DEVICES=0,1,2,3 QWEN_TENSOR_PARALLEL_SIZE=4 QWEN_VLLM_PORT=8000 bash scripts/start_vllm_qwen35.sh`).
  The September 3–4 partial ablation cells (`d05__b2k__*`, `d05__b4k__*`) and
  the September 8 `rerun2` archive were skipped/re-executed by the same launcher.
- **Completion:** **2026-09-15 00:59:11** — `TB (3.b) complete for
  Qwen3.5-35B-A3B: 2,340 planned runs`. On disk: 52 cells, 2,340 rows.
- Log: `logs/qwen_ablation_20260912_133847.log`.

```bash
sed -e 's/main/ablation/g' -e 's/Main/Ablation/g' -e 's/(3.a)/(3.b)/g' \
  scripts/run_qwen_tb_main_with_slack.sh > logs/run_qwen_tb_ablation_with_slack.sh   # untracked
export QWEN_A_BUDGET=2000 QWEN_P_BUDGET=3000 QWEN_B_BUDGET=4000 N_CONCURRENT=4 PYTHONUNBUFFERED=1
export QWEN_TB_LOG_FILE="$PWD/logs/qwen_ablation_$(date +%Y%m%d_%H%M%S).log"
nohup setsid bash logs/run_qwen_tb_ablation_with_slack.sh </dev/null >>"$QWEN_TB_LOG_FILE" 2>&1 &
echo $! > logs/qwen_tb_ablation_launcher.pid
```

### (c) GLM — split launch (September 16), resumed September 26, **in progress**

**September 16 — two servers, two halves.** Two GLM vLLM servers were started
by hand (not through `start_vllm_glm47flash.sh`), both TP=4, 65,536 context,
64 seqs, prefix caching on:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 nohup ./venv-glm-cu129-clean/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model zai-org/GLM-4.7-Flash --port 8003 --dtype auto --tensor-parallel-size 4 \
  --max-model-len 65536 --max-num-seqs 64 --enable-prefix-caching > logs/vllm_glm_gpu0-3.log 2>&1 &
CUDA_VISIBLE_DEVICES=4,5,6,7 nohup ./venv-glm-cu129-clean/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model zai-org/GLM-4.7-Flash --port 8004 ... > logs/vllm_glm_gpu4-7.log 2>&1 &
export SLACK_WEBHOOK_URL=...
nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 > logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &
nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu4-7 > logs/followup_tb_glm_ablation_gpu4-7.nohup.log 2>&1 &
```

- Both halves launched **2026-09-16 15:13:43**: `gpu0-3` = parts `d03 d07`
  (port 8003), `gpu4-7` = parts `di d05` (port 8004,
  `configs/config-glm47flash-vllm-8004.yaml`).
- Workspace HEAD at launch was `ec1e42a`; the split support
  (`ABLATION_PARTS`, `TB_LOG_SUFFIX`, `run_glm_tb_ablation_with_slack.sh`, the
  8004 config) was **uncommitted at launch and committed the same evening as
  `376f1df`** (2026-09-16 20:23). `376f1df` is the reconstruction reference.
- Both halves were terminated at about **17:47** the same day (GPUs handed to
  the summarizer-ablation servers, §7). Completed by then: `d03__b2k__tr`,
  `di__b2k__trc`, `di__b2k__trc-su`; partial: `d03__b2k__su-full`;
  `di__b2k__trc-ss` was entered but holds no completed trajectory.

**September 26 — single-server resume.** GLM vLLM restarted on GPUs 0–3, port
8003 (`bash scripts/start_vllm_glm47flash.sh`; vLLM 0.28.0, 65,536 context,
prefix caching on; log `logs/vllm_glm47flash.log`, the September 12 log was
moved to `logs/vllm_glm47flash_20260912.log`). HEAD **`b45f8dc`**.

```bash
nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 >> logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &
# ^ 08:48:54, default parts "d03 d07"; terminated within minutes and replaced by:
ABLATION_PARTS="d03 d07 di d05" nohup bash scripts/run_glm_tb_ablation_with_slack.sh gpu0-3 \
  >> logs/followup_tb_glm_ablation_gpu0-3.nohup.log 2>&1 &
```

- **Running since 2026-09-26 08:53:24** with all four parts on the one server
  (the `gpu0-3` label now only selects the port-8003 config and lock).
  Completed runs from September 16 are skipped. Parts run in the order
  `d03 d07 di d05`, so the September 16 `di` cells are not revisited until the
  depth-tail parts finish.
- Status at the time of this entry (2026-09-26 ~18:00): 12 cells on disk,
  480 rows; the launcher is in `d03__b3k__ss`. Log:
  `logs/followup_tb_glm_ablation_gpu0-3.log`. Remaining: 1,860 runs.

<a id="summarizer-ablation"></a>

## 7. Summarizer ablation on Terminal-Bench (FOLLOWUP §4.b / §4.d)

Agent Qwen3.5-35B-A3B (GPUs 0–3, port 8000, `scripts/start_vllm_qwen35.sh`,
prefix caching on, i.e. the production serving); summarizer served separately
on port 8001 (GPUs 4–5, TP=2). Cells: `d05__b3k__su-full` and `di__b3k__trc-su`
at 3K on `tbench_abl15.json` × 3 runs = **90 runs per summarizer**. Baseline =
the same cells under `main/qwen35b/` (self-summarization) restricted to ABL-15.
Outputs: `ICLR_results/terminalbench/model_ablation/<ICLR_MODEL>/<cell>/`.
Runner: `scripts/run_qwen_tb_summarizer_ablation.sh` (committed **`ae040f1`**,
2026-09-17), Slack wrapper `..._with_slack.sh` (**`e4dc951`**, 2026-09-21).

Note: the plan table says ABL-20 × 5 runs; the executed grid is ABL-15 × 3 runs
(`TB_TASKS_FILE=task_lists/tbench_abl15.json RUNS_PER_TASK=3`), matching the
Main baseline's run count.

| Summarizer | Smoke (1 task × 1 run, throwaway dir) | Full launch | Complete | HEAD at launch | Log |
|---|---|---|---|---|---|
| Qwen3.5-9B (`configs/config-summary-qwen35-9b.yaml`, `scripts/start_vllm_qwen35_9b.sh`) | 2026-09-16 20:44–21:00, HEAD `de7b1a1` (runner uncommitted until `ae040f1`) | **2026-09-23 13:11:58** | **2026-09-23 15:55:52** | `5ad3d7b` | `logs/followup_tb_qwen_sumabl_qwen35b-sum-qwen35-9b.log` |
| Gemma-4-12B (`configs/config-summary-gemma4-12b.yaml`, `scripts/start_vllm_gemma4_12b.sh`) | 2026-09-23 16:25–16:32 | **2026-09-23 16:32:16** | **2026-09-23 18:53:27** | `5ad3d7b`; Gemma config + start script **uncommitted until `4e25e6e`** (2026-09-26) | `logs/followup_tb_qwen_sumabl_qwen35b-sum-gemma4-12b.log` |

Both result dirs hold 2 cells × 45 = **90 rows**. Both `-smoke` dirs are still
on disk under `model_ablation/` (ignored by `build_coverage.py` /
`aggregate_terminalbench_results.py`; the `rm -rf` in shell history was run
from a different working directory).

```bash
cd /home/ak58925/agentCtx
bash scripts/start_vllm_qwen35.sh          # agent, GPUs 0-3, :8000
bash scripts/start_vllm_qwen35_9b.sh       # summarizer, GPUs 4-5, :8001
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"; export SLACK_WEBHOOK_URL=...
# smoke
N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 \
  ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/run_qwen_tb_summarizer_ablation.sh
# full
TB_TASKS_FILE=task_lists/tbench_abl15.json ICLR_MODEL=qwen35b-sum-qwen35-9b RUNS_PER_TASK=3 N_CONCURRENT=4 \
  nohup bash scripts/run_qwen_tb_summarizer_ablation_with_slack.sh > logs/followup_tb_qwen_sumabl_qwen9b.nohup.log 2>&1 &

# Gemma-4-12B: swap the summarizer server, then the same two commands with SUMMARY_CONFIG
bash scripts/stop_vllm.sh logs/vllm_qwen35_9b.pid
bash scripts/start_vllm_gemma4_12b.sh      # GPUs 4-5, :8001, venv-glm-cu129-clean (vLLM 0.28.0)
N_TASKS=1 RUNS_PER_TASK=1 N_CONCURRENT=1 CELLS=d05__b3k__su-full:summarization:0.5 \
  SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b-smoke \
  bash scripts/run_qwen_tb_summarizer_ablation.sh
TB_TASKS_FILE=task_lists/tbench_abl15.json SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml \
  ICLR_MODEL=qwen35b-sum-gemma4-12b RUNS_PER_TASK=3 N_CONCURRENT=4 \
  nohup bash scripts/run_qwen_tb_summarizer_ablation_with_slack.sh > logs/followup_tb_qwen_sumabl_gemma4-12b.nohup.log 2>&1 &
```

<a id="prefix-cache-ablation"></a>

## 8. Prefix-cache ablation on Terminal-Bench (dashboard 5.b) — complete

Production Qwen TB runs were served with vLLM prefix caching **on**. This grid
repeats the primary-budget cells with caching **off**, all else unchanged:
13 cells (5 depth-tunable @0.5 + 6 depth-invariant @3K, plus FC / OTRC @∞) ×
ABL-15 × 3 runs = **585 runs**, agent = summarizer. Outputs:
`ICLR_results/terminalbench/prefix_cache_ablation/qwen35b-noprefixcache/<cell>/`.
Baseline = the same cells under `main/qwen35b/` restricted to ABL-15.

- **Launch:** **2026-09-23 20:38:25**, both halves at once; HEAD **`5ad3d7b`**
  (`feat: scripts for prefix cache ablation`, 2026-09-21, which contains the
  runner, wrapper, `start_vllm_qwen35_no_prefix_cache.sh` and `stop_vllm.sh`).
  The split-grid support (`LAUNCH_GROUP`, `configs/config-qwen-vllm-8002.yaml`,
  `scripts/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh`) was **uncommitted at
  launch and committed as `4e25e6e`** (2026-09-26); the log headers
  (`[gpu0-3]` / `[gpu4-7]`) confirm that version was the one executed.
- **Servers:** two caching-off Qwen3.5-35B-A3B servers, production arguments
  otherwise (TP=4, 102,400 context, 64 seqs, vLLM 0.17.1): GPUs 0–3 / port 8000
  (`logs/vllm_qwen35_noprefixcache.log`) and GPUs 4–7 / port 8002
  (`logs/vllm_qwen35_noprefixcache_gpu4-7.log`); both logged
  `enable_prefix_caching=False`.
- **Completion:** `gpu4-7` (6 depth-invariant cells, 270 runs) **2026-09-24
  03:15:39**; `gpu0-3` (5 depth-tunable + FC + OTRC, 315 runs) **2026-09-24
  05:12:51**. Prefix-cache counters: `0 hit / 0 queried tokens` over every cell
  and the whole grid. On disk: 13 cells, **585 rows**.
- Logs: `logs/followup_tb_qwen_qwen35b-noprefixcache_gpu0-3.log`,
  `logs/followup_tb_qwen_qwen35b-noprefixcache_gpu4-7.log`.

```bash
cd /home/ak58925/agentCtx
bash scripts/stop_vllm.sh logs/vllm_gemma4_12b.pid; bash scripts/stop_vllm.sh logs/vllm_qwen35.pid
bash scripts/start_vllm_qwen35_no_prefix_cache.sh          # GPUs 0-3, :8000
bash scripts/start_vllm_qwen35_no_prefix_cache_gpu4-7.sh   # GPUs 4-7, :8002
grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/vllm_qwen35_noprefixcache.log | tail -1        # False
grep -a -o 'enable_prefix_caching=[A-Za-z]*' logs/vllm_qwen35_noprefixcache_gpu4-7.log | tail -1  # False
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"; export SLACK_WEBHOOK_URL=...
nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu0-3 \
  > logs/followup_tb_qwen_noprefixcache_gpu0-3.nohup.log 2>&1 &
nohup bash scripts/run_qwen_tb_prefix_cache_ablation_with_slack.sh gpu4-7 \
  > logs/followup_tb_qwen_noprefixcache_gpu4-7.nohup.log 2>&1 &
```

Outcome tables were regenerated afterwards and committed as **`b45f8dc`**
(`sep 24 tb outcome csv`, 2026-09-24 11:13).
