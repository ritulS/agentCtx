#!/usr/bin/env python3
"""Build one task × primitive outcome CSV per benchmark.

The canonical inputs are ``ICLR_results/swebench/**/experiment_results.json``
and ``ICLR_results/terminalbench/**/experiment_results.json``.  Copying a
Terminal-Bench result tree from another machine beneath ``ICLR_results/`` is
therefore sufficient; re-run this script to refresh its CSV.

Usage:
    python3 analysis/aggregate_benchmark_results.py
    python3 analysis/aggregate_benchmark_results.py --benchmark swebench
    python3 analysis/aggregate_benchmark_results.py --source-root /path/to/terminalbench \
        --benchmark terminalbench
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "outcomes"
BENCHMARKS = ("swebench", "terminalbench")
INFINITE_BUDGET = 999_999_999

# Keep the short names used in the canonical ICLR cell names.  The raw
# primitive is retained separately because the runner uses implementation
# names such as ``structured_summarize``.
CONDITION_TO_PRIMITIVE = {
    "full-context": "fc",
    "truncation": "tr",
    "summarization": "su-full",
    "summarization-partial": "su-partial",
    "structured-summarize": "ss",
    "structured-summarize-partial": "ss-partial",
    "tool-result-clear": "trc",
    "trc-su": "trc-su",
    "trc-ss": "trc-ss",
    "online-trc": "otrc",
    "otrc-tr": "otrc-tr",
    "otrc-su-partial": "otrc-su-partial",
    "otrc-ss-partial": "otrc-ss-partial",
}

FIELDNAMES = [
    "benchmark", "experiment_section", "model_key", "model", "cell",
    "source_file", "task_name", "condition", "primitive", "raw_primitive",
    "token_budget", "depth", "run_num", "resolved", "failure_mode",
    "execution_state", "agent_started", "pre_agent_failure", "returncode",
    "seeded_from",
    "exit_status", "patch_generated", "submission_generated", "reward",
    "step_count", "total_tokens", "total_prompt_tokens",
    "total_completion_tokens", "latency_e2e_s", "latency_llm_s",
    "compression_events", "trc_fallback_events", "online_trc_clears",
]


def records(path: Path) -> list[dict[str, Any]]:
    """Load either a bare list or a wrapper with a ``results`` list."""
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        payload = payload.get("results", [])
    if not isinstance(payload, list):
        raise ValueError("expected a list of run records")
    return [row for row in payload if isinstance(row, dict)]


def failure_mode(row: dict[str, Any]) -> str:
    if row.get("resolved") is True:
        return "resolved"
    status = str(row.get("exit_status") or "")
    if status.startswith("LimitsExceeded"):
        return "limits_exceeded"
    if row.get("patch_generated") and status == "Submitted":
        return "submitted_unresolved"
    if not row.get("patch_generated"):
        return "silent_crash"
    return "other"


def execution_state(row: dict[str, Any]) -> str:
    """Classify whether this row represents an actual agent attempt."""
    n_calls = row.get("n_calls") or 0
    total_tokens = row.get("total_tokens") or 0
    try:
        no_agent_activity = float(n_calls) == 0 and float(total_tokens) == 0
    except (TypeError, ValueError):
        no_agent_activity = False

    # ``seeded_from`` is a pointer to a source record absent from this cell,
    # not evidence that an agent run failed.
    if no_agent_activity and row.get("seeded_from"):
        return "seeded_placeholder"
    if no_agent_activity and row.get("returncode") not in (None, 0):
        return "pre_agent_failure"
    if no_agent_activity:
        return "zero_step_unknown"
    return "agent_started"


def metadata(path: Path, source_root: Path) -> tuple[str, str, str]:
    """Extract section/model/cell without assuming a fixed TB nesting depth."""
    parts = path.relative_to(source_root).parts[:-1]
    if len(parts) < 3:
        return ("", "", "")
    # Both result trees end in .../<section>/<model>/<cell>/experiment_results.json.
    # Terminal-Bench may have extra namespace components before that suffix.
    return ("/".join(parts[:-2]), parts[-2], parts[-1])


def normalized_row(
    row: dict[str, Any], benchmark: str, source_root: Path, source: Path
) -> dict[str, Any]:
    section, model_key, cell = metadata(source, source_root)
    condition = row.get("condition") or ""
    budget = row.get("budget")
    state = execution_state(row)
    return {
        "benchmark": benchmark,
        "experiment_section": section,
        "model_key": model_key,
        "model": row.get("model") or row.get("agent_model") or model_key,
        "cell": cell,
        "source_file": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "task_name": row.get("instance_id") or row.get("task_name") or "",
        "condition": condition,
        "primitive": CONDITION_TO_PRIMITIVE.get(condition, row.get("primitive") or ""),
        "raw_primitive": row.get("primitive") or "",
        "token_budget": budget,
        "depth": row.get("compression_ratio", 0.5),
        "run_num": row.get("run_num"),
        "resolved": row.get("resolved"),
        "failure_mode": failure_mode(row),
        "execution_state": state,
        "agent_started": state == "agent_started",
        "pre_agent_failure": state == "pre_agent_failure",
        "returncode": row.get("returncode"),
        "seeded_from": row.get("seeded_from") or "",
        "exit_status": row.get("exit_status") or "",
        "patch_generated": row.get("patch_generated"),
        "submission_generated": row.get("submission_generated"),
        "reward": row.get("reward"),
        "step_count": row.get("n_calls"),
        "total_tokens": row.get("total_tokens"),
        "total_prompt_tokens": row.get("total_prompt_tokens"),
        "total_completion_tokens": row.get("total_completion_tokens"),
        "latency_e2e_s": row.get("e2e_latency_s"),
        "latency_llm_s": row.get("llm_latency_s"),
        "compression_events": row.get("compression_events", 0),
        "trc_fallback_events": row.get("trc_truncation_fallback_events", 0),
        "online_trc_clears": row.get("online_trc_clears", 0),
    }


def build(benchmark: str, source_root: Path, output: Path) -> int:
    # A benchmark may not have been copied to this machine yet.  In that case
    # preserve any previously aggregated CSV rather than replacing it with an
    # empty header-only file.
    if not source_root.is_dir():
        print(f"{benchmark}: skipped; input directory does not exist: {source_root}")
        return 0

    rows: list[dict[str, Any]] = []
    bad_sources: list[str] = []
    for source in sorted(source_root.glob("**/experiment_results.json")):
        try:
            rows.extend(normalized_row(row, benchmark, source_root, source) for row in records(source))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            bad_sources.append(f"{source}: {exc}")

    rows.sort(key=lambda r: (
        r["experiment_section"], r["model_key"], r["cell"], r["task_name"],
        str(r["run_num"]), r["source_file"],
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{benchmark}: wrote {len(rows):,} runs from {len(list(source_root.glob('**/experiment_results.json'))):,} files to {output}")
    for message in bad_sources:
        print(f"WARNING: skipped {message}")
    return len(bad_sources)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=BENCHMARKS, action="append",
                        help="benchmark to build (default: both)")
    parser.add_argument("--source-root", type=Path,
                        help="override the input root; requires exactly one --benchmark")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    benchmarks = args.benchmark or list(BENCHMARKS)
    if args.source_root and len(benchmarks) != 1:
        raise SystemExit("--source-root requires exactly one --benchmark")
    errors = 0
    for benchmark in benchmarks:
        source_root = args.source_root or ROOT / "ICLR_results" / benchmark
        errors += build(benchmark, source_root, args.output_dir / f"{benchmark}_outcomes.csv")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
