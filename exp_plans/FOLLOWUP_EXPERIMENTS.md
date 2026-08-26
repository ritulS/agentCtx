# Follow-up Experiments Plan
Last update: August 24 by Akiho

## Overview

| Priority | Experiment | Dataset(s) | ETA |
|---:|---|---|---|
| 1 | [Increase runs/task](#exp-runs) | SWE: P100 + ABL-30 | **3–5 days** (4400 runs) |
| 2 | [Add 2 agent models](#exp-models) | SWE: P100 + ABL-30 | **3–7 days** (8580 runs) + TBD (8580 runs) |
| 3 | [Terminal-Bench evaluation](#exp-tb) | TB: Full + ABL-20 | TBD (31,200 runs) |
| 4 | [Summarizer ablation](#exp-summarizer) | SWE: ABL-30; TB: ABL-20 | TBD (760 runs) |
| 5 | [Quantization ablation](#exp-quantization) | TBD | TBD |
| 6 | [Add ACON](#exp-acon) | SWE: P100 | TBD |

- Experiments env: **Dobby (GPU: 4× A100 80GB)**
- Metrics: resolve rate (SWE-Bench), accuracy (Terminal-Bench), token cost, latency, compression behavior

<a id="exp-runs"></a>
## 1. [Priority] SWE-Bench: Runs/task: 2->3
- ETA: 3–5 days
- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : **3 (Additional 1 run/task** mostly)


| Primitives | Depths | Budget |Task |Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 | 1500 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3 / 0.7** | 10K / 15K / 20K | **ABL-30** | **900** | **Ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K | P100 | 5800 | Full-depth alternative (not used) |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100| 1800 ||
| FC, OTRC | depth invariant | ∞ | P100 | 200 ||

<a id="exp-models"></a>
## 2. [Priority] SWE-Bench: Add 2 agent models
- **GLM budget calibration (required before launch):** determine the model-appropriate primary budget *P*K (and ablation budgets *A*K/*B*K)
- Runs/task : 3

| Experiment | Model<br>(agent & summarizer) |Dataset | Notes | Runs |ETA |
|---|---|---|---|---|---|
| [(2.a) Devstral-24B Main](#exp-models-devstral-main) | Devstral-Small-2-24B|SB:P-100| Depth: 0.5 or depth-invariant / Budget: 15K or *P*K (or ∞) | 3900|1.3-3.3 days|
| [(2.b) GLM Main](#exp-models-glm-main) | GLM-4.7-Flash (30B-A3B MoE)|SB:P-100 | Depth: 0.5 or depth-invariant / Budget: 15K or *P*K (or ∞) | 3900|TBD|
| [(2.c) Devstral-24B Ablation](#exp-models-devstral-abl) | Devstral-Small-2-24B|SB:ABL-30 |depth & budget ablation|4680|1.6-3.9 days|
| [(2.d) GLM Ablation](#exp-models-glm-abl) | GLM-4.7-Flash (30B-A3B MoE)|SB:ABL-30 | depth & budget ablation |4680|TBD|

<a id="exp-models-devstral-main"></a>
### (2.a) Devstral-24B Main

| Primitives | Depths | Budget |Task | Runs |
|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  | 15K  | SB:P100 | 1500 |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |15K | SB:P100 | 1800 |
| FC, OTRC | depth invariant | ∞ | SB:P100 |600 |

<a id="exp-models-glm-main"></a>
### (2.b) GLM Main

| Primitives | Depths | Budget |Task | Runs |
|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  | *P*K  | SB:P100 |1500 |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant | *P*K | SB:P100 |1800 |
| FC, OTRC | depth invariant | ∞ | SB:P100 | 600|


<a id="exp-models-devstral-abl"></a>
### (2.c) Devstral-24B Ablation

| Primitives | Depths | Budget |Task | Runs |
|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 | 10K / 15K / 20K | SB:ABL-30 | 2700 |
| TR, SU-full, SU-partial, SS, SS-partial | 0.5 | 10K / 20K | SB:ABL-30 | 900 |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 20K | SB:ABL-30 | 1080 |

<a id="exp-models-glm-abl"></a>
### (2.d) GLM Ablation

| Primitives | Depths | Budget |Task | Runs |
|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 | *A*K / *P*K / *B*K | SB:ABL-30 | 2700 |
| TR, SU-full, SU-partial, SS, SS-partial | 0.5 | *A*K / *B*K | SB:ABL-30 | 900|
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |*A*K / *B*K | SB:ABL-30 | 1080|

<a id="exp-tb"></a>
## 3. [Priority] Terminal-Bench Evaluation
- Terminal-Bench 1.0 (80 tasks)
- Runs/task : 5
- Models (agent & summarizer): Qwen3.5-35B-A3B-Instruct, Devstral-Small-2-24B, GLM-4.7-Flash (30B-A3B MoE)

| Experiment | Dataset | Notes | Runs | ETA |
|---|---|---|---|---|
| [(3.a) TB Main](#exp-tb-main) | TB:P-80| Depth: 0.5 or depth-invariant / Budget: 15K or *P*K(or ∞) | 15600|TBD|
| [(3.b) TB Ablation](#exp-tb-abl) | TB:ABL-20 |depth & budget ablation|15600|TBD|

<a id="exp-tb-main"></a>
### (3.a) TB Main
| Models| Primitives | Depths | Budget | Tasks | Runs |
|---|---|---|---|---|---|
| Qwen-35B-A3B/<br>Devstral-24B | TR, SU-full, SU-partial, SS, SS-partial | 0.5 | 15K |TB:P-80 | 4000 |
| GLM | TR, SU-full, SU-partial, SS, SS-partial | 0.5 | *P*K |TB:P-80 | 2000 |
| Qwen-35B-A3B/<br>Devstral-24B |TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial |  depth invariant | 15K | TB:P-80 |4800|
| GLM |TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial |  depth invariant | *P*K | TB:P-80 |2400|
| Qwen-35B-A3B/<br>Devstral-24B/<br>GLM |FC, OTRC |  depth invariant | ∞ | TB:P-80 | 2400|

<a id="exp-tb-abl"></a>
### (3.b) TB Ablation
| Models| Primitives | Depths | Budget | Tasks | Runs |
|---|---|---|---|---|---|
| Qwen-35B-A3B/<br>Devstral-24B | TR, SU-full, SU-partial, SS, SS-partial | 0.5 | 10K/20K |TB:ALB-20 | 2000|
| GLM | TR, SU-full, SU-partial, SS, SS-partial | 0.5 | *A*K/*B*K |TB:ALB-20 | 1000|
| Qwen-35B-A3B/<br>Devstral-24B | TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | 10K/15K/20K |TB:ALB-20 | 6000|
| GLM | TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | *A*K/*P*K/*B*K |TB:ALB-20 | 3000|
| Qwen-35B-A3B/<br>Devstral-24B | TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant | 10K/20K | TB:ALB-20 |2400|
| GLM | TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant | *A*K/*B*K | TB:ALB-20 |1200|

<a id="exp-summarizer"></a>
## 4. [Priority] Summarizer Ablation
- ETA: TBD (760 runs)
- Agent: Qwen3.5-35B-A3B-Instruct

Existing self-summarization runs are used as the baseline.

| | **Summarizer** | Primitives | Agent | Budget | Tasks | Runs/task |
|---|---|---|---|---|---|---:|
|(4.a)|**Qwen3.5-9B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen-35B-A3B | 15K | SB:ABL-30 | 3 |
|(4.b)|**Qwen3.5-9B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen-35B-A3B | 15K | TB:ABL-20 | 5 |
|(4.c)|**Gemma-4-12B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen-35B-A3B | 15K | SB:ABL-30 | 3 |
|(4.d)|**Gemma-4-12B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen-35B-A3B | 15K | TB:ABL-20 | 5 |

<a id="exp-quantization"></a>
## 5. Quantization ablation
- ETA: TBD


<a id="exp-acon"></a>
## 6. SWE-Bench: Add [ACON](https://arxiv.org/abs/2510.00615)
- ETA: TBD
- Model (agent & judge/optimizer): Qwen3.5-35B-A3B-Instruct 
  - judge/optimizer for the offline summary-guideline optimization loop
- New primitive: `ACON`
  - Need a subset data for the offline summary-guideline optimization (size: **TBD**, around 30)
  - 'preserve_last_k_turns': 1 (default value in original)

| Primitives | Depth | Budget | Task | Runs |
|---|---|---|---|---|
| ACON | N/A (no depth param) | **TBD** |P100 (100 tasks) | 300 |
