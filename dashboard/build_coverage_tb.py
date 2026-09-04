#!/usr/bin/env python3
"""Build COVERAGE_TB.csv for Terminal-Bench experiment coverage.

Sources of truth:
  - disk:  ICLR_results/terminalbench/<track>/[<namespace>/]<model>/<cell>/
             experiment_results.json
           (per-record condition, budget, compression_ratio, instance_id)
Scope rule (main model) comes from CLAUDE.md / project_runs_checklist.md.

Does not read or write COVERAGE.csv.

Usage:  python dashboard/build_coverage_tb.py
        # writes COVERAGE_TB.csv at the repository root
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICLR_RESULTS = ROOT / "ICLR_results"
DEFAULT_TB_OUT = ROOT / "COVERAGE_TB.csv"
TB_HARBOR_JOBS = ROOT / "logs" / "harbor_jobs" / "terminalbench"

MAIN_MODEL = "Qwen3.5-35B-A3B"
INF = 999_999_999

TB_REQUIRED_RUNS_PER_TASK = 3

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

COHORT_GROUPS = ["tb15", "tb20", "tb40", "all"]
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


def terminalbench_harbor_fallbacks() -> list[tuple[str, str, dict]]:
    """Return live Harbor runs that belong to canonical Terminal-Bench cells.

    ``run_info.json`` is written before a cell starts, so it provides the
    budget/condition metadata missing from Harbor's per-trial result files.
    Job timestamps bound each launch and prevent an older launch of the same
    model/condition from being mixed in. Canonical records are processed first
    and therefore win later through the normal deduplication key.
    """
    launches = []
    for info_path in ICLR_RESULTS.glob("terminalbench/**/run_info.json"):
        try:
            info = json.loads(info_path.read_text())
            conditions = info.get("conditions", [])
            if len(conditions) != 1:
                continue
            started = datetime.strptime(info["started"], "%Y-%m-%d %H:%M:%S").timestamp()
            budget = int(info["budget_tokens"])
            runs_per_task = int(info.get("runs_per_task", 1))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue

        cell_name = info_path.parent.name
        depth_tag = cell_name.split("__", 1)[0]
        depth = {"d03": 0.3, "d05": 0.5, "d07": 0.7, "di": 0.5}.get(depth_tag)
        if depth is None:
            continue
        model_key = info_path.parent.parent.name
        launches.append({
            "started": started,
            "end": None,
            "model_key": model_key,
            "model": ICLR_MODEL_LABELS.get(model_key, model_key),
            "condition": conditions[0],
            "budget": budget,
            "depth": depth,
            "runs_per_task": runs_per_task,
            "source": f"logs/harbor_jobs/terminalbench/{model_key}",
        })

    groups = defaultdict(list)
    for launch in launches:
        groups[(launch["model_key"], launch["condition"])].append(launch)
    for group in groups.values():
        group.sort(key=lambda launch: launch["started"])
        for current, following in zip(group, group[1:]):
            current["end"] = following["started"]

    records = []
    for launch in launches:
        jobs_dir = TB_HARBOR_JOBS / launch["model_key"]
        for run_num in range(1, launch["runs_per_task"] + 1):
            pattern = f"{launch['model_key']}-{launch['condition']}-r{run_num}-*"
            for job_dir in jobs_dir.glob(pattern):
                match = re.search(r"-(\d{13})$", job_dir.name)
                if not match:
                    continue
                job_started = int(match.group(1)) / 1000
                if job_started < launch["started"]:
                    continue
                if launch["end"] is not None and job_started >= launch["end"]:
                    continue
                for result_path in job_dir.glob("*/result.json"):
                    try:
                        result = json.loads(result_path.read_text())
                    except (OSError, json.JSONDecodeError):
                        # A watcher may race a result file being replaced.
                        continue
                    instance_id = result.get("task_name")
                    if not instance_id:
                        continue
                    records.append((
                        "terminal-bench",
                        launch["source"],
                        {
                            "condition": launch["condition"],
                            "budget": launch["budget"],
                            "compression_ratio": launch["depth"],
                            "model": launch["model"],
                            "instance_id": instance_id,
                            "run_num": run_num,
                        },
                    ))
    return records


def budget_label(b) -> str:
    return "inf" if b == INF else f"{b // 1000}k"


def parse_args():
    parser = argparse.ArgumentParser(description="Build the Terminal-Bench experiment coverage CSV")
    parser.add_argument(
        "--tb-output",
        type=Path,
        default=DEFAULT_TB_OUT,
        help="Terminal-Bench output CSV path (default: COVERAGE_TB.csv at the repository root)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    tb_out = args.tb_output if args.tb_output.is_absolute() else ROOT / args.tb_output
    tb15 = load_task_list(ROOT / "task_lists/tbench_abl15.json")
    tb20 = load_task_list(ROOT / "task_lists/tbench_tasks.json")
    tb40 = load_task_list(ROOT / "task_lists/tbench_p40.json")

    # ---- 1. scan disk -------------------------------------------------------
    # cell key: (benchmark, model, primitive, budget, depth) -> coverage data.
    # Some dirs are copies of other dirs' runs (see seed_depth_dirs.py) — dedupe
    # by (cell, instance_id, run_num) so copies don't inflate run counts.
    #
    # ICLR_results/terminalbench holds the canonical, deduped copies built by
    # the archive scripts. Live Harbor results are added afterward only as a
    # fallback for (cell, task, run_num) records not present in canonical data.
    disk = defaultdict(lambda: {"tasks": set(), "runs": 0, "dirs": set(), "task_runs": Counter()})
    seen_runs = set()
    iclr_sources = [
        ("terminal-bench", f"ICLR_results/{meta.parent.relative_to(ICLR_RESULTS)}", meta)
        # Terminal-Bench tracks may contain an additional result namespace,
        # e.g. main/p80_rootless/<model>/<cell>.  Match recursively so adding
        # such a namespace does not silently remove live runs from coverage.
        for meta in ICLR_RESULTS.glob("terminalbench/**/experiment_results.json")
    ]
    sources = [
        (benchmark, source_name, record, meta)
        for benchmark, source_name, meta in sorted(iclr_sources)
        for record in load_records(meta)
    ]
    sources += [
        (benchmark, source_name, record, None)
        for benchmark, source_name, record in terminalbench_harbor_fallbacks()
    ]
    for benchmark, source_name, r, meta in sources:
        cond = r.get("condition")
        prim = CONDITION_TO_PRIMITIVE.get(cond)
        if prim is None:
            continue
        budget = r.get("budget")
        depth = r.get("compression_ratio", 0.5) or 0.5
        model_key = (
            meta.parents[1].name
            if meta is not None and ICLR_RESULTS in meta.parents
            else ""
        )
        model = model_for_record(r, source_name)
        model = ICLR_MODEL_LABELS.get(model, model)
        if model == MAIN_MODEL and model_key in ICLR_MODEL_LABELS:
            model = ICLR_MODEL_LABELS[model_key]
        cell_key = (benchmark, model, prim, budget, round(float(depth), 1))
        iid = r.get("instance_id")
        dedup_key = cell_key + (iid, r.get("run_num"))
        if dedup_key in seen_runs:
            continue
        seen_runs.add(dedup_key)
        cell = disk[cell_key]
        cell["tasks"].add(iid)
        cell["runs"] += 1
        cell["dirs"].add(source_name)
        cell["task_runs"][iid] += 1

    # ---- 2. enumerate the in-scope cells (main model) ------------------------
    expected = {}  # cell key -> required cohort
    # FOLLOWUP_EXPERIMENTS 3.a/3.b: main cells use the frozen P-40 cohort and
    # primary budget; ablation cells use the frozen P-15 cohort and A/P/B
    # budgets calibrated separately for each model.
    tb_budgets = {
        MAIN_MODEL: (2_000, 3_000, 4_000),
        "Devstral-Small-2-24B": (3_000, 4_000, 7_000),
        "GLM-4.7-Flash": (2_000, 3_000, 5_000),
    }
    for model, (a_budget, primary_budget, b_budget) in tb_budgets.items():
        for prim in DEPTH_TUNABLE:
            expected[("terminal-bench", model, prim, primary_budget, 0.5)] = "TB-40"
        for prim in DEPTH_INVARIANT:
            expected[("terminal-bench", model, prim, primary_budget, 0.5)] = "TB-40"
        for prim in ("FC", "OTRC"):
            expected[("terminal-bench", model, prim, INF, 0.5)] = "TB-40"
        for prim in DEPTH_TUNABLE:
            for b in (a_budget, b_budget):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-15"
            for b in (a_budget, primary_budget, b_budget):
                for d in (0.3, 0.7):
                    expected[("terminal-bench", model, prim, b, d)] = "TB-15"
        for prim in DEPTH_INVARIANT:
            for b in (a_budget, b_budget):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-15"

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
        cohort = f"TB-{len(covered)}" if covered else ""

        runs_per_task_min = 0
        # Cohort-specific capped run counts let downstream consumers answer
        # questions such as "how many third runs are complete for ABL-30?"
        # exactly.  A proportional slice of a mixed P100 cell is incorrect
        # when only the ABL-30 tasks have received run_3.
        d_runs = d["task_runs"] if d else {}
        def capped_runs(tasks, cap):
            return sum(min(cap, d_runs.get(t, 0)) for t in tasks)

        cohort_counts = {}
        for cohort_name, cohort_tasks in (
            ("tb15", tb15), ("tb20", tb20), ("tb40", tb40)
        ):
            cohort_counts[f"tasks_covered_{cohort_name}"] = sum(
                d_runs.get(t, 0) > 0 for t in cohort_tasks
            )
            for cap in range(1, 6):
                cohort_counts[f"runs_capped_{cap}_{cohort_name}"] = capped_runs(
                    cohort_tasks, cap
                )
        # Retain an all-observed count for legacy P-80/rootless views.
        all_observed_tasks = set(d_runs)
        cohort_counts["tasks_covered_all"] = len(all_observed_tasks)
        for cap in range(1, 6):
            cohort_counts[f"runs_capped_{cap}_all"] = capped_runs(
                all_observed_tasks, cap
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
                    covered >= tb15 if req == "TB-15" else
                    covered >= tb40 if req == "TB-40" else False
                )
                if not have_cohort:
                    status = "PARTIAL"
                else:
                    required_tasks = (tb15 if req == "TB-15" else
                                      tb40)
                    runs_per_task_min = min(
                        (d_runs.get(t, 0) for t in required_tasks),
                        default=0)
                    status = "COMPLETE" if runs_per_task_min >= TB_REQUIRED_RUNS_PER_TASK else "PARTIAL"

        notes = []
        has_required_cohort = (
            covered >= tb15 if req == "TB-15" else
            covered >= tb40 if req == "TB-40" else False
        )
        if status == "PARTIAL" and covered and has_required_cohort:
            notes.append(f"only {runs_per_task_min}/{TB_REQUIRED_RUNS_PER_TASK} runs/task")

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
            f"No Terminal-Bench experiment results found under "
            f"{ICLR_RESULTS / 'terminalbench'}; refusing to overwrite {tb_out}"
        )

    def write_rows(path, output_rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COVERAGE_FIELDNAMES, lineterminator="\n")
            w.writeheader()
            w.writerows(output_rows)

    write_rows(tb_out, rows)

    # ---- 4. console summary ---------------------------------------------------
    n = defaultdict(int)
    for r in rows:
        n[r["status"]] += 1
    def display_path(path):
        try:
            return path.relative_to(ROOT)
        except ValueError:
            return path

    print(f"Wrote {display_path(tb_out)} — {len(rows)} Terminal-Bench cells")
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
