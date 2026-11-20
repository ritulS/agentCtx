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
                        Standalone TR and the SU-free fallback target token_budget * r.

Protected messages (never compressed)
  index 0 — system prompt
  index 1 — first user message (the task statement)

Compressible: messages[2:]

Truncation (TR)
  Standalone TR and the SU-free fallback use truncate_oldest_turns():
  drop oldest assistant/result turns to token_budget * r, protecting system,
  task, and the latest turn.
  If those alone exceed the target, retain them and continue over target.
  The online primitives keep the legacy truncate() as their budget-time
  fallback: drop messages until the total estimated token count of
  (protected + remaining) ≤ target_tokens. Always keeps at least the last
  message in the compressible window.

Summarization, length-free (SU-free)
  summarize_free(): one LLM call asking for a *concise* summary of the
  compressible window, with no word target, so compression_ratio does not
  engage in the prompt (depth-invariant); the summary replaces the entire
  compressible window with one summary message. target_tokens only sizes the
  complete-turn TR fallback to B*r when all summary attempts fail.
  The call goes to the agent's model unless MSWEA_SUMMARY_MODEL_CONFIG (or
  MSWEA_SUMMARY_MODEL_NAME / MSWEA_SUMMARY_API_BASE) selects a different
  summarization model — see "Summarization model" below.
  The response is cleaned before it enters the history (reasoning preamble
  dropped, the marked block extracted or the text wrapped in the markers),
  rejected when the body is empty or the reasoning never closed (re-queried
  up to SUMMARY_MAX_ATTEMPTS times, then the TR fallback), and the message is
  tagged extra["kind"] = "summary" — see "Summary message handling" below.
  (The ICLR-era SU-full / SS / partial / TRC / staggered primitives were
  removed 2026-11-19; git history before that commit has them.)

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
# summarize_free() LLM call to a different model, set:
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
# the tag existed.
#
# The summarizer's raw response is normalised by clean_summary_text() before
# it enters the history. Qwen-style chat templates open a <think> block in the
# generation prompt, and the vLLM servers here run without a reasoning parser
# (mini-swe-agent parses raw text), so the reasoning arrives inline in
# `content` and ends with `</think>`. Passing that through verbatim (a) hid the
# marker line from the prefix checks (the tool-result clearing of the ICLR
# primitives then treated the summary as tool output), and (b) put "Let me
# create a structured summary ..." prose in front of the agent. The 2026-09-08
# audit found the preamble on 219/220 saved SS summaries and, in 33 runs, the agent re-summarising after a summary; whether (b) caused
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
    on_reject=None,
) -> tuple[str | None, dict, int, int, float]:
    """Query the summarizer until clean_summary_text() accepts a response.

    ``on_reject(reason, raw_reply) -> list[dict] | None`` (optional) runs after
    a rejected attempt; the messages it returns are appended to the prompt
    for the next attempt (before a trailing assistant prefill), so a
    rejection can carry a correction instead of re-asking the identical
    prompt. None / empty leaves the prompt as it was.

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
    # A prompt whose last message is an assistant turn is a prefill: the model
    # continues it, so its text is restored in front of every reply before the
    # marker check (online_claude_select with MSWEA_EXTRACT_PREFILL=1).
    _last = summary_prompt[-1] if summary_prompt else None
    prefill = response_text(_last) if isinstance(_last, dict) and _last.get("role") == "assistant" else ""
    summary_prompt = list(summary_prompt)
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
        model_text = response_text(response)
        raw = prefill + model_text if prefill else model_text
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
            "prefill": prefill or None,     # restored in front of `content` before validation
            "content": model_text,
            "reasoning": _response_reasoning(response),
            "summary": text,
        })
        if text is not None:
            break
        rejections.append(flags.get("rejected") or "unknown")
        if on_reject is not None and attempt < attempts:
            _extra = on_reject(flags.get("rejected"), raw)
            if _extra:
                _at = len(summary_prompt) - 1 if prefill else len(summary_prompt)
                summary_prompt[_at:_at] = list(_extra)
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


def _summarize_free(
    messages: list[dict],
    model,
    target_tokens: int,
    build_prompt,
    open_marker: str,
    close_marker: str,
) -> tuple[list[dict], int, int, int, float]:
    """Body of summarize_free() (one summarizer call, no word target)."""
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
    budget the trigger would fire again on the next step.

    Returns (new_message_list, tokens_saved, prompt_tokens_used, completion_tokens_used, latency_s).
    """
    return _summarize_free(
        messages, model, target_tokens, _su_prompt, SU_OPEN_MARKER, SU_CLOSE_MARKER
    )


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


def _select_render_message(msg: dict, tag: str | None = None) -> str:
    """One history message as the selector sees it: a header with the uid and
    role, then the text. Observations (user/tool messages) get ``n| `` line
    numbers so the reply can name line ranges; assistant messages are shown
    whole (they are kept or dropped as a unit; tool calls rendered as in
    _extract_history_text). ``tag`` (anchored selection) is appended to the
    header after a semicolon; None leaves the header as it always was."""
    uid  = _msg_uid(msg) or "?"
    role = msg.get("role", "unknown")
    text = _msg_text(msg)
    suffix = f"; {tag}" if tag else ""
    if role == "assistant":
        lines = [text] if text else []
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") or {}
            lines.append(f"[tool_call {call.get('id', '?')}] {fn.get('name', '?')}({fn.get('arguments', '')})")
        return f"[{uid} assistant{suffix}]\n" + "\n".join(lines)
    label = "tool result" if role == "tool" else role
    if role == "tool" and msg.get("tool_call_id"):
        label = f"tool result for {msg['tool_call_id']}"
    body_lines = text.split("\n")
    width = len(str(len(body_lines)))
    numbered = "\n".join(f"{i:{width}d}| {line}" for i, line in enumerate(body_lines, 1))
    return f"[{uid} {label}, {len(body_lines)} lines{suffix}]\n{numbered}"


def _select_prompt(extract_model, task_text: str, window: list[dict],
                   tags: dict | None = None, budget_tokens: int | None = None,
                   source: str = "full", anchor_style: str = "header",
                   prev_uids: list[str] | None = None) -> list[dict]:
    """Prompt for online_claude_select(): the selector returns uids and line
    ranges, never prose. The user message is a list of text blocks (task, one
    block per history message, the instructions) with a cache breakpoint on
    the last history block, so the growing history prefix is served from the
    prompt cache on the next step.

    ``tags`` (anchored selection, MSWEA_SELECT_ANCHOR) maps uid -> header tag
    (token count and whether the message was in the agent's context at the
    previous step) and adds the "start from the previous selection"
    paragraph; ``budget_tokens`` (MSWEA_SELECT_CAP) states the cap on the
    selected history. Both None = the plain online_claude_select prompt,
    byte for byte. ``source`` "context" (MSWEA_SELECT_SOURCE, the incremental
    condition) tells the selector it sees the previous step's context rather
    than the complete history and that what it drops is gone for good.

    ``anchor_style`` "trailing" (MSWEA_SELECT_ANCHOR=trailing, added 2026-11-12)
    is the prompt-cache-friendly anchored form: the header tag carries the
    token count only (fixed per message), the uids that were in the agent's
    context at the previous step (``prev_uids``) are listed in the trailing
    instruction block instead of in every header, and the budget number appears
    only there too. With the "header" form the per-message "in / not in context
    last step" tags and the budget figure in the system prompt changed every
    step, so the selector's prompt cache hit only ~6% (plain ocs: 92%)."""
    if anchor_style not in ("header", "trailing"):
        raise ValueError(f"anchor_style must be header | trailing, got {anchor_style!r}")
    trailing = anchor_style == "trailing"
    if source == "full":
        shown_text = ("its complete history so far (every command it ran and every output it "
                      "saw)")
        hidden_text = ("everything else is hidden from it for this step only (you select again, "
                       "from the complete history, before the next step)")
    else:
        shown_text = ("the context it had at the previous step (what was selected last time, "
                      "trimmed outputs included) plus the newest turn")
        hidden_text = ("everything else is removed for good: you select again before the next "
                       "step, but only from what you keep now plus the next turn")
    if tags is None:
        anchor_text = ""
    elif trailing:
        anchor_text = (
            "\n\nEach message's tag also says how many tokens it holds. The list after the "
            "history names the messages that were in the agent's context at the previous step. "
            "Start from that selection: keep what was in context unless it is no longer needed, "
            "add what the newest turn makes needed, and change as little as possible from step "
            "to step so the agent's context stays stable."
        )
    else:
        anchor_text = (
            "\n\nEach message's tag also says how many tokens it holds and whether it was in the "
            "agent's context at the previous step (\"in context last step\" / \"not in context last "
            "step\"). Start from the previous step's selection: keep what was in context unless "
            "it is no longer needed, add what the newest turn makes needed, and change as little "
            "as possible from step to step so the agent's context stays stable."
        )
    if budget_tokens is None:
        budget_text = ""
    elif trailing:
        budget_text = (
            "\n\nYour selection must total at most the selection budget stated after the history "
            "(the task statement and the newest messages are kept separately and do not count). "
            "A selection over the budget is rejected and you are asked again."
        )
    else:
        budget_text = (
            f"\n\nYour selection must total at most {budget_tokens} tokens (the task statement and "
            "the newest messages are kept separately and do not count). A selection over the "
            "budget is rejected and you are asked again."
        )
    system = (
        "You curate the context window of an autonomous software-engineering agent that "
        "fixes a bug in a repository by running one shell command per step. Before every "
        f"step you are shown the agent's task statement and {shown_text}, each message "
        "tagged with an id and, for outputs, numbered lines.\n\n"
        "Select the parts of that history the agent still needs to finish the task. The "
        "agent will see exactly the selected text, unchanged, in the original order, with "
        f"a short '[... N lines omitted ...]' marker where you cut; {hidden_text}.\n\n"
        "Reply with selection directives only, one per line, between a line containing only "
        f"{SEL_OPEN_MARKER} and a line containing only {SEL_CLOSE_MARKER}:\n"
        "  keep <id>                 keep the whole message\n"
        "  keep <id> L<a>-<b>, L<c>  keep only these lines of an output (assistant messages are kept whole)\n"
        "  drop <id>                 (optional) explicitly drop a message\n"
        "  none                      keep nothing (the agent sees only the task and its newest turn)\n"
        "Messages you do not mention are dropped. Do not write anything else: no notes, no "
        "summaries, no plans, no commands."
        + anchor_text + budget_text
    )
    blocks = [{"type": "text", "text": f"Task statement (for reference only):\n{task_text}\n\nHistory:"}]
    for msg in window:
        blocks.append({"type": "text", "text": _select_render_message(
            msg, None if tags is None else tags.get(_msg_uid(msg)))})
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    blocks.append({"type": "text", "text": (
        "Select what the agent still needs: the commands and outputs that located the code "
        "to change, the code it read and will edit or depends on, the edits already made, "
        "error messages and test results that still inform the next step, and the record of "
        "what was tried and ruled out. Drop outputs that were superseded, exploration that led "
        "nowhere, and the bulk of long outputs (installation logs, file listings, repeated "
        "reads) except the lines that matter. Keep assistant messages whose command the agent "
        "must remember having run. Reply with directives only, between the markers."
        + ("" if not (trailing and tags is not None) else
           "\nIn the agent's context at the previous step: "
           + (", ".join(prev_uids) if prev_uids else "none") + " (every other message was not).")
        + ("" if budget_tokens is None else f"\nSelection budget: {budget_tokens} tokens.")
    )})
    return [
        extract_model.format_message(role="system", content=system),
        {"role": "user", "content": blocks},
    ]


def parse_selection(text: str, window: list[dict], known_uids=None) -> tuple[dict | None, str | None]:
    """Parse a selection body into {uid: None | [(a, b), ...]} over ``window``.

    Returns (selection, None) or (None, reason). Reasons: ``unparseable_line``
    (anything that is not a keep/drop/none directive or blank), ``unknown_uid``
    (a ``keep`` of an id that is not in the window), ``range_out_of_bounds``.
    Some directives are tolerated rather than rejected (since 2026-10-26, for
    selectors that are not Claude): a ``drop`` of an unknown id is ignored
    (nothing is there to drop); a ``keep`` of an id that is absent from the
    window but either lies numerically inside the window's id range (a gap:
    uids are not contiguous, and selectors that enumerate a range hit them) or
    is in ``known_uids`` (the protected prefix / kept tail of the complete
    history, kept regardless) is ignored too, while a ``keep`` of an id outside
    both is still ``unknown_uid``; and a line range on an assistant message
    keeps that message whole (what the prompt says happens to assistant
    messages anyway). Keeping nothing is a valid decision,
    written as the directive ``none`` (the marker check rejects an empty body
    before this parser sees it). Ranges are clamped to the message, merged and
    sorted.
    """
    by_uid = {}
    for msg in window:
        uid = _msg_uid(msg)
        if uid:
            by_uid[uid] = msg
    known = set(known_uids or ())
    nums = [int(u[1:]) for u in by_uid if u[1:].isdigit()]
    lo, hi = (min(nums), max(nums)) if nums else (0, -1)

    def tolerated_keep(uid: str) -> bool:   # absent from the window, but nothing the selector could mean
        if uid in known:
            return True
        return uid[1:].isdigit() and lo <= int(uid[1:]) <= hi
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
            selection.pop(m.group(1), None)   # unknown id: nothing to drop, ignored
            continue
        m = _SEL_KEEP_RE.match(line)
        if not m:
            return None, "unparseable_line"
        uid, ranges = m.group(1), m.group(2)
        msg = by_uid.get(uid)
        if msg is None:
            if tolerated_keep(uid):
                continue
            return None, "unknown_uid"
        if not ranges:
            selection[uid] = None
            continue
        if msg.get("role") == "assistant":
            selection[uid] = None      # assistant messages are kept whole; the range is ignored
            continue
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


def _select_settings() -> tuple[bool, int, str]:
    """(anchor, cap, anchor_style) of online_claude_select from the environment:
    the condition online-claude-select-anchored sets MSWEA_SELECT_ANCHOR=1 (each
    history message is tagged with whether it was in the agent's context at the
    previous step, and the selector is told to start from that selection) and
    MSWEA_SELECT_CAP=<tokens> (the selected history must fit; an over-budget
    reply is rejected with a correction message and re-queried). Unset / 0 =
    the plain selection (2026-10-25 behaviour). MSWEA_SELECT_ANCHOR=trailing
    (2026-11-12; the threshold condition) is the same anchoring with the
    previous-context uids and the budget figure moved to the trailing block so
    the history blocks stay byte-identical across calls (_select_prompt)."""
    raw = os.environ.get("MSWEA_SELECT_ANCHOR", "0").strip().lower()
    if raw not in ("", "0", "off", "false", "no", "1", "on", "true", "yes", "trailing"):
        raise ValueError(f"MSWEA_SELECT_ANCHOR must be 0 | 1 | trailing, got {raw!r}")
    anchor = raw in ("1", "on", "true", "yes", "trailing")
    style = "trailing" if raw == "trailing" else "header"
    cap_raw = os.environ.get("MSWEA_SELECT_CAP", "").strip()
    cap = int(cap_raw) if cap_raw else 0
    if cap < 0:
        raise ValueError(f"MSWEA_SELECT_CAP must be a non-negative token count, got {cap_raw!r}")
    return anchor, cap, style


def select_source() -> str:
    """Which history online_claude_select() re-selects from, MSWEA_SELECT_SOURCE:
    ``full`` (default; the condition online-claude-select and its anchored
    variant) hands the selector the COMPLETE history, so a message dropped at
    an earlier step can return; ``context`` (the condition
    online-claude-select-incremental, 2026-11-07) hands it only the agent's
    current context, i.e. what the previous selection kept plus the newest
    turn, so the context can only shrink (as under online_claude_extract) and
    the selector reads a context-sized prompt instead of the whole history.
    A line range on an already-trimmed output then counts the lines of the
    trimmed text (the ``[... N lines omitted ...]`` marker is one line)."""
    raw = os.environ.get("MSWEA_SELECT_SOURCE", "full").strip().lower() or "full"
    if raw not in ("full", "context"):
        raise ValueError(f"MSWEA_SELECT_SOURCE must be full | context, got {raw!r}")
    return raw


def _select_prefill(extract_model, open_marker: str = SEL_OPEN_MARKER) -> str:
    """The assistant prefill for the selector reply (MSWEA_EXTRACT_PREFILL=1):
    the prompt then ends with an assistant message holding the open marker line,
    which the model continues, so a reply cannot start as anything but a
    selection (a selector that otherwise continues the transcript as the agent
    is held to the directive grammar). OpenRouter only: Claude with thinking
    takes no prefill, so the setting is an error for provider anthropic.
    Empty when off (default). ``open_marker`` is the marker line prefilled
    (the selection marker by default; the phase judge passes its own)."""
    raw = os.environ.get("MSWEA_EXTRACT_PREFILL", "0").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return ""
    if raw not in ("1", "on", "true", "yes"):
        raise ValueError(f"MSWEA_EXTRACT_PREFILL must be 0 | 1, got {raw!r}")
    provider = (getattr(extract_model, "settings", None) or {}).get("provider")
    if provider != "openrouter":
        raise ValueError("MSWEA_EXTRACT_PREFILL=1 needs MSWEA_EXTRACT_PROVIDER=openrouter "
                         f"(provider {provider!r}: Claude with thinking takes no assistant prefill)")
    return open_marker + "\n"


def _select_with_model(full_messages: list[dict], window: list[dict], tags: dict | None,
                       budget_window: int | None, source: str, anchor_style: str,
                       prev_in_window: list[str]) -> tuple[dict | None, dict, int, int, float]:
    """The default (generative) selector backend of online_claude_select(): one
    request_summary() call over ``window`` with parse_selection() as the
    validator and the over-budget correction as ``on_reject``. Returns
    (selection or None when no attempt was accepted, flags, prompt_tokens,
    completion_tokens, latency_s)."""
    from agentctx.compression.claude_extract import get_extract_model
    extract_model = get_extract_model()
    prompt = _select_prompt(extract_model, _history_text(full_messages[1:N_PROTECTED]), window,
                            tags=tags, budget_tokens=budget_window, source=source,
                            anchor_style=anchor_style, prev_uids=prev_in_window)
    prefill = _select_prefill(extract_model)
    if prefill:
        prompt.append({"role": "assistant", "content": prefill})
    parsed: dict = {}
    known_uids = {u for u in (_msg_uid(m) for m in full_messages) if u}
    over: dict = {}

    def _validate(body: str) -> str | None:
        sel, why = parse_selection(body, window, known_uids)
        if why:
            return why
        if budget_window is not None:
            selected_tokens = count_tokens(apply_selection(window, sel))
            if selected_tokens > budget_window:
                over["tokens"] = selected_tokens
                return "over_budget"
        parsed["selection"] = sel
        return None

    def _on_reject(reason, raw):
        if reason != "over_budget":
            return None
        return [extract_model.format_message(role="user", content=(
            f"Your selection totals {over.get('tokens')} tokens; the budget is {budget_window} tokens. "
            "Reply again, between the markers, with a selection within the budget: drop the least "
            "needed messages or keep only the lines that matter of long outputs."
        ))]

    text, flags, prompt_toks, completion_toks, latency_s = request_summary(
        extract_model, prompt, SEL_OPEN_MARKER, SEL_CLOSE_MARKER, validate=_validate,
        on_reject=_on_reject if budget_window is not None else None,
    )
    if text is None or "selection" not in parsed:
        return None, flags, prompt_toks, completion_toks, latency_s
    return parsed["selection"], flags, prompt_toks, completion_toks, latency_s


def online_claude_select(
    full_messages: list[dict],
    messages: list[dict],
    model,
    keep_recent: int = 1,
    source: str = "full",
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

    ``source`` "context" (MSWEA_SELECT_SOURCE, select_source(); the condition
    online-claude-select-incremental) is the monotone variant: the caller
    passes the agent's CURRENT context as ``full_messages`` (the previous
    selection, trimmed outputs included, plus the newest turn), the prompt
    says so, and what is dropped cannot return. The selection record then
    carries ``source``.

    Returns (new_message_list, tokens_saved, prompt_tokens_used,
    completion_tokens_used, latency_s); tokens_saved is relative to
    ``full_messages`` (the complete history, i.e. what full context would
    send, or the current context for source "context"), not to ``messages``.
    """
    if source not in ("full", "context"):
        raise ValueError(f"source must be full | context, got {source!r}")
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
    anchor, cap, anchor_style = _select_settings()
    prev_uids = {u for u in (_msg_uid(m) for m in messages) if u}   # the agent's context at the previous step
    tags = None
    prev_in_window: list[str] = []
    if anchor:
        tags = {}
        for m in window:
            uid = _msg_uid(m)
            if not uid:
                continue
            if anchor_style == "trailing":
                tags[uid] = f"{count_tokens([m])} tokens"   # fixed per message: the block stays cacheable
                if uid in prev_uids:
                    prev_in_window.append(uid)
            else:
                tags[uid] = (f"{count_tokens([m])} tokens, "
                             + ("in context last step" if uid in prev_uids else "not in context last step"))
    budget_window = None
    if cap:
        budget_window = max(0, cap - count_tokens(protected) - count_tokens(kept))

    selection, flags, prompt_toks, completion_toks, latency_s = _select_with_model(
        full_messages, window, tags, budget_window, source, anchor_style, prev_in_window)
    if selection is None:
        _mark_summary_fallback("unchanged")
        return messages, 0, prompt_toks, completion_toks, latency_s

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
    if source != "full":
        record["source"] = source
    if anchor or cap:
        # Stability against the previous context and the cap actually applied.
        in_prev = {u for u in (_msg_uid(m) for m in window) if u and u in prev_uids}
        record.update({
            "anchor": anchor, "cap": cap or None, "budget_window": budget_window,
            **({"anchor_style": anchor_style} if anchor else {}),
            "selected_tokens": count_tokens(chosen),
            "carried": len(set(selection) & in_prev),          # kept, and in context last step
            "added":   len(set(selection) - in_prev),          # kept, not in context last step
            "removed": len(in_prev - set(selection)),          # in context last step, now dropped
        })
    flags["selection"] = record
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    if isinstance(last, dict):
        last.setdefault("flags", {})["selection"] = record
    tokens_after = count_tokens(new_messages)
    return new_messages, max(0, tokens_full - tokens_after), prompt_toks, completion_toks, latency_s


# ── Per-output pre-extraction (MSWEA_OUTPUT_EXTRACT_ABOVE; added 2026-11-12) ──
# The one-line note the agent sees above a pre-extracted output.
OUTPUT_EXTRACT_NOTE_FMT = ("[tool output pre-extracted: {kept} of {total} lines kept; the omitted lines "
                           "were deleted from the history and cannot be recovered]")
_OE_KEEP_ALL_RE = re.compile(r"^keep\s+all$", re.I)


def output_extract_threshold() -> int:
    """MSWEA_OUTPUT_EXTRACT_ABOVE: token count above which a NEW tool output is
    handed to the extractor model (claude_extract.get_extract_model()) right
    after it is added to the history, and replaced, in the history itself, by
    the lines the extractor keeps (extract_tool_output()). 0 (default) = off.
    The condition online-claude-select-threshold-output-extract (ocstx) sets
    1000."""
    raw = os.environ.get("MSWEA_OUTPUT_EXTRACT_ABOVE", "0").strip() or "0"
    try:
        above = int(raw)
    except ValueError:
        raise ValueError(f"MSWEA_OUTPUT_EXTRACT_ABOVE must be a non-negative token count, got {raw!r}") from None
    if above < 0:
        raise ValueError(f"MSWEA_OUTPUT_EXTRACT_ABOVE must be a non-negative token count, got {raw!r}")
    return above


def _output_extract_prompt(extract_model, task_text: str, command_msg: dict | None,
                           observation: dict) -> list[dict]:
    """Prompt for extract_tool_output(): the same directive grammar as the
    selector (parse_selection), on ONE message. The extractor is shown the task
    statement (cache breakpoint: identical across the run's calls), the agent
    message that issued the command (its reasoning and the command, so the
    purpose of the output is known) and the output with numbered lines, and
    is told that what it omits is deleted from the history for good."""
    system = (
        "You curate the context window of an autonomous software-engineering agent that "
        "fixes a bug in a repository by running one shell command per step. The agent has "
        "just run a command whose output is long. Before that output enters the agent's "
        "history you are shown the agent's task statement, the agent message that issued "
        "the command (its reasoning and the command) and the output, tagged with an id and "
        "numbered lines.\n\n"
        "Select the lines of the output the agent will need to finish the task. The agent "
        "will see exactly the selected lines, unchanged and in order, with a short "
        "'[... N lines omitted ...]' marker where you cut, under a one-line note saying the "
        "output was pre-extracted. The omitted lines are deleted for good: they are removed "
        "from the agent's history itself, so no later step and no later re-selection of the "
        "history can bring them back, and the agent cannot ask for them.\n\n"
        "Reply with selection directives only, one per line, between a line containing only "
        f"{SEL_OPEN_MARKER} and a line containing only {SEL_CLOSE_MARKER}:\n"
        "  keep <id>                 keep the whole output\n"
        "  keep <id> L<a>-<b>, L<c>  keep only these lines\n"
        "  none                      keep nothing (the agent sees only the note that the output was removed)\n"
        "Do not write anything else: no notes, no summaries, no plans, no commands."
    )
    blocks = [{"type": "text", "text": f"Task statement (for reference only):\n{task_text}",
               "cache_control": {"type": "ephemeral"}}]
    if command_msg is not None:
        blocks.append({"type": "text", "text": "The agent message that issued the command:\n"
                       + _select_render_message(command_msg)})
    blocks.append({"type": "text", "text": "The command's output:\n" + _select_render_message(observation)})
    blocks.append({"type": "text", "text": (
        "Keep the return code line and the lines that answer what the command was run for: "
        "the matches or file contents the agent asked to see, the code it will edit or depends "
        "on, error messages and tracebacks, test names and results, and anything the agent's "
        "reasoning says it is looking for. Drop boilerplate, repeated lines and unrelated "
        "material (installation and download logs, long file listings, matches in unrelated "
        "files, decorative output). When in doubt, keep the line. Reply with directives only, "
        "between the markers."
    )})
    return [
        extract_model.format_message(role="system", content=system),
        {"role": "user", "content": blocks},
    ]


def extract_tool_output(
    observation: dict,
    command_msg: dict | None,
    task_text: str,
) -> tuple[str | None, dict, int, int, float]:
    """Hand ONE new tool output to the extractor and return what replaces it.

    Added 2026-11-12 for the condition online-claude-select-threshold-output-
    extract (ocstx): DefaultAgent calls this right after an observation whose
    token count exceeds output_extract_threshold() is added to the history,
    and overwrites the observation's ``content`` IN PLACE with the returned
    text, so the trimmed output is what the context, the complete history
    (``_full_messages``, the source of later threshold selections) and the
    trajectory hold: the omitted lines never return. Extractive like
    online_claude_select(): the reply is parsed by parse_selection() over the
    one-message window (``keep <id>`` = unchanged, ``keep <id> L<a>-<b>`` =
    those lines with ``[... N lines omitted ...]`` markers, ``none`` /
    ``drop <id>`` = every line omitted; ``keep all`` is accepted as
    ``keep <id>``), and the extractor never writes a word the agent reads
    except the fixed note line OUTPUT_EXTRACT_NOTE_FMT put above the kept
    lines. An unparseable reply is re-queried through request_summary() like
    a selector reply; when no attempt is accepted the output stays as it is
    (fallback "unchanged").

    Returns (new_content | None, record, prompt_tokens, completion_tokens,
    latency_s): new_content is None when the output is unchanged (kept whole,
    or every attempt rejected). ``record`` holds ``uid``, ``outcome``
    (trimmed | removed | kept_whole | unchanged), ``lines_total`` /
    ``lines_kept``, ``tokens_before`` / ``tokens_after`` (of the observation
    alone) and ``keep`` (the ranges) and is also attached to the summary
    outcome as flags["output_extract"].
    """
    uid = _msg_uid(observation)
    if not uid:
        raise ValueError("extract_tool_output needs an observation with extra.uid")
    total_lines   = len(_msg_text(observation).split("\n"))
    tokens_before = count_tokens([observation])
    record = {"uid": uid, "lines_total": total_lines, "tokens_before": tokens_before}
    from agentctx.compression.claude_extract import get_extract_model
    extract_model = get_extract_model()
    prompt  = _output_extract_prompt(extract_model, task_text, command_msg, observation)
    prefill = _select_prefill(extract_model)
    if prefill:
        prompt.append({"role": "assistant", "content": prefill})
    parsed: dict = {}

    def _validate(body: str) -> str | None:
        body = "\n".join(f"keep {uid}" if _OE_KEEP_ALL_RE.match(line.strip()) else line
                         for line in body.split("\n"))
        sel, why = parse_selection(body, [observation], {uid})
        if why:
            return why
        parsed["selection"] = sel
        return None

    text, flags, prompt_toks, completion_toks, latency_s = request_summary(
        extract_model, prompt, SEL_OPEN_MARKER, SEL_CLOSE_MARKER, validate=_validate,
    )
    if text is None or "selection" not in parsed:
        _mark_summary_fallback("unchanged")
        record.update({"outcome": "unchanged", "lines_kept": total_lines,
                       "tokens_after": tokens_before, "keep": None})
        return None, record, prompt_toks, completion_toks, latency_s
    selection = parsed["selection"]
    spans = selection.get(uid, "drop")
    new_content = None
    if spans is None:
        record.update({"outcome": "kept_whole", "lines_kept": total_lines,
                       "tokens_after": tokens_before, "keep": None})
    else:
        if spans == "drop":
            body, kept_lines, outcome = SEL_OMITTED_FMT.format(n=total_lines), 0, "removed"
        else:
            body = apply_selection([observation], selection)[0]["content"]
            kept_lines, outcome = sum(b - a + 1 for a, b in spans), "trimmed"
        new_content = OUTPUT_EXTRACT_NOTE_FMT.format(kept=kept_lines, total=total_lines) + "\n" + body
        record.update({"outcome": outcome, "lines_kept": kept_lines,
                       "tokens_after": count_tokens([{"content": new_content}]),
                       "keep": None if spans == "drop" else [list(s) for s in spans]})
    flags["output_extract"] = record
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    if isinstance(last, dict):
        last.setdefault("flags", {})["output_extract"] = record
    return new_content, record, prompt_toks, completion_toks, latency_s


# ── Phase-boundary gate (MSWEA_PHASE_GATE, added 2026-11-12 for the condition
#    online-claude-select-threshold-output-extract-15k-phase, cell tag ocstx15p) ──
#
# The threshold selector (MSWEA_EXTRACT_FIRE_ABOVE) fires as soon as the context
# exceeds the threshold, wherever the agent happens to be in its work. With the
# gate on, a due firing is first put to the extractor model as a question: is
# the newest turn a natural break in the agent's work (a phase boundary), or is
# the agent in the middle of something? The selector fires only on "boundary";
# on "continue" the step proceeds with the context untouched and the question is
# asked again before the next step. Above MSWEA_PHASE_GATE_FORCE_ABOVE tokens the
# selector fires without asking, so a judge that never sees a boundary cannot
# let the context grow past the agent model's window. The judge never writes a
# word the agent reads; its verdicts and reasons go to the token log only.
PHASE_OPEN_MARKER  = "[PHASE VERDICT]"
PHASE_CLOSE_MARKER = "[END PHASE VERDICT]"
PHASE_VERDICTS     = ("boundary", "continue")
_PHASE_VERDICT_RE  = re.compile(r"^\s*(?:verdict\s*:\s*)?(boundary|continue)\b[\s.:!]*$", re.IGNORECASE)
PHASE_CORRECTION   = (
    "That reply could not be used. Reply again with exactly one of the words boundary or "
    f"continue on the first line between a line containing only {PHASE_OPEN_MARKER} and a line "
    f"containing only {PHASE_CLOSE_MARKER}; one more line of reason after it is optional. "
    "Nothing else."
)


def phase_gate_config(fire_above: int) -> dict | None:
    """Settings of the phase-boundary gate, or None when it is off.

    MSWEA_PHASE_GATE=1 turns it on; it needs the threshold firing
    (MSWEA_EXTRACT_FIRE_ABOVE > 0, ``fire_above``), since the question is only
    asked when a firing is due. MSWEA_PHASE_GATE_FORCE_ABOVE=<tokens> is the
    ceiling above which the selector fires without asking (default twice the
    firing threshold; 0 = no ceiling, so only the agent model's window bounds
    the context). A ceiling at or below the threshold would never let the
    judge speak and is rejected.

    Returns {"fire_above", "force_above"}.
    """
    raw = os.environ.get("MSWEA_PHASE_GATE", "0").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    if raw not in ("1", "on", "true", "yes"):
        raise ValueError(f"MSWEA_PHASE_GATE must be 0 | 1, got {raw!r}")
    if fire_above <= 0:
        raise ValueError("MSWEA_PHASE_GATE=1 needs MSWEA_EXTRACT_FIRE_ABOVE > 0: the phase judge gates "
                         "the threshold firing and has nothing to gate without one")
    raw_force = os.environ.get("MSWEA_PHASE_GATE_FORCE_ABOVE", "").strip()
    if raw_force == "":
        force_above = 2 * fire_above
    else:
        try:
            force_above = int(raw_force)
        except ValueError:
            raise ValueError("MSWEA_PHASE_GATE_FORCE_ABOVE must be a non-negative token count, "
                             f"got {raw_force!r}") from None
        if force_above < 0:
            raise ValueError(f"MSWEA_PHASE_GATE_FORCE_ABOVE must be a non-negative token count, got {raw_force!r}")
        if 0 < force_above <= fire_above:
            raise ValueError(f"MSWEA_PHASE_GATE_FORCE_ABOVE ({force_above}) must exceed "
                             f"MSWEA_EXTRACT_FIRE_ABOVE ({fire_above}), or be 0 for no ceiling")
    return {"fire_above": fire_above, "force_above": force_above}


def _phase_judge_prompt(extract_model, task_text: str, window: list[dict]) -> list[dict]:
    """Prompt for judge_phase_boundary(): the judge is shown the task statement
    and the agent's CURRENT context after the protected prefix (every message
    rendered as the selector sees it, so the blocks are byte-identical from
    call to call and the growing prefix is served from the prompt cache; the
    cache breakpoint sits on the last history block) and answers whether the
    newest turn closes a phase of the work. The system prompt and the trailing
    question carry no per-step figures, so they too are cached."""
    system = (
        "You watch an autonomous software-engineering agent that fixes a bug in a repository by "
        "running one shell command per step. Its context window has grown past the point where "
        "it will be compacted (older messages reduced to the parts still needed). Compacting in "
        "the middle of an operation costs the agent its working state, so the compaction waits "
        "for a natural break in the work. You decide whether now is such a break.\n\n"
        "The agent's work falls into phases: understanding the issue and locating the relevant "
        "code; reproducing the bug; implementing the fix; verifying it (running tests, checking "
        "edge cases); and cleaning up and submitting. The newest turn is a phase boundary when "
        "it completes a phase or a self-contained piece of one: the information gathered in the "
        "recent steps has been consumed into a conclusion (the cause is identified, the place to "
        "edit is named, an edit is applied and confirmed, a test run has been read and acted on) "
        "and the next command would start something new. It is not a boundary when the agent is "
        "mid-operation: reading a file in pieces, editing one place over several commands, "
        "iterating on a failing test or reproduction script, or looking at an output it has not "
        "yet acted on.\n\n"
        "Reply in exactly this form, both marker lines included:\n"
        f"{PHASE_OPEN_MARKER}\n"
        "boundary or continue\n"
        "one line of reason (optional; logged for researchers, never shown to the agent)\n"
        f"{PHASE_CLOSE_MARKER}\n"
        "Nothing else: no advice, no plans, no commands."
    )
    blocks = [{"type": "text", "text": f"Task statement (for reference only):\n{task_text}\n\nHistory:"}]
    for msg in window:
        blocks.append({"type": "text", "text": _select_render_message(msg)})
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    blocks.append({"type": "text", "text": (
        "Is the newest turn a phase boundary, so that the agent's older context can be compacted "
        "now without interrupting an operation in progress? Reply with boundary or continue "
        "between the markers."
    )})
    return [
        extract_model.format_message(role="system", content=system),
        {"role": "user", "content": blocks},
    ]


def parse_phase_verdict(text: str) -> tuple[dict | None, str | None]:
    """Parse a judge reply body into {"verdict": boundary | continue, "reason": str | None}.

    The first non-empty line must be one of the two words (case-insensitive;
    a ``verdict:`` label and trailing punctuation are tolerated); the remaining
    non-empty lines, if any, are the reason (a ``reason:`` label is stripped).
    Returns (None, "unparseable_verdict") otherwise, and (None,
    "empty_verdict") for an empty body.
    """
    body = text
    for marker in (PHASE_OPEN_MARKER, PHASE_CLOSE_MARKER):   # clean_summary_text keeps the marker lines
        body = body.replace(marker, "")
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return None, "empty_verdict"
    m = _PHASE_VERDICT_RE.match(lines[0])
    if not m:
        return None, "unparseable_verdict"
    reason = " ".join(lines[1:]).strip()
    if reason.lower().startswith("reason:"):
        reason = reason[len("reason:"):].strip()
    return {"verdict": m.group(1).lower(), "reason": reason or None}, None


def judge_phase_boundary(messages: list[dict], task_text: str | None = None) -> tuple[dict, int, int, float]:
    """Ask the extractor model whether the agent's newest turn is a phase boundary.

    ``messages`` is the agent's CURRENT context (protected prefix included);
    everything after the prefix is shown. ``task_text`` defaults to the
    protected task message(s) of ``messages``. The reply goes through
    request_summary() with parse_phase_verdict() as the validator (an
    unparseable reply is answered with PHASE_CORRECTION and re-queried); when
    no attempt is accepted the record's ``verdict`` is None, ``outcome`` is
    "fallback" and the fallback is marked "fire" on the summary outcome: the
    caller then fires the selector, as it would without the gate, so a judge
    that cannot answer never holds the compaction back.

    Returns (record, prompt_tokens, completion_tokens, latency_s); record
    holds ``verdict`` (boundary | continue | None), ``reason``, ``outcome``
    (accepted | fallback) and ``tokens`` (of the context judged), and is also
    attached to the summary outcome as flags["phase_judge"].
    """
    from agentctx.compression.claude_extract import get_extract_model
    extract_model = get_extract_model()
    if task_text is None:
        task_text = _history_text(messages[1:N_PROTECTED])
    window  = list(messages[N_PROTECTED:])
    prompt  = _phase_judge_prompt(extract_model, task_text, window)
    prefill = _select_prefill(extract_model, PHASE_OPEN_MARKER)
    if prefill:
        prompt.append({"role": "assistant", "content": prefill})
    parsed: dict = {}

    def _validate(body: str) -> str | None:
        rec, why = parse_phase_verdict(body)
        if why:
            return why
        parsed.update(rec)
        return None

    def _on_reject(reason, raw_reply):
        return [extract_model.format_message(role="user", content=PHASE_CORRECTION)]

    text, flags, prompt_toks, completion_toks, latency_s = request_summary(
        extract_model, prompt, PHASE_OPEN_MARKER, PHASE_CLOSE_MARKER,
        validate=_validate, on_reject=_on_reject,
    )
    record = {"tokens": count_tokens(messages)}
    if text is None or "verdict" not in parsed:
        _mark_summary_fallback("fire")
        record.update({"verdict": None, "reason": None, "outcome": "fallback"})
    else:
        record.update({"verdict": parsed["verdict"], "reason": parsed.get("reason"), "outcome": "accepted"})
    flags["phase_judge"] = record
    last = getattr(_SUMMARY_OUTCOME, "last", None)
    if isinstance(last, dict):
        last.setdefault("flags", {})["phase_judge"] = record
    return record, prompt_toks, completion_toks, latency_s


def truncate_oldest_turns(messages: list[dict], budget_tokens: int) -> tuple[list[dict], int]:
    """Drop oldest complete turns, preserving the protected head and latest turn.

    An assistant turn includes all following observations/feedback up to the
    next assistant. This keeps parallel tool results together with their call.
    A leading summary or feedback block is a separate removable unit. If the
    protected head plus latest turn cannot fit, return them over the supplied
    limit. Standalone TR supplies B*r. The agent continues with the model
    request.
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
    data.update({
        # ── Per-output pre-extraction (MSWEA_OUTPUT_EXTRACT_ABOVE, extract_tool_output;
        #    the ocstx condition): one record per new tool output above the threshold:
        #    {"step", "uid", "tokens_before", "tokens_after", "lines_total",
        #     "lines_kept", "outcome" (trimmed | removed | kept_whole | unchanged),
        #     "accepted", "prompt_tokens", "completion_tokens", "latency_s", "error"} ──
        "output_extract_events":             getattr(agent, "_mem_output_extract_events", []),
        "output_extract_threshold":          getattr(agent, "_mem_output_extract_threshold", 0),
        "output_extract_total_tokens_saved": getattr(agent, "_mem_output_extract_tokens_saved", 0),
        "output_extract_accepted":           sum(
            1 for e in getattr(agent, "_mem_output_extract_events", []) if e.get("accepted")
        ),
        "output_extract_trimmed":            sum(
            1 for e in getattr(agent, "_mem_output_extract_events", []) if e.get("outcome") == "trimmed"
        ),
        "output_extract_removed":            sum(
            1 for e in getattr(agent, "_mem_output_extract_events", []) if e.get("outcome") == "removed"
        ),
        "output_extract_errors":             sum(
            1 for e in getattr(agent, "_mem_output_extract_events", []) if e.get("error")
        ),
    })
    data.update({
        # ── Phase-boundary gate (MSWEA_PHASE_GATE, judge_phase_boundary; the ocstx15p
        #    condition): one record per due threshold firing while the gate is on:
        #    {"step", "tokens", "verdict" (boundary | continue | None), "reason",
        #     "outcome" (accepted | fallback | forced | error), "forced", "fired",
        #     "accepted", "prompt_tokens", "completion_tokens", "latency_s", "error"}.
        #    "forced" = fired above MSWEA_PHASE_GATE_FORCE_ABOVE without asking. ──
        "phase_judge_config":   getattr(agent, "_mem_phase_judge_config", None),
        "phase_judge_events":   getattr(agent, "_mem_phase_judge_events", []),
        "phase_judge_calls":    sum(
            1 for e in getattr(agent, "_mem_phase_judge_events", []) if not e.get("forced")
        ),
        "phase_judge_boundary": sum(
            1 for e in getattr(agent, "_mem_phase_judge_events", []) if e.get("verdict") == "boundary"
        ),
        "phase_judge_continue": sum(
            1 for e in getattr(agent, "_mem_phase_judge_events", []) if e.get("verdict") == "continue"
        ),
        "phase_judge_forced":   sum(
            1 for e in getattr(agent, "_mem_phase_judge_events", []) if e.get("forced")
        ),
        "phase_judge_errors":   sum(
            1 for e in getattr(agent, "_mem_phase_judge_events", []) if e.get("error")
        ),
    })
    if (getattr(agent, "_mem_online_claude_extract_events", None)
            or getattr(agent, "_mem_online_claude_select_events", None)
            or getattr(agent, "_mem_output_extract_events", None)
            or getattr(agent, "_mem_phase_judge_events", None)):
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
