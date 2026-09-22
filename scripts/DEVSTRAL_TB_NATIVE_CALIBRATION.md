# Devstral native-context P-80 calibration on GPUs 4-7

Collect all 80 Terminal-Bench 1.0 tasks with full context, run_1, one Harbor
attempt per task, zero retries. Results, raw jobs and prefix-cache metrics stay
under `calibration_results/terminalbench/devstral24b_native_p80`, outside the
ICLR results tree. Coverage/dashboard postprocessing is disabled in this mode.
Do not use `run_budget_calibration_tb.sh devstral`: it writes to canonical main.

## Start Devstral

The checked host has RTX A6000 48GB GPUs, and GPUs 4-7 were idle. Port 8002
was free. The startup script rejects an existing Devstral server or occupied
port. It uses TP=4 and explicitly enables prefix caching.

```bash
cd /home/ak58925/agentCtx
DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 \
DEVSTRAL_MAX_MODEL_LEN=native \
DEVSTRAL_MAX_NUM_SEQS=4 \
bash scripts/start_vllm_devstral.sh

tail -f logs/vllm_devstral.log
```

The server is detached with nohup/setsid. Ctrl-C on `tail` only stops tail.
`native` omits `--max-model-len`; an empty value retains the normal 65536 default.
No KV-cache quantization change is made. Model weights already use the model's
FP8 checkpoint, while the previous server's KV cache was BF16 (`auto`).

There is a model metadata distinction: the cached Hugging Face `config.json`
has `text_config.max_position_embeddings=393216` (YaRN: 8192 x 48). The separate
Mistral `params.json` specifies 262144. This command keeps the existing HF auto
loading path, so 393216 is the expected derived value. Record the actual value
from vLLM; do not describe this run as a 262144-context run.

References: [HF config.json](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512/blob/main/config.json),
[Mistral params.json](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512/blob/main/params.json).

At 393216 tokens, BF16 KV storage is approximately 15 GiB per GPU with TP=4:
`393216 * 40 layers * 2 (K,V) * (8 KV heads / 4 GPUs) * 128 * 2 bytes`.
The previous 65K launch reported 35.06 GiB of KV memory per GPU. Two maximum
length sequences require about 30 GiB per GPU, so start with two concurrent
tasks and verify capacity in the new startup log. Four maximum length sequences
would need about 60 GiB per GPU and can cause preemption. These are estimates;
the native-length server has not been started as part of preparing this guide.

## Verify readiness, context length and prefix caching

Run after the log says `Application startup complete`:

```bash
curl -fsS http://localhost:8002/v1/models | venv-harbor/bin/python -c '
import json, sys
m = next(m for m in json.load(sys.stdin)["data"]
         if m["id"] == "mistralai/Devstral-Small-2-24B-Instruct-2512")
print(m["id"], "max_model_len =", m.get("max_model_len"))
assert m.get("max_model_len") == 393216, m
'
rg -o 'max_seq_len=[0-9]+|enable_prefix_caching=(True|False)|kv_cache_dtype=[^, ]+' \
  logs/vllm_devstral.log
curl -fsS http://localhost:8002/metrics \
  | rg '^vllm:prefix_cache_(hits|queries)_total'
```

If startup fails, inspect the error before launching tasks. Do not silently
reduce the context length or change KV precision for this collection.

## Dry-run and launch in background

Keep the GLM and Devstral directories and job names distinct. Do not launch a
second copy if this same collection is already running.

```bash
cd /home/ak58925/agentCtx
export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"
DEV_CAL_DIR="$PWD/calibration_results/terminalbench/devstral24b_native_p80"

venv-harbor/bin/python scripts/run_budget_calibration_tb.py \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --calibration-dir "$DEV_CAL_DIR" \
  --job-name tb1-devstral24b-native-p80-fc-run1 \
  --run-num 1 --n-tasks 80 --n-concurrent 2 \
  --dry-run
```

The dry run writes nothing and does not contact Docker or the model server.
For the actual collection, first ensure `docker info` succeeds and the model
checks above pass. All 80 task images must be available or buildable.

```bash
mkdir -p "$DEV_CAL_DIR"
cp logs/vllm_devstral.log "$DEV_CAL_DIR/vllm_startup.log"
cp configs/config-devstral-vllm.yaml "$DEV_CAL_DIR/agent_config.yaml"
curl -fsS http://localhost:8002/v1/models > "$DEV_CAL_DIR/vllm_models.json"

nohup venv-harbor/bin/python -u scripts/run_budget_calibration_tb.py \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --calibration-dir "$DEV_CAL_DIR" \
  --job-name tb1-devstral24b-native-p80-fc-run1 \
  --run-num 1 --n-tasks 80 --n-concurrent 2 \
  > "$DEV_CAL_DIR/launcher.log" 2>&1 < /dev/null &
echo $! > "$DEV_CAL_DIR/launcher.pid"

tail -f "$DEV_CAL_DIR/launcher.log"
```

Output paths relative to `DEV_CAL_DIR`:

- `results/experiment_results.json`: normalized per-task data, including prompt peaks.
- `results/<task>/full-context/run_1/`: trajectory and token logs.
- `results/CALIBRATION_MANIFEST.json`: completion/coverage.
- `harbor_jobs/tb1-devstral24b-native-p80-fc-run1/`: raw Harbor state.
- `metrics/tb1-devstral24b-native-p80-fc-run1/prefix_cache.jsonl`: automatic
  start/10-second/end snapshots from port 8002. The initial scrape must work
  before Harbor starts. Counter deltas are server-wide and include other clients.

## Agent limits and interpretation

`max_tokens: 4096` still caps each generated response; it does not cap input
history. The merged TB agent has a 100-step limit and the task's existing timeout.
Shell observations retain the existing output clipping. Compression budget is
999999999, so history compression does not fire before the model context limit.

Use `max(step_prompt_tokens)` per task for context growth, but inspect errors
and missing logs. In the current agent implementation, a malformed response is
kept as `extra.model_response` in the saved trajectory and is not sent as history
on the next call; those calls also bypass the token-log accumulation. These
limitations are shared with the GLM collection; no agent behavior was changed
for this Devstral setup.
