# Expanding SWE-Bench
Last update: August 20 by Akiho

## Expansion 1: # Runs/task: 2->3
### 1.1 Motivation
Increasing to 3 runs/task gives a more accurate estimate of each task's resolve rate.

### 1.2 Scope
- Runs/task : 3 runs/task for every cell below (existing runs auto-skipped).
- Context budget: 10K, 15K, 20K
- Model: Qwen3.5-35B-A3B-Instruct


| Group | Primitives | Depths | Cohort by budget |
|---|---|---|---|
| depth-tunable (5) | TR*, SU-full*, SU-partial*, SS*, SS-partial* | 0.3 / 0.5 / 0.7 | P100 (100 tasks) @15k; ABL-30 (30 tasks) @10k, 20k |
| depth-invariant + FC + OTRC (8) | TRC, TRC+SU, TRC+SS, OTRC+TR, OTRC+SU-partial, OTRC+SS-partial, FC, OTRC | (0.5 only) | P100 (100 tasks), all budgets |



### 1.3 Experiments Environment
Dobby
- GPU: 4 * Nvidia A100 80GB HBM-2e PCI-E
- CPU: AMD EPYC 9554P 64-Core Processor

## Expansion 2: # Model: 1 -> 3

