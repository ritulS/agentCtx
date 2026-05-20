"""Build Review1_<model_tag>.csv from Albus's ablation outputs.

Scans `results/ablations/<MODEL_TAG>/` plus `results/ablations/<MODEL_TAG>-*/`
(both the bare-name dir, if present, and any suffixed siblings),
filters by the canonical 30-task set, and writes:
  - Review1/Review1_<MODEL_TAG>.csv  (analysis-ready, same schema as Review1.csv
    plus the two trailing columns `ablation` and `depth`)
  - Review1/raw/<MODEL_TAG>/<ablation_name>.json  (filtered raw records)

Idempotent — rebuilds from scratch on each call so partial runs are picked up
incrementally. Safe to run during a sweep.

Usage:
  venv/bin/python3 Review1/build_review1_albus.py --model-tag qwen25-7b
  venv/bin/python3 Review1/build_review1_albus.py --model-tag llama33-70b
  venv/bin/python3 Review1/build_review1_albus.py --model-tag qwen3-30b-a3b \\
      --exclude '*-failed-*' --exclude '*-degraded-*'
"""

import argparse
import csv
import fnmatch
import json
import re
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


# Trailing `-d030` / `-d050` / `-d070` on an ablation dir name → depth 0.3/0.5/0.7.
# No suffix → canonical default depth 0.5.
_DEPTH_RE = re.compile(r"-d(\d{3})$")


def parse_depth(ablation_name: str) -> float:
    m = _DEPTH_RE.search(ablation_name)
    if m:
        return int(m.group(1)) / 100.0
    return 0.5


def to_row(r: dict, primitive_label: str, ablation: str, depth: float) -> dict:
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
        "ablation":                    ablation,
        "depth":                       depth,
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

# Schema matches Review1.csv header exactly, plus two trailing Albus-only
# provenance columns: `ablation` (source dir basename) and `depth` (parsed
# from the -d030/-d050/-d070 suffix; 0.5 when no suffix, the canonical default).
HEADER = [
    "task_name", "primitive", "token_budget", "run_num", "repo",
    "resolved", "exit_status", "patch_generated", "failure_mode",
    "step_count", "total_tokens_consumed", "total_prompt_tokens",
    "total_completion_tokens", "latency_e2e_s", "latency_llm_s",
    "mean_step_latency_s", "compression_events", "mean_compression_ratio",
    "summarization_prompt_tokens", "summarization_latency_s",
    "trc_fallback_events", "online_trc_clears",
    "ablation", "depth",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-tag", required=True,
                        help="Model tag (e.g. qwen25-7b, qwen3-30b-a3b). "
                             "Picks up results/ablations/<TAG>/ AND "
                             "results/ablations/<TAG>-*/experiment_results.json.")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                        help="fnmatch pattern applied to ablation-dir basenames; "
                             "matching dirs are dropped. Repeatable. "
                             "E.g. --exclude '*-failed-*' --exclude '*-degraded-*'.")
    args = parser.parse_args()
    tag = args.model_tag

    # Union: the bare-name dir (if present) + suffixed siblings. The original
    # `{tag}-*` glob silently dropped a bare-name dir, which on 2026-05-12
    # caused Review1_qwen3-30b-a3b-gptq-int4.csv to aggregate the failed
    # sidecar instead of the clean GPTQ rerun.
    ablations_root = ROOT / "results" / "ablations"
    candidates = set(ablations_root.glob(f"{tag}-*"))
    exact = ablations_root / tag
    if exact.is_dir():
        candidates.add(exact)
    ablation_dirs = sorted(d for d in candidates if d.is_dir())

    if args.exclude:
        before = len(ablation_dirs)
        ablation_dirs = [
            d for d in ablation_dirs
            if not any(fnmatch.fnmatch(d.name, p) for p in args.exclude)
        ]
        dropped = before - len(ablation_dirs)
        if dropped:
            print(f"  --exclude dropped {dropped} dir(s) matching {args.exclude}")

    if not ablation_dirs:
        print(f"WARNING: no ablation dirs matched tag={tag!r}")
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
        ablation_name = adir.name
        depth = parse_depth(ablation_name)
        for r in kept:
            cond = r.get("condition", "")
            label = CONDITION_TO_LABEL.get(cond, cond)
            rows.append(to_row(r, label, ablation_name, depth))
        print(f"  {adir.name}: {len(kept)}/{len(all_runs)} runs  (depth={depth})")

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
