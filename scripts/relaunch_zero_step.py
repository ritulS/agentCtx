"""Relaunch the 473 zero-step runs from the docker cold-pull incident.

For each (ablation, budget) cell:
  1. Remove zero-step keys from experiment_results.json
  2. Delete the corresponding run_X dirs (clean slate so new run writes cleanly)
  3. Write task-list JSON with the union of affected tasks
  4. Invoke run_experiment.py — resume logic re-runs only the missing keys

Designed to be safe to re-run (idempotent).
"""
import json, shutil, subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/rs67788/projects/agentCtx")
manifest = json.loads((ROOT / "scripts/zero_step_manifest.json").read_text())

# Group manifest by (ablation, budget)
by_cell = defaultdict(list)
for r in manifest:
    by_cell[(r["ablation"], r["token_budget"])].append(r)

print(f"Cells to recover: {len(by_cell)}")
for (abl, b), rs in sorted(by_cell.items()):
    print(f"  {abl:24s} budget={b}  n={len(rs)}")

print()
print("=== Cleaning up ===")

cells_to_run = []
for (abl, budget), rs in sorted(by_cell.items()):
    abl_dir = ROOT / "results/ablations" / abl
    rj = abl_dir / "experiment_results.json"
    rows = json.loads(rj.read_text())

    bad_keys = {f'{r["task_name"]}__{r["condition"]}__r{r["run_num"]}' for r in rs}
    before = len(rows)
    rows = [row for row in rows if row.get("key") not in bad_keys]
    after = len(rows)
    rj.write_text(json.dumps(rows, indent=2))
    print(f"  {abl}: removed {before-after} zero-step rows ({len(bad_keys)} keys), kept {after}")

    # Remove run_X dirs
    rm = 0
    for r in rs:
        rd = abl_dir / r["task_name"] / r["condition"] / f'run_{r["run_num"]}'
        if rd.exists():
            shutil.rmtree(rd); rm += 1
        # Tidy now-empty parents
        for p in (rd.parent, rd.parent.parent):
            if p.exists() and not any(p.iterdir()): p.rmdir()
    print(f"  {abl}: removed {rm} run dirs")

    # Build task-list JSON (union of tasks across all conditions in this cell)
    task_set = sorted({(r["task_name"], r["repo"]) for r in rs})
    tasks_payload = [{"instance_id": t, "repo": repo} for (t, repo) in task_set]
    tlist = ROOT / "task_lists" / f"recovery_{abl}.json"
    tlist.write_text(json.dumps(tasks_payload, indent=2))

    # Conditions that have entries in this cell
    conds = sorted({r["condition"] for r in rs})

    cells_to_run.append({"ablation": abl, "budget": budget,
                         "tasks_file": tlist, "conditions": conds,
                         "n_runs": len(rs), "n_tasks": len(task_set)})

print()
print("=== Cleanup complete. Now invoking runner per cell. ===")

# Order: smallest cells first (faster turnaround), then big ones
cells_to_run.sort(key=lambda c: c["n_runs"])

for c in cells_to_run:
    abl = c["ablation"]
    budget = c["budget"]
    cmd = [
        "venv/bin/python3", "scripts/run_experiment.py",
        "--ablation", abl,
        "--budget",   str(budget),
        "--tasks-file", str(c["tasks_file"]),
        "--conditions", *c["conditions"],
    ]
    print()
    print(f">>> {abl} | budget={budget} | tasks={c['n_tasks']} conds={c['conditions']} expected_runs={c['n_runs']}")
    print(f"    {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=False)

    # Eval pass
    cmd_eval = cmd + ["--eval-only"]
    print(f">>> EVAL {abl}")
    subprocess.run(cmd_eval, cwd=str(ROOT), check=False)

print("\n=== ALL ZERO-STEP RECOVERY CELLS DONE ===")
