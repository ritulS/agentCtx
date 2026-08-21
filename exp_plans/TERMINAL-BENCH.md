# Terminal-Bench
Last update: August 21 by Akiho


Experiments env: **Dobby (GPU: 4× A100 80GB)**

## [Priority] Terminal-Bench Evaluation
- ETA: 
    | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
    |---|---|---|---|
    | Ablation depths runs | Full (89 tasks) | **ABL-20 (20 tasks)** | TBD |
    | Full depth runs | Full (89 tasks) | **Full (89 tasks)** | TBD |

- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : 5
- Task: Terminal-Bench 2.0 Full (89 tasks)
- Metrics: accuracy, token cost, latency, compression behavior


| Primitives | Depths | Budget | Tasks | Runs | Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5 | Full (89 tasks)|10K / 15K / 20K | 6675 ||
| TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | ABL-20 (20 tasks) |10K / 15K / 20K | 3000 |Ablation depths runs|
| TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | Full (89 tasks)|10K / 15K / 20K | 13350 |Full depth runs|
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant |10K / 15K / 20K | Full (89 tasks)| 8010 ||
| FC, OTRC | depth invariant | ∞ | Full (89 tasks)| 890 ||
