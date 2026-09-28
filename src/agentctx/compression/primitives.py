"""Context-window memory primitives for mini-swe-agent.

Imported from mini-swe-agent/src/minisweagent/agents/default.py via a late
import (PYTHONPATH includes the agentCtx ``src`` directory, set by the
experiment runners).

Parameters
----------
token_budget  : int   — MSWEA_TOKEN_BUDGET env var
                        When estimated current context tokens exceed this value,
                        the selected budget-triggered primitive fires.
compression_r : float — MSWEA_COMPRESSION_RATIO, default 0.5
                        Standalone TR and SU-free/SS-free fallbacks target token_budget * r.
                        Other proportional policies target current context tokens * r.
                        TRC clearing and its turn-truncation fallback ignore r.

Protected messages (never compressed)
  index 0 — system prompt
  index 1 — first user message (the task statement)

Compressible: messages[2:]

Truncation
  Standalone TR and SU-free/SS-free fallbacks use truncate_oldest_turns():
  drop oldest assistant/result turns to token_budget * r, protecting system,
  task, and the latest turn.
  If those alone exceed the target, retain them and continue over target.
  Other policies keep the legacy truncate() fallback: drop messages until the total
  estimated token count of (protected + remaining) ≤ target_tokens.
  Always keeps at least the last message in the compressible window.

Tool-result clearing (TRC)
  On budget overflow, replace all but the latest three tool results with stubs.
  If still over budget, drop oldest complete assistant/result turns until the
  budget is met, preserving system, task, and the latest turn. If these alone
  cannot fit, the agent records the overflow and continues with the model call.
  See compression/README.md for the full contract and measurements.

Summarization
  Make a single LLM call asking for a summary of the compressible window
  targeting (target_tokens - protected_tokens) compressible tokens worth of text.
  Replaces the entire compressible window with one summary message.
  The call goes to the agent's model unless MSWEA_SUMMARY_MODEL_CONFIG (or
  MSWEA_SUMMARY_MODEL_NAME / MSWEA_SUMMARY_API_BASE) selects a different
  summarization model — see "Summarization model" below.
  The response is cleaned before it enters the history (reasoning preamble
  dropped, the marked block extracted or the text wrapped in the markers),
  rejected when the body is empty or the reasoning never closed (re-queried
  up to SUMMARY_MAX_ATTEMPTS times, then truncate() is the fallback), and the
  message is tagged extra["kind"] = "summary" so TRC never clears it — see
  "Summary message handling" below.

Summarization, length-free (SU-free / SS-free)
  summarize_free() / structured_summarize_free(): same LLM call and cleaning
  as summarize() / structured_summarize(), but the prompt asks for a
  *concise* summary with no word target, so compression_ratio does not engage
  in the prompt (depth-invariant). target_tokens only sizes the complete-turn
  TR fallback to B*r when all summary attempts fail.

Token log (MSWEA_TOKEN_LOG_PATH)
  Written after every agent step.  Schema:
    total_prompt_tokens, total_completion_tokens, total_tokens,
    total_latency_s, mean_latency_s,
    compression_events, total_tokens_saved, mean_compression_ratio
"""

import copy
import json
import os
import re
import threading
import time
from pathlib import Path

import tiktoken

from agentctx.summary_config import summary_model_config, summary_model_info

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


# ── Summarization model ────────────────────────────────────────────────────────
#
# By default the agent's own model writes the summaries. To route the
# summarize() / structured_summarize() LLM call to a different model, set:
#
#   MSWEA_SUMMARY_MODEL_CONFIG  path to a config YAML in the configs/*.yaml
#                               format; only its `model:` section is read
#                               (model_name, model_class, model_kwargs, ...).
#   MSWEA_SUMMARY_MODEL_NAME    optional override of model_name
#   MSWEA_SUMMARY_API_BASE      optional override of model_kwargs.api_base
#
# The name/api_base overrides work on top of the file, or on their own (then
# the model_class defaults to litellm_textbased, matching configs/*.yaml).
# Nothing set → agent model is used, i.e. behaviour is unchanged.
#
# The summary model is process-wide (like MSWEA_COMPRESSION_RATIO) and built
# lazily on the first summarization event, so runs that never compress never
# open a connection to it.

_SUMMARY_MODEL      = None
_SUMMARY_MODEL_LOCK = threading.Lock()


def get_summary_model(agent_model):
    """Model used for summarization calls: the override if configured, else
    the agent's own model."""
    cfg = summary_model_config()
    if cfg is None:
        return agent_model
    global _SUMMARY_MODEL
    with _SUMMARY_MODEL_LOCK:
        if _SUMMARY_MODEL is None:
            from minisweagent.models import get_model  # late import: same package that imports us
            _SUMMARY_MODEL = get_model(config=cfg)
    return _SUMMARY_MODEL


def query_summary(model, messages: list[dict]) -> dict:
    """Query for prose without interpreting the summary as an agent action.

    mini-swe-agent v2 model.query() also calls _parse_actions(), which rejects
    ordinary summaries for text-based models. Use a separate shallow copy so
    disabling that parser cannot affect agent calls, including when the agent
    and summarizer share a model. Keep query()'s API preparation, retries,
    usage metadata and cost tracking intact. Models without this parser hook
    retain their existing query behavior.
    """
    if callable(getattr(model, "_parse_actions", None)):
        model = copy.copy(model)
        model._parse_actions = lambda response: []
    return model.query(messages)


# ── Summary message handling ───────────────────────────────────────────────────
#
# Summaries are identified two ways. Structurally, via extra["kind"] ==
# SUMMARY_KIND on the message (survives the agent's uid tagging, is stripped
# before the API call, and is saved in trajectory.json / events.jsonl). And by
# content, via the SU / SS marker lines, kept for trajectories written before
# the tag existed. Only messages that pass neither test are tool output that
# TRC may clear.
#
# The summarizer's raw response is normalised by clean_summary_text() before
# it enters the history. Qwen-style chat templates open a <think> block in the
# generation prompt, and the vLLM servers here run without a reasoning parser
# (mini-swe-agent parses raw text), so the reasoning arrives inline in
# `content` and ends with `</think>`. Passing that through verbatim (a) hid the
# marker line from the prefix checks, so TRC treated the summary as tool output,
# and (b) put "Let me create a structured summary ..." prose in front of the
# agent. The 2026-09-08 audit found the preamble on 219/220 saved SS summaries
# and, in 33 runs, the agent re-summarising after a summary; whether (b) caused
# the re-summarising is a hypothesis the audit could not confirm. The flags
# returned alongside the text are stored in extra["summary_format"] so later
# audits can count these cases without re-reading the model output.
#
# Both SU and SS ask for the summary between marker lines. Markers count only
# when they are a line of their own, so a marker mentioned inside the model's
# reasoning ("I must use [CONTEXT SUMMARY] and ...") is never taken as the start
# of the body. Reasoning ends at the first </think> when the response opens
# with <think>, or when no marker line precedes that </think>; a marked body
# that merely quotes "</think>" is therefore left intact. A response with no
# marker line at all that contains "</think>" cannot be told apart from
# reasoning followed by an unformatted body, so it is rejected rather than
# guessed at; rejection feeds the retry / fallback path below.
#
# A response with no marker line is rejected as well (since 2026-09-27). Until
# then an unmarked response without "</think>" was accepted as an unformatted
# body. That was safe while the vLLM servers ran without a reasoning parser:
# Qwen's reasoning arrived inline, so a reply that ignored the instructions
# carried "</think>" and fell under the ambiguous-reasoning rejection above.
# With --reasoning-parser the reasoning is stripped server-side and such
# replies reached the history unchecked. In the r2 P30S SU-free / SS-free
# cells 76/245 and 83/252 summaries had no marker, and most of them were the
# summarizer continuing the transcript as the agent (a bare
# ```mswea_bash_command``` block, or "[user]: <returncode>..." tool output)
# rather than a summary. Requiring the marker line restores the old behaviour
# for those replies: retry, then truncate().
#
# Cleaning and validation are separate steps: a response whose summary body is
# empty, whose reasoning never closed (an open <think> with no </think>), whose
# reasoning boundary is undecidable, or that has no marker line is rejected.
# request_summary() re-queries up to SUMMARY_MAX_ATTEMPTS times
# and returns None when every attempt is rejected; the primitives then fall
# back to truncate() rather than replace the history with a non-summary.
#
# Each request_summary() call also leaves a per-thread outcome record
# (attempts, per-attempt rejection reasons, accepted flags, and whether the
# primitive fell back to truncate()). The agent pops it with
# pop_summary_outcome() right after the primitive returns and stores it in the
# compression event and the token log, so a truncation under a summarizing
# condition can be traced to its cause. Thread-local because Harbor runs
# several agents in one process; the record is consumed synchronously.

SUMMARY_KIND       = "summary"
SS_OPEN_MARKER     = "[CONTEXT SUMMARY]"
SS_CLOSE_MARKER    = "[END CONTEXT SUMMARY]"
SU_OPEN_MARKER     = "[COMPRESSED HISTORY SUMMARY]"
SU_CLOSE_MARKER    = "[END SUMMARY]"
_SUMMARY_PREFIXES  = ("[CONTEXT SUMMARY", "[COMPRESSED HISTORY")
_THINK_OPEN        = "<think>"
_THINK_CLOSE       = "</think>"
# Retries before the truncate() fallback. Each attempt is one summarizer call
# with the same prompt; usage is summed. 5 is the deployment-class default
# (Terminus 2 and OpenHands also retry several times before giving up).
SUMMARY_MAX_ATTEMPTS = max(1, int(os.environ.get("MSWEA_SUMMARY_MAX_ATTEMPTS", "5")))


def is_summary_message(msg: dict) -> bool:
    """True for a summary produced by any summarize* primitive.

    Checks the structural tag first, then the marker prefixes for summaries
    written before the tag existed.
    """
    extra = msg.get("extra")
    if isinstance(extra, dict) and extra.get("kind") == SUMMARY_KIND:
        return True
    content = msg.get("content") or ""
    return isinstance(content, str) and content.startswith(_SUMMARY_PREFIXES)


def response_text(response: dict) -> str:
    """Plain text of a model response (str or list-of-blocks content)."""
    text = response.get("content") or ""
    if isinstance(text, list):
        text = " ".join(
            block.get("text", "")
            for block in text
            if isinstance(block, dict)
        )
    return text


def _marker_spans(text: str, marker: str) -> list[tuple[int, int]]:
    """(start, end) of the marker itself on every line consisting only of
    ``marker`` (surrounding blanks allowed). Offsets exclude the blanks."""
    pattern = re.compile(r"^[ \t]*(" + re.escape(marker) + r")[ \t]*$", re.MULTILINE)
    return [(m.start(1), m.end(1)) for m in pattern.finditer(text)]


def _reasoning_end(text: str, open_starts: list[int]) -> int | str:
    """Offset just past the reasoning preamble, 0 when there is none, or a
    rejection reason ("unterminated_reasoning" / "ambiguous_reasoning").

    Rules (see the "Summary message handling" comment):
    - text opens with <think>: reasoning runs to the first </think>; none → unterminated.
    - no </think> anywhere: no reasoning.
    - </think> present but no marker line at all: undecidable → ambiguous.
    - no marker line precedes the first </think>: implicit-open reasoning
      (Qwen template) ends there.
    - a marker line precedes it: the reasoning quoted a marker only if another
      marker line follows the </think>; else the </think> is a literal inside
      the marked body and there is no reasoning.
    """
    close = text.find(_THINK_CLOSE)
    if text.startswith(_THINK_OPEN):
        return "unterminated_reasoning" if close < 0 else close + len(_THINK_CLOSE)
    if close < 0:
        return 0
    if not open_starts:
        return "ambiguous_reasoning"
    if not any(pos < close for pos in open_starts) or any(pos > close for pos in open_starts):
        return close + len(_THINK_CLOSE)
    return 0


def clean_summary_text(raw: str, open_marker: str, close_marker: str) -> tuple[str | None, dict]:
    """Normalise a summarizer response into ``open_marker\n<body>\nclose_marker``.

    Cleaning:
    1. Newlines are normalised (CRLF / CR → LF) so marker lines are found
       regardless of the model's line endings.
    2. Reasoning preamble: removed according to _reasoning_end(). Markers are
       recognised only as standalone lines, so a marker mentioned inside the
       reasoning does not start the body, and a literal ``</think>`` inside a
       marked body is preserved.
    3. The body is the text between the first marker line after the reasoning
       and the next closing-marker line (or the end of the response). Text
       outside the block, including indentation around the markers, is dropped.
    4. A response with no marker line is rejected ("missing_marker"); the
       markers are the only signal that the model answered the summary
       request rather than continued the conversation (see the module comment).

    Validation (separate from marking): rejected when the body is empty, when
    a ``<think>`` block never closed, when the response has ``</think>`` but
    no marker line (undecidable), or when it has no marker line at all. The
    accepted body is re-wrapped in the canonical markers.

    Returns (text, flags); text is None for a rejected response and
    flags["rejected"] then names the reason. flags also records what the raw
    response looked like: had_think_preamble, had_open_marker, had_close_marker.
    """
    flags = {
        "had_think_preamble": False,
        "had_open_marker":    False,
        "had_close_marker":   False,
        "rejected":           None,
    }
    text  = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    opens = _marker_spans(text, open_marker)

    cut = _reasoning_end(text, [o[0] for o in opens])
    if isinstance(cut, str):
        flags["had_think_preamble"] = True
        # Reasoning followed by nothing is reported as an empty body, not as ambiguous.
        if cut == "ambiguous_reasoning" and not text.split(_THINK_CLOSE, 1)[1].strip():
            cut = "empty_body"
        flags["rejected"] = cut
        return None, flags
    if cut > 0:
        flags["had_think_preamble"] = True
        text  = text[cut:].strip()
        opens = _marker_spans(text, open_marker)

    if opens:
        flags["had_open_marker"] = True
        body_start = opens[0][1]
        closes = [c for c in _marker_spans(text, close_marker) if c[0] >= body_start]
        if closes:
            flags["had_close_marker"] = True
            body = text[body_start:closes[0][0]]
        else:
            body = text[body_start:]
    else:
        flags["had_close_marker"] = bool(_marker_spans(text, close_marker))
        flags["rejected"] = "empty_body" if not text else "missing_marker"
        return None, flags

    body = body.strip()
    if not body:
        flags["rejected"] = "empty_body"
        return None, flags
    return f"{open_marker}\n{body}\n{close_marker}", flags


_SUMMARY_OUTCOME = threading.local()


def _set_summary_outcome(outcome: dict) -> None:
    _SUMMARY_OUTCOME.last = outcome


def _mark_summary_fallback(kind: str = "truncate") -> None:
    """Record on the current outcome that the primitive fell back to ``kind``."""
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    if isinstance(last, dict):
        last["fallback"] = kind


def pop_summary_outcome() -> dict | None:
    """Return and clear the outcome of the most recent request_summary() on
    this thread, or None when no summary was requested since the last pop.

    Keys: attempts, accepted, rejections (one reason per rejected attempt),
    flags (of the accepted or last response), fallback ("truncate" | None).
    """
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    _SUMMARY_OUTCOME.last = None
    return last


def _response_usage(response: dict) -> tuple[int, int]:
    extra = response.get("extra", {}) if isinstance(response, dict) else {}
    resp  = extra.get("response", {}) if isinstance(extra, dict) else {}
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    return (usage.get("prompt_tokens", 0) or 0), (usage.get("completion_tokens", 0) or 0)


def request_summary(
    summary_model,
    summary_prompt: list[dict],
    open_marker: str,
    close_marker: str,
    max_attempts: int | None = None,
) -> tuple[str | None, dict, int, int, float]:
    """Query the summarizer until clean_summary_text() accepts a response.

    Re-queries with the same prompt up to ``max_attempts`` times (default
    SUMMARY_MAX_ATTEMPTS). Token usage and latency are summed over attempts.

    Returns (text, flags, prompt_tokens, completion_tokens, latency_s); text is
    None when every attempt was rejected, and flags then describes the last
    rejected response. flags["attempts"] is the number of queries made.
    """
    attempts = max_attempts or SUMMARY_MAX_ATTEMPTS
    prompt_toks = completion_toks = 0
    latency_s   = 0.0
    text, flags = None, {}
    rejections: list[str] = []
    for attempt in range(1, attempts + 1):
        _t0       = time.time()
        response  = query_summary(summary_model, summary_prompt)
        latency_s += time.time() - _t0
        pt, ct = _response_usage(response)
        prompt_toks     += pt
        completion_toks += ct
        text, flags = clean_summary_text(response_text(response), open_marker, close_marker)
        flags["attempts"] = attempt
        if text is not None:
            break
        rejections.append(flags.get("rejected") or "unknown")
    _set_summary_outcome({
        "attempts":   len(rejections) + (1 if text is not None else 0),
        "accepted":   text is not None,
        "rejections": rejections,
        "flags":      dict(flags),
        "fallback":   None,
    })
    return text, flags, prompt_toks, completion_toks, latency_s


def make_summary_message(model, text: str, flags: dict) -> dict:
    """User-role summary message tagged with extra["kind"] = SUMMARY_KIND."""
    msg = model.format_message(role="user", content=text)
    extra = msg.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    msg["extra"] = {**extra, "kind": SUMMARY_KIND, "summary_format": dict(flags)}
    return msg


def _history_text(compressible: list[dict]) -> str:
    """Plain-text dump of the compressible window: one "[role]:" block per message."""
    text = ""
    for msg in compressible:
        role    = msg.get("role", "unknown")
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
            )
        text += f"[{role}]:\n{content}\n\n"
    return text


def _su_prompt(summary_model, history_text: str, target_words: int | None) -> list[dict]:
    """Prose-summary (SU) prompt.

    target_words is the approximate length asked of the summarizer (derived
    from target_tokens, i.e. from compression_ratio). None asks for a concise
    summary with no length target at all (SU-free, depth-invariant).
    """
    length = (
        f"in approximately {target_words} words" if target_words is not None
        else "concisely"
    )
    return [
        summary_model.format_message(
            role="system",
            content=(
                "You are summarizing an agent's work history to free up context window space. "
                "Your output will replace the conversation history — the agent will only see "
                "your summary, so it must be complete enough to continue the task."
            ),
        ),
        summary_model.format_message(
            role="user",
            content=(
                f"Summarize the following agent conversation history {length}. "
                f"Your summary MUST include all of:\n"
                f"1. Current task objective and progress made so far\n"
                f"2. Files examined and any modifications made (include exact file paths)\n"
                f"3. Key observations, errors encountered, and decisions taken\n"
                f"4. Current state — what has been done and what remains\n\n"
                f"Preserve exact file paths, error messages, and code snippets that are "
                f"likely still relevant. Be factual and concise.\n\n"
                f"Put the summary between a line containing only {SU_OPEN_MARKER} and a "
                f"line containing only {SU_CLOSE_MARKER}. Do not add any text outside "
                f"those two lines.\n\n"
                f"{history_text}"
            ),
        ),
    ]


def _ss_prompt(summary_model, history_text: str, target_words: int | None) -> list[dict]:
    """Structured-summary (SS) prompt; target_words=None as in _su_prompt()."""
    opening = (
        f"Produce a structured summary of the agent conversation below in approximately "
        f"{target_words} words total."
        if target_words is not None
        else "Produce a concise structured summary of the agent conversation below."
    )
    return [
        summary_model.format_message(
            role="system",
            content=(
                "You are compressing an agent's working memory to free up context window space. "
                "Your output will REPLACE the entire conversation history — the agent will only "
                "see your summary. It must contain everything needed to continue the task without "
                "any other context."
            ),
        ),
        summary_model.format_message(
            role="user",
            content=(
                f"{opening} Use EXACTLY this format and section order:\n\n"
                f"{SS_OPEN_MARKER}\n"
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
                f"{SS_CLOSE_MARKER}\n\n"
                f"Rules:\n"
                f"- Preserve exact file paths, line numbers, error strings, and symbol names.\n"
                f"- Do not speculate or add information not present in the history.\n"
                f"- Do not add any text outside the {SS_OPEN_MARKER} block.\n\n"
                f"Conversation history:\n{history_text}"
            ),
        ),
    ]


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

    history_text = _history_text(compressible)

    # Target compressible tokens = target_tokens minus what the protected msgs use
    protected_tokens  = count_tokens(protected)
    compress_target   = max(50, target_tokens - protected_tokens)
    # 1 token ≈ 4 chars ≈ 0.75 words (rough heuristic)
    target_words      = max(30, int(compress_target * 0.75))

    # The summary is produced by the summarization model (agent model unless
    # MSWEA_SUMMARY_MODEL_* overrides it); the resulting message is formatted
    # by the agent's model since it goes back into the agent's history.
    summary_model = get_summary_model(model)

    summary_prompt = _su_prompt(summary_model, history_text, target_words)

    summary_text, summary_flags, prompt_toks, completion_toks, latency_s = request_summary(
        summary_model, summary_prompt, SU_OPEN_MARKER, SU_CLOSE_MARKER
    )

    # Explicit fallback: no attempt produced a usable summary, so enforce the
    # target by truncation instead of replacing the history with a non-summary.
    if summary_text is None:
        _mark_summary_fallback("truncate")
        new_messages, _ = truncate(messages, target_tokens)
        tokens_after    = count_tokens(new_messages)
        return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s

    summary_msg   = make_summary_message(model, summary_text, summary_flags)
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

    history_text = _history_text(compressible)

    protected_tokens = count_tokens(protected)
    compress_target  = max(50, target_tokens - protected_tokens)
    target_words     = max(30, int(compress_target * 0.75))

    summary_model = get_summary_model(model)  # see "Summarization model" above

    summary_prompt = _ss_prompt(summary_model, history_text, target_words)

    summary_text, summary_flags, prompt_toks, completion_toks, latency_s = request_summary(
        summary_model, summary_prompt, SS_OPEN_MARKER, SS_CLOSE_MARKER
    )

    # Explicit fallback: no attempt produced a usable summary (see summarize()).
    if summary_text is None:
        _mark_summary_fallback("truncate")
        new_messages, _ = truncate(messages, target_tokens)
        tokens_after    = count_tokens(new_messages)
        return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s

    summary_msg  = make_summary_message(model, summary_text, summary_flags)
    new_messages = protected + [summary_msg]

    # Fallback: if model over-generated past target, truncate the summary itself
    if count_tokens(new_messages) > target_tokens:
        new_messages, _ = truncate(new_messages, target_tokens)

    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s


def _summarize_free(
    messages: list[dict],
    model,
    target_tokens: int,
    build_prompt,
    open_marker: str,
    close_marker: str,
) -> tuple[list[dict], int, int, int, float]:
    """Shared body of summarize_free() / structured_summarize_free()."""
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

    protected     = messages[:N_PROTECTED]
    compressible  = messages[N_PROTECTED:]
    tokens_before = count_tokens(messages)

    summary_model  = get_summary_model(model)
    summary_prompt = build_prompt(summary_model, _history_text(compressible), None)

    summary_text, summary_flags, prompt_toks, completion_toks, latency_s = request_summary(
        summary_model, summary_prompt, open_marker, close_marker
    )

    # Explicit fallback: no attempt produced a usable summary (see summarize()).
    # This is the only place target_tokens (hence compression_ratio) is used.
    if summary_text is None:
        _mark_summary_fallback("truncate")
        new_messages, _ = truncate_oldest_turns(messages, target_tokens)
        tokens_after    = count_tokens(new_messages)
        return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s

    summary_flags["length_free"] = True
    summary_msg  = make_summary_message(model, summary_text, summary_flags)
    new_messages = protected + [summary_msg]
    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s


def summarize_free(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int, float]:
    """SU-free: summarize() with no length target (depth-invariant).

    Same prompt and cleaning as summarize(), but the summarizer is
    asked for a *concise* summary instead of "approximately N words", so the
    summary length is whatever the model produces and compression_ratio never
    reaches the prompt. ``target_tokens`` (B*r from the agent) is used only for
    the truncate_oldest_turns() fallback when every attempt is rejected.
    This retains system, task, and the latest complete assistant/result turn.
    No post-hoc length enforcement: if the summary alone were still above the
    budget the trigger would fire again on the next step, as for SS today.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    return _summarize_free(
        messages, model, target_tokens, _su_prompt, SU_OPEN_MARKER, SU_CLOSE_MARKER
    )


def structured_summarize_free(
    messages: list[dict],
    model,
    target_tokens: int,
) -> tuple[list[dict], int, int, int, float]:
    """SS-free: structured_summarize() with no length target (depth-invariant).

    See summarize_free(); the schema-guided SS prompt is used instead.
    """
    return _summarize_free(
        messages, model, target_tokens, _ss_prompt, SS_OPEN_MARKER, SS_CLOSE_MARKER
    )


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


def _trc_result_indices(messages: list[dict]) -> list[int]:
    """Find tool observations, including tagged results and legacy text histories.

    Text-based models store results as user turns with raw_output/returncode.
    Legacy histories lack those fields; accept a user turn immediately following
    an assistant in that case. Parser feedback and summaries are not results.
    Already-cleared results still count towards the retention window.
    """
    indices = []
    for i in range(N_PROTECTED, len(messages)):
        msg = messages[i]
        extra = msg.get("extra") or {}
        if is_summary_message(msg) or extra.get("interrupt_type"):
            continue
        if msg.get("role") == "tool" or (
            msg.get("role") == "user"
            and (
                "raw_output" in extra or "returncode" in extra
                or messages[i - 1].get("role") == "assistant"
            )
        ):
            indices.append(i)
    return indices


def truncate_oldest_turns(messages: list[dict], budget_tokens: int) -> tuple[list[dict], int]:
    """Drop oldest complete turns, preserving the protected head and latest turn.

    An assistant turn includes all following observations/feedback up to the
    next assistant. This keeps parallel tool results together with their call.
    A leading summary or feedback block is a separate removable unit. If the
    protected head plus latest turn cannot fit, return them over the supplied
    limit. Standalone TR supplies B*r; TRC supplies B. The agent continues
    with the model request; TRC additionally records an explicit overflow flag.
    """
    tokens_before = count_tokens(messages)
    protected = messages[:N_PROTECTED]
    turns: list[list[dict]] = []
    for msg in messages[N_PROTECTED:]:
        if not turns or msg.get("role") == "assistant":
            turns.append([])
        turns[-1].append(msg)
    remaining = tokens_before
    first = 0
    while first < len(turns) - 1 and remaining > budget_tokens:
        remaining -= count_tokens(turns[first])
        first += 1
    result = protected + [msg for turn in turns[first:] for msg in turn]
    return result, tokens_before - count_tokens(result)


def tool_result_clear(
    messages: list[dict],
    budget_tokens: int,
    fallback_truncate: bool = True,
    *,
    stats: dict | None = None,
) -> tuple[list[dict], int, bool]:
    """On budget overflow, clear ALL results older than the latest KEEP_RECENT.

    Clearing does not stop early and never uses COMPRESSION_RATIO. If enabled,
    fallback drops oldest complete turns only until the budget is met. KEEP_RECENT
    applies to clearing; fallback may retain fewer results. The protected head
    and latest turn always survive, even if they alone exceed the budget.

    Returns (new_messages, net_tokens_saved, used_fallback). Savings are signed:
    replacing very short outputs can grow the context. Optional stats separate
    clearing from truncation and report an unattainable budget for the caller.
    """
    tokens_before = count_tokens(messages)
    new_messages = list(messages)
    cleared = 0
    if tokens_before > budget_tokens:
        result_indices = _trc_result_indices(messages)
        for idx in result_indices[:-KEEP_RECENT]:
            msg = new_messages[idx]
            content = msg.get("content") or ""
            if isinstance(content, str) and content.startswith(
                ("[TOOL OUTPUT CLEARED", "[tool-result cleared")
            ):
                continue
            n_tokens = count_tokens([msg])
            step_k = (idx - N_PROTECTED) // 2  # legacy approximate label
            new_messages[idx] = {
                **msg,
                "content": f"[TOOL OUTPUT CLEARED — {n_tokens} tokens — step {step_k}]",
            }
            cleared += 1

    after_clear = count_tokens(new_messages)
    used_fallback = False
    truncation_saved = 0
    if fallback_truncate and after_clear > budget_tokens:
        new_messages, truncation_saved = truncate_oldest_turns(new_messages, budget_tokens)
        used_fallback = True
    tokens_after = count_tokens(new_messages)
    if stats is not None:
        stats.update(
            policy="clear_all_keep3_budget_turns_v1",
            budget_tokens=budget_tokens,
            keep_recent=KEEP_RECENT,
            cleared_results=cleared,
            tokens_before=tokens_before,
            tokens_after_clear=after_clear,
            tokens_after_trc=tokens_after,
            clearing_tokens_saved=tokens_before - after_clear,
            truncation_tokens_saved=truncation_saved,
            used_truncation_fallback=used_fallback,
            budget_exceeded_after_trc=tokens_after > budget_tokens,
        )
    return new_messages, tokens_before - tokens_after, used_fallback


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

    _STUB_PREFIX = "[TOOL OUTPUT CLEARED"

    def _is_clearable(msg: dict) -> bool:
        if msg.get("role") != "user" or is_summary_message(msg):
            return False
        content = msg.get("content") or ""
        if isinstance(content, list):
            return False
        return not content.startswith(_STUB_PREFIX)

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
    # Replace atomically so interruption during serialization/writing leaves
    # the previous complete log readable, never a truncated JSON document.
    import tempfile

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(token_log_dict(agent), indent=2)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(payload)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def token_log_dict(agent) -> dict:
    """Build the token-log dict from an agent's _mem_* accumulators.

    Used by write_token_log (env-var path, SWE-bench harness) and by the
    Terminal-Bench Harbor adapter (agentctx.benchmarks.harbor_adapter), which
    writes per-task logs to explicit paths because Harbor runs concurrent
    tasks in one process.
    """
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
        # One entry per completed/failed agent query; null tokens mean usage
        # was unavailable, unlike the zero placeholders in the legacy arrays.
        "model_call_records":      getattr(agent, "_mem_model_call_records", []),
        "step_latency_s":          [round(x, 3) for x in agent._mem_call_latencies],
        # ── Summarization-specific ───────────────────────────────────────────
        "summarization_prompt_tokens": agent._mem_summarization_prompt_tokens,
        "summarization_latency_s":     round(agent._mem_summarization_latency_s, 3),
        "summarization_model":         summary_model_info(),
        # one entry per compression event that requested a summary:
        # {"step", "primitive", "picked", "attempts", "accepted", "rejections", "fallback"}
        "summary_outcomes":            getattr(agent, "_mem_summary_outcomes", []),
        "summary_fallback_events":     sum(
            1 for o in getattr(agent, "_mem_summary_outcomes", []) if o.get("fallback")
        ),
        # ── Standalone / length-free fallback TR diagnostics ─────────────────
        "tr_events": getattr(agent, "_mem_tr_events", []),
        "tr_target_not_met_events": sum(
            e["target_not_met"] for e in getattr(agent, "_mem_tr_events", [])
        ),
        "tr_budget_exceeded_events": sum(
            e["budget_exceeded"] for e in getattr(agent, "_mem_tr_events", [])
        ),
        "tr_zero_reduction_events": sum(
            e["zero_reduction"] for e in getattr(agent, "_mem_tr_events", [])
        ),
        # ── TRC-specific ─────────────────────────────────────────────────────
        "trc_events": getattr(agent, "_mem_trc_events", []),
        "trc_clear_only_events": sum(
            not e["used_truncation_fallback"] and not e["budget_exceeded_after_trc"]
            for e in getattr(agent, "_mem_trc_events", [])
        ),
        "trc_clearing_tokens_saved": sum(
            e["clearing_tokens_saved"] for e in getattr(agent, "_mem_trc_events", [])
        ),
        "trc_truncation_tokens_saved": sum(
            e["truncation_tokens_saved"] for e in getattr(agent, "_mem_trc_events", [])
        ),
        "trc_truncation_fallback_events": agent._mem_trc_fallback_events,
        # ── Online TRC ───────────────────────────────────────────────────────
        "online_trc_flags":              agent._mem_online_trc_flags,
        "online_trc_total_tokens_saved": agent._mem_online_trc_tokens_saved,
        "online_trc_clears":             len(agent._mem_online_trc_flags),
    }
    return data
