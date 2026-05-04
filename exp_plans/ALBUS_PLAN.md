# Albus — execution plan

Owner: ritul@utexas.edu. Created 2026-05-03 (updated 2026-05-04: 8 GPUs, was 6).
Hardware: 8× NVIDIA A6000 (384 GB total VRAM).
Workspace: TBD on Albus (suggested: `~/projects/agentCtx-mB` or rsync mirror of Dobby).

---

## Queue

Albus runs three experiments sequentially (each requires a different vLLM model serving — model swaps are unavoidable, plan for ~2h serving overhead per swap):

1. **Qwen2.5-7B-Instruct replication** (35 cells × 30 tasks × 2 runs = 2 100 runs, ~26h incl. setup)
2. **Llama 3.3 70B Instruct replication** (35 cells × 30 tasks × 2 runs = 2 100 runs, ~58h incl. setup; could be 45-72h depending on TP-8 throughput)
3. **Quantization sweep on Qwen3.5-35B-A3B** (TR + SU-full + FC + TRC+SS @ 20k × 4 quant levels × 30 tasks × 2 runs = 960 runs, ~21h incl. 4× model swaps)

**Wall-clock total**: ~105h ≈ **4.4 days** (with TP-8 on Llama 70B).

> **Important**: Phases 1 and 2 each include a *calibration pause* between
> running FC+OTRC (∞-budget cells) and the budgeted cells. The Qwen3.5-35B
> budgets (10k/15k/20k) are calibrated to that model's specific peak
> step-prompt-token distribution and won't transfer one-to-one to
> Qwen2.5-7B or Llama 3.3 70B. After FC+OTRC complete, compute the FC peak
> distribution and report back to Dobby for budget approval before
> launching the budgeted cells. See §1.3 and §2.2 for the exact protocol.

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
nvidia-smi                       # confirm 8 A6000s visible
venv/bin/python3 -c "import vllm, pandas, numpy; print('ok')"
ls task_lists/ablation_30tasks.json   # the 30-task list for ablations
ls task_lists/selected_tasks.json     # the 100-task list (used by Dobby's P100 runs, not Albus)
```

### 0.3 30-task ablation set is committed

Available at `task_lists/ablation_30tasks.json` (committed in d78d6bb so all
machines can pull it). No copy step needed.

### 0.4 Active_runs.md update

On Dobby, add to Active_runs.md:

```markdown
### Albus: model expansion + quantization sweep
- **Status:** RUNNING (Albus)
- **Started:** YYYY-MM-DD HH:MM CDT
- **Hardware:** 8× A6000 on <albus_hostname>
- **Phases:** 1 (Qwen2.5-7B) → 2 (Llama 3.3 70B) → 3 (Qwen3.5-35B quantization)
- **ETA:** ~4.4 days (with TP-8 on Llama 70B; range 4.0-5.4d depending on Llama throughput)
- **Logs:** Albus `logs/albus_phase{1,2,3}.log`
- **Result transfer:** post-completion rsync to Dobby `results/ablations/`
```

---

## 1. Phase 1: Qwen2.5-7B-Instruct replication (~26h)

### 1.1 Serving setup (~30 min)

Start vLLM with Qwen2.5-7B. Fits comfortably in 1 A6000 (~14 GB FP16). With 8 A6000s, simplest is a single TP=2 instance with high `--max-num-seqs` (other 6 GPUs idle, fine for a 7B model). If throughput is the bottleneck, switch to TP=1 with 4 instances behind a load balancer.

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

### 1.3 Run experiment — three sub-steps with a calibration pause

The Qwen3.5-35B-A3B budgets (10k/15k/20k) were calibrated to *that* model's
peak-context distribution. Qwen2.5-7B has a different distribution, so we
**must calibrate budgets from real data before running the budgeted cells**.

Workflow:
- **§1.3a**: run FC + OTRC only (both ∞-budget — no calibration dependency).
  Produces 60 FC trajectories whose peak `step_prompt_tokens` define the
  calibration.
- **§1.3b**: PAUSE — compute the FC peak distribution and report back to
  Dobby for budget approval. Do NOT proceed to §1.3c without explicit
  approval.
- **§1.3c**: run the 11 budgeted primitives × 3 calibrated budgets.

**Verify run_experiment.py supports `--model-tag` and `--agent-config`**
before launching — both are present as of commit 770577e.

#### §1.3a — FC + OTRC first (~6-8h)

`scripts/run_qwen25_7b_step1.sh`:

```bash
#!/bin/bash
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_7b_step1.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Qwen2.5-7B §1.3a: FC + OTRC ===" | tee -a "$LOG"

CONDS_INF="full-context online-trc"

venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-7b-inf \
    --model-tag    qwen25-7b \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    2>&1 | tee -a "$LOG"
venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-7b-inf \
    --model-tag    qwen25-7b \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --conditions   $CONDS_INF \
    --eval-only \
    2>&1 | tee -a "$LOG"

echo "[$(date)] === §1.3a done — STOP, run §1.3b calibration before continuing ===" | tee -a "$LOG"
```

Update `Active_runs.md` on launch and again on completion. **Do not auto-chain
to §1.3c.**

#### §1.3b — Calibration (5 min, no GPU)

After §1.3a completes, compute the FC peak distribution:

```bash
venv/bin/python3 -c "
import json, pathlib
rows = json.loads(pathlib.Path(
  'results/ablations/qwen25-7b-inf/experiment_results.json').read_text())
fc = [r for r in rows if r.get('condition')=='full-context']
peaks = sorted(max(r['step_prompt_tokens']) for r in fc if r.get('step_prompt_tokens'))
print(f'n={len(peaks)} FC trajectories')
print(f'p25={peaks[len(peaks)//4]}  median={peaks[len(peaks)//2]}  '
      f'p75={peaks[3*len(peaks)//4]}  max={peaks[-1]}')
print('Trigger rates at candidate budgets:')
for b in (4000, 6000, 8000, 10000, 12000, 15000, 20000, 25000, 30000):
    tr = sum(1 for p in peaks if p > b) / len(peaks)
    print(f'  {b//1000:>3}k → {tr*100:>3.0f}% trigger')
"
```

Paste the output back to Dobby. Budget proposal will mirror Qwen3.5-35B's
trigger rates (97% / 88% / 76% for tight / medium / loose) within ~5pp.
Wait for explicit approval before running §1.3c.

#### §1.3c — Run the 11 budgeted prims × 3 calibrated budgets (~18-20h)

Once budgets are locked, fill in `TIGHT_BUDGET`, `MEDIUM_BUDGET`,
`LOOSE_BUDGET` below.

`scripts/run_qwen25_7b_step3.sh`:

```bash
#!/bin/bash
set -euo pipefail
WS="$HOME/projects/agentCtx"
cd "$WS"
LOG="$WS/logs/qwen25_7b_step3.log"
mkdir -p "$WS/logs"
echo "[$(date)] === Qwen2.5-7B §1.3c: budgeted cells ===" | tee -a "$LOG"

CONDS_BUDGETED="truncation summarization summarization-partial structured-summarize structured-summarize-partial tool-result-clear trc-su trc-ss otrc-tr otrc-su-partial otrc-ss-partial"

# FILL THESE FROM §1.3b CALIBRATION
TIGHT_BUDGET=____
MEDIUM_BUDGET=____
LOOSE_BUDGET=____

# Run order: medium first, then tight, then loose (matches Dobby convention)
for budget in $MEDIUM_BUDGET $TIGHT_BUDGET $LOOSE_BUDGET; do
    name="qwen25-7b-budgeted-${budget}"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    qwen25-7b \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        2>&1 | tee -a "$LOG"
    venv/bin/python3 scripts/run_experiment.py \
        --ablation     "$name" \
        --model-tag    qwen25-7b \
        --agent-config config-qwen25-7b-vllm.yaml \
        --budget       "$budget" \
        --tasks-file   task_lists/ablation_30tasks.json \
        --conditions   $CONDS_BUDGETED \
        --eval-only \
        2>&1 | tee -a "$LOG"
done

echo "[$(date)] === Qwen2.5-7B done — switching to Llama 3.3 70B ===" | tee -a "$LOG"

# Stop vLLM, switch to Llama 70B
pkill -f vllm.entrypoints.openai.api_server || true
sleep 30
exec "$WS/scripts/run_llama33_70b_step1.sh"
```

### 1.4 Pre-flight pilot (10 min)

Before launching §1.3a, run a 5-task FC pilot to validate latency:

```bash
venv/bin/python3 scripts/run_experiment.py \
    --ablation     qwen25-7b-pilot \
    --model-tag    qwen25-7b \
    --agent-config config-qwen25-7b-vllm.yaml \
    --budget       999999999 \
    --tasks-file   task_lists/ablation_30tasks.json \
    --n-tasks      5 \
    --conditions   full-context \
    | tee logs/qwen25_7b_pilot.log
```

Median per-run latency should be ~300-500s on a 7B model. If much higher,
investigate before launching §1.3a.

Check the median per-run latency. If it's much higher than 400s, adjust the ETA in Active_runs.md.

---

## 2. Phase 2: Llama 3.3 70B Instruct replication (~58h, range 45-72h)

### 2.1 Serving setup (~1h, model weights are ~140GB so initial download is the slow part)

With 8 A6000s, use TP=8 — cleanest for a 70B model and gives the most headroom for KV cache (which lets us push `--max-num-seqs` higher → more concurrency → faster sweep).

```bash
# scripts/start_vllm_llama33_70b.sh
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  venv/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --port 8000 \
  --dtype auto \
  --tensor-parallel-size 8 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json \
  > logs/vllm_llama33_70b.log 2>&1 &
```

Verify, then create config-llama33-70b-vllm.yaml mirroring config-qwen25-7b-vllm.yaml but with `model_name: "hosted_vllm/meta-llama/Llama-3.3-70B-Instruct"`.

### 2.2 Run experiment — three sub-steps with a calibration pause

Same FC-first / calibrate / budgeted structure as Phase 1. Llama 3.3 70B has
a much tighter peak-context distribution than Qwen3.5-35B (preliminary FC
data on a different task subset shows median peak ~6k vs Qwen3.5's ~27k),
so its calibrated budgets will be substantially smaller — likely in the
3-8k range. **We must calibrate from the canonical 30-task set, not the
prior data.**

#### §2.2a — FC + OTRC first (~30-40h)

`scripts/run_llama33_70b_step1.sh` — mirrors §1.3a with `model-tag
llama33-70b` and `agent-config config-llama33-70b-vllm.yaml`. Output dir:
`results/ablations/llama33-70b-inf/`. Update `Active_runs.md` on launch.
**Do not auto-chain.**

#### §2.2b — Calibration (5 min, no GPU)

Same script as §1.3b but reading from
`results/ablations/llama33-70b-inf/experiment_results.json`. Paste the
output back to Dobby for budget approval. Wait for explicit approval.

#### §2.2c — Run the 11 budgeted prims × 3 calibrated budgets (~20-25h)

`scripts/run_llama33_70b_step3.sh` — mirrors §1.3c with `TIGHT_BUDGET`,
`MEDIUM_BUDGET`, `LOOSE_BUDGET` filled from §2.2b. Final `exec` →
`scripts/run_quantization_sweep.sh` (Phase 3).

### 2.3 Mid-run latency check (after ~30 min in §2.2a)

```bash
# How fast are runs actually completing?
tail -100 logs/llama33_70b_step1.log | grep -E '\[ +[0-9]+/'
# If the per-run latency is >1500s, post a warning to Active_runs.md and consider reducing scope
```

If latency >1500s/run sustained on TP-8, the 4.4-day estimate slips. Decide at that point: continue full sweep (6-7 days) or reduce to headline cells (FC + TRC+SS @ 20k only, ~120 runs, ~1-2 days).

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

- **vLLM OOMs at TP-8 for Llama 70B**: drop `--max-num-seqs` from 64 to 32 or 16. Re-run.
- **Phase 2 latency much higher than estimated**: pause; either extend the ETA or cut Llama scope to headline cells (FC + TRC+SS @ 20k only, ~120 runs, ~2 days).
- **Quantized model unavailable for Qwen3.5-35B-A3B**: substitute with quantized Qwen3.5-7B or skip that quant level.
- **rsync to Dobby fails**: results stay on Albus; rsync can be retried later. Don't block on transfer.

---

## 6. Chain structure (with calibration pauses)

The two calibration pauses (§1.3b after Phase 1's FC+OTRC, §2.2b after
Phase 2's FC+OTRC) prevent a single-PID chain across the whole queue.
Instead: each step runs as its own background job, the next step is
launched manually after Dobby approves the budgets.

```
§1.1-1.2  setup vLLM Qwen2.5-7B  (manual)
§1.3a     run_qwen25_7b_step1.sh  →  FC+OTRC, ~6-8h     (background)
                ↓ pause for calibration approval
§1.3c     run_qwen25_7b_step3.sh  →  budgeted cells, ~18-20h  (background, chains to §2.1)
§2.1      switch vLLM to Llama 70B  (autochained from end of step3)
§2.2a     run_llama33_70b_step1.sh  →  FC+OTRC, ~30-40h  (background)
                ↓ pause for calibration approval
§2.2c     run_llama33_70b_step3.sh  →  budgeted cells, ~20-25h  (chains to §3)
§3        run_quantization_sweep.sh  →  ~21h            (background)
```

Three nohup launches across the whole queue, with two human checkpoints
between them. Total runtime ~4.4 days (with TP-8 on Llama 70B).

Launch each segment as:

```bash
nohup scripts/run_<segment>.sh > logs/<segment>.out 2>&1 &
echo $! > logs/<segment>.pid
disown
```
