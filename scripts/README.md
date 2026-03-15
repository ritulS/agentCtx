# Experiment Scripts

This directory contains scripts to run the context compression primitives experiment.

## Scripts

### 1. `select_tasks.py`
Selects 9 tasks (3 per repo: Flask, Django, SymPy) based on problem complexity.
- Uses problem description word count as a proxy for complexity
- Selects low, medium, and high complexity tasks from each repo
- Outputs: `selected_tasks.json`

**Usage:**
```bash
python select_tasks.py
```

### 2. `run_experiment.py`
Runs the main experiment:
- 9 tasks × 3 primitives (truncation, summarization, retrieval) × 3 runs each = 81 total runs
- Logs: e2e latency, token usage, success rate, patch generation
- Outputs: `results/experiment_results_<timestamp>.json`

**Usage:**
```bash
python run_experiment.py
```

**Note:** This can take several hours to complete. Requires vLLM server to be running.

### 3. `analyze_results.py`
Analyzes experiment results and generates comprehensive statistics:
- Overall success rates and latency
- Token usage across primitives
- Compression effectiveness
- Per-task and per-primitive breakdowns
- Exports CSV for further analysis

**Usage:**
```bash
python analyze_results.py
```

### 4. `run_full_experiment.sh`
Master script that runs the complete pipeline:
1. Select tasks
2. Check vLLM server is running
3. Run experiment
4. Analyze results

**Usage:**
```bash
./run_full_experiment.sh
```

## Quick Start

To run the complete experiment:

```bash
# 1. Make sure vLLM server is running
curl http://localhost:8000/health

# 2. Run the full pipeline
cd /home/rs67788/Documents/agentCtx
source venv/bin/activate
./scripts/run_full_experiment.sh
```

Or run steps individually:

```bash
# Step by step
source venv/bin/activate

# 1. Select tasks
python scripts/select_tasks.py

# 2. Run experiment (takes hours)
python scripts/run_experiment.py

# 3. Analyze results
python scripts/analyze_results.py
```

## Output Structure

```
agentCtx/
├── selected_tasks.json          # Selected tasks with metadata
├── results/
│   ├── experiment_results_<timestamp>.json  # Raw results
│   ├── experiment_results.csv               # CSV export
│   └── <instance_id>__<primitive>__run<N>/  # Individual run outputs
│       ├── agent.log
│       ├── trajectory.json
│       └── patch.diff (if generated)
└── logs/
    └── (experiment logs)
```

## Key Metrics

The experiment tracks:
- **E2E Latency**: Total time from start to finish for each run
- **Token Usage**: Prompt, completion, and total tokens
- **Success Rate**: Patch generated AND passed tests
- **Compression Stats**: Whether compression fired, tokens saved
- **Patch Generation**: Whether any patch was generated (regardless of tests)

## Primitives

Three context compression primitives are tested:
1. **Truncation**: Keep most recent messages within budget
2. **Summarization**: Summarize oldest 50% of messages using LLM
3. **Retrieval**: Keep most relevant messages using semantic similarity
