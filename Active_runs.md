# Active Experiment Runs

## Currently Running

### Albus environment ready (Phase 1 prep complete; §1.3a not yet launched)
- **Hardware:** 8× A6000 on Albus, vLLM DP=8 serving Qwen2.5-7B-Instruct (port 8000, 1 replica/GPU)
- **Mini pilot done** (5 tasks × FC + OTRC × 2 reps = 20 runs): symmetric outcomes (4 Submitted + 6 LimitsExceeded per condition), 0 errors.
- **Pre-§1.3a fixes landed:**
  - `config-online-trc.yaml` stripped to delta (prompt only, no `model:`/`environment:`)
  - `run_experiment.py`: `--n-tasks` now slices ablation lists; `--max-workers` flag (default 16); OTRC chain layers `--agent-config` after the OTRC config so model wins
  - 4 step scripts added under `scripts/run_qwen25_7b_step{1,3}.sh` and `scripts/run_llama33_70b_step{1,3}.sh`, all `setsid`-launchable for clean process-group cleanup
- **Env setup notes (Albus-specific, not on Dobby):** rootless podman 5.8.2 at `~/.local/bin/`, DOCKER_HOST→podman socket, pinned `vllm==0.11.0` + `transformers<5.0` (vllm latest pulled cu130 incompatible with driver 12.9).
- **Dobby compatibility verified:** Dobby's run_p100_*.sh scripts don't pass any of the new flags → defaults preserved → identical behavior including upcoming OTRC stack phase.



### P100 expansion: 70 new tasks × 35 cells × 2 runs (4 452 new runs)
- **Status:** RUNNING
- **First attempt aborted:** 2026-04-30 12:13 CDT, PID 3861703 — died immediately with "unknown condition: summarization-full". Fixed via rename `summarization-full` → `summarization` in p100_inventory.py, p100_seed.py, run_p100_phase1.sh (Option A from earlier).
- **Second attempt aborted:** 2026-04-30 12:17 CDT, PID 3864657 — ran for ~4h on the WRONG 30 ablation tasks instead of the 70 new tasks. Root cause: `run_experiment.py:load_tasks()` ignored `--tasks-file` whenever `--ablation` was set. Patched run_experiment.py to honor `--tasks-file` even in ablation mode (added `TASKS_FILE_EXPLICIT` flag). Cleaned 295 wrong-task fresh entries from p100-singles-15000.
- **Started (third attempt):** 2026-04-30 16:19 CDT
- **Third attempt crashed:** 2026-05-01 ~10:20 CDT (after ~18h, agent runs for p100-singles-15000 finished 700/700, then `--eval-only` crashed with KeyError on `r["patch_generated"]` because seeded stubs lack that field). Patched `run_swebench_eval()` to skip records with `seeded_from` flag.
- **Started (fourth attempt):** 2026-05-01 11:37 CDT
- **Fourth attempt died:** 2026-05-02 (mid-run file move from `scripts/` to `task_lists/` invalidated bash-cached path in the for-loop; got `FileNotFoundError: scripts/p100_new_tasks.json`). Wrappers now updated; no further file moves planned.
- **Progress preserved:** p100-singles-15000 (700 agents + 303 evals) + p100-singles-10000 (700 agents) all on disk and resumable.
- **Started (fifth attempt):** 2026-05-02 15:53 CDT
- **PID:** 2743033
- **Phase 1 DONE:** 2026-05-03 05:33 CDT (~14h after fifth-attempt launch — all 4 sub-budgets complete: singles-10k/15k/20k + inf, fresh runs 2022, evals all clean, 0 wrong-task)
- **Phase 2 in progress:** started 2026-05-03 05:33 CDT, currently in p100-trc-15000 eval (~90% of that sub-budget)
- **Workers:** 16
- **Phases:** 1 (singles+∞) → 2 (TRC stack) → 3 (OTRC stack), chained via `exec`
- **Logs:** `logs/p100_chain.out`, `logs/p100_phase{1,2,3}.log`
- **PID file:** `logs/p100_chain.pid`
- **Output dirs:**
  - `results/ablations/p100-singles-{10000,15000,20000}/`
  - `results/ablations/p100-trc-{10000,15000,20000}/`
  - `results/ablations/p100-otrc-{10000,15000,20000}/`
  - `results/ablations/p100-inf/`
- **Inventory:** 448 existing runs reused (374 with full symlinks, 74 summarization-full with stubs only — known issue, fine for §6 since build_review1.py reads from source paths regardless)
- **ETA:** ~65h wall-clock (~3 days from start)

---

## Recently Completed

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
- **Command**: `python3 scripts/run_experiment.py --model-tag qwen35-a3b_fc-customprompt --agent-config config-fc-customprompt.yaml --conditions full-context --tasks-file selected_tasks.json`
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
  - `memory.py`: `tool_result_clear(..., fallback_truncate=False)` skips built-in TR fallback so a caller can run a second primitive
  - `mini-swe-agent/.../default.py`: new primitives `trc_summarize` and `trc_structured_summarize` (TRC then SU/SS)
  - `scripts/run_experiment.py`: new conditions `trc-su` and `trc-ss`
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
