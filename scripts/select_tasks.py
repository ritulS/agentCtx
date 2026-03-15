#!/usr/bin/env python3
"""
Select 10 tasks per repo (Flask, Django, SymPy) for the E1 experiment.

Selection strategy: sort all tasks in a repo by problem-statement word count
(complexity proxy) and pick 10 evenly-spaced tasks across the full complexity
spectrum.  This gives balanced coverage across easy, medium, and hard tasks.

Usage:
    source venv/bin/activate
    python scripts/select_tasks.py
"""

import json
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    print("Error: datasets library not found.  pip install datasets")
    raise SystemExit(1)

OUTPUT_FILE      = Path(__file__).parent.parent / "selected_tasks.json"
N_PER_REPO       = 10
DATASET_NAME     = "princeton-nlp/SWE-Bench_Lite"
DATASET_SPLIT    = "test"

REPOS = {
    "pallets/flask":  "flask",
    "django/django":  "django",
    "sympy/sympy":    "sympy",
}


def select_evenly(repo_tasks: list[dict], n: int) -> list[tuple[dict, int]]:
    """Pick n tasks evenly spaced across the word-count-sorted list."""
    tasks_wc = sorted(
        [(t, len(t["problem_statement"].split())) for t in repo_tasks],
        key=lambda x: x[1],
    )
    total = len(tasks_wc)
    if total <= n:
        print(f"  Warning: only {total} tasks available, returning all.")
        return tasks_wc

    # Evenly spaced indices: 0-based, distributed across [0, total-1]
    step = (total - 1) / (n - 1)
    indices = [round(i * step) for i in range(n)]
    return [tasks_wc[i] for i in indices]


def main() -> None:
    print(f"Loading {DATASET_NAME} ({DATASET_SPLIT})...")
    dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT)
    print(f"Total instances in dataset: {len(dataset)}")

    all_selected: list[dict] = []

    for repo, label in REPOS.items():
        print(f"\n[{label}] repo={repo}")
        repo_tasks = [t for t in dataset if t["repo"] == repo]
        print(f"  Available: {len(repo_tasks)} tasks")

        selected = select_evenly(repo_tasks, N_PER_REPO)
        word_counts = [wc for _, wc in selected]

        for rank, (task, wc) in enumerate(selected):
            # Assign coarse complexity label based on position in selection
            if rank < N_PER_REPO // 3:
                complexity = "low"
            elif rank < 2 * N_PER_REPO // 3:
                complexity = "medium"
            else:
                complexity = "high"

            all_selected.append({
                "instance_id":        task["instance_id"],
                "repo":               task["repo"],
                "problem_statement":  task["problem_statement"],
                "FAIL_TO_PASS":       task["FAIL_TO_PASS"],
                "PASS_TO_PASS":       task["PASS_TO_PASS"],
                "word_count":         wc,
                "complexity":         complexity,
            })
            print(f"  [{rank+1:2d}/{N_PER_REPO}] {complexity:<6} "
                  f"{task['instance_id']:<40} {wc:4d} words")

        print(f"  Word-count range: {min(word_counts)} – {max(word_counts)}")

    OUTPUT_FILE.write_text(json.dumps(all_selected, indent=2))
    print(f"\n✓ {len(all_selected)} tasks written to {OUTPUT_FILE}")
    for repo, label in REPOS.items():
        n = sum(1 for t in all_selected if t["repo"] == repo)
        print(f"  {label}: {n}")


if __name__ == "__main__":
    main()
