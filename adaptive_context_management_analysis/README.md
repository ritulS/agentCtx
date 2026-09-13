# adaptive_context_management_analysis

Scripts that mechanically classify the "termination type (trigger)" of failed runs
from `analysis/outcomes/swebench_outcomes.csv` and each run's `agent.log` /
`trajectory.json`.

## classify_failure_causes.py

```bash
# Failed runs for Qwen3.5-35B / full-context / difficulty "<15 min fix"
python3 adaptive_context_management_analysis/classify_failure_causes.py \
    --model qwen35b --primitive fc --difficulty u15

# Ablation TR@15k depth 0.5, ABL-25 only, run 1 only, including resolved runs
python3 adaptive_context_management_analysis/classify_failure_causes.py \
    --model qwen35b --primitive tr --budget 15000 --depth 0.5 --cohort abl25 --run 1 --include-resolved

# Failed runs across all models and all cells (no arguments -> results/all/)
python3 adaptive_context_management_analysis/classify_failure_causes.py
```

<details>
<summary>Example: Qwen3.5-35B full-context, split by difficulty</summary>

```bash
S=adaptive_context_management_analysis/classify_failure_causes.py

python3 $S --model qwen35b --primitive fc                      # all Qwen FC runs (153 runs)
python3 $S --model qwen35b --primitive fc --difficulty u15     # <15 min fix        (33 runs)
python3 $S --model qwen35b --primitive fc --difficulty 15m1h   # 15 min - 1 hour    (93 runs)
python3 $S --model qwen35b --primitive fc --difficulty 1to4h   # 1-4 hours          (24 runs)
python3 $S --model qwen35b --primitive fc --difficulty gt4h    # >4 hours           (3 runs)
python3 $S                                                     # all models, all cells (9,316 runs)
```

</details>

### Arguments (all AND-ed; multiple values are space- or comma-separated)

| Argument | Values |
|---|---|
| `--model` | `qwen35b` `devstral24b` `glm47flash` |
| `--section` | `main` `ablation` |
| `--primitive` | `fc` `tr` `su-full` `su-partial` `ss` `ss-partial` `trc` `trc-su` `trc-ss` `otrc` `otrc-tr` `otrc-su-partial` `otrc-ss-partial` |
| `--condition` / `--cell` | Directory name as-is (`full-context`, `di__binf__fc`, etc.) |
| `--budget` / `--depth` | `15000` … (FC is `999999999`) / `0.3` `0.5` `0.7` |
| `--run` | `1 2 3` |
| `--task` | instance_id or `@file` (a JSON task list, or a txt file with one task per line) |
| `--difficulty` | `u15` (<15 min fix) `15m1h` (15 min - 1 hour) `1to4h` (1-4 hours) `gt4h` (>4 hours) |
| `--cohort` | `p100` `abl30` `abl25` `new70` |
| `--include-resolved` | Also output resolved runs (`cause=resolved`) |
| `--no-log-scan` | Do not read agent.log (context limit is judged from exit_status only) |
| `--name` / `--tag` | Override the output directory name / append a suffix |

### Output: `results/<name generated from the arguments>/`

Example: `results/model=qwen35b__primitive=fc__difficulty=u15/`

| File | Contents |
|---|---|
| `failure_causes.csv` | One row per run: task, run, model, primitive, budget, depth, difficulty, cohorts, **cause**, cause_detail, exit_status, harness_returncode, step_count, max_step_prompt_tokens, latency, run_dir, … |
| `summary_by_cause.csv` | Number of runs / tasks per cause |
| `summary_pivot.csv` | (model, section, primitive, budget, depth) × cause |
| `summary_by_difficulty.csv` | Difficulty × cause |
| `args.json` | Arguments and constants used (STEP_LIMIT=125, AGENT_TIMEOUT=1500 s, per-model max-model-len) |

### Cause definitions and precedence

| cause | Meaning | Rule |
|---|---|---|
| `resolved` | Success (only with `--include-resolved`) | `resolved == True` |
| `submitted_unresolved` | Agent submitted on its own, but the patch was wrong | `exit_status == Submitted`. `cause_detail` = `wrong_patch` / `empty_patch` (submitted without a patch) |
| `step_limit` | 125-step limit reached | `exit_status == LimitsExceeded` |
| `context_limit` | vLLM max-model-len exceeded (qwen35b 102,400 / devstral24b and glm47flash 65,536) | `exit_status ∈ {BadRequestError, ContextWindowExceededError}`, or agent.log contains `"param":"input_tokens","code":400` / `maximum context length` |
| `timeout` | 1500 s timeout | harness `returncode == -1` |
| `other:<exit_status>` | API errors etc. (e.g. `InternalServerError`) | Any other non-empty exit_status |
| `unrecorded` | Nothing recorded | Neither the outcomes csv nor trajectory.json has an exit_status / returncode |

Rules are evaluated top to bottom. A run that hit the context limit, then hung in litellm
retries until the 1500 s kill, is classified as `context_limit` (with
`hung_until_1500s_kill` in `cause_detail`).
Runs with no exit_status in the outcomes csv (e.g. the 115 runs seeded from another machine)
are backfilled from `info.exit_status` in trajectory.json (see the `exit_status_source`
column). Runs with returncode == -1 (1500 s kill) are not backfilled and stay `timeout`.

`swebench_verified_difficulty.json` maps instance_id → difficulty for the 500 tasks of
HF `princeton-nlp/SWE-Bench_Verified`. The script regenerates it if missing.
