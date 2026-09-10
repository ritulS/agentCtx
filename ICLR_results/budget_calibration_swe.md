# Budget calibration (per-model A/P/B budgets)

Created: 2026-09-09 / Scope: SWE-Bench P100, agent model expansion (Devstral, GLM)
Related: [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md#budget-calibration-protocol), [EXPERIMENT_TIMELINE_DETAIL_SWE.md](EXPERIMENT_TIMELINE_DETAIL_SWE.md#budget-and-cohort-decisions), [FOLLOWUP_EXPERIMENTS.md](../exp_plans/FOLLOWUP_EXPERIMENTS.md)

## 1. Purpose

- The Qwen3.5-35B-A3B budgets 10K/15K/20K are tuned to that model's context growth.
- Other models (Devstral-24B, GLM-4.7-Flash) grow context differently, so A/P/B (tight / primary / loose) is re-derived per model instead of reusing the same numbers.
- What is matched is not the token count but the fraction of trajectories in which compression fires (trigger rate).
- Calibration data: FC (no compression, budget=∞) × P100 × run_1 = 100 trajectories per model. Each trajectory contributes `max(step_prompt_tokens)` (peak).

## 2. Runtime settings

### vLLM server

| Model | HF model ID | port | TP | dtype | `--max-model-len` | `--max-num-seqs` |
|---|---|---:|---:|---|---:|---:|
| Qwen3.5-35B-A3B | `Qwen/Qwen3.5-35B-A3B` | 8000 | 4 | auto | 102,400 | 64 |
| Devstral-Small-2-24B | `mistralai/Devstral-Small-2-24B-Instruct-2512` | 8002 | 4 | auto | ~~65,536~~ | 64 |
| GLM-4.7-Flash | `zai-org/GLM-4.7-Flash` | 8003 | 4 | auto | ~~65,536~~ | 64 |

- GPUs: `CUDA_VISIBLE_DEVICES=0,1,2,3` (Dobby).
- Launch scripts: [start_vllm_devstral.sh](../scripts/start_vllm_devstral.sh), [start_vllm_glm47flash.sh](../scripts/start_vllm_glm47flash.sh). Qwen is launched manually (recorded in `logs/vllm_qwen35_a3b.log`).
- `--max-num-seqs` is the server-side concurrency cap, separate from the experiment worker count (16).

### Agent (mini-swe-agent)

Shared by all three models ([configs/config-*-vllm.yaml](../configs/)):

| Setting | Value |
|---|---|
| `step_limit` | 125 LLM calls / run |
| `max_tokens` (per-generation cap) | 4,096 |
| `temperature` | 0.2 |
| `model_class` | `litellm_textbased` |
| `mode` | yolo |
| `cost_limit` | 0 (disabled) |

### FC collection run

| Setting | Value |
|---|---|
| condition | `full-context` |
| budget | 999,999,999 (= ∞; compression never fires) |
| depth | 0.5 (unused under FC) |
| tasks | P100 (django 34 / scikit-learn 32 / sympy 34) |
| runs/task | 1 (only run_1 is used for calibration) |
| workers | 16 |
| eval | yes (`--with-eval`; FC run_1 is reused as-is in experiments 2.a / 2.b) |
| launcher | `scripts/run_budget_calibration_sb.sh {devstral,glm}` → `run_experiment_iclr.py` |

| Model | Start (CDT) | End (CDT) | code |
|---|---|---|---|
| Devstral | 2026-08-28 12:15 | 2026-08-28 14:06 | `0d42a9b` |
| GLM | 2026-08-28 15:38 | 2026-08-28 17:47 | `0d42a9b` |

## 3. FC peak distribution (P100 × run_1, n=100 per model)

Unit: tokens. Distribution of `max(step_prompt_tokens)`.

| Model | min | P5 | P10 | P15 | P25 | P50 | P75 | P90 | max | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-35B-A3B | – | – | – | – | – | – | – | – | – | – |
| ~~Devstral-Small-2-24B~~ | ~~13,951~~ | ~~16,574~~ | ~~18,926~~ | ~~20,628~~ | ~~23,525~~ | ~~30,022~~ | ~~38,400~~ | ~~46,193~~ | ~~59,345~~ | ~~31,744~~ |
| ~~GLM-4.7-Flash~~ | ~~7,724~~ | ~~9,884~~ | ~~10,993~~ | ~~12,518~~ | ~~14,832~~ | ~~22,564~~ | ~~35,424~~ | ~~48,763~~ | ~~61,422~~ | ~~26,867~~ |

Trigger rate at candidate budgets (%, fraction with `peak > budget`):

| Budget | Qwen | Devstral | GLM |
|---:|---:|---:|---:|
| 8K | – | ~~100~~ | ~~98~~ |
| 10K | – | ~~100~~ | ~~94~~ |
| 12K | – | ~~100~~ | ~~86~~ |
| 15K | – | ~~98~~ | ~~74~~ |
| 20K | – | ~~87~~ | ~~60~~ |
| 25K | – | ~~72~~ | ~~46~~ |
| 30K | – | ~~50~~ | ~~32~~ |

- Trend: Devstral grows context the most. GLM has a smaller median but a longer tail.
- Source: `ICLR_results/swebench/main/<model>/di__binf__fc/{calibration_report.txt, fc_context_distribution.json}`

## 4. Computed vs adopted budgets

Reference trigger rates (Qwen tight / primary / loose): **97% / 88% / 76%**. The computed value is the 1K-step budget closest to each reference rate.

| Model | Computed (trigger-rate match) | Trigger rate of computed | **Adopted (A/P/B)** | Adoption rule |
|---|---|---|---|---|
| Qwen3.5-35B-A3B | – | – | **10K / 15K / 20K** | Existing values kept |
| Devstral-24B | 16K / 19K / 23K | 96 / 90 / 77 | **17K / 21K / 24K** | P5 / P15 / P25, rounded to 1K |
| GLM-4.7-Flash | 9K / 11K / 15K | 96 / 90 / 74 | **10K / 13K / 15K** | P5 / P15 / P25, rounded to 1K |

- The final adoption uses the **P5/P15/P25 rule**, not the trigger-rate match (matches the rounded percentiles in §3).
- Matches the launcher defaults: [run_agent_models_expansion.sh:57-73](../scripts/run_agent_models_expansion.sh#L57-L73).
- Cell names: Devstral `b17k/b21k/b24k`, GLM `bA/bP/bB` (=10K/13K/15K), Qwen `b10k/b15k/b20k`.

### Where the adopted budgets are used

| Phase | Qwen | Devstral | GLM |
|---|---|---|---|
| Main (P100) | 15K | 21K | 13K |
| Ablation (ABL-30) | 10K / 15K / 20K | 17K / 21K / 24K | 10K / 13K / 15K |
| Baseline (FC, OTRC) | ∞ | ∞ | ∞ |
