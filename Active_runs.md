# Active Experiment Runs

## Latest data status — 2026-09-29: SU-free and TRC archived

The September 29 fallback-ON / max_tokens=32768 full batch completed with
120 evaluated run_1 results (superseding the older "no new full batch" note below).
SU-free (30 runs, 19 resolved) and TRC (30 runs, 18 resolved) were subsequently
archived at the user's request before rerunning with the post-audit fixes.
Archive: [r2_p30s_qwen35b_su_free_trc_before_fixes_20260929_232739_847347](archives/r2_p30s_qwen35b_su_free_trc_before_fixes_20260929_232739_847347/manifest.json).
All 795 source files were verified by SHA-256 after moving.
The active `data/r2/swebench/p30s/qwen35b/` tree now retains only TR
(30 runs, 16 resolved) and FC (30 runs, 18 resolved); both verified unchanged.
Smoke results remain separate. No new batch was launched by this archival.


## ✅ RESOLVED 2026-08-07 — Dobby GPU/MIG incident (2026-07-30 → 08-07)

The 2026-07-30 09:55 reboot left MIG Enabled on all 4 A100s with zero
instances — CUDA saw no devices; all GPU work (incl. Qwen3.5-35B serving)
dead for a week, unnoticed. Fixed 2026-08-07 via lab-admin sudo:
`rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia` + `nvidia-smi -mig 0`
(no reboot needed; nvidia_drm/modeset was the hidden "client" blocking
gpu-reset). **Open follow-ups:** (1) find what enabled MIG at boot before
the next reboot repeats this; (2) persistence mode is off (`nvidia-smi
-pm 1`); (3) vLLM `vllm-qwen35` user unit + rootless podman socket still
need rebuilding for serving/tbench.

## Archived completion — 2026-09-28: r2 P30S fixed run1

- **ARCHIVED (2026-09-29):** Qwen3.5-35B-A3B, SU-free → TRC → TR → FC, 30 tasks × run_1 per cell (120 runs). Finished agent execution and evaluation at **2026-09-28 06:34:24 CDT**. No experiment/evaluation process remains at the audit; vLLM remains running.
- **Results:** SU-free 17/30, TRC 17/30, TR 16/30, FC 18/30 resolved. All verdicts populated; 17 step-limit failures, 5 invalid submissions (source excerpts instead of diffs). No outstanding infrastructure evaluation errors.
- **Audit:** 120/120 event replays verified. 800/13,193 agent calls have format errors (444 empty final content with reasoning, 325 output-length limits, 31 other format errors). SU-free falls back to TR in 15/74 compression events. See [audit report](experiments/r2/audits/r2_p30s_run1_20260928/report.md) and [per-run CSV](experiments/r2/audits/r2_p30s_run1_20260928/runs.csv).
- **Log:** `logs/experiments/r2_swebench_p30s_qwen35b-fixed-run1_20260928_023626.log`.
- **Archive:** [archives/r2_p30s_qwen35b_run1_before_reasoning_fallback_20260929_034952](archives/r2_p30s_qwen35b_run1_before_reasoning_fallback_20260929_034952/README.md). All 120 run_1 outputs moved out of `data/`; 1,505 files verified by SHA-256. Fallback smoke remains separate. No new full batch launched.
- The older local P30S statuses below are historical and superseded by the fixed-run1 batch. Prior SU-free/TRC/FC run_1–3 data was archived before this batch; it is not mixed into this audit.

## Currently Running

### Devstral-Small-2507 — sklearn-11578 ×5 with a fresh vLLM server per run, pool-wide KV trace (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-21 13:41:31 → 14:44:07 CDT (63 min, 5 cycles, 5 fresh servers; final clean-up ran,
  no containers left; log
  `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-iso-11578only-pool_20261021_134131.log`; one
  server log + KV trace dir per run, resolved per run through `serving_info.json`). Launched by Claude at the user's
  request ("isolatedの方もrun5まではかって欲しいかもです"), `ALLOW_NO_SLACK=1`.
- **Why:** the isolated counterpart of the pool-traced persistent cell below, so the upper panel of
  `plots/kv_timeline_11578_pool.png` gets a *measured* warm-cache line too (the 2026-10-17 per-run servers predate
  the pool records). Expected: the pool line restarts from ~0 at every run (fresh server), climbs to the run's
  own writes, and jumps by one full context copy at every SU (summarizer prompt shares no prefix).
- **What:** per-run server (`SERVER_LIFECYCLE=per-run`, default), `R2_MODEL=devstral2507-iso-11578only-pool`,
  task list `task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json`, 5 runs; otherwise the isolated
  recipe (TP=8, caching ON, MAX_WORKERS=1, SU-free at 15k, temperature 0, eval after every run, containers purged).
  ~8.7 min per cycle (measured 2026-10-17) → ~45 min.
- **Result (`data/r2/swebench/p30s/devstral2507-iso-11578only-pool/di__b15k__su-free/`, 5 rows):** **0/5** (Submitted
  ×5; r1/r2/r3/r5 52-62 calls / 2 compressions / 5.7-6.4 min; **r4 251 calls / 12 compressions / 23.8 min**, a
  long wandering run), the per-run picture again. Pool traces (one dir per server, each starting at 128 blocks =
  the first prefill chunk of step 1): hashed blocks never decrease within a server (0 decreases over 631-3,715
  rows), owned = total − 1 − free matches the live requests in every row, and the warm cache at the end of each
  run is 9.94 / 10.78 / 9.90 / **47.27** / 10.42 GiB. **The summarizer writes 43-49 % of each run's pool**: SU
  events added 4.4-4.8 GiB per ordinary run (2 events ≈ 29-32k tokens, one full context copy each) and 23.4 GiB in
  r4 (12 events). Figure: `plots/kv_timeline_11578_pool.png` (both panels measured, `--pool-trace`; r4's 47 GiB
  sets the y-scale).
- **Launch (used):**
  `ALLOW_NO_SLACK=1 R2_MODEL=devstral2507-iso-11578only-pool RUNS_PER_TASK=5 TASKS_FILE=$PWD/task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso-11578only-pool -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`


### Devstral-Small-2507 — sklearn-11578 ×5 alone on ONE persistent server, with the pool-wide KV trace (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-21 13:04:32 → 13:25:24 CDT (21 min, 5 cycles; one server, ready in 50 s; final
  clean-up ran, no containers left; log
  `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-serial-11578only-pool_20261021_130432.log`;
  server log `logs/servers/vllm_devstral2507_prefixcache_20261021_130433.log`, KV trace
  `logs/kv-cache/vllm_devstral2507_prefixcache_20261021_130433/`). Launched by Claude at the user's request
  ("では実測して。Persistentの11578 onlyだけでrun 5までやって欲しいです"), without Slack notices (`ALLOW_NO_SLACK=1`;
  the webhook URL is not in the launch environment).
- **Why:** replace the *estimated* warm-cache line of the KV figure (`--warm-cache-estimate`: cumulative
  `prompt − cached + completion`, eviction ignored) with a *measured* one. The tracer now also writes
  server-wide `type: pool` rows (`hashed_blocks` = blocks carrying a prefix hash, owned or free; `free_blocks`;
  `total_blocks`; see `src/agentctx/KV_CACHE_TRACE.md`), and `plot_kv_timeline.py --pool-trace` draws them.
  Same recipe as the 10-run persistent cell above (one server, TP=8, caching ON, one run per cycle, SU-free at
  15k, temperature 0, eval after every run), 5 runs, new model dir so nothing is skipped as recorded.
- **Result (`data/r2/swebench/p30s/devstral2507-serial-11578only-pool/di__b15k__su-free/`, 5 rows):** **4/5**
  (r1 unresolved, 42 calls / 1 compression, 5.0 min; r2 resolved, 25 calls / 1 compression, 1.8 min; r3-r5
  resolved, 24 calls / 0 compressions, 1.2-1.3 min): the 2026-10-20 cell's shape again. Pool trace
  (`logs/kv-cache/vllm_devstral2507_prefixcache_20261021_130433/`, 1,452 pool rows, `hashed_count: blocks`,
  no tracing error): **hashed blocks never decrease** (0 decreases; free ≠ evicted) and reach 5,431 blocks =
  13.26 GiB of the 120,978-block (295 GiB) pool at the end of r5 (6.60 / 10.59 / 12.30 / 12.80 / 13.26 GiB at
  the end of r1-r5); **owned = total − 1 − free equals the live requests' block sum in 1,452/1,452 rows**, so the
  solid per-request line and the pool line describe the same pool. **The summarizer request shares no prefix
  with the agent context**: during r1's SU the pool gained 14,944 tokens of hashed blocks for a 14,526-token
  prompt + 434 completion (r2: 12,976 for 13,660 + 315), i.e. every SU event writes a second full copy of the
  context. The token-count estimate (`--warm-cache-estimate`) had charged the summarizer only its prompt beyond
  the agent's last prompt and sat ~2.2 GiB per SU below the measurement; fixed on 2026-10-21 to charge the whole
  uncached prompt. Figure: `plots/kv_timeline_11578_pool.png` (`--warm-cache-estimate --pool-trace`).
- **Launch (used):**
  `ALLOW_NO_SLACK=1 SERVER_LIFECYCLE=persistent R2_MODEL=devstral2507-serial-11578only-pool RUNS_PER_TASK=5 TASKS_FILE=$PWD/task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial-11578only-pool -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`

### Devstral-Small-2507 — sklearn-11578 ×10 alone on ONE persistent server, no flush (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-20 00:45:28 → 01:22:33 CDT (37 min, 10 cycles; one server, ready in 60 s; no
  prefix-cache resets; final clean-up ran, no containers left; launched by the user; log
  `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-serial-11578only_20261020_004528.log`).
  Requested as "persistentでsklearn11578のタスクだけ10runs/taskしてみたい".
- **Result (`data/r2/swebench/p30s/devstral2507-serial-11578only/di__b15k__su-free/`, 10 rows):** **9/10** (Submitted
  ×10; r1 44 calls / 1 compression, unresolved; r2 25 calls / 1 compression, r3-r10 24 calls / 0 compressions, all
  resolved; e2e 229 s, 130 s, 86 s, then 69-70 s). **r1 is message-for-message identical to the per-run rows through
  message 37** (cold server = the per-run route, same wrong patch md5 d9f74121); r2 shares only its first 2
  assistant messages with r1 (step 1 served 3552/3562 tokens from r1's cache), r2/r3 share 3, r3/r4 share 21, and
  **r4-r10 are identical** (patch md5 f8ee19b9, a different correct patch from the interleaved persistent cell's
  520618d6, and 0 shared messages with that cell's fixed point). Prefill steps (≥ 1 block missed, from
  `cached_tokens`): 44/44, 22/25, 20/24, 2/24, then 0/24 ×6: from r5 on the server computes nothing but the
  partial tail block. Same shape as the interleaved cell (0/10 → convergence to a self-reproducing correct route),
  reached faster (fixed point at r4 vs r6) because no other task's blocks sit between consecutive runs and r1 starts
  from a genuinely cold cache (the interleaved r1 had hit 112 system-prompt tokens left by another task and already
  differed from the per-run route at message 10). Regimes on this task now: per-run servers 0/10, persistent + flush
  0/10, persistent interleaved 9/10, persistent alone 9/10 (two different correct fixed points).
- **Why:** a clean persistent contrast for the sklearn-11578 figures (KV occupancy / prefix-cache hits / prefill per
  step, `scripts/maintenance/plot_kv_timeline.py`): consecutive runs of the same task on one server, with nothing
  else in the cache, so run k+1's hits come only from run k.
- **What:** `SERVER_LIFECYCLE=persistent` with `R2_MODEL=devstral2507-serial-11578only` (the default
  `devstral2507-serial` dir already held 11578 r1-r10 and would have skipped everything), task list
  `task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json`; otherwise the persistent recipe (one server,
  TP=8, caching ON, one run per cycle, `MAX_WORKERS=1`, SU-free at 15k, temperature 0, eval after every run).
- **Launch (used):**
  `SERVER_LIFECYCLE=persistent R2_MODEL=devstral2507-serial-11578only TASKS_FILE=$PWD/task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial-11578only -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`

### Devstral-Small-2507 — sklearn-11578 ×10 on ONE persistent server with the prefix cache flushed between runs (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-18 20:00:09 → 21:44:50 CDT (1 h 45 min, 10 cycles; one server, ready in 50 s; 10
  prefix-cache resets, each confirmed by the server log; final clean-up ran, nothing left; launched by the user; log
  `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-serial-flush_20261018_200009.log`). Requested as
  "reset_prefix_cache を sklearn-11578 に対してだけやりたい。10 runs".
- **Result (`data/r2/swebench/p30s/devstral2507-serial-flush/di__b15k__su-free/`, 10 rows):** **0/10** (Submitted ×10,
  42-195 calls, 1-10 compressions). **All 10 runs are message-for-message identical to the per-run rows through
  message 74 (the first 37 commands, up to `pip install numpy==1.12.0 ...`) and diverge only at message 75, the pip
  output with random temp-dir names** — exactly the per-run picture. Against the persistent (unflushed) rows they
  differ at message 2, the first assistant message (0 shared commands). 9 of 10 runs submit the same wrong patch as the
  per-run rows (md5 d9f74121; r6 another). So the flush restores the cold-cache fixed point completely: **the whole
  persistent-server effect on this task (0/10 → 9/10, a different route from the first reply) is carried by the
  prefix cache; nothing else on the live server (allocator / cuBLAS warm state, scheduler) contributes.** This is the
  agent-level confirmation of the probe's `off2` = `on_cold` result (40/40, Δlogprob 0). Regimes on this task:
  per-run servers 0/10, persistent + flush 0/10, persistent 9/10, 8 workers 2/3.
- **Why:** sklearn-11578 is the task whose outcome flipped with the server regime (per-run servers 0/10 on one
  identical wrong route; persistent server 9/10 on one identical correct route, see the two entries below). If the
  flipped behaviour is carried by the prefix cache alone, flushing it between runs on a persistent server should
  reproduce the per-run rows (37 identical leading commands, the `pip install numpy==1.12` route, 0/10); if the
  flushed rows look like the persistent ones, something else on the live server (cuBLAS / allocator warm state, ...)
  carries it. The probe (`off2` = `on_cold`, 40/40, Δlogprob 0) predicts the former.
- **What:** `KV_FLUSH=prefix-cache` in the persistent mode of `run_r2_swe_sandbox_isolated.sh`: after every cycle's
  container purge, `POST /reset_prefix_cache`; the driver requires HTTP success and a new "Successfully reset prefix
  cache" line in the server log, else it stops. The wrapper exports `VLLM_SERVER_DEV_MODE=1` for that mode (the
  endpoint is 404 otherwise). Everything else as the persistent cell: one server (TP=8, caching ON, so the run's own
  self-hits remain), one run per cycle, `MAX_WORKERS=1`, SU-free at 15k, temperature 0, 10 runs. Task list
  `task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json` (1 task).
- **Dest:** `data/r2/swebench/p30s/devstral2507-serial-flush/di__b15k__su-free/` (10 rows when complete).
- **Launch (no server running; the driver starts it):**
  `KV_FLUSH=prefix-cache SERVER_LIFECYCLE=persistent TASKS_FILE=$PWD/task_lists/swe_verified/sandbox_devstral2507_sklearn11578.json AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial-flush -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`
  (from the repo root; `SLACK_WEBHOOK_URL` exported or `ALLOW_NO_SLACK=1`).
- **Estimate:** ~1 h (persistent 11578 runs took 2-6 min each; per-run ones 4-9 min) plus the 60 s server start.
- **Check afterwards:** `grep -c "Successfully reset prefix cache" logs/servers/vllm_devstral2507_prefixcache.latest.log`
  should be 10; compare events.jsonl of the 10 rows with the per-run rows (identical through the pip step?) and with
  the persistent rows.

### Devstral-Small-2507 — serial 6-task SU-free cell on ONE persistent server, 10 runs/task (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-18 12:09:11 → 19:47:16 CDT (7 h 38 min, 60 cycles, 7.6 min/cycle; agent e2e sum
  5.9 h, mean 5.9 min, median 2.9, max 28; one server for the whole plan, up 12:10:13, stopped by the final clean-up;
  no containers left; log `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-serial_20261018_120911.log`).
- **Results (`data/r2/swebench/p30s/devstral2507-serial/di__b15k__su-free/`, 60 rows, all evaluated; Submitted 52,
  LimitsExceeded 8):**

  | task | persistent server 10 runs | per-run servers 10 runs | calls (persistent) | compression events | distinct trajectories (events.jsonl) |
  |---|---|---|---|---|---|
  | django-15368 | 10/10 | 10/10 | 27-53 | 0 ×9, 1 | 8 (largest identical group 3) |
  | sklearn-11578 | **9/10** | **0/10** | 26-37 | 0 ×6, 1 ×3 | 6 (r6-r10 identical) |
  | sklearn-13135 | 8/10 (1 LimitsExceeded) | 10/10 | 20-300 | 1-7 | 10 |
  | django-11734 | 0/10 (5 LimitsExceeded) | 0/10 | 50-300 | 1-18 | 10 |
  | django-15525 | 0/10 (1 LimitsExceeded) | 0/10 | 38-300 | 0-11 | 10 |
  | sklearn-14087 | 0/10 (1 LimitsExceeded) | 0/10 | 30-300 | 1-7 | 10 |

- **Reading:** the resolved/unresolved split is the same 3/3 as per-run, but sklearn-11578 flips from 0/10 (one
  identical wrong patch, the "pip install numpy==1.12" route) to 9/10 (r2-r10 all submit the same correct patch;
  r6-r10 are message-for-message identical), and sklearn-13135 loses its determinism (28 calls, no compression ×10
  per-run → 20-300 calls, 1-7 compressions, 10 distinct trajectories). Pairwise first differing message between
  persistent runs is an **assistant** message in 4 of 6 tasks (15368: 42 of 45 pairs, 11578: 35, 13135: 45, 11734:
  45), i.e. model-side; per-run it was a tool observation in every task. 15525 (all 45 pairs) and 14087 (36 of 45)
  still diverge first at the `ls -la` mtime of step 1. The very first cycle (15368 r1, pristine server) is identical
  to the per-run trajectory; the second (11578 r1, after one run of another task) already differs from per-run at the
  first assistant message, so cached system-prompt blocks from any earlier request suffice to move greedy decoding onto
  a different path. Per-run and persistent are therefore two deterministic regimes (cold vs warm prefix cache) with
  different fixed points, not a noisy vs quiet one. Command-level agreement for 11578: per-run pairs share 37 leading
  commands (set Jaccard 0.58), persistent pairs 13 (0.56), per-run vs persistent 0 (0.11). For the three never-resolved
  tasks the two regimes share only 3-5 leading commands and the same target files (14087: `logistic.py` in all runs;
  15525: `testbug/models.py`), with 11734 taking a longer route under the persistent server (median 270 vs 184 calls,
  5 vs 1 LimitsExceeded, `sql/query.py` instead of the tests file / `expressions.py`).
- **Next (proposed, not built yet):** `KV_FLUSH=prefix-cache` for the persistent mode — `POST /reset_prefix_cache`
  (server started with `VLLM_SERVER_DEV_MODE=1`) after every cycle's purge, dest `devstral2507-serial-flush`. If those
  rows reproduce the per-run ones (15368 bit-identical ×10, 11578 back on the 0/10 route), the whole persistent-server
  effect is the prefix cache; the probe's off2 = on_cold (40/40, Δlogprob 0) predicts that it is.
  Requested as
  "isolation のところでサーバーの kill と restart の部分だけを変えて、サーバーは常駐で concurrent な run は 1 つだけ".
- **What:** the same driver and wrapper as the isolated cell below with `SERVER_LIFECYCLE=persistent`: the
  Devstral-2507 server (TP=8, caching ON) is started once before cycle 1 and stopped once on exit; every cycle is
  still exactly one (task, run) with `MAX_WORKERS=1`, eval, then the container purge (+ orphaned conmon reaping). The
  driver stops, and never restarts the server, if it is gone between cycles. Same 6 tasks, 10 runs/task, SU-free
  only (60 keys), run-major order, temperature 0, agent config `configs/config-devstral2507-vllm.yaml`. The only
  difference from the per-run rows is therefore the shared live server: with caching ON, run k of a task hits the
  prefix blocks run k-1 (and the other tasks' runs) left in the cache, and the scheduler / compiled state carries
  over; `PREFIX_CACHE=off` removes the cross-run cache hits (dest `devstral2507-serial-nocache`).
- **Dest:** `data/r2/swebench/p30s/devstral2507-serial/di__b15k__su-free/` (60 rows when complete).
- **Launch (no server running; the driver starts it):**
  `SERVER_LIFECYCLE=persistent AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-serial -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`
  (`SLACK_WEBHOOK_URL` exported or `ALLOW_NO_SLACK=1`). Plan only: prepend `DRY_RUN=1` (60 pending as of 12:01 CDT).
- **Estimate:** ~7 h (the per-run cell took 8.7 min/cycle of which ~60 s was the server start; cross-run prefix hits
  may shave a little more).
- **Verification:** new unit test `test_persistent_server_is_started_once_and_runs_stay_serial` (one start, one stop,
  serial runs with 1-task lists, purge between runs, stop when the server dies) plus the existing suite: 24 passed
  (2026-10-18 12:05 CDT); per-run and pilot dry runs unchanged.
- **Comparison target:** the per-run rows below (15368 / 13135 bit-identical ×10; 11578 / 11734 / 15525 / 14087
  diverging only at nondeterministic tool outputs). Question: does a shared live server add model-side divergence
  (first differing message = assistant) on top of that?

### Devstral-Small-2507 — isolated 6-task cells: SU-free → TR, 10 runs/task, one run per fresh server (SWE-bench) — Albus

- **Status:** ✅ COMPLETE (SU-free cell) 2026-10-17 20:35:22 → 2026-10-18 05:10:22 CDT: 59 cycles in 8 h 35 min
  (8.7 min/cycle; agent e2e sum 5.8 h, mean 5.8 min, median 3.5, max 29.4; server ready in 50-60 s per cycle; the rest
  is eval + purge). Relaunched by the user with `CELLS="di__b15k__su-free:summarization-free:0.5"` after the first
  launch (20:24:05, both cells) was killed 20:32 at their request to drop TR ("TR はやらなくていい"; cycle 1 django-15368
  r1 from that launch is row 1 of the cell; the kill left 74 orphaned `conmon` processes of the force-removed
  container, terminated by hand, and `purge_containers` now reaps them itself via `reap_conmon`). Final clean-up ran
  (no server, no containers); machine idle. Log
  `logs/experiments/r2_swebench_sandbox_isolated_p30s-devstral2507-iso_20261017_203521.log`. TR not run (add
  `d05__b15k__tr:truncation:0.5` to `CELLS` and rerun the same command if wanted; recorded keys are skipped).
- **Results (`data/r2/swebench/p30s/devstral2507-iso/di__b15k__su-free/`, 60 rows, all evaluated):**

  | task | isolated 10 runs | 8-worker 3 runs | isolated calls | compression events | note |
  |---|---|---|---|---|---|
  | django-15368 | **10/10** | 3/3 | 30 ×10 | 0 ×10 | all 10 runs message-for-message identical, 1 patch |
  | sklearn-13135 | **10/10** | 3/3 | 28 ×10 | 0 ×10 | all 10 runs identical, 1 patch (8-worker: 21-54 calls, 1-3 compressions) |
  | sklearn-11578 | **0/10** | 2/3 | 42-86 | 1-3 | identical through step 37; 1 distinct (wrong) patch |
  | django-11734 | **0/10** | 0/3 | 114-300 | 3-11 | identical through step 95; 1 LimitsExceeded; 4 empty patches |
  | django-15525 | **0/10** | 0/3 | 30-132 | 0-3 | identical through step 1; 10 distinct patches |
  | sklearn-14087 | **0/10** | 0/3 | 30-300 | 1-17 | identical through step 1; 2 LimitsExceeded; 2 empty patches |

  Exit statuses: Submitted 57, LimitsExceeded 3. Outcomes are fully bimodal per task (10/10 or 0/10); no task is
  split. sklearn-11578, 2/3 under 8 workers, is 0/10 in isolation.
- **Where the run-to-run differences come from (events.jsonl, pre-compression):** in every task the first message
  that differs between two isolated runs is a **tool observation, never an assistant message**: django-15525 and
  sklearn-14087 at step 1 (`ls -la` shows the mtime of `..`, i.e. the container's creation time, 10 distinct values
  in 10 runs); django-11734 at step 96 (an `ls -la` mtime of a test file); sklearn-11578 at step 37 (`pip install
  numpy==1.12.0 ...` output with random `/tmp/pip-install-xxxx` paths; its run_1 instead restarted the agent
  conversation at that step — a second system prompt with seq 1 in events.jsonl, 53 api calls in total — cause not
  dug into). django-15368 and sklearn-13135 never print a timestamp and are bit-identical ×10. So **in isolation,
  Devstral-2507 at temperature 0 is reproducible token for token; all within-task variance is environment
  nondeterminism (timestamps, temp-dir names) amplified by greedy decoding afterwards.** The 8-worker rows differ
  from the isolated path already at the **first assistant message** for sklearn-13135 (all 3 runs), sklearn-14087
  (all 3) and django-15368 (run 1): concurrent batching changes greedy outputs from step 1, and the 1-3 compression
  events the 8-worker sklearn-13135 runs needed were themselves a consequence of that divergence (isolated: 28 calls,
  no compression). Note for the sandbox design: the two SU-free "positives" never trigger compression in isolation,
  so this cell says nothing about SU-free on them; the 4 negatives compress 1-17 times and never resolve.
  Follow-up to the
  20-task cells below: "これを 10 runs/task にして、isolated と同じ、run ごとにコンテナも消すし 1 run のみ".
- **Tasks:** `task_lists/swe_verified/sandbox_devstral2507_sufree3_never3.json` (6 = the 3 tasks resolved in ≥2 of 3
  SU-free runs — django-15368, sklearn-11578, sklearn-13135 — plus 3 of the 11 tasks at 0/3 under both SU-free and TR
  — django-11734, django-15525, sklearn-14087 — chosen so that compression fires in every run, runs stay under ~30 min
  when Submitted, repos 3/3 and Qwen P30S outcomes mix; selection notes in `task_lists/README.md`). Note that
  django-15368 was resolved without a single compression event in all 6 of its runs.
- **What:** `scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh` → `run_r2_swe_sandbox_isolated.sh`
  with the new `INNER=p30s` mode (inner launcher `run_r2_swe_p30s.sh` instead of the capped pilot): for every pending
  (cell, task, run) key, start a fresh Devstral-2507 server (`start_vllm_devstral2507_sandbox.sh`, TP=8, **caching ON**
  by default, `PREFIX_CACHE=off` → `devstral2507-iso-nocache`), wait for `/v1/models`, run the one task with
  `RUNS_PER_TASK=<run>` and `MAX_WORKERS=1` (recorded keys skipped → exactly that run), eval, stop the server, remove
  every container; watchdog / traps / busy guards as in the Qwen isolated cells. Cells `di__b15k__su-free` then
  `d05__b15k__tr`, 10 runs/task, **run-major order** (run 1 of all 6 tasks, then run 2, ...), agent config
  `configs/config-devstral2507-vllm.yaml` (temperature 0, max_tokens 4096, step limit 300), model tag
  devstral-small-2507, runner defaults (timeout 5400 s). 120 keys in total.
- **Dest:** `data/r2/swebench/p30s/devstral2507-iso/{di__b15k__su-free,d05__b15k__tr}/` (section p30s because the 6
  tasks ⊂ P30S; the model dir keeps them apart from the 8-worker `devstral2507` cells). Per-run one-task lists in
  `logs/experiments/isolated_tasks/devstral2507-iso/`.
- **Launch (the driver starts the server itself; the 20-task cells' server was already stopped by hand 19:5x CDT, so
  the initial clean-up finds nothing):**
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p30s-devstral2507-iso -- bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`
  (`SLACK_WEBHOOK_URL` exported or `ALLOW_NO_SLACK=1`). Plan only: `DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_devstral2507.sh`.
  SU-free only: prepend `CELLS="di__b15k__su-free:summarization-free:0.5"`. Resume = rerun the same command.
- **Estimate:** server ready ~60 s after start (weights cached); the 8-worker rows of these 6 tasks averaged 14 min
  e2e (SU-free) and 20 min (TR) and single-worker runs are faster, so ~10-15 min per cycle incl. eval: ~12 h SU-free
  (+ ~15 h if TR is added later), i.e. 1-1.5 days for both (the 20-task cells ran 1.6x over their estimate; the long tail of LimitsExceeded runs,
  up to 90 min, is the risk here too).
- **Verification:** `DRY_RUN=1` on the real tree prints 120 pending keys in run-major order; the refusals (PATTERNS /
  SUMMARIZER / wrong section / malformed CELLS / CYCLE_ORDER / PREFIX_CACHE) exit 1 before anything starts; the pilot
  mode (`run_r2_swe_sandbox_isolated_fc_only4.sh` dry run) is unchanged; new unit test
  `test_inner_p30s_runs_plain_cells_one_run_per_server` in `tests/test_r2_adaptive_launch.py` drives the driver with
  fakes through 7 cycles; `uvx --with pyyaml pytest tests/test_r2_adaptive_launch.py tests/test_r2_isolated_cleanup.py`: 23 passed (2026-10-17 19:40 CDT).

### Devstral-Small-2507 — P30S first-20 sandbox cells: SU-free → TR, caching ON (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-17 10:20:51-18:33:54 CDT (relaunched by the user at temperature 0 after the
  0.2 false start below; notify_run wrapper 2969842). Both cells have 60/60 rows, evaluated; no runner processes
  left. Wall time 8 h 13 min (SU-free 10:20-14:25 = 4 h 05 incl. eval; TR 14:25-18:33 = 4 h 08), **~1.6x the 5 h
  estimate**: mean e2e 17.3 min/run (SU-free) and 19.5 (TR), medians 9.2 / 6.8, max 83 / 90 min, i.e. a long tail
  of LimitsExceeded / near-timeout runs dominates. Log `logs/experiments/r2_swebench_p30s_devstral2507_20261017_102051.log`.
  The caching-ON Devstral server (pid 2900059, up since 09:57) was stopped 2026-10-17 19:5x CDT at the user's request
  before the isolated cells (entry above); GPUs idle, port 8000 free, no pid files, no containers.
- **Results (first 20 of P30S, 3 runs each, temperature 0):**

  | cell | resolved runs | ≥2/3 tasks | 1/3 tasks | 0/3 tasks | exit statuses |
  |---|---|---|---|---|---|
  | `di__b15k__su-free` | 12/60 (20.0%) | 3 | 4 | 13 | Submitted 53, LimitsExceeded 7 |
  | `d05__b15k__tr` | 13/60 (21.7%) | 5 | 2 | 13 | Submitted 41, LimitsExceeded 17, Timeout 2 |

  ≥2/3 tasks: SU-free django-15368 (3/3), sklearn-11578 (2/3), sklearn-13135 (3/3); TR django-15368 (3/3),
  sklearn-11578, -13135, -13439, -13779 (2/3 each). 1/3 tasks: SU-free django-12276, django-15741, sklearn-13439,
  sklearn-14053; TR sklearn-14053, sklearn-14894. 0/3 in both cells (11 tasks): django-11734, -12304, -15098, -15278,
  -15525, -15957, -17084, sklearn-12682, -14087, -25232, -26194; additionally 0/3 in SU-free only: sklearn-13779,
  sklearn-14894; in TR only: django-12276, django-15741. No LimitsExceeded / Timeout run resolved. The two TR
  timeouts (5400 s): django-15278 run_3, django-15957 run_2. Only 10 of 20 tasks were ever resolved in either cell;
  django 1/10 tasks (15368) vs scikit-learn 5/10 resolved at least twice. At temperature 0, 6 of 20 tasks (SU-free)
  and 6 of 20 (TR) are still split across the 3 runs (neither 0/3 nor 3/3), so greedy did not remove run-to-run
  variance (probe entry below explains why). Compare Qwen3.5-35B-A3B P30S at 15k, TR 16/30 (53%) on the full 30:
  Devstral-2507 at ~21% on these 20 is far below its published 53.6% SWE-bench Verified (OpenHands scaffold) and
  below Devstral-2's 56% TR@21k in this project; budget 15k was not re-calibrated for it and mini-swe-agent's bash-only
  scaffold is a different setting from OpenHands, so the gap is not interpreted yet.
- **False start (same day):** the user's first launch at 10:11:14 CDT was killed at 10:13:4x at their request; it had
  used temperature 0.2 (the launch preceded the config change to 0 at 10:12:10). 1 recorded row (django-12276 run_3)
  and 9 run dirs were moved to `data/r2/swebench/p30s/devstral2507-aborted-t02-20261017/` so the relaunch started
  from scratch (only `-smoke` dirs are skipped by `analysis/aggregate_benchmark_results.py` /
  `dashboard/build_coverage.py`, so delete it with `rm -r` if not wanted). Log
  `logs/experiments/r2_swebench_p30s_devstral2507_20261017_101114.log`.
- **Originally:** prepared 2026-10-17 for "caching ON で Devstral 1 を 3 runs/task で 20 タスク、SU-free と TR".
- **What:** `scripts/expansions/run_r2_swe_p30s_devstral2507.sh` (new wrapper over `run_r2_swe_p30s.sh`): section
  `p30s`, first 20 tasks of `task_lists/swe_verified/p30_stratified.json` (`N_TASKS=20`), 3 runs/task, cells
  `di__b15k__su-free` (summarization-free, agent model as summarizer) then `d05__b15k__tr` (truncation, depth 0.5),
  budget 15k (the P30S section budget; Devstral-2's calibrated 21k was not re-calibrated for 2507), 8 workers
  (`AGENTCTX_PROFILE=albus-swe`), eval after each cell. Agent config `configs/config-devstral2507-vllm.yaml` (new:
  port 8000, max_tokens 4096, litellm timeout 600, **temperature 0**, step limit 300; no thinking, so no cap/nothink
  variants). Runner defaults otherwise (agent timeout 5400 s, retry attempts 10).
- **Server:** `AGENTCTX_PROFILE=albus-swe PREFIX_CACHE=on bash scripts/serving/start_vllm_devstral2507_sandbox.sh`
  (TP=8, 131072 context, caching ON; log/pid `vllm_devstral2507_prefixcache`). The wrapper refuses to start unless
  port 8000 serves `mistralai/Devstral-Small-2507` with `enable_prefix_caching="True"` (`REQUIRE_PREFIX_CACHE=off|any`
  overrides). Caching ON is deliberate for this model: see the probe entry below (ON with no hit is bit-identical to
  OFF; hits perturb numerics no more than a server restart). The wrapper was syntax-checked only (not executed, not
  smoke-tested); the cells and the env overrides are the ones `run_r2_swe_p30s.sh` already documents.
- **Launch (after the server answers `/v1/models`):**
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/p30s/devstral2507 -- bash scripts/expansions/run_r2_swe_p30s_devstral2507.sh`
  (`SLACK_WEBHOOK_URL` exported, or add `ALLOW_NO_SLACK=1`). TR only: prepend `CELLS="d05__b15k__tr:truncation:0.5"`.
  **Temperature 0** (the user's choice, 2026-10-17; changed from the 0.2 of every other agent config, so these
  cells are not temperature-matched to the Qwen P30S reference cells). Greedy is not bit-reproducible under cache
  hits / restarts / batching (probe below), so runs will still differ.
- **Dest:** `data/r2/swebench/p30s/devstral2507/{di__b15k__su-free,d05__b15k__tr}/` (60 rows each). Logs:
  `logs/experiments/r2_swebench_p30s_devstral2507_<ts>.log` (notify_run) and `r2_sb_p30s_devstral2507_<ts>.log`.
- **Estimate:** ~2.5 h SU-free + ~2 h TR including eval (Devstral-2 on Dobby: TR mean 5.3 min/run, SU-full 6.3;
  Albus ~1.4x slower for Qwen, plus margin for bf16 prefill at ~500 tok/s per request); roughly 5 h for both.
- **Reference numbers to compare against:** Qwen3.5-35B-A3B P30S at 15k (`data/r2/swebench/p30s/qwen35b/`): TR 16/30
  resolved, FC 18/30 (3 runs each, see the top of this file); Devstral-2 P100 FC@∞ 55.7%, TR@21k 56%.

### Devstral-Small-2507 — prefix-cache effect probe before a Devstral sandbox (SWE-bench) — Albus

- **Status:** ✅ COMPLETE 2026-10-17 02:31-09:35 CDT (Claude, at the user's request: "本当に prefix cache の on/off で
  ブレないか、Qwen3.5-35B の時みたいに検証して欲しい"). Not an experiment run; the GPUs were idle before and are idle
  again (all servers stopped, no pid files).
- **Why Devstral-Small-2507:** the user wants a second sandbox model that is dense (no MoE), bf16 as distributed
  (Devstral-Small-2-24B-2512 is FP8 in the official checkpoint, `quantization_config.quant_method=fp8`, served on
  Albus as weight-only FP8 Marlin), full attention only (no linear-attention / sliding-window hybrid, so prefix caching
  is the textbook kind) and close to Qwen3.5-35B-A3B on SWE-bench Verified (this project's FC@∞ P100 ×3: Qwen 53.0%,
  Devstral-2 55.7%, GLM-4.7-Flash 41.0%; Devstral-Small-2507 reports 53.6% with OpenHands). Qwen3-32B (23% OpenHands,
  15% mini-SWE-agent on 100 tasks) and Qwen2.5-Coder-32B (6-14%) were rejected as too weak; Seed-OSS-36B (56%) kept
  as the alternative.
- **Weights:** `mistralai/Devstral-Small-2507` HF-format shards (10 × ~4.8 GB bf16, `model-*.safetensors` +
  `config.json`, `params.json`, `tekken.json`; the duplicate 47 GB `consolidated.safetensors` was not fetched),
  downloaded 2026-10-17 into the HF cache (`logs/downloads/devstral2507_*.log`). Only `tekken.json` ships, so vLLM
  0.17.1 picks `tokenizer_mode=mistral` by itself (`vllm/tokenizers/registry.py`).
- **Server:** `scripts/serving/start_vllm_devstral2507_sandbox.sh` (new): port 8000, TP from `AGENTCTX_PROFILE`
  (albus-swe = 8), dtype auto, max-model-len 131072, 64 seqs, `--enable-prompt-tokens-details`, KV trace;
  `PREFIX_CACHE=off` (default, `--no-enable-prefix-caching`, log/pid `vllm_devstral2507_noprefixcache`) or
  `PREFIX_CACHE=on` (`vllm_devstral2507_prefixcache`). No reasoning / tool-call parser.
- **Probe:** `scripts/maintenance/probe_prefix_cache_effect.py` now takes the model id from `/v1/models` and
  `--prompts-from`, so Devstral is probed on the **same 40 agent prompts** as the Qwen probe of 2026-10-09
  (`data/r2/probes/prefix_cache_effect/prompts.json`: message prefixes of infra-clean runs of the 4 sandbox tasks,
  median 34k chars). Same protocol: greedy (temperature 0, seed 0), 512 tokens, one request at a time, each prompt
  twice per server, idle server. Output `data/r2/probes/prefix_cache_effect_devstral2507/{prompts,off,on}.json`,
  `rows.csv`. Commands:
  `AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_devstral2507_sandbox.sh` →
  `venv/bin/python scripts/maintenance/probe_prefix_cache_effect.py --out data/r2/probes/prefix_cache_effect_devstral2507 collect --label off --prompts-from data/r2/probes/prefix_cache_effect/prompts.json` →
  `bash scripts/serving/stop_vllm.sh logs/servers/vllm_devstral2507_noprefixcache.pid` →
  `AGENTCTX_PROFILE=albus-swe PREFIX_CACHE=on bash scripts/serving/start_vllm_devstral2507_sandbox.sh` →
  `... collect --label on` → `... compare off on --csv data/r2/probes/prefix_cache_effect_devstral2507/rows.csv`.
- **Reference (Qwen3.5-35B-A3B, 2026-10-09):** OFF vs OFF 40/40 identical, ON vs ON 39/40, **OFF vs ON 11/40**,
  median first divergence token 30. A dense full-attention model should come out at the noise floor.
- **Result (40 prompts × 2 passes per server, greedy, 512 tokens; `rows.csv`, `rows_on_cold.csv`):**

  | pair | identical | first divergence (median token) | mean abs Δlogprob on common prefix |
  |---|---|---|---|
  | off pass1 vs off pass2 (same server) | 40/40 | — | 0.0000 |
  | off vs on pass1 (partial cache hits) | 32/40 | 30.5 | 0.0048 |
  | off vs on pass2 (full-prefix hits, 99.9% cached) | 27/40 | 38 | 0.0052 |
  | on pass1 vs on pass2 | 28/40 | 49.5 | 0.0042 |
  | **off vs on_cold** (ON engine, `/reset_prefix_cache` before every request, 0 cached) | 34/40 | 54.5 | 0.0046 |
  | **off vs off2** (a second, freshly started OFF server) | 34/40 (the same 6 prompts) | 54.5 | 0.0046 |
  | **off2 vs on_cold** | **40/40** | — | **0.0000** |

  Reading: the caching-ON engine with no cache hit is bit-identical to a caching-OFF engine (off2 vs on_cold 40/40,
  Δlogprob 0); the 6 prompts on which the first OFF server disagreed with both are process-to-process numerical
  drift (kernel/autotune selection at startup), not the cache. Serving a prefix from the cache instead of
  recomputing it does change the numerics slightly (Δlogprob ≈ 0.005, max 0.13), which flips greedy argmax at
  near-tie tokens on 8-13/40 prompts, mostly long generations (median 268 tokens for prompts that ever diverged vs
  45 for those that never did); no prompt diverges at token 0 (Qwen: 4/40). This is the same magnitude as the
  OFF-instance-to-OFF-instance drift, and far below the production temperature 0.2 sampling noise. Contrast
  Qwen3.5-35B-A3B (hybrid): OFF vs ON 11/40 while ON vs ON was 39/40, i.e. the cache changed the computation path.
  **Decision input:** for Devstral-Small-2507 prefix caching does not change the model's computation; caching ON
  is a numerics-level perturbation equal to restarting the server. Either setting is defensible for a Devstral
  sandbox; keep OFF only if the argument "identical engine path to the Qwen sandbox" matters more than the
  ~2x per-call latency (median pass1 18.5 s OFF vs 8.2 s ON with partial hits at TP=8, 1 request at a time).
- **Servers used:** OFF pid 2475935 (02:31-03:11, log `vllm_devstral2507_noprefixcache_20261017_023110.log`), ON pid
  2523931 (03:11-08:44), ON with `VLLM_SERVER_DEV_MODE=1` pid 2822475 (08:44-09:09, for `/reset_prefix_cache`), OFF
  pid 2852581 (09:09-09:35). KV cache 1,934,992 tokens at TP=8 / 131072 context; weights bf16, `quantization=None`,
  `MistralForCausalLM`, 40 layers, 8 KV heads, no sliding window; vLLM picked the mistral tokenizer (tekken.json).
- **Next (not launched):** a Devstral sandbox needs an agent config (`configs/config-devstral-vllm.yaml` points at
  port 8002 / Devstral-2; a cap4k-style copy on port 8000 for 2507) and a pilot dest model dir; `SUMMARIZER=nothink`
  does not apply (no thinking). Decide first whether the 2507 FC@∞ rate on P100 is close enough to Qwen's 53%.

### Qwen3.5-35B-A3B — controlled-sandbox pilot: SU-free majority (sss) with runaway guards (SWE-bench) — Albus
- **Status:** ✅ COMPLETE (relaunch, caching OFF, 3 workers, timeout 600 s, agent 7200 s): launched 2026-10-09 23:15:38 CDT,
  agent + eval finished **2026-10-10 13:41:08 CDT** (14.4 h). 60/60 runs evaluated: **44 resolved** (django-11299 14/15,
  sklearn-10908 11/15, sklearn-11310 10/15, sklearn-25102 9/15) vs 39/60 on the same 4 tasks in the uncapped `qwen35b`
  cell (13/12/8/6). `tag_run_failures.py`: 7 infra / 9 model failures (uncapped on these tasks: 15 infra / 6 model),
  wasted 1.9 h vs 8.8 h. Non-Submitted exits: 3 LimitsExceeded (300 steps), 1 Timeout (sklearn-25102 run_4 hit the
  7200 s agent limit at 242 calls). 6,978 agent calls: latency p50/p90/p99/max 9.9/26.8/82/421 s, 0 litellm timeouts,
  38 calls (0.5%) at the 4,096 cap. Summary fallback 45/228 (20%) vs 21/207 (10%) uncapped: the cap now cuts the
  summarizer too (61 `truncated` rejections vs 6), while `missing_marker` is unchanged (164 vs 166). Output:
  `data/r2/swebench/p100_su_free_majority/qwen35b-cap4k/d05__b15k__adaptive-prefix3-sss/` (+ `failure_tags.csv`).
- **✅ COMPLETE (user-launched 2026-10-10 15:54:43 CDT, agent + eval finished 2026-10-11 03:07:00 CDT, 11.2 h; caching-OFF server, 3 workers):** summarizer-only
  thinking OFF cell `qwen35b-cap4k-sumnothink` (agent cap4k config, summary requests via
  `configs/config-summary-qwen35-35b-nothink.yaml`, `MSWEA_SUMMARY_MAX_ATTEMPTS=2`; provenance recorded in every row).
  Result: 60/60 evaluated, **48 resolved** (django-11299 15/15, sklearn-10908 11/15, sklearn-11310 9/15, sklearn-25102 13/15)
  vs 44/60 (cap4k) and 39/60 (uncapped); all 60 `Submitted` (no Timeout / LimitsExceeded). `tag_run_failures.py`: 4 infra
  (all = a capped agent call in a run that still submitted) / 8 model, wasted 1.2 h (cap4k 1.9 h). 5,523 agent calls, 25 capped,
  0 >=600 s. Summarizer: 179 events, 28 fallbacks (16%; cap4k 20% with 5 attempts), 211 attempts with 60 rejections
  (39 missing_marker, 20 truncated, 1 missing_close_marker) vs 470 attempts / 287 rejections in cap4k; summarizer time
  2.5 h = 9% of the 27.5 h e2e (cap4k 8.3 h = 22% of 37.8 h). Output `.../qwen35b-cap4k-sumnothink/d05__b15k__adaptive-prefix3-sss/`
  (+ `failure_tags.csv`). Log
  `logs/experiments/r2_swebench_majority_capped_qwen35b-cap4k-sumnothink_20261010_155443.log`.
- **✅ nothink4k cell COMPLETE (step 1 of the overnight chain; agent + eval finished 2026-10-12 ~02:58 CDT, last run 01:07):** 60/60 evaluated,
  **39 resolved** (django-11299 14/15, sklearn-10908 10/15, sklearn-11310 6/15, sklearn-25102 9/15); 58 `Submitted`, 2 `LimitsExceeded`.
  Same 39/60 as uncapped, below cap4k 44/60 and sumnothink 48/60. First-3-run view: 11/12 (uncapped 11/12, cap4k 8/12, sumnothink 10/12).
  `failure_tags.csv` not yet generated. The chain then started step 2 (`p100_fc_only4`, 8 prefix-3 orders) at 02:58 CDT.
- **Recipe (prepared 2026-10-11): `SUMMARIZER=nothink4k`** = sumnothink with the summarizer reply cap back at 4096
  (`configs/config-summary-qwen35-35b-nothink-4k.yaml`) and the primitive's default 5 attempts, dest `qwen35b-cap4k-sumnothink4k`.
  Why: of sumnothink's 28 fallbacks, 12 began with a reply cut at 2048 tokens (0/12 recovered on the single retry) and 16 with
  missing_marker (3/19 rescued with one retry; uncapped rescued 36/57 with four). In uncapped / cap4k most >2048-token
  summaries completed below 16k chars (4096 tokens), and a thinking-OFF attempt costs ~33 s median, so both limits can go back up.
  Expect fallback near or below uncapped's 10% if ~2/3 of the 2048-overflows finish at 4096. This cell (and any run
  launched from now on) also writes `<run_dir>/summary_attempts.jsonl`: every summarizer reply verbatim with its
  accept/reject verdict, so the truncated / marker-less summaries can be read afterwards. Launch:
  **Overnight chain: RUNNING (user-launched 2026-10-11 15:30:27 CDT, wrapper PID 21392, log
  `logs/experiments/r2_swebench_sandbox_chain_qwen35b-cap4k-sumnothink4k_20261011_153027.log`).** `scripts/expansions/run_r2_swe_sandbox_chain.sh` runs this
  nothink4k cell and then `p100_fc_only4` with all eight prefix-3 orders (ttt tts tst tss stt sts sst sss) on django-11433 and
  sklearn-13124 x 15 runs (240 runs, section limits 400 steps / 7200 s) into `data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink4k/`;
  ~12 h + ~35-40 h. It waits for a capped pilot already running, and every step resumes. Launch:
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_chain/qwen35b-cap4k-sumnothink4k -- bash scripts/expansions/run_r2_swe_sandbox_chain.sh`
  Single-cell launch (step 1 only):
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink4k -- env SUMMARIZER=nothink4k bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh`
- **Chain state observed 2026-10-12 15:09 CDT (nothing changed by this note):** no chain / runner process alive (wrapper 21392 gone).
  `p100_fc_only4/qwen35b-cap4k-sumnothink4k/`: ttt 30/30 rows (1 resolved); tts 3 rows recorded (django-11433 r1, r3, r4; run dirs 1-6
  exist, r2 / r5 / r6 unrecorded), i.e. the tts cell was interrupted around 15:00 CDT. Three `minisweagent-*` containers (started
  14:36-14:54) and the caching-OFF server (pid file `logs/servers/vllm_qwen35_a3b_noprefixcache.pid`) are still up.
- **Prepared 2026-10-12 (not launched): isolated serial driver** `scripts/expansions/run_r2_swe_sandbox_isolated.sh` for the
  contamination check: one run per fresh caching-OFF server and per container generation (start server -> wait for `/v1/models` ->
  capped pilot on a one-task list with `RUNS_PER_TASK=<run>`, `MAX_WORKERS=1`, eval -> `stop_vllm.sh` -> `docker rm -f` every
  container of the user's podman -> check the key is recorded). Its initial clean-up stops the running sandbox server and removes the
  orphan containers. Recipe: `SUMMARIZER` defaults to `nothink` (summarizer reply cap 2048 as in `qwen35b-cap4k-sumnothink`) but with
  `SUMMARY_MAX_ATTEMPTS=5` (that cell used 2; `nothink4k` / `agent` selectable), dest `R2_MODEL` = pilot dir + `-iso` (`qwen35b-cap4k-sumnothink-iso`), so the rows never mix
  with the 3-worker cells; resumable (recorded keys skipped without a restart); refuses to run beside another launcher; a separate watchdog process
  cleans up (pilot group, server, containers) even if the driver itself is SIGKILLed. Launch:
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/qwen35b-cap4k-sumnothink-iso -- bash scripts/expansions/run_r2_swe_sandbox_isolated.sh`
  (`DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated.sh` prints the plan first;
  `SECTIONS=p100_fc_only4 N_TASKS=2 RUNS_PER_TASK=15 PATTERNS="..."` for the step-2 cells). Each run costs one server start extra.
- **✅ isolated cell COMPLETE (user-launched 2026-10-12 15:38 CDT, finished 2026-10-13 14:16 CDT, 60 cycles, exit 0, server stopped and
  containers purged):** `p100_su_free_majority/qwen35b-cap4k-sumnothink-iso/d05__b15k__adaptive-prefix3-sss` 60/60 rows, **46 resolved**
  (django-11299 14/15, sklearn-10908 12/15, sklearn-11310 11/15, sklearn-25102 9/15); 58 `Submitted`, 2 `LimitsExceeded`; mean e2e 18.9 min
  (3-worker sumnothink 27.5 min). Against the 3-worker cells: cap4k 44/60, sumnothink 48/60 (2 summarizer attempts), nothink4k 39/60; the
  isolated 46/60 sits inside that spread, so concurrency shows no detectable effect on the outcome (60-run cells resolve differences
  of ~10 runs at best). Contamination evidence for the 3-worker cells is mechanistic, not this comparison: KV ownership trace of the
  3-worker server (`logs/kv-cache/vllm_qwen35_a3b_noprefixcache_20261009_231228/`) has 0 shared blocks in 167,552 snapshots over 24,130
  requests, and none of the 180 cap4k / sumnothink / nothink4k trajectories mentions the other task's repository (django<->sklearn grep,
  2026-10-12). Log `logs/experiments/r2_swebench_sandbox_isolated_qwen35b-cap4k-sumnothink-iso_20261012_153824.log`. `failure_tags.csv` not yet generated.
- **Prepared 2026-10-14 (not launched): concurrent twin of the isolated cell.** Same recipe as `-iso` (agent cap4k, summarizer
  `config-summary-qwen35-35b-nothink.yaml` = thinking OFF / reply cap 2048, **5 summarizer attempts**, same 4 tasks x 15) but the
  pilot's normal 3-worker operation on one long-lived caching-OFF server, dest `qwen35b-cap4k-sumnothink-conc` (explicit `R2_MODEL`,
  so it does not resume into the 2-attempt `qwen35b-cap4k-sumnothink`). Only the serving condition differs from `-iso`, so
  iso vs conc isolates concurrency; conc vs sumnothink isolates the attempt budget. Expect ~11-12 h wall-clock at 3 workers (sumnothink 11.2 h, nothink4k 11.5 h).
  Albus idle at preparation time (no server, no containers, GPUs empty). Launch (server first, wait for `/v1/models`):
  `AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_qwen35_sandbox.sh`
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink-conc -- env SUMMARIZER=nothink SUMMARY_MAX_ATTEMPTS=5 R2_MODEL=qwen35b-cap4k-sumnothink-conc bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh`
- **✅ conc cell COMPLETE (user-launched 2026-10-14 00:24 CDT, agent + eval finished 14:46 CDT, 14.4 h):**
  `qwen35b-cap4k-sumnothink-conc/d05__b15k__adaptive-prefix3-sss` 60/60, **37 resolved** (django-11299 14/15, sklearn-10908 9/15,
  sklearn-11310 7/15, sklearn-25102 7/15); 57 `Submitted`, 3 `LimitsExceeded`; mean e2e 37.1 min, per-call latency 16.8 s (iso 9.1 s).
  Reading: iso 46/60 vs conc 37/60 is p=0.11 (Fisher), but conc vs sumnothink 48/60 (same 3-worker serving, only the summarizer
  retry budget differs, 5 vs 2) is p=0.044 with conc having FEWER summarizer fallbacks (14/222 = 6% vs 18% in iso), so nominally
  equivalent sandbox cells already differ by ~10 runs: the iso/conc gap cannot be attributed to concurrency, and pooled concurrent
  nothink-2048 (85/120) vs iso (46/60) is p=0.48. `tag_run_failures.py` (failure_tags.csv written for iso, conc, sumnothink):
  conc 9 infra (8 runs with runaway agent calls, 2 at the 300-step limit) + 14 model failures; iso 4 infra (2 agent runaway, 3 summary
  runaway) + 10 model; sumnothink 4 infra (all runaway) + 8 model. The only concurrency-shaped signal is more runaway/limit runs under
  slower concurrent calls (an infra-failure effect, not contamination); the contamination evidence stays the mechanistic one above.
  Log `logs/experiments/r2_swebench_majority_capped_qwen35b-cap4k-sumnothink-conc_20261014_002419.log`.
- **Prepared 2026-10-14 (not launched): neighbour-content probe** `scripts/maintenance/probe_neighbor_content.py`: the direct
  test of information leakage under concurrency, separating neighbour CONTENT from neighbour COUNT. The 40 prefix-cache-probe prompts
  (real agent prompts, greedy, seed 0) are each generated under `alone`, `same` (2 co-scheduled prompts from other runs of the same
  task), `other` (2 prompts from the other repo) and `self` (2 copies of the target), twice each; neighbours are single streaming
  `ignore_eos` requests confirmed decoding before the target is sent and aborted when it finishes (one neighbour prefill per
  condition, coverage recorded; `verify-trace` checks co-residency in the server's KV ownership trace). Reading: equal agreement with
  `alone` across same/other/self (within the repeat noise floor) = content does not enter the generation. Smoke test on 1 prompt
  (8 generations, 2.3 min, caching-OFF server idle after the conc cell): all identical across conditions, coverage 1.00; an earlier
  re-send-loop design was dropped because repeated 8k-token neighbour prefills slowed the target 10x and made the load depend on the
  neighbours' reply length. Cost ~90 min for 40 prompts x 4 conditions x 2 passes (`--conditions alone,same,other` ~70 min); the
  server must be idle (no agent runs). Output `data/r2/probes/neighbor_content/` (gitignored). Launch (server up and idle):
  `venv/bin/python scripts/maintenance/probe_neighbor_content.py collect --label nb1`
  `venv/bin/python scripts/maintenance/probe_neighbor_content.py compare nb1 --csv data/r2/probes/neighbor_content/rows.csv`
  `venv/bin/python scripts/maintenance/probe_neighbor_content.py verify-trace nb1 --trace-dir logs/kv-cache/<server log name>`
- **✅ neighbour-content probe nb1 COMPLETE (user-launched 2026-10-14 15:16 CDT, 89 min, 320 target + 480 neighbour generations on
  the idle caching-OFF server of 00:22):** noise floor 40/40 identical in every condition (alone, same, other, self). **same, other and
  self are token-identical to each other in 80/80** generations (mean |dlogprob| 0.0000), i.e. the neighbours' content, even two copies
  of the target prompt itself, has no effect on the generation. Each of them differs from `alone` in 60/80 (identical 20/80, median
  first divergence token 27.5, min 0, |dlogprob| 0.017): the batch SIZE changes the numerics deterministically, the batch CONTENT does
  not. McNemar discordant pairs same/other 0/0. `verify-trace`: all 320 targets and 480 neighbours found in the KV trace, both
  neighbours resident for 100% of every target's residency (min 1.000), alone targets overlapped nothing (0/80). Latency 7.0-7.7 s in
  every condition. Output `data/r2/probes/neighbor_content/{nb1.json,rows.csv}`, log
  `logs/experiments/probes_neighbor_content_nb1_20261014_151634.log`. This is the direct leakage test to cite alongside the
  0-shared-blocks trace and the cross-repo grep; the iso/conc resolve-rate gap is batch-size numerics plus sampling noise.
- **Prepared 2026-10-14 (not launched): 1-worker shared-server cell** `qwen35b-cap4k-sumnothink-conc1`: the iso recipe (agent cap4k,
  summarizer thinking OFF / reply cap 2048, 5 attempts, same 4 tasks x 15) with `MAX_WORKERS=1` on the long-lived caching-OFF server,
  i.e. the third serving point between iso (fresh server per run, 1 worker) and conc (shared server, 3 workers): batch size 1 like iso,
  server state shared like conc. Explicit `R2_MODEL` so it cannot resume into the other cells. Sequential, so expect ~19 h of agent
  time (iso mean 18.9 min/run) + ~2 h eval = ~21 h. Server of 00:22 up and idle at preparation time. Launch:
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink-conc1 -- env MAX_WORKERS=1 SUMMARIZER=nothink SUMMARY_MAX_ATTEMPTS=5 R2_MODEL=qwen35b-cap4k-sumnothink-conc1 bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh`
- **✅ conc1 cell COMPLETE (user-launched 2026-10-14 17:09 CDT, finished 2026-10-15 11:41 CDT, 18.5 h):** 60/60, **40 resolved**
  (django-11299 14/15, sklearn-10908 10/15, sklearn-11310 7/15, sklearn-25102 9/15); 60 `Submitted`, 0 `LimitsExceeded`; mean e2e 16.6 min,
  per-call latency 8.8 s (iso 9.1 s, conc 16.8 s); 5 infra (all sklearn-11310) + 15 model failures; summarizer fallback 23/173 = 13%.
  Serving-condition series (same recipe): iso 46 (fresh server, 1 worker) / conc1 40 (shared, 1 worker) / conc 37 (shared, 3 workers);
  all pairwise Fisher p >= 0.31 (conc1 vs iso 0.31, conc1 vs conc 0.70). The four nothink-2048 cells (sumnothink 48, iso 46, conc1 40,
  conc 37) are compatible with one resolve rate of 71% (chi2 6.4, df 3, p 0.09; between-cell SD 5.0 runs vs binomial 3.5), so no
  serving condition (server reuse or batch size) is detectably changing the outcome at 60 runs; this matches the neighbour-content
  probe (content has no effect, batch size only perturbs numerics). Log
  `logs/experiments/r2_swebench_majority_capped_qwen35b-cap4k-sumnothink-conc1_20261014_170943.log`; `failure_tags.csv` written.
- **Prepared 2026-10-15 (not launched): isolated cell on the four `p100_fc_only4` tasks** (django-11433, sklearn-13124,
  sklearn-14983, sympy-17318: resolved under full context, never under fixed TR / SU-free), same recipe as the sandbox iso cell
  (fresh caching-OFF server per run, 1 worker, cap4k agent, `SUMMARIZER=nothink` 2048 cap, 5 attempts, prefix3-sss, 15k, d0.5) and
  the section's own 400-call / 7200 s limits; 4 x 15 = 60 cycles. Wrapper `scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh`
  only fixes `SECTIONS=p100_fc_only4 PATTERNS=sss RUNS_PER_TASK=15` and execs the isolated driver (resume / DRY_RUN / guards as there).
  Dest `data/r2/swebench/p100_fc_only4/qwen35b-cap4k-sumnothink-iso/d05__b15k__adaptive-prefix3-sss/` (separate section dir from the
  sandbox iso cell). Existing fc_only4 data for reference: 3-worker `qwen35b-cap4k-sumnothink4k` ttt 1/30 (django-11433 1/15,
  sklearn-13124 0/15, 5 Timeout), e2e 61 min mean, so expect ~45 min per isolated cycle: **~45 h** (RUNS_PER_TASK=10 -> ~30 h).
  Dry run 2026-10-15 15:53 CDT: 60 keys, 0 recorded. The driver's initial clean-up will stop the idle caching-OFF server started
  2026-10-14 00:22 (pid file present) and purge containers. Launch:
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p100_fc_only4-qwen35b-cap4k-sumnothink-iso -- bash scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh`
  (`DRY_RUN=1 bash scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh` prints the plan).
- **Launched 2026-10-15 15:54 CDT by the user with 15 runs/task, KILLED 16:00 CDT (TERM to the driver, clean exit: server stopped,
  container purged, no row recorded; cycle 1 django-11433 r1 had run 3 min):** the user wants 10 runs/task instead. The wrapper's
  default is now `RUNS_PER_TASK=10` (4 x 10 = 40 cycles, ~30 h); the launch command above is unchanged. Log of the killed attempt:
  `logs/experiments/r2_swebench_sandbox_isolated_p100_fc_only4-qwen35b-cap4k-sumnothink-iso_20261015_155430.log`.
- **✅ fc_only4 isolated cell COMPLETE (user-launched 2026-10-15 16:00:59 CDT with RUNS_PER_TASK=10, finished 2026-10-16 04:58 CDT,
  13.0 h for 40 cycles, exit 0, server stopped, containers purged):** `p100_fc_only4/qwen35b-cap4k-sumnothink-iso/d05__b15k__adaptive-prefix3-sss`
  40/40 rows, all `Submitted`, **1 resolved** (sklearn-13124 r3; django-11433 0/10, sklearn-14983 0/10, sympy-17318 0/10). Far faster
  than the 30 h estimate: e2e mean django-11433 27 min, sklearn-13124 20 min, sklearn-14983 7 min, sympy-17318 9 min (3-worker ttt
  rows of the first two took 61 min). `failure_tags.csv` written: infra 14 (django-11433 9/10 runaway-call runs, sklearn-13124 5/10;
  the two easy-looking tasks 0 infra, 20 model failures), no hung / timeout / summary runaway. Reference 3-worker `sumnothink4k` ttt
  cell: 1/30 (django-11433 1/15, sklearn-13124 0/15; 26 infra). So on these tasks the isolated 1-worker serving changes nothing:
  the fc-only tasks stay unresolved under prefix3-sss with 1/40.
- **Prepared 2026-10-16 (not launched): top-up to 15 runs/task** on the same cell: rerun the wrapper with `RUNS_PER_TASK=15`; the
  driver skips the 40 recorded keys (dry run 10:3x CDT: 60 keys, 40 recorded, 20 pending = r11-r15 of each task), ~6.5 h at the
  observed 13 h / 40 cycles. Launch:
  `AGENTCTX_PROFILE=albus-swe RUNS_PER_TASK=15 bash scripts/notify_run.sh --unit r2/swebench/sandbox_isolated/p100_fc_only4-qwen35b-cap4k-sumnothink-iso -- bash scripts/expansions/run_r2_swe_sandbox_isolated_fc_only4.sh`
- **✅ top-up COMPLETE (user-launched 2026-10-16 10:31 CDT, finished 16:52 CDT, 20 cycles in 6.4 h, exit 0, clean):** the cell is now
  60/60 rows (15/task), all `Submitted`, **6 resolved**: django-11433 0/15, sklearn-13124 2/15 (r3, r14), sklearn-14983 1/15 (r13),
  sympy-17318 3/15 (r11, r13, r14). `failure_tags.csv` regenerated (60 rows): infra 22 (django-11433 14 runaway runs, sklearn-13124 8),
  model 32, no hung / timeout. Note: r1-r10 resolved 1/40 and the top-up r11-r15 5/20 (Fisher p = 0.013); serving config
  (`serving_info.json` cache_config identical, 12744 blocks, prefix caching OFF), scripts, configs and code were unchanged between the
  two launches and per-run call counts / compression events / latencies match, so no cause is identifiable beyond chance on 10%-rate tasks.
  Log `logs/experiments/r2_swebench_sandbox_isolated_p100_fc_only4-qwen35b-cap4k-sumnothink-iso_20261016_103113.log`.
- **Prepared 2026-10-10 (recipe):** summarizer-only thinking OFF. `configs/config-summary-qwen35-35b-nothink.yaml`
  (same model and server, thinking OFF, max_tokens 2048) goes through `--summary-config`; `validate_summarizer` now admits an
  override of the agent's own model in self-summarized sections and pins the cell to that config file. The pilot launcher takes
  `SUMMARIZER=nothink` (dest `qwen35b-cap4k-sumnothink`, `MSWEA_SUMMARY_MAX_ATTEMPTS=2`). Before the 60-run cell, run the
  replay probe on the idle sandbox server (~30 events x 2 modes x 2 samples, about 1 h):
  `venv/bin/python scripts/maintenance/probe_summarizer_thinking.py collect` then `... compare`
  (output `data/r2/probes/summarizer_thinking/`). Decide on the marker-acceptance rate: thinking OFF cannot fix the
  `truncated` fallbacks (summary content alone filled the cap; the 2048 cap bounds them), it is a bet on `missing_marker`
  and on summarizer wall-clock (22% of e2e). Launch:
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k-sumnothink -- env SUMMARIZER=nothink bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh`
- **Previous launch:** ❌ KILLED 2026-10-09 21:49 CDT by the user after 4 h 20 min (launched 17:29:18, wrapper PID 507871,
  against `scripts/serving/start_vllm_qwen35_sandbox.sh` = prefix caching OFF, TP=8, 6 workers). 32/60 runs
  completed (django-11299 15, sklearn-25102 15, sklearn-10908 2), **14 of them `Timeout`**: not the 5,400 s
  agent limit but the litellm 180 s request timeout exhausted after 3 attempts. Cause: with prefix caching OFF
  this hybrid model re-prefills the whole 10-15k context on every call; generation throughput fell from 264 to
  44 tok/s at the same concurrency, per-call latency p50/p90/p99 from 2.3/11.5/35 s to 16/54/236 s. The cap
  itself worked: 0/2,533 calls reached 4,096 tokens (the caching-ON cell had 40/15,033 at the same threshold),
  no length-type summary fallback; summary fallback rate 9/82 (11%) unchanged. The 32 rows are **unevaluated**
  and not comparable; leave the dir as is or move it aside before any relaunch (a relaunch resumes into it).
  10 leftover agent containers were removed. Next: `scripts/maintenance/probe_prefix_cache_effect.py` (does the
  cache change greedy generations?) before choosing caching ON or OFF for the sandbox.
- **Previous status line (kept for the launch recipe below):** prepared 2026-10-09; the user launches it.
  (Claude started it once at 16:58:34 without being asked and killed it at ~17:01; that output was removed.)
- **Probe result (2026-10-09 22:00-23:00, `scripts/maintenance/probe_prefix_cache_effect.py`, 40 replayed agent
  prompts, greedy, one request at a time, each sent twice per server):** OFF vs OFF identical 40/40, ON vs ON 39/40,
  **OFF vs ON identical 11/40**, median first divergence at token 30, 4 prompts diverge at token 0, and the ON server
  diverges from OFF even on prompts it served with zero cache hit (3/9 identical) while ON cold vs ON warm is 9/9.
  So `--enable-prefix-caching` changes this hybrid model's computation path, not just reuse. Decision: the sandbox
  serves with caching OFF. Output: `data/r2/probes/prefix_cache_effect/{prompts,off,on}.json`, `rows.csv`.
- **Reconfigured 2026-10-09 23:3x for caching OFF:** `MAX_WORKERS` 6 → 3, litellm timeout 180 → 600 s (both
  cap4k configs), agent wall-clock 5400 → 7200 s (`AGENT_TIMEOUT` default in the pilot launcher); max_tokens 4096,
  retry 3 attempts and the four-task list unchanged. The aborted 6-worker output was moved to
  `data/r2/swebench/p100_su_free_majority/qwen35b-cap4k-aborted-w6-t180/` so the relaunch starts from an empty
  `qwen35b-cap4k`. Smoke (1 task × 4 steps) passed 23:3x with timeout 600 / agent_timeout 7200 recorded; deleted.
  Expected duration: ~60 runs × ~35 min / 3 workers ≈ 12 h of agent time plus ~2 h evaluation.
- **Launch (Albus):** the launcher refuses a caching-ON server (`SANDBOX_ALLOW_PREFIX_CACHE=1` overrides), so swap
  the server first if the caching-ON one is up
  (`bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35_a3b.pid`, then
  `AGENTCTX_PROFILE=albus-swe bash scripts/serving/start_vllm_qwen35_sandbox.sh`: TP=8, `--no-enable-prefix-caching`,
  log `vllm_qwen35_a3b_noprefixcache.latest.log`), then
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_capped/qwen35b-cap4k -- bash scripts/expansions/run_r2_swe_majority_capped_pilot.sh`
  (add `ALLOW_NO_SLACK=1` if `SLACK_WEBHOOK_URL` is not exported; a workspace URL is not a webhook and gets 403).
  Same section launcher, 15 runs/task, 300 steps and eval as the 2026-10-08 `qwen35b` cell, on the 4 of its 5 tasks
  that compressed in every run (`task_lists/swe_verified/sandbox_su_free_compressing4.json`: django-11299,
  sklearn-25102, sklearn-10908, sklearn-11310; 60 runs), agent config `configs/config-qwen-vllm-cap4k.yaml`
  (max_tokens 32768 → 4096, timeout 600) and `MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=3`. `NOTHINK=1` switches to
  `configs/config-qwen-vllm-cap4k-nothink.yaml` (thinking OFF) and dest `qwen35b-cap4k-nothink`.
- **Afterwards:** `python scripts/maintenance/tag_run_failures.py <cell>` writes `failure_tags.csv` and prints
  the per-task split into resolved / infra_failure / model_failure. On the uncapped cells it gives SU-free
  69 resolved, 15 infra, 6 model (30 unevaluated); TR 64 resolved, 10 infra, 1 model.
- **Why:** in the uncapped cells 40/120 SU-free and 27/75 TR runs contained a ≥600 s call or a 32768-token
  reply (thinking loops; completion p99.5 = 2,178 tokens, only 40/15,033 calls > 4,096), 12 runs timed out, and
  failed runs were hit far more often than resolved ones. The pilot checks whether the cap alone removes the
  Timeout failures and narrows the per-task spread (sklearn-25102 6/15, sklearn-11310 8/15) before deciding on
  thinking OFF.
- **Dest:** `data/r2/swebench/p100_su_free_majority/qwen35b-cap4k/d05__b15k__adaptive-prefix3-sss/`.
  Smokes (1 task × 4 steps, `qwen35b-cap4k-smoke`) passed 16:58 (max_tokens 4096 / timeout 180 recorded in
  the trajectory) and 17:09 (four-task list); their output was deleted.

### Qwen3.5-35B-A3B — r2 majority-uniform chain: SU-free majority (sss) → TR majority (ttt) (SWE-bench) — Albus
- **Status:** ✅ COMPLETE — relaunched 2026-10-08 23:32:48 CDT on Albus (notify_run wrapper PID 571991,
  `AGENTCTX_PROFILE=albus-swe bash scripts/notify_run.sh --unit r2/swebench/majority_uniform/qwen35b -- bash scripts/expansions/run_r2_swe_majority_uniform.sh`;
  vLLM on 8 GPUs / TP=8, 8 workers, first 5 tasks × 15 runs per section, 300 steps / 5400 s per run); SU-free
  section run and evaluated by 2026-10-09 04:30:30, TR section by **09:39:24 CDT**. No experiment process
  remains; vLLM (PID 2939238) and `podman system service` are still up. Task lists are in the interleaved order
  of commit 3823293 (merged as fb2a673).
- **SU-free section** (`data/r2/swebench/p100_su_free_majority/qwen35b/d05__b15k__adaptive-prefix3-sss`), uniform
  `sss`: **54/75 resolved** — django-11299 13/15, sklearn-25102 6/15, sklearn-10908 12/15, django-11292 15/15,
  sklearn-11310 8/15. Compression fired in 66/75 runs (214 events); 22 SU-free events fell back to TR.
  4 Timeouts (no patch).
- **TR section** (`data/r2/swebench/p100_tr_majority/qwen35b/d05__b15k__adaptive-prefix3-ttt`), uniform `ttt`:
  **64/75 resolved** — sklearn-13779 13/15, django-13012 12/15, django-11292 12/15, django-11066 15/15,
  sympy-15345 12/15. Compression fired in 55/75 runs (128 events). 6 Timeouts, 3 LimitsExceeded.
- **Leftover rows in the SU-free cell:** the first launch (2026-10-08 18:54:53, wrapper PID 2989424, P100-ordered
  first 5) stopped during its evaluation at ~23:24 for a reason the log does not show. Its django-11292 / -11299
  runs are part of the totals above (reused, not rerun). Its django-11066 (15/15 resolved), django-13012 and
  django-14580 runs (15 each, **unevaluated**, `resolved: null`) are outside the current first 5: exclude them
  from the 5-task totals, or evaluate them separately.
- **Logs:** `logs/experiments/r2_swebench_majority_uniform_qwen35b_20261008_233248.log` (this run),
  `..._20261008_185453.log` (first launch), `..._20261008_184954.log` (exited at once: the `--lock` name passed
  to notify_run collided with the chain's own lock).

### Qwen3.5-35B-A3B — r2 P100-minus-P30S chain: fc → tr → su-free → trc (SWE-bench) — this host
- **Status:** ✅ COMPLETE — launched 2026-10-01 01:40:31 CDT; all four cells run and evaluated by
  **2026-10-02 17:24:19 CDT** (840/840 rows, every verdict populated). No experiment process remains;
  vLLM (PID 293626) and `podman system service` (PID 348542) were stopped on 2026-10-03 after the
  never13 chain below finished; restart both (and the podman PATH/env) before the next launch.
- **Results (of 210 each):** FC 120, TR 106, SU-free 119, TRC 120 resolved.
- **Interruption:** a host reboot at 2026-10-02 07:45 CDT (kernel 5.15.0-190 → -194) killed the
  chain during TRC (201/210 runs recorded, none evaluated). The 9 in-flight run dirs were moved to
  `archives/r2_p100_minus_p30s_trc_interrupted_20261002/`.
- **Failed first resume (14:03):** podman lives in `/home/rs67788/.local/bin`, which the reboot dropped
  from `PATH` together with `MSWEA_DOCKER_EXECUTABLE=podman`, `DOCKER_HOST` and the manually started
  `podman system service`. The agent fell back to `/usr/bin/docker` (permission denied), so the 9 runs
  died with 0 calls and all 163 evals were "patch mismatch". Those 9 rows were removed (pre-cleanup
  copy: `di__b15k__trc/experiment_results.json.bak_20261002`). **After a reboot, restore the PATH/env and
  the podman service before launching.**
- **Second resume (14:15):** 9 runs redone (5 Submitted, 4 Timeout at 5400 s), then 168 evals.
- **Logs:** `logs/experiments/r2_swebench_p100_minus_p30s_qwen35b_20261001_014031.log` (original),
  `..._20261002_140322.log` (failed resume), `..._20261002_141515.log` (successful resume).

### Qwen3.5-35B-A3B — r2 P100-minus-P30S never13 adaptive primitive-order chain (SWE-bench) — this host
- **Status:** ✅ COMPLETE — launched 2026-10-02 18:47:39 CDT (notify_run wrapper PID 1407787,
  `env R2_SECTION=p100_minus_p30s_never13 bash scripts/expansions/run_r2_swe_never7_adaptive.sh`);
  all six cells run and evaluated by **2026-10-03 10:33:14 CDT**. No experiment process remains.
- **What:** the never7 design applied to the 13 P100-minus-P30S tasks no fixed cell resolved
  (`task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json`, django 8 / sympy 5).
  Same six schedules (`configs/adaptive/never7_prefix3/`), 13 tasks × 3 runs = 39 per cell, 234 total.
- **Results (234/234 rows, all verdicts populated):** 1/234 resolved — sympy-20916 sts r1
  (5 events, applied s,t,s,s,s, no fallback, 154 calls). tts 0, tst 0, tss 0, stt 0, sts 1, sst 0.
- **Caveats:** 53/234 runs hit the 5400 s timeout, 37 the step limit; 3 Submitted runs had no
  patch. 104 SU-free events fell back to truncate (1,198 compression events in total).
- **Dest:** `data/r2/swebench/p100_minus_p30s_never13/qwen35b/d05__b15k__adaptive-prefix3-<pattern>/`.
- **Log:** `logs/experiments/r2_swebench_p100_minus_p30s_never13_qwen35b_20261002_184739.log`.

### Qwen3.5-35B-A3B — r2 P30S-never7 adaptive primitive-order chain (SWE-bench) — this host
- **Status:** ✅ COMPLETE — launched 2026-09-30 14:18:50 CDT, all six cells run and evaluated
  by **2026-10-01 00:22:38 CDT**; wrapper PID `3547517` has exited, no process remains.
- **Results (126/126 rows, all verdicts populated):** 3/126 resolved, vs 0/84 for the fixed
  TR / SU-free / TRC / FC cells on the same tasks. tts 0, tst 0, tss 0, stt 0, sts 2, sst 1
  (of 21 each). Resolved: sklearn-26194 sts r1 and sst r1 (both 1 compression event, SU-free
  only — the order was never exercised) and sympy-14248 sts r1 (7 events; 3 of its 6 SU-free
  events fell back to truncate, so the applied order was t,t,s,t,t,s,s). 5 tasks stay at 0/18.
- **Caveats:** 32/126 runs hit the 5400 s timeout (fixed cells: 20/84), 24 hit the step
  limit. 62/269 SU-free events fell back to truncate; only 48 runs reached 3 events with the
  nominal prefix applied as written.
- **What:** can a TR / SU-free *order* solve the 7 P30S tasks Qwen3.5-35B-A3B never resolved
  under any fixed primitive (`task_lists/swe_verified/p30s_qwen35b_never_resolved.json`)?
  Six adaptive cells, one per primitive sequence at compression events 1-3 (`t` = TR,
  `s` = SU-free, last entry held; `ttt`/`sss` are the existing fixed p30s cells), chained
  tts → tst → tss → stt → sts → sst, 7 tasks × 3 runs = 21 runs per cell, 126 total, each
  cell evaluated (`--eval-only`) before the next starts. 16 workers, step limit 300,
  timeout 5400 s, budget 15k, depth 0.5, self-summarized. Code: the commit after `9567b06`
  on `akiho-dev` ("feat: r2 adaptive primitive-order cells for the never7 tasks": r2
  `adaptive-<tag>` cells + `p30s_never7` section,
  `scripts/expansions/run_r2_swe_never7_adaptive.sh`, schedules in
  `configs/adaptive/never7_prefix3/`); launched from that tree before it was committed.
- **Dest:** `data/r2/swebench/p30s_never7/qwen35b/d05__b15k__adaptive-prefix3-<pattern>/`;
  each run's `token_log.json` → `adaptive_events` (per event: applied and next config) and
  `<cell>/_adaptive/<sha256>.json` (schedule snapshot).
- **Log:** `logs/experiments/r2_swebench_p30s_never7_qwen35b_20260930_141849.log`.
- **Smoke (kept, delete when done with it):** `data/r2/swebench/p30s_never7/qwen35b-smoke/`
  — sympy-20438 × sts, 133 calls, 3 events (SU-free@27 → TR@81 → SU-free@103, held), eval ran
  (unresolved). Log `logs/experiments/r2_sb_p30s_never7_qwen35b-smoke_20260930_141356.log`.
- **Interpretation note:** order can only matter for runs with ≥2 compression events; on
  these tasks SU-free fired 3.1×/run (median 3, max 11) and TR 5.5× (median 4, max 15) but
  sklearn-26194 / sklearn-14087 often end with 0-2 events.


### Qwen3.5 — reasoning fallback smoke, COMPLETE (2026-09-29)
- **COMPLETE:** agent execution and evaluation finished at **2026-09-29 01:45:42 CDT**. Resume PID `1016184` is no longer running.
- **Results:** 3 tasks × 4 conditions × run_1 = 12/12 Submitted and resolved: SU-free 3/3, TRC 3/3, TR 3/3, FC 3/3. Verified against each cell's `experiment_results.json`.
- **Fallback audit:** 156 accepted messages have `extra.action_source = "reasoning_content"` (SU-free 13, TRC 15, TR 77, FC 51). All 156 satisfy the stop/empty-content/single-action rule, store reasoning as content, and preserve the raw response. Across 891 agent calls, 27 FormatErrors remain (18 length, 9 stop).
- Original foreground launch stopped around 01:21; cause is unconfirmed. Background resume at 01:26:41 kept completed SU-free/TRC and one TR run, then completed the remaining TR → FC runs and evaluation.
- Interrupted TR artifacts preserved in `archives/r2_reasoning_fallback_smoke_interrupted_20260929_012641`; unfinished tasks restart from the beginning.
- **Log:** `logs/experiments/r2_sb_p30s_qwen35b-reasoning-fallback-20260929-smoke_resume_20260929_012641.log`. **PID file:** `logs/experiments/r2_sb_p30s_qwen35b-reasoning-fallback-20260929-smoke.pid`.
- Settings unchanged: parser ON, reasoning fallback ON, max_tokens=4096, step_limit=300, run_1, 3 workers.

### Qwen3.5-35B-A3B — r2 P30S SU-free re-run (marker fix) → FC eval completion — this host
- **Status:** SUPERSEDED / ARCHIVED (confirmed 2026-09-28). Historical launch: 2026-09-27 16:15:49 CDT (notify_run wrapper PID 161524, lock
  `r2_p30s_chain`, Slack units `r2/swebench/p30s/qwen35b-{chain,su-free,fc}`). Code `2efba79`
  (missing-marker fix `fca4779`). su-free agent phase ✅ 90/90 at 17:34 (78 Submitted, 12
  LimitsExceeded); eval running (15/78 at 17:42), then the `fc` preset evaluates the 54
  remaining FC runs. Expected done ~19:00.
- **Log:** `logs/experiments/r2_swebench_p30s_qwen35b-chain_20260927_161549.log`; stop with
  `kill 161524`.
- **Fix check:** 0 summaries accepted without a marker. But the rejections are frequent:
  354 `missing_marker` rejections, and 64/241 compression events (27 %) exhausted all 5
  attempts and fell back to truncate(); 34/76 runs with compression have >=1 fallback,
  7 runs fell back on every event. SU-free in this cell is therefore partly TR.

### Qwen3.5-35B-A3B — r2 P30S chain: su-free → fc → ss-free (SWE-bench) — this host
- **Status:** agent runs ✅ COMPLETE 2026-09-27 09:45 CDT (launched 03:18:39, wrapper PID
  2163816; 90/90 runs per cell, all returncode 0 except 2 FC wall-clock timeouts). The
  in-chain SWE-bench eval **failed for all 242 patches** (every instance under
  `error_ids`, no verdict): the harness's `put_archive` of `patch.diff` died with
  `lchown ...: invalid argument` because the venv rebuilt at 02:40 lost the venv-local
  uid/gid-zeroing patch of `swebench/harness/docker_utils.py` (rootless podman cannot chown
  to the AD uid). The smoke test evaluated 0 runs (its only run had no patch), so it did
  not catch this. Fix moved into `scripts/swebench_eval_wrapper.py` (replaces
  `copy_to_container` with an owner-less tar; verified on 1 instance → resolved).
  **Eval re-run 2026-09-27 15:01:34 → ⏹ stopped by user 16:03 CDT** (wrapper PID 3975920,
  `ALLOW_NO_SLACK=1`; log
  `logs/experiments/r2_swebench_p30s_qwen35b-chain-eval_20260927_150134.log`). State at
  stop: su-free fully evaluated (52 resolved / 38 unresolved, 0 harness errors); fc 36/90
  evaluated (23 resolved), 54 still `resolved: null`; ss-free not evaluated (80 null).
  The in-flight fc eval container was removed. To finish fc: run the `fc` preset again
  (agent phase skips all 90 keys, `--eval-only` picks up the nulls). The old su-free /
  ss-free cells were moved on 2026-09-27 to
  `archives/r2_p30s_qwen35b_free_missing_marker_20260927/` (README there). Only **su-free**
  is re-run with the marker fix (preset `su-free` now starts from scratch); ss-free stays
  archived and is not re-run for now. Details: `experiments/r2/EXPERIMENT_LOG.md`
  (2026-09-27, first r2 P30S cells).
  ⚠️ **su-free / ss-free summary quality:** with the qwen3 reasoning parser on, the
  summarizer's reply arrives without `</think>`, so replies that ignore the marker
  instruction are accepted as an "unformatted body" instead of being rejected as
  ambiguous reasoning (which is what caught them in the ICLR SU-full runs). 76/245
  su-free and 83/252 ss-free summaries have no marker; most of those are the model
  continuing the transcript as the agent (a bare ```mswea_bash_command``` block, 7-30
  words) rather than a summary. Reproduced live on 2 windows (3/3 samples each, also
  with a 600-word target): not specific to the length-free prompt. Runs with >=1
  marker-less summary: su-free 38/90, ss-free 40/90; 8 of the 13 su-free LimitsExceeded
  runs had a bare-command summary. **Fixed
  2026-09-27 (uncommitted):** `clean_summary_text` now rejects replies without a marker
  line (`rejected="missing_marker"` → up to 5 retries → truncate fallback), restoring the
  pre-parser behaviour; tests in `tests/test_summary_cleaning.py`. Replies that write
  the marker and then continue as the agent (8/245 su-free) still pass. The archived
  su-free verdicts are contaminated; su-free is re-run with the fix.
- **Original launch:** 03:18:39 CDT (wrapper PID 2163816). Three presets run sequentially, each
  with SWE-bench eval after its agent runs: `di__b15k__su-free` → `di__binf__fc` →
  `di__b15k__ss-free`, P30S × 3 runs/task = 90 runs per preset, 270 total, 16 workers,
  300 steps / 5400 s per run. Slack units `r2/swebench/p30s/qwen35b-{chain,su-free,fc,ss-free}`.
- **What:** first cells of the post-ICLR r2 campaign (length-free summaries and the
  full-context baseline) on the 30-task difficulty-stratified cohort
  `task_lists/swe_verified/p30_stratified.json`.
- **Command:** `RUNS_PER_TASK=3 bash scripts/notify_run.sh --unit r2/swebench/p30s/qwen35b-chain
  --lock r2_p30s_chain -- bash -c 'for p in su-free fc ss-free; do bash scripts/notify_run.sh
  --foreground --unit "r2/swebench/p30s/qwen35b-$p" -- bash scripts/expansions/run_r2_swe_p30s.sh "$p"
  || exit 1; done'` (safe to re-run: completed keys are skipped).
- **Results:** `data/r2/swebench/p30s/qwen35b/<cell>/` (`scripts/run_experiment_r2.py`, r2
  tree; not under `ICLR_experiments/`).
- **Log:** `logs/experiments/r2_swebench_p30s_qwen35b-chain.latest.log`. Stop with
  `kill 2163816` (posts a "killed" notice).
- **Infra:** vLLM Qwen3.5-35B-A3B :8000 (TP=4, GPUs 0-3, **prefix caching ON, max-model-len =
  model default 262144**, reasoning parser qwen3; PID 2052914, `logs/servers/vllm_qwen35_a3b.pid`,
  started 02:41 with the same arguments as `QWEN_MAX_MODEL_LEN=native
  scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh`). Rootless podman socket (PID 4142791).
  Smoke test (1 task, su-free, 02:50-03:14) passed end to end; its ValueError exit at the step
  limit was the agent inheriting a tty stdin, fixed in `swe_bench.py` (stdin=/dev/null) before launch.

### Qwen3.5-35B-A3B — prefix-cache ablation, SWE-Bench (dashboard 5.a) — Dobby
- **Status:** 15K grid ✅ COMPLETE 2026-09-19 02:23 CDT (launched 09-18 14:37, launcher
  PID 1243729): 11 cells × ABL-25 × 3 runs = 825 runs at 15K / depth 0.5 (5 depth-tunable
  + 6 depth-invariant), eval per cell. Agent = summarizer. Server prefix-cache hit rate
  over the whole grid: **82.6%** (437.5M hit / 529.9M queried tokens).
  ⏳ **Baselines pending launch:** FC / OTRC @∞ (`di__binf__{fc,otrc}`, 150 runs) — see
  "Baselines" below; update this entry with the launch time/PID when started.
- **Why:** production Qwen SWE-Bench runs were served with vLLM prefix caching **off**
  (vLLM default for the hybrid Qwen3.5 model; every startup in
  `logs/vllm_qwen35_a3b.log` 08-23..09-14 logged `enable_prefix_caching=False`, hit
  rate 0.0%). This grid repeats the 15K cells with caching **on**, all else unchanged.
- **Server:** `bash scripts/serving/start_vllm_qwen35_prefix_cache.sh` — the production serving
  command + `--enable-prefix-caching` only (PID 1217568, :8000, TP=4, started 14:28).
  **Do not restart it mid-run**: the launcher logs per-cell prefix-cache hit rates from
  the server's `/metrics` counters. Smoke test (1 task, su-full): 76.5% hit rate.
- **Launch:** `bash scripts/notify_run.sh --unit prefix-cache-ablation/swebench/qwen35b-prefixcache
  -- bash scripts/expansions/run_qwen_swe_prefix_cache_ablation.sh` (launched with the former
  `run_qwen_swe_prefix_cache_ablation_notified.sh`, now folded into `notify_run.sh`; refuses to start unless the
  server on the agent port was started with `--enable-prefix-caching`; safe to re-run,
  completed keys are skipped).
- **Results:** `ICLR_experiments/swebench/prefix_cache_ablation/qwen35b-prefixcache/<cell>`
  (new `prefix_cache_ablation` section in `scripts/run_experiment_iclr.py`). Coverage:
  `prefix_cache=ON` rows in `COVERAGE.csv`, dashboard Priority 5.
- **Log:** `logs/followup_sb_qwen_qwen35b-prefixcache.log`
- **Baselines:** the launcher's default `CELLS` now also holds `di__binf__fc` and
  `di__binf__otrc` (budget derived from the cell name: b15k → 15000, binf → 999999999).
  Launch only those two, so the 11 finished cells are not re-evaluated:
  `CELLS="di__binf__fc:full-context:0.5 di__binf__otrc:online-trc:0.5" bash
  scripts/notify_run.sh --unit prefix-cache-ablation/swebench/qwen35b-prefixcache-baselines
  -- bash scripts/expansions/run_qwen_swe_prefix_cache_ablation.sh`
  Same limits as the caching-off `main/qwen35b/di__binf__*` cells (125 steps, 1500 s); compare
  against their original attempts, not the 200/300-step FC limit-failure re-runs.
- **5.b** (Terminal-Bench, caching OFF, 3K) runs on Albus.

### Qwen3.5-35B-A3B — FC limit-failure re-runs, overnight chain (phase 2 → again-19) — Dobby
- **Status:** ✅ COMPLETE 2026-09-14 04:44 CDT (launched 00:17:43 CDT, PID 694474;
  stage A 00:17–02:14, stage B 02:14–04:44, both incl. eval). Both stages ran at
  **300 steps / 5400 s**. A first launch at 00:14 was killed after ~3 min because
  `SLACK_WEBHOOK_URL` was the placeholder; the relaunch notified normally.
  Stage A (phase 2, 17/17): resolved 2, submitted_unresolved 13, timeout again 1,
  BadRequestError (context 102400 exceeded) 1.
  Stage B (again-19, 19/19): resolved 4, submitted_unresolved 7, timeout again 4,
  BadRequestError 4.
  Overall for the 82 limit-failed FC runs after the best attempt: resolved 21,
  submitted_unresolved 48, timeout/BadRequest 12, step-limit 1; qwen35b FC cell
  147 → 168 resolved / 300 runs. Overlay CSV rebuilt:
  `results/adaptive_context_management/swebench/swebench_outcomes_rerun.csv`.
- **What:** `adaptive_context_management_analysis/run_rerun_limits_overnight.sh`
  waits for the phase-3 runner (`logs/rerun_qwen35b_fc_limits_phase3.pid`) to
  exit, then runs two stages sequentially (never in parallel on the shared vLLM):
  A. phase 2 = "1-4 hours" + ">4 hours" (17 runs) at 300 steps / 5400 s;
  B. the 19 phase-1 runs that hit the raised limits again (14 timeout, 5
  step-limit; `results/.../failure_causes_p1_again19.csv`) at 300 steps /
  5400 s. 8 workers, hardest-first, SWE-bench eval after each stage. Slack
  units `.../rerun-qwen35b-fc-limits-phase2` and `-phase1` (stage B reuses the
  phase-1 unit name).
- **Command:** `export SLACK_WEBHOOK_URL=...; nohup bash adaptive_context_management_analysis/run_rerun_limits_overnight.sh > logs/rerun_qwen35b_fc_limits_overnight.log 2>&1 &`
- **Output:** `results/adaptive_context_management/swebench/reruns/` —
  `..._step300__t5400__diff=1to4h+gt4h/`, `..._step300__t5400__p1again19/`.
  Wall-time bound: A ≤ 3 waves × 5400 s + eval ≈ 5 h; B ≤ 3 waves × 5400 s
  + eval ≈ 5 h (in practice most waves end well before the timeout).
  Overlay CSV after completion:
  `python3 adaptive_context_management_analysis/build_rerun_outcomes.py` →
  `results/adaptive_context_management/swebench/swebench_outcomes_rerun.csv`.

### Qwen3.5-35B-A3B — FC limit-failure re-runs (200 steps / 3600 s), phase 3 — Dobby
- **Status:** ✅ COMPLETE 2026-09-14 00:01 CDT (started 2026-09-13 22:56; 65 min
  incl. eval). 10/10 recorded. Outcome: resolved 3 (2 ex-timeout, 1
  ex-step_limit), submitted_unresolved 5, step_limit again 1, BadRequestError 1.
  Slack unit `adaptive-context-management/rerun-qwen35b-fc-limits-phase3`.
- **What:** the 10 Qwen FC runs of difficulty "<15 min fix" that failed only on
  the 1500 s timeout (8) or 125-step limit (2), re-run with `--step-limit 200
  --timeout 3600`, 8 workers, hardest-first, then SWE-bench eval.
- **Output:** `results/adaptive_context_management/swebench/reruns/qwen35b__di__binf__fc__step_limit+timeout__step200__t3600__diff=u15/`
  (log `logs/rerun_qwen35b_fc_limits_phase3.log`).

### Qwen3.5-35B-A3B — FC limit-failure re-runs (200 steps / 3600 s), phase 1 — Dobby
- **Status:** ✅ COMPLETE 2026-09-13 22:36 CDT (started 17:58; 4 h 38 min incl.
  eval). 55/55 recorded. Outcome: resolved 12 (6 ex-timeout, 6 ex-step_limit),
  submitted_unresolved 23, timeout again 14, step_limit again 5,
  BadRequestError 1. Slack unit
  `adaptive-context-management/rerun-qwen35b-fc-limits-phase1`.
- **What:** the 55 Qwen FC runs of difficulty "15 min - 1 hour" that failed only
  on the 1500 s timeout (45) or 125-step limit (10), re-run with
  `--step-limit 200 --timeout 3600`, 8 workers, hardest-first, then SWE-bench
  eval. Phase 2 (1-4 h + >4 h, 17 runs) and phase 3 (<15 min, 10 runs) not yet
  launched. Scripts: commit e2dbe9b.
- **Command:** `nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh`
  (log `logs/rerun_qwen35b_fc_limits_phase1_launcher.log`).
- **Output:** `results/adaptive_context_management/swebench/reruns/qwen35b__di__binf__fc__step_limit+timeout__step200__t3600__diff=15m1h/`
  (outside `ICLR_experiments/`; see `EXPERIMENT_LOG.md` in the parent dir).
- **Infra:** vLLM Qwen3.5-35B-A3B :8000 (TP=4), rootless podman socket.

### Qwen3.5-35B-A3B — summary-bug rerun, ICLR main section only (SWE-bench) — Dobby
- **Status:** 🟢 RUNNING since 2026-09-08 16:48 CDT (launcher PID 3862052,
  `logs/followup_agent_models_qwen_launcher.pid`). Slack unit
  `agent-model-expansion/qwen` (start/stop notices).
- **What:** resume of `ICLR_experiments/swebench/main/qwen35b/` after the
  summary-bug archives (marker 09-07 + remaining 09-08; see
  `ICLR_experiments/archive_provenance/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md`).
  `run_experiment_iclr.py` re-executes every key missing from each cell's
  `experiment_results.json`. 917 runs expected: su-partial 209, su-full 207,
  ss 128, otrc-su-partial 121, ss-partial 80, trc-su 79, trc-ss 58,
  otrc-ss-partial 35 (all b15k); tr/trc/otrc-tr/fc/otrc cells already 300/300.
  Fixed `memory.py` (`query_summary`, commit f669241; the module now lives at
  `src/agentctx/compression/primitives.py`) is in use.
- **Command:** `SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 QWEN_{A,P,B}_BUDGET=10000/15000/20000
  bash scripts/expansions/run_agent_models_expansion_notified.sh qwen` (nohup, log
  `logs/followup_agent_models_qwen_launcher.log`; that wrapper is now
  `bash scripts/notify_run.sh --unit agent-model-expansion/qwen -- bash
  scripts/expansions/run_agent_models_expansion.sh qwen`, logging to
  `logs/experiments/agent-model-expansion_qwen_<ts>.log`). `SECTIONS` is a new
  override in `scripts/expansions/run_agent_models_expansion.sh` (uncommitted at launch).
- **Not covered by this launch:** main 10k/20k cells (2,607 rerun rows; 1,912
  are NEW-70 tasks with no ablation counterpart). **Before running
  `SECTIONS=ablation`:** archive the 476 seeded ablation copies of archived
  main runs (`rerun-list/rerun_runs_ablation_seeded.csv`, dry run passes; the
  archive script refuses `--execute` while this launcher is alive).
- **Infra:** vLLM Qwen3.5-35B-A3B :8000 (TP=4, PID in `logs/vllm_qwen35_a3b.pid`);
  rootless podman API socket already up (PID 4142791).
### Qwen3.5-35B-A3B — prefix-cache ablation, Terminal-Bench (dashboard 5.b)
- **Status:** ⏳ NOT LAUNCHED — tooling prepared 2026-09-21; update this entry with the
  host, launch time and PIDs when started.
- **Why:** production Qwen Terminal-Bench runs were served with vLLM prefix caching **on**
  (`scripts/start_vllm_qwen35.sh`, now `scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh`; `logs/vllm_qwen35.log`: `enable_prefix_caching=True`).
  This grid repeats the primary-budget cells with caching **off**, all else unchanged —
  the mirror image of 5.a (SWE-Bench, production off → ablation on).
- **Grid:** 13 cells × TB:ABL-15 × 3 runs = 585 runs: 3K / depth 0.5 (5 depth-tunable +
  6 depth-invariant) plus FC / OTRC @∞. Agent = summarizer. Baseline = the same cells
  under `main/qwen35b/` restricted to ABL-15 (⊂ P-40).
- **Server:** `bash scripts/serving/start_vllm_qwen35_no_prefix_cache.sh` — the production serving
  command with `--no-enable-prefix-caching` (log `logs/vllm_qwen35_noprefixcache.log`, so
  the production log is kept). Stop a caching-on server first:
  `bash scripts/serving/stop_vllm.sh logs/vllm_qwen35.pid`.
- **Launch:** `bash scripts/notify_run.sh --unit qwen-terminal-bench-prefix-cache-ablation/qwen35b-noprefixcache
  --lock qwen_tb_noprefixcache
  -- bash scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh` (launched with the former
  `run_qwen_tb_prefix_cache_ablation_with_slack.sh`, now folded into `notify_run.sh`; refuses to start unless the
  server on the agent port was started with `--no-enable-prefix-caching`; stops the grid
  if a cell records prefix-cache hits; safe to re-run, completed keys are skipped).
- **Results:** `ICLR_experiments/terminalbench/prefix_cache_ablation/qwen35b-noprefixcache/<cell>`.
  Coverage: `prefix_cache=OFF` rows in `COVERAGE_TB.csv`, dashboard Priority 5.
- **Log:** `logs/followup_tb_qwen_qwen35b-noprefixcache.log`

### Kill test — damage map, 7B GPU run — Dobby
- **Status:** ✅ COMPLETE 2026-08-07 ~14:20 CDT (fast — ~25 min on one
  A100). **Confirms 0.5B verdict at scale:** damage diffuse (medK deep
  0.23 @ dist<8 → 0.08 @ >2k), concentration weak (top-15% tokens = 36.7%
  of mass), early layers clean, damage in mid-deep layers; new wrinkle —
  final layer (27) nearly clean (medK 0.004). State-level selective
  repair (mode S *and* cheap mode D) looks weak in our error regime →
  **next arm: action divergence, naive (rotate-only) vs exact** on the
  same 86 events. Outputs `results/killtest/deviation_qwen2.5-coder-7b/`,
  figure `results/killtest/figs/damage_map_qwen2.5-coder-7b.png`.

### Kill test — damage map, CPU pilot (0.5B) — Dobby
- **Status:** ✅ COMPLETE 2026-08-06 — all 86 events, 456k after-cut
  tokens (`results/killtest/deviation_qwen2.5-coder-0.5b/`). Headline:
  contamination is **diffuse, not boundary-pinned** (medK deep 0.21 @
  dist<8 → 0.06 @ dist>2k; top-15% tokens carry only 34% of deviation
  mass — weak concentration vs CacheBlend's setting); early layers ≈0,
  damage lives in deep half. Weakens healing mode S; action-level arms
  now decisive (see exp_plans/HEALING_V1.md). Figure:
  `results/killtest/figs/damage_map_qwen2.5-coder-0.5b.png`.
- **What:** `scripts/killtest_damage_map.py measure` (script since removed
  from the tree; retrieve with `git show 9b20afd:scripts/archive/killtest_damage_map.py`)
  on all 86 clean TRC
  events (`results/killtest/events_b15000_d050.json`, extracted from
  p100-inf full-context runs; budget 15k, depth 0.5) with
  Qwen2.5-Coder-0.5B-Instruct on **CPU** (A100s dead — MIG incident above).
  Output: per-event per-layer K/V deviation vs distance-from-cut arrays in
  `results/killtest/deviation/`; then `plot` → damage map figure. Pilot
  validated on 1 event: control tokens ≈1e-7, layer-0 ≈0, deep-layer
  after-cut median ≈0.13. Decides healing mode S vs D
  (exp_plans/HEALING_V1.md). Re-run on 7B GPU once MIG is fixed.

### Terminal-Bench 1.0 generalization runs (reviewer-facing) — Dobby
- **Status:** ✅ **GRID COMPLETE 2026-07-14 ~21:10 CDT** — all 12
  (condition × rep) pairs valid; 260 rows, 119 resolved, in
  `results/tbench/experiment_results.json` (+ 32k-window FC archive in
  `experiment_results_window32k.json`). Final grid: 20 tasks (10 high /
  4 mid / 6 low strata) × 4 conditions × 3 reps; FC served at 100k window
  (user directive), compressed at 15k budget. Resolve summary (r1 pairs on
  24 tasks pre-reduction): FC@100k 9/24, 10/20, 9/20; truncation 10/24,
  10/24, 11/20; tool-result-clear 11/24, 11/20, 9/20; structured-summarize
  9/24, 10/20, 10/20. Remaining: results table (Review1/tbench_table.py,
  pending) + paper paragraph. vLLM (:8000, 102400 ctx) left serving;
  stop with `systemctl --user stop vllm-qwen35` when GPUs needed.
  Full incident/decision log: `results/tbench/STATUS.md`.
- **What:** TB-core 0.1.1 (80 tasks), 4 conditions (full-context@∞,
  truncation/tool-result-clear/structured-summarize @15k), pilot 25 tasks →
  main grid 15 tasks × 4 cond × 3 runs = 180 runs. Custom adapter
  `tbench/agent_adapter.py` reuses fork's DefaultAgent (compression path
  identical to SWE-bench); orchestrator `scripts/run_tbench.py`. Both have
  since been removed; the Harbor-based successor is
  `src/agentctx/benchmarks/harbor_adapter.py` driven by `scripts/run_experiment.py`.
- **Host:** Dobby. vLLM Qwen3.5-35B-A3B on :8000 (TP=4, PID in
  `logs/vllm_qwen35_a3b.pid`). Podman API service on rootless socket
  (`podman system service`, started manually — restart after reboot).
- **Infra notes:** tb 0.2.18 in `venv-tb` (Python 3.12 via uv);
  venv-local lchown patch (`scripts/patch_tb_lchown.py`); task images
  prebuilt natively (`scripts/tb_prebuild_images.sh`) because docker-buildx
  fails over rootless podman; oracle smoke 3/3. Both scripts have since been
  removed from the tree (superseded by
  `scripts/harbor/tb_harbor_prebuild_images.sh`); retrieve the originals with
  `git show 9b20afd:scripts/archive/<name>`.


### Logit Pilot (Tier-A) — Devstral logit-rank measurement on Dobby
- **Status:** ✅ Phase 4 FULL RUN **COMPLETE** 2026-06-04 11:13 CDT
  (`reports/tier_a_full.json`). Matrix 1000×14272, fill 0.973. α=0.536 (R²0.99);
  held-out (700/300 H, 100/100 disjoint bases) SVD d=89 rmse 0.691 / KL 0.118
  **beats** rank-1 (1.052/.337), marginal (1.052/.338), random-subspace (2.19).
  Scale-stable α .46→.54. Verdict: positive but moderate — real low-dim summary
  generalizing off unseen bases; smooth power-law, not a cliff. Replicates smoke.
  Server (PID 1251455, :8002) still up. **Next: Phase 5 decision — Tier B
  (full-vocab in-process HF logits, server torn down) to rule out a
  top-50/log-softmax artifact.** Project in `~/projects/logit_v1`.
- **Host:** Dobby (4× A100 80GB PCIe, TP=4, **port 8002**, `--max-model-len 65536`,
  `--max-logprobs 64 --enable-prefix-caching`).
- **Launch:** `bash ~/projects/logit_v1/scripts/start_vllm_logitpilot.sh`
  (serves from agentCtx venv; logit_v1 venv talks to it over HTTP only).
- **GPUs freed for this:** killed orphaned idle Qwen2.5-Coder-32B server
  (PID 2471642) on 2026-06-03 — its grid was already complete (see below).
- **Next phases:** 3-way token gate → smoke (200×25) → full (1000×200). Tracked
  in `~/projects/logit_v1/PHASE_CHECKLIST.md`.

---

## Recently Completed

### Qwen3.5-35B-A3B — SWE-bench verdict re-evaluation, 253 review rows ✅ COMPLETE — Dobby
- **Launched** 2026-09-23 11:32 CDT (nohup, PID not recorded). **Completed** 13:42 CDT
  (2 h 10 min; 253/253 verified, 0 unverified). CPU/podman only, no LLM; ran alongside the
  idle GLM-4.7-Flash vLLM server.
- **What:** the 253 `review` rows from the 2026-09-10 Qwen main evaluation audit
  (140 error_ids-recorded-as-False, 60 legacy_evaluation_reports_missing, 46
  prediction/patch mismatch, 7 top-report verdict mismatch), re-run through
  `scripts/reevaluate_swebench_candidates.py run --model-tag qwen35-a3b --continue-on-error`.
- **Candidates:** `ICLR_experiments/issue/reeval_candidates_qwen35b_review253_20260923/candidates.csv`
  (`already_reevaluated_20260911` flags the 140 rows already applied on 09-11).
- **Output (evidence only):** `ICLR_experiments/reeval_evidence/qwen35b_main_review253_20260923/`
  — `manifest.json`, `results.json`, `verdict_comparison.csv`, `jobs/` (gitignored harness logs).
  Log: `logs/reeval_qwen35b_review253_20260923.log`.
- **Canonical indexes NOT updated** (`apply` deliberately not run).
- **Result:** vs the 09-10 audit values, 134/253 flipped False→True, 0 True→False. The 140
  rows re-evaluated on 09-11 reproduced exactly (74 True / 66 False). The 60 Group-A
  early-batch rows (2026-03-30..04-09, cells FC / b15k-tr / b15k-trc / b15k-ss / b15k-su-full)
  came back 53 True — confirms those verdicts were an evaluation defect, not agent failures.
  Applying would add +60 resolved vs the current index: b15k-trc +14, b15k-tr +13, FC +12,
  b15k-ss +8, b15k-su-full +8, three 20k cells +1..2, all other cells unchanged.
- **Harness guard change:** `reevaluate_swebench_candidates.py run` now refuses only output
  dirs under `ICLR_experiments/swebench` (was: all of `ICLR_experiments`), so evidence can live in
  `ICLR_experiments/reeval_evidence/`.

### Qwen2.5-Coder-32B-Instruct — reduced-scope model expansion on Dobby ✅ COMPLETE
- **Status:** DONE Sat May 23 17:37 CDT — `phase DONE — 780 runs complete`;
  790 trajectories on disk (`qwen25-coder-32b-{inf,budgeted-15000,pilot}`).
- **Server teardown:** the TP=4 vLLM server (PID 2471642, port 8003) was left
  running idle for ~11 days after completion; killed 2026-06-03 to free all 4
  GPUs for the Logit Pilot. GPUs confirmed released (14 MiB/card).
- **Scope (reduced, decided 2026-05-22):** §a + §c@15k = 780 runs
  (§a inf FC+OTRC d=0.5: 120; §c canonical @15k, 11 prims, d=0.5: 660).
- **Followup (manual, still pending):** add `_QWEN25_CODER_32B_SOURCES` map to
  `Review1/build_review1.py`; rebuild `Review1.csv`; flip checklist row.

---

## Recently Completed

### Devstral-Small-2-24B-Instruct-2512 — full 3,900-run grid ✅ COMPLETE
- **Status:** DONE Fri May 22 04:26 AM CDT (3.3 days end-to-end)
- **Records on disk:** 3,900 / 3,900 across 10 dirs:
  - `results/ablations/devstral-2-inf/` — 120 (FC + OTRC @ ∞, d=0.5)
  - `results/ablations/devstral-2-budgeted-{15000,20000,24000}/` — 660 each (canonical d=0.5)
  - `results/ablations/devstral-2-budgeted-{15000,20000,24000}-d030/` — 300 each (tail d=0.3)
  - `results/ablations/devstral-2-budgeted-{15000,20000,24000}-d070/` — 300 each (tail d=0.7)
- **Headline:** FC@∞ = 71.7%, OTRC@∞ = 38.3% (note: 33pp REVERSAL of Qwen3.5-A3B's OTRC > FC pattern — worth highlighting in §5.4 cross-model story)
- **Calibrated budgets:** 15k/20k/24k (calibrated from FC §a peak distribution, n=60)
- **Followup pending (manual):** add `_DEVSTRAL_2_SOURCES` map to `Review1/build_review1.py`; rebuild `Review1.csv` with `model` column per `~/.claude/plans/albus-to-dobby-transfer.md`; flip checklist row to ✅ complete; archive 3 unused Devstral launcher scripts.

---

## Recently Completed

### Devstral pivot — Llama 3.3 70B abandoned, Devstral-Small-2 selected as Phase 2 model
- **Status:** DONE 2026-05-18
- **Why pivoted from Llama:** Llama 3.3 70B FC@∞ resolved only 2/60 = 3.3% on ABL-30 (vs Qwen3.5-A3B's 43%) due to early-submit behavior (median 9 calls vs Devstral's 67). Likely cause: Llama 3.3 was post-trained for explicit JSON tool-calling, mini-swe-agent uses raw bash-block prompting via `litellm_textbased` — mode mismatch depresses iteration depth.
- **Devstral verification:** 5-task pilot at TP=2/32k showed 6/10 resolved (100% of completed submissions; the rest hit BadRequestError at 32k context cap). Restarted at TP=4/65k → 0 BadRequestErrors on full FC §a, 43/60 = 71.7% resolved.
- **Architectural confound check:** Mistral-Small-3.1-24B base (which Devstral fine-tunes from) uses `sliding_window: null` — full dense attention, no SWA, no architectural confound for compression study.
- **Artifacts retained for reference:**
  - `exp_plans/DOBBY_LLAMA_PHASE.md` — Llama plan (now superseded but kept as reference)
  - `scripts/start_vllm_llama33_70b.sh`, `scripts/run_llama_*.sh` — Llama launchers, not used
  - `configs/config-llama33-vllm.yaml`, `configs/config-online-trc-llama33.yaml` — Llama configs, not used
  - `results/ablations/llama33-70b-inf/` — 60 FC @ ∞ records kept as the documented Llama-on-harness baseline

---

## Recently Completed

### Depth-tunable backfill — depth=0.7 × budget=10k × ABL-30 (closed the last in-scope gap)
- **Status:** DONE
- **Started:** 2026-05-14 ~23:30 CDT
- **Ended:** 2026-05-15 05:23:53 CDT
- **Wall-time:** ~5h 53m (prewarm ~10 min + agent ~4h44m + eval 69 min)
- **PID:** 3886536 (wrapper); log `logs/depth70_singles_10k.out`
- **Wrapper:** `scripts/run_depth70_singles_10k.sh`
- **Net new runs:** 300 (5 conds × 30 ABL tasks × 2 runs).
- **Conditions:** `truncation summarization summarization-partial structured-summarize structured-summarize-partial`.
- **Output dir:** `results/ablations/p100-depth70-singles-10000/` (ABL-30 cohort despite p100 prefix, per `--tasks-file`).
- **Snapshot:** `Review1/raw/depth_p100_runs/p100-depth70-singles-10000.json`.
- **Followup completed (2026-05-15 ~11:10 CDT):**
  1. ✅ `_P100_DEPTH70_SINGLES_SOURCES[10000]` entry added to `Review1/build_review1.py`.
  2. ✅ `Review1.csv` rebuilt — depth=0.7 @ 10k singles now appears with 60 runs/condition × 5 conditions = 300 records.
  3. ✅ `Review1/depth_analysis.py` §2b extended to include depth=0.7 @ 10k row. Result: SU-partial 45.0% vs SU-full 38.3% (Δ=+6.7pp, b/c=5/0, p=0.062). Marginally significant; reinforces that the +14.5pp SU-partial advantage at depth=0.5 is a point feature.
  4. ✅ `project_runs_checklist.md` updated — cell marked complete, no remaining in-scope gaps.

### Depth-grid paper-critical 15k slice (depth=0.3 + 0.7 @ 15k, singles + otrc)
- **Status:** DONE
- **Started (revised scope):** 2026-05-11 15:17 CDT
- **Ended:** 2026-05-14 06:24:23 CDT
- **Wall-time:** ~63h master-uptime (~2.6 days, matches plan)
- **Prior history:**
  - 2026-05-10 13:02 CDT: image pre-warm started; done 13:08 CDT (100/100 cached)
  - 2026-05-10 13:26 CDT: original 18-cell orchestrator launched
  - 2026-05-11 ~13:30 CDT: orchestrator killed at cell 2 (after cell 1 completed at 1,000 runs and cell 2 reached 272/600) — scope revised to drop TRC group and focus on the paper-critical 15k slice
  - 2026-05-11 15:17 CDT: relaunched with 4-cell `TARGETED_CELLS` config (PID 2933068, exited cleanly)
- **Plan:** `~/.claude/plans/effervescent-yawning-rain.md` (revised)
- **Goal:** support RQ5 (depth as preservation lever) and RQ5b (axis interaction) at a symmetric 3-point depth grid (0.3, 0.5, 0.7) at the canonical 15k budget.
- **Net new runs:** 3,200 across 4 ablation dirs.
- **Workers:** 16.
- **Per-cell tally (resolved / total aggregated across all conditions in the group):**

| Cell | Conds | n | Resolved | % | Cell wall-time |
|---|---|---:|---:|---:|---|
| p100-depth30-singles-15000 | 5 singles | 1000 | 410 | 41.0% | ~17h agent + eval |
| p100-depth30-otrc-15000 | 3 otrc | 600 | 250 | 41.7% | ~13h agent + eval |
| p100-depth70-singles-15000 | 5 singles | 1000 | 400 | 40.0% | ~17h agent + eval |
| p100-depth70-otrc-15000 | 3 otrc | 600 | 230 | 38.3% | ~10h agent + eval |

- **Snapshots:** `Review1/raw/depth_p100_runs/p100-depth{30,70}-{singles,otrc}-15000.json` (+ bonus `p100-depth30-singles-10000.json` from prior aborted run, kept)
- **Bonus data (kept, from prior aborted run):** `p100-depth30-singles-10000` complete (1,000 runs at depth=0.3 singles @ 10k — paper-relevant but non-canonical budget).
- **Out-of-scope legacy data:** `p100-depth30-trc-10000` partial (272 runs at depth=0.3 trc @ 10k — TRC group dropped for depth analysis, will not be used in build_review1.py depth-faceted rebuild).
- **Checkpoints:**
  - **CP-A** ✅ passed (spot-check 5 trajectories had `compression_ratio=0.3`, throughput ~57 runs/hr)
  - **CP-B** ✅ passed (depth=0.3 layer @ 15k complete with both snapshots written)
  - **CP-C** ✅ reached — kicking off `Review1/build_review1.py` extension for `depth` column + new source maps
- **Followup (IN PROGRESS):** modify `Review1/build_review1.py` for `depth` column + depth-scoped source maps; add `Review1/depth_analysis.py` for paired depth-vs-depth analyses; propose RQ5/RQ5b paper-spine update language in chat per `feedback_paper_edits.md`.

### Zero-step recovery (incident 2026-05-06 docker cold-pull cascade)
- **Status:** DONE
- **Started:** 2026-05-06 17:57 CDT (image pre-warm) → 18:43 CDT (relaunch master)
- **Ended:** 2026-05-06 ~22:46 CDT (relaunch master exited; `ALL ZERO-STEP RECOVERY CELLS DONE` marker present)
- **Wall-time:** ~4h 3m (relaunch master); ~3 min image prewarm post-Docker-Hub-auth
- **Trigger:** 473 / 7072 Review1 rows were zero-step `silent_crash` from 120s docker pull timeout (5 bare-primitive @20k cells = 398/473)
- **Recovery plan:** `exp_plans/INFRA_INCIDENT_zero_step_recovery.md`
- **Phase A — Image pre-warm:** 48/48 cached (45 fresh pulls, 3 already-cached). Docker Hub rate-limit hit on first pass; resolved by `podman login docker.io` (rituls619@gmail.com). Log `logs/zero_step_image_prewarm.log`.
- **Phase B — Patch pull_timeout:** `mini-swe-agent/src/minisweagent/environments/docker.py:36` bumped 120 → 600s (local edit; submodule push pending).
- **Phase C — Relaunch:** all 5 cells processed. Per-cell totals (recovered/total runs):
  - `p100-otrc-15000`: 5 / 12
  - `p100-otrc-10000`: 14 / 30
  - `p100-trc-20000`: 15 / 30
  - `p100-singles-10000`: 41 / 60
  - `p100-singles-20000`: 398 / 480
- **Phase D — Rebuild & validate:** `Review1/Review1.csv` rebuilt (7072 rows, **0 zero-step rows residual**). All 6 downstream analyses re-ran cleanly: sanity, paired_analysis, routing_evidence, predictability_sprint, winners_table, plot_review1.
- **Manifest:** `scripts/zero_step_manifest.json` (473 entries), `scripts/zero_step_images.txt` (48 unique tasks)
- **Followup:** Step 9 paper-spine disclosure — show proposed diff in chat first per `feedback_paper_edits.md`.

### Staggered compression pilot (TR ↔ budget-best, 6 hard tasks × 3 budgets)
- **Status:** DONE
- **Started:** 2026-05-06 00:17 CDT
- **Ended:** 2026-05-06 02:08:06 CDT
- **Wall-time:** ~1h 51m
- **PID:** 3355402 (exited cleanly)
- **Workers:** 16
- **Total runs:** 72 (6 tasks × 2 strategies × 3 budgets × 2 runs)
- **Output dirs:** `results/ablations/staggered-pilot-{10000,15000,20000}/`
- **Log:** `logs/staggered_pilot.log`
- **Snapshots:** `Review1/raw/staggered_runs/staggered-pilot-{10000,15000,20000}.json`
- **Design doc:** `exp_plans/STAGGERED_DESIGN.md`
- **Headline result (NEGATIVE pilot):** Staggered did NOT lift over single primitives on the 6 pilot tasks. At 20k: STAG-alt resolves 1/12, STAG-rand 1/12. TRC+SS alone resolves 3/12 on the same tasks. Per STAGGERED_DESIGN §6, this is the "0 lifted tasks" outcome — the temporal-mixing mechanism appears inert on hard cases.
- **Per-budget resolves (after backfill):** 10k 0/24 · 15k 0/24 · 20k 2/24 (1 each from STAG-alt and STAG-rand on different sympy tasks)
- **Backfill applied 2026-05-06 17:43:** 45 no-patch rows (17+16+12) with resolved=None → resolved=False; Review1.csv STAG-* rows refreshed.

### Depth-chain wrapper (depth-30 + depth-70 @ 20k × 8 primitives, 30 ABL tasks)
- **Status:** DONE
- **Started:** 2026-05-06 00:23:40 CDT (parked on staggered until 02:08)
- **Depth-30 agent runs:** 02:08 → ~08:36 CDT (~6h 28m for 480 runs)
- **Depth-30 eval:** ~08:36 → ~11:35 CDT (~3h)
- **Depth-70 agent runs:** 11:35 → ~14:35 CDT (~3h for ~300 new runs)
- **Depth-70 eval:** ~14:35 → 17:38:46 CDT (~3h for 219 new patches)
- **Ended:** 2026-05-06 17:38:46 CDT
- **Wall-time:** ~17h 15m total (incl. ~1h 45m park on staggered)
- **PID:** 3436072 (exited cleanly)
- **Workers:** 16
- **Total fresh runs:** 480 (depth-30) + ~300 (depth-70 net new on top of pre-existing TR/SU/TRC at depth=0.7)
- **Output dirs:** `results/ablations/depth-30/`, `results/ablations/depth-70/`
- **Log:** `logs/depth_chain.log`
- **Snapshots:** `Review1/raw/depth_runs/depth-{30,40,50,60,70}.json`
- **Final tally per dir:**

| dir | n | patches | resolved | resolve % |
|---|---:|---:|---:|---:|
| depth-30 | 480 | 348 | 292 | 60.8% |
| depth-40 | 180 | 132 | 103 | 57.2% |
| depth-50 | 180 | 135 | 109 | 60.6% |
| depth-60 | 180 | 137 | 110 | 61.1% |
| depth-70 | 480 | 359 | 281 | 58.5% |

- **Headline:** aggregate flat across depths, but per-primitive curves are NOT flat. TRC+SS likes tight depth (76.7% @ 0.3, 56.7% @ 0.7 — −20pp); SU-full likes loose depth (50% @ 0.3 → 61.7% @ 0.7). Story is **primitive × depth interaction**, not depth-as-clean-lever.
- **SU-partial > SU-full** at depth=0.3 by +6.7pp, at 0.5 by +5.0pp (regular runs filtered to ABL), at 0.7 by −1.7pp — gap collapses as depth loosens. Consistent with n=100's +14.5pp at 15k/0.5 (paired analysis).
- **Backfill applied 2026-05-06 17:43:** 253 no-patch rows (132 depth-30 + 121 depth-70) with resolved=None → resolved=False.

### P100 expansion: 70 new tasks × 35 cells × 2 runs (4 452 new runs)
- **Status:** DONE
- **Started (first attempt):** 2026-04-30 12:13 CDT
- **Ended (sixth attempt):** 2026-05-05 20:07:50 CDT
- **Total wall-clock (incl. crashes/relaunches):** ~5d 8h
- **Total fresh runs:** 4 452 / 4 452 ✅ (matches plan exactly), 0 wrong-task entries
- **Total evaled patches:** 2 185
- **Final per-dir tally:**

| Dir | Fresh | Evaled (patches) |
|---|---|---|
| p100-inf | 146 | 65 |
| p100-singles-10000 | 665 | 252 |
| p100-singles-15000 | 583 | 311 |
| p100-singles-20000 | 628 | 120 |
| p100-trc-10000 | 400 | 244 |
| p100-trc-15000 | 374 | 249 |
| p100-trc-20000 | 396 | 270 |
| p100-otrc-10000 | 420 | 170 |
| p100-otrc-15000 | 420 | 250 |
| p100-otrc-20000 | 420 | 254 |

- **Known data issue (handed off to main chat):** non-patch fresh runs have `resolved=None` instead of `resolved=False` due to bug in `run_swebench_eval` (no save_results after no_patch loop). One-shot backfill required at §6.
- **vLLM:** restarted 2026-05-05 11:32 CDT (PID 1111264), still alive at task end.

### Failure-and-recovery history (kept for the main chat):
- **First attempt aborted:** 2026-04-30 12:13 CDT, PID 3861703 — died immediately with "unknown condition: summarization-full". Fixed via rename `summarization-full` → `summarization` in p100_inventory.py, p100_seed.py, run_p100_phase1.sh.
- **Second attempt aborted:** 2026-04-30 12:17 CDT, PID 3864657 — ran for ~4h on the WRONG 30 ablation tasks instead of the 70 new tasks. Root cause: `run_experiment.py:load_tasks()` ignored `--tasks-file` whenever `--ablation` was set. Patched run_experiment.py to honor `--tasks-file` even in ablation mode (added `TASKS_FILE_EXPLICIT` flag). Cleaned 295 wrong-task fresh entries from p100-singles-15000.
- **Third attempt crashed:** 2026-05-01 ~10:20 CDT (after ~18h, agent runs for p100-singles-15000 finished 700/700, then `--eval-only` crashed with KeyError on `r["patch_generated"]` because seeded stubs lack that field). Patched `run_swebench_eval()` to skip records with `seeded_from` flag.
- **Fourth attempt died:** 2026-05-02 (mid-run file move from `scripts/` to `task_lists/` invalidated bash-cached path in the for-loop; got `FileNotFoundError: scripts/p100_new_tasks.json`). Wrappers updated.
- **Fifth attempt:** 2026-05-02 15:53 → 2026-05-05 06:18 — Phase 1+2 fully clean; Phase 3 partial: vLLM crashed at 03:05 CDT (TimeoutError → EngineDeadError), so all 420 fresh runs in p100-otrc-20000 exited as InternalServerError.
- **Sixth attempt:** 2026-05-05 11:34 → 20:07 — vLLM restart + cleanup of garbage p100-otrc-20000 entries + chain re-launch; cleanly filled the missing 420 OTRC-20k fresh runs + their evals. Done.

### Files / scripts created (kept for §6 reference):
- `scripts/p100_inventory.py` (writes `task_lists/p100_new_tasks.json` + `scripts/p100_existing_runs.json`)
- `scripts/p100_seed.py` (idempotent — symlinks existing source data into p100-* dirs)
- `scripts/run_p100_chain.sh` → `run_p100_phase1.sh` → `phase2.sh` → `phase3.sh` (chained via `exec`)
- Patches: `TASKS_FILE_EXPLICIT` flag in run_experiment.py, `seeded_from` filter in `run_swebench_eval`
- **Workers:** 16, **Logs:** `logs/p100_chain.out`, `logs/p100_phase{1,2,3}.log`, `logs/vllm-qwen35.log`
- **Final master PID:** 1117086 (exited cleanly at 20:07:50 CDT)

---

### Partial-summary ablation (SU-partial + SS-partial + SS gap-fill)
- **Status:** DONE
- **Started:** 2026-04-28 16:20 CDT
- **Ended:** 2026-04-29 02:20 CDT
- **Wall-time:** ~10h 0m
- **PID:** 1904105 (exited cleanly)
- **Workers:** 16
- **Total runs:** 480 (all present, all evaled — `unevaled_patches=0` across all conditions)
- **Output dirs:** `results/ablations/partial-{10000,15000,20000}/`
- **Log:** `logs/partial_ablation.log`
- **Brief result table** (resolve % per condition × budget):

| condition | partial-10000 | partial-15000 | partial-20000 |
|---|---|---|---|
| summarization-partial          | 30 patches → ?? resolved | 40 → ?? | 43 → ?? |
| structured-summarize-partial   | 29 patches → ?? resolved | 40 → ?? | 45 → ?? |
| structured-summarize (gap-fill) | 23 patches → ?? resolved | (covered by 15k Fullrun) | 43 → ?? |

(Resolve counts available via §6 verification — not run in this chat per user instruction.)

### OTRC stacked ablation (OTRC+TR + OTRC+SU-partial + OTRC+SS-partial)
- **Status:** DONE
- **Started:** 2026-04-29 02:20:56 CDT (auto-launched by wrapper after partial-summary exited)
- **Ended:** 2026-04-29 13:32 CDT
- **Wall-time:** ~11h 11m
- **PID:** 3097797 (wrapper inherited via `exec`; exited cleanly)
- **Workers:** 16
- **Total runs:** 540 (all present, eval complete except 1 unevaled patch in otrc-stacked-20000/otrc-su-partial)
- **Output dirs:** `results/ablations/otrc-stacked-{10000,15000,20000}/`
- **Log:** `logs/otrc_stacked_ablation.log`
- **Wait log:** `logs/otrc_stacked_ablation.wait.log`
- **OTRC freeze-window hook fired:** median `online_trc_clears` per condition × budget all > 50 (range 52–90), confirms hook is active
- **Brief result table** (resolved / total = resolve %):

| condition | otrc-stacked-10000 | otrc-stacked-15000 | otrc-stacked-20000 |
|---|---|---|---|
| otrc-tr          | 28/60 (47%) | 33/60 (55%) | 40/60 (67%) |
| otrc-su-partial  | 29/60 (48%) | 39/60 (65%) | 37/60 (62%) |
| otrc-ss-partial  | 23/60 (38%) | 31/60 (52%) | 39/60 (65%) |

---

---

## Agent runs done, eval pending

### FC custom-prompt run — EVAL PENDING
- **Started**: 2026-04-20 14:20 — agent runs verified complete 2026-04-26 (PID 928353 no longer running)
- **Command**: `python3 scripts/run_experiment.py --model-tag qwen35-a3b_fc-customprompt --agent-config configs/config-fc-customprompt.yaml --conditions full-context --tasks-file selected_tasks.json`
- **Log**: `logs/fc_customprompt.log`
- **Results dir**: `results/qwen35-a3b_fc-customprompt/`
- **State**: 198/198 runs (99 tasks × 2), 152 patches generated, **0 evaluated** (resolved=None for all)
- **To finish**: re-run the same command with `--eval-only` to score the 152 patches
- **Purpose**: Isolate prompt effect — compare against FC-default (Fullrun) and online-TRC to determine how much of the resolve rate gap is prompt vs context strategy

---

## Fill Runs: 10k & 20k → 99 tasks (STOPPED)

Started 2026-04-26 13:41 CDT, stopped by user shortly after launch.
No partial results expected to be useful — all child processes killed.

### 10k fill — STOPPED
### 20k fill — STOPPED

---

## Ablation Runs (ABL-1 Timing + ABL-2 Depth)

### ABL-1 timing-10k
- **Name**: timing-10k
- **Command**: `python scripts/run_experiment.py --ablation timing-10k --budget 10000 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-20 20:47 CDT
- **End time**: 2026-04-21 01:13 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/timing-10k/`

### ABL-1 timing-20k
- **Name**: timing-20k
- **Command**: `python scripts/run_experiment.py --ablation timing-20k --budget 20000 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-21 01:13 CDT
- **End time**: 2026-04-21 05:38 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/timing-20k/`

### ABL-2 depth-40
- **Name**: depth-40
- **Command**: `python scripts/run_experiment.py --ablation depth-40 --budget 20000 --depth 0.4 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-21 05:38 CDT
- **End time**: 2026-04-21 10:23 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/depth-40/`

### ABL-2 depth-50
- **Name**: depth-50
- **Command**: `python scripts/run_experiment.py --ablation depth-50 --budget 20000 --depth 0.5 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-21 10:23 CDT
- **End time**: 2026-04-21 14:42 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/depth-50/`

### ABL-2 depth-60
- **Name**: depth-60
- **Command**: `python scripts/run_experiment.py --ablation depth-60 --budget 20000 --depth 0.6 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-21 14:42 CDT
- **End time**: 2026-04-21 19:17 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/depth-60/`

### ABL-2 depth-70
- **Name**: depth-70
- **Command**: `python scripts/run_experiment.py --ablation depth-70 --budget 20000 --depth 0.7 --conditions truncation summarization tool-result-clear`
- **Start time**: 2026-04-21 19:17 CDT
- **End time**: 2026-04-21 23:51 CDT
- **Expected run count**: 180 (30 tasks × 3 conditions × 2 runs)
- **Status**: DONE
- **Results dir**: `results/ablations/depth-70/`

### ABL-3 stacked (trc-su, trc-ss) at 10k / 15k / 20k
- **Names**: `stacked-10000`, `stacked-15000`, `stacked-20000`
- **Command (per stage)**: `python scripts/run_experiment.py --ablation stacked-{B} --budget {B} --conditions trc-su trc-ss` followed by the same command with `--eval-only`
- **Start time**: 2026-04-26 13:56 CDT
- **End time**: 2026-04-26 21:14 CDT (~7h17m total)
- **Run count**: 360 (30 tasks × 2 conditions × 2 runs × 3 budgets)
- **Workers**: 16 (bumped from 8 for this run; see `scripts/run_experiment.py:94`)
- **Status**: DONE
- **Results dirs**:
  - `results/ablations/stacked-10000/` — trc-su 55.0% / trc-ss 60.0%
  - `results/ablations/stacked-15000/` — trc-su 65.0% / trc-ss 58.3%
  - `results/ablations/stacked-20000/` — trc-su 66.7% / trc-ss 76.7%
- **Code changes that landed**:
  - `memory.py` (now `src/agentctx/compression/primitives.py`): `tool_result_clear(..., fallback_truncate=False)` skips built-in TR fallback so a caller can run a second primitive
  - `mini-swe-agent/.../default.py`: new primitives `trc_summarize` and `trc_structured_summarize` (TRC then SU/SS)
  - `scripts/run_experiment.py` (conditions now live in `src/agentctx/experiments/conditions.py`): new conditions `trc-su` and `trc-ss`
- **Headline finding**: stacking lift narrows with budget — +11.7pp at 10k (trc-ss vs best single), +13.3pp at 15k (trc-su vs best single matched), only +5.0pp at 20k for trc-ss and **−5.0pp at 20k for trc-su**. At loose budgets where TRC alone already works well, the cascade's extra summarization step destroys capability TRC was preserving. This budget-dependent pattern motivates the OCC two-tier framing (proactive online-TRC keeps headroom; reactive cascade only fires when budget is tight).

---

## Completed Runs (reference)

| Tag | Conditions | Tasks×Runs | Patch rate | Notes |
|-----|-----------|------------|-----------|-------|
| `qwen3.5-35B-A3B_15k_Fullrun` | full-context, truncation, summarization, structured-summarize, tool-result-clear | 99×2 | fc:76% patch, 25% resolve | E1 main run, 15k budget, default prompt |
| `qwen35-a3b_online-trc` | online-trc | 99×2 | 68% patch, 46% resolve | Online proactive TRC, custom prompt, eval complete |
| `qwen35-a3b_20k` | full-context, truncation, summarization, structured-summarize, tool-result-clear | 30×2 | fc:28.3%, trc:28.3% resolved | 20k budget, 30 tasks only |
| `qwen35-a3b_trc20k-fill` | tool-result-clear @ 20k | 70×2 = 140 runs | 84% patch | Fills TRC-20k to 99 tasks; combine with qwen35-a3b_20k for full coverage |
| `online-trc-pilot` | full-context, online-trc, online-trc-20k | 5×1 | otrc:4/5 resolved | Pilot v6 — freeze k=4 validated |
