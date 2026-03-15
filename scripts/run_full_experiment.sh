#!/bin/bash
# ============================================================
# WAF Experiment — full pipeline
# ============================================================
# Runs: 3 tasks x 2 primitives x 4 budgets x 1 run = 24 agent runs
# LLM context: 50 000 tokens  (start vLLM with --max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes)
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================================"
echo "WAF EXPERIMENT PIPELINE"
echo "========================================================"
echo ""

# -- Step 0: Activate project venv ----------------------------
source "$WORKSPACE_ROOT/venv/bin/activate"
cd "$WORKSPACE_ROOT"

# -- Step 1: Select tasks (idempotent) ------------------------
if [ ! -f "$WORKSPACE_ROOT/selected_tasks.json" ]; then
  echo "Step 1: Selecting tasks..."
  python scripts/select_tasks.py
else
  echo "Step 1: selected_tasks.json already exists - skipping."
fi
echo ""

# -- Step 2: Check vLLM server --------------------------------
echo "Step 2: Checking vLLM server (http://localhost:8000/health)..."
if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo ""
  echo "ERROR: vLLM server is not running."
  echo ""
  echo "Start it with --max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes for the 50k context window:"
  echo ""
  echo "  screen -dmS vllm-server bash -c \\"
  echo "    'source $WORKSPACE_ROOT/venv/bin/activate && \\"
  echo "     vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \\"
  echo "       --port 8000 --dtype auto --max-model-len 32768 --enable-auto-tool-choice --tool-call-parser hermes \\"
  echo "       2>&1 | tee logs/vllm-server.log'"
  echo ""
  exit 1
fi
echo "  vLLM server is running."
echo ""

# -- Step 3: Ensure Podman socket is up -----------------------
echo "Step 3: Checking Podman socket..."
PODMAN_SOCK="unix:///run/user/$(id -u)/podman/podman.sock"
if ! curl -sf --unix-socket "/run/user/$(id -u)/podman/podman.sock" \
     http://localhost/v4.0.0/libpod/info > /dev/null 2>&1; then
  echo "  Starting Podman service..."
  podman system service --time=0 "$PODMAN_SOCK" &
  sleep 3
fi
export DOCKER_HOST="$PODMAN_SOCK"
echo "  Podman socket ready."
echo ""

# -- Step 4: Run agents (108 runs) ----------------------------
echo "Step 4: Running agent experiment..."
echo "  Results saved incrementally -> results/experiment_results.json"
echo ""
python scripts/run_experiment.py
echo ""

# -- Step 5: SWE-bench patch evaluation -----------------------
echo "Step 5: Running SWE-bench evaluation on generated patches..."
python scripts/run_experiment.py --eval-only
echo ""

# -- Step 6: Aggregate analysis + WAF -------------------------
echo "Step 6: Analyzing results and computing WAF..."
python scripts/analyze_results.py
echo ""

echo "========================================================"
echo "EXPERIMENT COMPLETE"
echo "========================================================"
echo "  results/experiment_results.json  -- raw run records"
echo "  results/experiment_results.csv   -- flat CSV for plotting"
echo ""
