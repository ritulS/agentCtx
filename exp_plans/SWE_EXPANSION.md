# Expanding SWE-Bench
Last update: August 20 by Akiho


Experiments env: Dobby (GPU: 4* A100 80GB)

## 1. [Priority] Runs/task: 2->3
- ETA: **3-5 days**
- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : **3 (Additional 1 run/task** mostly)
- Metrics: resolve rate, token cost, latency, compression behavior


| Primitives | Depths | Budget |Task |
|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  ABL-30 (30 tasks) |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 

## 2. [Priority] Add 2 models
- ETA: TBD
  - Devstral-Small-2-24B: **10 days** (Skip existing ones (15K, depth 0.5, ABL-30))
  - GLM-4.7-Flash: TBD
- Model (agent & summarizer): **Devstral-Small-2-24B, GLM-4.7-Flash**
- Runs/task : 3
- Metrics: resolve rate, token cost, latency, compression behavior

| Primitives | Depths | Budget |Task |
|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5  |10K / 15K / 20K | P100 (100 tasks) |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.7 |10K / 15K / 20K |  ABL-30 (30 tasks) |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial | depth invariant |10K / 15K / 20K | P100 (100 tasks) | 
| FC, OTRC | depth invariant | ∞ | P100 (100 tasks) | 

## 3. Add ACON
- ETA: TBD
- Model (agent & judge/optimizer): Qwen3.5-35B-A3B-Instruct 
  - judge/optimizer for the offline summary template optimization loop
- New primitive: `ACON`
  - Need a subset of the data for the offline summary-template optimization loop (size: TBD, around 30)

| Primitives | Depth | Task cohort | Budget |
|---|---|---|---|
| ACON | N/A (no depth param) | P100 (100 tasks) | TBD |
