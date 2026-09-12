# Budget calibration — Terminal-Bench 1.0 (per-model A/P/B budgets)

Created: 2026-09-09 / Scope: Terminal-Bench 1.0 P-80, agent model expansion (Qwen, Devstral, GLM)
Related: [EXPERIMENT_LOG_TB.md](EXPERIMENT_LOG_TB.md#fc-calibration), [EXPERIMENT_TIMELINE_DETAIL.md](EXPERIMENT_TIMELINE_DETAIL.md), [FOLLOWUP_EXPERIMENTS.md §3](../exp_plans/FOLLOWUP_EXPERIMENTS.md#exp-tb), SWE version: `budget_calibration_swe.md`
Procedures: [GLM_TB_NATIVE_CALIBRATION.md](../scripts/GLM_TB_NATIVE_CALIBRATION.md), [DEVSTRAL_TB_NATIVE_CALIBRATION.md](../scripts/DEVSTRAL_TB_NATIVE_CALIBRATION.md)

## 1. Purpose

- As on SWE-Bench, each model grows context differently, so the A/P/B (tight / primary / loose) budgets are derived per model for TB as well.
- TB trajectories have fewer steps than SWE (median around 20 calls) and smaller peak token counts, so budgets are cut in the **few-K range** rather than the 10K–20K range used for SWE.
- Budgets are not fixed token counts; they are cut at **P5 / P15 / P25 of each model's FC peak distribution** (same rule as the SWE version).
- Calibration data: FC (no compression, budget=∞) × P-80 × run_1 = up to 80 trajectories per model. Each trajectory contributes `max(step_prompt_tokens)` (peak).
- **For Devstral and GLM, the calibration data is the re-collection (2026-09-09) with vLLM's `--max-model-len` set to the model's native context length.** The FC run_1 collected on 8/30–31 at 65,536 is kept in §3.2 for comparison only. Qwen was not re-collected; its 8/29–31 data at the 102,400 setting is used as-is.

## 2. Runtime settings

### vLLM server (during calibration collection)

| Model | HF model ID | port | TP | dtype / KV | quant | `--max-model-len` | effective `max_seq_len` | `--max-num-seqs` | GPU | vLLM |
|---|---|---:|---:|---|---|---|---:|---:|---|---|
| Qwen3.5-35B-A3B | `Qwen/Qwen3.5-35B-A3B` | 8000 | 4 | bf16 / auto | none | 102,400 | 102,400 | 64 | 0–3 | 0.17.1 |
| Devstral-Small-2-24B | `mistralai/Devstral-Small-2-24B-Instruct-2512` | 8002 | 4 | bf16 / auto | fp8 (from checkpoint) | **native (omitted)** | **393,216** | 4 | 4–7 | 0.17.1 |
| GLM-4.7-Flash | `zai-org/GLM-4.7-Flash` | 8003 | 4 | bf16 / auto | none | **native (omitted)** | **202,752** | 64 | 0–3 (script default) | 0.28.0 |

- Host: Albus (8× RTX A6000 48GB). The Devstral and GLM native collections ran concurrently on the same host (GPUs split 4–7 / 0–3).
- Launch: `DEVSTRAL_MAX_MODEL_LEN=native DEVSTRAL_CUDA_VISIBLE_DEVICES=4,5,6,7 DEVSTRAL_MAX_NUM_SEQS=4 bash scripts/start_vllm_devstral.sh` and `GLM_MAX_MODEL_LEN=native bash scripts/start_vllm_glm47flash.sh` ([start_vllm_devstral.sh](../scripts/start_vllm_devstral.sh), [start_vllm_glm47flash.sh](../scripts/start_vllm_glm47flash.sh)). `native` omits `--max-model-len` entirely.
- Devstral's effective length 393,216 comes from `max_position_embeddings` in the HF `config.json` (YaRN: 8192 × 48), not the 262,144 in Mistral's `params.json`. Verified via `vllm_models.json`.
- Qwen's native context is 262,144, but the TB collection stayed at 102,400 (server setting as of 8/29, `logs/vllm_qwen35.log`).
- All servers use `--enable-prefix-caching`. Devstral uses `--max-num-seqs 4` because of KV capacity (393K tokens × 2.34 concurrent is the ceiling).
- `--max-num-seqs` is the server-side concurrency cap, separate from Harbor's `--n-concurrent`.

### Agent (mini-swe-agent 2.2.6 + Harbor 0.20.0)

Shared by all three models ([configs/config-*-vllm.yaml](../configs/) merged onto [configs/config-tbench.yaml](../configs/config-tbench.yaml)):

| Setting | Value |
|---|---|
| `step_limit` | 100 LLM calls / run (`config-tbench.yaml`) |
| `max_tokens` (per-generation cap) | 4,096 |
| `temperature` | 0.2 |
| `model_class` | `litellm_textbased` |
| `mode` | yolo |
| `cost_limit` | 0 (disabled) |
| Observation clipping | Output over 10,000 chars is reduced to head 5,000 + tail 5,000 |
| Command timeout | 60 s / command |
| Task timeout | `agent.timeout_sec` from task.toml (e.g. 900 s) × multiplier 1.0 |
| Environment | rootless Podman, prebuilt images (80/80) |

### FC collection run

| Setting | Value |
|---|---|
| condition | `full-context` |
| budget | 999,999,999 (= ∞; compression never fires) |
| depth | 0.5 (unused under FC) |
| tasks | P-80 (`terminal-bench-core@0.1.1`, 80 tasks) |
| runs/task | 1 (only run_1 is used for calibration) |
| Harbor | `--n-attempts 1 --max-retries 0` |
| eval | yes (Harbor verifier, `reward`) |

| Model | Data | Start (CDT) | End (CDT) | Concurrency | code | Output |
|---|---|---|---|---:|---|---|
| Qwen | rootless 42 | 2026-08-29 17:05 | 2026-08-29 17:44 | 4 | `77b6da5` | `ICLR_results/terminalbench/main/p80_rootless/qwen35b/di__binf__fc/` |
| Qwen | subuid 38 | 2026-08-30 20:22 | 2026-08-30 21:02 | 4 | `55d9ea5` | `ICLR_results/terminalbench/main/p80_subuid_required/qwen35b/di__binf__fc/` |
| Devstral | **native P-80** | 2026-09-09 09:58 | 2026-09-09 12:35 | 2 | `26d5fbc` + uncommitted diff | `calibration_results/terminalbench/devstral24b_native_p80/` |
| GLM | **native P-80** | 2026-09-09 09:15 | 2026-09-09 10:54 | 4 | `26d5fbc` + uncommitted diff | `calibration_results/terminalbench/glm47flash_native_p80/` |

- Launcher for the native collections: `scripts/run_budget_calibration_tb.py --calibration-dir ...` (`--calibration-dir` and the prefix-cache recording were uncommitted as of 9/9; `scripts/log_vllm_prefix_cache.py` is also untracked). Nothing is written to the canonical `ICLR_results/`; everything is isolated under `calibration_results/`.
- Each native collection directory contains `results/experiment_results.json`, `results/<task>/full-context/run_1/`, `results/CALIBRATION_MANIFEST.json` (80/80 complete), `harbor_jobs/`, `metrics/*/prefix_cache.jsonl`, and, for Devstral only, `vllm_startup.log` and `vllm_models.json`.
- The 65K-setting Devstral / GLM FC run_1 (comparison only) lives in the same `p80_rootless` / `p80_subuid_required` cells as Qwen (8/30 03:44–04:33 and 23:05–23:54 / 8/30 11:52–12:50 and 8/31 00:25–01:33 CDT).

## 3. FC peak distribution

### 3.0 Aggregation rules

- peak = `max(step_prompt_tokens)` per trajectory, not the sum of input tokens.
- **Trajectories without a token log are excluded** (mixing them in as peak=0 collapses P5/P10). Reasons for exclusion are in §5. Valid n: Qwen 73, Devstral native 73, GLM native 74.
- Percentiles use numpy's default (linear interpolation). Trigger rate is the fraction with `peak > budget`.

### 3.1 Native collection (adopted data, collected 2026-09-09)

Unit: tokens.

| Model | n | min | P5 | P10 | P15 | P25 | P50 | P75 | P90 | max | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-35B-A3B (native 262K) | | | | | | | | | | | |
| Devstral-Small-2-24B (native 393K) | 73 | 1,151 | 2,368 | 3,393 | 3,929 | 6,334 | 12,563 | 22,360 | 29,836 | 312,264 | 20,128 |
| GLM-4.7-Flash (native 203K) | 74 | 1,027 | 1,595 | 2,453 | 2,732 | 4,489 | 9,668 | 16,377 | 23,893 | 48,203 | 12,340 |

Trigger rate at candidate budgets (%, fraction with `peak > budget`):

| Budget | Qwen | Devstral | GLM |
|---:|---:|---:|---:|
| 1K | | 100.0 | 100.0 |
| 2K | | 95.9 | 93.2 |
| 3K | | 91.8 | 82.4 |
| 4K | | 83.6 | 79.7 |
| 5K | | 78.1 | 71.6 |
| 6K | | 75.3 | 67.6 |
| 7K | | 69.9 | 62.2 |
| 8K | | 61.6 | 59.5 |
| 10K | | 57.5 | 48.6 |
| 12K | | 50.7 | 40.5 |
| 15K | | 43.8 | 27.0 |

### 3.2 Reference: 65K-setting FC run_1 (8/30–31, old calibration data)

- In this collection, vLLM's `--max-model-len` was mistakenly set to **65,536** instead of the model's native context length (Devstral native 393,216, GLM native 202,752). The peak tail was therefore censored server-side, so this data is not used for calibration. It was replaced by the native re-collection in §3.1.

<details>
<summary><strong>65K-setting distribution and trigger rates (for comparison)</strong></summary>

| Model | n | P5 | P15 | P25 | P50 | P75 | P90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Devstral (65K) | 74 | 2,705 | 3,864 | 6,573 | 12,386 | 22,886 | 30,687 | 60,457 |
| GLM (65K) | 73 | 2,165 | 2,859 | 5,240 | 9,419 | 16,370 | 22,113 | 58,424 |

| Budget | Devstral 65K | GLM 65K |
|---:|---:|---:|
| 2K | 97.3 | 95.9 |
| 3K | 93.2 | 83.6 |
| 4K | 83.8 | 82.2 |
| 5K | 78.4 | 75.3 |
| 7K | 74.3 | 64.4 |

- P50–P90 are nearly the same between 65K and native. The differences are in the lower end P5–P25 (sampling noise; Devstral 2,705→2,368, GLM 5,240→4,489) and Devstral's max (60K→312K).
- The current launcher defaults (Devstral 3K/4K/7K, GLM 2K/3K/5K) match the P5/P15/P25 of this 65K data rounded to 1K.

</details>

## 4. Computed vs adopted budgets

The derivation rule is the same **P5 / P15 / P25 rule** as the SWE version (P5 / P15 / P25 of the FC peak distribution in §3.1, rounded to 1K).

| Model | Computed from native collection, P5 / P15 / P25 (rounded to 1K) | **Adopted (A/P/B) (used for Main / ablation)** | Percentile the adopted values land on in the native distribution | Notes |
|---|---|---|---|---|
| Qwen3.5-35B-A3B | | **2K / 3K / 4K** (from 102K data) | | |
| Devstral-24B | **2K / 4K / 6K** | **3K / 4K / 7K** (from 65K data) | P8 / P16 / P30 | Native lowers A and B by 1K each; P unchanged at 4K |
| GLM-4.7-Flash | **2K / 3K / 4K** | **2K / 3K / 5K** (from 65K data) | P7 / P18 / P28 | Native lowers B from 5K to 4K; A and P unchanged |

- "Percentile landed on" is the fraction of trajectories with `peak ≤ budget` in the native distribution (Devstral 3K: 6/73, 4K: 12/73, 7K: 22/73; GLM 2K: 5/74, 3K: 13/74, 5K: 21/74).
- The adopted values are the ones used for Main (P-40) and ablation (P-15). Devstral / GLM A/B differ from the native-computed values by 1K, but they still land at P7–P8 / P15–P18 / P28–P30 in the native distribution, so the intended tight / primary / loose positioning holds. **Primary (P) matches the native-computed value for all three models.**
- Launcher defaults: [run_agent_models_expansion_tb.sh:18-26](../scripts/run_agent_models_expansion_tb.sh#L18-L26). Plan: [FOLLOWUP_EXPERIMENTS.md §3](../exp_plans/FOLLOWUP_EXPERIMENTS.md#exp-tb).
- Cell names: Qwen `b2k/b3k/b4k`, Devstral `b3k/b4k/b7k`, GLM `b2k/b3k/b5k`.

### Where the adopted budgets are used

| Phase | Qwen | Devstral | GLM |
|---|---|---|---|
| Main (P-40) | 3K | 4K | 3K |
| Ablation (P-15) | 2K / 3K / 4K | 3K / 4K / 7K | 2K / 3K / 5K |
| Baseline (FC, OTRC) | ∞ | ∞ | ∞ |

## 5. Missing data and censoring

<details>
<summary>Details on missing token logs, exit statuses, and prefix cache</summary>

### Trajectories without a token log (excluded from the distribution)

| Task | Qwen | Devstral native | GLM native | Cause |
|---|---|---|---|---|
| `oom`, `security-vulhub-minio`, `simple-sheets-put`, `simple-web-scraper`, `create-bucket`, `extract-safely` | missing | missing | missing | Harbor `docker compose` startup failure (`RuntimeError: Docker compose command failed`). The agent never ran. Common to all three models and both 65K/native |
| `polyglot-rust-c` | missing (7 calls) | present | present | Qwen 8/29 collection only; token log not written |
| `intrusion-detection` | present | missing (12 calls, `CancelledError`) | present | Devstral native only; token log not written at task timeout |

- The 6 tasks above fail on the environment side, so they fail consistently in calibration. They are in neither `tbench_p40.json` nor `tbench_abl15.json`, so Main / ablation are unaffected.

### Exit status (valid trajectories)

| Model | Submitted | timeout (`CancelledError`) | `LimitsExceeded` (100 steps) | Other |
|---|---:|---:|---:|---:|
| Qwen (102K) | 55 | 15 (recorded as `''` by the old adapter) | 2 | `BadRequestError` 1 (context limit) |
| Devstral native | 57 | 14 | 2 | — |
| GLM native | 44 | 27 | 3 | — |

- `CancelledError` is Harbor's `AgentTimeoutError` (`agent.timeout_sec` from task.toml, multiplier 1.0). It has been recorded this way since the 9/6 adapter fix; the 8/30 collection recorded it as an empty string.
- Calibration peaks are censored by the step limit (100), the task timeout, and output clipping (10,000 chars). FC=∞ only means "no compression"; execution is not unbounded.
- Under the native setting, `ContextWindowExceededError` / `BadRequestError` occurred 0 times for Devstral and GLM. The 65K collection had 1 for GLM.

### Prefix cache (during native collection, server-wide counter deltas)

| Model | Records | queries (tokens) | hits (tokens) | hit rate |
|---|---:|---:|---:|---:|
| Devstral | 940 | 32.7M | 31.6M | 96.9% |
| GLM | 592 | 19.4M | 18.5M | 95.2% |

- Start→end delta from `metrics/<job>/prefix_cache.jsonl`. No other clients were connected at the time.

</details>

## 6. Re-aggregation command

<details>
<summary>Snippet to recompute the numbers in §3.1 / §4</summary>

```bash
cd /home/ak58925/agentCtx
venv/bin/python - <<'PY'
import json, numpy as np
src = {
  "qwen":     ["ICLR_results/terminalbench/main/p80_rootless/qwen35b/di__binf__fc/experiment_results.json",
               "ICLR_results/terminalbench/main/p80_subuid_required/qwen35b/di__binf__fc/experiment_results.json"],
  "devstral": ["calibration_results/terminalbench/devstral24b_native_p80/results/experiment_results.json"],
  "glm":      ["calibration_results/terminalbench/glm47flash_native_p80/results/experiment_results.json"],
}
for name, paths in src.items():
    rows = [r for p in paths for r in json.load(open(p)) if r.get("run_num", 1) == 1]
    peaks = np.array([max(r["step_prompt_tokens"]) for r in rows if r.get("step_prompt_tokens")])
    print(name, "n=%d" % len(peaks),
          "P5/P15/P25 = %d / %d / %d" % tuple(np.percentile(peaks, [5, 15, 25])),
          "trig@2K/3K/4K = %.1f / %.1f / %.1f" % tuple(100 * (peaks > b).mean() for b in (2000, 3000, 4000)))
PY
```

</details>
