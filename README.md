# agentCtx

Empirical study of context-compression strategies for LLM agents on SWE-bench
Verified. See [CLAUDE.md](CLAUDE.md) for the full project context, vocabulary,
scope rules, and critical conventions — read it before making changes.

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
pip install -e mini-swe-agent          # editable install of the agent harness
# plus the serving/eval stack: vllm, litellm, swebench, pandas, matplotlib, ...
```

> **Heads-up — no pinned dependency manifest yet.** There is currently no
> root `requirements.txt`/`pyproject.toml` capturing the exact versions used.
> The vLLM/CUDA pins in particular are host-specific (see the Albus notes in
> [exp_plans/ALBUS_PLAN.md](exp_plans/ALBUS_PLAN.md)). Generate one from a
> known-good venv with `pip freeze > requirements.txt` and commit it to make
> the environment reproducible.

## Repository layout

| Path | What |
|------|------|
| `memory.py` | Compression primitive functions (truncate, summarize, structured_summarize, tool_result_clear, …). |
| `mini-swe-agent/` | Submodule — agent loop; primitives dispatched in `src/minisweagent/agents/default.py` via `MSWEA_PRIMITIVE`. |
| `scripts/run_experiment.py` | Main run harness. Conditions in the `CONDITIONS` list; `--ablation`, `--budget`, `--tasks-file`, `--conditions`, `--otrc-config`, `--max-workers`. |
| `Review1/` | Analysis suite. `Review1.csv` is the central data file; `build_review1.py` regenerates it from raw trajectories. |
| `task_lists/` | Pinned task JSONs (P100, ablation sets, recovery lists). |
| `exp_plans/` | Per-machine queues (`DOBBY_PLAN.md`, `ALBUS_PLAN.md`) and per-ablation handoff docs. |
| `Active_runs.md` | Live status of long-running experiments — update on launch/kill/completion. |
| `project_runs_checklist.md` | Runs/coverage tracking — read first when planning runs. |

## Data

Experiment outputs (`results/`, `logs/`, figures, raw trajectories) are **not**
in git. See [DATA.md](DATA.md) for what is tracked, how to obtain the raw data,
and how to regenerate `Review1.csv`.

## Running experiments

```bash
source venv/bin/activate
python scripts/run_experiment.py --ablation <name> --budget 15000 \
    --tasks-file task_lists/p100_all_100_tasks.json
```

Data flow: `results/ablations/<exp>/<task>/<condition>/run_<n>/trajectory.json`
→ `Review1/build_review1.py` → `Review1/Review1.csv` → analysis scripts in
`Review1/`.

## Two-machine workflow

Worked across **Dobby** (primary/dev) and **Albus** (8× A6000, model expansion).
Code goes through git; results go through rsync (see [DATA.md](DATA.md)). Sync
at task boundaries — push from the machine you edited on, then pull on the
other. Per-machine queues live in `exp_plans/DOBBY_PLAN.md` and
`exp_plans/ALBUS_PLAN.md`.
