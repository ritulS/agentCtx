"""KV block ownership snapshots and per-agent-step export (no vLLM dependency).

Bytes describe occupied slots in the preallocated cache pool of ONE model
worker, including padding, not extra CUDA allocations or a GPU-memory delta.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re


def block_bytes(config, parallel_config) -> tuple[int | None, str]:
    # The scheduler receives a representative worker's config. With pipeline
    # parallelism workers can have different layer counts, so do not guess.
    if getattr(parallel_config, "pipeline_parallel_size", 1) != 1:
        return None, "unsupported_pipeline_parallelism"
    if config.num_blocks <= 0:
        return None, "invalid_capacity"
    sizes = [tensor.size for tensor in config.kv_cache_tensors]
    if not sizes or any(size % config.num_blocks for size in sizes):
        return None, "unavailable_layout"
    return sum(size // config.num_blocks for size in sizes), "available"


def ownership_snapshot(manager, request_ids, bytes_per_block):
    """Count unique physical blocks, including across hybrid cache groups.

    Use request-to-block mappings rather than ref_cnt alone: repeated references
    within one request must not be mistaken for sharing between requests.
    Null blocks (sliding-window padding) are never charged to a request.
    """
    allocations = {}
    owners = defaultdict(set)
    for request_id in request_ids:
        blocks = {
            block.block_id
            for group in manager.get_blocks(request_id).blocks
            for block in group
            if not block.is_null
        }
        allocations[request_id] = blocks
        for block_id in blocks:
            owners[block_id].add(request_id)
    result = {}
    for request_id, blocks in allocations.items():
        exclusive = sum(len(owners[b]) == 1 for b in blocks)
        shared = len(blocks) - exclusive
        row = {"exclusive_blocks": exclusive, "shared_blocks": shared,
               "total_blocks": len(blocks)}
        for name in ("exclusive", "shared", "total"):
            row[f"{name}_bytes_per_worker"] = (
                row[f"{name}_blocks"] * bytes_per_block
                if bytes_per_block is not None else None
            )
        result[request_id] = row
    return result


def request_matches(response_id: str, request_id: str) -> bool:
    """vLLM V1 single-output chat/completion IDs, with optional internal salt.

    Completion serving appends -0 for its first prompt; input_processor can
    append an eight-hex-digit salt. Do not use a loose startswith match.
    Multiple prompts/outputs are intentionally not merged into one agent step.
    """
    suffix = r"(?:-[0-9a-f]{8})?"
    if response_id.startswith("cmpl-"):
        suffix = r"(?:-0)?" + suffix
    return re.fullmatch(re.escape(response_id) + suffix, request_id) is not None


MEASUREMENT_NOTES = [
    "Bytes are per model worker (one tensor-parallel shard): multiply by "
    "metadata.tensor_parallel_size for the GPU-wide figure; pipeline parallelism "
    "leaves bytes null.",
    "shared means simultaneous ownership of a physical block by two or more "
    "live requests at that instant. Blocks reused from an already finished "
    "request (e.g. the previous step of the same task) count as exclusive, and "
    "cached-but-unowned blocks are charged to nobody.",
    "peak_exclusive_*, peak_shared_* and peak_total_* are independent maxima "
    "over the request lifetime and need not occur at the same instant; use "
    "samples for a time-resolved view instead of adding the peaks.",
    "Requests are not experiment tasks: a shared block's other owner may be "
    "another task, this task's summarizer request, or an unrelated client.",
]

_PEAK_FIELDS = ("exclusive_bytes_per_worker", "shared_bytes_per_worker",
                "total_bytes_per_worker", "exclusive_blocks", "shared_blocks", "total_blocks")


def _load_matches(trace_dir: Path, response_ids: set[str]) -> tuple[dict, list[str]]:
    """Trace records grouped by (response id, trace file, request id)."""
    matches = defaultdict(dict)
    warnings = []
    for path in sorted(trace_dir.glob("kv-cache-*.jsonl")):
        metadata = None
        matched_ids = {}
        with path.open() as stream:
            for number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"{path.name}:{number}: incomplete or invalid record")
                    continue
                if record.get("type") == "metadata":
                    metadata = record
                    continue
                rid = record.get("request_id")
                if not isinstance(rid, str):
                    if record.get("type") == "error":
                        warnings.append(f"{path.name}:{number}: {record.get('error')}")
                    continue
                if rid not in matched_ids:
                    matched_ids[rid] = [r for r in response_ids if request_matches(r, rid)]
                for response_id in matched_ids[rid]:
                    entry = matches[response_id].setdefault((path.name, rid), {
                        "request_id": rid, "trace_file": path.name,
                        "metadata": metadata, "samples": [], "finished": False,
                    })
                    if record.get("type") == "snapshot":
                        entry["samples"].append(record)
                    elif record.get("type") == "finished":
                        entry["finished"] = True
                        entry["finished_at"] = record["time"]
    return matches, warnings


def _join(row: dict, response_id, matches: dict) -> dict:
    """Attach the unique matching trace (if any) and its per-field peaks."""
    row["response_id"] = response_id
    candidates = list(matches.get(response_id, {}).values())
    if not response_id:
        row["status"] = "missing_response_id"
    elif not candidates:
        row["status"] = "not_found"
    elif len(candidates) != 1:
        row["status"] = "ambiguous_request"
    else:
        entry = candidates[0]
        row.update(entry)
        samples = entry["samples"]
        row["status"] = "complete" if entry["finished"] else "partial"
        if not samples:
            row["status"] = "no_samples"
        for field in _PEAK_FIELDS:
            values = [s[field] for s in samples if s.get(field) is not None]
            row[f"peak_{field}"] = max(values) if values else None
    return row


def export_steps(run_dir: Path, trace_dir: Path) -> dict:
    """Join agent model calls and summarizer calls to their KV traces.

    ``steps`` holds one row per agent model call (token_log.json
    ``model_call_records``). ``summary_calls`` holds one row per summarizer
    query (``summary_outcomes[].response_ids``, one per attempt, rejected
    attempts included); those requests are only found when the summarizer was
    served by the traced vLLM. Both lists are kept apart on purpose: a
    summarizer request is not an agent step, and it runs between two steps.
    """
    log = json.loads((run_dir / "token_log.json").read_text())
    calls = log.get("model_call_records", [])
    outcomes = log.get("summary_outcomes", [])
    response_ids = {c["response_id"] for c in calls if c.get("response_id")}
    response_ids |= {r for o in outcomes for r in (o.get("response_ids") or []) if r}
    matches, warnings = _load_matches(trace_dir, response_ids)
    rows = [_join({"step": call["step"]}, call.get("response_id"), matches) for call in calls]
    summary_rows = []
    for index, outcome in enumerate(outcomes):
        ids = outcome.get("response_ids")
        if ids is None:
            # Logs written before response ids were recorded: report, never infer.
            warnings.append(f"summary_outcomes[{index}] (step {outcome.get('step')}): "
                            "no response_ids recorded")
            continue
        event_accepted = bool(outcome.get("accepted"))
        for attempt, response_id in enumerate(ids, 1):
            summary_rows.append(_join({
                "event_index": index, "step": outcome.get("step"),
                "primitive": outcome.get("primitive"), "attempt": attempt,
                # Only the last query of an accepted event produced the summary;
                # earlier rows are rejected attempts (see rejections[]).
                "attempt_accepted": event_accepted and attempt == len(ids),
                "event_accepted": event_accepted,
                "interrupted": outcome.get("interrupted"),
            }, response_id, matches))
    return {"schema_version": 2, "scope": "per_request_per_worker",
            "notes": list(MEASUREMENT_NOTES), "warnings": warnings,
            "steps": rows, "summary_calls": summary_rows}


def main():
    parser = argparse.ArgumentParser(description="Join vLLM KV ownership traces to agent steps.")
    parser.add_argument("run_dir", type=Path, help="Directory containing token_log.json")
    parser.add_argument("--trace-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.trace_dir.is_dir():
        parser.error("--trace-dir must be an existing trace directory")
    data = export_steps(args.run_dir, args.trace_dir)
    output = args.run_dir / "kv_cache_steps.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(output)
    print(output)


if __name__ == "__main__":
    main()
