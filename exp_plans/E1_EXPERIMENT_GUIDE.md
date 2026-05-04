# E1 Experiment: Silent Waste Analysis
## Execution Guide

This guide walks you through running the E1 experiment to measure Write-Amplification Factor (WAF) across compression primitives.

---

## Overview

**Goal**: Demonstrate that different compression strategies (truncation, summarization, retrieval) waste different amounts of work (extra LLM calls) on SWE-bench tasks.

**Experiment Design**:
- **9 tasks**: 3 random per repo (Flask, Django, SymPy)
- **4 primitives**: truncation, summarization, retrieval, full-context
- **3 runs each**: Per task-primitive combination = 108 total runs
- **Budget**: 8,000 tokens (anchor point where summarization succeeds best)
- **Step limit**: 100 LLM calls per run (increased from default 30)
- **Execution**: Sequential (no parallelism) to ensure clean isolation

**Timeline**:
- Setup: ~5 min
- Dry run (12 runs): ~3 min
- Validation: ~1 min
- Full run (108 runs): ~2.5 hours
- **Total**: ~3 hours wall-clock time

---

## Prerequisites

```bash
# Install dependencies if needed
pip install datasets matplotlib scipy

# Ensure vLLM server is running on localhost:8000
# If not, start it: vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --tensor-parallel-size 1
```

---

## Step 1: Download SWE-Bench Tasks

This downloads 3 random tasks from each repo (Flask, Django, SymPy).

```bash
python scripts/download_swe_bench_tasks.py
```

**Output**: `tasks_e1_random_9.json` with 9 task definitions

**Expected output**:
```
Found 48 total flask tasks
  [1] pallets__flask-XXXX: 230 chars
  ...
✓ Saved 9 tasks to tasks_e1_random_9.json
```

---

## Step 2: Run Dry Run (12 tasks)

This runs 1 task per repo × 4 primitives × 1 run = 12 runs.
Expected duration: **~3 minutes**

```bash
bash scripts/run_e1_dryrun.sh
```

**Output**: 12 log directories under `logs/e1_dryrun/`

Expected structure:
```
logs/e1_dryrun/
  pallets__flask-XXXX/{truncation,summarization,retrieval,full-context}/run_1/
    run_1.traj.json           # Trajectory (messages, exit status)
    run_1.token_log.json      # Token metrics (tokens, latency, compression)
    run_1.agent.log           # Agent stderr/stdout
  ... (3 more task dirs)
```

---

## Step 3: Validate Dry Run

```bash
python scripts/validate_e1_dryrun.py
```

**What it checks**:
- All 12 task-primitive combinations completed
- Required files present (traj.json, token_log.json)
- Data format correct

**Expected output**:
```
Results by primitive:
  truncation:
    ✓ flask: traj=true token=true
    ✓ djang: traj=true token=true
    ✓ sympy: traj=true token=true
    Summary: 3/3 succeeded
  ...

✓ Dry run validation PASSED

Ready for full run. Next steps:
  1. rm -rf logs/e1_dryrun/
  2. bash scripts/run_e1_full.sh
```

**If FAILED**, check logs for errors:
```bash
tail logs/e1_dryrun/*/*/run_1/run_1.agent.log
```

---

## Step 4: Clean Dry Run Logs

Once validated, remove dry run logs to save space:

```bash
rm -rf logs/e1_dryrun/
```

---

## Step 5: Run Full Experiment (108 runs)

**Duration**: ~2.5 hours (sequential, no parallelism)

```bash
bash scripts/run_e1_full.sh
```

**Real-time progress**:

During the run, you can check progress in another terminal:

```bash
# Check every 30 seconds
watch -n 30 'bash scripts/check_e1_progress.sh'

# Or manually:
bash scripts/check_e1_progress.sh
```

**Progress log**: `logs/e1_full_progress.log` (updated every run)

**Expected output during run**:
```
[1/108] (0%) Flask + truncation (run 1)...
[2/108] (1%) Flask + truncation (run 2)...
...
[108/108] (100%) SymPy + full-context (run 3)...
✓ Full run completed in 150 min
```

---

## Step 6: Extract Metrics

After full run completes:

```bash
python scripts/extract_e1_metrics.py
```

**Output**: `e1_metrics_raw.json` with all 108 run metrics
- num_model_calls (ToolCalls)
- patch_generated (success indicator)
- total_tokens
- latency_seconds
- compression_events

---

## Step 7: Calculate WAF

```bash
python scripts/calculate_e1_waf.py
```

**Output**: `e1_waf_results.json`

**Key metrics**:
- `waf_per_primitive`: Aggregate WAF (work amplification) per primitive
- `success_rates`: % of runs that generated a patch per primitive
- `reference_per_task`: Which primitive was most efficient (min ToolCalls) per task

**Interpretation**:
- WAF = 1.0 = Reference (most efficient)
- WAF = 2.0 = Uses 2x the calls as reference
- Lower WAF = More efficient (less wasted calls)

**Example output**:
```
truncation:
  WAF: 1.85 ± 0.42 (range: 1.2-2.4)
  Success rate: 33.3%
  
summarization:
  WAF: 1.0 ± 0.0 (range: 1.0-1.0)
  Success rate: 72.2%
  
retrieval:
  WAF: 2.1 ± 0.53 (range: 1.5-3.2)
  Success rate: 45.0%
  
full-context:
  WAF: 1.3 ± 0.35 (range: 1.0-1.8)
  Success rate: 55.5%
```

**Story**: Summarization is reference (WAF=1.0) and succeeds most (72%), showing it's both efficient and effective. Truncation fails more (33%) despite appearing cheap.

---

## Step 8: Generate Visualizations

```bash
python scripts/generate_e1_graphs.py
```

**Output**: Graphs saved to `graphs/e1/`

**Individual graphs** (4 graphs):
- `e1_success_rate_by_primitive.png` — Success % per primitive
- `e1_tokens_by_primitive.png` — Mean tokens consumed
- `e1_latency_by_primitive.png` — Mean E2E latency
- `e1_waf_by_primitive.png` — WAF (Work Amplification Factor)

**Story graph** (1 combined visualization):
- `e1_combined_story.png` — 2-panel figure:
  - Left: Success rate + WAF overlay (showing tradeoff)
  - Right: Token efficiency vs success scatter (showing silent waste)

---

## Step 9: Review Results

```bash
# View all graphs
ls -la graphs/e1/

# View metrics JSON (optional)
cat e1_waf_results.json | less
```

---

## Troubleshooting

### vLLM server not responding

```bash
# Check if server is running
curl http://localhost:8000/v1/models

# If not, start it:
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
  --tensor-parallel-size 1 \
  --max-model-len 16384 \
  --port 8000
```

### Dry run failed on specific primitive

```bash
# Check that primitive's log
cat logs/e1_dryrun/{task}/{primitive}/run_1/run_1.agent.log

# Common issues:
# - vLLM server offline: Check server logs
# - Task not found: Verify tasks_e1_random_9.json exists
# - Environment error: Check Docker is running (if using DockerEnvironment)
```

### Full run stuck/slow

```bash
# Check progress manually
find logs/e1_full -name "*.traj.json" | wc -l  # Shows completed runs (should increment)

# View last activity
tail -20 logs/e1_full_progress.log

# To gracefully pause/resume:
# - Stop the run (Ctrl+C)
# - Check which runs completed: ls logs/e1_full/*/*/*/
# - Resuming will skip completed runs
```

---

## File Summary

| File | Purpose |
|------|---------|
| `tasks_e1_random_9.json` | 9 random SWE-bench tasks (3 per repo) |
| `e1_metrics_raw.json` | All 108 run metrics (num_calls, tokens, latency, etc.) |
| `e1_waf_results.json` | Aggregated WAF, success rates, per-task analysis |
| `graphs/e1/` | 5 visualization PNG files |
| `logs/e1_full/` | Raw experiment logs (108 dirs × 3 files each) |

---

## Next Steps (Analysis)

Once graphs are generated:
1. **Review the 2-panel combined story graph** — This tells the narrative
2. **Compare WAF across primitives** — Which wastes the most work?
3. **Correlate WAF with success rate** — Is the extra work justified?
4. **Propose improvements** — What would reduce WAF while maintaining success?

---

## Quick Reference: Commands in Order

```bash
# 1. Download (5 min)
python scripts/download_swe_bench_tasks.py

# 2. Dry run (3 min)
bash scripts/run_e1_dryrun.sh

# 3. Validate dry run
python scripts/validate_e1_dryrun.py

# 4. Clean (if OK)
rm -rf logs/e1_dryrun/

# 5. Full run (150 min)
bash scripts/run_e1_full.sh
# Monitor in another terminal: watch -n 30 'bash scripts/check_e1_progress.sh'

# 6. Extract metrics (1 min)
python scripts/extract_e1_metrics.py

# 7. Calculate WAF (1 min)
python scripts/calculate_e1_waf.py

# 8. Generate graphs (1 min)
python scripts/generate_e1_graphs.py

# 9. Review results
ls graphs/e1/
```

---

## Contact

Questions? Check:
- Agent logs: `logs/e1_full/{task}/{primitive}/run_{1,2,3}/run_N.agent.log`
- Metrics: `e1_metrics_raw.json`
- Progress: `logs/e1_full_progress.log`
