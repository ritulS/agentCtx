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
import re
import time
from pathlib import Path

import tiktoken

COMPRESSION_RATIO = float(os.environ.get("MSWEA_COMPRESSION_RATIO", "0.5"))
N_PROTECTED       = 2   # system + first-user (task) messages are never compressed
KEEP_RECENT       = 3   # TRC: preserve the last N tool-result turns (mirrors Anthropic's default)

# cl100k_base is accurate to ~5% for code+English across all major models (GPT-4,
# Claude, Qwen, Llama, etc.).  Loading the exact Qwen tokenizer would require
# transformers — unnecessary overhead for a budget trigger.
_ENCODER = tiktoken.get_encoding("cl100k_base")


# ── Token counting ─────────────────────────────────────────────────────────────

def count_tokens(messages: list[dict]) -> int:
    """Token count using tiktoken cl100k_base (accurate to ~5% across models)."""
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(_ENCODER.encode(str(block.get("text", ""))))
        else:
            total += len(_ENCODER.encode(str(content)))
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
) -> tuple[list[dict], int, int, int, float]:
    """Summarize the compressible window with one LLM call.

    The summary targets (target_tokens - count_tokens(protected)) tokens worth
    of compressible content, approximated as target_words.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

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
                "You are summarizing an agent's work history to free up context window space. "
                "Your output will replace the conversation history — the agent will only see "
                "your summary, so it must be complete enough to continue the task."
            ),
        ),
        model.format_message(
            role="user",
            content=(
                f"Summarize the following agent conversation history in approximately "
                f"{target_words} words. Your summary MUST include all of:\n"
                f"1. Current task objective and progress made so far\n"
                f"2. Files examined and any modifications made (include exact file paths)\n"
                f"3. Key observations, errors encountered, and decisions taken\n"
                f"4. Current state — what has been done and what remains\n\n"
                f"Preserve exact file paths, error messages, and code snippets that are "
                f"likely still relevant. Be factual and concise.\n\n"
                f"{history_text}"
            ),
        ),
    ]

    _t0          = time.time()
    response     = model.query(summary_prompt)
    latency_s    = time.time() - _t0
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

    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s


def structured_summarize(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int, float]:
    """Summarize the compressible window using a structured schema.

    Produces a section-headed summary (Task / Files Modified / Files Examined /
    Execution Anchors / Current State) that preserves the information most
    critical for a coding agent to continue its work.

    Falls through to truncate() if the LLM output still exceeds target.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

    protected     = messages[:N_PROTECTED]
    compressible  = messages[N_PROTECTED:]
    tokens_before = count_tokens(messages)

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

    protected_tokens = count_tokens(protected)
    compress_target  = max(50, target_tokens - protected_tokens)
    target_words     = max(30, int(compress_target * 0.75))

    summary_prompt = [
        model.format_message(
            role="system",
            content=(
                "You are compressing an agent's working memory to free up context window space. "
                "Your output will REPLACE the entire conversation history — the agent will only "
                "see your summary. It must contain everything needed to continue the task without "
                "any other context."
            ),
        ),
        model.format_message(
            role="user",
            content=(
                f"Produce a structured summary of the agent conversation below in approximately "
                f"{target_words} words total. Use EXACTLY this format and section order:\n\n"
                f"[CONTEXT SUMMARY]\n"
                f"## Task\n"
                f"<One sentence: what the task is asking for.>\n\n"
                f"## Files Modified\n"
                f"<Each file the agent has written or edited. Format: path — what changed and why. "
                f"If none yet, write 'None'.>\n\n"
                f"## Files Examined\n"
                f"<Each file the agent has read. Format: path — key observation. "
                f"If none yet, write 'None'.>\n\n"
                f"## Execution Anchors\n"
                f"<Exact commands run, test results, error messages, or shell output that the agent "
                f"will need to reference going forward. Quote verbatim where possible.>\n\n"
                f"## Current State\n"
                f"<What has been done, what has NOT been done, and the immediate next step.>\n"
                f"[END CONTEXT SUMMARY]\n\n"
                f"Rules:\n"
                f"- Preserve exact file paths, line numbers, error strings, and symbol names.\n"
                f"- Do not speculate or add information not present in the history.\n"
                f"- Do not add any text outside the [CONTEXT SUMMARY] block.\n\n"
                f"Conversation history:\n{history_text}"
            ),
        ),
    ]

    _t0       = time.time()
    response  = model.query(summary_prompt)
    latency_s = time.time() - _t0

    summary_text = response.get("content") or ""
    if isinstance(summary_text, list):
        summary_text = " ".join(
            block.get("text", "")
            for block in summary_text
            if isinstance(block, dict)
        )

    extra = response.get("extra", {})
    resp  = extra.get("response", {})
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    prompt_toks     = usage.get("prompt_tokens", 0) or 0
    completion_toks = usage.get("completion_tokens", 0) or 0

    summary_msg  = model.format_message(
        role="user",
        content=summary_text,
    )
    new_messages = protected + [summary_msg]

    # Fallback: if model over-generated past target, truncate the summary itself
    if count_tokens(new_messages) > target_tokens:
        new_messages, _ = truncate(new_messages, target_tokens)

    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s


def _fit_tail(messages: list[dict], tail_budget: int) -> int:
    """Find the largest k such that count_tokens(messages[k:]) <= tail_budget.

    Walks backward from the end accumulating message tokens until adding the
    next-oldest would exceed tail_budget. Always returns k <= len(messages),
    and never goes below N_PROTECTED.

    Returns k — messages[N_PROTECTED:k] is the head (to compress);
                messages[k:] is the budget-fitting tail (kept verbatim).
    """
    if tail_budget <= 0:
        return len(messages)
    k = len(messages)
    tail_tokens = 0
    while k > N_PROTECTED:
        msg_tokens = count_tokens([messages[k - 1]])
        if tail_tokens + msg_tokens > tail_budget:
            break
        tail_tokens += msg_tokens
        k -= 1
    return k


def summarize_partial(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int, float]:
    """SU-partial: summarize only the older head, keep the budget-fitting tail verbatim.

    Splits the available compression budget 50/50 between the summary and the tail:
      tail_budget    = (target_tokens - protected_tokens) // 2
      summary_target = (target_tokens - protected_tokens) - tail_budget

    1. Find largest k such that messages[k:] fits in tail_budget (tail kept).
    2. Summarize messages[N_PROTECTED:k] via the existing summarize() LLM call.
    3. Combine: protected + [summary_msg] + messages[k:].

    If the head ends up empty (k <= N_PROTECTED) — i.e. the tail alone already
    exceeds the budget — fall back to truncate to enforce target_tokens.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

    tokens_before = count_tokens(messages)
    if tokens_before <= target_tokens:
        return messages, 0, 0, 0, 0.0

    protected        = messages[:N_PROTECTED]
    protected_tokens = count_tokens(protected)
    available        = max(0, target_tokens - protected_tokens)
    tail_budget      = available // 2
    summary_target   = available - tail_budget

    k = _fit_tail(messages, tail_budget)

    # No room for any head to summarize → fall back to truncate
    if k <= N_PROTECTED:
        new_messages, _ = truncate(messages, target_tokens)
        return new_messages, max(0, tokens_before - count_tokens(new_messages)), 0, 0, 0.0

    # Summarize the head: build (protected + head_window) then call summarize()
    head_window = list(messages[N_PROTECTED:k])
    head_input  = protected + head_window
    head_summarized, _, pt, ct, lat = summarize(
        head_input, model, protected_tokens + summary_target
    )
    # head_summarized = protected + [summary_msg]; append the tail
    new_messages = list(head_summarized) + list(messages[k:])

    # Safety net: if summary over-generated and we're still over target, truncate
    if count_tokens(new_messages) > target_tokens:
        new_messages, _ = truncate(new_messages, target_tokens)

    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), pt, ct, lat


def structured_summarize_partial(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int, float]:
    """SS-partial: structured-summarize the older head, keep the budget-fitting tail verbatim.

    Same algorithm as summarize_partial(), but uses structured_summarize() for the head.
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

    tokens_before = count_tokens(messages)
    if tokens_before <= target_tokens:
        return messages, 0, 0, 0, 0.0

    protected        = messages[:N_PROTECTED]
    protected_tokens = count_tokens(protected)
    available        = max(0, target_tokens - protected_tokens)
    tail_budget      = available // 2
    summary_target   = available - tail_budget

    k = _fit_tail(messages, tail_budget)

    if k <= N_PROTECTED:
        new_messages, _ = truncate(messages, target_tokens)
        return new_messages, max(0, tokens_before - count_tokens(new_messages)), 0, 0, 0.0

    head_input = protected + list(messages[N_PROTECTED:k])
    head_summarized, _, pt, ct, lat = structured_summarize(
        head_input, model, protected_tokens + summary_target
    )
    new_messages = list(head_summarized) + list(messages[k:])

    if count_tokens(new_messages) > target_tokens:
        new_messages, _ = truncate(new_messages, target_tokens)

    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), pt, ct, lat


def tool_result_clear(
    messages: list[dict],
    target_tokens: int,
    fallback_truncate: bool = True,
) -> tuple[list[dict], int]:
    """Clear bash tool output bodies from old user turns to reduce context size.

    Works front-to-back (oldest first) through compressible user-role messages,
    replacing verbose output with a stub. Preserves the last KEEP_RECENT tool
    results (the agent is actively working with these). If clearing all eligible
    tool outputs is still insufficient and fallback_truncate=True, falls back to
    truncate(). Set fallback_truncate=False when a caller will apply a second
    primitive (e.g. summarization) after TRC.

    Returns (new_message_list, tokens_saved, used_fallback).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0

    if count_tokens(messages) <= target_tokens:
        return messages, 0

    new_messages = list(messages)
    tokens_saved = 0

    _STUB_PREFIX      = "[TOOL OUTPUT CLEARED"
    _SUMMARY_PREFIXES = ("[CONTEXT SUMMARY", "[COMPRESSED HISTORY")

    def _is_clearable(msg: dict) -> bool:
        if msg.get("role") != "user":
            return False
        content = msg.get("content") or ""
        if isinstance(content, list):
            return False
        return (
            not content.startswith(_STUB_PREFIX)
            and not content.startswith(_SUMMARY_PREFIXES)
        )

    # Indices into new_messages for clearable turns (compressible window only)
    compressible_user_indices = [
        i for i in range(N_PROTECTED, len(new_messages))
        if _is_clearable(new_messages[i])
    ]

    # Respect KEEP_RECENT — never clear the last N tool-result turns
    eligible = compressible_user_indices[:-KEEP_RECENT] if len(compressible_user_indices) > KEEP_RECENT else []

    for idx in eligible:
        original_content = new_messages[idx].get("content", "")
        n_tokens = len(_ENCODER.encode(str(original_content)))
        step_k   = (idx - N_PROTECTED) // 2  # approximate step number (2 msgs per step)
        new_messages[idx] = {
            **new_messages[idx],
            "content": f"[TOOL OUTPUT CLEARED — {n_tokens} tokens — step {step_k}]",
        }
        tokens_saved += n_tokens
        if count_tokens(new_messages) <= target_tokens:
            break

    # Fallback: if still above target after clearing all eligible outputs
    used_fallback = False
    if fallback_truncate and count_tokens(new_messages) > target_tokens:
        new_messages, extra_saved = truncate(new_messages, target_tokens)
        tokens_saved  += extra_saved
        used_fallback  = True

    return new_messages, tokens_saved, used_fallback


# ── Scored TRC helpers ─────────────────────────────────────────────────────────

STRC_SCORE_FLOOR  = 0.6    # hard floor — never clear a result with score ≥ this
_STRC_SIZE_NORM   = 2000   # chars at which size contribution saturates to 1.0
_STRC_CITE_BOOST  = 0.10   # score increment per citing assistant message
_STRC_MAX_BOOST   = 0.30   # cap on total citation contribution

# Type weights calibrated from Qwen 15K reference-rate analysis
# (git 46.7 %, file_read 14.0 %, search 15.4 %, test 11.6 %, install 4.2 %)
_STRC_TYPE_WEIGHTS: dict[str, float] = {
    "git":     0.80,
    "file":    0.70,
    "search":  0.40,
    "test":    0.30,
    "install": 0.10,
    "other":   0.25,
}

_STRC_BASH_RE   = re.compile(r"```mswea_bash_command\s*(.*?)\s*```", re.DOTALL)
_STRC_ENTITY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./\-]{7,}")


def _strc_get_cmd(msg: dict) -> str:
    """Extract the bash command text from an assistant message."""
    content = msg.get("content") or ""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                content = block.get("text", "")
                break
    m = _STRC_BASH_RE.search(str(content))
    return m.group(1).strip() if m else str(content)[:100]


def _strc_classify_cmd(cmd: str) -> str:
    c = cmd.lower()
    if "git " in c:
        return "git"
    if any(k in c for k in ("cat ", " head ", " tail ", "less ", "open(", "read(")):
        return "file"
    if any(k in c for k in ("grep ", "find ", " rg ", " ag ", "glob ")):
        return "search"
    if any(k in c for k in ("pytest", "python -m ", "unittest")):
        return "test"
    if any(k in c for k in ("pip ", "pip3 ", "apt-get ", "echo ", "which ")):
        return "install"
    return "other"


def _strc_citation_strings(content: str) -> frozenset:
    """Return identifiers/paths ≥8 chars from tool-result text.

    These are used to detect whether the agent later referenced this result
    by checking for substring matches in subsequent assistant messages.
    """
    return frozenset(_STRC_ENTITY_RE.findall(content))


def _strc_count_citations(cstrings: frozenset, later_messages: list) -> int:
    """Count assistant messages (after this result) that contain ≥1 citation string."""
    if not cstrings:
        return 0
    n = 0
    for msg in later_messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if any(s in str(content) for s in cstrings):
            n += 1
    return n


def scored_tool_result_clear(
    messages: list[dict],
    target_tokens: int,
) -> tuple[list[dict], int, bool]:
    """Clear tool output bodies ranked by value score (lowest first).

    Each clearable user turn is scored:
        score = type_weight × min(1, len(output) / 2000) + citation_boost
    where:
        type_weight   — calibrated from observed reference rates per command type
        citation_boost = min(0.30, 0.10 × n_citations)
        n_citations   — number of later assistant messages containing ≥1 entity
                        from this output (ACT-R base-level activation proxy)

    Hard constraints:
        KEEP_RECENT (3)        — never clear the last N tool-result turns
        STRC_SCORE_FLOOR (0.6) — never clear a result above this score

    Falls back to truncate() if scored clearing alone is insufficient.

    Returns (new_message_list, tokens_saved, used_fallback).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, False
    if count_tokens(messages) <= target_tokens:
        return messages, 0, False

    _STUB_PREFIX      = "[TOOL OUTPUT CLEARED"
    _SUMMARY_PREFIXES = ("[CONTEXT SUMMARY", "[COMPRESSED HISTORY")

    def _is_clearable(msg: dict) -> bool:
        if msg.get("role") != "user":
            return False
        content = msg.get("content") or ""
        if isinstance(content, list):
            return False
        return (
            not content.startswith(_STUB_PREFIX)
            and not content.startswith(_SUMMARY_PREFIXES)
        )

    compressible_user_indices = [
        i for i in range(N_PROTECTED, len(messages))
        if _is_clearable(messages[i])
    ]

    # Respect KEEP_RECENT — never touch the last N result turns
    eligible = (
        compressible_user_indices[:-KEEP_RECENT]
        if len(compressible_user_indices) > KEEP_RECENT
        else []
    )

    if not eligible:
        new_messages, extra = truncate(messages, target_tokens)
        return new_messages, extra, True

    # Score every eligible result
    scored: list[tuple[float, int]] = []
    for idx in eligible:
        content  = messages[idx].get("content", "") or ""
        cmd      = _strc_get_cmd(messages[idx - 1]) if idx > N_PROTECTED else ""
        cstrings = _strc_citation_strings(content)
        citations = _strc_count_citations(cstrings, messages[idx + 1:])
        type_w   = _STRC_TYPE_WEIGHTS[_strc_classify_cmd(cmd)]
        size_s   = min(1.0, len(content) / _STRC_SIZE_NORM)
        cite_b   = min(_STRC_MAX_BOOST, _STRC_CITE_BOOST * citations)
        score    = min(1.0, type_w * size_s + cite_b)
        scored.append((score, idx))

    scored.sort(key=lambda x: x[0])  # lowest value first

    new_messages = list(messages)
    tokens_saved = 0

    for score, idx in scored:
        if count_tokens(new_messages) <= target_tokens:
            break
        if score >= STRC_SCORE_FLOOR:
            break  # remaining results are too valuable to clear
        original_content = new_messages[idx].get("content", "")
        n_tokens = len(_ENCODER.encode(str(original_content)))
        step_k   = (idx - N_PROTECTED) // 2
        new_messages[idx] = {
            **new_messages[idx],
            "content": f"[TOOL OUTPUT CLEARED — {n_tokens} tokens — step {step_k}]",
        }
        tokens_saved += n_tokens

    # Fallback if scored clearing was insufficient
    used_fallback = False
    if count_tokens(new_messages) > target_tokens:
        new_messages, extra_saved = truncate(new_messages, target_tokens)
        tokens_saved  += extra_saved
        used_fallback  = True

    return new_messages, tokens_saved, used_fallback


# ── Token log ──────────────────────────────────────────────────────────────────

def write_token_log(agent) -> None:
    """Write accumulated token stats to MSWEA_TOKEN_LOG_PATH (if set)."""
    log_path = os.environ.get("MSWEA_TOKEN_LOG_PATH")
    if not log_path:
        return

    n = len(agent._mem_call_latencies)
    data = {
        # ── Cumulative totals ────────────────────────────────────────────────
        "total_prompt_tokens":     agent._mem_prompt_tokens,
        "total_completion_tokens": agent._mem_completion_tokens,
        "total_tokens":            agent._mem_prompt_tokens + agent._mem_completion_tokens,
        "total_latency_s":         round(agent._mem_total_latency, 3),
        "mean_latency_s":          round(agent._mem_total_latency / n, 3) if n else 0.0,
        # ── Compression events ───────────────────────────────────────────────
        "compression_events":              agent._mem_compression_events,
        "compression_event_steps":         agent._mem_compression_event_steps,
        "context_tokens_at_compression":   agent._mem_context_tokens_at_compression,
        "context_tokens_after_compression": agent._mem_context_tokens_after_compression,
        "total_tokens_saved":              agent._mem_tokens_saved,
        "mean_compression_ratio":          (
            sum(agent._mem_compression_ratios) / len(agent._mem_compression_ratios)
            if agent._mem_compression_ratios else 1.0
        ),
        # ── Per-step breakdown ───────────────────────────────────────────────
        "step_prompt_tokens":      agent._mem_step_prompt_tokens,
        "step_completion_tokens":  agent._mem_step_completion_tokens,
        "step_latency_s":          [round(x, 3) for x in agent._mem_call_latencies],
        # ── Summarization-specific ───────────────────────────────────────────
        "summarization_prompt_tokens": agent._mem_summarization_prompt_tokens,
        "summarization_latency_s":     round(agent._mem_summarization_latency_s, 3),
        # ── TRC-specific ─────────────────────────────────────────────────────
        "trc_truncation_fallback_events": agent._mem_trc_fallback_events,
        # ── Online TRC ───────────────────────────────────────────────────────
        "online_trc_flags":              agent._mem_online_trc_flags,
        "online_trc_total_tokens_saved": agent._mem_online_trc_tokens_saved,
        "online_trc_clears":             len(agent._mem_online_trc_flags),
    }
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).write_text(json.dumps(data, indent=2))
