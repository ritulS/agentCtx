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

Summary attempt log (MSWEA_EVENT_LOG_DIR/summary_attempts.jsonl)
  Every summarizer reply, accepted or rejected, is appended verbatim as one
  JSON line (request_seq, attempt, attempts_allowed, accepted, rejected
  reason, outcome accepted|retry|fallback, finish_reason, usage, latency,
  provider response id, the raw content, the model's reasoning when the
  provider returned it, and the cleaned summary when accepted), so a
  rejected summary can be read afterwards. MSWEA_SUMMARY_ATTEMPT_LOG names
  another file ("0" disables); nothing is written when neither is set.

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
# Since 2026-09-29 a response is also rejected when its generation was cut
# off (finish_reason == "length") or when the open marker is never closed. The
# r2 P30S run1 audit (experiments/r2/audits/r2_p30s_run1_20260929) found an
# SU-free summary of 133,948 characters accepted with the open marker only: a
# copy of the transcript that more than doubled the history (15,123 ->
# 31,684 tokens). Before this date an unclosed body was taken to the end of
# the response and finish_reason was never consulted; among the 48 accepted
# SU-free summaries of that audit exactly one lacked the close marker. Runs
# from before this date and after it are not the same condition for
# summary-based primitives.
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
# online_claude_extract (Claude-written digest, see claude_extract.py / online_claude_extract())
EX_OPEN_MARKER     = "[CONTEXT EXTRACT]"
EX_CLOSE_MARKER    = "[END CONTEXT EXTRACT]"
SEL_OPEN_MARKER    = "[CONTEXT SELECTION]"
SEL_CLOSE_MARKER   = "[END CONTEXT SELECTION]"
SEL_OMITTED_FMT    = "[... {n} lines omitted ...]"
_SUMMARY_PREFIXES  = ("[CONTEXT SUMMARY", "[COMPRESSED HISTORY", "[CONTEXT EXTRACT")
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


def clean_summary_text(raw: str, open_marker: str, close_marker: str,
                       finish_reason: str | None = None) -> tuple[str | None, dict]:
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
    no marker line (undecidable), when it has no marker line at all, when the
    generation was cut off (``finish_reason == "length"``, "truncated"), or
    when the open marker is never followed by a closing-marker line
    ("missing_close_marker"; since 2026-09-29, see the module comment). The
    accepted body is re-wrapped in the canonical markers.

    Returns (text, flags); text is None for a rejected response and
    flags["rejected"] then names the reason. flags also records what the raw
    response looked like: had_think_preamble, had_open_marker,
    had_close_marker, finish_reason (as given) and raw_chars.
    """
    flags = {
        "had_think_preamble": False,
        "had_open_marker":    False,
        "had_close_marker":   False,
        "finish_reason":      finish_reason,
        "raw_chars":          len(raw or ""),
        "rejected":           None,
    }
    text  = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    opens = _marker_spans(text, open_marker)

    # Completeness first: a generation cut off by the token limit is not a
    # finished summary whatever it contains (it may even carry both markers
    # if the model started a second block). Marker flags are still recorded.
    if finish_reason == "length":
        flags["had_open_marker"]  = bool(opens)
        flags["had_close_marker"] = bool(_marker_spans(text, close_marker))
        flags["rejected"] = "truncated"
        return None, flags

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
    # An open marker never closed means the model was still writing (or
    # copying the transcript) when it stopped, even with finish_reason=stop.
    if not flags["had_close_marker"]:
        flags["rejected"] = "missing_close_marker"
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
    flags (of the accepted or last response), fallback ("truncate" | None),
    response_ids (one provider response id per attempt, None when absent),
    interrupted (exception type name when a query raised, else None) and
    interrupted_attempt. An interrupted record is left in the slot for the
    agent to salvage; ``accepted`` is False and ``attempts`` counts only the
    queries that returned.
    """
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    _SUMMARY_OUTCOME.last = None
    return last


def _response_finish_reason(response: dict) -> str | None:
    """finish_reason of the first choice of the provider response, if kept."""
    extra = response.get("extra", {}) if isinstance(response, dict) else {}
    resp  = extra.get("response", {}) if isinstance(extra, dict) else {}
    choices = resp.get("choices") if isinstance(resp, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        reason = choices[0].get("finish_reason")
        return str(reason) if reason is not None else None
    return None


def _response_usage(response: dict) -> tuple[int, int]:
    extra = response.get("extra", {}) if isinstance(response, dict) else {}
    resp  = extra.get("response", {}) if isinstance(extra, dict) else {}
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    return (usage.get("prompt_tokens", 0) or 0), (usage.get("completion_tokens", 0) or 0)


def _response_id(response: dict) -> str | None:
    """Provider response id (vLLM: ``chatcmpl-...``), used to join the
    summarizer request to the server-side KV trace (agentctx.kv_cache_trace).
    None when the model kept no provider response or it carried no id."""
    extra = response.get("extra", {}) if isinstance(response, dict) else {}
    resp  = extra.get("response", {}) if isinstance(extra, dict) else {}
    rid = resp.get("id") if isinstance(resp, dict) else None
    return rid if isinstance(rid, str) and rid else None


def _response_reasoning(response: dict) -> str | None:
    """The provider's parsed reasoning for the first choice (vLLM
    --reasoning-parser: ``reasoning`` since 0.17, ``reasoning_content``
    before), None when absent."""
    extra = response.get("extra", {}) if isinstance(response, dict) else {}
    resp  = extra.get("response", {}) if isinstance(extra, dict) else {}
    choices = resp.get("choices") if isinstance(resp, dict) else None
    if not (isinstance(choices, list) and choices and isinstance(choices[0], dict)):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    for key in ("reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    provider = message.get("provider_specific_fields")
    if isinstance(provider, dict):
        for key in ("reasoning", "reasoning_content"):
            value = provider.get(key)
            if isinstance(value, str) and value:
                return value
    return None


_SUMMARY_ATTEMPT_LOCK = threading.Lock()
_SUMMARY_REQUEST_SEQ  = [0]   # per process; increments once per request_summary()


def summary_attempt_log_path() -> Path | None:
    """Where summarizer replies are appended, or None when logging is off.

    MSWEA_SUMMARY_ATTEMPT_LOG names the file ("0" / "off" disables it);
    otherwise MSWEA_EVENT_LOG_DIR/summary_attempts.jsonl next to the run's
    events.jsonl / compression_events.jsonl; nothing without either.
    """
    explicit = os.environ.get("MSWEA_SUMMARY_ATTEMPT_LOG", "").strip()
    if explicit:
        return None if explicit.lower() in ("0", "off", "none") else Path(explicit)
    event_dir = os.environ.get("MSWEA_EVENT_LOG_DIR", "").strip()
    return Path(event_dir) / "summary_attempts.jsonl" if event_dir else None


def _log_summary_attempt(record: dict) -> None:
    """Append one summarizer reply to the attempt log (best effort: a logging
    failure never fails the compression event)."""
    path = summary_attempt_log_path()
    if path is None:
        return
    try:
        with _SUMMARY_ATTEMPT_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
    except Exception:   # noqa: BLE001 - diagnostics only
        pass


def request_summary(
    summary_model,
    summary_prompt: list[dict],
    open_marker: str,
    close_marker: str,
    max_attempts: int | None = None,
    validate=None,
) -> tuple[str | None, dict, int, int, float]:
    """Query the summarizer until clean_summary_text() accepts a response.

    ``validate(body) -> str | None`` (optional) runs on the marker-cleaned text
    of an otherwise accepted reply; a returned string is a rejection reason
    (recorded like the marker rejections, in flags["rejected"] and the attempt
    log) and the reply is re-queried. online_claude_select() uses it to insist
    on a parseable selection.

    Re-queries with the same prompt up to ``max_attempts`` times (default
    SUMMARY_MAX_ATTEMPTS). Token usage and latency are summed over attempts.

    Returns (text, flags, prompt_tokens, completion_tokens, latency_s); text is
    None when every attempt was rejected, and flags then describes the last
    rejected response. flags["attempts"] is the number of queries made.

    The outcome record keeps one provider response id per attempt (rejected
    attempts included, None when unavailable) so a summarizer request served
    by the traced vLLM can be attributed to this compression event, and the
    running prompt/completion tokens and latency of the completed attempts.
    The record is published to the thread-local slot before the first query
    and updated after every attempt, so a transport error on a later attempt
    (which propagates to the caller) leaves the ids and usage obtained so far
    in place with ``interrupted`` set to the exception type and
    ``interrupted_attempt`` to the attempt that failed.

    Every reply, accepted or rejected, is also appended verbatim to the
    summary attempt log (summary_attempt_log_path(); see the module
    docstring) so rejected summaries can be inspected afterwards.
    """
    attempts = max_attempts or SUMMARY_MAX_ATTEMPTS
    with _SUMMARY_ATTEMPT_LOCK:
        _SUMMARY_REQUEST_SEQ[0] += 1
        request_seq = _SUMMARY_REQUEST_SEQ[0]
    prompt_toks = completion_toks = 0
    latency_s   = 0.0
    text, flags = None, {}
    rejections: list[str] = []
    response_ids: list[str | None] = []
    outcome = {
        "attempts":   0,
        "accepted":   False,
        "rejections": rejections,
        "flags":      {},
        "fallback":   None,
        # one per query made, in order; joins to kv-cache-*.jsonl request ids
        "response_ids": response_ids,
        # running usage/latency over the attempts that completed, so a
        # transport error on a later attempt does not lose what the earlier
        # attempts consumed (the agent adds these when it salvages the event)
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_s": 0.0,
        "interrupted": None,
        "interrupted_attempt": None,
    }
    _set_summary_outcome(outcome)
    for attempt in range(1, attempts + 1):
        _t0       = time.time()
        try:
            response = query_summary(summary_model, summary_prompt)
        except BaseException as exc:
            outcome["interrupted"] = type(exc).__name__
            outcome["interrupted_attempt"] = attempt
            outcome["flags"] = dict(flags)
            raise
        attempt_latency = time.time() - _t0
        latency_s += attempt_latency
        response_ids.append(_response_id(response))
        outcome["attempts"] = attempt
        pt, ct = _response_usage(response)
        # The provider's raw usage object, when the model adapter exposes one
        # (ClaudeExtractModel: uncached / cache_read / cache_creation input
        # tokens), so cached-prefix hits can be costed afterwards.
        _raw_usage = ((response.get("extra") or {}).get("response") or {}).get("usage") \
            if isinstance(response, dict) else None
        prompt_toks     += pt
        completion_toks += ct
        outcome["prompt_tokens"]     = prompt_toks
        outcome["completion_tokens"] = completion_toks
        outcome["latency_s"]         = latency_s
        raw = response_text(response)
        finish_reason = _response_finish_reason(response)
        text, flags = clean_summary_text(raw, open_marker, close_marker, finish_reason=finish_reason)
        if text is not None and validate is not None:
            _why = validate(text)
            if _why:
                flags["rejected"] = _why
                text = None
        flags["attempts"] = attempt
        _log_summary_attempt({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "request_seq": request_seq,
            "attempt": attempt,
            "attempts_allowed": attempts,
            "marker": open_marker,
            "accepted": text is not None,
            "rejected": flags.get("rejected"),
            "outcome": "accepted" if text is not None else ("fallback" if attempt >= attempts else "retry"),
            "finish_reason": finish_reason,
            "response_id": response_ids[-1],
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "usage": _raw_usage if isinstance(_raw_usage, dict) else None,
            "latency_s": round(attempt_latency, 3),
            "raw_chars": len(raw),
            "had_open_marker": flags.get("had_open_marker"),
            "had_close_marker": flags.get("had_close_marker"),
            "content": raw,
            "reasoning": _response_reasoning(response),
            "summary": text,
        })
        if text is not None:
            break
        rejections.append(flags.get("rejected") or "unknown")
    outcome["attempts"] = len(rejections) + (1 if text is not None else 0)
    outcome["accepted"] = text is not None
    outcome["flags"]    = dict(flags)
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


def _extract_history_text(window: list[dict]) -> str:
    """_history_text() for the extractor: tool calls are part of the record.

    With tool-calling models the command lives in ``tool_calls`` (and the
    observation in a ``tool`` message), so a content-only dump would show the
    extractor outputs with no commands. Each tool call is rendered as
    ``[tool_call <id>] <name>(<arguments>)`` after the message text, and tool
    results are labelled with the id they answer. Text-based histories
    (no ``tool_calls``) render exactly as _history_text().
    """
    text = ""
    for msg in window:
        role    = msg.get("role", "unknown")
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        label = f"[{role}]"
        if role == "tool" and msg.get("tool_call_id"):
            label = f"[tool result for {msg['tool_call_id']}]"
        lines = [content] if content else []
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") or {}
            lines.append(f"[tool_call {call.get('id', '?')}] {fn.get('name', '?')}({fn.get('arguments', '')})")
        text += f"{label}:\n" + "\n".join(lines) + "\n\n"
    return text


def _extract_keep_split(compressible: list[dict], keep_recent: int) -> int:
    """Index k such that compressible[k:] is kept verbatim: the newest
    ``keep_recent`` messages, extended backwards to the assistant message
    that opened that turn so a tool call is never separated from its result
    (or an observation from its command). 0 keeps everything, len() keeps nothing."""
    k = max(0, len(compressible) - max(0, keep_recent))
    if k >= len(compressible):
        return len(compressible)
    while k > 0 and compressible[k].get("role") != "assistant":
        k -= 1
    return k


def _extract_prompt(extract_model, task_text: str, history_text: str) -> list[dict]:
    """Prompt for online_claude_extract(): keep what the agent still needs, drop the rest.

    No length target (length-free). The window handed over may open with the
    previous extract, so the extractor is told to merge rather than restart.
    """
    return [
        extract_model.format_message(
            role="system",
            content=(
                "You maintain the working memory of an autonomous software-engineering agent "
                "that fixes a bug in a repository by running one shell command per step. After "
                "every step you are shown the agent's task statement and its conversation history "
                "since the task statement (its commands and their outputs). The history may begin "
                "with the extract you produced after the previous step.\n\n"
                "Rewrite that history as the information the agent still needs to finish the task. "
                "Your output REPLACES the history: the agent will see only the task statement and "
                "your extract, so anything you leave out is gone for good."
            ),
        ),
        extract_model.format_message(
            role="user",
            content=(
                f"Task statement (for reference only, do not repeat it):\n{task_text}\n\n"
                f"Extract, from the conversation history below, everything the agent still needs "
                f"to solve the task. Merge the previous extract (if the history starts with one) "
                f"with what the newer steps revealed; keep facts that are still relevant, update "
                f"facts that changed, and drop exploration that led nowhere.\n\n"
                f"Keep, verbatim where it matters:\n"
                f"- exact file paths, function/class names and line numbers the agent located\n"
                f"- code snippets the agent read and will edit or depends on\n"
                f"- the edits already made (file, what changed) and the commands already run\n"
                f"- error messages, test names and test results, and other command output that "
                f"still informs the next step\n"
                f"- what has been tried and ruled out, and what remains to be done\n\n"
                f"Do not add information that is not in the history, do not propose commands, "
                f"and do not address the agent. Write in compact prose or bullet lists.\n\n"
                f"Put the extract between a line containing only {EX_OPEN_MARKER} and a line "
                f"containing only {EX_CLOSE_MARKER}. Do not add any text outside those two lines.\n\n"
                f"Conversation history:\n{history_text}"
            ),
        ),
    ]


def online_claude_extract(
    messages: list[dict],
    model,
    keep_recent: int = 0,
) -> tuple[list[dict], int, int, int, float]:
    """Replace the compressible window with a Claude-written extract of it.

    Fires before every agent model call, once the previous call's observation
    is in the history (see DefaultAgent.query); there is no token budget and
    no length target. The protected system prompt and task statement are
    never sent for compression (the task statement is given to the extractor
    as reference only). ``keep_recent`` newest compressible messages are kept
    verbatim after the extract (0 = none); the kept span is widened to the
    assistant message that opened its first turn so a command (or tool call)
    is never split from its observation.

    The extractor is ``claude_extract.get_extract_model()``; the request goes
    through request_summary(), so retries, the marker check, the thread-local
    outcome record and summary_attempts.jsonl behave as for SU / SS. When no
    attempt yields a usable extract (every reply rejected, or a refusal), the
    history is returned unchanged and the outcome is marked
    ``fallback="unchanged"``; a transport error propagates to the caller.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    if len(messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0

    keep_recent = max(0, int(keep_recent))
    protected    = messages[:N_PROTECTED]
    compressible = list(messages[N_PROTECTED:])
    k            = _extract_keep_split(compressible, keep_recent)
    window, kept = compressible[:k], compressible[k:]
    if not window:
        return messages, 0, 0, 0, 0.0
    tokens_before = count_tokens(messages)

    from agentctx.compression.claude_extract import get_extract_model
    extract_model  = get_extract_model()
    extract_prompt = _extract_prompt(
        extract_model, _history_text(messages[1:N_PROTECTED]), _extract_history_text(window)
    )
    text, flags, prompt_toks, completion_toks, latency_s = request_summary(
        extract_model, extract_prompt, EX_OPEN_MARKER, EX_CLOSE_MARKER
    )
    if text is None:
        _mark_summary_fallback("unchanged")
        return messages, 0, prompt_toks, completion_toks, latency_s

    flags["length_free"] = True
    flags["extract"] = True
    extract_msg  = make_summary_message(model, text, flags)
    new_messages = protected + [extract_msg] + kept
    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_before - tokens_after), prompt_toks, completion_toks, latency_s



# ── online_claude_select: keep the original text, drop what the task no longer needs ──
_SEL_KEEP_RE  = re.compile(r"^keep\s+([A-Za-z]\d+)\s*(?:(?:lines?|L)?\s*((?:L?\d+(?:\s*-\s*L?\d+)?\s*,?\s*)+))?$", re.I)
_SEL_DROP_RE  = re.compile(r"^drop\s+([A-Za-z]\d+)\s*$", re.I)
_SEL_RANGE_RE = re.compile(r"L?(\d+)(?:\s*-\s*L?(\d+))?")


def _msg_uid(msg: dict) -> str | None:
    extra = msg.get("extra")
    return extra.get("uid") if isinstance(extra, dict) else None


def _msg_text(msg: dict) -> str:
    content = msg.get("content") or ""
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content


def _select_render_message(msg: dict) -> str:
    """One history message as the selector sees it: a header with the uid and
    role, then the text. Observations (user/tool messages) get ``n| `` line
    numbers so the reply can name line ranges; assistant messages are shown
    whole (they are kept or dropped as a unit; tool calls rendered as in
    _extract_history_text)."""
    uid  = _msg_uid(msg) or "?"
    role = msg.get("role", "unknown")
    text = _msg_text(msg)
    if role == "assistant":
        lines = [text] if text else []
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") or {}
            lines.append(f"[tool_call {call.get('id', '?')}] {fn.get('name', '?')}({fn.get('arguments', '')})")
        return f"[{uid} assistant]\n" + "\n".join(lines)
    label = "tool result" if role == "tool" else role
    if role == "tool" and msg.get("tool_call_id"):
        label = f"tool result for {msg['tool_call_id']}"
    body_lines = text.split("\n")
    width = len(str(len(body_lines)))
    numbered = "\n".join(f"{i:{width}d}| {line}" for i, line in enumerate(body_lines, 1))
    return f"[{uid} {label}, {len(body_lines)} lines]\n{numbered}"


def _select_prompt(extract_model, task_text: str, window: list[dict]) -> list[dict]:
    """Prompt for online_claude_select(): the selector returns uids and line
    ranges, never prose. The user message is a list of text blocks (task, one
    block per history message, the instructions) with a cache breakpoint on
    the last history block, so the growing history prefix is served from the
    prompt cache on the next step."""
    system = (
        "You curate the context window of an autonomous software-engineering agent that "
        "fixes a bug in a repository by running one shell command per step. Before every "
        "step you are shown the agent's task statement and its complete history so far "
        "(every command it ran and every output it saw), each message tagged with an id and, "
        "for outputs, numbered lines.\n\n"
        "Select the parts of that history the agent still needs to finish the task. The "
        "agent will see exactly the selected text, unchanged, in the original order, with "
        "a short '[... N lines omitted ...]' marker where you cut; everything else is hidden "
        "from it for this step only (you select again, from the complete history, before the "
        "next step).\n\n"
        "Reply with selection directives only, one per line, between a line containing only "
        f"{SEL_OPEN_MARKER} and a line containing only {SEL_CLOSE_MARKER}:\n"
        "  keep <id>                 keep the whole message\n"
        "  keep <id> L<a>-<b>, L<c>  keep only these lines of an output (assistant messages are kept whole)\n"
        "  drop <id>                 (optional) explicitly drop a message\n"
        "  none                      keep nothing (the agent sees only the task and its newest turn)\n"
        "Messages you do not mention are dropped. Do not write anything else: no notes, no "
        "summaries, no plans, no commands."
    )
    blocks = [{"type": "text", "text": f"Task statement (for reference only):\n{task_text}\n\nHistory:"}]
    for msg in window:
        blocks.append({"type": "text", "text": _select_render_message(msg)})
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    blocks.append({"type": "text", "text": (
        "Select what the agent still needs: the commands and outputs that located the code "
        "to change, the code it read and will edit or depends on, the edits already made, "
        "error messages and test results that still inform the next step, and the record of "
        "what was tried and ruled out. Drop outputs that were superseded, exploration that led "
        "nowhere, and the bulk of long outputs (installation logs, file listings, repeated "
        "reads) except the lines that matter. Keep assistant messages whose command the agent "
        "must remember having run. Reply with directives only, between the markers."
    )})
    return [
        extract_model.format_message(role="system", content=system),
        {"role": "user", "content": blocks},
    ]


def parse_selection(text: str, window: list[dict]) -> tuple[dict | None, str | None]:
    """Parse a selection body into {uid: None | [(a, b), ...]} over ``window``.

    Returns (selection, None) or (None, reason). Reasons: ``unparseable_line``
    (anything that is not a keep/drop/none directive or blank), ``unknown_uid``,
    ``range_on_assistant`` (line ranges are only valid on outputs),
    ``range_out_of_bounds``. Keeping nothing is a valid decision, written as the
    directive ``none`` (the marker check rejects an empty body before this
    parser sees it). Ranges are clamped to the message, merged and sorted.
    """
    by_uid = {}
    for msg in window:
        uid = _msg_uid(msg)
        if uid:
            by_uid[uid] = msg
    body = text
    for marker in (SEL_OPEN_MARKER, SEL_CLOSE_MARKER):
        body = body.replace(marker, "")
    selection: dict = {}
    for raw_line in body.split("\n"):
        line = raw_line.strip().rstrip(".;")
        if not line or line.startswith("#"):
            continue
        if line.lower() in ("none", "keep none", "nothing", "keep nothing"):
            continue
        m = _SEL_DROP_RE.match(line)
        if m:
            uid = m.group(1)
            if uid not in by_uid:
                return None, "unknown_uid"
            selection.pop(uid, None)
            continue
        m = _SEL_KEEP_RE.match(line)
        if not m:
            return None, "unparseable_line"
        uid, ranges = m.group(1), m.group(2)
        msg = by_uid.get(uid)
        if msg is None:
            return None, "unknown_uid"
        if not ranges:
            selection[uid] = None
            continue
        if msg.get("role") == "assistant":
            return None, "range_on_assistant"
        n_lines = len(_msg_text(msg).split("\n"))
        spans = []
        for a, b in _SEL_RANGE_RE.findall(ranges):
            a = int(a); b = int(b) if b else a
            if a > b:
                a, b = b, a
            if a < 1 or a > n_lines:
                return None, "range_out_of_bounds"
            spans.append((a, min(b, n_lines)))
        if selection.get(uid, ()) is None:
            continue   # already kept whole
        spans = sorted(spans + list(selection.get(uid) or []))
        merged = []
        for a, b in spans:
            if merged and a <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        selection[uid] = merged
    return selection, None


def apply_selection(window: list[dict], selection: dict) -> list[dict]:
    """The selected messages, original order; whole keeps are the original
    message objects, line selections are copies whose content is the kept
    lines with ``[... N lines omitted ...]`` where lines were cut (same uid, so
    the event log records them as replaced, not added)."""
    out = []
    for msg in window:
        uid = _msg_uid(msg)
        if uid not in selection:
            continue
        spans = selection[uid]
        if spans is None:
            out.append(msg)
            continue
        lines = _msg_text(msg).split("\n")
        parts, cursor = [], 1
        for a, b in spans:
            if a > cursor:
                parts.append(SEL_OMITTED_FMT.format(n=a - cursor))
            parts.extend(lines[a - 1:b])
            cursor = b + 1
        if cursor <= len(lines):
            parts.append(SEL_OMITTED_FMT.format(n=len(lines) - cursor + 1))
        extra = dict(msg.get("extra") or {})
        extra["selection"] = {"kept_lines": [list(s) for s in spans], "total_lines": len(lines)}
        out.append({**msg, "content": "\n".join(parts), "extra": extra})
    return out


def online_claude_select(
    full_messages: list[dict],
    messages: list[dict],
    model,
    keep_recent: int = 1,
) -> tuple[list[dict], int, int, int, float]:
    """Rebuild the context as a Claude-chosen subset of the COMPLETE history.

    Extractive counterpart of online_claude_extract(): nothing is rewritten.
    Before every agent model call the selector is shown the task statement and
    every message the agent ever added (``full_messages``, the agent's
    uncompressed record, not the current context) with ids and numbered
    output lines, and replies with keep/drop directives; the new context is
    the protected head, the selected messages (whole, or the kept lines with
    omission markers) in original order, then the newest ``keep_recent``
    messages verbatim (widened to the assistant message that opened the turn).
    Because the selection is recomputed from the complete history each step,
    a message dropped earlier can be brought back later.

    The reply goes through request_summary() with parse_selection() as the
    validator, so an unparseable or out-of-range reply is re-queried like a
    marker rejection and logged in summary_attempts.jsonl. When no attempt is
    accepted the current context ``messages`` is returned unchanged
    (fallback "unchanged"). ``flags["selection"]`` on the outcome records the
    counts (kept whole / partial / dropped, lines kept / total).

    Returns (new_message_list, tokens_saved, prompt_tokens_used,
    completion_tokens_used, latency_s); tokens_saved is relative to the
    complete history (what full context would send), not to ``messages``.
    """
    if len(full_messages) <= N_PROTECTED:
        return messages, 0, 0, 0, 0.0
    keep_recent  = max(0, int(keep_recent))
    protected    = full_messages[:N_PROTECTED]
    compressible = list(full_messages[N_PROTECTED:])
    k            = _extract_keep_split(compressible, keep_recent)
    window, kept = compressible[:k], compressible[k:]
    if not window:
        return messages, 0, 0, 0, 0.0
    tokens_full = count_tokens(full_messages)

    from agentctx.compression.claude_extract import get_extract_model
    extract_model = get_extract_model()
    prompt = _select_prompt(extract_model, _history_text(full_messages[1:N_PROTECTED]), window)
    parsed: dict = {}

    def _validate(body: str) -> str | None:
        sel, why = parse_selection(body, window)
        if why:
            return why
        parsed["selection"] = sel
        return None

    text, flags, prompt_toks, completion_toks, latency_s = request_summary(
        extract_model, prompt, SEL_OPEN_MARKER, SEL_CLOSE_MARKER, validate=_validate
    )
    if text is None or "selection" not in parsed:
        _mark_summary_fallback("unchanged")
        return messages, 0, prompt_toks, completion_toks, latency_s

    selection = parsed["selection"]
    chosen = apply_selection(window, selection)
    new_messages = protected + chosen + kept
    n_whole   = sum(1 for v in selection.values() if v is None)
    n_partial = sum(1 for v in selection.values() if v is not None)
    total_lines = sum(len(_msg_text(m).split("\n")) for m in window)
    kept_lines  = 0
    for m in window:
        v = selection.get(_msg_uid(m), "drop")
        if v == "drop":
            continue
        kept_lines += len(_msg_text(m).split("\n")) if v is None else sum(b - a + 1 for a, b in v)
    record = {
        "window": len(window), "kept_whole": n_whole, "kept_partial": n_partial,
        "dropped": len(window) - n_whole - n_partial,
        "lines_total": total_lines, "lines_kept": kept_lines,
        "keep": {uid: (None if v is None else [list(s) for s in v]) for uid, v in selection.items()},
    }
    flags["selection"] = record
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    if isinstance(last, dict):
        last.setdefault("flags", {})["selection"] = record
    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_full - tokens_after), prompt_toks, completion_toks, latency_s


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


def _trc_cleared_stub(msg: dict, n_tokens: int) -> str:
    """Placeholder text for a cleared tool result.

    The step label comes from the result's original ``extra.uid_step``
    (assigned once when the message was added), so it survives truncation and
    parser-feedback insertions that shift history positions. Legacy histories
    without that field show ``step unknown``.
    """
    step_k = (msg.get("extra") or {}).get("uid_step")
    if step_k is None:
        step_k = "unknown"
    return f"[TOOL OUTPUT CLEARED — {n_tokens} tokens — step {step_k}]"


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
            new_messages[idx] = {**msg, "content": _trc_cleared_stub(msg, n_tokens)}
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
        new_messages[idx] = {
            **new_messages[idx],
            "content": _trc_cleared_stub(new_messages[idx], n_tokens),
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
        # Signed sum of (before - after) over the same events. total_tokens_saved
        # is what the primitives report and is clamped at 0 per event, so an
        # event that grew the history (a summary longer than what it replaced)
        # counts as 0 there and as a negative term here.
        "net_tokens_saved":                sum(
            b - a for b, a in zip(agent._mem_context_tokens_at_compression,
                                  agent._mem_context_tokens_after_compression)
        ),
        "growth_events":                   sum(
            1 for b, a in zip(agent._mem_context_tokens_at_compression,
                              agent._mem_context_tokens_after_compression) if a > b
        ),
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
        # {"step", "primitive", "picked", "attempts", "accepted", "rejections",
        #  "fallback", "flags", "response_ids"}; plus "interrupted" /
        # "interrupted_attempt" when a summarizer query raised mid-event
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
        # ── Online Claude extract ──────────────────────────────────────────────
        # one entry per extraction attempt after a model call: {"step",
        # "tokens_before", "tokens_after", "accepted", "prompt_tokens",
        # "completion_tokens", "latency_s", "error"}
        "online_claude_extract_events":             getattr(agent, "_mem_online_claude_extract_events", []),
        "online_claude_extract_total_tokens_saved": getattr(agent, "_mem_online_claude_extract_tokens_saved", 0),
        "online_claude_extract_accepted":           sum(
            1 for e in getattr(agent, "_mem_online_claude_extract_events", []) if e.get("accepted")
        ),
        "online_claude_extract_errors":             sum(
            1 for e in getattr(agent, "_mem_online_claude_extract_events", []) if e.get("error")
        ),
    }
    data.update({
        # ── Online Claude select (extractive counterpart; same record shape,
        #    plus "tokens_full" = the complete history the selector saw) ──
        "online_claude_select_events":             getattr(agent, "_mem_online_claude_select_events", []),
        "online_claude_select_total_tokens_saved": getattr(agent, "_mem_online_claude_select_tokens_saved", 0),
        "online_claude_select_accepted":           sum(
            1 for e in getattr(agent, "_mem_online_claude_select_events", []) if e.get("accepted")
        ),
        "online_claude_select_errors":             sum(
            1 for e in getattr(agent, "_mem_online_claude_select_events", []) if e.get("error")
        ),
    })
    if (getattr(agent, "_mem_online_claude_extract_events", None)
            or getattr(agent, "_mem_online_claude_select_events", None)):
        from agentctx.compression.claude_extract import extract_model_info
        data["extract_model"] = extract_model_info()
    if getattr(agent, "_memory_config", None) is not None:
        data["adaptive_config"] = agent._memory_config.to_dict()
        data["adaptive_events"] = agent._mem_adaptive_events
        if getattr(agent, "_memory_selection", None) is not None:
            data["adaptive"] = agent._memory_selection
    from agentctx.compression.cache_metrics import compression_cache_comparisons

    # Per-call cache usage lives in model_call_records; only the boundary
    # comparison is derived here.
    data["compression_cache_comparisons"] = compression_cache_comparisons(data)
    return data
