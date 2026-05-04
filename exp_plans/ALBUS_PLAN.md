# Albus — execution plan

Owner: ritul@utexas.edu. Created 2026-05-03.
Hardware: 6× NVIDIA A6000 (288 GB total VRAM).
Workspace: TBD on Albus (suggested: `~/projects/agentCtx-mB` or rsync mirror of Dobby).

---

## Queue

Albus runs three experiments sequentially (each requires a different vLLM model serving — model swaps are unavoidable, plan for ~2h serving overhead per swap):

1. **Qwen2.5-7B-Instruct replication** (35 cells × 30 tasks × 2 runs = 2 100 runs, ~26h incl. setup)
2. **Llama 3.3 70B Instruct replication** (35 cells × 30 tasks × 2 runs = 2 100 runs, ~72h incl. setup; could be 53-88h depending on TP-6 throughput)
3. **Quantization sweep on Qwen3.5-35B-A3B** (TR + SU-full + FC + TRC+SS @ 20k × 4 quant levels × 30 tasks × 2 runs = 960 runs, ~21h incl. 4× model swaps)

**Wall-clock total**: ~119h ≈ **5 days**.

---

## 0. Initial setup (~2h, one-time)

### 0.1 Workspace

Suggested: keep code in sync with Dobby via rsync or git. The simplest pattern:

```bash
# On Albus
mkdir -p ~/projects/agentCtx-mB
cd ~/projects/agentCtx-mB

# Pull from Dobby (assumes git remote is set up; if not, rsync)
git clone <repo-url> .
# Or: rsync -avz --exclude=results --exclude=logs --exclude=__pycache__ \
#       rs67788@dobby:/home/rs67788/projects/agentCtx/ .

# Set up venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt   # (or whatever the install pattern is)
```

### 0.2 Verify minimum environment

```bash
nvidia-smi                       # confirm 6 A6000s visible
venv/bin/python3 -c "import vllm, pandas, numpy; print('ok')"
ls task_lists/                   # selected_tasks.json should be present
ls results/ablations/tasks.json  # the 30-task list for ablations
```

### 0.3 Pull existing 30-task ablation set

```bash
cp results/ablations/tasks.json task_lists/ablation_30tasks.json
# (Albus will use this as the input task list for all three phases)
```

### 0.4 Active_runs.md update

On Dobby, add to Active_runs.md:

```markdown
### Albus: model expansion + quantization sweep
- **Status:** RUNNING (Albus)
- **Started:** YYYY-MM-DD HH:MM CDT
- **Hardware:** 6× A6000 on <albus_hostname>
- **Phases:** 1 (Qwen2.5-7B) → 2 (Llama 3.3 70B) → 3 (Qwen3.5-35B quantization)
- **ETA:** ~5 days
- **Logs:** Albus `logs/albus_phase{1,2,3}.log`
- **Result transfer:** post-completion rsync to Dobby `results/ablations/`
```

---

## 1. Phase 1: Qwen2.5-7B-Instruct replication (~26h)

### 1.1 Serving setup (~30 min)

Start vLLM with Qwen2.5-7B. Fits comfortably in 1 A6000 (~14 GB FP16); use 6 A6000s for high concurrency via TP=2 and 3 instances, OR a single TP=2 instance with high batch size. Simpler is the latter.

```bash
# scripts/start_vllm_qwen25_7b.sh
CUDA_VISIBLE_DEVICES=0,1 \
  venv/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --dtype auto \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  > logs/vllm_qwen25_7b.log 2>&1 &
```

Verify:

```bash
sleep 60 && curl -s http://localhost:8000/v1/models | head
```

### 1.2 Create model config

`config-qwen25-7b-vllm.yaml`:

```yaml
agent:
  step_limit: 125
  cost_limit: 0.0
  cost_tracking: ignore_errors
  mode: yolo
  confirm_exit: false

model:
  model_name: "hosted_vllm/Qwen/Qwen2.5-7B-Instruct"
  model_class: "litellm_textbased"
  model_kwargs:
    api_base: "http://localhost:8000/v1"
    drop_params: true
    temperature: 0.2
    max_tokens: 4096
  cost_tracking: ignore_errors

environment:
  env:
    PAGER: cat
    MANPAGER: cat
    LESS: -R
    PIP_PROGRESS_BAR: "off"
    TQDM_DISABLE: "1"
```

### 1.3 Run experiment

Set `MODEL_TAG=qwen25-7b` so result dirs are tagged distinctly. Add a `--model-tag` arg to `run_experiment.py` (already present).

`scripts/run_qwen25_7b.sh`:

```bash
#!/bin/bash
set -euo pipefail
WS="$HOME/projects/agentCtx-mB"
cd "$WS"
LOG="$WS/logs/qwen25_7b_replication.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Qwen2.5-7B replication starting ===" | tee -a "$LOG"

# Same 35 cells as Review1: 11 budgeted prims × 3 budgets + FC + OTRC
CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"
CONDS_INF="full-context online-trc"

for budget in 15000 10000 20000; do
    name="qwen25-7b-budgeted-${budget}"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --model-tag  "qwen25-7b" \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget     "$budget" \
        --tasks-file task_lists/ablation_30tasks.json \
        --conditions $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "$name" \
        --model-tag  "qwen25-7b" \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget     "$budget" \
        --tasks-file task_lists/ablation_30tasks.json \
        --conditions $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

# ∞-budget conditions
venv/bin/python3 scripts/run_experiment.py \
    --ablation   qwen25-7b-inf \
    --model-tag  "qwen25-7b" \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget     999999999 \
    --tasks-file task_lists/ablation_30tasks.json \
    --conditions $CONDS_INF \
    2>&1 | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation   qwen25-7b-inf \
    --model-tag  "qwen25-7b" \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget     999999999 \
    --tasks-file task_lists/ablation_30tasks.json \
    --conditions $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === Qwen2.5-7B replication done — chaining to Llama 3.3 70B ===" | tee -a "$LOG"

# Stop vLLM, switch to Llama 70B
pkill -f vllm.entrypoints.openai.api_server || true
sleep 30
exec "$WS/scripts/run_llama33_70b.sh"
```

**Verify run_experiment.py supports `--model-tag` and `--agent-config`** before launching — these args are referenced but I haven't confirmed they exist in the current code. If not, add them (they're 5-line additions).

### 1.4 Pre-flight pilot (10 min)

Before the full 2 100-run launch, run a 5-task × 1 condition × 1 run pilot (~5 runs) to validate latency:

```bash
venv/bin/python3 scripts/run_experiment.py \
    --ablation   qwen25-7b-pilot \
    --model-tag  qwen25-7b \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget     15000 \
    --tasks-file task_lists/ablation_30tasks.json \
    --n-tasks    5 \
    --conditions truncation \
    | tee logs/qwen25_7b_pilot.log
```

Check the median per-run latency. If it's much higher than 400s, adjust the ETA in Active_runs.md.

---

## 2. Phase 2: Llama 3.3 70B Instruct replication (~72h, range 53-88h)

### 2.1 Serving setup (~1h, model weights are ~140GB so initial download is the slow part)

```bash
# scripts/start_vllm_llama33_70b.sh
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5 \
  venv/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --port 8000 \
  --dtype auto \
  --tensor-parallel-size 6 \
  --max-model-len 32768 \
  --max-num-seqs 32 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json \
  > logs/vllm_llama33_70b.log 2>&1 &
```

Verify, then create config-llama33-70b-vllm.yaml mirroring config-qwen25-7b-vllm.yaml but with `model_name: "hosted_vllm/meta-llama/Llama-3.3-70B-Instruct"`.

### 2.2 Run experiment

Same wrapper structure as Phase 1, with `model-tag llama33-70b`:

`scripts/run_llama33_70b.sh` (mirror of run_qwen25_7b.sh, with two changes):
- `model_name` → Llama 3.3 70B
- Final `exec` → `scripts/run_quantization_sweep.sh`

### 2.3 Mid-run latency check (after ~30 min)

```bash
# How fast are runs actually completing?
tail -100 logs/llama33_70b_replication.log | grep -E '\[ +[0-9]+/'
# If the per-run latency is >1500s, post a warning to Active_runs.md and consider reducing scope
```

If latency >1500s/run sustained, the 5-day estimate slips. Decide at that point: continue full sweep (8+ days) or reduce to headline cells (FC + TRC+SS @ 20k only, ~120 runs, ~2 days).

---

## 3. Phase 3: Quantization sweep on Qwen3.5-35B-A3B (~21h)

### 3.1 Scope

4 conditions × 4 quantization levels × 30 tasks × 2 runs = 960 runs at 20k budget.

| condition | rationale |
|---|---|
| FC (full-context, no compression) | the no-compression baseline that shows degradation effect |
| TR (truncation) | simplest compression; quantization may interact with truncation differently |
| SU-full (summarization) | summarization quality may degrade more under quantization |
| TRC+SS (resolve-rate champ) | the headline compression strategy |

| quantization level | how to obtain |
|---|---|
| FP16 (baseline) | the standard Qwen3.5-35B-A3B weights |
| INT8 (W8A8) | use vLLM's `--quantization fp8` or run Qwen-INT8 if available |
| INT4-AWQ | download AWQ-quantized Qwen3.5-35B-A3B from HF (`Qwen/Qwen3.5-35B-A3B-AWQ-Int4` or similar) |
| INT4-GPTQ | download GPTQ-quantized variant |

If only 2-3 quant variants are reliably available on HF for this model, run those — note the omission and proceed.

### 3.2 Serving + run loop

```bash
#!/bin/bash
set -euo pipefail
WS="$HOME/projects/agentCtx-mB"
cd "$WS"
LOG="$WS/logs/quantization_sweep.log"

CONDS="full-context truncation summarization trc-ss"

QUANT_CONFIGS=(
    "fp16 Qwen/Qwen3.5-35B-A3B"
    "int8 Qwen/Qwen3.5-35B-A3B"           # use --quantization fp8 vLLM flag
    "awq-int4 Qwen/Qwen3.5-35B-A3B-AWQ"   # adjust HF id as needed
    "gptq-int4 Qwen/Qwen3.5-35B-A3B-GPTQ-Int4"
)

for entry in "${QUANT_CONFIGS[@]}"; do
    quant_tag=$(echo "$entry" | awk '{print $1}')
    model_name=$(echo "$entry" | awk '{print $2}')
    echo "[$(date)] --- $quant_tag : $model_name ---" | tee -a "$LOG"

    # Stop any prior vLLM
    pkill -f vllm.entrypoints.openai.api_server || true
    sleep 60

    # Start vLLM with the chosen quant
    if [ "$quant_tag" = "int8" ]; then
        QUANT_FLAG="--quantization fp8"
    elif [ "$quant_tag" = "awq-int4" ]; then
        QUANT_FLAG="--quantization awq"
    elif [ "$quant_tag" = "gptq-int4" ]; then
        QUANT_FLAG="--quantization gptq"
    else
        QUANT_FLAG=""
    fi

    CUDA_VISIBLE_DEVICES=0,1,2,3 \
      nohup venv/bin/python3 -m vllm.entrypoints.openai.api_server \
      --model "$model_name" \
      --port 8000 \
      --dtype auto \
      --tensor-parallel-size 4 \
      --max-model-len 32768 \
      --max-num-seqs 32 \
      $QUANT_FLAG \
      --enable-auto-tool-choice \
      --tool-call-parser hermes \
      > "logs/vllm_${quant_tag}.log" 2>&1 &

    sleep 120
    curl -s http://localhost:8000/v1/models > /dev/null || { echo "vLLM failed for $quant_tag"; exit 1; }

    # Generate config-quant.yaml on the fly
    cat > "config-quant-${quant_tag}.yaml" <<EOF
agent:
  step_limit: 125
  cost_limit: 0.0
  cost_tracking: ignore_errors
  mode: yolo
  confirm_exit: false
model:
  model_name: "hosted_vllm/${model_name}"
  model_class: "litellm_textbased"
  model_kwargs:
    api_base: "http://localhost:8000/v1"
    drop_params: true
    temperature: 0.2
    max_tokens: 4096
  cost_tracking: ignore_errors
environment:
  env:
    PAGER: cat
    MANPAGER: cat
    LESS: -R
EOF

    # Run experiment
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "quant-${quant_tag}" \
        --model-tag  "qwen35-a3b-${quant_tag}" \
        --agent-config "config-quant-${quant_tag}.yaml" \
        --budget     20000 \
        --tasks-file task_lists/ablation_30tasks.json \
        --conditions $CONDS \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation   "quant-${quant_tag}" \
        --model-tag  "qwen35-a3b-${quant_tag}" \
        --agent-config "config-quant-${quant_tag}.yaml" \
        --budget     20000 \
        --tasks-file task_lists/ablation_30tasks.json \
        --conditions $CONDS \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Quantization sweep complete — Albus queue done ===" | tee -a "$LOG"
```

### 3.3 Risks specific to quantization

- **HF availability**: confirm AWQ and GPTQ variants of Qwen3.5-35B-A3B exist before launching. If only AWQ exists, drop GPTQ and rerun the structure with 3 levels.
- **vLLM compatibility**: AWQ + tool-call-parser hermes may not co-operate. Test with a 1-task pilot before full launch.
- **Numerical instability**: aggressive quantization can produce nonsense outputs. Eyeball one trajectory per quant level for sanity.

---

## 4. Result transfer back to Dobby

After each phase finishes:

```bash
# On Albus
rsync -avz \
    results/qwen25-7b/ \
    rs67788@dobby:/home/rs67788/projects/agentCtx/results/qwen25-7b/

rsync -avz \
    results/ablations/qwen25-7b-* \
    rs67788@dobby:/home/rs67788/projects/agentCtx/results/ablations/

# After all 3 phases:
rsync -avz \
    results/ablations/llama33-70b-* \
    results/ablations/quant-* \
    rs67788@dobby:/home/rs67788/projects/agentCtx/results/ablations/
```

On Dobby, after results land:

```bash
# Add new model results to Review1.csv via build_review1.py
# (will need a --model-tag argument to filter; if not present, build separate CSVs)
venv/bin/python3 Review1/build_review1.py --model-tag qwen25-7b > Review1/Review1_qwen25-7b.csv
venv/bin/python3 Review1/build_review1.py --model-tag llama33-70b > Review1/Review1_llama33-70b.csv
venv/bin/python3 Review1/build_review1.py --model-tag qwen35-a3b-fp16 > Review1/Review1_quant_fp16.csv
# ... etc for each quant tag
```

Then cross-model comparison figure:

```bash
venv/bin/python3 Review1/plot_cross_model.py
# fig: FC resolve rate vs model class (Qwen2.5-7B, Qwen3.5-35B-A3B, Llama 3.3 70B)
#      and Pareto compression-as-perf-tool gap per model
```

---

## 5. Failure recovery

- **vLLM OOMs at TP-6 for Llama 70B**: try TP-8 if Albus has 8 GPUs, or drop max-num-seqs from 32 to 16. Re-run.
- **Phase 2 latency much higher than estimated**: pause; either extend the ETA or cut Llama scope to headline cells (FC + TRC+SS @ 20k only, ~120 runs, ~2 days).
- **Quantized model unavailable for Qwen3.5-35B-A3B**: substitute with quantized Qwen3.5-7B or skip that quant level.
- **rsync to Dobby fails**: results stay on Albus; rsync can be retried later. Don't block on transfer.

---

## 6. Single-PID chain

After Phase 1 pilot validates latency, the three phases chain via `exec`:

```
run_qwen25_7b.sh → exec run_llama33_70b.sh → exec run_quantization_sweep.sh
```

```bash
nohup scripts/run_qwen25_7b.sh > logs/albus_chain.out 2>&1 &
echo $! > logs/albus_chain.pid
disown
```

One PID, one log per phase. Total runtime ~5 days.
