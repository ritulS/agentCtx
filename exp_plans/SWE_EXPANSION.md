# Expanding SWE-Bench
Last update: August 21 by Akiho


Experiments env: **Dobby (GPU: 4× A100 80GB)**

## 1. [Priority] Runs/task: 2->3
- ETA

  | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
  |---|---|---|---|
  | Ablation depths runs | P100 (100 tasks) | **ABL-30 (30 tasks)** | **3–5 days** |
  | Full depth runs | P100 (100 tasks) | **P100 (100 tasks)** | **7-11 days** |

- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : **3 (Additional 1 run/task** mostly)
- Metrics: resolve rate, token cost, latency, compression behavior


| Primitives | Depths | Budget |Task |Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 1500 ||
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  ABL-30 (30 tasks) | 900|Ablation depths runs|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  **P100 (100 tasks)** | 5800 |Full depth runs|
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 1800 ||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 200 ||

## 2. [Priority] Add 2 models
- ETA: TBD
  - Devstral-Small-2-24B: **10 days** 
    - Skip existing [Budget: 15K, Depth: 0.5, Task: ABL-30]

      | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
      |---|---|---|---|
      | **Ablation depths runs** | P100 (100 tasks) | **ABL-30 (30 tasks)** | **10 days**  |
      | **Full depth runs** | P100 (100 tasks) | **P100 (100 tasks)** | **15 days** |


  - GLM-4.7-Flash: TBD
- Model (agent & summarizer): **Devstral-Small-2-24B**, **GLM-4.7-Flash** (30B-A3B MoE)
- Runs/task : 3
- Metrics: resolve rate, token cost, latency, compression behavior


**Devstral-Small-2-24B**
| Primitives | Depths | Budget |Task | Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 4200 ||
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  ABL-30 (30 tasks)|  2100 |Ablation depths runs|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  **P100 (100 tasks)**|  8400 |Full depths runs|
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 5040||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 480 ||

**GLM-4.7-Flash**
| Primitives | Depths | Budget |Task | Runs |Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) | 4500 ||
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  ABL-30 (30 tasks)|  2700 |Ablation depths runs|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  **P100 (100 tasks)**|  9000 |Full depths runs|
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 5400 ||
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 600 |

## 3. Add [ACON](https://arxiv.org/abs/2510.00615)
- ETA: TBD
- Model (agent & judge/optimizer): Qwen3.5-35B-A3B-Instruct 
  - judge/optimizer for the offline summary-guideline optimization loop
- New primitive: `ACON`
  - Need a subset data for the offline summary-guideline optimization (size: **TBD**, around 30)
  - 'preserve_last_k_turns': 1 (default value in original)

| Primitives | Depth | Budget | Task | Runs |
|---|---|---|---|---|
| ACON | N/A (no depth param) | **TBD** |P100 (100 tasks) | 300 |
