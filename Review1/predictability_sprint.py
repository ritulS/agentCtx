"""Predictability sprint Phase 1.

Question: do tasks where TR uniquely wins look *different* — on features visible
before running the agent — from tasks where the budget-best primitive uniquely wins?

If yes (≥70% leave-one-out classifier accuracy on a sane feature set) → +13pp
routing headroom is achievable; build the controller.

If no (≈50%) → headroom is an oracle artifact; reframe paper as "pick the
average winner, routing is not buildable from observables".

Pairs we test (from M3 oracle-of-k):
  10k:  TR  vs  TRC+SS
  15k:  TR  vs  SU-partial
  20k:  TR  vs  TRC+SS

We also pool all 3 budgets ("pan-budget") since the paper's claim is that *TR
itself* covers a structurally different task slice from compression.
"""

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from scipy.stats import mannwhitneyu, fisher_exact

ROOT   = Path(__file__).parent.parent
REVIEW = Path(__file__).parent
CSV    = REVIEW / "Review1.csv"
OUT_MD = REVIEW / "predictability_report.md"

# ────────────────────────────────────────────────────────────────────────────
# 1. Locate per-task problem statements (one trajectory.json per task is enough)
# ────────────────────────────────────────────────────────────────────────────
def find_problem_statement(task_name: str) -> str | None:
    """Look for any trajectory.json for this task and pull the user prompt."""
    candidates = list((ROOT / "results").rglob(f"{task_name}/full-context/run_*/trajectory.json"))
    if not candidates:
        candidates = list((ROOT / "results").rglob(f"{task_name}/*/run_*/trajectory.json"))
    for p in candidates:
        try:
            traj = json.loads(p.read_text())
            for msg in traj.get("messages", []):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    m = re.search(r"<pr_description>\s*Consider the following PR description:\s*(.*?)\s*</pr_description>",
                                  content, re.DOTALL)
                    if m:
                        return m.group(1).strip()
                    return content
        except Exception:
            continue
    return None


# ────────────────────────────────────────────────────────────────────────────
# 2. Extract features from a problem statement
# ────────────────────────────────────────────────────────────────────────────
TEST_RE       = re.compile(r"\btest[s_]?\b", re.IGNORECASE)
TRACEBACK_RE  = re.compile(r"\bTraceback\b|\bError\b|\bException\b")
URL_RE        = re.compile(r"https?://\S+")
PATH_RE       = re.compile(r"[\w\-/\.]+\.py")
CODEBLOCK_RE  = re.compile(r"```")
INLINECODE_RE = re.compile(r"`[^`\n]+`")

def featurize(ps: str, repo: str) -> dict:
    chars  = len(ps)
    words  = len(ps.split())
    lines  = ps.count("\n") + 1
    return {
        "len_chars":      chars,
        "len_words":      words,
        "len_lines":      lines,
        "n_code_blocks":  len(CODEBLOCK_RE.findall(ps)) // 2,
        "n_inline_code":  len(INLINECODE_RE.findall(ps)),
        "n_py_paths":     len(PATH_RE.findall(ps)),
        "n_urls":         len(URL_RE.findall(ps)),
        "n_traceback":    len(TRACEBACK_RE.findall(ps)),
        "n_tests":        len(TEST_RE.findall(ps)),
        "is_django":      int("django"  in repo),
        "is_sympy":       int("sympy"   in repo),
        "is_sklearn":     int("scikit"  in repo),
        "is_astropy":     int("astropy" in repo),
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. Define the task groups for each comparison
# ────────────────────────────────────────────────────────────────────────────
df = pd.read_csv(CSV)
df = df[df.depth == 0.5].copy()  # scope to canonical depth — depth-grid lives in depth_analysis.py
df["resolved_bool"] = df["resolved"].astype(str) == "True"
N_TASKS = df.task_name.nunique()

def per_task_rate(prim, budget=None):
    if prim in ("FC", "OTRC"):
        sub = df[df.primitive == prim]
    else:
        sub = df[(df.primitive == prim) & (df.token_budget == budget)]
    return sub.groupby("task_name").resolved_bool.mean().sort_index()

PAIRS = [
    ("10k", "TR", 10000, "TRC+SS",     10000),
    ("15k", "TR", 15000, "SU-partial", 15000),
    ("20k", "TR", 20000, "TRC+SS",     20000),
]

def label_tasks(rate_a: pd.Series, rate_b: pd.Series) -> pd.DataFrame:
    """Return DataFrame of tasks with diff > 0 (label=1, A wins) or diff < 0 (label=0)."""
    diff = (rate_a - rate_b).rename("diff")
    out = pd.DataFrame({"diff": diff})
    out = out[out["diff"] != 0]
    out["label"] = (out["diff"] > 0).astype(int)  # 1 = A (TR) wins, 0 = B wins
    return out


# ────────────────────────────────────────────────────────────────────────────
# 4. Build feature matrix once (per task)
# ────────────────────────────────────────────────────────────────────────────
all_tasks = sorted(df.task_name.unique())
repo_map  = df.set_index("task_name").repo.to_dict()

print(f"Loading problem statements for {len(all_tasks)} tasks…")
features = {}
missing  = []
for t in all_tasks:
    ps = find_problem_statement(t)
    if ps is None:
        missing.append(t)
        continue
    features[t] = featurize(ps, repo_map[t])
print(f"  got {len(features)} / {len(all_tasks)} (missing: {missing})")

feat_df = pd.DataFrame(features).T
feat_df.index.name = "task_name"


# ────────────────────────────────────────────────────────────────────────────
# 5. Run the analysis
# ────────────────────────────────────────────────────────────────────────────
report = ["# Predictability sprint Phase 1\n",
          "Can a controller pick the right primitive from observables alone?\n"]

def out(s=""):
    print(s); report.append(s)

for label, pA, bA, pB, bB in PAIRS:
    out(f"\n## Budget {label}: {pA} vs {pB}\n")
    rA = per_task_rate(pA, bA)
    rB = per_task_rate(pB, bB)
    tasks = label_tasks(rA, rB)
    n_a = int((tasks.label == 1).sum())
    n_b = int((tasks.label == 0).sum())
    out(f"- Tasks where {pA} > {pB}: **{n_a}**")
    out(f"- Tasks where {pB} > {pA}: **{n_b}**")
    out(f"- Ties dropped: {N_TASKS - n_a - n_b}\n")

    # Restrict to tasks for which we have features
    keep = [t for t in tasks.index if t in feat_df.index]
    X = feat_df.loc[keep]
    y = tasks.loc[keep, "label"].values
    if len(set(y)) < 2 or len(y) < 6:
        out("  (skipped: not enough samples in both classes)")
        continue

    # Per-feature univariate tests
    out("### Univariate feature tests")
    out("| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |")
    out("| --- | ---: | ---: | ---: |")
    rows = []
    for col in X.columns:
        a = X.loc[y == 1, col].values.astype(float)
        b = X.loc[y == 0, col].values.astype(float)
        if a.std() == 0 and b.std() == 0:
            p = 1.0
        else:
            try:
                _, p = mannwhitneyu(a, b, alternative="two-sided")
            except ValueError:
                p = 1.0
        rows.append((col, a.mean(), b.mean(), p))
    rows.sort(key=lambda r: r[3])
    for col, ma, mb, p in rows:
        flag = "**" if p < 0.05 else ""
        out(f"| {flag}{col}{flag} | {ma:.2f} | {mb:.2f} | {p:.3f}{flag} |")

    # Multivariate: leave-one-out logistic-regression accuracy
    pipe = Pipeline([
        ("scale", StandardScaler()),
        ("lr",    LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    loo = LeaveOneOut()
    correct = 0
    for tr, te in loo.split(X):
        pipe.fit(X.iloc[tr], y[tr])
        pred = pipe.predict(X.iloc[te])
        correct += int(pred[0] == y[te][0])
    acc = correct / len(y)
    base = max((y == 1).mean(), (y == 0).mean())
    out(f"\n### Leave-one-out logistic regression\n")
    out(f"- LOO accuracy: **{acc*100:.1f}%**  (n={len(y)})")
    out(f"- Majority-class baseline: {base*100:.1f}%")
    out(f"- **Verdict:** {'separable' if acc > base + 0.10 else 'NOT separable'}"
        f" ({'+' if acc > base else ''}{(acc - base)*100:+.1f}pp over baseline)")


# ────────────────────────────────────────────────────────────────────────────
# 6. Pan-budget pooled analysis: TR-friendly vs compression-friendly task
# ────────────────────────────────────────────────────────────────────────────
out("\n## Pooled: TR-friendly vs compression-friendly tasks (pan-budget)\n")
out("A task is 'TR-friendly' if TR's mean rate across budgets > best-compression's.")

tr_avg = pd.concat([per_task_rate("TR", b) for b in (10000, 15000, 20000)], axis=1).mean(axis=1)
comp_primitives = ["TRC+SS", "SU-partial", "TRC", "TRC+SU", "SS", "SS-partial",
                   "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial", "SU-full"]
comp_max = pd.concat(
    [per_task_rate(p, b) for p in comp_primitives for b in (10000, 15000, 20000)
     if len(per_task_rate(p, b)) == N_TASKS], axis=1).max(axis=1)

diff = (tr_avg - comp_max).dropna()
labels = pd.Series((diff >= 0).astype(int), name="tr_friendly")  # 1 = TR ≥ best comp
pos = (labels == 1).sum(); neg = (labels == 0).sum()
out(f"- TR-friendly (TR ≥ best compressor on average): **{pos}** tasks")
out(f"- compression-friendly: **{neg}** tasks\n")

X = feat_df.loc[labels.index.intersection(feat_df.index)]
y = labels.loc[X.index].values
if len(set(y)) >= 2 and len(y) >= 10:
    out("### Univariate (pooled)")
    out("| feature | mean(TR-friendly) | mean(comp-friendly) | p |")
    out("| --- | ---: | ---: | ---: |")
    rows = []
    for col in X.columns:
        a = X.loc[y == 1, col].values.astype(float)
        b = X.loc[y == 0, col].values.astype(float)
        try:
            _, p = mannwhitneyu(a, b, alternative="two-sided")
        except ValueError:
            p = 1.0
        rows.append((col, a.mean(), b.mean(), p))
    rows.sort(key=lambda r: r[3])
    for col, ma, mb, p in rows:
        flag = "**" if p < 0.05 else ""
        out(f"| {flag}{col}{flag} | {ma:.2f} | {mb:.2f} | {p:.3f}{flag} |")

    pipe = Pipeline([("scale", StandardScaler()),
                     ("lr",    LogisticRegression(max_iter=1000, class_weight="balanced"))])
    loo = LeaveOneOut()
    correct = 0
    for tr, te in loo.split(X):
        pipe.fit(X.iloc[tr], y[tr])
        correct += int(pipe.predict(X.iloc[te])[0] == y[te][0])
    acc = correct / len(y)
    base = max((y == 1).mean(), (y == 0).mean())
    out(f"\n### Leave-one-out logistic regression (pooled)")
    out(f"- LOO accuracy: **{acc*100:.1f}%**  (n={len(y)})")
    out(f"- Majority-class baseline: {base*100:.1f}%")
    out(f"- **Verdict:** {'separable' if acc > base + 0.10 else 'NOT separable'}"
        f" ({(acc - base)*100:+.1f}pp over baseline)")


# ────────────────────────────────────────────────────────────────────────────
# 7. Save report
# ────────────────────────────────────────────────────────────────────────────
OUT_MD.write_text("\n".join(report))
out(f"\n---\n\nReport: {OUT_MD}")
