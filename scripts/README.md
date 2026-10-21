# Scripts

Run the examples below from the repository root. Shared Python implementation
lives in `src/agentctx/`; this directory contains command-line entry points and
operational launchers.

| Location | Purpose |
| --- | --- |
| `run_experiment.py` | General SWE-Bench / Terminal-Bench experiment CLI (`agentctx.experiments.runner`). |
| `run_experiment_iclr.py` | Run a cell in the canonical ICLR results tree (`agentctx.experiments.iclr`). |
| `run_experiment_r2.py` | Same, for the r2 extension campaign: writes to `data/r2/<benchmark>/<section>/<model>/<cell>/` (`agentctx.experiments.r2`). |
| `swebench_eval_wrapper.py` | SWE-bench harness wrapper the SWE-bench adapter launches for evaluation (thread cap inside eval containers). |
| `notify_run.sh` | Run any launcher with Slack start / completion / failure notices (see below). |
| `calibration/` | Collect full-context trajectories and calibrate token budgets. |
| `expansions/run_r2_swe_p30s.sh` | r2 campaign on the P30S cohort with Qwen3.5-35B-A3B, into `data/r2/swebench/p30s/<model>/<cell>`; the first argument picks a preset (`free` = `di__b15k__{su-free,ss-free}`, default; `su-free`, `ss-free`, `fc`, `otrc`, `baselines`), `CELLS` and `RUNS_PER_TASK` override. `R2_SECTION=p100_minus_p30s` runs the other 70 P100 tasks (`task_lists/swe_verified/p100_minus_p30s.json`) into `data/r2/swebench/p100_minus_p30s/<model>/<cell>` instead. |
| `expansions/run_r2_swe_p30s_devstral2507.sh` | Devstral-Small-2507 sandbox cells: `run_r2_swe_p30s.sh` with `R2_MODEL=devstral2507`, `configs/config-devstral2507-vllm.yaml` (port 8000, max_tokens 4096, timeout 600, temperature 0), tag `devstral-small-2507`, first 20 P30S tasks (`N_TASKS=20`), 3 runs/task, `CELLS` = `di__b15k__su-free` then `d05__b15k__tr`; refuses to start unless port 8000 serves `mistralai/Devstral-Small-2507` with prefix caching in the `REQUIRE_PREFIX_CACHE` state (default `on`, the deliberate choice for this dense model after the 2026-10-17 probe; `off` / `any`). Pair with `serving/start_vllm_devstral2507_sandbox.sh` (`PREFIX_CACHE=on`). |
| `expansions/run_r2_swe_never7_adaptive.sh` | r2 adaptive primitive-order cells on the 7 P30S tasks Qwen3.5-35B-A3B never resolved, into `data/r2/swebench/p30s_never7/<model>/d05__b15k__adaptive-prefix3-<pattern>`; one cell per `PATTERNS` entry (default `tts tst tss stt sts sst` = the primitive at compression events 1-3, `t` TR / `s` SU-free, last held), schedules in `configs/adaptive/never7_prefix3/`. `R2_SECTION=p100_minus_p30s_never13` runs the same six cells on the 13 P100-minus-P30S tasks the model never resolved (`task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json`) into `data/r2/swebench/p100_minus_p30s_never13/<model>/...` instead. `R2_SECTION=p100_fc_only4` runs all eight orders (the six plus `ttt` / `sss`) at 10 runs per task on the 4 P100 tasks resolved under full context but never under fixed TR or SU-free (`task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json`) into `data/r2/swebench/p100_fc_only4/<model>/...`. `R2_SECTION=p100_su_free_majority` / `R2_SECTION=p100_tr_majority` run the uniform `sss` / `ttt` order only (SU-free / TR at every compression event) on the first `N_TASKS` (default 5; `N_TASKS=all` for every task) of `task_lists/swe_verified/p100_qwen35b_{su-free,tr}_majority_resolved.json` into `data/r2/swebench/<section>/<model>/...`. |
| `expansions/run_r2_swe_majority_uniform.sh` | Chains the two majority sections of `run_r2_swe_never7_adaptive.sh`: `p100_su_free_majority` (sss) then `p100_tr_majority` (ttt), first 5 tasks of each list × `RUNS_PER_TASK` (default 15), one log for both; `SECTIONS`, `N_TASKS`, `RUNS_PER_TASK`, `R2_MODEL`, `RUN_EVAL`, `MAX_WORKERS` override. |
| `expansions/run_r2_swe_sandbox_chain.sh` | Overnight sandbox chain: step 1 the capped pilot's `SUMMARIZER=nothink4k` cell (`p100_su_free_majority`, sss, 4 sandbox tasks × 15), step 2 `p100_fc_only4` with all eight prefix-3 orders on its first 2 tasks × 15 (`RUNS_PER_TASK_STEP2`, `N_TASKS_STEP2`, `PATTERNS_STEP2`; `SKIP_STEP1` / `SKIP_STEP2`), both into `qwen35b-cap4k-sumnothink4k`. Waits first for any capped pilot already running (`WAIT_FOR_PATTERN`), and both steps resume (completed keys skipped). |
| `expansions/run_r2_swe_sandbox_isolated.sh` | Isolated serial driver for the capped pilot: for every pending (section, order, task, run) key it starts a fresh caching-OFF server (`serving/start_vllm_qwen35_sandbox.sh`), waits for `/v1/models`, runs the pilot on a one-task list with `RUNS_PER_TASK=<run>` and `MAX_WORKERS=1` (recorded keys skipped, so exactly that run executes; `RUN_EVAL=1` grades it at once), stops the server (`serving/stop_vllm.sh`) and removes every container of the user's podman (`PURGE_CONTAINERS=all`; `experiment` = only `minisweagent-*` / `sweb.eval.*`; images stay), then checks the key was recorded. The same stop + purge runs before the first cycle and on every exit. Settings pass through to the pilot (`SECTIONS`, `PATTERNS`, `TASKS_FILE`, `N_TASKS`, `RUNS_PER_TASK`, ...); `SUMMARIZER` defaults to `nothink` (the 2048-cap summarizer recipe) with `SUMMARY_MAX_ATTEMPTS` 5 instead of the pilot's 2; dest `R2_MODEL` defaults to the pilot's dir plus `ISO_SUFFIX` (`-iso`, e.g. `qwen35b-cap4k-sumnothink-iso`). Refuses to start while another r2 launcher / runner is running (`BUSY_PATTERN`) or a server without the sandbox pid file answers; `DRY_RUN=1` prints the plan. `INNER=p30s` swaps the pilot for `run_r2_swe_p30s.sh` (plain grid cells from `CELLS="cell:condition:depth ..."`, summarizer = agent model, `QWEN_AGENT_CONFIG` / `QWEN_TAG` passed through; `SECTIONS` p30s | p100_minus_p30s, explicit `R2_MODEL` required, keys `<task>__<condition>__r<n>` in `data/r2/swebench/<section>/<R2_MODEL>/<cell>/`); `CYCLE_ORDER=run-major` runs run 1 of every task before run 2 (default `task-major`). `SERVER_LIFECYCLE=persistent` starts the server once before the first cycle and stops it once on exit instead of restarting it per run (runs stay serial with `MAX_WORKERS=1`, containers are still purged after every run, orphaned `conmon` monitors of removed containers are reaped; the driver stops if the server dies between cycles). `KV_FLUSH=prefix-cache` (persistent only) POSTs `/reset_prefix_cache` after every cycle's purge and requires the server's "Successfully reset prefix cache" log line (server started with `VLLM_SERVER_DEV_MODE=1`). |
| `expansions/run_r2_swe_sandbox_isolated_devstral2507.sh` | Devstral-Small-2507 isolated cells: the isolated driver with `INNER=p30s` on the 6-task Devstral sandbox cohort (`task_lists/swe_verified/sandbox_devstral2507_sufree3_never3.json`), `RUNS_PER_TASK=10`, cell `di__b15k__su-free` (add `d05__b15k__tr:truncation:0.5` to `CELLS` for TR), run-major order, agent config `configs/config-devstral2507-vllm.yaml` (temperature 0), server `serving/start_vllm_devstral2507_sandbox.sh` with `PREFIX_CACHE=on` (default; `off` for caching OFF) started fresh for every run, or once for the whole plan with `SERVER_LIFECYCLE=persistent` (plus `KV_FLUSH=prefix-cache` to empty the prefix cache between runs; dest `devstral2507-serial-flush`); dest `data/r2/swebench/p30s/devstral2507-iso/` (`-iso-nocache` with caching OFF; `devstral2507-serial[-nocache]` with the persistent server). `DRY_RUN=1` prints the 60-key plan; measured 8 h 35 min for the per-run SU-free cell (8.7 min/cycle), ~7 h expected with the persistent server. |
| `expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh` | The Devstral-Small-2507 isolated wrapper on all 30 P30S tasks (`task_lists/swe_verified/p30_stratified.json`), `RUNS_PER_TASK=3`, dest `data/r2/swebench/p30s/devstral2507-iso-p30s/` (a clean 30 × 3 grid, apart from the 6-task `devstral2507-iso` dir; without `AGENTCTX_PROFILE`, i.e. on Dobby, `devstral2507-iso-p30s-dobby` with the server on GPUs 2-3 only, `DEVSTRAL_CUDA_DEVICES=2,3 DEVSTRAL_TP_SIZE=2`); every other default (fresh server per run, `MAX_WORKERS=1`, caching ON, cell `di__b15k__su-free`, run-major, temperature 0, eval + purge after every run) is the Devstral wrapper's. `DRY_RUN=1` prints the 90-key plan; ~13 h at 8.7 min/cycle. |
| `expansions/run_r2_swe_sandbox_isolated_fc_only4.sh` | The isolated driver on the four `p100_fc_only4` tasks (django-11433, sklearn-13124, sklearn-14983, sympy-17318) with the sandbox iso recipe: fixes `SECTIONS=p100_fc_only4 PATTERNS=sss RUNS_PER_TASK=10` (override by env) and execs `run_r2_swe_sandbox_isolated.sh`; dest `data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink-iso/`. |
| `expansions/run_r2_swe_majority_capped_pilot.sh` | Controlled-sandbox pilot: `run_r2_swe_never7_adaptive.sh` per section (default `SECTIONS=p100_su_free_majority`) on `task_lists/swe_verified/sandbox_su_free_compressing4.json` (the 4 SU-majority first-5 tasks that compressed in every run; `TASKS_FILE` / `N_TASKS` override) with `configs/config-qwen-vllm-cap4k.yaml` (max_tokens 4096, litellm timeout 600 s; `NOTHINK=1` → `...-cap4k-nothink.yaml`, thinking off), `MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=3`, `MAX_WORKERS` default 3, `AGENT_TIMEOUT` default 7200, dest model dir `qwen35b-cap4k[-nothink]`; `SUMMARIZER=nothink` keeps the agent config but routes summary requests through `configs/config-summary-qwen35-35b-nothink.yaml` (same model/server, thinking OFF, max_tokens 2048; `SUMMARY_CONFIG` overrides the file) with `MSWEA_SUMMARY_MAX_ATTEMPTS=2` (`SUMMARY_MAX_ATTEMPTS`), dest `qwen35b-cap4k-sumnothink`; `SUMMARIZER=nothink4k` is the same with `configs/config-summary-qwen35-35b-nothink-4k.yaml` (reply cap 4096) and the default 5 attempts, dest `qwen35b-cap4k-sumnothink4k`; measure first with `maintenance/probe_summarizer_thinking.py`; `SECTIONS=p100_fc_only4` runs that section's eight prefix-3 orders on its own task list (`N_TASKS=2` = django-11433, sklearn-13124; 400 steps / 7200 s) under the same sandbox settings; refuses a server whose `/metrics` reports prefix caching ON (`SANDBOX_ALLOW_PREFIX_CACHE=1` overrides; the probe below showed caching ON changes this model's generations). Pair with `serving/start_vllm_qwen35_sandbox.sh`. |
| `expansions/` | Launch model grids, additional repetitions and the summarizer / prefix-cache ablations. |
| `serving/` | Start and stop model-specific vLLM servers. |
| `harbor/` | Prebuild Terminal-Bench images, configure Harbor tasks, check worker cancellation. |
| `maintenance/` | Audit, re-evaluate, repair and archive existing results. |
| `maintenance/never_resolved_tasks.py` | Lists the tasks with no resolved run across a set of cells of one model dir (e.g. `data/r2/swebench/p100_minus_p30s/qwen35b`) in the `task_lists/swe_verified/` schema, with difficulty from the cached SWE-bench Verified dataset; produced `p30s_qwen35b_never_resolved.json` (7) and `p100_minus_p30s_qwen35b_never_resolved.json` (13). |
| `maintenance/majority_resolved_tasks.py` | The complement: lists the tasks resolved in at least `--min-resolved` (default 2) of `--min-runs` (default 3) evaluated runs of one `--cell` across one or more model dirs (e.g. the r2 `p30s` and `p100_minus_p30s` sections together), in P100 order with difficulty (`--interleave` instead alternates the not-always-resolved tasks with the always-resolved ones, cycling through the difficulty levels); produced, with `--interleave`, `p100_qwen35b_tr_majority_resolved.json` (53) and `p100_qwen35b_su-free_majority_resolved.json` (55). |

The isolated driver's cleanup stops the pilot/agent/evaluation process group
before stopping vLLM and removing containers (including anonymous volumes).
A shared launcher lock prevents two isolated drivers with the same log root
from overlapping. Cleanup errors produce a nonzero exit and prevent the next
run. EXIT, INT, TERM and HUP trigger cleanup; against SIGKILL / OOM of the
driver a watchdog in its own session (`isolated-watchdog`, started after the
guards, stopped first on a clean exit) kills the pilot's process group, stops
the server and purges the containers; only killing driver and watchdog
together, or power loss, leaves work behind.
This resets live inference state and container writable layers. Results/logs,
model/dataset/compilation caches and images remain on disk. The default agent
configs have no host bind mounts or named volumes; custom mounts or a separate
summary server require their own isolation.

## Calibration

- `run_budget_calibration_sb.py` / `.sh`: canonical SWE-Bench P100 FC run_1.
- `run_budget_calibration_tb.py` / `.sh`: canonical Terminal-Bench 1.0 FC runs,
  including rootless and subuid subsets, and isolated native-context
  collections (`--calibration-dir`; see `DEVSTRAL_TB_NATIVE_CALIBRATION.md`,
  `GLM_TB_NATIVE_CALIBRATION.md`).
- `run_budget_calibration_tb2.sh`: Terminal-Bench 2.0 FC runs through the same
  Python launcher; `prepare_tb2_fc_resume.py` lists the tasks left for a resume.
- `run_model_budget_calibration.sh`: earlier 60-trajectory calibration using
  ABL-30 and reference trigger rates; distinct from the canonical P100 workflow.
- `log_vllm_prefix_cache.py`: vLLM `/metrics` prefix-cache recorder used by the
  isolated calibration mode.

```bash
bash scripts/calibration/run_budget_calibration_sb.sh devstral
bash scripts/calibration/run_budget_calibration_tb.sh qwen-rootless
```

## Expansions

- `run_agent_models_expansion.sh`: SWE-Bench Qwen / Devstral / GLM grids.
- `run_agent_models_expansion_tb.sh`: Terminal-Bench Qwen / Devstral / GLM grids.
- `run_glm_tb_ablation_split.sh {gpu0-3|gpu4-7}`: the GLM Terminal-Bench
  ablation split across two vLLM servers (sets `ABLATION_PARTS`, config and
  health URL per half, then launches through `notify_run.sh`).
- `run_terminalbench_rootless_fc_expansion.sh`: FC run_2 through run_5 on the
  Terminal-Bench rootless subset.
- `run_qwen_{swe,tb}_summarizer_ablation.sh`: summarizer-model ablation
  (`--summary-config`, `model_ablation` section).
- `run_qwen_{swe,tb}_prefix_cache_ablation.sh`: vLLM prefix-caching ablation
  (`prefix_cache_ablation` section).
- `run_qwen_tb_prefix_cache_ablation_split.sh {gpu0-3|gpu4-7}`: the
  Terminal-Bench prefix-cache ablation split across two caching-off servers
  (port 8000 on GPUs 0-3, port 8002 on GPUs 4-7; sets `CELLS`, config and
  health URL per half, then launches through `notify_run.sh`).

```bash
bash scripts/expansions/run_agent_models_expansion.sh devstral
bash scripts/expansions/run_agent_models_expansion_tb.sh qwen both
```

### Slack notices: `notify_run.sh`

Every launcher above is plain; wrap it in `scripts/notify_run.sh` to run it
in the background with a start notice, a completion / failure notice with the
exit status and log path, signal forwarding (HUP / INT / TERM stop the
launcher and everything it spawned before the notice goes out) and an
optional per-experiment lock. The wrapper validates its arguments, takes the
lock and checks the webhook, then detaches (nohup + setsid) and prints the
wrapper PID; `kill <PID>` stops the run and posts a "killed" notice. The
launcher's stdout / stderr go to a new `logs/experiments/<unit>_<timestamp>.log`
(or `--log FILE`). Environment overrides of the launcher pass through
unchanged. `--foreground` keeps the run attached to the terminal (smoke
tests, sequential chains).

```bash
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'   # or ALLOW_NO_SLACK=1

# Terminal-Bench main grid (previously run_qwen_tb_main_with_slack.sh)
bash scripts/notify_run.sh --unit qwen-terminal-bench-main --lock qwen_tb_main \
    -- bash scripts/expansions/run_agent_models_expansion_tb.sh qwen main

# SWE-Bench model grid (previously run_agent_models_expansion_notified.sh)
MAX_WORKERS=16 RUN_EVAL=1 bash scripts/notify_run.sh --unit agent-model-expansion/glm \
    -- bash scripts/expansions/run_agent_models_expansion.sh glm

# Summarizer / prefix-cache ablations (previously *_notified.sh / *_with_slack.sh)
SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b \
    bash scripts/notify_run.sh --unit summarizer-ablation/swebench/qwen35b-sum-gemma4-12b \
    -- bash scripts/expansions/run_qwen_swe_summarizer_ablation.sh
bash scripts/notify_run.sh --unit qwen-terminal-bench-prefix-cache-ablation --lock qwen_tb_noprefixcache \
    -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh

# Attached, e.g. a one-task smoke test
bash scripts/notify_run.sh --foreground --unit smoke -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh
```

`--on-success '<command>'` runs a follow-up (for example a results summary)
after a clean exit; `--pid-file` records the launched command's PID for
chained scripts.

### Machine profiles: `lib/profiles.sh`

`AGENTCTX_PROFILE=albus-swe` is the only profile: on Albus (8× A6000) it makes
`serving/start_vllm_qwen35_prefix_cache.sh` (and its prefix-caching-OFF twin for
the sandbox runs, `serving/start_vllm_qwen35_sandbox.sh`, log/pid
`vllm_qwen35_a3b_noprefixcache`) serve Qwen3.5-35B-A3B on all 8 GPUs
with `--tensor-parallel-size 8` (likewise
`serving/start_vllm_devstral2507_sandbox.sh`: Devstral-Small-2507 on port
8000, caching OFF by default, `PREFIX_CACHE=on` for the prefix-cache probe;
log/pid `vllm_devstral2507_noprefixcache` / `vllm_devstral2507_prefixcache`; an explicit `DEVSTRAL_CUDA_DEVICES` / `DEVSTRAL_TP_SIZE` wins over the profile, e.g. `2,3` / `2` to leave Dobby's GPUs 0-1 to another job), and the r2 SWE-bench launchers
(`expansions/run_r2_swe_p30s.sh`, `expansions/run_r2_swe_never7_adaptive.sh`
and so `expansions/run_r2_swe_majority_uniform.sh`) default `MAX_WORKERS` to 8.
Unset, everything keeps the Dobby defaults (GPUs 0-3, TP=4, 16 workers); an
explicit `MAX_WORKERS` always wins; an unknown profile name is an error.

### Log files: `lib/logpaths.sh`

Every shell launcher sources `scripts/lib/logpaths.sh`, which fixes where
logs go and who writes them:

| Path | Contents |
| --- | --- |
| `logs/experiments/<name>_<YYYYmmdd_HHMMSS>.log` | launcher / experiment output, one file per launch |
| `logs/experiments/<name>.latest.log` | symlink to the newest log of that name (`tail -f` target) |
| `logs/experiments/<name>.{lock,pid}` | locks and PID files of runs |
| `logs/servers/vllm_<name>_<YYYYmmdd_HHMMSS>.log` (+ `.latest.log`) | vLLM output, one file per start |
| `logs/servers/vllm_<name>.pid` | the server's process-group id, for `serving/stop_vllm.sh` |

The outermost script owns the log: it creates the file, captures its own
stdout there and exports `AGENTCTX_LOG_FILE`. Launchers underneath call
`experiment_log <name>`, which returns the owner's file when one exists and
otherwise creates their own, and pipe through `emit`, which only tee's when
the launcher owns the file. So `bash scripts/expansions/...` on its own
writes `logs/experiments/followup_..._<ts>.log`, and the same launcher under
`notify_run.sh` writes only into the wrapper's log, never twice. Data
directories under `logs/` (`harbor_jobs/`, `replay_reverify/`, `reeval/`,
`tb_verdict_audit/`) are unaffected. `dashboard/notify_slack.py` is the notifier it calls
(`start <unit>` / `stop <unit> <result> <status> <log>`); `python3
dashboard/notify_slack.py test` checks the webhook. `tests/test_notify_run.py`
covers the wrapper.

## Serving and Harbor setup

`serving/start_vllm_{qwen35_prefix_cache_ablation,qwen35_prefix_cache,qwen35_no_prefix_cache,qwen35_no_prefix_cache_gpu4-7,qwen35_9b,qwen35_swe_summarizer_ablation,devstral,glm47flash,summarizer,gemma4_12b}.sh`
start the selected model, logging to `logs/servers/vllm_<name>_<timestamp>.log`
(`vllm_<name>.latest.log` follows the newest start) with the process-group id
in `logs/servers/vllm_<name>.pid`; `serving/stop_vllm.sh <pid file>` stops a
server with its process group. Check each script's environment overrides and
GPU requirements before use.

`harbor/tb_harbor_prebuild_images.sh` builds Terminal-Bench 1.0 task images and
calls `harbor/configure_tb_harbor_prebuilt.py` to update task and Compose
configuration; `harbor/tb2_harbor_prebuild_images.sh` does the same for
Terminal-Bench 2.0. `harbor/check_vllm_cancellation.py` exercises the Harbor
worker cancellation path against an idle vLLM server (`HARBOR_CANCELLATION.md`).

```bash
bash scripts/serving/start_vllm_devstral.sh
bash scripts/harbor/tb_harbor_prebuild_images.sh hello-world
```

## Maintenance

Post-hoc tools for existing result trees; none of them launches new agent runs
except the re-verification replays.

- `audit_tb_verdicts.py`, `replay_reverify_tb.py`: Terminal-Bench verdict audit
  and command-replay re-verification (`agentctx.benchmarks.replay_agent`).
- `build_reevaluation_candidates.py`, `reevaluate_swebench_candidates.py`:
  re-evaluate saved SWE-bench patches with stale or errored verdicts.
- `repair_token_log_transcription.py`: refresh result rows from their token logs.
- `tag_run_failures.py <cell>...`: tags every run of a cell from its
  `token_log.json` / `trajectory.json` with `runaway` (a reply reached the
  run's `max_tokens`), `summary_runaway`, `hung` (a call took at least the
  client timeout: lost request, retried), `timeout`, `limits_exceeded`, and a
  class `resolved` / `infra_failure` / `model_failure` / `unevaluated`; writes
  `<cell>/failure_tags.csv` and prints a per-task summary (`--no-write` to
  only print).
- `probe_summarizer_thinking.py collect` / `compare`: rebuilds the summary requests of recorded SU-free compression events (default 30 from the `qwen35b-cap4k` sandbox cell, via the event logs and the primitive's own prompt builder), sends each to the live server with thinking ON and OFF (`chat_template_kwargs.enable_thinking`, production temperature 0.2, max_tokens 4096; `--off-max-tokens 2048` mirrors the override), validates the replies with `clean_summary_text()` and compares acceptance, rejection reasons, reply/reasoning size and latency (`data/r2/probes/summarizer_thinking/`). Run it before launching a `SUMMARIZER=nothink` cell.
- `probe_prefix_cache_effect.py collect --label <off|on>` / `compare off on`:
  replays real agent prompts (message prefixes of infra-clean trajectories of
  the 4 sandbox tasks) one at a time, greedily, twice each, against the live
  server, and compares generated token streams and logprobs between a
  prefix-caching-OFF and a prefix-caching-ON server (within-server repeat
  agreement is the noise floor). Server must be idle while collecting. The
  model id comes from `/v1/models` (`--model` asserts it); `--out <dir>` plus
  `--prompts-from <prompts.json>` probes another model (Devstral-Small-2507:
  `data/r2/probes/prefix_cache_effect_devstral2507/`) on the same 40 prompts;
  `--reset-cache` (caching-ON server started with `VLLM_SERVER_DEV_MODE=1`)
  resets the cache before every request, and a second OFF instance after a
  restart (`--label off2`) measures process-to-process numerical drift. Output
  under `data/r2/probes/prefix_cache_effect/` (gitignored).
- `plot_kv_timeline.py --task <id> --regime "<label>=<cell dir>" ... --out <png>`:
  KV-cache occupancy over time for one task, one panel per regime (e.g. the
  `devstral2507-iso` vs `devstral2507-serial` cells), runs laid out left to
  right with the gaps between runs removed so run k starts at the same dashed
  line in every panel. Solid line = blocks held by the run's live requests
  from the scheduler trace in `logs/kv-cache/` (joined through token_log
  response ids, GiB across all TP shards); hollow markers = the 10 s
  `/metrics` samples of `resource_log.jsonl` (`--metrics-samples`); `--warm-cache-estimate` overlays a
  dashed cumulative estimate of the KV written to each server's pool since it started (uncached
  prompt tokens + completions of every agent and summarizer call, summed across the runs that share
  a server, eviction ignored, so an upper bound on the warm prefix cache). Needs the trace dirs of the
  servers named in each run's `serving_info.json`. `--series cache` draws
  instead each step's prompt tokens vs. the `cached_tokens` served from the
  prefix cache (filled = tokens actually prefilled, a bar below the axis marks
  the steps that missed ≥ 1 whole block); `--series prefill-steps` puts the
  agent step on the x axis and draws the prefilled tokens per step as bars.
  The "prefix-cache block miss: k/n" labels count steps that recomputed ≥ 1 whole block
  of the prompt; the partial tail block (< 16 tokens) is never cached and is
  recomputed at every step (drawn grey, invisible at this scale), and a hit on
  an exact block multiple, which vLLM reports as one recomputed block, is
  drawn as 0. With `--series prefill-steps --divergence` a second panel under
  each regime shows, per step, how many tokens of that step's prompt do not
  match the previous run's prompt at the same step (prompts replayed from
  events.jsonl + compression_events.jsonl, messages aligned with difflib and
  differing messages diffed token by token with the Devstral tekken tokenizer
  from the HF cache, `--tokenizer` overrides; `--divergence-outline` adds each
  step's whole prompt length as a faint outline, run 1 is greyed out, steps past the previous run's end are hatched;
  the count is one-sided, so a compressed prompt in the current run gives a
  small bar even when the previous run's prompt was large). `--layout shared-time` keeps real seconds on a shared
  axis instead of one equal-width slot per run; `--max-runs N` limits the runs.
- `reconstruct_context.py <run_dir> [--step N] [--event K]`: replay a run's
  `events.jsonl` / `compression_events.jsonl` (written when
  `MSWEA_EVENT_LOG_DIR` is set; SWE-bench runs since 2026-09-23) to recover
  the context the model saw at any step, verified against `trajectory.json`
  and `token_log.json`.
- `archive_devstral_fc_r23.py`, `archive_qwen_ablation_seeded.sh`,
  `reuse_qwen_main_for_ablation.py`: archive or seed result cells.

The grouped scripts previously lived directly under `scripts/`; the Python
modules they import moved from `scripts/bench_adapters/`, `memory.py`,
`summary_config.py` and `tbench/` into `src/agentctx/` (a root-level
`memory.py` alias remains for the pinned mini-swe-agent commit). Use the new paths in
local launch commands and any external job definitions. Arguments, environment
overrides, and result locations are unchanged (`tests/` verifies this against
the pre-reorganization branch).
