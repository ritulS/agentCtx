#!/usr/bin/env python3
"""Build COVERAGE.csv — a sheet tracking every (model, primitive, budget,
depth) cell found in the canonical ICLR_results/swebench tree and annotating
its paper scope and completion status.

Sources of truth:
  - disk:  ICLR_results/swebench/<track>/<model>/<cell>/experiment_results.json
           (per-record condition, budget, compression_ratio, instance_id)
Scope rule (main model) comes from CLAUDE.md / project_runs_checklist.md.

Does not read or write COVERAGE_TB.csv — that sheet is built separately from
the Terminal-Bench result tree.

Usage:  python dashboard/build_coverage_sb.py
        # writes COVERAGE.csv at the repository root
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICLR_RESULTS = ROOT / "ICLR_results"
DEFAULT_OUT = ROOT / "COVERAGE.csv"

MAIN_MODEL = "Qwen3.5-35B-A3B"
INF = 999_999_999

# Expansion 1 (see exp_plans/SWE_EXPANSION.md): runs/task 2->3.
REQUIRED_RUNS_PER_TASK = 3

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

# Fixed CSV column order, matching the keys assembled per row in main().
COHORT_GROUPS = ["abl30", "p100"]
COVERAGE_FIELDNAMES = [
    "benchmark", "model", "primitive", "budget", "depth", "scope",
    "required_cohort", "status", "tasks_on_disk", "runs_on_disk",
    "runs_per_task_min", "cohort_covered", "rows_in_csv", "source_dirs", "notes",
] + [
    field
    for name in COHORT_GROUPS
    for field in (
        [f"tasks_covered_{name}"] + [f"runs_capped_{cap}_{name}" for cap in range(1, 6)]
    )
]


def model_for_dir(name: str) -> str:
    if name.startswith("devstral-2"):
        return "Devstral-Small-2-24B"
    if name.startswith("qwen25-coder-32b"):
        return "Qwen2.5-Coder-32B"
    if name.startswith("llama33-70b"):
        return "Llama-3.3-70B"
    return MAIN_MODEL


ICLR_MODEL_LABELS = {
    "qwen35b": MAIN_MODEL,
    "devstral24b": "Devstral-Small-2-24B",
    "glm47flash": "GLM-4.7-Flash",
}


def model_for_record(record: dict, source_name: str) -> str:
    """Prefer metadata, while retaining compatibility with older aggregates."""
    return (
        record.get("model")
        or record.get("agent_model")
        or model_for_dir(source_name)
    )


def load_records(path: Path) -> list[dict]:
    data = json.load(open(path))
    return data.get("results", []) if isinstance(data, dict) else data


def load_task_list(path: Path) -> set:
    data = json.load(open(path))
    if isinstance(data, dict):
        data = data.get("tasks", data.get("instances", []))
    return {t["instance_id"] if isinstance(t, dict) else t for t in data}


def budget_label(b) -> str:
    return "inf" if b == INF else f"{b // 1000}k"


def classify_cohort(tasks: set, abl30: set, p100: set) -> str:
    if tasks >= p100:
        return "P100"
    if tasks >= abl30:
        extra = len(tasks - abl30)
        return "ABL-30" if extra == 0 else f"ABL-30 (+{extra})"
    return f"partial ({len(tasks & abl30)}/30 ABL-30, {len(tasks)} total)"


def parse_args():
    parser = argparse.ArgumentParser(description="Build the SWE-Bench experiment coverage CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="output CSV path (default: COVERAGE.csv at the repository root)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    out = args.output if args.output.is_absolute() else ROOT / args.output
    abl30 = load_task_list(ROOT / "task_lists/ablation_30tasks.json")
    p100 = load_task_list(ROOT / "task_lists/p100_all_100_tasks.json")

    # ---- 1. scan disk -------------------------------------------------------
    # cell key: (benchmark, model, primitive, budget, depth) -> coverage data.
    # Some dirs are copies of other dirs' runs (see seed_depth_dirs.py) — dedupe
    # by (cell, instance_id, run_num) so copies don't inflate run counts.
    #
    # ICLR_results/ holds the canonical, deduped, run-complete copies built by
    # the archive scripts (see ICLR_CELL_MANIFEST.json in each cell). It is the
    # only result tree scanned here; raw data directories are intentionally
    # excluded from coverage.
    disk = defaultdict(lambda: {"tasks": set(), "runs": 0, "dirs": set(), "task_runs": Counter()})
    seen_runs = set()
    iclr_sources = [
        ("swebench", f"ICLR_results/{meta.parent.relative_to(ICLR_RESULTS)}", meta)
        for meta in ICLR_RESULTS.glob("swebench/*/*/*/experiment_results.json")
    ]
    for benchmark, source_name, meta in sorted(iclr_sources):
        records = load_records(meta)
        for r in records:
            cond = r.get("condition")
            prim = CONDITION_TO_PRIMITIVE.get(cond)
            if prim is None:
                continue
            budget = r.get("budget")
            depth = r.get("compression_ratio", 0.5) or 0.5
            model_key = meta.parents[1].name if ICLR_RESULTS in meta.parents else ""
            model = model_for_record(r, source_name)
            if model == MAIN_MODEL and model_key in ICLR_MODEL_LABELS:
                model = ICLR_MODEL_LABELS[model_key]
            cell_key = (benchmark, model, prim, budget, round(float(depth), 1))
            cell = disk[cell_key]
            iid = r.get("instance_id")
            dedup_key = cell_key + (iid, r.get("run_num"))
            if dedup_key in seen_runs:
                cell["dirs"].add(source_name)  # still note provenance, don't double count
                continue
            seen_runs.add(dedup_key)
            cell["tasks"].add(iid)
            cell["runs"] += 1
            cell["dirs"].add(source_name)
            cell["task_runs"][iid] += 1

    # ---- 2. enumerate the in-scope cells (main model) ------------------------
    expected = {}  # cell key -> required cohort
    for prim in DEPTH_TUNABLE:
        for b in BUDGETS:
            for d in DEPTH_GRID:
                expected[("swebench", MAIN_MODEL, prim, b, d)] = "P100" if b == 15_000 else "ABL-30"
    for prim in DEPTH_INVARIANT:
        for b in BUDGETS:
            expected[("swebench", MAIN_MODEL, prim, b, 0.5)] = "P100"
    for prim in ("FC", "OTRC"):
        expected[("swebench", MAIN_MODEL, prim, INF, 0.5)] = "P100"
    # Legacy model-expansion baselines that only used the ABL-30 cohort.
    for model in ("Qwen2.5-Coder-32B", "Llama-3.3-70B"):
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "ABL-30"

    # FOLLOWUP_EXPERIMENTS 2.a/2.b use P100. Calibration FC trajectories in
    # these canonical cells count as run_1 of the corresponding experiment.
    for model in ("Devstral-Small-2-24B", "GLM-4.7-Flash"):
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "P100"

    # Concrete model-expansion cells in FOLLOWUP_EXPERIMENTS.md. A/P/B are
    # the rounded P5/P15/P25 values of each model's P100 FC run_1 peak-context
    # distribution. The primary (P) arm uses P100; budget/depth ablations use
    # ABL-30.
    expansion_budgets = {
        "Devstral-Small-2-24B": (17_000, 21_000, 24_000),
        "GLM-4.7-Flash": (10_000, 13_000, 15_000),
    }
    for model, (a_budget, p_budget, b_budget) in expansion_budgets.items():
        for prim in DEPTH_TUNABLE:
            expected[("swebench", model, prim, p_budget, 0.5)] = "P100"
            for budget in (a_budget, p_budget, b_budget):
                for depth in (0.3, 0.7):
                    expected[("swebench", model, prim, budget, depth)] = "ABL-30"
            for budget in (a_budget, b_budget):
                expected[("swebench", model, prim, budget, 0.5)] = "ABL-30"
        for prim in DEPTH_INVARIANT:
            expected[("swebench", model, prim, p_budget, 0.5)] = "P100"
            for budget in (a_budget, b_budget):
                expected[("swebench", model, prim, budget, 0.5)] = "ABL-30"
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "P100"

    # ---- 3. merge into sheet rows --------------------------------------------
    # The coverage CSVs inventory data that actually exists.  ``expected``
    # only annotates the scope/status of observed cells; planned-but-unrun
    # follow-ups must not create rows of their own.
    all_keys = sorted(disk,
                      key=lambda k: (k[0], k[1] != MAIN_MODEL, k[1], k[2], k[3], k[4]))
    rows = []
    for key in all_keys:
        benchmark, model, prim, budget, depth = key
        d = disk.get(key)
        req = expected.get(key)
        covered = d["tasks"] if d else set()
        cohort = classify_cohort(covered, abl30, p100) if covered else ""

        runs_per_task_min = 0
        # Cohort-specific capped run counts let downstream consumers answer
        # questions such as "how many third runs are complete for ABL-30?"
        # exactly.  A proportional slice of a mixed P100 cell is incorrect
        # when only the ABL-30 tasks have received run_3.
        d_runs = d["task_runs"] if d else {}
        def capped_runs(tasks, cap):
            return sum(min(cap, d_runs.get(t, 0)) for t in tasks)

        cohort_counts = {}
        for cohort_name, cohort_tasks in (("abl30", abl30), ("p100", p100)):
            cohort_counts[f"tasks_covered_{cohort_name}"] = sum(
                d_runs.get(t, 0) > 0 for t in cohort_tasks
            )
            for cap in range(1, 6):
                cohort_counts[f"runs_capped_{cap}_{cohort_name}"] = capped_runs(
                    cohort_tasks, cap
                )
        if req is None:
            scope = "out-of-scope" if model == MAIN_MODEL else "model-expansion"
            status = "EXTRA" if model == MAIN_MODEL else "HAVE"
        else:
            scope = "in-scope"
            if not covered:
                status = "MISSING"
            else:
                have_cohort = (
                    cohort.startswith(req) or
                    (req == "ABL-30" and cohort.startswith("P100"))
                )
                if not have_cohort:
                    status = "PARTIAL"
                else:
                    required_tasks = p100 if req == "P100" else abl30
                    runs_per_task_min = min(
                        (d_runs.get(t, 0) for t in required_tasks),
                        default=0)
                    status = "COMPLETE" if runs_per_task_min >= REQUIRED_RUNS_PER_TASK else "PARTIAL"

        notes = []
        has_required_cohort = bool(req) and (
            cohort.startswith(req) or (req == "ABL-30" and cohort.startswith("P100"))
        )
        if status == "PARTIAL" and covered and has_required_cohort:
            notes.append(f"only {runs_per_task_min}/{REQUIRED_RUNS_PER_TASK} runs/task")

        rows.append({
            "benchmark": benchmark,
            "model": model,
            "primitive": prim,
            "budget": budget_label(budget),
            "depth": depth,
            "scope": scope,
            "required_cohort": req or "",
            "status": status,
            "tasks_on_disk": len(d["tasks"]) if d else 0,
            "runs_on_disk": d["runs"] if d else 0,
            "runs_per_task_min": runs_per_task_min,
            "cohort_covered": cohort,
            # Retained as a zero-valued compatibility column for dashboard and
            # any existing consumers of the coverage schema.
            "rows_in_csv": 0,
            "source_dirs": ";".join(sorted(d["dirs"])) if d else "",
            "notes": "; ".join(notes),
            **cohort_counts,
        })

    if not rows:
        raise SystemExit(
            f"No SWE-Bench experiment results found under {ICLR_RESULTS / 'swebench'}; "
            f"refusing to overwrite {out}"
        )

    def write_rows(path, output_rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COVERAGE_FIELDNAMES, lineterminator="\n")
            w.writeheader()
            w.writerows(output_rows)

    write_rows(out, rows)

    # ---- 4. console summary ---------------------------------------------------
    n = defaultdict(int)
    for r in rows:
        n[r["status"]] += 1
    def display_path(path):
        try:
            return path.relative_to(ROOT)
        except ValueError:
            return path

    print(f"Wrote {display_path(out)} — {len(rows)} SWE-Bench cells")
    for status in ("COMPLETE", "PARTIAL", "MISSING", "EXTRA", "HAVE"):
        if n[status]:
            print(f"  {status}: {n[status]}")
    problems = [r for r in rows
                if r["status"] in ("MISSING", "PARTIAL")
                or r["notes"]]
    if problems:
        print("\nAttention:")
        for r in problems:
            print(f"  [{r['status']:8s}] {r['benchmark']} / {r['model']} / {r['primitive']} / "
                  f"{r['budget']} / d={r['depth']}  {r['cohort_covered']}  {r['notes']}")


if __name__ == "__main__":
    main()
