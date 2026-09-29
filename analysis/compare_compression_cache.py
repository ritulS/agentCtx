#!/usr/bin/env python3
"""Export observed cache changes from token_log.json files as CSV.

Usage: python analysis/compare_compression_cache.py RUN_OR_RESULTS_DIR --output /tmp/cache.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentctx.compression.cache_metrics import compression_cache_comparisons


FIELDS = [
    "token_log", "before_step", "after_step", "compression_kinds", "compression_count", "status",
    "before_status", "after_status", "before_prompt_tokens", "after_prompt_tokens",
    "before_cached_tokens", "after_cached_tokens", "cached_tokens_drop",
    "before_cache_hit_rate", "after_cache_hit_rate", "cache_hit_rate_drop_pp",
    "before_uncached_prompt_tokens", "after_uncached_prompt_tokens", "uncached_prompt_tokens_increase",
    "before_completion_tokens", "before_processed_tokens", "reuse_ratio_vs_before_processed",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="token_log.json files or directories to search recursively")
    parser.add_argument("--output", type=Path, help="CSV destination (default: stdout); null values are blank")
    args = parser.parse_args()
    paths = set()
    for path in args.paths:
        if not path.exists():
            parser.error(f"path does not exist: {path}")
        paths.update(p.resolve() for p in (path.rglob("token_log.json") if path.is_dir() else [path]))
    if not paths:
        parser.error("no token_log.json files found")
    if args.output and args.output.resolve() in paths:
        parser.error("output must not overwrite an input token log")
    rows = []
    skipped = 0
    for path in sorted(paths):
        try:
            log = json.loads(path.read_text())
            comparisons = compression_cache_comparisons(log)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # Killed runs can leave truncated logs; report and keep exporting the rest.
            print(f"warning: skipping unreadable token log {path}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        for comparison in comparisons:
            rows.append({"token_log": str(path), **comparison,
                         "compression_kinds": "+".join(comparison["compression_kinds"])})
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    stream = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            stream.close()
    comparable = sum(r["status"] == "available" for r in rows)
    print(f"{len(paths)} logs ({skipped} skipped); {len(rows)} compression boundaries; "
          f"{comparable} with comparable cache counts. "
          "Positive drop means less cache reuse; blank means unknown. "
          "Adjacent-call changes do not isolate compression's causal effect.", file=sys.stderr)


if __name__ == "__main__":
    main()
