# ICLR 2027 Experiment Log
Experiment Plan → [ICLR_experiments/FOLLOWUP_EXPERIMENTS.md](../ICLR_experiments/FOLLOWUP_EXPERIMENTS.md)

> **Note: this file is a historical log.** Commands, script paths, and code
> locations are recorded exactly as they were when each entry was written and
> are intentionally not updated when the repository is reorganized, so they may
> not match the current tree (e.g. scripts have since moved under
> `scripts/{calibration,expansions,serving,harbor,maintenance}/` and shared
> code into `src/agentctx/`). For present-day paths see `scripts/README.md` and
> `CLAUDE.md`; for the code as it was at a given entry, check out the commit
> hash recorded there.

## Follow-up 1 — Runs/task 2 → 3
- Started: 2026-08-23 17:24:53 CDT
- Code version used:  `27606ac14f4ff4bb96caf429984ad8fd26325cba`
    - Provenance note: The experiment was launched before this change was
    committed. At launch, HEAD was `f8cd6f9`; the relevant working-tree changes
    were committed unchanged as `27606ac`.
- Results root: `results/ablations/`
    - Canonical location: `data/swebench/ablations/`
    - `results/ablations/` is a symlink to the canonical location above.
    - Each experiment cell stores its aggregate metadata in
      `<results-root>/<cell>/experiment_results.json` and per-task artifacts in
      `<results-root>/<cell>/<instance_id>/<condition>/run_3/`.
    - The same cell directories also contain the earlier `run_1` and `run_2`;
      this follow-up experiment adds the `run_3` artifacts.
- Experiment cell directories:
    - P100: `p100-singles-{10000,15000,20000}`,
      `p100-trc-{10000,15000,20000}`,
      `p100-otrc-{10000,15000,20000}`, and `p100-inf`
    - ABL-30 depth ablations: `p100-depth{30,70}-singles-{10000,15000,20000}`
    - ABL-30 existing/canonical cells: `timing-{10k,20k}`,
      `partial-{10000,15000,20000}`, `stacked-{10000,15000,20000}`,
      `otrc-stacked-{10000,15000,20000}`,
      `qwen3.5-35B-A3B_15k_Fullrun`, and `qwen35-a3b_online-trc`
- Runtime logs: `logs/run3_expansion.log` and
  `logs/run3_expansion.nohup.log` (local, gitignored)
- [DONE] 2026-08-28: Ran `scripts/archive_and_organize_qwen35b_swebench.py`
  (HEAD `cb5d3771791cbca0e05f1ff1f71177ec4e902051`, script last changed in
  `8f9a50bf8fe7943059148af11cc09525453a0eed`) to copy the result files under
  `ICLR_experiments/`:
  ```bash
  python3 scripts/archive_and_organize_qwen35b_swebench.py \
    --backup-root /home/ak58925/agentCtx_backups/run3-complete-2026-08-28
  ```
  All 65 cells (`main/qwen35b`: 35, `ablation/qwen35b`: 30) reported COMPLETE.

## Follow-up 2 — Agent model expansion

### Budget calibration protocol

The Devstral SB:P100 budget calibration was run with code from commit
`0d42a9b4c9a9706e0b05eb3c1128d9b117369414` (calibration artifacts completed
2026-08-28 14:06 CDT).

Calibrate each model independently from context growth in **100 uncompressed
trajectories** (SB:P100 × run_1). These are stored directly as the FC run_1
portion of experiment 2.a/2.b, so calibration does not duplicate agent runs.
For every trajectory, take
`max(step_prompt_tokens)`, then choose `A/P/B` thresholds whose compression
trigger rates match the Qwen3.5 reference rates `97% / 88% / 76%` within ±5pp.
The calculation and 1K rounding are implemented in
`Review1/calibrate_budgets.py`.

1. Start the model server and verify its `/v1/models` endpoint.
2. Collect FC trajectories and calculate budgets (resumable):

   ```bash
   # Devstral (also produces experiment 2.a FC run_1)
   setsid venv/bin/python scripts/run_budget_calibration_sb.py \
     --model-key devstral24b \
     --agent-config configs/config-devstral-vllm.yaml \
     > logs/devstral_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/devstral_budget_calibration.pid

   # GLM (also produces experiment 2.b FC run_1; after its config exists)
   setsid venv/bin/python scripts/run_budget_calibration_sb.py \
     --model-key glm47flash \
     --agent-config configs/config-glm47flash-vllm.yaml \
     > logs/glm_budget_calibration.nohup.log 2>&1 &
   echo $! > logs/glm_budget_calibration.pid
   ```

3. Inspect the generated file and require `ALL_WITHIN_TOLERANCE=true`:

   ```bash
   cat ICLR_experiments/swebench/main/devstral24b/di__binf__fc/calibrated_budgets.sh
   cat ICLR_experiments/swebench/main/glm47flash/di__binf__fc/calibrated_budgets.sh
   ```

   The earlier ABL-30 × 2 Devstral estimate was `A/P/B = 15000/20000/24000`.
   Treat it as a comparison point, not a required result: the canonical P100 ×
   run_1 distribution may differ. If a value collides after rounding or falls
   outside tolerance, stop for manual review; do not silently substitute Qwen
   budgets.

4. Review the calibration output, record the final adopted values, and pass
   them to the expansion launcher. Devstral uses the finalized
   `A/P/B = 17000/21000/24000` defaults; GLM remains explicit:

   ```bash
   source ICLR_experiments/swebench/main/glm47flash/di__binf__fc/calibrated_budgets.sh
   GLM_A_BUDGET="$TIGHT_BUDGET" \
   GLM_P_BUDGET="$MEDIUM_BUDGET" \
   GLM_B_BUDGET="$LOOSE_BUDGET" \
     setsid bash scripts/run_agent_models_expansion.sh glm \
     > logs/agent_models_glm.out 2>&1 &
   echo $! > logs/agent_models_glm.pid
   ```

Artifacts to retain for provenance:

- `ICLR_experiments/swebench/main/<model>/di__binf__fc/experiment_results.json`
- `ICLR_experiments/swebench/main/<model>/di__binf__fc/<instance>/full-context/run_1/`
- `ICLR_experiments/swebench/main/<model>/di__binf__fc/fc_context_distribution.json`
- `ICLR_experiments/swebench/main/<model>/di__binf__fc/{calibration_report.txt,calibrated_budgets.sh}`
- the launch PID, code version, model ID, context-window setting, and approval
  decision recorded below

The reusable FC launcher below collects exactly `run_1` for every selected
task and writes it directly into the canonical ICLR cell. It then calculates
the percentile report and rebuilds `COVERAGE.csv` and `DASHBOARD.html`.

```bash
# SWE-Bench P100 (counts as the FC run_1 portion of 2.a or 2.b)
venv/bin/python scripts/run_budget_calibration_sb.py \
  --model-key devstral24b \
  --agent-config configs/config-devstral-vllm.yaml \
  --tasks-file task_lists/p100_all_100_tasks.json

# GLM (after adding its model config)
venv/bin/python scripts/run_budget_calibration_sb.py \
  --model-key glm47flash \
  --agent-config configs/config-glm47flash-vllm.yaml \
  --tasks-file task_lists/p100_all_100_tasks.json
```

Outputs are stored under
`ICLR_experiments/swebench/main/<model>/di__binf__fc/`, including
`experiment_results.json` (all per-step prompt-token arrays), raw per-task
artifacts, `fc_context_distribution.json`, `calibration_report.txt`, and
`calibrated_budgets.sh`. FC never
invokes a summarizer, so only the agent model is configured for this stage.
The calibration report explicitly filters `run_num == 1`, so adding run_2 and
run_3 to the same canonical FC cell later cannot change the saved calibration
distribution.
SWE-Bench patch evaluation is enabled by default so these are complete
experimental run_1 records; pass `--skip-eval` only when evaluation will be
resumed separately later.

### Devstral (2.a)/(2.c) launch commands

The Devstral (2.a)/(2.c) expansion was initially launched with code from
commit `20df6a5362a3611add3991d3a07aa4fd5b87437a` on 2026-08-29 00:30 CDT.
It was resumed on 2026-08-31 02:34:19 CDT with launcher PID `2882597`;
`logs/followup_agent_models_devstral_launcher.log` begins this resume at the
`main/devstral24b/d05__b21k__tr` cell. The launcher and experiment logs were
still being updated on 2026-08-31 13:37 CDT.

The experiment worker concurrency is fixed at **16**. The vLLM
`--max-num-seqs 64` setting is the server-side capacity, not the experiment
worker concurrency.

```bash
cd /home/ak58925/agentCtx

# Inspect the existing experiment and model-server processes.
pgrep -af 'run_agent_models_expansion|run_experiment_iclr|swebench_single|minisweagent'
pgrep -af 'vllm.entrypoints.openai.api_server'
nvidia-smi
ss -ltnp | grep -E ':8000|:8001|:8002|:8003' || true

# Stop the previous GLM-4.7-Flash vLLM server found on port 8003.
# Process at inspection time:
# 3783208 .../venv-glm-cu129-clean/bin/python -m
# vllm.entrypoints.openai.api_server --model zai-org/GLM-4.7-Flash
# --port 8003 ...
kill -TERM 3783208

# Wait for and verify shutdown.
for i in $(seq 1 30); do
    kill -0 3783208 2>/dev/null || break
    sleep 2
done
ps -fp 3783208
pgrep -af 'vllm.entrypoints.openai.api_server' || echo 'vLLM stopped'
nvidia-smi

# Start Devstral-Small-2-24B-Instruct-2512 on GPUs 0,1,2,3 / port 8002.
bash scripts/serving/start_vllm_devstral.sh

# Inspect startup. Exit tail with Ctrl-C after the server is ready.
tail -f logs/vllm_devstral.log

# Verify the model endpoint and process.
curl -fsS http://localhost:8002/v1/models | python3 -m json.tool
ps -fp "$(cat logs/vllm_devstral.pid)"
nvidia-smi

# Launch both (2.a) P100 main and (2.c) ABL-30 ablation, with concurrency 16.
nohup env MAX_WORKERS=16 RUN_EVAL=1 \
    bash scripts/run_agent_models_expansion.sh devstral \
    > logs/followup_agent_models_devstral_launcher.log 2>&1 &
echo $! | tee logs/followup_agent_models_devstral_launcher.pid

# Verify that the runner received --max-workers 16.
ps -fp "$(cat logs/followup_agent_models_devstral_launcher.pid)"
pgrep -af 'run_experiment_iclr.py'

# Monitor experiment and launcher logs.
tail -f logs/followup_agent_models_devstral.log
tail -f logs/followup_agent_models_devstral_launcher.log
```

The launcher runs (2.a) first and then (2.c), and skips completed
task/condition/run keys when resumed.

#### Devstral status — 2026-08-31 13:45 CDT

- Calibration completed 2026-08-28 14:06 CDT from 100 FC run_1 trajectories.
  The trigger-rate-matching report produced the reference values
  `A/P/B = 16000/19000/23000`, trigger rates `96%/90%/77%`, and
  `ALL_WITHIN_TOLERANCE=true`. After review, the experiment's final adopted
  budgets were `A/P/B = 17000/21000/24000` using the P5/P15/P25 rule.
- The initial launch used commit
  `20df6a5362a3611add3991d3a07aa4fd5b87437a`; the current resume began at
  2026-08-31 02:34:19 CDT with launcher PID `2882597`.
- Runtime logs: `logs/followup_agent_models_devstral_launcher.log` and
  `logs/followup_agent_models_devstral.log`; model-server log and recorded PID:
  `logs/vllm_devstral.log` and `logs/vllm_devstral.pid` (`2253428`).
- Current P100 coverage snapshot: FC, OTRC, TR@21k, and SU-full@21k are
  complete at 300/300 runs each. SU-partial@21k is in progress (108/300 rows
  on disk, 37/100 tasks represented in the latest `COVERAGE.csv`). The ABL-30
  phase has not started because the launcher runs it after the P100 phase.
- **Final budget decision:** Devstral runs use `17000/21000/24000`. P100 main
  uses the 21k medium budget; the later ABL-30 phase uses all three budgets.
  The launcher changes were uncommitted when the 2026-08-31 02:34 resume began
  and were later committed unchanged as
  `7b4bbe407a05c769d495af2219e9110c10d02c53` (`fix: FIX BUDGETS`) at 13:44
  CDT. Existing 21k results are therefore part of the intended grid and do not
  require replacement or backfill at 19k.
- [TODO] Record final completion status and end time after the launcher exits.
- [TODO] Create the GLM agent/OTRC configs and vLLM launcher, then calibrate its `A/P/B` budgets with the protocol above.
- [TODO] Start and verify the GLM vLLM server on the configured endpoint.
- [TODO] Launch GLM: `GLM_A_BUDGET=<A> GLM_P_BUDGET=<P> GLM_B_BUDGET=<B> setsid bash scripts/run_agent_models_expansion.sh glm > logs/agent_models_glm.out 2>&1 &`.
- [TODO] Record the start time, code version, PID, calibrated budgets, and runtime log paths here.

## 2026-09-07 — Summary-bug rerun and Qwen SWE-Bench resume

Summary calls incorrectly required a bash command, causing FormatErrors and
making affected runs require rerunning. After applying the fix, 2,359 local
SWE-Bench runs with `summary_marker_error` were archived and their result-index
entries removed where present. See
[ARCHIVE_LOG.md](../archives/summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md)
for the audit, selection rules, archive tooling, and Qwen result-reuse details.

- Qwen resumed: **2026-09-07 20:01:53 CDT**, as recorded in the launcher log.
- Resume commit (HEAD): **`da461d6`**. The working tree also contains an
  uncommitted `scripts/run_experiment.py` change recording `step_completion_tokens`.
- Scope: P100 main first, then ABL-30 ablation, with 3 runs/task, 16 workers,
  and evaluation enabled. Existing result keys are skipped; archived/missing
  keys in this grid are rerun. The 10K/20K depth=0.5 and depth-invariant arms
  use ABL-30; 1,761 existing runs across 22 cells were copied into ablation.
- Slack notifications: experiment start and final success/failure.
- Runtime log: `logs/followup_agent_models_qwen_launcher.log`.

Resume command (Qwen vLLM on port 8000, the rootless Podman API, and
`SLACK_WEBHOOK_URL` must already be configured):

```bash
cd /home/ak58925/agentCtx
mkdir -p logs
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"

nohup env MAX_WORKERS=16 RUN_EVAL=1 \
  PYTHON="$PWD/venv/bin/python3" \
  QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 \
  bash scripts/run_agent_models_expansion_notified.sh qwen \
  >> logs/followup_agent_models_qwen_launcher.log 2>&1 < /dev/null &
echo $! > logs/followup_agent_models_qwen_launcher.pid
```

## Harness bug — online-TRC hook cleared the task statement (fixed 2026-09-23)
- Affects every OTRC-family cell (`otrc`, `otrc-tr`, `otrc-su-partial`,
  `otrc-ss-partial`) run before submodule commit `b54c485`
  (`takeshiho0531/mini-swe-agent`, branch `event-log`), i.e. all OTRC data
  currently under `ICLR_experiments/` for both benchmarks and all models.
- Mechanism: `DefaultAgent.query()` rewrote `messages[-9]` by position.
  FormatErrors (user message, no assistant reply) and odd-count truncations
  shift message parity; with `len(messages) == 10` the hook overwrote
  `messages[1]` (the task statement) with `[tool-result cleared …]`, and with
  a FormatError inside the last 9 messages it cleared assistant turns.
- Detection: `messages[1].content` starts with `[tool-result cleared`.
  qwen35b SWE-bench main: 225/2483 OTRC runs affected, 0/225 resolved
  (169 LimitsExceeded, 56 silent_crash); worst cell `di__b10k__otrc-tr`
  111/300. devstral24b main ≈ 55/300 per cell; Terminal-Bench main up to
  78/120 (`glm47flash di__b3k__otrc-tr`). 1651/2483 qwen35b main OTRC runs
  had at least one assistant turn cleared.
- Fix: target selected by role (user messages at index ≥ `N_PROTECTED`,
  excluding summaries/stubs; newest FREEZE_K kept verbatim). Regression
  tests: `mini-swe-agent/tests/agents/test_online_trc.py`.
- Existing OTRC results are NOT re-run yet; any OTRC number quoted from
  pre-fix data must either exclude affected runs or be re-collected.

## Evaluation bug — ungraded SWE-bench attempts stored as `resolved=False` (fixed 2026-09-11, verdicts corrected 09-11 and 09-24)
- Symptom: attempts with `patch_generated=True` and a saved `submission` carried
  `resolved=False` in `experiment_results.json` with no evaluation evidence
  anywhere (no `<cell>/eval/<model_tag>.<key>.json`, no `report.json` under
  `eval/logs/run_evaluation/`, not listed in any aggregate report). Found by
  the 2026-09-10 audits (`ICLR_experiments/issue/{qwen_main,devstral_summary,devstral_rule_otrc}_20260910/`,
  category `legacy_evaluation_reports_missing`; dirs removed 09-26, see
  "Data audits" below); the same check on the ablation track on 09-24 found
  155 more.
- Not random: Qwen main hit 8 heavy-test-suite tasks only (django-13012,
  scikit-learn-13328/-14496/-15100/-26323, sympy-15017/-19637/-24443), runs 1
  and 2 only, in the 5 cells generated and graded 2026-03-30..04-09
  (`di__binf__fc`, `d05__b15k__tr`, `di__b15k__trc`, `d05__b15k__ss`,
  `d05__b15k__su-full`). Run 3 of the same tasks, graded Aug–Sep with the
  fixed harness, has complete reports.
- Cause (best-supported): the grading code of that period
  (`scripts/run_experiment.py`, `f064da2` 2026-03-15 … `dfda60c` 2026-05-03;
  later `scripts/bench_adapters/swe_bench.py`, now
  `src/agentctx/benchmarks/swe_bench.py`) called `swebench.harness.run_evaluation`
  with a 600 s `subprocess` timeout covering image pull/build *and* the tests,
  no harness `--timeout`, no OpenMP/BLAS thread cap inside the container (128
  host cores → small-data suites spin in thread synchronisation), and the
  default cache level (instance image deleted after every run). When the
  subprocess was killed nothing was written, the adapter returned `None`, and
  a later eval-only/consolidation pass stored the missing verdict as `False`.
  The exact writer cannot be reconstructed: the March launcher logs are gone
  and the pre-merge source index
  (`data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/`) already has False.
  A second mechanism (Devstral/GLM, `devstral_summary_20260910`): the adapter
  reused the same `run_id`/model tag after saving a new prediction, so the
  harness found an old `report.json`, skipped evaluation and returned the
  stale verdict for a different patch (224 records).
- Fix `34ac3cb` (2026-09-11, `scripts/bench_adapters/swe_bench.py` +
  new `scripts/swebench_eval_wrapper.py`): harness `--timeout 1800` (lowered to
  600 in `90a4899`), subprocess timeout = test timeout + 900 s,
  `SWEBENCH_EVAL_THREADS=8` exported into the container via the wrapper,
  `--cache_level instance`, and a missing report now returns `None` (retried)
  instead of False; `unresolved_ids` and patch-apply failures in the instance
  log are the only paths that return False. Verified with the 09-23 run:
  every audited row that *had* a report reproduced exactly, and no row flipped
  True→False.
- Re-evaluation tooling `b244237` (`scripts/maintenance/reevaluate_swebench_candidates.py`
  `plan` / `run` / `apply`, `scripts/maintenance/build_reevaluation_candidates.py`):
  re-runs the official harness on the **saved submission patch** only (no agent,
  no LLM), checks patch identity by SHA-256 (`manifest.json`: `patch_sha256`,
  `generation_sha256`), writes only under `--output-dir`, and `apply --write`
  backs up every touched `experiment_results.json` next to a `changes.json`
  before rewriting `resolved` (each changed row gets a `reevaluation`
  provenance block). Output-dir guard relaxed in `88fcc61` so `--output-dir`
  may be `ICLR_experiments/reeval_evidence/<run>/` (committed evidence:
  `manifest.json`, `results.json`, `verdict_comparison.csv`; `jobs/` and
  `backups/` gitignored). The 09-21 reorganization (`e8dcedb`) re-protected
  all of `ICLR_experiments`; on 09-26 `PROTECTED_ROOTS` was narrowed to
  `ICLR_experiments/{swebench,terminalbench}`, `results`, `data` (uncommitted
  with the `ICLR_reeval` → `reeval_evidence` rename).
- Corrections applied (run details in the dated entries below):

  | Date | Scope | Candidates | Result |
  |---|---|---:|---|
  | 09-11 | Devstral main | 269 | 174 True / 94 False / 1 unverified |
  | 09-11 | Qwen main (first pass) | 150 | 84 True / 66 False |
  | 09-11 | GLM main | 37 | 22 True / 14 False / 1 unverified |
  | 09-24 | Qwen main (`review` rows of the 09-10 audit, incl. the 140 from 09-11) | 253 | 253 verified; vs the index after 09-11: **60 False→True, 0 True→False** |
  | 09-24 | Qwen ABL-25 ablation (10K/20K, D=0.3/0.7 cells) | 155 | 155 verified, all stay False (0 flips) |

  Qwen main flips by cell: `di__b15k__trc` 14, `d05__b15k__tr` 13,
  `di__binf__fc` 12, `d05__b15k__ss` 8, `d05__b15k__su-full` 8,
  `d05__b20k__ss-partial` 2, `d05__b15k__su-partial` 1,
  `d05__b20k__su-partial` 1, `d05__b20k__su-full` 1; by run 24/29/7.
- Downstream: `analysis/outcomes/swebench_outcomes.csv` rebuilt with
  `analysis/aggregate_benchmark_results.py --benchmark swebench` after each
  apply (09-24: 60 of 29,527 rows change, only `resolved` and the derived
  `failure_mode`). Before the apply, `analysis/apply_reeval_outcomes.py`
  (`eeca0b6`) produced a non-canonical copy of the table with the flips
  applied (`ICLR_experiments/ICLR_analysis/outcome/swebench_outcomes_reeval.csv`,
  gitignored) for the figure scripts; both are obsolete since the canonical
  table carries the verdicts, and the script was removed on 09-26. Every
  `plot_bank.py` tool, including `task-map-reeval` / `depth-trigger-reeval`,
  reads `analysis/outcomes/swebench_outcomes.csv` by default.
- Effect on paper numbers (Qwen SWE-bench only; tokens, latency, cost, TB,
  Devstral, GLM unchanged). P100 attempt-level resolve: FC 49.0 → 53.0, TR
  40.0 → 44.3, TRC 49.0 → 53.7, SU 39.3 → 42.0, SS 40.3 → 43.0, SU-p 48.7 → 49.0;
  every other policy's Δ vs FC shifts by −4.0 pp. No policy is above FC any
  more (best TRC +0.7 pp, CI [−4.0, +5.0]; TRC+SU +3.0 → −1.0). Task map
  (≥2 of 3): FC 53 (was 46). ABL-25 knob table: only D=0.5/15K cells and the
  FC header move (FC 53.3 → 65.3, TR 36.0 → 46.7, SU 42.7 → 53.3,
  SS 45.3 → 54.7, SU-p 60.0 → 61.3); all 10K/20K and D=0.3/0.7 cells were
  re-evaluated on 09-24 with no change.

## Adapter fix — no-patch runs now persisted as `resolved=False` (2026-09-26)
- Before: `evaluate_results()` (`src/agentctx/benchmarks/swe_bench.py`) set
  `resolved=False` on runs without a patch only *after* its last `save()`, so
  on the plain evaluation path (no explicit `--tasks-file`) the value stayed
  `null` on disk. Reported in `Active_runs.md` (2026-05, "no save_results
  after no_patch loop"); the canonical SWE outcomes table has 2,476 such rows
  (of 8,168 no-patch rows). Aggregation and figures already treat a missing
  verdict as unresolved (`failure_mode` comes from `patch_generated`), so no
  number changes.
- After: the adapter saves once more if it changed any no-patch row. Nothing
  is rewritten until a cell's evaluation pass runs again (`--eval-only`,
  resume); from then on that cell's `null` rows become `False`, which changes
  the index file's SHA256. A hash difference on an index with no other
  change is expected after this date. A one-shot backfill of the remaining
  `null` rows has not been run.
- Tests: `tests/test_runner_equivalence.py` asserts the new value;
  `tests/harness.py` normalizes the reference branch's `null` to `False`
  for the equivalence diff (listed under "Intentional differences" in
  `tests/README.md`).

## Data audits 2026-09-08 → 09-24 — findings and how each was closed
Read-only audits of the canonical indexes, formerly one directory each under
`ICLR_experiments/issue/<name>/` (README + scripts + candidate CSVs). The
closed ones were removed from the tree on 2026-09-26; their files are in git
at `4baa6fb` (09-10 audits), `b6b9f75` (review-253 lists) and `8caf652`
(ablation-155 list). Still open, kept under `issue/`:
`resume_audit_20260908/`, `qwen_fc_15min_1hour_20260910/` (see the end).

### `devstral_summary_20260910` — Devstral main SU/SU-p/SS/SS-p/TRC+SU/TRC+SS @21K (closed 09-11)
- Question: after the summary-bug reruns of 09-09/10 (241/238/221/218/50/45
  runs per cell), are the retained originals and the reruns consistent, and
  do all runs need regenerating? Answer: no regeneration. 1,800 records, no
  duplicate keys, index/token_log/trajectory agree, configs identical to the
  archived originals (temperature 0.2, max_tokens 4096, step_limit 125,
  budget 21000, D=0.5, mini_version 2.2.6), max concurrency 16 reconstructed
  from timestamp−e2e, all `agent.log`s `no_summary_evidence`.
- Bug found: **stale verdicts**. `scripts/bench_adapters/swe_bench.py` called
  the harness with the same `run_id`/model tag after saving a new prediction;
  `run_evaluation.py` saw the existing `report.json` and returned the old
  verdict without comparing patches. 224 records had a `patch.diff` under
  the old report that differs from the current submission (e.g.
  `d05__b21k__su-full/django-11292 r1`: generated 09-09 15:37, report dated
  08-31). Plus 14 container-409 errors and 3 harness timeouts, all
  `scikit-learn-14710` (14 stored False, 3 null).
- Closed: 241 candidates re-graded on 09-11 (part of the Devstral 269 pass,
  see "Evaluation bug" and the 09-10/11 entry). Fix for the mechanism:
  `34ac3cb` (isolated eval dir per re-evaluation, `None` instead of stale/False).

### `devstral_rule_otrc_20260910` — Devstral main TR/TRC/OTRC family @21K + OTRC@∞ (closed 09-11)
- Same checks for the 6 rule-based cells (1,800 records). All OTRC records
  have `online_trc_clears > 0`, TR/TRC 0; configs differ only in
  `system_template`. The TR cell's 08-31 launch had 244 `calls=0` failures
  before the 02:34 resume; all were replaced, the 21 + 279 current records
  don't overlap in time, so TR was not discarded. OTRC@∞ is the dedicated
  09-03 rerun (300 unique keys in `logs/devstral24b_p100_otrc_rerun.log`).
- Bug found: 11 more stale reports (4 OTRC+SU-p, 7 OTRC+SS-p, the 09-10
  partial reruns), 16 container-409 and 1 timeout (15× sklearn-14710,
  sympy-19637, sympy-18189).
- Closed: 28 candidates, combined with the 241 above into the 269-row
  Devstral pass of 09-11 (174 True / 94 False / 1 unverified:
  `sympy-18189 otrc r3`).

### `qwen_main_20260910` + `reeval_candidates_qwen35b_main_20260910` + `..._review253_20260923` — Qwen main, 35 cells / 7,893 records (closed 09-24)
- Classification of every record by evidence: 667 fully verified (internal
  report + patch + index agree), 4,573 verified only through old aggregate
  reports (`report.json`/`patch.diff` missing), 2,359 `patch_generated=False`,
  20 current-patch apply failures, and the problem groups below.
- Bugs found: (a) 150 records with `evaluation_error_recorded_as_false`
  (harness ERROR, mostly sklearn-14710: 56 rows), (b) 253 `review` rows: 46
  prediction/submission mismatches without internal report, 140 listed in
  old `error_ids`, 60 with no evaluation evidence at all, 7 verdict
  mismatches between old aggregate reports and the index; (c) 1
  result-sync case where the internal report says True but the index has
  None (`d05__b15k__ss / django-17087 / run_2`).
- Closed: (a) 09-11 pass, 150 rows → 84 True / 66 False. (b) 09-23 pass on
  all 253 (the 140 already re-graded reproduced exactly) → 60 False→True,
  applied 09-24. The 60 are the "Evaluation bug" cohort. (c) **not done**:
  the outcomes table still has `resolved` empty for that run; it was never
  in a candidate list. Needs a one-row sync on Dobby.

### `reeval_candidates_glm47flash_main_20260910` — GLM main (closed 09-11)
- 37 candidates (32 `stale_report_different_patch`, 5
  `evaluation_error_recorded_as_false`), same two mechanisms as Devstral.
  Re-graded 09-11 → 22 True / 14 False / 1 unverified
  (`sympy-19637 truncation r3`).

### `reeval_candidates_qwen35b_ablation155_20260924` — Qwen ABL-25 ablation (closed 09-24)
- The 60-row check of the main track repeated on
  `ICLR_experiments/swebench/ablation/qwen35b/`: 155 records with a saved
  patch, `resolved=False` and no report (`d03__b20k__*`, `d05__b10k__*`,
  `d05__b20k__*`, `d07__b20k__*`, `di__b10k__*`, `di__b20k__*`; dated
  04-20..08-28). Re-graded 09-24, all 155 stay False; applied anyway so every
  row now carries a `reevaluation` provenance block.

### Still open (kept under `issue/`)
- `resume_audit_20260908/` — audit of the 645 runs completed after the
  09-07 Qwen resume. Done since: the 8 sklearn-14710 evaluation timeouts
  were covered by the 09-11 Qwen pass; the 1500 s agent-timeout question
  led to the FC∞ limit-failure reruns of 09-13/14. **Open**: 219/220
  saved structured summaries carry the model's `</think>` preamble
  (`structured_summarize` forwards `response.content` unvalidated, and TRC's
  `content.startswith` summary guard therefore misses them); 33 runs show
  the agent re-summarizing after a summary. No code change yet in
  `src/agentctx/compression/primitives.py`.
- `qwen_fc_15min_1hour_20260910/` — why 98/165 FC∞ runs on the 55
  "15 min – 1 hour" tasks failed (45 agent timeouts, 26 wrong fixes, 10 step
  limits, 4 non-diff submissions, 13 evaluation problems, 2 provenance
  mismatches). Done since: 13 of the 15 flagged runs were in the 09-11/09-23
  candidate lists (12 now True, `sympy-13798 r2` False). **Open**: the 2
  provenance mismatches (`django-11734 r2`, `sympy-12419 r1`: index row from
  the 03-30 timed-out run, `trajectory.json` from an 04-16 rerun that
  submitted an unevaluated patch) were never reconciled.

## 2026-09-08 → 2026-09-26 — Backfilled entries (SWE-Bench on Dobby, Terminal-Bench cells from Albus)

All times are CDT. "HEAD at launch" is reconstructed from the local git
reflog; where a launcher change was still uncommitted at launch, the commit
that later recorded it is given as the code reference. Launch commands are
taken from `~/.bash_history` and the launcher log banners; `SLACK_WEBHOOK_URL`
and `DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"` were exported
in the shell before every launch below and are omitted.

### 2026-09-08 — Qwen main-section-only resume (summary-bug rerun, P100 @15K + ∞)
- Launched 16:41:25 (stopped: webhook not configured), relaunched **16:48:02**
  (launcher PID 3862052); `=== sections run: main (ablation skipped) ===` at
  **2026-09-09 14:53:13**.
- HEAD at launch: `bbe9e5df949080d424df9aca94d4004557d81672`. The `SECTIONS`
  override in `scripts/run_agent_models_expansion.sh` was uncommitted at launch
  and recorded in `4cbf6edec45ed32aae6d9cb22186aec7390f0daf` (2026-09-13).
- Preceded by the second summary-bug archive
  (`archives/swebench_summary_bug_remaining_20260908_162042_CDT`, commits
  `25b7ca7`/`16dacec`); 917 missing keys were expected across the 15K su-partial,
  su-full, ss, ss-partial, trc-su, trc-ss, otrc-su-partial, otrc-ss-partial cells.
- Command:
  ```bash
  nohup env MAX_WORKERS=16 RUN_EVAL=1 SECTIONS=main PYTHON="$PWD/venv/bin/python3" \
    QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 \
    bash scripts/run_agent_models_expansion_notified.sh qwen \
    >> logs/followup_agent_models_qwen_launcher.log 2>&1 < /dev/null &
  echo $! > logs/followup_agent_models_qwen_launcher.pid
  ```
- Output: `ICLR_experiments/swebench/main/qwen35b/{d05__b15k__*,di__b15k__*,di__binf__*}`;
  log `logs/followup_agent_models_qwen_launcher.log`. Audit of the resumed runs:
  `ICLR_experiments/issue/resume_audit_20260908/report.md`.

### 2026-09-09 — Devstral main rerun of the archived summary-bug runs (P100 @21K)
- Launched **15:33:07**, `sections run: main (ablation skipped)` at
  **2026-09-10 06:14:27**. HEAD `bbe9e5df949080d424df9aca94d4004557d81672`
  (uncommitted `SECTIONS` override, see above). vLLM: `bash scripts/serving/start_vllm_devstral.sh`
  (:8002, TP=4, `--max-model-len 65536`). The Qwen vLLM (PID 2552238) was stopped first.
- Command:
  ```bash
  nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 \
    bash scripts/run_agent_models_expansion_notified.sh devstral \
    >> logs/followup_agent_models_devstral_launcher.log 2>&1 < /dev/null &
  echo $! > logs/followup_agent_models_devstral_launcher.pid
  ```
- Re-executed keys (per the 2026-09-10 audits): SU-full 241, SU-partial 238,
  SS 221, SS-partial 218, TRC+SU 50, TRC+SS 45, OTRC+SU-partial 47,
  OTRC+SS-partial 36 (1,096 runs). Audits:
  `ICLR_experiments/issue/devstral_summary_20260910/`, `ICLR_experiments/issue/devstral_rule_otrc_20260910/`.

### 2026-09-10 — GLM main resume attempt (stopped the same day)
- Launched **12:58:46** (`SECTIONS=main`, HEAD `bbe9e5d`), reached
  `d05__bP__su-full`, then the launcher, runner, agents and the GLM vLLM were
  stopped with `pkill -TERM` to free the GPUs for the Devstral FC regeneration
  below. The earlier 2026-09-06 17:51 GLM main launch is in
  `EXPERIMENT_TIMELINE_DETAIL_SWE.md`. Both attempts share
  `logs/followup_agent_models_glm.log`; the launcher log was truncated on 09-14.
  ```bash
  nohup env PYTHON="$PWD/venv/bin/python3" MAX_WORKERS=16 RUN_EVAL=1 SECTIONS=main \
    bash scripts/run_agent_models_expansion_notified.sh glm \
    >> logs/followup_agent_models_glm_launcher.log 2>&1 < /dev/null &
  ```

### 2026-09-10 — Devstral FC∞ run_2/run_3 archived and regenerated
- The FC run_2/run_3 records were archived (run_1 = calibration kept) with
  `scripts/archive_devstral_fc_r23.py` (committed as
  `d4332a5f653018430efce0312274c3d10eee8a97` on 09-13):
  ```bash
  python3 scripts/archive_devstral_fc_r23.py \
    --archive-name devstral_fc_r23_before_rerun_20260910 --execute
  ```
  Archive: `archives/devstral_fc_r23_before_rerun_20260910/` (removed 200,
  remaining 100, 677 paths moved).
- Regeneration launched **16:47:30** (main only; every cell except FC had 0
  missing keys), complete **19:55:55**. HEAD `bbe9e5d`.
  ```bash
  nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 PYTHONUNBUFFERED=1 \
    PYTHON="$PWD/venv/bin/python3" \
    bash scripts/run_agent_models_expansion_notified.sh devstral \
    >> logs/followup_agent_models_devstral_launcher.log 2>&1 < /dev/null &
  ```
- 2026-09-11 (~11:05–11:12): evaluation-only pass over the FC cell after the
  re-evaluation below:
  ```bash
  venv/bin/python3 scripts/run_experiment_iclr.py --iclr-section main --iclr-model devstral24b \
    --iclr-cell di__binf__fc --ablation iclr-devstral24b-main-di__binf__fc --model-tag devstral-2 \
    --agent-config "$PWD/configs/config-devstral-vllm.yaml" --otrc-config "$PWD/configs/config-online-trc.yaml" \
    --budget 999999999 --depth 0.5 --tasks-file "$PWD/task_lists/p100_all_100_tasks.json" \
    --conditions full-context --runs-per-task 3 --max-workers 16 --eval-only
  ```

### 2026-09-10/11 — Verdict re-evaluations applied to the canonical indexes
Evaluation only (no agent runs). Tooling: `34ac3cb051cc57ad9289771aca0ce6ec8d4bbfc0`
(trustworthy verdicts, container thread cap), `b24423785a6007b4f682fb6b8cf5dbf1d6c3139a`
(`scripts/maintenance/reevaluate_swebench_candidates.py`, `scripts/build_reevaluation_candidates.py`),
`90a4899e3a91ae4f2a0431462a888d5f3d8141a2` (600 s harness timeout, 19:11).
Candidates come from the 2026-09-10 audits under `ICLR_experiments/issue/`
(committed `4baa6fb31d88e7acca2fd78fe6f6c2c49feb7693`). Evidence dirs under
`archives/reeval_*` (gitignored). After each `apply --write`:
`venv/bin/python3 analysis/aggregate_benchmark_results.py && venv/bin/python3 dashboard/build_coverage.py`.

| Model | Candidates | Run (start → end) | Result | Apply |
|---|---:|---|---|---|
| Devstral main | 269 (`devstral_rule_otrc_20260910/reevaluation_candidates_combined.csv`: 241 summary-family + 28 TR/TRC/OTRC) | 09-10 22:13 failed (python path), 22:26 started, killed; resumed 09-11 10:12 → 11:05 | 174 True / 94 False / 1 unverified (`sympy__sympy-18189__online-trc__r3`) | `apply --allow-partial --write` |
| Qwen main | 150 (`reeval_candidates_qwen35b_main_20260910/candidates.csv`) | 09-11 11:14 → 12:24 | 84 True / 66 False | `apply --write` |
| GLM main | 37 (`reeval_candidates_glm47flash_main_20260910/candidates.csv`) | 09-11 15:05 → 15:36 | 22 True / 14 False / 1 unverified (`sympy__sympy-19637__truncation__r3`) | `apply --allow-partial --write` |

```bash
# Devstral (default candidates file; resume form shown)
nohup venv/bin/python3 scripts/maintenance/reevaluate_swebench_candidates.py run \
  --output-dir archives/reeval_devstral_main_20260910 --resume --continue-on-error --eval-threads 8 \
  >> logs/reeval_devstral_main_20260910.log 2>&1 < /dev/null &
# Qwen / GLM
nohup venv/bin/python3 scripts/maintenance/reevaluate_swebench_candidates.py run --candidates "$CAND" \
  --output-dir "$OUT" --model-tag qwen35-a3b --continue-on-error --eval-threads 8 >> "$LOG" 2>&1 < /dev/null &
# (GLM: --model-tag glm47-flash)
venv/bin/python3 scripts/maintenance/reevaluate_swebench_candidates.py apply --output-dir "$OUT" [--allow-partial] --write
```

### 2026-09-11 — Qwen ABL-25 ablation rerun (all 52 ablation cells)
- Pre-step: the 476 ablation copies seeded from archived main runs were
  archived with `bash scripts/archive_qwen_ablation_seeded.sh --execute`
  (dry run first) → `archives/swebench_summary_bug_ablation_seeded_20260911_171617_374762025/`
  (476 runs, 476 index rows). Script committed in `d4332a5`.
- Launched **17:17:08**, `complete: sections=ablation` at **2026-09-12 23:03:25**
  (log `logs/followup_agent_models_qwen_launcher.log`). HEAD
  `d19852a899d4c418eb1b1cd657517dd17431d76d`; the ABL-30 → ABL-25 launcher switch
  was uncommitted at launch and recorded in `4cbf6ed` (banner already reads
  `section 2 ablation (ABL-25)`, `tasks=ablation_25tasks.json`).
- Qwen vLLM restarted by hand (TP=4, `--max-model-len 102400 --max-num-seqs 64`,
  no prefix caching), rootless Podman socket.
  ```bash
  nohup env SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 \
    QWEN_A_BUDGET=10000 QWEN_P_BUDGET=15000 QWEN_B_BUDGET=20000 \
    bash scripts/run_agent_models_expansion_notified.sh qwen \
    >> logs/followup_agent_models_qwen_launcher.log 2>&1 &
  echo $! > logs/followup_agent_models_qwen_launcher.pid
  ```
- Output: `ICLR_experiments/swebench/ablation/qwen35b/` (52 cells; ABL-30-era rows
  remain in the indexes, so several cells hold more than 75 records).

### 2026-09-13/14 — Devstral ABL-25 ablation (all 52 ablation cells)
- First launch **2026-09-13 00:59:32** (HEAD `90a4899e3a91ae4f2a0431462a888d5f3d8141a2`),
  ran through `d07__b24k__su-partial` (17:15) and was stopped together with the
  Devstral vLLM in the evening so the Qwen FC limit-failure reruns below could
  use the GPUs. Relaunched **2026-09-14 09:51:20** (HEAD
  `e2dbe9bca9993c4e3253784e27fddb0108e667ee`), `complete: sections=ablation` at
  **19:00:57**. vLLM: `bash scripts/serving/start_vllm_devstral.sh`.
  ```bash
  nohup env AGENTCTX_WS="$PWD" PYTHON="$PWD/venv/bin/python3" SECTIONS=ablation \
    MAX_WORKERS=16 RUN_EVAL=1 \
    DEVSTRAL_A_BUDGET=17000 DEVSTRAL_P_BUDGET=21000 DEVSTRAL_B_BUDGET=24000 \
    bash scripts/run_agent_models_expansion_notified.sh devstral \
    >> logs/followup_agent_models_devstral_launcher.log 2>&1 < /dev/null &
  echo $! > logs/followup_agent_models_devstral_launcher.pid
  ```
- Output: `ICLR_experiments/swebench/ablation/devstral24b/` (52 cells).

### 2026-09-13/14 — Qwen FC∞ limit-failure reruns (outside `ICLR_experiments/`)
Diagnostic reruns of the 82 Qwen FC runs that failed only on the 1500 s /
125-step limits; results live in
`adaptive_context_management_analysis/results/.../reruns/` and overlay CSV
`swebench_outcomes_rerun.csv`. Full outcomes are in `Active_runs.md`. Code:
`e2dbe9bca9993c4e3253784e27fddb0108e667ee` (`rerun_limit_failures.py`,
`run_rerun_limits_notified.sh`), overnight chain and outcome builder
`aaf4909d6e04931c6027d0bf767610044b85d05e` / `d04a786bc4735c27cef82416977362731993acf5`
(committed 09-17, uncommitted at run time), outcomes doc `7280cff`.

| Phase | Start → end | Limits | Runs |
|---|---|---|---:|
| 1 (15 min–1 h) | 09-13 17:58:59 → 22:36 | 200 steps / 3600 s | 55 |
| 3 (<15 min) | 09-13 22:56:55 → 09-14 00:01 | 200 steps / 3600 s | 10 |
| 2 (1–4 h, >4 h) + phase-1 again-19 | 09-14 00:17:43 → 02:14 → 04:44:10 | 300 steps / 5400 s | 17 + 19 |

```bash
nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh > logs/rerun_qwen35b_fc_limits_phase1_launcher.log 2>&1 &
PHASE=3 nohup bash adaptive_context_management_analysis/run_rerun_limits_notified.sh > logs/rerun_qwen35b_fc_limits_phase3_launcher.log 2>&1 &
P2_STEP_LIMIT=300 P2_TIMEOUT=5400 AGAIN_STEP_LIMIT=300 AGAIN_TIMEOUT=5400 \
  nohup bash adaptive_context_management_analysis/run_rerun_limits_overnight.sh > logs/rerun_qwen35b_fc_limits_overnight.log 2>&1 &
python3 adaptive_context_management_analysis/build_rerun_outcomes.py
```
(8 workers, hardest-first, SWE-bench eval per stage; Qwen vLLM restarted by hand on :8000.)

### 2026-09-14 → 09-17 — GLM main P100 @13K completed
- 20:52:45 an `SECTIONS=ablation` launch was started by mistake (it truncated
  `logs/followup_agent_models_glm_launcher.log` with `>`), terminated within a
  minute; **20:53:53** `SECTIONS=main` launched; `sections run: main (ablation
  skipped)` at **2026-09-17 13:50:28**. HEAD `e2dbe9bca9993c4e3253784e27fddb0108e667ee`.
  vLLM: `bash scripts/serving/start_vllm_glm47flash.sh` (:8003, TP=4, 65536,
  `venv-glm-cu129-clean`).
  ```bash
  nohup env SECTIONS=main MAX_WORKERS=16 RUN_EVAL=1 \
    bash scripts/run_agent_models_expansion_notified.sh glm \
    >> logs/followup_agent_models_glm_launcher.log 2>&1 < /dev/null &
  echo $! > logs/followup_agent_models_glm_launcher.pid
  ```
- Output: `ICLR_experiments/swebench/main/glm47flash/` — 13 cells × 300 = 3,900 runs.

### 2026-09-17/18 — Summarizer ablation, SWE-Bench (FOLLOWUP §4.a / §4.c)
- Agent Qwen3.5-35B-A3B via `bash scripts/serving/start_vllm_qwen35_prefix_cache_ablation.sh` (:8000,
  `--gpu-memory-utilization 0.70`); summarizer via
  `bash scripts/serving/start_vllm_summarizer.sh {qwen35-9b|gemma4-12b}` (:8001, 0.15,
  32k window; Gemma from `venv-glm-cu129-clean`, vLLM 0.28). Cells
  `d05__b15k__su-full` and `di__b15k__trc-su`, ABL-25 × 3 runs, 16 workers, eval on.
  Workflow commits `725a42c8ca08693f4fc174252db46029097d278c`,
  `83327620b05446d3281bc9d890f481201d2d1d7d`, `45983aa96cfd4b50dec6249fcf73ea82db9ecfd2`
  (all 2026-09-17 14:15–14:16); Gemma config + notified wrapper recorded in
  `3c44002d1c9bbb9db2fc7cd5e6bd747e0451079d` (2026-09-18 14:40, after the Gemma launch).
- **Qwen3.5-9B summarizer** — smoke 14:38:11 (1 task, `ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke`,
  `RUN_EVAL=0`); full run **15:37:24 → 19:15:50**. HEAD `45983aa`.
  ```bash
  N_TASKS=1 RUNS_PER_TASK=1 MAX_WORKERS=1 RUN_EVAL=0 CELLS=d05__b15k__su-full:summarization:0.5 \
    ICLR_MODEL=qwen35b-sum-qwen35-9b-smoke bash scripts/run_qwen_swe_summarizer_ablation.sh
  nohup bash scripts/run_qwen_swe_summarizer_ablation_notified.sh \
    > logs/followup_sb_qwen_sumabl_qwen9b.nohup.log 2>&1 &
  ```
- **Gemma-4-12B summarizer** — `bash scripts/serving/stop_vllm.sh logs/vllm_summarizer_qwen35-9b.pid`,
  `bash scripts/serving/start_vllm_summarizer.sh gemma4-12b`; run **2026-09-18 10:31:14 → 13:55:49**.
  HEAD `45983aa` (Gemma config uncommitted → `3c44002`).
  ```bash
  nohup env SUMMARY_CONFIG=configs/config-summary-gemma4-12b.yaml ICLR_MODEL=qwen35b-sum-gemma4-12b \
    bash scripts/run_qwen_swe_summarizer_ablation_notified.sh \
    > logs/followup_sb_qwen_sumabl_gemma12b.nohup.log 2>&1 &
  ```
- Output: `ICLR_experiments/swebench/model_ablation/qwen35b-sum-qwen35-9b/`
  (su-full 28/75, trc-su 47/75) and `qwen35b-sum-gemma4-12b/` (su-full 21/75,
  trc-su 50/75). The `*-smoke` dir (1 run) is ignored by coverage/aggregation.

### 2026-09-18/19 — Prefix-cache ablation, SWE-Bench (dashboard 5.a)
- Server: `bash scripts/serving/start_vllm_qwen35_prefix_cache.sh` (production command +
  `--enable-prefix-caching`; PID 1217568, started 14:28). Smoke 14:35:36
  (`ICLR_MODEL=qwen35b-prefixcache-smoke`).
- 15K grid (11 cells, ABL-25 × 3, 16 workers, eval on) **14:37:23 → 2026-09-19 02:23:07**
  (launcher PID 1243729). HEAD `45983aa`; the workflow was committed 3 minutes
  after launch as `e5d25caaba725c364b43a75dda17d24cc9c605c5` (14:40) with the
  launched script content.
  ```bash
  nohup bash scripts/run_qwen_swe_prefix_cache_ablation_notified.sh \
    > logs/followup_sb_qwen_prefixcache.nohup.log 2>&1 &
  ```
- Baselines FC∞ / OTRC∞ (150 runs) **2026-09-19 19:36:08 → 21:53:16**, HEAD
  `3b1fd9182d0fc0479179eb2aaecb258be2204ba4`; the `CELLS` defaults were extended
  afterwards in `d4709034de16d73902f69343e81cbae0e762b08a` (09-21).
  ```bash
  nohup env CELLS="di__binf__fc:full-context:0.5 di__binf__otrc:online-trc:0.5" \
    bash scripts/run_qwen_swe_prefix_cache_ablation_notified.sh \
    > logs/followup_sb_qwen_prefixcache_baselines.nohup.log 2>&1 &
  ```
- Output: `ICLR_experiments/swebench/prefix_cache_ablation/qwen35b-prefixcache/`
  (13 cells × 75 = 975 runs). Server hit rate: 82.6% over the 15K grid
  (TR/TRC family 85–91%, OTRC family 63–67%), FC 96.3%, OTRC∞ 69.8%.

### 2026-09-20 → 09-23 — GLM ABL-25 ablation (all 52 ablation cells)
- vLLM `bash scripts/serving/start_vllm_glm47flash.sh` (PID file 09-19 23:53). Launched
  **2026-09-20 00:00:06**, `complete: sections=ablation (full grid: 3,900 main +
  3,900 ablation runs)` at **2026-09-23 10:31:24**. HEAD `3b1fd9182d0fc0479179eb2aaecb258be2204ba4`.
  The `MSWEA_SUMMARY_*` variables were unset explicitly so the summarizer-ablation
  environment could not leak into the self-summarizing GLM runs.
  ```bash
  nohup env -u MSWEA_SUMMARY_MODEL_CONFIG -u MSWEA_SUMMARY_MODEL_NAME -u MSWEA_SUMMARY_API_BASE \
    SECTIONS=ablation MAX_WORKERS=16 RUN_EVAL=1 \
    bash scripts/run_agent_models_expansion_notified.sh glm \
    >> logs/followup_agent_models_glm_launcher.log 2>&1 < /dev/null &
  echo $! > logs/followup_agent_models_glm_launcher.pid
  ```
- Output: `ICLR_experiments/swebench/ablation/glm47flash/` — 52 cells × 75 = 3,900 runs.

### 2026-09-23/24 — Qwen main review-253 re-evaluation, applied 09-24
- Run **2026-09-23 11:32 → 13:42** (253/253 verified; 165 True / 88 False;
  134 False→True vs the 09-10 audit, 0 True→False). HEAD
  `df273ed8d6c9c8aabd9094b71173e3dd9d8d544a`; the harness guard relaxation was
  uncommitted and recorded in `88fcc61420eb7fda79f358a72dad06bd0433739f`.
  Candidates/comparison committed in `b6b9f758a4d34e108850eedf465799c9ddd9d41c`.
  Details in `Active_runs.md`.
  ```bash
  nohup venv/bin/python scripts/maintenance/reevaluate_swebench_candidates.py run \
    --candidates ICLR_experiments/issue/reeval_candidates_qwen35b_review253_20260923/candidates.csv \
    --output-dir ICLR_experiments/reeval_evidence/qwen35b_main_review253_20260923 \
    --model-tag qwen35-a3b --continue-on-error > logs/reeval_qwen35b_review253_20260923.log 2>&1 &
  ```
- **Applied 2026-09-24** (between the 11:44 pull to `1e0b47f` and the 16:01
  commit `397c232f6510e0d9b1398578806f1d2e74182a90`, which carries the updated
  outcomes table and `REEVAL_NOTES`):
  ```bash
  venv/bin/python scripts/maintenance/reevaluate_swebench_candidates.py apply \
    --output-dir ICLR_experiments/reeval_evidence/qwen35b_main_review253_20260923 --write
  mkdir -p archive/swebench_main_qwen35b_pre_reeval_20260924
  cp -r ICLR_experiments/reeval_evidence/qwen35b_main_review253_20260923/backups/*/ archive/swebench_main_qwen35b_pre_reeval_20260924/
  venv/bin/python analysis/aggregate_benchmark_results.py --benchmark swebench
  venv/bin/python scripts/build_coverage.py
  ```
  All 35 `main/qwen35b` indexes were rewritten (mtime 2026-09-24 15:57).

### 2026-09-24 — Qwen ABL-25 ablation 155-run re-evaluation, applied
- 155 ablation records whose evaluation reports were missing
  (`ICLR_experiments/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv`,
  reason `ablation_evaluation_reports_missing`, cells `d03__b20k__*`, `d05__b10k__*`,
  `d05__b20k__*`, `d07__b20k__*`, `di__b10k__*`, `di__b20k__*`). Run
  **15:14:50 → 16:27** (PID file `logs/reeval_qwen35b_ablation155_20260924.pid`);
  155/155 verified, **all `resolved=False`** (no verdict flips). HEAD `397c232`.
  Evidence `ICLR_experiments/reeval_evidence/qwen35b_ablation_abl25_155_20260924/`
  (committed `8caf652a1c102835bbf209c99cd8f96f6a31adfc` / `fdd4277ab5eba1334320afbe96d01ab3bf33115a`, 09-26).
  ```bash
  nohup venv/bin/python scripts/maintenance/reevaluate_swebench_candidates.py run \
    --candidates ICLR_experiments/issue/reeval_candidates_qwen35b_ablation155_20260924/candidates.csv \
    --output-dir ICLR_experiments/reeval_evidence/qwen35b_ablation_abl25_155_20260924 \
    --model-tag qwen35-a3b --continue-on-error > logs/reeval_qwen35b_ablation155_20260924.log 2>&1 &
  echo $! > logs/reeval_qwen35b_ablation155_20260924.pid
  venv/bin/python scripts/maintenance/reevaluate_swebench_candidates.py apply \
    --output-dir ICLR_experiments/reeval_evidence/qwen35b_ablation_abl25_155_20260924 --write
  mkdir -p archive/swebench_ablation_qwen35b_pre_reeval_20260924
  cp -r ICLR_experiments/reeval_evidence/qwen35b_ablation_abl25_155_20260924/backups/*/ archive/swebench_ablation_qwen35b_pre_reeval_20260924/
  venv/bin/python analysis/aggregate_benchmark_results.py --benchmark swebench
  venv/bin/python scripts/build_coverage.py
  ```
  The affected `ablation/qwen35b` indexes carry mtime 2026-09-24 16:31.

### Terminal-Bench cells collected on Albus (2026-09-12 → 09-24), synced by rsync
These were run on **Albus**; the launch commands, HEADs and launcher logs
(`logs/followup_tb_*`) live there and are not recoverable from this machine.
`ICLR_experiments/EXPERIMENT_LOG_TB.md` on branch
`akiho-expansion-terminalbench-0829` (tip `b45f8dc`, 2026-09-24) ends at the
2026-09-07 summary-bug rerun, so the cells below are logged nowhere else yet.
[TODO on Albus] add their launch commands, HEADs and logs to `EXPERIMENT_LOG_TB.md`.
Dates are `experiment_results.json` mtimes (CDT) after rsync.

| Section (`ICLR_experiments/terminalbench/...`) | Cells | Runs | Index mtimes |
|---|---:|---:|---|
| `main/{qwen35b,devstral24b,glm47flash}` — P-40 Main complete (13 cells × 120; qwen35b also keeps `d05__b27k__tr` 320 and a 400-row `d05__b3k__tr` from the P-80 phase) | 13/13/13 | 1,560 each | last updates 09-11 20:36 (qwen, devstral), 09-12 12:34 (glm) |
| `ablation/qwen35b` — P-15 ablation, 2K/3K/4K × depth grid + depth-invariant | 52 | 2,340 (45/cell) | 09-03 15:23 (`d05__b2k__tr`) → 09-15 00:59 |
| `ablation/devstral24b` — P-15 ablation, 3K/4K/7K | 52 | 2,340 | 09-12 01:46 → 09-14 07:05 |
| `ablation/glm47flash` | — | — | **not present** (GLM TB ablation not run / not synced) |
| `model_ablation/qwen35b-sum-qwen35-9b` (`d05__b3k__su-full`, `di__b3k__trc-su`; 4.b) | 2 | 90 | smoke 09-16 21:00; 09-23 14:30, 15:55 |
| `model_ablation/qwen35b-sum-gemma4-12b` (4.d) | 2 | 90 | smoke 09-23 16:32; 09-23 17:42, 18:53 |
| `prefix_cache_ablation/qwen35b-noprefixcache` — 3K grid + FC∞/OTRC∞, caching OFF (dashboard 5.b) | 13 | 585 | 09-23 21:25 → 09-24 05:12 |

Sync commands run on Dobby (first one between the 09-14 GLM launch and the
09-17 summarizer commits; second on 09-24/25):
```bash
rsync -avh --partial --progress ak58925@albus.ece.utexas.edu:/home/ak58925/agentCtx/ICLR_experiments/terminalbench \
  /home/ak58925/agentCtx/ICLR_experiments/
rsync -avh --partial --progress \
  ak58925@albus.ece.utexas.edu:/home/ak58925/agentCtx/ICLR_experiments/terminalbench/{model_ablation,prefix_cache_ablation} \
  /home/ak58925/agentCtx/ICLR_experiments/terminalbench/
```
