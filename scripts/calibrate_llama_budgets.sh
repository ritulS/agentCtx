#!/bin/bash
# Llama 3.3 70B  §b: derive TIGHT / MEDIUM / LOOSE budgets from the FC peak
# token distribution. Mirrors ALBUS_PLAN §1.3b. No GPU needed.
#
# Reads:  results/ablations/llama33-70b-inf/experiment_results.json
# Prints: peak token quartiles + trigger rates at candidate budgets.
# Target: mirror Qwen3.5-35B-A3B trigger rates (97% / 88% / 76% for T/M/L)
#         within ~5pp.
#
# Usage:  bash scripts/calibrate_llama_budgets.sh
#         (then paste output to chat for budget approval before §c)
set -euo pipefail

WS="$HOME/projects/agentCtx"
cd "$WS"

INF_JSON="$WS/results/ablations/llama33-70b-inf/experiment_results.json"
if [ ! -f "$INF_JSON" ]; then
    echo "[ERROR] Inf-baseline results not found at $INF_JSON" >&2
    echo "[ERROR] Run scripts/run_llama_inf.sh first." >&2
    exit 1
fi

venv/bin/python3 -c "
import json, pathlib
rows = json.loads(pathlib.Path('$INF_JSON').read_text())
fc = [r for r in rows if r.get('condition')=='full-context']
peaks = sorted(max(r['step_prompt_tokens']) for r in fc if r.get('step_prompt_tokens'))
if not peaks:
    raise SystemExit('No FC peak data found — did the agent runs complete?')
print(f'=== Llama 3.3 70B FC peak distribution (n={len(peaks)} trajectories) ===')
print(f'p25    = {peaks[len(peaks)//4]:>6}')
print(f'median = {peaks[len(peaks)//2]:>6}')
print(f'p75    = {peaks[3*len(peaks)//4]:>6}')
print(f'max    = {peaks[-1]:>6}')
print()
print('=== Trigger rates at candidate budgets ===')
print('budget | trigger rate (fraction of trajectories where peak > budget)')
print('-------+---------------------------------------------------------------')
for b in (2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000, 20000):
    tr = sum(1 for p in peaks if p > b) / len(peaks)
    print(f'{b//1000:>3}k    | {tr*100:>5.1f}%')
print()
print('Anchor: Qwen3.5-35B-A3B trigger rates are 97% / 88% / 76% for T / M / L.')
print('Pick three budgets whose trigger rates land within ~5pp of those targets,')
print('paste this output to chat for explicit user approval before §c.')
"
