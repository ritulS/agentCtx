#!/usr/bin/env python3
"""
Select 3 tasks per repo (Flask, Django, SymPy) based on problem complexity.
Uses problem description word count as a proxy for complexity.
Selects: low, medium, and high complexity tasks from each repo.
"""

import json
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    print("Error: datasets library not found. Install with: pip install datasets")
    exit(1)

OUTPUT_FILE = Path(__file__).parent.parent / "selected_tasks.json"

REPOS = {
    "pallets/flask": "flask",
    "django/django": "django",
    "sympy/sympy": "sympy"
}


def count_words(text):
    """Count words in a text string."""
    return len(text.split())


def select_tasks_by_complexity(repo_tasks):
    """
    Select 3 tasks from a repo: low, medium, and high complexity.
    Complexity is based on problem description word count.
    """
    # Calculate word count for each task
    tasks_with_words = []
    for task in repo_tasks:
        word_count = count_words(task["problem_statement"])
        tasks_with_words.append((task, word_count))
    
    # Sort by word count
    tasks_with_words.sort(key=lambda x: x[1])
    
    if len(tasks_with_words) < 3:
        print(f"  Warning: Only {len(tasks_with_words)} tasks available")
        return tasks_with_words
    
    # Select low (first tercile), medium (second tercile), high (third tercile)
    n = len(tasks_with_words)
    if n == 3:
        # If exactly 3, just use them as low, med, high
        selected = tasks_with_words
    else:
        low_idx = n // 6  # Middle of first tercile
        med_idx = n // 2  # Middle of second tercile
        high_idx = n - n // 6 - 1  # Middle of third tercile (fixed off-by-one)
        
        selected = [
            tasks_with_words[low_idx],
            tasks_with_words[med_idx],
            tasks_with_words[high_idx]
        ]
    
    return selected


def main():
    print("Loading SWE-Bench_Lite dataset...")
    dataset = load_dataset("princeton-nlp/SWE-Bench_Lite", split="test")
    
    all_selected = []
    
    for repo, label in REPOS.items():
        print(f"\nProcessing {label} ({repo})...")
        
        # Filter tasks from this repo
        repo_tasks = [t for t in dataset if t["repo"] == repo]
        print(f"  Found {len(repo_tasks)} total tasks")
        
        # Select 3 tasks by complexity
        selected = select_tasks_by_complexity(repo_tasks)
        
        for task, word_count in selected:
            complexity = "low" if word_count == selected[0][1] else \
                        "medium" if word_count == selected[1][1] else "high"
            
            task_info = {
                "instance_id": task["instance_id"],
                "repo": task["repo"],
                "problem_statement": task["problem_statement"],
                "FAIL_TO_PASS": task["FAIL_TO_PASS"],
                "PASS_TO_PASS": task["PASS_TO_PASS"],
                "word_count": word_count,
                "complexity": complexity
            }
            
            all_selected.append(task_info)
            print(f"  [{complexity:6}] {task['instance_id']:30} | {word_count:4} words")
    
    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_selected, f, indent=2)
    
    print(f"\n✓ Selected {len(all_selected)} tasks saved to {OUTPUT_FILE}")
    print(f"  Breakdown: {sum(1 for t in all_selected if 'flask' in t['repo'])} Flask + "
          f"{sum(1 for t in all_selected if 'django' in t['repo'])} Django + "
          f"{sum(1 for t in all_selected if 'sympy' in t['repo'])} SymPy")
    
    # Print summary statistics
    word_counts = [t["word_count"] for t in all_selected]
    print(f"\nWord count range: {min(word_counts)} - {max(word_counts)}")
    print(f"  Low complexity: {[t['word_count'] for t in all_selected if t['complexity'] == 'low']}")
    print(f"  Medium complexity: {[t['word_count'] for t in all_selected if t['complexity'] == 'medium']}")
    print(f"  High complexity: {[t['word_count'] for t in all_selected if t['complexity'] == 'high']}")


if __name__ == "__main__":
    main()
