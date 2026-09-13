# agentCtx

Empirical study of context-compression strategies for LLM agents. An agent
(`mini-swe-agent`) runs a tool-use loop on SWE-bench Verified; when trajectory
tokens exceed a budget, a compression primitive fires. We characterize how the
choice of primitive, trigger budget, and compression depth affect resolve rate
and token cost, across models. Terminal-Bench is a second benchmark for
transfer checks.

**Start here, in order:**

1. **Coverage dashboard** (`DASHBOARD.html`, gitignored) — every run we
   already have, per model × primitive × budget × depth, with gaps
   highlighted. Regenerable (see [Coverage tracking](#coverage-tracking)).
2. [CLAUDE.md](CLAUDE.md) — project context, vocabulary (primitive families,
   depths, cohorts), scope rules, critical conventions.
3. [ICLR.md](ICLR.md) — the current target (ICLR 2027), the framing of
   record, and the source of truth for every topic.
4. [ICLR_analysis/exp_grid.md](ICLR_analysis/exp_grid.md) — the experiment
   grid and its status; [Active_runs.md](Active_runs.md) — live experiment
   status.

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
Per-model serving configs live in [configs/](configs/).

## Code map

| Path | What |
|------|------|
| `memory.py` | The compression primitives (truncate, summarize, structured_summarize, tool_result_clear, online variants, …). This is the scientific core. |
| `mini-swe-agent/` | Submodule — agent loop; primitives dispatched in `src/minisweagent/agents/default.py` via the `MSWEA_PRIMITIVE` env var. |
| `scripts/run_experiment.py` | Main run harness. Conditions in the `CONDITIONS` list; `--ablation`, `--budget`, `--tasks-file`, `--conditions`, `--otrc-config`, `--max-workers`. |
| `dashboard/build_coverage.py` | Regenerates the coverage CSVs from experiment results. |
| `dashboard/build_dashboard.py` | Renders `DASHBOARD.html` from the coverage CSVs. |
| `scripts/run_experiment_iclr.py` | Wraps the harness to write into the canonical `ICLR_results/` tree. |
| `scripts/bench_adapters/`, `tbench/` | Per-benchmark adapters, including the Terminal-Bench harbor adapter. |
| `configs/` | Per-model vLLM/agent configs (`config-qwen-vllm.yaml` is the main model). |
| `Review1/` | Analysis suite. `build_review1.py` distills raw trajectories into `Review1.csv`; the other scripts produce stats, tables, figures. |
| `task_lists/` | Pinned task JSONs — `p100_all_100_tasks.json` (P100), `ablation_25tasks.json` (ABL-25), `ablation_30tasks.json` (older ABL-30), tbench sets. |
| `exp_plans/` | Current experiment queue (`FOLLOWUP_EXPERIMENTS.md`); retired plans in `archived/`. |
| `ICLR_results/`, `ICLR_analysis/`, `analysis/` | Canonical ICLR run data, the experiment grid, and per-run outcome aggregation. |

## Data

**ICLR run data is canonical in `ICLR_results/`**, one directory per cell,
laid out as `<bench>/<track>/<model>/<cell>/`. The populated tree lives in
Akiho's clone (`/home/ak58925/agentCtx/ICLR_results/`) and is symlinked into
this one. It never travels through git. See [ICLR.md](ICLR.md) for the full
source-of-truth table, and `ICLR_results/README.md` for the cell naming.

Data flow: `ICLR_results/<bench>/<track>/<model>/<cell>/`
→ `analysis/aggregate_benchmark_results.py` → `analysis/outcomes/<bench>_outcomes.csv`
→ analysis in `ICLR_analysis/`.

Terminal-Bench runs on Albus; its results are not here. See the Terminal-Bench
section of [ICLR.md](ICLR.md).

**Older (EMNLP-era) data lives in `data/`** (~10 GB, gitignored).
`data/README.md` is its provenance map — canonical grid vs source runs vs
retired legacy runs. It backs the `Review1/` suite, not the ICLR analysis.

- `data/swebench/ablations/`:
  `<exp>/<task>/<condition>/run_<n>/trajectory.json`.
- `results/ablations`, `results/tbench`, and `Review1/raw` are compatibility
  symlinks into `data/`, so all older script paths still work.
- `Review1/Review1.csv` (git-tracked) is the distilled table for that older
  grid. Do not mix `data/swebench/legacy/` or `early_2026-03/` into new
  analysis.
- Data moves between machines with rsync, never git — see [DATA.md](DATA.md).

## Coverage tracking

Two generated artifacts keep "what runs exist" honest — they are derived from
disk, never hand-edited:

- **`COVERAGE.csv`** (git-tracked) — one row per (benchmark, model, primitive,
  budget, depth) cell that has actual data: scope, status, tasks/runs on disk,
  and CSV ingest state. Dirty/archived experiment data is intentionally
  excluded. **The committed copy is stale** (2026-08-28, no Devstral or GLM
  rows), so regenerate before relying on it. `COVERAGE_TB.csv` is header-only
  here because Terminal-Bench runs on another machine — see
  [ICLR.md](ICLR.md).
- **`DASHBOARD.html`** (gitignored, regenerable) — the human-friendly view.
  The live copy is published by GitHub Actions on a cron; see
  `dashboard/README.md` for the URL and the publishing pipeline.
  Solid chips = full 100-task cohort; outlined = ablation cohort only; one
  section per benchmark. The chip labels and CSV columns still say `abl30`,
  which predates the move to ABL-25.

After any run completes:

```bash
python dashboard/build_coverage.py && python dashboard/build_dashboard.py
```

then republish the dashboard to keep the link current.

## Running experiments

```bash
source venv/bin/activate
python scripts/run_experiment.py --ablation <name> --budget 15000 \
    --tasks-file task_lists/p100_all_100_tasks.json
```

Update `Active_runs.md` on every launch/kill/completion.

## Two-clone workflow

SWE-bench runs on **Dobby** (4× A100 80GB); Terminal-Bench runs on **Albus**
(8× A6000). Two clones share Dobby — Ritul's (`/home/rs67788/projects/agentCtx`, paper and analysis)
and Akiho's (`/home/ak58925/agentCtx`, experiment runs and the canonical
`ICLR_results/` tree). Code goes through git on `akiho-expansion`; run data
stays on disk (see [DATA.md](DATA.md)). Pull before starting and push at task
boundaries.
