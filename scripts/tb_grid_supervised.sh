#!/bin/bash
# Supervised TB grid launcher: waits for vLLM health, then runs the grid.
# Launched via systemd-run --user so it survives terminal/session teardown.
cd "$HOME/projects/agentCtx"
for i in $(seq 1 120); do
    curl -s --max-time 3 http://localhost:8000/v1/models | grep -q "Qwen3.5-35B-A3B" && break
    sleep 10
done
curl -s --max-time 3 http://localhost:8000/v1/models | grep -q "Qwen3.5-35B-A3B" || { echo "vLLM never became healthy"; exit 1; }
exec python3 scripts/run_tbench.py --runs 3 --tasks-file task_lists/tbench_tasks.json --n-concurrent 4
