# Terminal-Bench
Last update: August 20 by Akiho


Experiments env: Dobby (GPU: 4* A100 80GB)

## [Priority] Terminal-Bench Evaluation
- ETA: **TBD**
- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : 5
- Task: Terminal-Bench 2.0 Full (89 tasks)
- Metrics: accuracy, token cost, latency, compression behavior


| Primitives | Depths | Budget | Runs |
|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.5/0.7  |10K / 15K / 20K | 20025 |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant |10K / 15K / 20K | 8010 |
| FC, OTRC | depth invariant | ∞ | 890 |
