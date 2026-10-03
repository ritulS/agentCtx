"""Per-call cache usage and observed changes across compression boundaries.

These are adjacent-call observations, not a counterfactual estimate of the
effect of compression. Eviction, other clients and prompt growth also matter.
"""
from __future__ import annotations


def cache_usage(usage: dict) -> dict:
    """Normalize OpenAI-compatible usage without turning missing data into zero."""
    details = usage.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    prompt = usage.get("prompt_tokens")
    status = "unavailable" if cached is None else "available"
    if cached is not None and (type(cached) is not int or cached < 0):
        cached, status = None, "invalid"
    valid_prompt = type(prompt) is int and prompt >= 0
    if cached is not None and valid_prompt and cached > prompt:
        cached, status = None, "invalid"
    return {
        "cached_tokens": cached,
        "uncached_prompt_tokens": prompt - cached if valid_prompt and cached is not None else None,
        "cache_hit_rate": cached / prompt if valid_prompt and prompt > 0 and cached is not None else None,
        "cache_usage_status": status,
        "cache_usage_source": "usage.prompt_tokens_details.cached_tokens" if status == "available" else None,
    }


def _count(value) -> bool:
    return type(value) is int and value >= 0


def compression_cache_comparisons(log: dict) -> list[dict]:
    """Compare call s with s+1: legacy compression steps count completed calls.

    Group all changes before the same call: no inference occurred between them,
    so their individual cache effects cannot be separated. Missing/failed calls
    are never skipped in favor of a more distant call with available usage.

    ``before_processed_tokens`` is what the server processed for call s
    (prompt plus completion) when that call completed normally; it is null
    when call s failed, because a rejected completion never enters the history
    and so cannot be reused. ``reuse_ratio_vs_before_processed`` divides the
    hit of call s+1 by it. This is a reference ratio, not a survival rate: the
    hit may include blocks written by other requests (concurrent runs sharing
    the same prefix, summarizer calls), so it can exceed 1, and block rounding
    or eviction can lower it without any compression damage.
    """
    boundaries: dict[int, list[str]] = {}
    for step in log.get("compression_event_steps", []):
        boundaries.setdefault(step, []).append("budget")
    for event in log.get("online_trc_flags", []):
        if isinstance(event, dict) and type(event.get("step")) is int:
            boundaries.setdefault(event["step"], []).append("online_trc")
    calls = {r["step"]: r for r in log.get("model_call_records", [])}
    rows = []
    for step, kinds in sorted(boundaries.items()):
        before, after = calls.get(step), calls.get(step + 1)
        row = {
            "before_step": step if step > 0 else None,
            "after_step": step + 1,
            "compression_kinds": sorted(set(kinds)),
            "compression_count": len(kinds),
            "status": "available",
        }
        for label, call in (("before", before), ("after", after)):
            for key in ("status", "prompt_tokens", "cached_tokens", "uncached_prompt_tokens", "cache_hit_rate"):
                row[f"{label}_{key}"] = call.get(key) if call else None
        row["before_completion_tokens"] = before.get("completion_tokens") if before else None
        if before is None:
            row["status"] = "missing_before_call"
        elif after is None:
            row["status"] = "missing_after_call"
        elif before.get("cached_tokens") is None or after.get("cached_tokens") is None:
            row["status"] = "missing_cache_usage"
        for field, key, scale in (
            ("cached_tokens_drop", "cached_tokens", 1),
            ("cache_hit_rate_drop_pp", "cache_hit_rate", 100),
        ):
            b, a = row[f"before_{key}"], row[f"after_{key}"]
            row[field] = (b - a) * scale if b is not None and a is not None else None
        b, a = row["before_uncached_prompt_tokens"], row["after_uncached_prompt_tokens"]
        row["uncached_prompt_tokens_increase"] = a - b if b is not None and a is not None else None
        bp, bc = row["before_prompt_tokens"], row["before_completion_tokens"]
        processed = bp + bc if row["before_status"] == "ok" and _count(bp) and _count(bc) else None
        row["before_processed_tokens"] = processed
        row["reuse_ratio_vs_before_processed"] = (
            row["after_cached_tokens"] / processed
            if processed and row["after_cached_tokens"] is not None else None
        )
        rows.append(row)
    return rows
