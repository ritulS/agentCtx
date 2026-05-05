"""Build Review1_<model_tag>.csv from Albus's ablation outputs.

Scans `results/ablations/<MODEL_TAG>-*/experiment_results.json`, filters by
the canonical 30-task set, and writes:
  - Review1/Review1_<MODEL_TAG>.csv  (analysis-ready, same schema as Review1.csv)
  - Review1/raw/<MODEL_TAG>/<ablation_name>.json  (filtered raw records)

Idempotent — rebuilds from scratch on each call so partial runs are picked up
incrementally. Safe to run during a sweep.

Usage:
  venv/bin/python3 Review1/build_review1_albus.py --model-tag qwen25-7b
  venv/bin/python3 Review1/build_review1_albus.py --model-tag llama33-70b
"""

import argparse
import csv
import json
from pathlib import Path

ROOT   = Path(__file__).parent.parent
REVIEW = Path(__file__).parent

# Resolve ABL_TASKS: Albus stores the canonical 30-task list at
# task_lists/ablation_30tasks.json (committed); Dobby uses
# results/ablations/tasks.json (gitignored, locally present).
_ABL_TASKS_PATHS = [
    ROOT / "task_lists" / "ablation_30tasks.json",
    ROOT / "results" / "ablations" / "tasks.json",
]
_abl_path = next((p for p in _ABL_TASKS_PATHS if p.exists()), None)
if _abl_path is None:
    raise SystemExit(f"ERROR: no ablation task list found at any of {_ABL_TASKS_PATHS}")
with open(_abl_path) as f:
    ABL_TASKS = set(t["instance_id"] for t in json.load(f))


def repo_of(instance_id: str) -> str:
    return instance_id.split("__", 1)[0] + "__" + instance_id.split("__", 1)[1].rsplit("-", 1)[0]


def failure_mode(r: dict) -> str:
    if r.get("resolved") is True:
        return "resolved"
    if (r.get("exit_status") or "").startswith("LimitsExceeded"):
        return "limits_exceeded"
    if r.get("patch_generated") and r.get("exit_status") == "Submitted":
        return "submitted_unresolved"
    if not r.get("patch_generated"):
        return "silent_crash"
    return "other"


def to_row(r: dict, primitive_label: str) -> dict:
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
        "step_count":                  r.get("n_calls") or 0,
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

CONDITION_TO_LABEL = {
    "full-context":                 "FC",
    "truncation":                   "TR",
    "summarization":                "SU-full",
    "summarization-partial":        "SU-partial",
    "structured-summarize":         "SS",
    "structured-summarize-partial": "SS-partial",
    "tool-result-clear":            "TRC",
    "online-trc":                   "OTRC",
    "trc-su":                       "TRC+SU",
    "trc-ss":                       "TRC+SS",
    "otrc-tr":                      "OTRC+TR",
    "otrc-su-partial":              "OTRC+SU-partial",
    "otrc-ss-partial":              "OTRC+SS-partial",
    "staggered-alternate":          "STAG-alt",
    "staggered-random":             "STAG-rand",
}

# Schema matches Review1.csv header exactly.
HEADER = [
    "task_name", "primitive", "token_budget", "run_num", "repo",
    "resolved", "exit_status", "patch_generated", "failure_mode",
    "step_count", "total_tokens_consumed", "total_prompt_tokens",
    "total_completion_tokens", "latency_e2e_s", "latency_llm_s",
    "mean_step_latency_s", "compression_events", "mean_compression_ratio",
    "summarization_prompt_tokens", "summarization_latency_s",
    "trc_fallback_events", "online_trc_clears",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-tag", required=True,
                        help="Model tag prefix (e.g. qwen25-7b, llama33-70b). "
                             "Globs results/ablations/<TAG>-*/experiment_results.json.")
    args = parser.parse_args()
    tag = args.model_tag

    pattern = f"{tag}-*"
    ablation_dirs = sorted(d for d in (ROOT / "results" / "ablations").glob(pattern) if d.is_dir())
    if not ablation_dirs:
        print(f"WARNING: no ablation dirs matched results/ablations/{pattern}")
        return

    raw_root = REVIEW / "raw" / tag
    raw_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for adir in ablation_dirs:
        results_path = adir / "experiment_results.json"
        if not results_path.exists():
            print(f"  SKIP {adir.name}: no experiment_results.json yet")
            continue
        with open(results_path) as f:
            all_runs = json.load(f)
        kept = [r for r in all_runs if r.get("instance_id") in ABL_TASKS]
        # Copy filtered raw to Review1/raw/<TAG>/<ablation>.json
        with open(raw_root / f"{adir.name}.json", "w") as f:
            json.dump(kept, f, indent=2)
        # Build CSV rows
        for r in kept:
            cond = r.get("condition", "")
            label = CONDITION_TO_LABEL.get(cond, cond)
            rows.append(to_row(r, label))
        print(f"  {adir.name}: {len(kept)}/{len(all_runs)} runs")

    csv_path = REVIEW / f"Review1_{tag}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {csv_path.relative_to(ROOT)}")
    print(f"raw filtered records under {raw_root.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
