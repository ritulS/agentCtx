"""Populate Review1.csv from existing experiment_results.json files.

Run incrementally per primitive. Currently fills SU-full from:
  10k: results/ablations/timing-10k/
  15k: results/qwen3.5-35B-A3B_15k_Fullrun/
  20k: results/ablations/timing-20k/

Also copies the filtered raw run records to Review1/raw/<primitive>/ for traceability.

Each invocation APPENDS rows to Review1.csv (header preserved).
"""

import csv
import json
import shutil
from pathlib import Path

ROOT     = Path(__file__).parent.parent
REVIEW   = Path(__file__).parent
CSV_PATH = REVIEW / "Review1.csv"

with open(ROOT / "results/ablations/tasks.json") as f:
    ABL_TASKS = set(t["instance_id"] for t in json.load(f))


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


def to_row(r: dict, primitive_label: str) -> dict:
    n = r.get("n_calls") or 0
    return {
        "task_name":                   r.get("instance_id"),
        "primitive":                   primitive_label,
        "token_budget":                r.get("budget"),
        "run_num":                     r.get("run_num"),
        "repo":                        repo_of(r.get("instance_id", "")),
        "resolved":                    r.get("resolved"),
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


_TIMING_SOURCES = {
    10000: ROOT / "results/ablations/timing-10k/experiment_results.json",
    15000: ROOT / "results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json",
    20000: ROOT / "results/ablations/timing-20k/experiment_results.json",
}


def _fill_from_timing(condition_name: str, primitive_label: str, raw_subdir: str) -> None:
    """Fill rows for a primitive that's present in timing-10k / Fullrun-15k / timing-20k.

    Filters each source by `condition_name`, copies filtered records to
    Review1/raw/<raw_subdir>/<label>_<budget>k.json, and appends rows to Review1.csv.
    """
    raw_dir = REVIEW / "raw" / raw_subdir
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for budget, path in _TIMING_SOURCES.items():
        with open(path) as f:
            all_runs = json.load(f)
        rs = [r for r in all_runs
              if r.get("condition") == condition_name
              and r.get("instance_id") in ABL_TASKS]
        with open(raw_dir / f"{raw_subdir.lower()}_{budget // 1000}k.json", "w") as f:
            json.dump(rs, f, indent=2)
        for r in rs:
            rows.append(to_row(r, primitive_label))
        print(f"  {budget // 1000}k: {len(rs)} runs from {path.relative_to(ROOT)}")

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
    _fill_from_timing("tool-result-clear", "TRC", "TRC")


_STACKED_SOURCES = {
    10000: ROOT / "results/ablations/stacked-10000/experiment_results.json",
    15000: ROOT / "results/ablations/stacked-15000/experiment_results.json",
    20000: ROOT / "results/ablations/stacked-20000/experiment_results.json",
}


def _fill_from_stacked(condition_name: str, primitive_label: str, raw_subdir: str) -> None:
    """Fill rows for a stacked primitive from the stacked-{10,15,20}k ablation dirs."""
    raw_dir = REVIEW / "raw" / raw_subdir
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for budget, path in _STACKED_SOURCES.items():
        with open(path) as f:
            all_runs = json.load(f)
        rs = [r for r in all_runs
              if r.get("condition") == condition_name
              and r.get("instance_id") in ABL_TASKS]
        with open(raw_dir / f"{raw_subdir.lower().replace('+','_')}_{budget // 1000}k.json", "w") as f:
            json.dump(rs, f, indent=2)
        for r in rs:
            rows.append(to_row(r, primitive_label))
        print(f"  {budget // 1000}k: {len(rs)} runs from {path.relative_to(ROOT)}")

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
                       raw_subdir: str) -> None:
    raw_dir = REVIEW / "raw" / raw_subdir
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    safe_name = raw_subdir.lower().replace("+", "_")
    for budget, path in sources.items():
        if not path.exists():
            print(f"  {budget // 1000}k: MISSING {path}"); continue
        with open(path) as f:
            all_runs = json.load(f)
        rs = [r for r in all_runs
              if r.get("condition") == condition_name
              and r.get("instance_id") in ABL_TASKS]
        with open(raw_dir / f"{safe_name}_{budget // 1000}k.json", "w") as f:
            json.dump(rs, f, indent=2)
        for r in rs:
            rows.append(to_row(r, primitive_label))
        print(f"  {budget // 1000}k: {len(rs)} runs from {path.relative_to(ROOT)}")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_su_partial() -> None:
    print("[SU-partial]")
    _fill_from_sources(_PARTIAL_SOURCES, "summarization-partial", "SU-partial", "SU-partial")


def fill_ss_partial() -> None:
    print("[SS-partial]")
    _fill_from_sources(_PARTIAL_SOURCES, "structured-summarize-partial", "SS-partial", "SS-partial")


def fill_ss() -> None:
    """SS coverage: 10k & 20k from partial-* (gap-fill), 15k from Fullrun-15k."""
    print("[SS]")
    raw_dir = REVIEW / "raw" / "SS"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    sources = {
        10000: _PARTIAL_SOURCES[10000],
        15000: ROOT / "results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json",
        20000: _PARTIAL_SOURCES[20000],
    }
    for budget, path in sources.items():
        with open(path) as f:
            all_runs = json.load(f)
        rs = [r for r in all_runs
              if r.get("condition") == "structured-summarize"
              and r.get("instance_id") in ABL_TASKS]
        with open(raw_dir / f"ss_{budget // 1000}k.json", "w") as f:
            json.dump(rs, f, indent=2)
        for r in rs:
            rows.append(to_row(r, "SS"))
        print(f"  {budget // 1000}k: {len(rs)} runs from {path.relative_to(ROOT)}")
    append_rows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_otrc_tr() -> None:
    print("[OTRC+TR]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-tr", "OTRC+TR", "OTRC+TR")


def fill_otrc_su_partial() -> None:
    print("[OTRC+SU-partial]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-su-partial", "OTRC+SU-partial", "OTRC+SU-partial")


def fill_otrc_ss_partial() -> None:
    print("[OTRC+SS-partial]")
    _fill_from_sources(_OTRC_STACKED_SOURCES, "otrc-ss-partial", "OTRC+SS-partial", "OTRC+SS-partial")


def fill_fc() -> None:
    """FC (full-context, no compression) on the 30-task ablation set."""
    print("[FC]")
    src = ROOT / "results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json"
    raw_dir = REVIEW / "raw" / "FC"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with open(src) as f:
        all_runs = json.load(f)
    rs = [r for r in all_runs
          if r.get("condition") == "full-context"
          and r.get("instance_id") in ABL_TASKS]
    with open(raw_dir / "fc_no_compression.json", "w") as f:
        json.dump(rs, f, indent=2)

    rows = [to_row(r, "FC") for r in rs]
    append_rows(rows)
    print(f"  {len(rs)} runs from {src.relative_to(ROOT)}")
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


def fill_otrc() -> None:
    """OTRC at budget=999_999_999 (no threshold, FREEZE_K=4 step-level clearing).

    Source is the full 99-task SWE-bench run; we filter to the 30-task ablation set.
    """
    print("[OTRC]")
    src = ROOT / "results/qwen35-a3b_online-trc/experiment_results.json"
    raw_dir = REVIEW / "raw" / "OTRC"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with open(src) as f:
        all_runs = json.load(f)
    rs = [r for r in all_runs
          if r.get("condition") == "online-trc"
          and r.get("instance_id") in ABL_TASKS]
    with open(raw_dir / "otrc_no_threshold.json", "w") as f:
        json.dump(rs, f, indent=2)

    rows = [to_row(r, "OTRC") for r in rs]
    append_rows(rows)
    print(f"  {len(rs)} runs from {src.relative_to(ROOT)}")
    print(f"appended {len(rows)} rows to {CSV_PATH.name}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            globals()[f"fill_{arg.replace('-', '_')}"]()
    else:
        fill_su_full()
