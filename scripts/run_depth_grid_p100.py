"""Master orchestrator — paper-critical 15k slice.

Targeted cells (4 total, ~3,200 runs):
  - p100-depth30-singles-15000
  - p100-depth30-otrc-15000
  - p100-depth70-singles-15000
  - p100-depth70-otrc-15000

These support the RQ5 (SU-partial > SU-full at varied depth) and RQ5b
(OTRC + partial-summarization super-additivity at varied depth) claims at the
canonical 15k budget, on a symmetric depth grid (0.3, 0.5, 0.7).

Each cell:
  1. Run agent loop via scripts/run_experiment.py
  2. Run --eval-only pass on the same cell
  3. Snapshot experiment_results.json into Review1/raw/depth_p100_runs/
  4. Print cell-done banner
"""
import json, shutil, subprocess, time
from pathlib import Path

ROOT = Path("/home/rs67788/projects/agentCtx")
TASKS_FILE = ROOT / "task_lists/p100_all_100_tasks.json"
PYTHON = "venv/bin/python3"
SNAPSHOT_DIR = ROOT / "Review1/raw/depth_p100_runs"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GROUP_CONDS = {
    "singles": ["truncation","summarization","summarization-partial",
                "structured-summarize","structured-summarize-partial"],
    "otrc":    ["otrc-tr","otrc-su-partial","otrc-ss-partial"],
}

# (depth, budget, group)  — order is depth then group within depth
TARGETED_CELLS = [
    (0.3, 15000, "singles"),
    (0.3, 15000, "otrc"),
    (0.7, 15000, "singles"),
    (0.7, 15000, "otrc"),
]

def cell_name(depth, group, budget):
    return f"p100-depth{int(depth*100)}-{group}-{budget}"

def run_cmd(cmd, label):
    print(f"\n>>> {label}")
    print(f"    {' '.join(str(c) for c in cmd)}")
    start = time.time()
    r = subprocess.run(cmd, cwd=str(ROOT))
    dur = time.time() - start
    print(f"<<< {label}  exit={r.returncode}  duration={dur/60:.1f}min")
    return r.returncode

def snapshot(ablation):
    src = ROOT / "results/ablations" / ablation / "experiment_results.json"
    dst = SNAPSHOT_DIR / f"{ablation}.json"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"    snapshot → {dst}")
    else:
        print(f"    [WARN] no source experiment_results.json at {src}")

def main():
    print(f"=== DEPTH-GRID P100 (15K SLICE) START — {time.ctime()} ===")
    print(f"Tasks file: {TASKS_FILE}")
    print(f"Targeted cells: {TARGETED_CELLS}")
    n_cells = len(TARGETED_CELLS)
    print(f"Total cells: {n_cells}")

    for cell_idx, (depth, budget, group) in enumerate(TARGETED_CELLS, start=1):
        ablation = cell_name(depth, group, budget)
        conditions = GROUP_CONDS[group]
        label_prefix = f"[{cell_idx:>2}/{n_cells}] {ablation}"

        # Agent loop
        agent_cmd = [
            PYTHON, "scripts/run_experiment.py",
            "--ablation",   ablation,
            "--budget",     str(budget),
            "--depth",      str(depth),
            "--tasks-file", str(TASKS_FILE),
            "--conditions", *conditions,
        ]
        run_cmd(agent_cmd, f"{label_prefix} AGENT")

        # Eval pass
        eval_cmd = agent_cmd + ["--eval-only"]
        run_cmd(eval_cmd, f"{label_prefix} EVAL")

        # Snapshot
        snapshot(ablation)
        print(f"=== CELL {cell_idx}/{n_cells} DONE: {ablation} @ {time.ctime()} ===")

    print(f"\n=== ALL DEPTH-GRID (15K SLICE) CELLS DONE — {time.ctime()} ===")

if __name__ == "__main__":
    main()
