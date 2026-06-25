# Active Experiment Runs

## Currently Running

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
  - `config-llama33-vllm.yaml`, `config-online-trc-llama33.yaml` — Llama configs, not used
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
