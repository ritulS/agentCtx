"""Context-window memory primitives for mini-swe-agent.

Imported from mini-swe-agent/src/minisweagent/agents/default.py via a late
import (PYTHONPATH includes the agentCtx repo root, set by run_experiment.py).

Parameters
----------
token_budget  : int   — MSWEA_TOKEN_BUDGET env var
                        When the accumulated prompt tokens exceed this value,
                        the selected primitive fires.
compression_r : float — fixed at 0.5
                        Target = budget * r tokens after compression.
                        e.g. budget=50 000, r=0.5  →  compress down to 25 000 tokens.

Protected messages (never compressed)
  index 0 — system prompt
  index 1 — first user message (the task statement)

Compressible: messages[2:]

Truncation
  Drop messages from the front of the compressible window until the total
  estimated token count of (protected + remaining) ≤ target_tokens.
  Always keeps at least the last message in the compressible window.

Summarization
  Make a single LLM call asking for a summary of the compressible window
  targeting (target_tokens - protected_tokens) compressible tokens worth of text.
  Replaces the entire compressible window with one summary message.

Token log (MSWEA_TOKEN_LOG_PATH)
  Written after every agent step.  Schema:
    total_prompt_tokens, total_completion_tokens, total_tokens,
    total_latency_s, mean_latency_s,
    compression_events, total_tokens_saved, mean_compression_ratio
"""

import json
import os
from pathlib import Path

COMPRESSION_RATIO = 0.5
N_PROTECTED       = 2   # system + first-user (task) messages are never compressed


# ── Token counting ─────────────────────────────────────────────────────────────

def count_tokens(messages: list[dict]) -> int:
    """Approximate token count: 1 token ≈ 4 characters."""
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(str(block.get("text", ""))) // 4
        else:
            total += len(str(content)) // 4
    return max(total, 0)


# ── Primitives ─────────────────────────────────────────────────────────────────

def truncate(messages: list[dict], target_tokens: int) -> tuple[list[dict], int]:
    """Drop messages from the front of the compressible window.

    Keeps dropping until estimated total ≤ target_tokens, or only the last
    compressible message remains.

    Returns (new_message_list, tokens_saved).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0

    protected    = messages[:N_PROTECTED]
    compressible = list(messages[N_PROTECTED:])
    tokens_before = count_tokens(messages)

    # Drop from the front until we are at or below target
    while len(compressible) > 1 and count_tokens(protected + compressible) > target_tokens:
        compressible.pop(0)

    new_messages  = protected + compressible
    tokens_after  = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after)


def summarize(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int]:
    """Summarize the compressible window with one LLM call.

    The summary targets (target_tokens - count_tokens(protected)) tokens worth
    of compressible content, approximated as target_words.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0

    protected    = messages[:N_PROTECTED]
    compressible = messages[N_PROTECTED:]
    tokens_before = count_tokens(messages)

    # Build plain-text dump
    history_text = ""
    for msg in compressible:
        role    = msg.get("role", "unknown")
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
            )
        history_text += f"[{role}]:\n{content}\n\n"

    # Target compressible tokens = target_tokens minus what the protected msgs use
    protected_tokens  = count_tokens(protected)
    compress_target   = max(50, target_tokens - protected_tokens)
    # 1 token ≈ 4 chars ≈ 0.75 words (rough heuristic)
    target_words      = max(30, int(compress_target * 0.75))

    summary_prompt = [
        model.format_message(
            role="system",
            content=(
                "You are a concise summarizer for a software engineering agent. "
                "Summarize the following conversation history, preserving all file paths, "
                "command outputs, error messages, key findings, and the current task state. "
                "Be factual and brief."
            ),
        ),
        model.format_message(
            role="user",
            content=(
                f"Summarize this agent conversation history in approximately "
                f"{target_words} words:\n\n{history_text}"
            ),
        ),
    ]

    response     = model.query(summary_prompt)
    summary_text = response.get("content") or ""
    if isinstance(summary_text, list):
        summary_text = " ".join(
            block.get("text", "")
            for block in summary_text
            if isinstance(block, dict)
        )

    # Collect actual tokens used by the summarization call
    extra = response.get("extra", {})
    resp  = extra.get("response", {})
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    prompt_toks     = usage.get("prompt_tokens", 0) or 0
    completion_toks = usage.get("completion_tokens", 0) or 0

    summary_msg  = model.format_message(
        role="user",
        content=f"[COMPRESSED HISTORY SUMMARY]\n{summary_text}\n[END SUMMARY]",
    )
    new_messages  = protected + [summary_msg]
    tokens_after  = count_tokens(new_messages)

    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks


# ── Token log ──────────────────────────────────────────────────────────────────

def write_token_log(agent) -> None:
    """Write accumulated token stats to MSWEA_TOKEN_LOG_PATH (if set)."""
    log_path = os.environ.get("MSWEA_TOKEN_LOG_PATH")
    if not log_path:
        return

    n = len(agent._mem_call_latencies)
    data = {
        "total_prompt_tokens":     agent._mem_prompt_tokens,
        "total_completion_tokens": agent._mem_completion_tokens,
        "total_tokens":            agent._mem_prompt_tokens + agent._mem_completion_tokens,
        "total_latency_s":         round(agent._mem_total_latency, 3),
        "mean_latency_s":          round(agent._mem_total_latency / n, 3) if n else 0.0,
        "compression_events":      agent._mem_compression_events,
        "total_tokens_saved":      agent._mem_tokens_saved,
        "mean_compression_ratio":  (
            sum(agent._mem_compression_ratios) / len(agent._mem_compression_ratios)
            if agent._mem_compression_ratios else 1.0
        ),
    }
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).write_text(json.dumps(data, indent=2))
