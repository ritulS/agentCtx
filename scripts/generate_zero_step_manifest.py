"""Generate manifest of all zero-step runs in Review1.csv for the docker cold-pull recovery."""
import pandas as pd, json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/rs67788/projects/agentCtx")
df = pd.read_csv(ROOT / "Review1/Review1.csv")
zs = df[df.step_count == 0].copy()

PRIMITIVE_TO_CONDITION = {
    "TR":              "truncation",
    "SU-full":         "summarization",
    "SU-partial":      "summarization-partial",
    "SS":              "structured-summarize",
    "SS-partial":      "structured-summarize-partial",
    "TRC":             "tool-result-clear",
    "TRC+SU":          "trc-su",
    "TRC+SS":          "trc-ss",
    "OTRC+TR":         "otrc-tr",
    "OTRC+SS-partial": "otrc-ss-partial",
    "OTRC+SU-partial": "otrc-su-partial",
    "FC":              "full-context",
    "OTRC":            "online-trc",
}

# Map (condition, budget) → ablation dir name (verified from prior P100 work)
def ablation_for(condition: str, budget: int) -> str:
    if budget >= 999_999_998 or condition in ("full-context", "online-trc"):
        return "p100-inf"
    if condition in ("truncation", "summarization", "summarization-partial",
                     "structured-summarize", "structured-summarize-partial"):
        return f"p100-singles-{budget}"
    if condition in ("tool-result-clear", "trc-su", "trc-ss"):
        return f"p100-trc-{budget}"
    if condition in ("otrc-tr", "otrc-su-partial", "otrc-ss-partial"):
        return f"p100-otrc-{budget}"
    raise ValueError(f"Unmapped condition {condition}")

manifest = []
for _, row in zs.iterrows():
    prim = row["primitive"]
    cond = PRIMITIVE_TO_CONDITION.get(prim)
    if cond is None:
        print(f"WARN: unmapped primitive {prim!r}")
        continue
    budget = int(row["token_budget"])
    manifest.append({
        "task_name":  row["task_name"],
        "primitive":  prim,
        "condition":  cond,
        "token_budget": budget,
        "run_num":    int(row["run_num"]),
        "repo":       row["repo"],
        "ablation":   ablation_for(cond, budget),
    })

(ROOT / "scripts/zero_step_manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"Manifest: {len(manifest)} runs")

unique_tasks = sorted({r["task_name"] for r in manifest})
(ROOT / "scripts/zero_step_images.txt").write_text("\n".join(unique_tasks) + "\n")
print(f"Unique tasks: {len(unique_tasks)}")

# Per-cell breakdown
by_cell = defaultdict(list)
for r in manifest:
    by_cell[(r["ablation"], r["condition"], r["token_budget"])].append(r)
print("\nPer-cell counts:")
for (abl, cond, b), rs in sorted(by_cell.items()):
    print(f"  {abl:24s} {cond:32s} budget={b}  n={len(rs)}")
