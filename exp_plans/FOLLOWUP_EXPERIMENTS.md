# Follow-up Experiment Plan
Last update: August 24 by Akiho

## Overview

| Priority | Experiment | Dataset(s) | ETA |
|---:|---|---|---|
| 1 | [Increase runs/task](#exp-runs) | SWE: P100 + ABL-30 | **3–5 days** (4,400 runs) |
| 2 | [Add 2 agent models](#exp-models) | SWE: P100 + ABL-30 | **10 days** (11,820 runs) / TBD (13,200 runs) |
| 3 | [Terminal-Bench evaluation](#exp-tb) | TB: Full + ABL-20 | TBD (17,000 runs) |
| 4 | [Summarizer ablation](#exp-summarizer) | SWE: ABL-30; TB: ABL-20 | TBD (760 runs) |
| 5 | [Quantization ablation](#exp-quantization) | TBD | TBD |
| 6 | [Add ACON](#exp-acon) | SWE: P100 | TBD |

- Experiments env: **Dobby (GPU: 4× A100 80GB)**
- Metrics: resolve rate (SWE-Bench), accuracy (Terminal-Bench), token cost, latency, compression behavior

<a id="exp-runs"></a>
## 1. [Priority] SWE-Bench: Runs/task: 2->3
- ETA

  | Status | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
  |---|---|---|---|---|
  | **Selected** | **Ablation-depth runs** | P100 (100 tasks) | **ABL-30 (30 tasks)** | **3–5 days** |
  | Not selected | Full-depth runs | P100 (100 tasks) | P100 (100 tasks) | 7–11 days |

- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : **3 (Additional 1 run/task** mostly)


| Primitives | Depths | Budget |Task |Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 1500 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3 / 0.7** | 10K / 15K / 20K | **ABL-30 (30 tasks)** | **900** | **Selected: ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K | P100 (100 tasks) | 5800 | Not selected: full-depth alternative |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 1800 ||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 200 ||

<a id="exp-models"></a>
## 2. [Priority] SWE-Bench: Add 2 agent models
- ETA: TBD
  - Devstral-Small-2-24B: **10 days** 
    - Skip existing [Budget: 15K, Depth: 0.5, Task: ABL-30]

      | Status | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
      |---|---|---|---|---|
      | **Selected** | **Ablation-depth runs** | P100 (100 tasks) | **ABL-30 (30 tasks)** | **10 days** |
      | Not selected | Full-depth runs | P100 (100 tasks) | P100 (100 tasks) | 15 days |


  - GLM-4.7-Flash: TBD (13,200 runs)
- Model (agent & summarizer): **Devstral-Small-2-24B**, **GLM-4.7-Flash** (30B-A3B MoE)
- Runs/task : 3


**Devstral-Small-2-24B**
| Primitives | Depths | Budget |Task | Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 4200 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3 / 0.7** | 10K / 15K / 20K | **ABL-30 (30 tasks)** | **2100** | **Selected: ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K | P100 (100 tasks) | 8400 | Not selected: full-depth alternative |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 5040||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 480 ||

**GLM-4.7-Flash**
| Primitives | Depths | Budget |Task | Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 4500 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3 / 0.7** | 10K / 15K / 20K | **ABL-30 (30 tasks)** | **2700** | **Selected: ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K | P100 (100 tasks) | 9000 | Not selected: full-depth alternative |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 5400 ||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 600 |

<a id="exp-tb"></a>
## 3. [Priority] Terminal-Bench Evaluation
- ETA: 
    | Status | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
    |---|---|---|---|---|
    | **Selected** | **Ablation-depth runs** | Full (80 tasks) | **ABL-20 (20 tasks)** | TBD (3000 runs) |
    | Not selected | Full-depth runs | Full (80 tasks) | Full (80 tasks) | TBD (12000 runs) |

- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : 5
- Task: Terminal-Bench 1.0 Full (80 tasks)


| Primitives | Depths | Budget | Tasks | Runs | Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5 | Full (80 tasks)|10K / 15K / 20K | 6000 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3/0.7** | **ABL-20 (20 tasks)** | 10K / 15K / 20K | **3000** | **Selected: ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | Full (80 tasks)|10K / 15K / 20K | 12000 | Not selected: full-depth alternative |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant |10K / 15K / 20K | Full (80 tasks)| 7200 ||
| FC, OTRC | depth invariant | ∞ | Full (80 tasks)| 800 ||


<a id="exp-summarizer"></a>
## 4. [Priority] Summarizer-model ablation
- ETA: TBD (760 runs)
- Budget: 15K

Existing self-summarization runs are used as the baseline.

| **Summarizer** | Primitives | Agent | Benchmark | Tasks | Runs/task |
|---|---|---|---|---|---:|
| **Qwen3.5-9B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen3.5-35B-A3B-Instruct | SWE-Bench | ABL-30 | 3 |
| **Qwen3.5-9B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen3.5-35B-A3B-Instruct | Terminal-Bench | ABL-20 | 5 |
| **Gemma-4-12B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen3.5-35B-A3B-Instruct | SWE-Bench | ABL-30 | 3 |
| **Gemma-4-12B** | SU-full (0.5), TRC+SU (depth invariant) | Qwen3.5-35B-A3B-Instruct | Terminal-Bench | ABL-20 | 5 |

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
