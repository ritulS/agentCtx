# Terminal-Bench
Last update: August 21 by Akiho


Experiments env: **Dobby (GPU: 4× A100 80GB)**

## [Priority③] Terminal-Bench Evaluation
- ETA: 
    | Status | Option | Depth 0.5 | Depth 0.3 / 0.7 | ETA |
    |---|---|---|---|---|
    | **Selected** | **Ablation-depth runs** | Full (80 tasks) | **ABL-20 (20 tasks)** | TBD |
    | Not selected | Full-depth runs | Full (80 tasks) | Full (80 tasks) | TBD |

- Model (agent & summarizer): Qwen3.5-35B-A3B-Instruct
- Runs/task : 5
- Task: Terminal-Bench 1.0 Full (80 tasks)
- Metrics: accuracy, token cost, latency, compression behavior


| Primitives | Depths | Budget | Tasks | Runs | Notes|
|---|---|---|---|---|---|
| TR, SU-full, SU-partial, SS, SS-partial | 0.5 | Full (80 tasks)|10K / 15K / 20K | 6000 ||
| TR, SU-full, SU-partial, SS, SS-partial | **0.3/0.7** | **ABL-20 (20 tasks)** | 10K / 15K / 20K | **3000** | **Selected: ablation-depth runs** |
| TR, SU-full, SU-partial, SS, SS-partial | 0.3/0.7 | Full (80 tasks)|10K / 15K / 20K | 12000 | Not selected: full-depth alternative |
| TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | depth invariant |10K / 15K / 20K | Full (80 tasks)| 7200 ||
| FC, OTRC | depth invariant | ∞ | Full (80 tasks)| 800 ||
