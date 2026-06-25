"""Per-task efficiency winner, computed at each budget.

For each budget B ∈ {10000, 15000, 20000}, and each task:
  Among primitives that resolved the task at budget B (FC and OTRC always at ∞):
    - find the primitive with strictly minimum mean-tokens across resolving runs
    - if a single primitive has the min (no ties) → unambiguous winner
    - if two or more tie at the min                → no clear winner
    - if no primitive resolved                     → unresolved

Writes Review1/winners_table.md (combined report for all 3 budgets) and prints it.
"""
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
df   = pd.read_csv(ROOT / "Review1.csv")
df = df[df.depth == 0.5].copy()  # scope to canonical depth — depth-grid lives in depth_analysis.py
df["resolved_bool"] = df["resolved"].astype(str) == "True"

PRIMS = ["FC", "TR", "SU-full", "SU-partial", "SS", "SS-partial", "TRC",
        "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial", "OTRC"]
BUDGETS = [10000, 15000, 20000]
N_TASKS = df.task_name.nunique()

def slice_for(prim, budget):
    if prim in ("FC", "OTRC"):
        return df[df.primitive == prim]
    return df[(df.primitive == prim) & (df.token_budget == budget)]


def run_budget(budget: int) -> tuple[list, dict]:
    rows = []
    for task in sorted(df.task_name.unique()):
        cost = {}                                      # prim -> (mean_tok, mean_steps, n_resolved)
        for p in PRIMS:
            sub = slice_for(p, budget)
            sub = sub[sub.task_name == task]
            if sub.empty: continue
            win = sub[sub.resolved_bool]
            if len(win) == 0: continue
            cost[p] = (win.total_tokens_consumed.mean(),
                       win.step_count.mean(),
                       len(win))

        if not cost:
            rows.append((task, 0, "—", "—", "—", "no primitive resolved"))
            continue

        tok_winner = min(cost, key=lambda p: cost[p][0])
        tok_min    = cost[tok_winner][0]
        tok_ties   = [p for p, c in cost.items() if c[0] == tok_min]
        runner_up  = sorted(cost.items(), key=lambda kv: kv[1][0])[1][0] if len(cost) > 1 else None
        runner_up_tok = cost[runner_up][0] if runner_up else None

        if len(tok_ties) == 1:
            verdict = f"**{tok_winner}**"
        else:
            verdict = "no clear winner"

        margin = f"{(runner_up_tok - tok_min)/1000:.0f}k" if runner_up_tok else "—"
        rows.append((
            task,
            len(cost),
            f"{tok_winner} ({tok_min/1000:.0f}k)",
            f"{runner_up} ({runner_up_tok/1000:.0f}k)" if runner_up else "—",
            margin,
            verdict,
        ))

    n_winner   = sum(1 for r in rows if r[5].startswith("**"))
    n_unclear  = sum(1 for r in rows if r[5] == "no clear winner")
    n_unsolved = sum(1 for r in rows if r[5] == "no primitive resolved")
    winner_counts = Counter(r[5].strip("*") for r in rows if r[5].startswith("**"))
    return rows, {"n_winner": n_winner, "n_unclear": n_unclear,
                  "n_unsolved": n_unsolved, "winner_counts": winner_counts}


parts = ["# Per-task efficiency winner — by budget\n",
         "Among primitives that resolved each task, which uses the fewest tokens?\n",
         "FC and OTRC always at ∞. Cost = mean total tokens across resolving runs only.\n"]

cross_budget = []                                       # for the comparison summary
for budget in BUDGETS:
    rows, stats = run_budget(budget)
    cross_budget.append((budget, stats))

    parts.append(f"\n## Budget = {budget//1000}k\n")
    parts.append("| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |")
    parts.append("|---|---:|---|---|---:|---|")
    for t, n, tw, ru, mg, v in rows:
        parts.append(f"| `{t}` | {n} | {tw} | {ru} | {mg} | {v} |")

    parts.append(f"\n**Summary @ {budget//1000}k:** "
                 f"{stats['n_winner']}/{N_TASKS} unambiguous winner · "
                 f"{stats['n_unclear']}/{N_TASKS} no clear winner · "
                 f"{stats['n_unsolved']}/{N_TASKS} unresolved.\n")
    if stats["winner_counts"]:
        parts.append(f"**Winner distribution @ {budget//1000}k:**")
        for p, n in stats["winner_counts"].most_common():
            parts.append(f"- {p}: {n}")

# Cross-budget comparison
parts.append("\n\n## Cross-budget comparison\n")
parts.append("| budget | unambig winner | no clear winner | unresolved |")
parts.append("|---|---:|---:|---:|")
for budget, s in cross_budget:
    parts.append(f"| {budget//1000}k | {s['n_winner']}/{N_TASKS} | "
                 f"{s['n_unclear']}/{N_TASKS} | {s['n_unsolved']}/{N_TASKS} |")

parts.append("\n### Winner counts side-by-side")
all_winners = sorted(set().union(*(s["winner_counts"].keys() for _, s in cross_budget)))
parts.append("| primitive | 10k | 15k | 20k |")
parts.append("|---|---:|---:|---:|")
for p in all_winners:
    cells = " | ".join(str(s["winner_counts"].get(p, 0)) for _, s in cross_budget)
    parts.append(f"| {p} | {cells} |")

out_md = "\n".join(parts) + "\n"
(ROOT / "winners_table.md").write_text(out_md)
print(out_md)
