# agentCtx — E1 Experiment: Context-Window Compression on SWE-bench

Measures the effect of token-budget constraints on mini-swe-agent's resolve rate
and work amplification factor (WAF) across 30 SWE-bench Lite tasks (10 per repo,
3 repos: Flask · Django · SymPy) using two memory primitives: truncation and summarization.

---

## Repository layout

```
agentCtx/
├── mini-swe-agent/          # git submodule — SWE-agent/mini-swe-agent @ e68906f
├── memory.py                # truncation + summarization primitives (hook target)
├── configs/config-qwen-vllm.yaml    # agent config pointing to local vLLM server
├── setup.sh                 # one-shot setup script (submodule + patch + venv)
├── patches/
│   └── default_memory_hook.patch   # patch applied to mini-swe-agent/default.py
├── scripts/
│   ├── select_tasks.py      # select 30 tasks from SWE-bench Lite
│   ├── run_experiment.py    # main E1 runner (two-phase: baseline → compressed)
│   ├── analyze_results.py   # CLI analysis of experiment_results.json
│   ├── check_progress.py    # live progress monitor
│   └── plot_e1.py           # generate Figure 1 + Figure 2
├── selected_tasks.json      # 30 selected tasks (committed)
├── results/                 # experiment output (gitignored, except .gitkeep)
├── figures/e1/              # saved plots (gitignored)
└── logs/                    # vLLM server logs (gitignored)
```

---

## Quick start on a new machine

### Prerequisites
- Python 3.10+
- Git with submodule support
- A running vLLM server serving `Qwen/Qwen2.5-Coder-72B-Instruct` on port 8000
- SWE-bench evaluation environment (see *SWE-bench setup* below)

### 1. Clone and set up

```bash
git clone --recurse-submodules https://github.com/ritulS/agentCtx.git
cd agentCtx
bash setup.sh          # creates venv/, applies patch to mini-swe-agent/default.py
source venv/bin/activate
```

`setup.sh` does three things:
1. Initialises/updates the `mini-swe-agent` submodule
2. Applies `patches/default_memory_hook.patch` to `mini-swe-agent/src/minisweagent/agents/default.py`
   (adds the `MSWEA_TOKEN_BUDGET` / `MSWEA_PRIMITIVE` hook into `DefaultAgent.query()`)
3. Creates `venv/` and installs `mini-swe-agent[all]` + `litellm`

Re-applying the patch only (e.g. after a submodule update):
```bash
bash setup.sh --patch
```

### 2. Start the vLLM server

```bash
screen -dmS vllm-server bash -c \
  "vllm serve Qwen/Qwen2.5-Coder-72B-Instruct \
     --port 8000 --dtype auto --max-model-len 32768 \
     2>&1 | tee logs/vllm-server.log"

# Verify:
curl -s http://localhost:8000/health
```

### 3. (Optional) Re-select tasks

`selected_tasks.json` is already committed. Only re-run if you want different tasks:

```bash
source venv/bin/activate
python scripts/select_tasks.py    # requires: pip install datasets
```

### 4. Run the E1 experiment

```bash
source venv/bin/activate
python scripts/run_experiment.py
```

Monitor progress in another terminal:
```bash
watch -n 60 python scripts/check_progress.py
```

### 5. Analyse results

```bash
python scripts/analyze_results.py           # summary tables + WAF
python scripts/plot_e1.py                   # saves figures/e1/fig1_*.png + fig2_*.png
```

---

## Experiment design

| Parameter | Value |
|---|---|
| Repos | pallets/flask, django/django, sympy/sympy |
| Tasks per repo | 10 (evenly spaced by problem-statement word count) |
| Runs per task×budget×primitive | 3 |
| Memory primitives | truncation, summarization |
| Budget levels | 100% (baseline), 90%, 75%, 60%, 50%, 40%, 30%, 25% |
| Compression ratio *r* | 0.5 (fire → compress to budget × 0.5) |
| Model | Qwen/Qwen2.5-Coder-72B-Instruct |
| Total agent runs | 30 × 2 × 8 × 3 = **1 440** |

**Two-phase budget design**

Phase 0 (baseline): all tasks run at 100% budget (no compression), recording actual
prompt token counts per task.

Phase 2 (compressed): absolute token budgets are derived as
`budget_abs = mean_baseline_prompt_tokens × budget_pct` per task.  This ensures
"40%" means 40% of *that specific task's* real context usage.

---

## Memory hook

`memory.py` (repo root) provides:

| Symbol | Purpose |
|---|---|
| `count_tokens(messages)` | char/4 heuristic token counter |
| `truncate(messages, target)` | drops messages from front of compressible window until ≤ target |
| `summarize(messages, model, target)` | one LLM call; returns `(new_messages, saved, pt, ct)` |
| `write_token_log(agent)` | writes JSON token log to `MSWEA_TOKEN_LOG_PATH` |
| `COMPRESSION_RATIO` | 0.5 |

The hook in `default.py` fires *before* each LLM call:
```
if raw_tokens > MSWEA_TOKEN_BUDGET:
    target = budget * COMPRESSION_RATIO
    apply primitive → update accumulators
```

---

## SWE-bench evaluation (UT Austin server)

The SWE-bench harness runs in a separate venv (`~/waf_experiment`) using Podman
as the container runtime (no sudo).

```bash
source ~/waf_experiment/bin/activate
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
python -m swebench.harness.run_evaluation \
  --predictions_path results/experiment_results.json \
  --max_workers 1 \
  --run_id e1_eval
```

**Known issues on this machine:**
- Domain UID causes `lchown` EINVAL in `put_archive` → patched in
  `~/waf_experiment/lib/python3.10/site-packages/swebench/harness/docker_utils.py`
  (uses `base64+exec_run` instead).
- Podman socket must be running (auto-started by `~/.bashrc`).
  Manual: `podman system service --time=0 unix:///run/user/$(id -u)/podman/podman.sock &`

---

## Output files

| Path | Description |
|---|---|
| `results/experiment_results.json` | Primary results file — one record per agent run (see schema below) |
| `results/experiment_results.csv`  | Same records as CSV |
| `results/<iid>/<primitive>/<pct>/run_<n>/trajectory.json` | Full mini-swe-agent trajectory |
| `results/<iid>/<primitive>/<pct>/run_<n>/token_log.json`  | Per-run token accounting (see schema below) |
| `results/<iid>/<primitive>/<pct>/run_<n>/agent.log`       | Raw stdout/stderr from the agent subprocess |
| `figures/e1/fig1_metric_divergence.png` | Figure 1: dual-axis resolve rate + WAF vs budget |
| `figures/e1/fig2_success_vs_calls.png`  | Figure 2: per-task success/calls scatter at 100% and 40% |

---

## Log schemas and metrics

### Run record (`results/experiment_results.json`)

The results file is a JSON array — one object per agent run.  Fields are grouped
below by concern.

**Identity**

| Field | Type | Description |
|---|---|---|
| `key` | string | Unique run ID, e.g. `pallets__flask-4045__truncation__p040__r2` |
| `instance_id` | string | SWE-bench Lite instance, e.g. `pallets__flask-4045` |
| `primitive` | string | Memory primitive used: `truncation` or `summarization` |
| `budget_pct` | float | Budget as a fraction of the task's full-context token count (primary budget field). `1.0` = unconstrained baseline |
| `budget_abs` | int | Absolute token threshold passed to the agent. Equal to `mean_baseline_tokens × budget_pct`. Sentinel value `999999` for baseline runs |
| `is_baseline` | bool | `true` when `budget_pct == 1.00` |
| `run_num` | int | Repetition index, 1–3 |
| `timestamp` | string | ISO-8601 datetime when the run completed |

**Process**

| Field | Type | Description |
|---|---|---|
| `returncode` | int | Subprocess exit code. `0` = clean exit, `-1` = timeout killed |
| `e2e_latency_s` | float | Wall-clock seconds from subprocess launch to completion |

**Agent metrics** *(parsed from `trajectory.json → info`)*

| Field | Type | Description |
|---|---|---|
| `n_calls` | int | Total LLM API calls the agent made |
| `exit_status` | string | mini-swe-agent exit reason, e.g. `submit`, `step_limit` |
| `patch_generated` | bool | `true` if the agent produced a non-empty diff |
| `submission` | string | Raw unified diff string (empty if no patch) |

**Evaluation** *(populated by Phase 3 — SWE-bench harness)*

| Field | Type | Description |
|---|---|---|
| `resolved` | bool \| null | `true` = tests pass, `false` = tests fail, `null` = not yet evaluated |

**Token accounting** *(merged from `token_log.json`, written by `memory.py`)*

| Field | Type | Description |
|---|---|---|
| `total_prompt_tokens` | int | Sum of prompt tokens across every agent LLM call. For summarization runs this includes tokens used by the summarization call itself |
| `total_completion_tokens` | int | Sum of completion tokens across every agent LLM call |
| `total_tokens` | int | `total_prompt_tokens + total_completion_tokens` |
| `llm_latency_s` | float | Total wall-clock seconds spent waiting for LLM responses |
| `mean_latency_s` | float | `llm_latency_s / n_calls` |

**Compression metrics** *(zero for baseline runs)*

| Field | Type | Description |
|---|---|---|
| `compression_events` | int | Number of times the primitive fired (budget threshold crossed) |
| `total_tokens_saved` | int | Estimated tokens removed across all compression events, sum of `(tokens_before − tokens_after)` per event |
| `mean_compression_ratio` | float | Mean of `tokens_after / tokens_before` per event. Values below 1.0 mean the context shrank; `1.0` if no compression occurred |

**Derived metrics used in analysis**

| Metric | How it is computed |
|---|---|
| Resolve Rate (RR) | `mean(resolved == True)` over all runs in a `(primitive, budget_pct)` cell |
| WAF (Work Amplification Factor) | `mean_calls(budget_pct) / mean_calls(budget_pct=1.0)` — computed per task, then averaged. WAF > 1 means the agent needed more steps under compression |
| CIR onset | The lowest `budget_pct` at which RR drops more than 5% below the baseline RR for any primitive |

---

### Token log (`token_log.json`)

Sits alongside `trajectory.json` and `agent.log` inside each run directory.
Written and overwritten after every agent step by `memory.write_token_log(agent)`,
so the on-disk file always reflects the complete run when the agent exits.

| Field | Description |
|---|---|
| `total_prompt_tokens` | Cumulative prompt tokens (all agent LLM calls, including any summarization calls) |
| `total_completion_tokens` | Cumulative completion tokens |
| `total_tokens` | Sum of the two above |
| `total_latency_s` | Wall-clock seconds waiting for LLM responses |
| `mean_latency_s` | `total_latency_s / number_of_calls` |
| `compression_events` | Times the memory primitive fired |
| `total_tokens_saved` | Cumulative tokens removed by compression |
| `mean_compression_ratio` | Mean `tokens_after / tokens_before` per compression event; `1.0` if none |

---

### Trajectory (`trajectory.json`)

Standard mini-swe-agent output file.  The harness reads only three fields:

| Path in JSON | Maps to |
|---|---|
| `info.model_stats.api_calls` | `n_calls` |
| `info.exit_status` | `exit_status` |
| `info.submission` | `submission` / `patch_generated` |

The rest of the file contains the full message history and step-by-step
action/observation pairs — useful for manual inspection but not consumed by
the analysis scripts.

---

## Environment variables (memory hook)

Set by `run_experiment.py` for each agent subprocess:

| Variable | Example value | Purpose |
|---|---|---|
| `MSWEA_PRIMITIVE` | `truncation` | Which primitive fires when the budget is exceeded |
| `MSWEA_TOKEN_BUDGET` | `12480` | Absolute token threshold. `999999` = baseline (no compression) |
| `MSWEA_TOKEN_LOG_PATH` | `results/.../token_log.json` | Where `memory.write_token_log()` writes |
| `PYTHONPATH` | `/home/.../agentCtx:…` | Prepended so `import memory` resolves from the repo root |
| `DOCKER_HOST` | `unix:///run/user/…/podman.sock` | Podman socket for SWE-bench container runtime |
