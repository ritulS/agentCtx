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

## rerun_limit_failures.py

Re-runs **only** the runs that a `failure_causes.csv` classified as `timeout`
and/or `step_limit`, with `STEP_LIMIT` / `AGENT_TIMEOUT` raised. The runner
`scripts/run_experiment.py` is imported unchanged; only its two limit constants
and its result directory are overridden (same technique as
`scripts/run_experiment_iclr.py`). `ICLR_experiments/` is never written to.

```bash
S=adaptive_context_management_analysis/rerun_limit_failures.py

# Plan only (nothing created): the 82 Qwen3.5-35B / full-context runs, per difficulty
python3 $S --step-limit 250 --timeout 3600 --dry-run

# Launch agent runs + SWE-bench evaluation (vLLM Qwen :8000 and podman socket must be up;
# add an Active_runs.md entry first)
nohup python3 $S --step-limit 250 --timeout 3600 --max-workers 8 --with-eval \
    > logs/rerun_qwen35b_fc_limits.log 2>&1 &

# Only a subset, e.g. the 1-4 h and >4 h runs of run_1
python3 $S --step-limit 250 --timeout 3600 --difficulty 1to4h gt4h --run 1 --dry-run

# Evaluate later / retry evaluation errors (same arguments -> same output dir)
python3 $S --step-limit 250 --timeout 3600 --eval-only
```

| Argument | Meaning |
|---|---|
| `--step-limit N` / `--timeout SEC` | New limits (required; at least one must exceed 125 / 1500) |
| `--causes-csv` | Input (default `results/model=qwen35b__primitive=fc/failure_causes.csv`). Must be a single cell |
| `--causes` | Which causes to re-run (default `timeout,step_limit`) |
| `--difficulty` / `--task` / `--run` / `--limit` | Further narrowing (same aliases as `classify_failure_causes.py`); `--limit` applies after ordering |
| `--order` | Launch order: `hard-first` (default, >4 h → 1-4 h → 15 min-1 h → <15 min), `easy-first`, `task` |
| `--out-root` / `--name` | Output location (default `results/adaptive_context_management/swebench/reruns/<model>__<cell>__<causes>__step<N>__t<SEC>[__filters]`) |
| `--agent-config` / `--model-tag` / `--max-workers` | Passed to the runner (defaults: `configs/config-qwen-vllm.yaml`, `qwen35-a3b`, 8) |
| `--with-eval` / `--eval-only` | SWE-bench evaluation via the runner's adapter |
| `--force` | Redo keys already present in the output `experiment_results.json` (default: skip = resume) |
| `--dry-run` | Print the plan and the per-difficulty table; write nothing |

Output directory contents: `experiment_results.json` (runner schema plus
`rerun_of`, `original_cause`, `step_limit`, `agent_timeout_s`),
`rerun_manifest.csv` (one row per selected run with the original cause, exit
status, step count, and both run directories), `rerun_info.json`, and
`<task>/<condition>/run_<n>/{agent.log,trajectory.json,token_log.json}`.
The run numbers are kept from the original runs, so `run_2` in the new
directory is the re-run of the original `run_2`.

The output lives under `results/` (gitignored via `results/*`) on purpose: the outcomes aggregator
scans `ICLR_experiments/swebench/**`, and the re-runs must not be mixed into the
canonical cells.

## run_rerun_limits_notified.sh

Slack-notified launcher for one phase of `rerun_limit_failures.py`: it runs the
preflight checks (webhook, vLLM, Podman socket), then hands the runner to
`scripts/notify_run.sh` (background launch, start / completion / failure
notices, per-phase lock, PID file, signal forwarding) with
`post_rerun_summary.py` as the on-success hook that posts the outcome counts.
The launch returns at once and prints the wrapper PID; `FOREGROUND=1` keeps it
attached.

| Phase | Difficulties | Runs |
|---|---|---|
| `PHASE=1` (default) | `15 min - 1 hour` | 55 |
| `PHASE=2` | `1-4 hours` + `>4 hours` | 17 |
| `PHASE=3` | `<15 min fix` | 10 |

Both phases run hardest-first within the phase (`--order hard-first`).

```bash
L=adaptive_context_management_analysis/run_rerun_limits_notified.sh
DRY_RUN=1 bash $L                    # print the plan; no Slack, nothing written
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
bash $L                              # phase 1; detaches, prints the wrapper PID
PHASE=2 bash $L
PHASE=3 bash $L
kill $(cat logs/experiments/rerun_qwen35b_fc_limits_phase1.pid)   # stop (sends a "terminated" notice)
tail -f logs/experiments/rerun_qwen35b_fc_limits_phase1.latest.log
```

Preflight refuses to start unless `SLACK_WEBHOOK_URL` is set (or
`ALLOW_NO_SLACK=1`), vLLM Qwen3.5-35B-A3B answers on `:8000`, the podman socket
exists, and no launcher for the same phase is alive. Other experiment runners on
the machine produce a warning (they inflate per-step latency). Defaults
`STEP_LIMIT=200 TIMEOUT=3600 MAX_WORKERS=8 WITH_EVAL=1` can be overridden via
the environment; `EXTRA_ARGS="--limit 4"` appends arguments for a smoke test.
Runner output goes to `logs/rerun_qwen35b_fc_limits_phase<N>.log`, the PID to
the matching `.pid`. Remember to add an `Active_runs.md` entry before launching.

## build_rerun_outcomes.py

Overlays the raised-limit re-run results on `analysis/outcomes/swebench_outcomes.csv`
and writes a second outcomes table (the canonical CSV and `ICLR_experiments/` are
never modified):

```bash
python3 adaptive_context_management_analysis/build_rerun_outcomes.py            # every reruns/*/
python3 adaptive_context_management_analysis/build_rerun_outcomes.py \
    --rerun-dir results/adaptive_context_management/swebench/reruns/<name>      # only these dirs
```

Output: `results/adaptive_context_management/swebench/swebench_outcomes_rerun.csv`
(+ `swebench_outcomes_rerun.meta.json` with the base-CSV mtime, git HEAD, the
re-run directories / limits used, and an `original → rerun` failure-mode
transition table).

Same columns as `swebench_outcomes.csv`, plus:

| Column | Contents |
|---|---|
| `rerun` | `True` if the row was replaced by a re-run result |
| `step_limit` / `agent_timeout_s` | Harness limits that applied to **this** row (125 / 1500 for non-rerun rows) |
| `rerun_name`, `rerun_source_file`, `rerun_original_cause` | Re-run directory, its `experiment_results.json`, and why the run was selected (`timeout` / `step_limit`) |
| `rerun_attempts`, `rerun_history` | Number of re-run attempts for this run and `<dir>@step<N>/t<M>:<failure_mode>; ...` for all of them |
| `original_*` | `source_file`, `resolved`, `failure_mode`, `exit_status`, `returncode`, `step_count`, `latency_e2e_s` of the replaced canonical row |

Rules:

- A re-run row replaces the canonical row with the same
  `(section, model, cell, task, condition, run)` taken from its `rerun_of` path.
- If the same run was re-run more than once (e.g. 200/3600 then 300/5400) the
  attempt with the highest `(step_limit, agent_timeout_s)` wins; ties go to the
  latest timestamp. All attempts stay listed in `rerun_history`.
- Re-run rows whose `resolved` is missing (eval not run yet) are skipped with a
  warning so an evaluated `False` is never replaced by a blank; pass
  `--include-unevaluated` to overlay them anyway.
