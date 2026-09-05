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
  START_SCRIPT=scripts/start_vllm_qwen35.sh
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
