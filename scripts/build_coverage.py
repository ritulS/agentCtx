#!/usr/bin/env python3
"""Build COVERAGE.csv — the single sheet tracking every (benchmark, model,
primitive, budget, depth) cell: which cells the paper scope requires, which we
have data for on disk, and which are ingested into the analysis CSVs.

Sources of truth:
  - disk:  ICLR_results/swebench/<track>/<model>/<cell>/experiment_results.json
           ICLR_results/terminalbench/<track>/[<namespace>/]<model>/<cell>/
             experiment_results.json
           data/swebench/ablations/<exp>/experiment_results.json (fallback)
           data/swebench/tbench/experiment_results.json (fallback)
           (per-record condition, budget, compression_ratio, instance_id)
  - CSVs:  Review1/Review1.csv (main model),
           Review1/Review1_qwen25-7b.csv, Review1/Review1_qwen3-30b-a3b-quant.csv

Scope rule (main model) comes from CLAUDE.md / project_runs_checklist.md.

Usage:  python scripts/build_coverage.py        # writes COVERAGE.csv at repo root
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABLATIONS = ROOT / "data/swebench/ablations"
TB_RESULTS = ROOT / "data/swebench/tbench/experiment_results.json"
ICLR_RESULTS = ROOT / "ICLR_results"
DEFAULT_OUT = ROOT / "COVERAGE.csv"

MAIN_MODEL = "Qwen3.5-35B-A3B"
INF = 999_999_999

# Expansion 1 (see exp_plans/SWE_EXPANSION.md): runs/task 2->3.
REQUIRED_RUNS_PER_TASK = 3
TB_REQUIRED_RUNS_PER_TASK = 5

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
    parser = argparse.ArgumentParser(description="Build the experiment coverage CSV")
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
    tb20 = load_task_list(ROOT / "task_lists/tbench_tasks.json")

    # ---- 1. scan disk -------------------------------------------------------
    # cell key: (benchmark, model, primitive, budget, depth) -> coverage data.
    # Some dirs are copies of other dirs' runs (see seed_depth_dirs.py) — dedupe
    # by (cell, instance_id, run_num) so copies don't inflate run counts.
    #
    # ICLR_results/ holds the canonical, deduped, run-complete copies built by
    # archive_and_organize_qwen35b_swebench.py (see ICLR_CELL_MANIFEST.json in
    # each cell). Scan those first so their rows win the dedup below; raw
    # ABLATIONS/tbench dirs are then only a fallback for cells not yet
    # archived (other models, pilots, depth points outside the 3-point grid).
    disk = defaultdict(lambda: {"tasks": set(), "runs": 0, "dirs": set(), "task_runs": Counter()})
    seen_runs = set()
    iclr_sources = [
        ("swebench", f"ICLR_results/{meta.parent.relative_to(ICLR_RESULTS)}", meta)
        for meta in ICLR_RESULTS.glob("swebench/*/*/*/experiment_results.json")
    ] + [
        ("terminal-bench", f"ICLR_results/{meta.parent.relative_to(ICLR_RESULTS)}", meta)
        # Terminal-Bench tracks may contain an additional result namespace,
        # e.g. main/p80_rootless/<model>/<cell>.  Match recursively so adding
        # such a namespace does not silently remove live runs from coverage.
        for meta in ICLR_RESULTS.glob("terminalbench/**/experiment_results.json")
    ]
    raw_sources = [
        ("swebench", p.parent.name, p)
        for p in ABLATIONS.glob("*/experiment_results.json")
    ]
    if TB_RESULTS.exists():
        raw_sources.append(("terminal-bench", "tbench", TB_RESULTS))
    disk_sources = sorted(iclr_sources) + sorted(raw_sources)

    for benchmark, source_name, meta in disk_sources:
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

    # ---- 2. scan CSVs --------------------------------------------------------
    csv_rows = defaultdict(int)    # same cell key -> ingested row count
    csv_tasks = defaultdict(set)   # same cell key -> tasks present in CSV
    csv_task_runs = defaultdict(Counter)   # same cell key -> {task: run count}

    def scan_csv(path: Path, model_fn, benchmark="swebench"):
        if not path.exists():
            return
        for row in csv.DictReader(open(path)):
            model = model_fn(row)
            key = (benchmark, model, row["primitive"], int(row["token_budget"]),
                   round(float(row.get("depth") or 0.5), 1))
            csv_rows[key] += 1
            csv_tasks[key].add(row["task_name"])
            csv_task_runs[key][row["task_name"]] += 1

    scan_csv(ROOT / "Review1/Review1.csv", lambda r: MAIN_MODEL)
    scan_csv(ROOT / "Review1/Review1_qwen25-7b.csv", lambda r: "Qwen2.5-7B")
    scan_csv(ROOT / "Review1/Review1_qwen3-30b-a3b-quant.csv",
             lambda r: "Qwen3-30B-A3B-2507/" + r["ablation"].removeprefix(QUANT_MODEL_PREFIX))

    # ---- 3. enumerate the in-scope cells (main model) ------------------------
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

    # Concrete Devstral cells in FOLLOWUP_EXPERIMENTS.md.  This makes the
    # follow-up plan part of the same inventory as completed data, instead of
    # showing only whichever archived cells happen to exist today.
    devstral = "Devstral-Small-2-24B"
    for prim in DEPTH_TUNABLE:
        expected[("swebench", devstral, prim, 15_000, 0.5)] = "P100"
        for b in BUDGETS:
            for d in DEPTH_GRID:
                expected.setdefault(("swebench", devstral, prim, b, d), "ABL-30")
    for prim in DEPTH_INVARIANT:
        expected[("swebench", devstral, prim, 15_000, 0.5)] = "P100"
        for b in (10_000, 20_000):
            expected[("swebench", devstral, prim, b, 0.5)] = "ABL-30"
    for prim in ("FC", "OTRC"):
        expected[("swebench", devstral, prim, INF, 0.5)] = "P100"

    # Concrete Terminal-Bench follow-up cells.  Primary depth/budget cells and
    # the unlimited baselines use all 80 tasks; the remaining grid uses the
    # frozen 20-task ablation cohort.
    for model in (MAIN_MODEL, "Devstral-Small-2-24B", "GLM-4.7-Flash"):
        for prim in DEPTH_TUNABLE:
            expected[("terminal-bench", model, prim, 15_000, 0.5)] = "TB-80"
        for prim in DEPTH_INVARIANT:
            expected[("terminal-bench", model, prim, 15_000, 0.5)] = "TB-80"
        for prim in ("FC", "OTRC"):
            expected[("terminal-bench", model, prim, INF, 0.5)] = "TB-80"
        for prim in DEPTH_TUNABLE:
            for b in (10_000, 20_000):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-20"
            for b in BUDGETS:
                for d in (0.3, 0.7):
                    expected[("terminal-bench", model, prim, b, d)] = "TB-20"
        for prim in DEPTH_INVARIANT:
            for b in (10_000, 20_000):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-20"

    # ---- 4. merge into sheet rows --------------------------------------------
    # COVERAGE.csv is an inventory of data that actually exists.  ``expected``
    # only annotates the scope/status of observed cells; planned-but-unrun
    # follow-ups must not create rows of their own.
    all_keys = sorted(set(disk) | set(csv_rows),
                      key=lambda k: (k[0], k[1] != MAIN_MODEL, k[1], k[2], k[3], k[4]))
    rows = []
    for key in all_keys:
        benchmark, model, prim, budget, depth = key
        d = disk.get(key)
        req = expected.get(key)
        n_csv = csv_rows.get(key, 0)
        required_runs = (TB_REQUIRED_RUNS_PER_TASK
                         if benchmark == "terminal-bench"
                         else REQUIRED_RUNS_PER_TASK)
        # coverage = union of what's on this disk and what's already ingested
        # (ABL-30 slices of some canonical cells live in source_runs/ and are
        # reachable only through Review1.csv's dedup ingest)
        covered = (d["tasks"] if d else set()) | csv_tasks.get(key, set())
        cohort = (f"TB-{len(covered)}" if benchmark == "terminal-bench" else
                  classify_cohort(covered, abl30, p100)) if covered else ""

        runs_per_task_min = 0
        # Cohort-specific capped run counts let downstream consumers answer
        # questions such as "how many third runs are complete for ABL-30?"
        # exactly.  A proportional slice of a mixed P100 cell is incorrect
        # when only the ABL-30 tasks have received run_3.
        d_runs = d["task_runs"] if d else {}
        c_runs = csv_task_runs.get(key, {})

        def capped_runs(tasks, cap):
            return sum(min(cap, max(d_runs.get(t, 0), c_runs.get(t, 0))) for t in tasks)

        cohort_counts = {}
        for cohort_name, cohort_tasks in (
            ("abl30", abl30), ("p100", p100), ("tb20", tb20)
        ):
            cohort_counts[f"tasks_covered_{cohort_name}"] = sum(
                max(d_runs.get(t, 0), c_runs.get(t, 0)) > 0 for t in cohort_tasks
            )
            for cap in range(1, 6):
                cohort_counts[f"runs_capped_{cap}_{cohort_name}"] = capped_runs(
                    cohort_tasks, cap
                )
        # TB:P-80 progress can include provisional/rootless subsets.  Counting
        # every observed task directly avoids proportionally scaling a 42-task
        # subset up to 80 tasks in the dashboard.
        all_observed_tasks = set(d_runs) | set(c_runs)
        cohort_counts["tasks_covered_all"] = len(all_observed_tasks)
        for cap in range(1, 6):
            cohort_counts[f"runs_capped_{cap}_all"] = capped_runs(
                all_observed_tasks, cap
            )

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
                have_cohort = (
                    covered >= tb20 if req == "TB-20" else
                    len(covered) >= 80 if req == "TB-80" else
                    cohort.startswith(req) or
                    (req == "ABL-30" and cohort.startswith("P100"))
                )
                if not have_cohort:
                    status = "PARTIAL"
                else:
                    required_tasks = (tb20 if req == "TB-20" else
                                      covered if req == "TB-80" else
                                      p100 if req == "P100" else abl30)
                    runs_per_task_min = min(
                        (max(d_runs.get(t, 0), c_runs.get(t, 0)) for t in required_tasks),
                        default=0)
                    status = "COMPLETE" if runs_per_task_min >= required_runs else "PARTIAL"

        notes = []
        if d and benchmark == "swebench" and model == MAIN_MODEL and n_csv == 0 and req is not None:
            notes.append("on disk, NOT in Review1.csv")
        if d is None and n_csv:
            notes.append("csv only (raw data on Albus)")
        has_required_cohort = (
            covered >= tb20 if req == "TB-20" else
            len(covered) >= 80 if req == "TB-80" else
            bool(req) and (cohort.startswith(req) or
                           (req == "ABL-30" and cohort.startswith("P100")))
        )
        if status == "PARTIAL" and covered and has_required_cohort:
            notes.append(f"only {runs_per_task_min}/{required_runs} runs/task")

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
            "rows_in_csv": n_csv,
            "source_dirs": ";".join(sorted(d["dirs"])) if d else "",
            "notes": "; ".join(notes),
            **cohort_counts,
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # ---- 5. console summary ---------------------------------------------------
    n = defaultdict(int)
    for r in rows:
        n[r["status"]] += 1
    try:
        display_out = out.relative_to(ROOT)
    except ValueError:
        display_out = out
    print(f"Wrote {display_out} — {len(rows)} cells")
    for status in ("COMPLETE", "PARTIAL", "MISSING", "EXTRA", "HAVE", "HAVE (csv-only)"):
        if n[status]:
            print(f"  {status}: {n[status]}")
    problems = [r for r in rows
                if r["status"] in ("MISSING", "PARTIAL")
                or (r["notes"] and r["status"] != "HAVE (csv-only)")]
    if problems:
        print("\nAttention:")
        for r in problems:
            print(f"  [{r['status']:8s}] {r['benchmark']} / {r['model']} / {r['primitive']} / "
                  f"{r['budget']} / d={r['depth']}  {r['cohort_covered']}  {r['notes']}")


if __name__ == "__main__":
    main()
