"""Populate Review1.csv from existing experiment_results.json files.

Sources cover two task cohorts:
  * The original 30 ABL_TASKS (FC-stratified) — `results/qwen3.5-35B-A3B_15k_Fullrun/`,
    `results/ablations/timing-{10,20}k/`, `results/ablations/{partial,stacked,
    otrc-stacked}-{10,15,20}000/`, `results/qwen35-a3b_online-trc/`.
  * The 70 P100_NEW tasks added in the n=30→100 expansion — `results/ablations/
    p100-{singles,trc,otrc}-{10,15,20}000/` plus `results/ablations/p100-inf/`
    for FC + OTRC at ∞.

Every primitive's `fill_*` reads from BOTH cohorts. The filter is `P100_TASKS`
(the union of 30 + 70 = 100). p100-* dirs contain stub `seeded_from` rows that
duplicate the 30-task originals — we skip those and pull the data from the
original sources.

Run with no args → rebuild everything from scratch (truncates Review1.csv to
header). Run with primitive args → append-only fills for those primitives.
"""

import csv
import json
import shutil
import sys
from pathlib import Path

ROOT     = Path(__file__).parent.parent
REVIEW   = Path(__file__).parent
CSV_PATH = REVIEW / "Review1.csv"

with open(ROOT / "results/ablations/tasks.json") as f:
    ABL_TASKS = set(t["instance_id"] for t in json.load(f))

with open(ROOT / "task_lists/p100_new_tasks.json") as f:
    P100_NEW_TASKS = set(t["instance_id"] for t in json.load(f))

P100_TASKS = ABL_TASKS | P100_NEW_TASKS  # the full 100-task cohort


def repo_of(instance_id: str) -> str:
    return instance_id.split("__", 1)[0] + "__" + instance_id.split("__", 1)[1].rsplit("-", 1)[0]


def failure_mode(r: dict) -> str:
    if r.get("resolved") is True:
        return "resolved"
    if r.get("exit_status", "").startswith("LimitsExceeded"):
        return "limits_exceeded"
    if r.get("patch_generated") and r.get("exit_status") == "Submitted":
        return "submitted_unresolved"
    if not r.get("patch_generated"):
        return "silent_crash"
    return "other"


FIELDNAMES = [
    "task_name", "primitive", "token_budget", "depth", "run_num", "repo",
    "resolved", "exit_status", "patch_generated", "failure_mode", "step_count",
    "total_tokens_consumed", "total_prompt_tokens", "total_completion_tokens",
    "latency_e2e_s", "latency_llm_s", "mean_step_latency_s",
    "compression_events", "mean_compression_ratio",
    "summarization_prompt_tokens", "summarization_latency_s",
    "trc_fallback_events", "online_trc_clears",
]


def to_row(r: dict, primitive_label: str) -> dict:
    n = r.get("n_calls") or 0
    return {
        "task_name":                   r.get("instance_id"),
        "primitive":                   primitive_label,
        "token_budget":                r.get("budget"),
        "depth":                       r.get("compression_ratio", 0.5),
        "run_num":                     r.get("run_num"),
        "repo":                        repo_of(r.get("instance_id", "")),
        "resolved":                    r.get("resolved") if r.get("resolved") is not None else False,
        "exit_status":                 r.get("exit_status"),
        "patch_generated":             r.get("patch_generated"),
        "failure_mode":                failure_mode(r),
        "step_count":                  n,
        "total_tokens_consumed":       r.get("total_tokens"),
        "total_prompt_tokens":         r.get("total_prompt_tokens"),
        "total_completion_tokens":     r.get("total_completion_tokens"),
        "latency_e2e_s":               r.get("e2e_latency_s"),
        "latency_llm_s":               r.get("llm_latency_s"),
        "mean_step_latency_s":         r.get("mean_latency_s"),
        "compression_events":          r.get("compression_events", 0),
        "mean_compression_ratio":      r.get("mean_compression_ratio"),
        "summarization_prompt_tokens": r.get("summarization_prompt_tokens", 0),
        "summarization_latency_s":     r.get("summarization_latency_s", 0.0),
        "trc_fallback_events":         r.get("trc_truncation_fallback_events", 0),
        "online_trc_clears":           r.get("online_trc_clears", 0),
    }


def append_rows(rows: list[dict]) -> None:
    with open(CSV_PATH, "r", newline="") as f:
        fieldnames = next(csv.reader(f))
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        for row in rows:
            w.writerow(row)


# Auxiliary "fill" sources that carry P100_NEW records for the original 5
# conditions at 10k/20k/∞. They were created during the n=30→100 expansion to
# back-fill cells that timing-{10,20}k / Fullrun-15k didn't cover.
_AUX_FILL_SOURCES = [
    ROOT / "data/swebench/source_runs/qwen35-a3b_10k/experiment_results.json",
    ROOT / "data/swebench/source_runs/qwen35-a3b_20k/experiment_results.json",
    ROOT / "data/swebench/legacy/qwen35-a3b_trc20k/experiment_results.json",
    ROOT / "data/swebench/legacy/qwen35-a3b_trc20k-fill/experiment_results.json",
]


def _collect_cell(cond: str, budget: int | None, primitive_label: str,
                  raw_subdir: str, primary_sources: list[Path],
                  depth_filter: float | None = None,
                  consult_aux: bool = True) -> list[dict]:
    """Collect 200 (task, run) records for a (cond, budget) cell using a
    priority-ordered list of sources, deduping by (instance_id, run_num).

    The first record encountered for a given (task, run) is kept. Pass
    `primary_sources` ordered most-canonical-first; auxiliary fill sources are
    consulted afterwards (unless consult_aux=False) for any (task, run) still
    missing. depth_filter restricts to records with a specific compression
    ratio (used by depth-grid fills to guard against cross-depth contamination).
    """
    seen = {}  # (task, run_num) → record

    def consume(path: Path, task_filter: set):
        if not path.exists():
            return
        for r in json.loads(path.read_text()):
            if r.get("condition") != cond:
                continue
            if r.get("instance_id") not in task_filter:
                continue
            if "seeded_from" in r:
                continue
            # Match cell budget (∞ → 999_999_999)
            expected = budget if budget is not None else 999_999_999
            if r.get("budget") != expected:
                continue
            if depth_filter is not None and r.get("compression_ratio", 0.5) != depth_filter:
                continue
            key = (r["instance_id"], r["run_num"])
            if key not in seen:
                seen[key] = r

    for path in primary_sources:
        consume(path, P100_TASKS)
    if consult_aux:
        for path in _AUX_FILL_SOURCES:
            consume(path, P100_TASKS)

    # Save filtered raw records for traceability.
    raw_dir = REVIEW / "raw" / raw_subdir
    raw_dir.mkdir(parents=True, exist_ok=True)
    suffix = "inf" if budget is None else f"{budget // 1000}k"
    safe_name = raw_subdir.lower().replace("+", "_")
    with open(raw_dir / f"{safe_name}_{suffix}.json", "w") as f:
        json.dump(list(seen.values()), f, indent=2)

    return [to_row(r, primitive_label) for r in seen.values()]


_TIMING_SOURCES = {
    10000: ROOT / "results/ablations/timing-10k/experiment_results.json",
    15000: ROOT / "data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json",
    20000: ROOT / "results/ablations/timing-20k/experiment_results.json",
}

_P100_SINGLES_SOURCES = {
    10000: ROOT / "results/ablations/p100-singles-10000/experiment_results.json",
    15000: ROOT / "results/ablations/p100-singles-15000/experiment_results.json",
    20000: ROOT / "results/ablations/p100-singles-20000/experiment_results.json",
}

_P100_TRC_SOURCES = {
    10000: ROOT / "results/ablations/p100-trc-10000/experiment_results.json",
    15000: ROOT / "results/ablations/p100-trc-15000/experiment_results.json",
    20000: ROOT / "results/ablations/p100-trc-20000/experiment_results.json",
}

_P100_OTRC_SOURCES = {
    10000: ROOT / "results/ablations/p100-otrc-10000/experiment_results.json",
    15000: ROOT / "results/ablations/p100-otrc-15000/experiment_results.json",
    20000: ROOT / "results/ablations/p100-otrc-20000/experiment_results.json",
}

_P100_INF_SOURCE = ROOT / "results/ablations/p100-inf/experiment_results.json"


def _records_in(path: Path, condition_name: str, task_set: set) -> list[dict]:
    """Return runs from `path` matching `condition_name` and within `task_set`,
    skipping seeded-stub rows (those duplicate records that live in the
    original sources)."""
    if not path.exists():
        return []
    runs = json.loads(path.read_text())
    return [r for r in runs
            if r.get("condition") == condition_name
            and r.get("instance_id") in task_set
            and "seeded_from" not in r]


def _fill_from_timing(condition_name: str, primitive_label: str, raw_subdir: str,
                      p100_sources: dict = None) -> None:
    """Fill a primitive across 10/15/20k from timing/Fullrun sources +
    p100-* sources, with dedupe by (instance_id, run_num)."""
    p100_sources = p100_sources or _P100_SINGLES_SOURCES
    rows = []
    for budget in (10000, 15000, 20000):
        # Priority: p100 fresh (canonical for P100_NEW) → original 30-task source.
        primary = [p100_sources[budget], _TIMING_SOURCES[budget]]
        cell = _collect_cell(condition_name, budget, primitive_label, raw_subdir, primary)
        rows.extend(cell)
        print(f"  {budget // 1000}k: {len(cell)} runs (deduped)")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_su_full() -> None:
    print("[SU-full]")
    _fill_from_timing("summarization", "SU-full", "SU-full")


def fill_tr() -> None:
    print("[TR]")
    _fill_from_timing("truncation", "TR", "TR")


def fill_trc() -> None:
    print("[TRC]")
    _fill_from_timing("tool-result-clear", "TRC", "TRC", _P100_TRC_SOURCES)


_STACKED_SOURCES = {
    10000: ROOT / "results/ablations/stacked-10000/experiment_results.json",
    15000: ROOT / "results/ablations/stacked-15000/experiment_results.json",
    20000: ROOT / "results/ablations/stacked-20000/experiment_results.json",
}


def _fill_from_stacked(condition_name: str, primitive_label: str, raw_subdir: str) -> None:
    """Fill TRC+SU / TRC+SS via _collect_cell."""
    rows = []
    for budget in (10000, 15000, 20000):
        primary = [_P100_TRC_SOURCES[budget], _STACKED_SOURCES[budget]]
        cell = _collect_cell(condition_name, budget, primitive_label, raw_subdir, primary)
        rows.extend(cell)
        print(f"  {budget // 1000}k: {len(cell)} runs (deduped)")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_trc_su() -> None:
    print("[TRC+SU]")
    _fill_from_stacked("trc-su", "TRC+SU", "TRC+SU")


def fill_trc_ss() -> None:
    print("[TRC+SS]")
    _fill_from_stacked("trc-ss", "TRC+SS", "TRC+SS")


_PARTIAL_SOURCES = {
    10000: ROOT / "results/ablations/partial-10000/experiment_results.json",
    15000: ROOT / "results/ablations/partial-15000/experiment_results.json",
    20000: ROOT / "results/ablations/partial-20000/experiment_results.json",
}

_OTRC_STACKED_SOURCES = {
    10000: ROOT / "results/ablations/otrc-stacked-10000/experiment_results.json",
    15000: ROOT / "results/ablations/otrc-stacked-15000/experiment_results.json",
    20000: ROOT / "results/ablations/otrc-stacked-20000/experiment_results.json",
}


def _fill_from_sources(sources: dict, condition_name: str, primitive_label: str,
                       raw_subdir: str, p100_sources: dict = None) -> None:
    """Fill from {partial,stacked,otrc-stacked}-* + matching p100-* via _collect_cell."""
    rows = []
    for budget in (10000, 15000, 20000):
        primary = []
        if p100_sources is not None:
            primary.append(p100_sources[budget])
        primary.append(sources[budget])
        cell = _collect_cell(condition_name, budget, primitive_label, raw_subdir, primary)
        rows.extend(cell)
        print(f"  {budget // 1000}k: {len(cell)} runs (deduped)")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_su_partial() -> None:
    print("[SU-partial]")
    _fill_from_sources(_PARTIAL_SOURCES, "summarization-partial", "SU-partial",
                       "SU-partial", _P100_SINGLES_SOURCES)


def fill_ss_partial() -> None:
    print("[SS-partial]")
    _fill_from_sources(_PARTIAL_SOURCES, "structured-summarize-partial", "SS-partial",
                       "SS-partial", _P100_SINGLES_SOURCES)


def fill_ss() -> None:
    """SS @10k/20k: partial-* (30 ABL) + p100-singles-* (70 NEW).
    SS @15k: Fullrun-15k (99 tasks) + p100-singles-15000 fresh."""
    print("[SS]")
    rows = []
    ss_sources_30 = {
        10000: _PARTIAL_SOURCES[10000],
        15000: ROOT / "data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json",
        20000: _PARTIAL_SOURCES[20000],
    }
    for budget in (10000, 15000, 20000):
        primary = [_P100_SINGLES_SOURCES[budget], ss_sources_30[budget]]
        cell = _collect_cell("structured-summarize", budget, "SS", "SS", primary)
        rows.extend(cell)
        print(f"  {budget // 1000}k: {len(cell)} runs (deduped)")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_otrc_tr() -> None:
    print("[OTRC+TR]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-tr", "OTRC+TR",
                       "OTRC+TR", _P100_OTRC_SOURCES)


def fill_otrc_su_partial() -> None:
    print("[OTRC+SU-partial]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-su-partial", "OTRC+SU-partial",
                       "OTRC+SU-partial", _P100_OTRC_SOURCES)


def fill_otrc_ss_partial() -> None:
    print("[OTRC+SS-partial]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-ss-partial", "OTRC+SS-partial",
                       "OTRC+SS-partial", _P100_OTRC_SOURCES)


def fill_fc() -> None:
    """FC @∞: p100-inf (canonical for P100_NEW) + Fullrun-15k (30 ABL)."""
    print("[FC]")
    primary = [_P100_INF_SOURCE,
               ROOT / "data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json"]
    cell = _collect_cell("full-context", None, "FC", "FC", primary)
    append_rows(cell)
    print(f"  {len(cell)} runs (deduped)")


def fill_otrc() -> None:
    """OTRC @∞: p100-inf (canonical for P100_NEW) + qwen35-a3b_online-trc (30 ABL)."""
    print("[OTRC]")
    primary = [_P100_INF_SOURCE,
               ROOT / "data/swebench/source_runs/qwen35-a3b_online-trc/experiment_results.json"]
    cell = _collect_cell("online-trc", None, "OTRC", "OTRC", primary)
    append_rows(cell)
    print(f"  {len(cell)} runs (deduped)")


# Staggered pilot: 6 tasks × 2 strategies × 3 budgets × 2 runs.
# Cell size is ~12 records per (primitive, budget) — much smaller than the
# 200-row n=100 cells. Fills are best-effort and skip any missing dir.
_STAGGERED_PILOT_SOURCES = {
    10000: ROOT / "results/ablations/staggered-pilot-10000/experiment_results.json",
    15000: ROOT / "results/ablations/staggered-pilot-15000/experiment_results.json",
    20000: ROOT / "results/ablations/staggered-pilot-20000/experiment_results.json",
}


def _fill_staggered(condition_name: str, primitive_label: str, raw_subdir: str) -> None:
    rows = []
    for budget in (10000, 15000, 20000):
        primary = [_STAGGERED_PILOT_SOURCES[budget]]
        if not primary[0].exists():
            print(f"  {budget // 1000}k: source missing, skipping")
            continue
        cell = _collect_cell(condition_name, budget, primitive_label, raw_subdir, primary)
        rows.extend(cell)
        print(f"  {budget // 1000}k: {len(cell)} runs (deduped)")
    if rows:
        append_rows(rows)
        print(f"appended {len(rows)} rows to {CSV_PATH.name}")
    else:
        print("no staggered rows appended (no source files yet)")


def fill_staggered_alternate() -> None:
    print("[STAG-alt]")
    _fill_staggered("staggered-alternate", "STAG-alt", "STAG-alt")


def fill_staggered_random() -> None:
    print("[STAG-rand]")
    _fill_staggered("staggered-random", "STAG-rand", "STAG-rand")


# Depth-grid. The 20k tail cells cover ABL-30 only.
# Each dir is a single (depth, budget, group) cell. Sources read with
# depth_filter and consult_aux=False to keep depth strata cleanly separated.
_P100_DEPTH30_SINGLES_SOURCES = {
    10000: ROOT / "results/ablations/p100-depth30-singles-10000/experiment_results.json",  # bonus
    15000: ROOT / "results/ablations/p100-depth30-singles-15000/experiment_results.json",
    20000: ROOT / "results/ablations/p100-depth30-singles-20000/experiment_results.json",
}
_P100_DEPTH30_OTRC_SOURCES = {
    15000: ROOT / "results/ablations/p100-depth30-otrc-15000/experiment_results.json",
}
_P100_DEPTH70_SINGLES_SOURCES = {
    10000: ROOT / "results/ablations/p100-depth70-singles-10000/experiment_results.json",
    15000: ROOT / "results/ablations/p100-depth70-singles-15000/experiment_results.json",
    20000: ROOT / "results/ablations/p100-depth70-singles-20000/experiment_results.json",
}
_P100_DEPTH70_OTRC_SOURCES = {
    15000: ROOT / "results/ablations/p100-depth70-otrc-15000/experiment_results.json",
}
_P100_DEPTH30_TRC_SOURCES = {
    20000: ROOT / "results/ablations/p100-depth30-trc-20000/experiment_results.json",
}
_P100_DEPTH70_TRC_SOURCES = {
    20000: ROOT / "results/ablations/p100-depth70-trc-20000/experiment_results.json",
}

_SINGLES_CONDS = [
    ("truncation",                   "TR"),
    ("summarization",                "SU-full"),
    ("summarization-partial",        "SU-partial"),
    ("structured-summarize",         "SS"),
    ("structured-summarize-partial", "SS-partial"),
]

_OTRC_CONDS = [
    ("otrc-tr",          "OTRC+TR"),
    ("otrc-su-partial",  "OTRC+SU-partial"),
    ("otrc-ss-partial",  "OTRC+SS-partial"),
]

_TRC_CONDS = [
    ("tool-result-clear", "TRC"),
    ("trc-su",            "TRC+SU"),
    ("trc-ss",            "TRC+SS"),
]


def _fill_depth_cells(depth: float, sources: dict, conds: list,
                      group_tag: str) -> None:
    """Fill all (cond × budget) cells for a single (depth, group) bundle.

    depth: 0.3 or 0.7 — used for depth_filter and raw_subdir naming.
    sources: {budget: Path} for the depth/group bundle.
    conds: list of (condition, primitive_label) tuples.
    group_tag: "singles" or "otrc" for raw_subdir naming.
    """
    rows = []
    for budget, src in sources.items():
        for cond, label in conds:
            raw_subdir = f"depth{int(depth*100):02d}-{label}"
            cell = _collect_cell(cond, budget, label, raw_subdir,
                                 [src], depth_filter=depth, consult_aux=False)
            rows.extend(cell)
            print(f"  depth={depth} {budget // 1000}k {label}: {len(cell)} runs")
    if rows:
        append_rows(rows)
        print(f"appended {len(rows)} rows to {CSV_PATH.name}")
    else:
        print("no rows appended (sources missing?)")


def fill_depth30_singles() -> None:
    print("[depth=0.3 singles]")
    _fill_depth_cells(0.3, _P100_DEPTH30_SINGLES_SOURCES, _SINGLES_CONDS, "singles")


def fill_depth30_otrc() -> None:
    print("[depth=0.3 otrc]")
    _fill_depth_cells(0.3, _P100_DEPTH30_OTRC_SOURCES, _OTRC_CONDS, "otrc")


def fill_depth70_singles() -> None:
    print("[depth=0.7 singles]")
    _fill_depth_cells(0.7, _P100_DEPTH70_SINGLES_SOURCES, _SINGLES_CONDS, "singles")


def fill_depth70_otrc() -> None:
    print("[depth=0.7 otrc]")
    _fill_depth_cells(0.7, _P100_DEPTH70_OTRC_SOURCES, _OTRC_CONDS, "otrc")


def fill_depth30_trc() -> None:
    print("[depth=0.3 trc]")
    _fill_depth_cells(0.3, _P100_DEPTH30_TRC_SOURCES, _TRC_CONDS, "trc")


def fill_depth70_trc() -> None:
    print("[depth=0.7 trc]")
    _fill_depth_cells(0.7, _P100_DEPTH70_TRC_SOURCES, _TRC_CONDS, "trc")


_ALL_FILLS = [
    fill_fc, fill_otrc,
    fill_tr, fill_su_full, fill_ss,
    fill_su_partial, fill_ss_partial,
    fill_trc, fill_trc_su, fill_trc_ss,
    fill_otrc_tr, fill_otrc_su_partial, fill_otrc_ss_partial,
    fill_staggered_alternate, fill_staggered_random,
    fill_depth30_singles, fill_depth30_otrc,
    fill_depth70_singles, fill_depth70_otrc,
    fill_depth30_trc, fill_depth70_trc,
]


def _truncate_csv_to_header() -> None:
    """Reset Review1.csv to canonical header-only, ready for full rebuild."""
    with open(CSV_PATH, "w", newline="") as f:
        csv.writer(f).writerow(FIELDNAMES)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            globals()[f"fill_{arg.replace('-', '_')}"]()
    else:
        print("=== Full rebuild (n=100 cohort) ===")
        _truncate_csv_to_header()
        for fn in _ALL_FILLS:
            fn()
        print("\n=== Rebuild complete ===")
