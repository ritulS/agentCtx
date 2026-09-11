# ICLR experiment grid

Last update: 2026-09-11. Sources: `exp_plans/FOLLOWUP_EXPERIMENTS.md`, `COVERAGE.csv`.
Status: Done = finished · In progress = started, not finished · blank = not started.
Runs/task = 3 everywhere except the TB summarizer ablation (5).
Priority: 1 SWE main → 2 SWE ablation → 3 summarizer ablation → 4 TB main → 5 TB ablation.

| Benchmark | Section | Model (agent) | Summarizer | Cohort | Budget | Depth | Primitives | Status | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWE-bench | main | Qwen3.5-35B-A3B | self | P100 | ∞ | 0.5 | FC, OTRC | Done | 1 |
| SWE-bench | main | Qwen3.5-35B-A3B | self | P100 | 15K | 0.5 | DT + DI | Done | 1 |
| SWE-bench | ablation | Qwen3.5-35B-A3B | self | ABL-25 | 10K / 20K | 0.5 | DT + DI | In progress | 2 |
| SWE-bench | ablation | Qwen3.5-35B-A3B | self | ABL-25 | 10K / 15K / 20K | 0.3 / 0.7 | DT | In progress | 2 |
| SWE-bench | main | Devstral-Small-2-24B | self | P100 | ∞ | 0.5 | FC, OTRC | Done | 1 |
| SWE-bench | main | Devstral-Small-2-24B | self | P100 | 21K | 0.5 | DT + DI | Done | 1 |
| SWE-bench | ablation | Devstral-Small-2-24B | self | ABL-25 | 17K / 24K | 0.5 | DT + DI | In progress | 2 |
| SWE-bench | ablation | Devstral-Small-2-24B | self | ABL-25 | 17K / 21K / 24K | 0.3 / 0.7 | DT | In progress | 2 |
| SWE-bench | main | GLM-4.7-Flash | self | P100 | ∞ | 0.5 | FC, OTRC | In progress | 1 |
| SWE-bench | main | GLM-4.7-Flash | self | P100 | 13K | 0.5 | DT + DI | In progress | 1 |
| SWE-bench | ablation | GLM-4.7-Flash | self | ABL-25 | 10K / 15K | 0.5 | DT + DI |  | 2 |
| SWE-bench | ablation | GLM-4.7-Flash | self | ABL-25 | 10K / 13K / 15K | 0.3 / 0.7 | DT |  | 2 |
| Terminal-Bench | main | Qwen3.5-35B-A3B | self | P40 | ∞ | 0.5 | FC, OTRC | Done | 4 |
| Terminal-Bench | main | Qwen3.5-35B-A3B | self | P40 | 3K | 0.5 | DT + DI | Done | 4 |
| Terminal-Bench | ablation | Qwen3.5-35B-A3B | self | ABL-15 | 2K / 4K | 0.5 | DT + DI | In progress | 5 |
| Terminal-Bench | ablation | Qwen3.5-35B-A3B | self | ABL-15 | 2K / 3K / 4K | 0.3 / 0.7 | DT |  | 5 |
| Terminal-Bench | main | Devstral-Small-2-24B | self | P40 | ∞ | 0.5 | FC, OTRC | Done | 4 |
| Terminal-Bench | main | Devstral-Small-2-24B | self | P40 | 4K | 0.5 | DT + DI | Done | 4 |
| Terminal-Bench | ablation | Devstral-Small-2-24B | self | ABL-15 | 3K / 7K | 0.5 | DT + DI |  | 5 |
| Terminal-Bench | ablation | Devstral-Small-2-24B | self | ABL-15 | 3K / 4K / 7K | 0.3 / 0.7 | DT |  | 5 |
| Terminal-Bench | main | GLM-4.7-Flash | self | P40 | ∞ | 0.5 | FC, OTRC | In progress | 4 |
| Terminal-Bench | main | GLM-4.7-Flash | self | P40 | 3K | 0.5 | DT + DI | In progress | 4 |
| Terminal-Bench | ablation | GLM-4.7-Flash | self | ABL-15 | 2K / 5K | 0.5 | DT + DI |  | 5 |
| Terminal-Bench | ablation | GLM-4.7-Flash | self | ABL-15 | 2K / 3K / 5K | 0.3 / 0.7 | DT |  | 5 |
| SWE-bench | summarizer | Qwen3.5-35B-A3B | Qwen3.5-9B | ABL-25 | 15K | 0.5 | SU-full, TRC+SU |  | 3 |
| Terminal-Bench | summarizer | Qwen3.5-35B-A3B | Qwen3.5-9B | ABL-20 | 3K | 0.5 | SU-full, TRC+SU |  | 3 |
| SWE-bench | summarizer | Qwen3.5-35B-A3B | Gemma-4-12B | ABL-25 | 15K | 0.5 | SU-full, TRC+SU |  | 3 |
| Terminal-Bench | summarizer | Qwen3.5-35B-A3B | Gemma-4-12B | ABL-20 | 3K | 0.5 | SU-full, TRC+SU |  | 3 |

Notes

- Primitive groups
  - DT (depth-tunable): TR, SU-full, SU-partial, SS, SS-partial
  - DI (depth-invariant, no depth parameter): TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial
- Cohorts
  - SWE-bench
    - P100 = `task_lists/p100_all_100_tasks.json` (100 tasks)
    - ABL-25 = `task_lists/ablation_25tasks.json` (25 ⊂ P100)
  - Terminal-Bench
    - P40 = `task_lists/tbench_p40.json` (40 tasks)
    - ABL-20 (summarizer ablation) = TBD (20 ⊂ P40)
    - ABL-15 = `task_lists/tbench_abl15.json` (15 ⊂ ABL-20 ⊂ P40)
- Results: `ICLR_results/<bench>/{main,ablation}/<model>/<cell>`.
