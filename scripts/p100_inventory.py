"""Phase-100 inventory.

Outputs:
  task_lists/p100_new_tasks.json     — the 70 new tasks (selected_tasks.json minus Review1's 30)
  scripts/p100_existing_runs.json    — for each (cond, budget): list of (task, run_num) already on disk
  scripts/p100_seed_dir.sh           — bash script that symlinks existing trajectory files into the
                                       new ablation dirs so run_experiment.py auto-skips them
"""
import json, re, pathlib
from collections import defaultdict

ROOT = pathlib.Path('/home/rs67788/projects/agentCtx')

# 1) New tasks
full = json.load(open(ROOT / 'task_lists' / 'selected_tasks.json'))
import pandas as pd
df = pd.read_csv(ROOT / 'Review1/Review1.csv')
cur = set(df.task_name.unique())
new_tasks = [t for t in full if t['instance_id'] not in cur]
assert len(new_tasks) == 70
(ROOT / 'task_lists' / 'p100_new_tasks.json').write_text(json.dumps(new_tasks, indent=2))
print(f'wrote task_lists/p100_new_tasks.json  ({len(new_tasks)} tasks)')

# 2) Slug → (condition string used by run_experiment.py, primitive label, budget rule)
SLUG_TO_COND = {
    'truncation':                       'truncation',
    'summarization':                    'summarization',
    'summarization-partial':            'summarization-partial',
    'structured-summarize':             'structured-summarize',
    'structured-summarize-partial':     'structured-summarize-partial',
    'tool-result-clear':                'tool-result-clear',
    'trc-su':                           'trc-su',
    'trc-summarize':                    'trc-su',
    'trc-ss':                           'trc-ss',
    'trc-structured-summarize':         'trc-ss',
    'full-context':                     'full-context',
    'online-trc':                       'online-trc',
    'online_trc':                       'online-trc',
    'otrc-tr':                          'otrc-tr',
    'otrc-truncation':                  'otrc-tr',
    'otrc-su-partial':                  'otrc-su-partial',
    'otrc-summarization-partial':       'otrc-su-partial',
    'otrc-ss-partial':                  'otrc-ss-partial',
    'otrc-structured-summarize-partial':'otrc-ss-partial',
}

def budget_from_dir(d: pathlib.Path):
    n = d.name.lower()
    if '20000' in n or '_20k' in n: return 20000
    if '15000' in n or '_15k' in n: return 15000
    if '10000' in n or '_10k' in n: return 10000
    if 'fullrun' in n: return 15000
    return None

new_ids = {t['instance_id'] for t in new_tasks}
existing = defaultdict(list)   # (cond, budget) → [(task, run, src_traj_path, src_token_log, src_eval_dir, src_agent_log)]

# Layout A: results/<exp_dir>/eval/<prefix>.<task>__<slug>__r<n>.json
for p in (ROOT / 'results').rglob('*.json'):
    s = str(p)
    if '/eval/' not in s or 'Llama' in s: continue
    # Skip our own seeded p100-* dirs to prevent feedback loop on re-run
    if '/p100-' in s: continue
    m = re.search(r'\.((?:django__django|sympy__sympy|scikit-learn__scikit-learn)-\d+)__([a-z0-9_-]+)__r(\d)\.json', s)
    if not m: continue
    tid, slug, run = m.group(1), m.group(2), int(m.group(3))
    if tid not in new_ids: continue
    cond = SLUG_TO_COND.get(slug)
    if not cond: continue
    if cond in ('full-context', 'online-trc'):
        budget = 999999999
    else:
        budget = budget_from_dir(p.parent.parent)
        if budget is None: continue
    existing[(cond, budget)].append((tid, run, str(p)))

# Layout B: results/ablations/<exp>/<task>/<slug>/run_<k>/trajectory.json
for traj in (ROOT / 'results/ablations').rglob('trajectory.json'):
    s = str(traj)
    # Skip our own seeded p100-* dirs to prevent feedback loop on re-run
    if '/p100-' in s: continue
    parts = traj.parts
    try:
        i = parts.index('ablations')
        exp, task, slug = parts[i+1], parts[i+2], parts[i+3]
        run = int(parts[i+4].split('_')[1])
    except (ValueError, IndexError): continue
    if task not in new_ids: continue
    cond = SLUG_TO_COND.get(slug)
    if not cond: continue
    if cond in ('full-context', 'online-trc'):
        budget = 999999999
    else:
        budget = budget_from_dir(ROOT / 'results/ablations' / exp)
        if budget is None: continue
    existing[(cond, budget)].append((task, run, str(traj)))

# Print summary
print()
print(f'{"cell":<40} {"existing":>10}')
print('-'*52)
for (cond, b), entries in sorted(existing.items()):
    print(f'{cond+"@"+str(b):<40} {len(entries):>10}')
print(f'\nTotal existing runs to reuse: {sum(len(v) for v in existing.values())}')

(ROOT / 'scripts/p100_existing_runs.json').write_text(
    json.dumps({f'{c}|{b}': v for (c, b), v in existing.items()}, indent=2))
print('wrote scripts/p100_existing_runs.json')
