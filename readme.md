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
├── config-qwen-vllm.yaml    # agent config pointing to local vLLM server
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
| `results/experiment_results.json` | All run records (budget_pct, patch_generated, resolved, n_calls, …) |
| `results/experiment_results.csv`  | Same as CSV |
| `logs/<run_key>/token_log.json`   | Per-run token accounting from memory hook |
| `figures/e1/fig1_metric_divergence.png` | Figure 1: dual-axis resolve rate + WAF vs budget |
| `figures/e1/fig2_success_vs_calls.png`  | Figure 2: per-task success/calls scatter at 100% and 40% |
