# GLM native-context P-80 calibration

This collects Terminal-Bench 1.0 P-80 (80 tasks), full context, run_1,
one attempt per task and zero Harbor retries. It does not select the smaller
P-80-rootless subset.

Do not use `run_budget_calibration_tb.sh glm` for this collection: that wrapper
writes to the canonical main results. Use the Python command below with
`--calibration-dir`. This mode stores both normalized results and Harbor jobs
outside `ICLR_experiments`, rejects destinations inside that tree, and skips
coverage/dashboard postprocessing automatically.

## Start the server

Run from `/home/ak58925/agentCtx`. First finish any experiments using the existing
GLM server and stop that server before starting its replacement. The launcher
refuses to start when the port or another GLM server is already in use.

```bash
cd /home/ak58925/agentCtx
GLM_MAX_MODEL_LEN=native bash scripts/serving/start_vllm_glm47flash.sh
tail -f logs/servers/vllm_glm47flash.latest.log
```

`native` omits `--max-model-len` entirely. The ordinary launcher default remains
65536. An empty environment value still selects that default; use `native`.
Do not substitute `auto`/`-1`: the installed vLLM can fit those to GPU memory.
The cached GLM-4.7-Flash model config has `max_position_embeddings=202752`.
Check the actual running server before collection:

```bash
curl -fsS http://localhost:8003/v1/models | venv-harbor/bin/python -c '
import json, sys
models = json.load(sys.stdin)["data"]
model = next(m for m in models if m["id"] == "zai-org/GLM-4.7-Flash")
print(model["id"], "max_model_len =", model.get("max_model_len"))
assert model.get("max_model_len") == 202752, model
'
```

If native length cannot fit, resolve the GPU/KV-cache capacity problem before
collecting data. A successful launch with a reduced context would be a different
calibration condition.

## Validate, then collect

The local `data/tb1-harbor-0.1.1` dataset must have 80 tasks. A working Docker or
Podman API and images/build support for all 80 tasks are required (including the
38 tasks in `task_lists/tbench_p80_subuid_required.json`).

```bash
cd /home/ak58925/agentCtx
export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/podman/podman.sock}"
TB_CAL_DIR="$PWD/calibration_results/terminalbench/glm47flash_native_p80"

venv-harbor/bin/python scripts/calibration/run_budget_calibration_tb.py \
  --model-key glm47flash \
  --agent-config configs/config-glm47flash-vllm.yaml \
  --calibration-dir "$TB_CAL_DIR" \
  --job-name tb1-glm47flash-native-p80-fc-run1 \
  --run-num 1 --n-tasks 80 --n-concurrent 4 \
  --dry-run
```

The dry run prints destinations and the Harbor command without creating files,
contacting Docker, or starting inference. For the actual run:

```bash
docker info >/dev/null && mkdir -p "$TB_CAL_DIR" && \
nohup venv-harbor/bin/python -u scripts/calibration/run_budget_calibration_tb.py \
  --model-key glm47flash \
  --agent-config configs/config-glm47flash-vllm.yaml \
  --calibration-dir "$TB_CAL_DIR" \
  --job-name tb1-glm47flash-native-p80-fc-run1 \
  --run-num 1 --n-tasks 80 --n-concurrent 4 \
  > "$TB_CAL_DIR/launcher.log" 2>&1 &
```

Keep a distinct calibration directory and job name for a new collection. Never
point a native-context collection at an existing 65K-context job.

Outputs:

- `results/experiment_results.json`: task records with `step_prompt_tokens`.
- `results/<task>/full-context/run_1/`: trajectory, token log, exit status, Harbor result.
- `results/CALIBRATION_MANIFEST.json`: completeness and task coverage.
- `harbor_jobs/tb1-glm47flash-native-p80-fc-run1/`: raw Harbor job.
- `launcher.log`: launcher output.
- `metrics/tb1-glm47flash-native-p80-fc-run1/prefix_cache.jsonl`: timestamped
  prefix-cache counters at start, every 10 seconds, and at end/interruption.

Isolated calibration automatically scrapes the agent server's `/metrics`.
No extra option or server restart is needed. `--metrics-url` overrides that URL
for a reverse proxy or separate metrics endpoint. The initial scrape must expose
prefix-cache hits and queries; otherwise Harbor is not started. Later failed
scrapes are recorded as errors, not as zero cache usage.

Each JSONL record keeps original Prometheus lines (including HELP, TYPE and
model/engine labels), a UTC timestamp, a recording session ID and phase.
The relevant counters are typically `vllm:prefix_cache_hits_total` and
`vllm:prefix_cache_queries_total`. Within a session with no server restart,
compute the hit rate from `delta(hits) / delta(queries)` per matching label set,
or sum the deltas across engines before division. Zero queries means the ratio
is undefined. Do not average the cumulative ratios. Check error records and
counter resets; these are server-wide counters and include other clients.

For a calibration that is already running, use the standalone recorder in a
second terminal, then stop it with Ctrl-C when collection finishes:

```bash
venv-harbor/bin/python scripts/calibration/log_vllm_prefix_cache.py \
  --url http://localhost:8003/metrics \
  --output "$TB_CAL_DIR/metrics/manual-prefix-cache.jsonl"
```

Add `--once` for a single snapshot; use port 8002 and a separate output path for
Devstral. Starting recording partway through a run does not recover its missing
start baseline. This implements the `/metrics` option requested for cache usage
logging; it does not add per-request `cached_tokens` fields to the token log.

Inspect the most recent snapshot:

```bash
tail -n 1 "$TB_CAL_DIR/metrics/tb1-glm47flash-native-p80-fc-run1/prefix_cache.jsonl" \
  | python3 -m json.tool
```

## Inspect the context-growth data

Full context means the compression budget is effectively infinite (999999999).
The existing TB agent still has 100 steps, at most 4096 generated tokens per
response, the observation-output clipping in `config-tbench.yaml`, and each
task's agent timeout (multiplier 1.0). The model context limit covers input plus
output. These limits can censor observed trajectory peaks; full context does
not imply unlimited execution or unbounded shell output.

After the launcher completes, inspect task coverage, exits, missing token logs,
and compression counts before using peaks to select budgets:

```bash
venv-harbor/bin/python - "$TB_CAL_DIR/results/experiment_results.json" <<'PY'
import collections
import json
import sys

rows = json.load(open(sys.argv[1]))
assert len(rows) == 80, len(rows)
assert len({r['instance_id'] for r in rows}) == 80
assert all(r['run_num'] == 1 and r['condition'] == 'full-context' for r in rows)
print('Exit statuses:', dict(collections.Counter(r['exit_status'] for r in rows)))
print('Harbor errors:', sum(r['returncode'] != 0 for r in rows))
print('Missing/empty token logs:', sum(not r.get('step_prompt_tokens') for r in rows))
for r in rows:
    peak = max(r.get('step_prompt_tokens') or [0])
    print(r['instance_id'], peak, r['exit_status'],
          'compression_events=', r.get('compression_events'))
PY
```

Each task's peak is `max(step_prompt_tokens)`, not the sum of input tokens over
all calls. Missing logs and early failures must not be silently treated as
complete low-context trajectories. This collection does not choose A/P/B budget
thresholds automatically.

Reference: [vLLM model configuration](https://docs.vllm.ai/en/latest/api/vllm/config/model/).
