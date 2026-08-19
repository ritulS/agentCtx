#!/usr/bin/env python3
"""Build COVERAGE.csv — the single sheet tracking every (model, primitive,
budget, depth) cell: which cells the paper scope requires, which we have data
for on disk, and which are ingested into the analysis CSVs.

Sources of truth:
  - disk:  data/swebench/ablations/<exp>/experiment_results.json
           (per-record condition, budget, compression_ratio, instance_id)
  - CSVs:  Review1/Review1.csv (main model),
           Review1/Review1_qwen25-7b.csv, Review1/Review1_qwen3-30b-a3b-quant.csv

Scope rule (main model) comes from CLAUDE.md / project_runs_checklist.md.

Usage:  python scripts/build_coverage.py        # writes COVERAGE.csv at repo root
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABLATIONS = ROOT / "data/swebench/ablations"
OUT = ROOT / "COVERAGE.csv"

MAIN_MODEL = "Qwen3.5-35B-A3B"
INF = 999_999_999

CONDITION_TO_PRIMITIVE = {
    "truncation": "TR",
    "summarization": "SU-full",
    "summarization-partial": "SU-partial",
    "structured-summarize": "SS",
    "structured-summarize-partial": "SS-partial",
    "tool-result-clear": "TRC",
    "trc-su": "TRC+SU",
    "trc-ss": "TRC+SS",
    "otrc-tr": "OTRC+TR",
    "otrc-su-partial": "OTRC+SU-partial",
    "otrc-ss-partial": "OTRC+SS-partial",
    "full-context": "FC",
    "online-trc": "OTRC",
    "staggered-alternate": "STAG-alt",
    "staggered-random": "STAG-rand",
}

DEPTH_TUNABLE = ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]
DEPTH_INVARIANT = ["TRC", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]
BUDGETS = [10_000, 15_000, 20_000]
DEPTH_GRID = [0.3, 0.5, 0.7]

QUANT_MODEL_PREFIX = "qwen3-30b-a3b-"  # precision sweep base model


def model_for_dir(name: str) -> str:
    if name.startswith("devstral-2"):
        return "Devstral-Small-2-24B"
    if name.startswith("qwen25-coder-32b"):
        return "Qwen2.5-Coder-32B"
    if name.startswith("llama33-70b"):
        return "Llama-3.3-70B"
    return MAIN_MODEL


def load_task_list(path: Path) -> set:
    return {t["instance_id"] if isinstance(t, dict) else t for t in json.load(open(path))}


def budget_label(b) -> str:
    return "inf" if b == INF else f"{b // 1000}k"


def classify_cohort(tasks: set, abl30: set, p100: set) -> str:
    if tasks >= p100:
        return "P100"
    if tasks >= abl30:
        extra = len(tasks - abl30)
        return "ABL-30" if extra == 0 else f"ABL-30 (+{extra})"
    return f"partial ({len(tasks & abl30)}/30 ABL-30, {len(tasks)} total)"


def main():
    abl30 = load_task_list(ABLATIONS / "tasks.json")
    p100 = load_task_list(ROOT / "task_lists/p100_all_100_tasks.json")

    # ---- 1. scan disk -------------------------------------------------------
    # cell key: (model, primitive, budget, depth) -> {tasks, runs, dirs}
    disk = defaultdict(lambda: {"tasks": set(), "runs": 0, "dirs": set()})
    for exp in sorted(ABLATIONS.iterdir()):
        meta = exp / "experiment_results.json"
        if not exp.is_dir() or not meta.exists():
            continue
        model = model_for_dir(exp.name)
        records = json.load(open(meta))
        if isinstance(records, dict):
            records = records.get("results", [])
        for r in records:
            cond = r.get("condition")
            prim = CONDITION_TO_PRIMITIVE.get(cond)
            if prim is None:
                continue
            budget = r.get("budget")
            depth = r.get("compression_ratio", 0.5) or 0.5
            cell = disk[(model, prim, budget, round(float(depth), 1))]
            cell["tasks"].add(r.get("instance_id"))
            cell["runs"] += 1
            cell["dirs"].add(exp.name)

    # ---- 2. scan CSVs --------------------------------------------------------
    csv_rows = defaultdict(int)    # same cell key -> ingested row count
    csv_tasks = defaultdict(set)   # same cell key -> tasks present in CSV

    def scan_csv(path: Path, model_fn):
        if not path.exists():
            return
        for row in csv.DictReader(open(path)):
            model = model_fn(row)
            key = (model, row["primitive"], int(row["token_budget"]),
                   round(float(row.get("depth") or 0.5), 1))
            csv_rows[key] += 1
            csv_tasks[key].add(row["task_name"])

    scan_csv(ROOT / "Review1/Review1.csv", lambda r: MAIN_MODEL)
    scan_csv(ROOT / "Review1/Review1_qwen25-7b.csv", lambda r: "Qwen2.5-7B")
    scan_csv(ROOT / "Review1/Review1_qwen3-30b-a3b-quant.csv",
             lambda r: "Qwen3-30B-A3B-2507/" + r["ablation"].removeprefix(QUANT_MODEL_PREFIX))

    # ---- 3. enumerate the in-scope cells (main model) ------------------------
    expected = {}  # cell key -> required cohort
    for prim in DEPTH_TUNABLE:
        for b in BUDGETS:
            for d in DEPTH_GRID:
                expected[(MAIN_MODEL, prim, b, d)] = "P100" if b == 15_000 else "ABL-30"
    for prim in DEPTH_INVARIANT:
        for b in BUDGETS:
            expected[(MAIN_MODEL, prim, b, 0.5)] = "P100"
    for prim in ("FC", "OTRC"):
        expected[(MAIN_MODEL, prim, INF, 0.5)] = "P100"
    # known model-expansion requirements (∞ baselines; see HANDOFF_COHERENCE.md)
    for model in ("Devstral-Small-2-24B", "Qwen2.5-Coder-32B", "Llama-3.3-70B"):
        for prim in ("FC", "OTRC"):
            expected[(model, prim, INF, 0.5)] = "ABL-30"

    # ---- 4. merge into sheet rows --------------------------------------------
    all_keys = sorted(set(disk) | set(expected) | set(csv_rows),
                      key=lambda k: (k[0] != MAIN_MODEL, k[0], k[1], k[2], k[3]))
    rows = []
    for key in all_keys:
        model, prim, budget, depth = key
        d = disk.get(key)
        req = expected.get(key)
        n_csv = csv_rows.get(key, 0)
        # coverage = union of what's on this disk and what's already ingested
        # (ABL-30 slices of some canonical cells live in source_runs/ and are
        # reachable only through Review1.csv's dedup ingest)
        covered = (d["tasks"] if d else set()) | csv_tasks.get(key, set())
        cohort = classify_cohort(covered, abl30, p100) if covered else ""

        if req is None:
            scope = "out-of-scope" if model == MAIN_MODEL else "model-expansion"
            status = "EXTRA" if model == MAIN_MODEL else "HAVE"
            if d is None and n_csv:
                status = "HAVE (csv-only)"
        else:
            scope = "in-scope"
            if not covered:
                status = "MISSING"
            else:
                have = cohort.startswith(req) or (req == "ABL-30" and cohort.startswith("P100"))
                status = "COMPLETE" if have else "PARTIAL"

        notes = []
        if d and model == MAIN_MODEL and n_csv == 0 and req is not None:
            notes.append("on disk, NOT in Review1.csv")
        if d is None and n_csv:
            notes.append("csv only (raw data on Albus)")

        rows.append({
            "model": model,
            "primitive": prim,
            "budget": budget_label(budget),
            "depth": depth,
            "scope": scope,
            "required_cohort": req or "",
            "status": status,
            "tasks_on_disk": len(d["tasks"]) if d else 0,
            "runs_on_disk": d["runs"] if d else 0,
            "cohort_covered": cohort,
            "rows_in_csv": n_csv,
            "source_dirs": ";".join(sorted(d["dirs"])) if d else "",
            "notes": "; ".join(notes),
        })

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 5. console summary ---------------------------------------------------
    n = defaultdict(int)
    for r in rows:
        n[r["status"]] += 1
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(rows)} cells")
    for status in ("COMPLETE", "PARTIAL", "MISSING", "EXTRA", "HAVE", "HAVE (csv-only)"):
        if n[status]:
            print(f"  {status}: {n[status]}")
    problems = [r for r in rows
                if r["status"] in ("MISSING", "PARTIAL")
                or (r["notes"] and r["status"] != "HAVE (csv-only)")]
    if problems:
        print("\nAttention:")
        for r in problems:
            print(f"  [{r['status']:8s}] {r['model']} / {r['primitive']} / "
                  f"{r['budget']} / d={r['depth']}  {r['cohort_covered']}  {r['notes']}")


if __name__ == "__main__":
    main()
