"""Seed new ablation dirs from existing runs so run_experiment.py auto-skips them.

For each (cond, budget, task, run) in scripts/p100_existing_runs.json:
  1. Determine target ablation dir name (see PHASE_MAP below).
  2. Symlink the source trajectory.json + token_log.json + agent.log into
     results/ablations/<target>/<task>/<cond>/run_<n>/
  3. Append a row to <target>/experiment_results.json so load_existing_results
     marks the run done.
  4. Symlink/copy the source eval JSON into <target>/eval/.
"""
import json, os, pathlib, re, shutil

ROOT = pathlib.Path('/home/rs67788/projects/agentCtx')

# Map (cond, budget) → target ablation dir name. Keep budget in name.
def target_ablation(cond: str, budget: int) -> str:
    if budget >= 999999998:
        return 'p100-inf'                 # FC and OTRC share the same dir
    if cond in ('truncation', 'summarization', 'summarization-partial',
                'structured-summarize', 'structured-summarize-partial'):
        return f'p100-singles-{budget}'
    if cond in ('tool-result-clear', 'trc-su', 'trc-ss'):
        return f'p100-trc-{budget}'
    if cond in ('otrc-tr', 'otrc-su-partial', 'otrc-ss-partial'):
        return f'p100-otrc-{budget}'
    raise ValueError(cond)

existing = json.loads((ROOT / 'scripts/p100_existing_runs.json').read_text())

seeded = 0
for cell, entries in existing.items():
    cond, budget = cell.split('|')
    budget = int(budget)
    target = target_ablation(cond, budget)
    tdir   = ROOT / 'results/ablations' / target
    (tdir / 'eval').mkdir(parents=True, exist_ok=True)

    rows_path = tdir / 'experiment_results.json'
    rows = json.loads(rows_path.read_text()) if rows_path.exists() else []
    keys = {r['key'] for r in rows}

    for task, run, src in entries:
        key = f'{task}__{cond}__r{run}'
        if key in keys: continue
        run_dir = tdir / task / cond / f'run_{run}'
        run_dir.mkdir(parents=True, exist_ok=True)

        src_path = pathlib.Path(src)
        # Detect layout: eval JSON vs trajectory.json
        if src_path.name == 'trajectory.json':
            traj_src = src_path
            tlog_src = src_path.parent / 'token_log.json'
            alog_src = src_path.parent / 'agent.log'
            # eval JSON is usually colocated in <exp>/eval/<prefix>.<task>__<slug>__r<n>.json
            # — search for it
            eval_candidates = list((src_path.parents[3] / 'eval').glob(f'*.{task}__*__r{run}.json'))
            eval_src = eval_candidates[0] if eval_candidates else None
        else:
            # eval JSON path; trajectory lives in trajectories/<task>/<slug>/run_<n>/
            traj_src = src_path.parent.parent / 'trajectories' / task / cond / f'run_{run}' / 'trajectory.json'
            if not traj_src.exists():
                # try alternative
                cand = list(src_path.parents[1].rglob(f'{task}/{cond}/run_{run}/trajectory.json'))
                traj_src = cand[0] if cand else None
            tlog_src = traj_src.parent / 'token_log.json' if traj_src else None
            alog_src = traj_src.parent / 'agent.log' if traj_src else None
            eval_src = src_path

        # Symlink files
        for srcf, name in [(traj_src, 'trajectory.json'),
                           (tlog_src, 'token_log.json'),
                           (alog_src, 'agent.log')]:
            if srcf and srcf.exists() and not (run_dir / name).exists():
                os.symlink(srcf, run_dir / name)

        if eval_src and eval_src.exists():
            dst_eval = tdir / 'eval' / f'qwen35-a3b.{task}__{cond}__r{run}.json'
            if not dst_eval.exists():
                os.symlink(eval_src, dst_eval)

        # Append to experiment_results.json (minimal fields run_experiment.py checks)
        rows.append({'key': key, 'instance_id': task, 'condition': cond, 'run_num': run,
                     'budget': budget, 'seeded_from': str(src_path)})
        keys.add(key)
        seeded += 1

    rows_path.write_text(json.dumps(rows, indent=2))

print(f'seeded {seeded} runs across {len(existing)} cells')
