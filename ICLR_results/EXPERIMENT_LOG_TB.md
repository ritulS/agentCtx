# ICLR 2027 Experiment Log — Terminal-Bench

Experiment Plan → [FOLLOWUP_EXPERIMENTS.md](../exp_plans/FOLLOWUP_EXPERIMENTS.md)

## Follow-up 4 — Terminal-Bench 1.0 evaluation

### Qwen budget-calibration infrastructure and image prebuild

#### Summary

| Item | Value |
|---|---|
| Status | **Complete: 80/80 images** |
| Dataset | Terminal-Bench Core 1.0 / `terminal-bench-core@0.1.1` |
| Dataset source commit | `91e1045` |
| Prebuild implementation | `77b6da5` |
| Runtime | Rootless Podman |
| Build log | `logs/tb1_harbor_prebuild.log` |

The 80 tasks were split by the user-namespace setup required to prebuild them:

| Subset | Tasks | Rootless configuration | Completed | Workspace HEAD at launch |
|---|---:|---|---|---|
| `P-80-rootless` | 42 | Single UID/GID; no subuid/subgid | 2026-08-29 16:10 CDT | `0d42a9b` |
| `P-80-subuid-required` | 38 | Subordinate UID/GID mapping and `uidmap` | 2026-08-30 19:57 CDT | `8e3d3f3` |

Both subsets use the same Terminal-Bench source commit (`91e1045`) and the
same prebuild implementation (`77b6da5`). The difference is only the
rootless Podman user-namespace configuration.

> The 42-task prebuild ran while its scripts were still working-tree changes.
> That exact implementation was committed afterward as `77b6da5`.
>
> During the detached 38-task build, unrelated dashboard commit `751f704`
> was created. It did not change the dataset or prebuild scripts.

#### Why prebuild was needed

- Docker Compose v5/buildx could not run its privileged BuildKit container
  under rootless Podman.
- Native sequential Podman builds avoided that limitation.
- `uv` was baked into each main task image so verifier setup is not included
  in experimental runtime.
- Multi-service task images were also prebuilt and referenced from the
  migrated Compose files.
- `ROOTLESS_CHOWN_WORKAROUND=1` was **not** used; normal ownership semantics
  were preserved.

Image build time is excluded from `agent_latency_s`, `llm_latency_s`, and
`e2e_latency_s`. All models and repetitions reuse these images.

#### Prebuild results

| Phase | Result | Task list |
|---|---|---|
| Single-UID rootless | 42 succeeded, 38 failed on ownership operations | `task_lists/tbench_p80_rootless.json` |
| Rootless with subuid/subgid | Remaining 38 succeeded | `task_lists/tbench_p80_subuid_required.json` |
| Final | **80 succeeded, 0 failed** | `logs/tb1_harbor_prebuild.log` |

The complete host setup, subordinate-ID mapping, validation, and rollback
procedure for the 38-task phase is documented in
[tb_prebuild.md](./tb_prebuild.md).

#### Reproduce or validate

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

### FC calibration on the 42/38 split

Each vLLM server uses all four GPUs. **Run one model at a time:** start one
server, run that model's experiments, stop it, and then switch models.

#### Select one model

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

#### Common workflow

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

#### Subuid launcher provenance

Commit `55d9ea5` (`feat: modified for subuid tasks`) records the infrastructure
used for the 38-task runs:

- `qwen-subuid`, `devstral-subuid`, and `glm-subuid` launcher selections
- `p80_subuid_required` result scope
- `task_lists/tbench_p80_subuid_required.json` (38 tasks)
- corrected dashboard postprocessing paths

| Model | 38-task run started | Relation to `55d9ea5` |
|---|---|---|
| Qwen | 2026-08-30 20:22 CDT | Working-tree version; completed before commit |
| Devstral | 2026-08-30 23:05 CDT | Working-tree version; completed before commit |
| GLM | 2026-08-31 00:25 CDT | Working-tree version; commit created during the run |

The working-tree implementation used by these launches was committed unchanged
as `55d9ea5` at 2026-08-31 00:43 CDT. This is the canonical code provenance
for the 38-task launch path; it does not change the dataset or prebuilt images.

### FC@∞ repetitions on the 42-task subset

The initial calibration supplied `run_1`. The remaining four repetitions
(`run_2`–`run_5`) were then run for all three models on `P-80-rootless`.

#### Code provenance

| Item | Commit |
|---|---|
| Repetition launcher | `64278ff` |
| Final Terminal-Bench runner used by later launches | `6042415` |

| Model | First repetition started | Workspace HEAD | Result |
|---|---|---|---|
| Qwen3.5-35B-A3B | 2026-08-29 18:03 CDT | `a12955e` | runs 1–5: 42/42 each |
| Devstral-Small-2-24B | 2026-08-30 04:33 CDT | `5b2c07e` | runs 1–5: 42/42 each |
| GLM-4.7-Flash | 2026-08-30 12:50 CDT | `5b2c07e` | runs 1–5: 42/42 each |

Qwen `run_2` started while the launcher and runner changes were still
uncommitted; they were recorded during that run as `64278ff` and `6042415`.
Qwen `run_3`–`run_5`, Devstral, and GLM used the committed versions. These
commits changed orchestration and result collection, not the task images;
all runs reused the images described above.

#### Commands used

For each model, after starting its vLLM server with the common workflow above:

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
export N_CONCURRENT=4

bash scripts/run_terminalbench_rootless_fc_expansion.sh "$MODEL"
```

The server was stopped before selecting and running the next model.

The GLM launcher was interrupted after `run_2`; the remaining runs were
resumed with:

```bash
START_RUN=3 END_RUN=5 \
  bash scripts/run_terminalbench_rootless_fc_expansion.sh glm
```

Final aggregate size for each model: **42 tasks × 5 runs = 210 rows**.
