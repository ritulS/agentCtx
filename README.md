# agentCtx

Empirical study of context-compression strategies for LLM agents. An agent
(`mini-swe-agent`) runs a tool-use loop on SWE-bench Verified; when trajectory
tokens exceed a budget, a compression primitive fires. We characterize how the
choice of primitive, trigger budget, and compression depth affect resolve rate
and token cost, across models. Terminal-Bench is a second benchmark for
transfer checks.

**Start here, in order:**

1. **[Coverage dashboard]**
   — every run we already have, per model × primitive × budget × depth,
   with gaps highlighted. Regenerable (see [Coverage tracking](#coverage-tracking) below).
2. [CLAUDE.md](CLAUDE.md) — project context, vocabulary (primitive families,
   depths, cohorts), scope rules, critical conventions.
3. [exp_plans/HANDOFF_COHERENCE.md](exp_plans/HANDOFF_COHERENCE.md) — the
   current research direction (ICLR 2027) and week plan.
4. [project_runs_checklist.md](project_runs_checklist.md) — narrative
   run-coverage notes; [Active_runs.md](Active_runs.md) — live experiment status.

## Clone

The agent harness lives in a git submodule, so clone recursively:

```bash
git clone --recurse-submodules git@github.com:ritulS/agentCtx.git
cd agentCtx
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

The submodule (`mini-swe-agent/`) is a fork pinned to branch
`agentctx-customizations` (`github.com/ritulS/mini-swe-agent`). The pinned
branch is recorded in [.gitmodules](.gitmodules), so `update --init` checks out
the right branch automatically.

## Environment

- Python **3.10** (developed on 3.10.12).
- The `venv/` is **not** in git (~11 GB, CUDA/vLLM, machine-specific). Recreate
  it locally.

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # pinned deps + the mini-swe-agent submodule (editable)
```

[requirements.txt](requirements.txt) is a pinned snapshot from the dev venv. The
GPU stack (torch, vllm, triton) is CUDA-coupled and the explicit `nvidia-cuda-*`
pins are intentionally omitted — if your driver/CUDA differs, install torch/vllm
per their platform instructions first, then `pip install -r requirements.txt`.
See the Albus notes in [exp_plans/ALBUS_PLAN.md](exp_plans/ALBUS_PLAN.md) for
host-specific serving caveats.

## Code map

| Path | What |
|------|------|
| `memory.py` | The compression primitives (truncate, summarize, structured_summarize, tool_result_clear, online variants, …). This is the scientific core. |
| `mini-swe-agent/` | Submodule — agent loop; primitives dispatched in `src/minisweagent/agents/default.py` via the `MSWEA_PRIMITIVE` env var. |
| `scripts/run_experiment.py` | Main run harness. Conditions in the `CONDITIONS` list; `--ablation`, `--budget`, `--tasks-file`, `--conditions`, `--otrc-config`, `--max-workers`. |
| `dashboard/build_coverage_sb.py` | Regenerates `COVERAGE.csv` from SWE-Bench experiment results. |
| `dashboard/build_coverage_tb.py` | Regenerates `COVERAGE_TB.csv` from Terminal-Bench experiment results. |
| `dashboard/build_dashboard.py` | Renders `DASHBOARD.html` from the coverage CSVs. |
| `scripts/run_experiment.py`, `scripts/bench_adapters/` | Unified SWE-Bench/Terminal-Bench orchestrator and benchmark adapters. |
| `configs/` | Per-model vLLM/agent configs (`config-qwen-vllm.yaml` is the main model). |
| `Review1/` | Analysis suite. `build_review1.py` distills raw trajectories into `Review1.csv`; the other scripts produce stats, tables, figures. |
| `task_lists/` | Pinned task JSONs — `p100_all_100_tasks.json` (P100), `ablation_30tasks.json` (ABL-30), tbench sets. |
| `exp_plans/` | Per-machine queues (`DOBBY_PLAN.md`, `ALBUS_PLAN.md`), the current handoff, prior-work scan. |

## Data

**All collected run data lives in one gitignored folder: `data/`** (~10 GB).
[data/README.md](data/README.md) is the provenance map — canonical grid vs
source runs vs retired legacy runs. Key facts:

- `data/swebench/ablations/` is the canonical grid:
  `<exp>/<task>/<condition>/run_<n>/trajectory.json`.
- `results/ablations`, `results/tbench`, and `Review1/raw` are compatibility
  symlinks into `data/`, so all older script paths still work.
- `Review1/Review1.csv` (git-tracked) is the canonical distilled table for the
  main model. Do not mix `data/swebench/legacy/` or `early_2026-03/` into new
  analysis.
- Data moves between machines with rsync, never git — see [DATA.md](DATA.md).

Data flow: `results/ablations/<exp>/<task>/<condition>/run_<n>/trajectory.json`
→ `Review1/build_review1.py` → `Review1/Review1.csv` → analysis scripts in
`Review1/`.

## Coverage tracking

Three generated artifacts keep "what runs exist" honest — they are derived from
disk, never hand-edited:

- **`COVERAGE.csv`** (git-tracked) — SWE-Bench coverage, with one row per
  (model, primitive, budget, depth) cell that has actual data.
- **`COVERAGE_TB.csv`** (git-tracked on the Terminal-Bench data branch) — the
  equivalent Terminal-Bench coverage, including fixed P-15/P-40 cohort counts.
  Both CSVs record scope, status, tasks/runs on disk, and source directories.
- **`DASHBOARD.html`** (gitignored, regenerable) — the human-friendly view,
  published at
  **https://claude.ai/code/artifact/5952fe5d-6a12-4ae4-b9b2-0032b7e11fc0**.
  Solid chips = full 100-task cohort; outlined = ABL-30 only; one section per
  benchmark.

After any run completes (or `Review1.csv` is rebuilt):

```bash
python dashboard/build_coverage_sb.py
python dashboard/build_coverage_tb.py
python dashboard/build_dashboard.py
```

`dashboard/watch.py` runs the same three steps periodically. To publish the
combined dashboard data branch, use `python dashboard/publish.py`; the publisher
builds SWE-Bench coverage locally and fetches Terminal-Bench coverage from its
dedicated data branch.

## Running experiments

```bash
source venv/bin/activate
python scripts/run_experiment.py --ablation <name> --budget 15000 \
    --tasks-file task_lists/p100_all_100_tasks.json
```

Update `Active_runs.md` on every launch/kill/completion.

## Two-machine workflow

Worked across **Dobby** (primary/dev) and **Albus** (8× A6000, model expansion).
Code goes through git; results go through rsync (see [DATA.md](DATA.md)). Sync
at task boundaries — push from the machine you edited on, then pull on the
other. Per-machine queues live in `exp_plans/DOBBY_PLAN.md` and
`exp_plans/ALBUS_PLAN.md`.
