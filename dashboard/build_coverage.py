#!/usr/bin/env python3
"""Build COVERAGE.csv and COVERAGE_TB.csv — sheets tracking every (model,
primitive, budget, depth) cell found in the canonical ICLR_results tree and
annotating its paper scope and completion status.

Sources of truth:
  - disk:  ICLR_results/swebench/<track>/<model>/<cell>/experiment_results.json
           ICLR_results/terminalbench/<track>/[<namespace>/]<model>/<cell>/
             experiment_results.json
           (per-record condition, budget, compression_ratio, instance_id)
           <model> may be <agent>-sum-<summarizer> (track model_ablation): those
           runs become separate cells with a non-empty ``summarizer`` column.
           Runs below the prefix_cache_ablation track become separate cells
           with a non-empty ``prefix_cache`` column (ON / OFF).
Scope rule (main model) comes from CLAUDE.md / project_runs_checklist.md.

Usage:  python dashboard/build_coverage.py
        # writes COVERAGE.csv and COVERAGE_TB.csv at the repository root
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICLR_RESULTS = ROOT / "ICLR_results"
DEFAULT_OUT = ROOT / "COVERAGE.csv"
DEFAULT_TB_OUT = ROOT / "COVERAGE_TB.csv"

MAIN_MODEL = "Qwen3.5-35B-A3B"
INF = 999_999_999

# Expansion 1 (see exp_plans/SWE_EXPANSION.md): runs/task 2->3.
REQUIRED_RUNS_PER_TASK = 3
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
BUDGETS = [10_000, 15_000, 20_000]
DEPTH_GRID = [0.3, 0.5, 0.7]

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

# Summarizer ablation (FOLLOWUP_EXPERIMENTS.md §4): result model directories
# are named <agent>-sum-<summarizer>, e.g.
# ICLR_results/swebench/model_ablation/qwen35b-sum-qwen35-9b/<cell>.
# Such runs form their own cells, keyed additionally by the summarizer label;
# ordinary cells (the agent summarizes for itself) carry an empty summarizer.
SUMMARIZER_SEPARATOR = "-sum-"
SUMMARIZER_LABELS = {
    "qwen35-9b": "Qwen3.5-9B",
    "gemma4-12b": "Gemma-4-12B",
}
# Throwaway smoke-test directories (…-smoke) are never counted.
SMOKE_SUFFIX = "-smoke"

# Prefix-cache ablation (dashboard Priority 5): every run below
# ICLR_results/<benchmark>/prefix_cache_ablation/ was served with the vLLM
# prefix-caching setting flipped relative to that benchmark's production runs.
# Production SWE-Bench Qwen runs had it off (the vLLM default for the hybrid
# Qwen3.5 model, see ICLR.md) and production Terminal-Bench runs had it on, so
# the ablation is ON for SWE-Bench (scripts/run_qwen_swe_prefix_cache_ablation.sh)
# and OFF for Terminal-Bench.  Such runs form their own cells, keyed
# additionally by this label; every other cell carries an empty prefix_cache.
PREFIX_CACHE_TRACK = "prefix_cache_ablation"
PREFIX_CACHE_ABLATION = {"swebench": "ON", "terminal-bench": "OFF"}
# Model directories of that track name the serving condition
# (qwen35b-prefixcache / qwen35b-noprefixcache); the agent is the part before it.
PREFIX_CACHE_DIR_SUFFIXES = ("-noprefixcache", "-prefixcache")
# Finite budget of the tracked cells (dashboard 5.a / 5.b): the main model's
# primary budget on each benchmark.
PREFIX_CACHE_BUDGETS = {"swebench": 15_000, "terminal-bench": 3_000}


def split_model_key(model_key: str) -> tuple[str, str]:
    """Return (agent_key, summarizer_label) for a result model directory name."""
    agent_key, separator, summarizer_key = model_key.partition(SUMMARIZER_SEPARATOR)
    if not separator:
        return model_key, ""
    return agent_key, SUMMARIZER_LABELS.get(summarizer_key, summarizer_key)


def prefix_cache_for(benchmark: str, track: str) -> str:
    """Return the prefix_cache label ("" outside the prefix-cache ablation track)."""
    return PREFIX_CACHE_ABLATION[benchmark] if track == PREFIX_CACHE_TRACK else ""


def strip_prefix_cache_suffix(model_key: str) -> str:
    """qwen35b-prefixcache -> qwen35b, so the agent maps to its usual label."""
    for suffix in PREFIX_CACHE_DIR_SUFFIXES:
        if model_key.endswith(suffix):
            return model_key[: -len(suffix)]
    return model_key


def model_for_record(record: dict, source_name: str) -> str:
    """Prefer metadata, while retaining compatibility with older aggregates."""
    return (
        record.get("model")
        or record.get("agent_model")
        or model_for_dir(source_name)
    )


def load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return data.get("results", []) if isinstance(data, dict) else data


def load_task_list(path: Path) -> set:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get("tasks", data.get("instances", []))
    return {t["instance_id"] if isinstance(t, dict) else t for t in data}


def budget_label(b) -> str:
    return "inf" if b == INF else f"{b // 1000}k"


def classify_cohort(tasks: set, abl25: set, p100: set) -> str:
    if tasks >= p100:
        return "P100"
    if tasks >= abl25:
        extra = len(tasks - abl25)
        return "ABL-25" if extra == 0 else f"ABL-25 (+{extra})"
    return f"partial ({len(tasks & abl25)}/25 ABL-25, {len(tasks)} total)"


def parse_args():
    parser = argparse.ArgumentParser(description="Build the experiment coverage CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="output CSV path (default: COVERAGE.csv at the repository root)",
    )
    parser.add_argument(
        "--tb-output",
        type=Path,
        default=DEFAULT_TB_OUT,
        help="Terminal-Bench output CSV path (default: COVERAGE_TB.csv at the repository root)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    out = args.output if args.output.is_absolute() else ROOT / args.output
    tb_out = args.tb_output if args.tb_output.is_absolute() else ROOT / args.tb_output
    abl25 = load_task_list(ROOT / "task_lists/ablation_25tasks.json")
    p100 = load_task_list(ROOT / "task_lists/p100_all_100_tasks.json")
    tb20 = load_task_list(ROOT / "task_lists/tbench_tasks.json")

    # ---- 1. scan disk -------------------------------------------------------
    # cell key: (benchmark, model, summarizer, prefix_cache, primitive, budget,
    # depth) -> coverage data.  summarizer is "" unless the model dir is
    # <agent>-sum-<summarizer> (summarizer ablation); prefix_cache is "" unless
    # the run lives below the prefix_cache_ablation track.
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
    ] + [
        ("terminal-bench", f"ICLR_results/{meta.parent.relative_to(ICLR_RESULTS)}", meta)
        # Terminal-Bench tracks may contain an additional result namespace,
        # e.g. main/p80_rootless/<model>/<cell>.  Match recursively so adding
        # such a namespace does not silently remove live runs from coverage.
        for meta in ICLR_RESULTS.glob("terminalbench/**/experiment_results.json")
    ]
    for benchmark, source_name, meta in sorted(iclr_sources):
        model_key = meta.parents[1].name if ICLR_RESULTS in meta.parents else ""
        if model_key.endswith(SMOKE_SUFFIX):
            continue
        agent_key, summarizer = split_model_key(model_key)
        # <benchmark dir>/<track>/...: the track is the first component.
        track = meta.relative_to(ICLR_RESULTS).parts[1]
        prefix_cache = prefix_cache_for(benchmark, track)
        if prefix_cache:
            agent_key = strip_prefix_cache_suffix(agent_key)
        records = load_records(meta)
        for r in records:
            cond = r.get("condition")
            prim = CONDITION_TO_PRIMITIVE.get(cond)
            if prim is None:
                continue
            budget = r.get("budget")
            depth = r.get("compression_ratio", 0.5) or 0.5
            model = model_for_record(r, source_name)
            if model == MAIN_MODEL and agent_key in ICLR_MODEL_LABELS:
                model = ICLR_MODEL_LABELS[agent_key]
            cell_key = (benchmark, model, summarizer, prefix_cache, prim, budget,
                        round(float(depth), 1))
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
    # Evaluate legacy model-expansion baselines on the current ablation subset.
    for model in ("Qwen2.5-Coder-32B", "Llama-3.3-70B"):
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "ABL-25"

    # FOLLOWUP_EXPERIMENTS 2.a/2.b use P100. Calibration FC trajectories in
    # these canonical cells count as run_1 of the corresponding experiment.
    for model in ("Devstral-Small-2-24B", "GLM-4.7-Flash"):
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "P100"

    # All three SWE models share the same main/ablation grid. Qwen retains
    # its existing 10K/15K/20K budgets; the other models use calibrated values.
    # Only the primary budget at canonical depth and infinite baselines use
    # P100. Every budget/depth ablation uses ABL-25, regardless of source path.
    expansion_budgets = {
        MAIN_MODEL: (10_000, 15_000, 20_000),
        "Devstral-Small-2-24B": (17_000, 21_000, 24_000),
        "GLM-4.7-Flash": (10_000, 13_000, 15_000),
    }
    for model, (a_budget, p_budget, b_budget) in expansion_budgets.items():
        for prim in DEPTH_TUNABLE:
            expected[("swebench", model, prim, p_budget, 0.5)] = "P100"
            for budget in (a_budget, p_budget, b_budget):
                for depth in (0.3, 0.7):
                    expected[("swebench", model, prim, budget, depth)] = "ABL-25"
            for budget in (a_budget, b_budget):
                expected[("swebench", model, prim, budget, 0.5)] = "ABL-25"
        for prim in DEPTH_INVARIANT:
            expected[("swebench", model, prim, p_budget, 0.5)] = "P100"
            for budget in (a_budget, b_budget):
                expected[("swebench", model, prim, budget, 0.5)] = "ABL-25"
        for prim in ("FC", "OTRC"):
            expected[("swebench", model, prim, INF, 0.5)] = "P100"

    # Concrete Terminal-Bench follow-up cells. A/P/B are model-specific. The
    # primary (P) depth/budget cells and unlimited baselines use 40 tasks;
    # the remaining grid uses the 15-task cohort.
    tb_expansion_budgets = {
        MAIN_MODEL: (2_000, 3_000, 4_000),
        "Devstral-Small-2-24B": (3_000, 4_000, 7_000),
        "GLM-4.7-Flash": (2_000, 3_000, 5_000),
    }
    for model, (a_budget, p_budget, b_budget) in tb_expansion_budgets.items():
        for prim in DEPTH_TUNABLE:
            expected[("terminal-bench", model, prim, p_budget, 0.5)] = "TB-40"
        for prim in DEPTH_INVARIANT:
            expected[("terminal-bench", model, prim, p_budget, 0.5)] = "TB-40"
        for prim in ("FC", "OTRC"):
            expected[("terminal-bench", model, prim, INF, 0.5)] = "TB-40"
        for prim in DEPTH_TUNABLE:
            for b in (a_budget, b_budget):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-15"
            for b in (a_budget, p_budget, b_budget):
                for d in (0.3, 0.7):
                    expected[("terminal-bench", model, prim, b, d)] = "TB-15"
        for prim in DEPTH_INVARIANT:
            for b in (a_budget, b_budget):
                expected[("terminal-bench", model, prim, b, 0.5)] = "TB-15"

    # Every cell above is self-summarized and served as in production: insert
    # the empty summarizer and prefix_cache slots so the keys line up with the
    # (benchmark, model, summarizer, prefix_cache, primitive, budget, depth)
    # cell keys used on disk.
    expected = {
        (benchmark, model, "", "", prim, budget, depth): cohort
        for (benchmark, model, prim, budget, depth), cohort in expected.items()
    }

    # FOLLOWUP_EXPERIMENTS 4: summarizer ablation.  SU-full (0.5) and TRC+SU
    # (DI) with a different summarizer and the main model as agent.  SWE cells
    # follow scripts/run_qwen_swe_summarizer_ablation.sh (ABL-25 at 15k);
    # Terminal-Bench cells use ABL-15 at the primary budget.
    for summarizer in SUMMARIZER_LABELS.values():
        for prim in ("SU-full", "TRC+SU"):
            expected[("swebench", MAIN_MODEL, summarizer, "", prim, 15_000, 0.5)] = "ABL-25"
            expected[("terminal-bench", MAIN_MODEL, summarizer, "", prim, 3_000, 0.5)] = "TB-15"

    # Dashboard Priority 5: prefix-cache ablation with the main model as agent
    # and summarizer.  Every primitive at canonical depth plus the unlimited
    # baselines, on ABL-25 (SWE-Bench, 5.a) and ABL-15 (Terminal-Bench, 5.b).
    for benchmark, cohort in (("swebench", "ABL-25"), ("terminal-bench", "TB-15")):
        label = PREFIX_CACHE_ABLATION[benchmark]
        for prim in DEPTH_TUNABLE + DEPTH_INVARIANT:
            expected[(benchmark, MAIN_MODEL, "", label, prim,
                      PREFIX_CACHE_BUDGETS[benchmark], 0.5)] = cohort
        for prim in ("FC", "OTRC"):
            expected[(benchmark, MAIN_MODEL, "", label, prim, INF, 0.5)] = cohort

    # ---- 3. merge into sheet rows --------------------------------------------
    # The coverage CSVs inventory data that actually exists.  ``expected``
    # only annotates the scope/status of observed cells; planned-but-unrun
    # follow-ups must not create rows of their own.
    all_keys = sorted(disk,
                      key=lambda k: (k[0], k[1] != MAIN_MODEL, k[1], k[2] != "", k[2],
                                     k[3] != "", k[3], k[4], k[5], k[6]))
    rows = []
    for key in all_keys:
        benchmark, model, summarizer, prefix_cache, prim, budget, depth = key
        d = disk.get(key)
        req = expected.get(key)
        required_runs = (TB_REQUIRED_RUNS_PER_TASK
                         if benchmark == "terminal-bench"
                         else REQUIRED_RUNS_PER_TASK)
        covered = d["tasks"] if d else set()
        cohort = (f"TB-{len(covered)}" if benchmark == "terminal-bench" else
                  classify_cohort(covered, abl25, p100)) if covered else ""

        runs_per_task_min = 0
        # Cohort-specific capped run counts let downstream consumers answer
        # questions such as "how many third runs are complete for ABL-25?"
        # exactly.  A proportional slice of a mixed P100 cell is incorrect
        # when only the ABL-25 tasks have received run_3.
        d_runs = d["task_runs"] if d else {}
        def capped_runs(tasks, cap):
            return sum(min(cap, d_runs.get(t, 0)) for t in tasks)

        cohort_counts = {}
        for cohort_name, cohort_tasks in (
            ("abl25", abl25), ("p100", p100), ("tb20", tb20)
        ):
            cohort_counts[f"tasks_covered_{cohort_name}"] = sum(
                d_runs.get(t, 0) > 0 for t in cohort_tasks
            )
            for cap in range(1, 6):
                cohort_counts[f"runs_capped_{cap}_{cohort_name}"] = capped_runs(
                    cohort_tasks, cap
                )
        # TB:ABL-15/P-40 progress can include provisional/rootless subsets.
        # Counting every observed task directly avoids proportionally scaling
        # a partial subset up to the planned cohort size in the dashboard.
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
                    len(covered) >= int(req.removeprefix("TB-")) if req and req.startswith("TB-") else
                    cohort.startswith(req) or
                    (req == "ABL-25" and cohort.startswith("P100"))
                )
                if not have_cohort:
                    status = "PARTIAL"
                else:
                    required_tasks = (covered if req and req.startswith("TB-") else
                                      p100 if req == "P100" else abl25)
                    runs_per_task_min = min(
                        (d_runs.get(t, 0) for t in required_tasks),
                        default=0)
                    status = "COMPLETE" if runs_per_task_min >= required_runs else "PARTIAL"

        notes = []
        has_required_cohort = (
            len(covered) >= int(req.removeprefix("TB-")) if req and req.startswith("TB-") else
            bool(req) and (cohort.startswith(req) or
                           (req == "ABL-25" and cohort.startswith("P100")))
        )
        if status == "PARTIAL" and covered and has_required_cohort:
            notes.append(f"only {runs_per_task_min}/{required_runs} runs/task")

        rows.append({
            "benchmark": benchmark,
            "model": model,
            # Empty for ordinary (self-summarized) cells; the summarizer model
            # label for summarizer-ablation cells (model_ablation/<agent>-sum-<summarizer>).
            "summarizer": summarizer,
            # Empty for ordinary cells; ON / OFF for prefix-cache-ablation cells
            # (<benchmark>/prefix_cache_ablation/<model>/<cell>).
            "prefix_cache": prefix_cache,
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

    swe_rows = [r for r in rows if r["benchmark"] == "swebench"]
    tb_rows = [r for r in rows if r["benchmark"] == "terminal-bench"]

    def write_rows(path, output_rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(output_rows)

    write_rows(out, swe_rows)
    write_rows(tb_out, tb_rows)

    # ---- 4. console summary ---------------------------------------------------
    n = defaultdict(int)
    for r in rows:
        n[r["status"]] += 1
    def display_path(path):
        try:
            return path.relative_to(ROOT)
        except ValueError:
            return path

    print(f"Wrote {display_path(out)} — {len(swe_rows)} SWE-Bench cells")
    print(f"Wrote {display_path(tb_out)} — {len(tb_rows)} Terminal-Bench cells")
    for status in ("COMPLETE", "PARTIAL", "MISSING", "EXTRA", "HAVE"):
        if n[status]:
            print(f"  {status}: {n[status]}")
    problems = [r for r in rows
                if r["status"] in ("MISSING", "PARTIAL")
                or r["notes"]]
    if problems:
        print("\nAttention:")
        for r in problems:
            summarizer = f" (summarizer {r['summarizer']})" if r["summarizer"] else ""
            if r["prefix_cache"]:
                summarizer += f" (prefix cache {r['prefix_cache']})"
            print(f"  [{r['status']:8s}] {r['benchmark']} / {r['model']}{summarizer} / "
                  f"{r['primitive']} / {r['budget']} / d={r['depth']}  "
                  f"{r['cohort_covered']}  {r['notes']}")


if __name__ == "__main__":
    main()
