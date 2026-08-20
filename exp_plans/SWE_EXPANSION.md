# Expanding SWE-Bench
Last update: August 20 by Akiho


Experiments env: Dobby (GPU: 4* A100 80GB)

## Expansion 1: Runs/task: 2->3
- ETA: (8-)13 days
- Model: Qwen3.5-35B-A3B-Instruct
- Task: P100 (100 tasks)
- Context budget: 10K, 15K, 20K
- Runs/task : **3 (Additional 1 run/task** mostly)
- Metrics: resolve rate, token cost, latency, compression behavior


| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant | 

## Expansion 2: Add 2 models
- ETA: depending on models
- Model: **TBD**, **TBD**
- Task: P100 (100 tasks)
- Context budget: 10K, 15K, 20K
- Runs/task : 3
- Metrics: resolve rate, token cost, latency, compression behavior

| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant | 

## Expansion 3: # Add ACON
- ETA: 
- Model: Qwen3.5-35B-A3B-Instruct
- Task: 
- Context budget: 10K, 15K, 20K
- Runs/task : 3

| Primitives | Depths | 
|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3 / 0.5 / 0.7 |  
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant | 