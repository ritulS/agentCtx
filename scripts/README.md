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
| `expansions/run_r2_swe_p30s.sh` | r2 campaign on the P30S cohort with Qwen3.5-35B-A3B, into `data/r2/swebench/p30s/<model>/<cell>`; the first argument picks a preset (`free` = `di__b15k__su-free`, default; `su-free`, `fc`, `baselines` = `fc`; the `ss-free` and `otrc` presets went with their conditions on 2026-11-19), `CELLS` and `RUNS_PER_TASK` override. `R2_SECTION=p100_minus_p30s` runs the other 70 P100 tasks (`task_lists/swe_verified/p100_minus_p30s.json`) into `data/r2/swebench/p100_minus_p30s/<model>/<cell>` instead. |
| `expansions/run_r2_swe_p30s_devstral2507.sh` | Devstral-Small-2507 sandbox cells: `run_r2_swe_p30s.sh` with `R2_MODEL=devstral2507`, `configs/config-devstral2507-vllm.yaml` (port 8000, max_tokens 4096, timeout 600, temperature 0), tag `devstral-small-2507`, first 20 P30S tasks (`N_TASKS=20`), 3 runs/task, `CELLS` = `di__b15k__su-free` then `d05__b15k__tr`; refuses to start unless port 8000 serves `mistralai/Devstral-Small-2507` with prefix caching in the `REQUIRE_PREFIX_CACHE` state (default `on`, the deliberate choice for this dense model after the 2026-10-17 probe; `off` / `any`). Pair with `serving/start_vllm_devstral2507_sandbox.sh` (`PREFIX_CACHE=on`). |
| `expansions/run_r2_swe_never7_adaptive.sh` | r2 adaptive primitive-order cells on the 7 P30S tasks Qwen3.5-35B-A3B never resolved, into `data/r2/swebench/p30s_never7/<model>/d05__b15k__adaptive-prefix3-<pattern>`; one cell per `PATTERNS` entry (default `tts tst tss stt sts sst` = the primitive at compression events 1-3, `t` TR / `s` SU-free, last held), schedules in `configs/adaptive/never7_prefix3/`. `R2_SECTION=p100_minus_p30s_never13` runs the same six cells on the 13 P100-minus-P30S tasks the model never resolved (`task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json`) into `data/r2/swebench/p100_minus_p30s_never13/<model>/...` instead. `R2_SECTION=p100_fc_only4` runs all eight orders (the six plus `ttt` / `sss`) at 10 runs per task on the 4 P100 tasks resolved under full context but never under fixed TR or SU-free (`task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json`) into `data/r2/swebench/p100_fc_only4/<model>/...`. `R2_SECTION=p100_su_free_majority` / `R2_SECTION=p100_tr_majority` run the uniform `sss` / `ttt` order only (SU-free / TR at every compression event) on the first `N_TASKS` (default 5; `N_TASKS=all` for every task) of `task_lists/swe_verified/p100_qwen35b_{su-free,tr}_majority_resolved.json` into `data/r2/swebench/<section>/<model>/...`. |
| `expansions/run_r2_swe_majority_uniform.sh` | Chains the two majority sections of `run_r2_swe_never7_adaptive.sh`: `p100_su_free_majority` (sss) then `p100_tr_majority` (ttt), first 5 tasks of each list × `RUNS_PER_TASK` (default 15), one log for both; `SECTIONS`, `N_TASKS`, `RUNS_PER_TASK`, `R2_MODEL`, `RUN_EVAL`, `MAX_WORKERS` override. |
| `expansions/run_r2_swe_sandbox_chain.sh` | Overnight sandbox chain: step 1 the capped pilot's `SUMMARIZER=nothink4k` cell (`p100_su_free_majority`, sss, 4 sandbox tasks × 15), step 2 `p100_fc_only4` with all eight prefix-3 orders on its first 2 tasks × 15 (`RUNS_PER_TASK_STEP2`, `N_TASKS_STEP2`, `PATTERNS_STEP2`; `SKIP_STEP1` / `SKIP_STEP2`), both into `qwen35b-cap4k-sumnothink4k`. Waits first for any capped pilot already running (`WAIT_FOR_PATTERN`), and both steps resume (completed keys skipped). |
| `expansions/run_r2_swe_sandbox_isolated.sh` | Isolated serial driver for the capped pilot: for every pending (section, order, task, run) key it starts a fresh caching-OFF server (`serving/start_vllm_qwen35_sandbox.sh`), waits for `/v1/models`, runs the pilot on a one-task list with `RUNS_PER_TASK=<run>` and `MAX_WORKERS=1` (recorded keys skipped, so exactly that run executes; `RUN_EVAL=1` grades it at once), stops the server (`serving/stop_vllm.sh`) and removes every container of the user's podman (`PURGE_CONTAINERS=all`; `experiment` = only `minisweagent-*` / `sweb.eval.*`; images stay), then checks the key was recorded. The same stop + purge runs before the first cycle and on every exit. Settings pass through to the pilot (`SECTIONS`, `PATTERNS`, `TASKS_FILE`, `N_TASKS`, `RUNS_PER_TASK`, ...); `SUMMARIZER` defaults to `nothink` (the 2048-cap summarizer recipe) with `SUMMARY_MAX_ATTEMPTS` 5 instead of the pilot's 2; dest `R2_MODEL` defaults to the pilot's dir plus `ISO_SUFFIX` (`-iso`, e.g. `qwen35b-cap4k-sumnothink-iso`). Refuses to start while another r2 launcher / runner is running (`BUSY_PATTERN`) or a server without the sandbox pid file answers; `DRY_RUN=1` prints the plan. `INNER=p30s` swaps the pilot for `run_r2_swe_p30s.sh` (plain grid cells from `CELLS="cell:condition:depth ..."`, summarizer = agent model, `QWEN_AGENT_CONFIG` / `QWEN_TAG` passed through; `SECTIONS` p30s | p100_minus_p30s, explicit `R2_MODEL` required, keys `<task>__<condition>__r<n>` in `data/r2/swebench/<section>/<R2_MODEL>/<cell>/`); `CYCLE_ORDER=run-major` runs run 1 of every task before run 2 (default `task-major`). `SERVER_LIFECYCLE=persistent` starts the server once before the first cycle and stops it once on exit instead of restarting it per run (runs stay serial with `MAX_WORKERS=1`, containers are still purged after every run, orphaned `conmon` monitors of removed containers are reaped; the driver stops if the server dies between cycles). `KV_FLUSH=prefix-cache` (persistent only) POSTs `/reset_prefix_cache` after every cycle's purge and requires the server's "Successfully reset prefix cache" log line (server started with `VLLM_SERVER_DEV_MODE=1`). `OPENROUTER_QUOTA_GATE=1` (INNER=p30s) starts a key whose condition is `online-claude-*` only while the OpenRouter account has >= `OPENROUTER_MIN_REMAINING` (320) free-model requests left in the current UTC day (GET `/api/v1/key`), runs the next ungated key while such a key is deferred (deferred keys are retried before every cycle, so they run first after the daily reset), and sleeps until 00:00 UTC + 5 min when nothing may start (for `:free` selector models, 1000 requests/day; a run that hits the cap dies after 3 consecutive selector errors). | `OPENROUTER_CREDIT_GATE=1` (INNER=p30s; the fc20 wrapper turns it on for a paid OpenRouter selector) starts an `online-claude-*` key only while the key can still spend >= `OPENROUTER_MIN_CREDITS` USD (10; the smaller of the account's credits left from GET `/api/v1/credits` and the key's own `limit_remaining` from `/api/v1/key`), since a paid selector run that exhausts either dies mid-run on 402 / 403 after 3 consecutive errors (2026-10-30/31); credits do not reset, so a shortfall defers the gated keys for the rest of the launch and the driver stops once nothing else is left.
| `expansions/run_r2_swe_sandbox_isolated_devstral2507.sh` | Devstral-Small-2507 isolated cells: the isolated driver with `INNER=p30s` on the 6-task Devstral sandbox cohort (`task_lists/swe_verified/sandbox_devstral2507_sufree3_never3.json`), `RUNS_PER_TASK=10`, cell `di__b15k__su-free` (add `d05__b15k__tr:truncation:0.5` to `CELLS` for TR), run-major order, agent config `configs/config-devstral2507-vllm.yaml` (temperature 0), server `serving/start_vllm_devstral2507_sandbox.sh` with `PREFIX_CACHE=on` (default; `off` for caching OFF) started fresh for every run, or once for the whole plan with `SERVER_LIFECYCLE=persistent` (plus `KV_FLUSH=prefix-cache` to empty the prefix cache between runs; dest `devstral2507-serial-flush`); dest `data/r2/swebench/p30s/devstral2507-iso/` (`-iso-nocache` with caching OFF; `devstral2507-serial[-nocache]` with the persistent server). `DRY_RUN=1` prints the 60-key plan; measured 8 h 35 min for the per-run SU-free cell (8.7 min/cycle), ~7 h expected with the persistent server. |
| `expansions/run_r2_swe_sandbox_isolated_devstral24b_fcmaj4.sh` | Devstral-Small-2-24B isolated cells on the same 4 tasks: phase A `di__binf__fc` at 2 runs/task (the `d05__b21k__su-full` cell it also ran on 2026-10-25 was retired with the su-full condition on 2026-11-19), phase B `di__binf__ocs` (online-claude-select) at 1 run/task, each phase one invocation of the isolated driver (fresh `serving/start_vllm_devstral.sh` server per run on port 8002 / GPUs 0-3 / TP=4, caching ON, `MAX_WORKERS=1`, temperature 0 via `configs/config-devstral-vllm-temp0.yaml`), dest `data/r2/swebench/p30s/devstral24b-iso-fcmaj4/`. `PHASES=B` runs the OCS phase alone; `DRY_RUN=1` prints both plans; ~3-5 h. |
| `expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh` | Devstral-Small-2-24B isolated cells on the 20 P100 tasks it resolved in 3/3 or exactly 2/3 ICLR full-context runs (`task_lists/swe_verified/p100_devstral24b_fc_3of3_10_2of3_10.json`; 15 in P30S, 5 outside): preset `ocs` (default; `di__binf__ocs`, selector through OpenRouter, default the free `nvidia/nemotron-3-ultra-550b-a55b:free` at effort medium with `MSWEA_EXTRACT_MAX_TOKENS` 6000, assistant prefill and `MSWEA_EXTRACT_KEEP_RECENT` 3 = the 2 newest turns verbatim, `MSWEA_EXTRACT_*` override), `ocsa` (`di__binf__ocsa`, `online-claude-select-anchored`: history tagged with the previous step's context and a 30000-token cap on the selection, not part of `all`), `ocsi` (`di__binf__ocsi`, `online-claude-select-incremental`: the selector sees the agent's current context instead of the complete history, so the context only shrinks; not part of `all`), `ocst` (`di__binf__ocst`, `online-claude-select-threshold`: the ocsa selector fired only while the context exceeds 30000 tokens, rebuilding it under a 20000-token cap, so the context is append-only between firings and the agent model's prefix cache serves every step; not part of `all`), `ocstx` (`di__binf__ocstx`, `online-claude-select-threshold-output-extract`: ocst plus a per-output pre-extraction, every new tool output above 1000 tokens is trimmed in place by the extractor model right after it is added, in the context, the complete history and the trajectory at once, so omitted output text never returns; not part of `all`), `ocstx15` (`di__binf__ocstx15`, `online-claude-select-threshold-output-extract-15k`: ocstx with the firing threshold halved to 15000 and the cap lowered to 10000), `ocstx15p` (`di__binf__ocstx15p`, `online-claude-select-threshold-output-extract-15k-phase`: ocstx15 with a phase-boundary gate, the extractor model is asked above 15000 tokens whether the newest turn is a natural break in the agent's work and the selector fires only on `boundary`, or without asking above 30000), `su-free` (`di__b21k__su-free`), `fc` (`di__binf__fc`) or `all`; same recipe as the fcmaj4 wrapper (fresh `serving/start_vllm_devstral.sh` server per run on port 8002, all 8 GPUs / TP=8 by default (`DEVSTRAL_CUDA_VISIBLE_DEVICES` / `DEVSTRAL_TENSOR_PARALLEL_SIZE`; the ICLR layout was 4-7 / TP=4), `MAX_WORKERS=1`, temperature 0, eval + purge per run). Defaults to the smoke scope `N_TASKS=1 RUNS_PER_TASK=1` (django-14915); the campaign is `N_TASKS=all RUNS_PER_TASK=3 ... all` (180 keys, run-major within each cell). `TASK_SET=ocsi10` swaps the list for the 10-task subset `task_lists/swe_verified/p100_devstral24b_fc20_ocsi10.json` (ocsi-vs-fc comparison; same dest dir and keys, so the 25-task FC runs are reused). With a `:free` selector the driver's quota gate is on (`OPENROUTER_QUOTA_GATE=1`, `OPENROUTER_MIN_REMAINING` 200 here). `AGENT_TIMEOUT` defaults to 14400 s for every cell (OCS steps are 5-10x slower than FC steps; the 300-step limit is the binding cap). Section dir `p30s` is a label only (the driver accepts p30s | p100_minus_p30s); dest `data/r2/swebench/p30s/devstral24b-iso-fc20/`. |
| `expansions/run_r2_swe_sandbox_isolated_qwen35b_fcmaj4.sh` | Qwen3.5-35B-A3B isolated cells (fresh caching-ON server with a float32 SSM cache per run via `serving/start_vllm_qwen35_ssm_probe.sh` on port `QWEN_VLLM_PORT` (default 8002 with `configs/config-qwen-vllm-temp0-8002.yaml`; 8000 was taken by another user's service on 2026-10-25) / GPUs 0-3 / TP=4, `SSM_DTYPE=auto` for the bf16 cache, `MAX_WORKERS=1`, temperature 0 via `configs/config-qwen-vllm-temp0.yaml`) on the 4 P30S tasks of `task_lists/swe_verified/p30s_qwen35b_fc_majority_su-free_minority.json`: cells `di__binf__fc`, `di__binf__oce` (online-claude-extract; needs `ANTHROPIC_API_KEY` or `~/.config/agentctx/anthropic_api_key`, checked before anything starts) and `di__b15k__su-free`, `RUNS_PER_TASK=2`, run-major, dest `data/r2/swebench/p30s/qwen35b-iso-fcmaj4-ssmfp32/` (`qwen35b-iso-fcmaj4` with `SSM_DTYPE=auto`). `DRY_RUN=1` prints the 24-key plan; ~4-5 h. |
| `expansions/run_r2_swe_sandbox_isolated_devstral2507_p30s.sh` | The Devstral-Small-2507 isolated wrapper on all 30 P30S tasks (`task_lists/swe_verified/p30_stratified.json`), `RUNS_PER_TASK=3`, dest `data/r2/swebench/p30s/devstral2507-iso-p30s/` (a clean 30 × 3 grid, apart from the 6-task `devstral2507-iso` dir; without `AGENTCTX_PROFILE`, i.e. on Dobby, `devstral2507-iso-p30s-dobby` with the server on GPUs 2-3 only, `DEVSTRAL_CUDA_DEVICES=2,3 DEVSTRAL_TP_SIZE=2`); every other default (fresh server per run, `MAX_WORKERS=1`, caching ON, cell `di__b15k__su-free`, run-major, temperature 0, eval + purge after every run) is the Devstral wrapper's. `DRY_RUN=1` prints the 90-key plan; ~13 h at 8.7 min/cycle. |
| `expansions/run_r2_swe_sandbox_isolated_fc_only4.sh` | The isolated driver on the four `p100_fc_only4` tasks (django-11433, sklearn-13124, sklearn-14983, sympy-17318) with the sandbox iso recipe: fixes `SECTIONS=p100_fc_only4 PATTERNS=sss RUNS_PER_TASK=10` (override by env) and execs `run_r2_swe_sandbox_isolated.sh`; dest `data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink-iso/`. |
| `expansions/run_r2_swe_majority_capped_pilot.sh` | Controlled-sandbox pilot: `run_r2_swe_never7_adaptive.sh` per section (default `SECTIONS=p100_su_free_majority`) on `task_lists/swe_verified/sandbox_su_free_compressing4.json` (the 4 SU-majority first-5 tasks that compressed in every run; `TASKS_FILE` / `N_TASKS` override) with `configs/config-qwen-vllm-cap4k.yaml` (max_tokens 4096, litellm timeout 600 s; `NOTHINK=1` → `...-cap4k-nothink.yaml`, thinking off), `MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=3`, `MAX_WORKERS` default 3, `AGENT_TIMEOUT` default 7200, dest model dir `qwen35b-cap4k[-nothink]`; `SUMMARIZER=nothink` keeps the agent config but routes summary requests through `configs/config-summary-qwen35-35b-nothink.yaml` (same model/server, thinking OFF, max_tokens 2048; `SUMMARY_CONFIG` overrides the file) with `MSWEA_SUMMARY_MAX_ATTEMPTS=2` (`SUMMARY_MAX_ATTEMPTS`), dest `qwen35b-cap4k-sumnothink`; `SUMMARIZER=nothink4k` is the same with `configs/config-summary-qwen35-35b-nothink-4k.yaml` (reply cap 4096) and the default 5 attempts, dest `qwen35b-cap4k-sumnothink4k`; measure first with `maintenance/probe_summarizer_thinking.py`; `SECTIONS=p100_fc_only4` runs that section's eight prefix-3 orders on its own task list (`N_TASKS=2` = django-11433, sklearn-13124; 400 steps / 7200 s) under the same sandbox settings; refuses a server whose `/metrics` reports prefix caching ON (`SANDBOX_ALLOW_PREFIX_CACHE=1` overrides; the probe below showed caching ON changes this model's generations). Pair with `serving/start_vllm_qwen35_sandbox.sh`. |
| `expansions/` | The r2 launchers above (the ICLR model grids and summarizer / prefix-cache ablation launchers were deleted 2026-11-19; git history has them). |
| `serving/` | Start and stop model-specific vLLM servers. |
| `maintenance/` | Probes, replays and analysis tools over existing result trees. |
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

## Expansions

The r2 launchers are described in the table above: `run_r2_swe_p30s.sh` and
`run_r2_swe_never7_adaptive.sh` drive `run_experiment_r2.py`; the sandbox
wrappers (`run_r2_swe_sandbox_isolated*.sh`, `run_r2_swe_majority_capped_pilot.sh`,
`run_r2_swe_sandbox_chain.sh`, `run_r2_swe_majority_uniform.sh`) stack on them.

```bash
bash scripts/expansions/run_r2_swe_p30s.sh fc
DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh ocsa
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

# A Devstral fc20 cell on Albus (see Active_runs.md for the full environment)
DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock N_TASKS=all RUNS_PER_TASK=1 TASK_SET=ocst4 \
    bash scripts/notify_run.sh --unit devstral24b_fc20_ojfstblg_4 --lock devstral_fc20_albus \
    --pid-file devstral24b_fc20_ojfstblg_4 \
    -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral24b_fc20.sh ojfstblg

# Attached, e.g. a one-task smoke test
bash scripts/notify_run.sh --foreground --unit smoke -- bash scripts/expansions/run_r2_swe_p30s.sh fc
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
`tb_verdict_audit/`) are unaffected. `scripts/lib/notify_slack.py` is the notifier it calls
(`start <unit>` / `stop <unit> <result> <status> <log>`); `python3
scripts/lib/notify_slack.py test` checks the webhook. `tests/test_notify_run.py`
covers the wrapper.

## Serving

`serving/start_vllm_{qwen35_prefix_cache,qwen35_sandbox,qwen35_ssm_probe,devstral,devstral2507_sandbox}.sh`
start the selected model, logging to `logs/servers/vllm_<name>_<timestamp>.log`
(`vllm_<name>.latest.log` follows the newest start) with the process-group id
in `logs/servers/vllm_<name>.pid`; `serving/stop_vllm.sh <pid file>` stops a
server with its process group. Check each script's environment overrides and
GPU requirements before use.

```bash
bash scripts/serving/start_vllm_devstral.sh
```

## Maintenance

Post-hoc tools for existing result trees; none of them launches new agent runs
except the replay / continuation probes. (The ICLR-era audit, re-evaluation,
repair and archive tools were deleted 2026-11-19; git history has them.)

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
- `replay_decision.py plan|select|sample|judge|report`: branch-point replay
  (2026-11-02/04): at the call where a run commits to its fix (or, for
  sympy-12419, right after the fix is confirmed), re-query Devstral once at
  temperature 0 and N times at 0.7 under the run's own context, the full
  history and an OCSA selection of the same history (simulated with the
  campaign's selector), label the replies blind with Claude Haiku and compare.
  `--probe-calls` probes explicit calls. Out: `data/r2/probes/replay_decision_*`.
- `continue_run.py plan|run|batch`: continue a finished full-context run from
  call K (container restored by replaying the source commands, agent seeded with
  the source history) to Submitted and grade it: `--mode fc` (control) or
  `--mode window` (calls a..b through the OCSA selector, first anchor = the
  simulated selection of call K-1, then the last selection frozen and new
  messages appended). `plan` writes the 6 failed-FC-run start points of the
  turning-point study; `batch` runs every (entry × mode × rep) not yet graded,
  one at a time, with a prefix-cache reset before each run. Needs the
  Devstral server (`VLLM_SERVER_DEV_MODE=1`) and the rootless podman socket.
  Out: `data/r2/probes/continue_fc_turning/` (`continuation_results.json`).
- `export_selection_views.py <cell> --out <dir>`: human-readable export of an
  online-claude-select cell (ocs / ocsa / ocsi): per run a self-contained
  `view.html` (grid of history messages × selection steps coloured kept /
  partial / dropped / verbatim tail; click a step for the agent's newest
  command, the selector's reasoning and directives, a row for the message
  text), the same grid as `matrix.csv`, `messages.csv` (one row per message
  with its lifecycle), `selections.csv` / `selections.jsonl` (one row per
  selection: counts, attempts, rejections, removed / added uids; the jsonl
  also holds reasoning and directives verbatim), plus `index.html` /
  `index.csv`. Reads the run's event logs; added 2026-11-11 for the DeepSeek
  OCSA cell (`data/r2/probes/ocsa_dsflash_selection/`, gitignored).

The grouped scripts previously lived directly under `scripts/`; the Python
modules they import moved from `scripts/bench_adapters/`, `memory.py`,
`summary_config.py` and `tbench/` into `src/agentctx/` (a root-level
`memory.py` alias remains for the pinned mini-swe-agent commit). Use the new paths in
local launch commands and any external job definitions. Arguments, environment
overrides, and result locations are unchanged (`tests/` verifies this against
the pre-reorganization branch).
