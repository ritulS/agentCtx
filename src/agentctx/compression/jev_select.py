"""Jev-backed per-message relevance judge for ``online_claude_select``
(``MSWEA_SELECT_BACKEND=jev``; added 2026-11-17).

The default selector backend hands the COMPLETE history to one generative model
call (DeepSeek / Nemotron / Claude through ``claude_extract.py``) and parses its
keep/drop directives. This backend asks TypeSafe's Jev decision model
(https://docs.typesafe.ai, ``POST /v1/systemone``) ONE QUESTION PER HISTORY
MESSAGE, in parallel: shown the task statement, the agent's newest turn (its
current activity) and the candidate message alone, Jev answers a ``noul``
question ("the agent still needs this message to finish the task") with a
probability in [0, 1]. The primitive keeps the messages whose probability
clears ``MSWEA_JEV_KEEP_THRESHOLD`` and, under a cap (``MSWEA_SELECT_CAP``),
ranks them by probability and keeps the top ones that fit, so a cap never
needs a re-query. Jev returns typed values only, never text, so the context
is rebuilt from the original messages exactly as under the default backend.
Whole messages by default; with ``MSWEA_JEV_SELECT_LINES`` (added 2026-11-18)
a kept observation above that many tokens is judged line by line too and kept
as line ranges (see below), and the per-output pre-extraction
``MSWEA_OUTPUT_EXTRACT_ABOVE`` (``MSWEA_OUTPUT_EXTRACT_BACKEND=jev``) trims a
new output once, as it enters the history.

Each judgement is LOCAL: Jev sees one candidate at a time and cannot know that
a message is redundant with another one or superseded by a later one. That is
the point of the comparison (does per-message relevance alone curate a usable
context?), not an oversight.

Settings (environment variables, read on every selection):

  TYPESAFE_API_KEY                API key. When unset, the file named by
                                  AGENTCTX_TYPESAFE_API_KEY_FILE (default
                                  ~/.config/agentctx/typesafe_api_key) is read.
  TYPESAFE_BASE_URL               default https://api.typesafe.ai
  MSWEA_JEV_MODEL                 default jev-latest (``model`` of the request; the
                                  response names the resolved version, recorded
                                  per judgement)
  MSWEA_JEV_KEEP_THRESHOLD        keep a message when its probability, plus the
                                  anchor bonus when it applies, is at least this
                                  (default 0.5)
  MSWEA_JEV_ANCHOR_BONUS          hysteresis: added to the probability of a message
                                  that was in the agent's context at the previous
                                  step, when MSWEA_SELECT_ANCHOR is on (default 0.15;
                                  0 = no hysteresis even when anchored)
  MSWEA_JEV_CONTEXT_TURNS         how many of the newest (kept-verbatim) turns are
                                  shown to Jev as the agent's current activity
                                  (default 1; 0 = none)
  MSWEA_JEV_HISTORY               none (default) | full: with full, every request also
                                  carries the COMPLETE history (window and kept tail,
                                  rendered as the generative selector sees it) so Jev
                                  can tell a superseded or repeated message; the
                                  judgement is then no longer local (what DeepSeek sees,
                                  one question per message). Every request exceeds the
                                  long-context size, and the input grows with the
                                  square of the history (added 2026-11-17 for the probe
                                  comparison with the ocst selector).
  MSWEA_JEV_QUESTION              needed (default) | budget: the wording of the noul
                                  question. ``needed`` asks whether the agent still needs
                                  the message to finish the task from here; ``budget``
                                  asks whether the message belongs on the kept side when
                                  the history is trimmed to a budget, relative to the rest
                                  of the history and explicitly independent of how far
                                  along the task is (added 2026-11-17: under ``needed``
                                  every probability fell once the newest turn was a
                                  passing verification); ``score`` puts TypeSafe's score
                                  primitive instead (five levels described as situations,
                                  from dispensable to indispensable; p = score / 4, so the
                                  threshold and the cap ranking apply unchanged, and each
                                  judgement records ``score``, ``level_probs``,
                                  ``confidence``); ``aligned`` is the needed noul with the
                                  kept side defined as the generative selector's prompt
                                  defines it (dead-end records and commands to remember are
                                  kept) and a preamble that says dropping is costly (added
                                  2026-11-17). The question key is ``needed`` in every
                                  variant; the record carries ``question``.
  MSWEA_JEV_UNIT                  message (default) | turn: with turn, each assistant
                                  message and the observations that follow it are judged
                                  as ONE unit (rendered together) and kept or dropped
                                  together; the cap ranks units by their total tokens and
                                  the anchor bonus applies when any member was in the
                                  previous context (added 2026-11-17: judged alone, a
                                  bare command gets the same probability whether the
                                  generative selector kept or dropped it). The judgement
                                  log carries the unit's ``members``.
  MSWEA_JEV_SELECT_LINES          0 (default) = whole messages only. A token count > 0
                                  (the cells use 1000) turns on LINE-LEVEL SELECTION at
                                  firing time (added 2026-11-18): every observation of the
                                  window that passes the keep threshold and exceeds that
                                  many tokens is handed, in parallel, to the line judge of
                                  the per-output pre-extraction (jev_extract_output: the
                                  state holds the task statement, the agent message that
                                  issued the command and the output with ``L0042|`` line
                                  tags, one noul per line or block, the kept lines decided
                                  by MSWEA_JEV_LINE_THRESHOLD / _PAD / _MAX_FRACTION /
                                  _BLOCK), and is kept as those line ranges, rendered by
                                  the caller exactly as a generative ``keep <uid> L<a>-<b>``
                                  reply (``[... N lines omitted ...]`` where it cut, same
                                  uid, so the event log records a replacement). The cap
                                  ranks and admits a message by its TRIMMED size. Under
                                  MSWEA_SELECT_SOURCE=full (the default) an omitted line is
                                  only out of the context and can return at a later firing;
                                  the pre-extraction is the one that deletes lines. A line
                                  request that fails keeps its output whole (recorded as
                                  ``error``); an authentication failure raises. The
                                  selection record carries ``select_lines``, ``lines``
                                  (per uid: ranges, lines kept / total, tokens before /
                                  after, requests, errors), ``line_requests``,
                                  ``line_input_tokens``, ``line_trimmed``, ``line_errors``;
                                  the judgement log gets one ``kind: select_lines`` record
                                  per judged output. The agent's newest turn (kept tail)
                                  is never trimmed.
  MSWEA_JEV_WORKERS               parallel requests per selection (default 8)
  MSWEA_JEV_TIMEOUT_S             per-request timeout (default 60)
  MSWEA_JEV_MAX_RETRIES           retries per request on 408/429/5xx and transport
                                  errors, exponential backoff (default 3)
  MSWEA_JEV_LONG_CONTEXT          header (default) sends TypeSafe-Danger-Zone-Long-Context
                                  when a request exceeds ~30000 bytes of text (TypeSafe's
                                  long-context mode: slower, less accurate, recorded as
                                  ``long_context`` on the judgement); truncate cuts the
                                  candidate's text to fit instead (head and tail, a note
                                  in between) and records ``truncated``.
  MSWEA_JEV_JUDGEMENT_LOG         where every judgement is appended as one JSON line
                                  (default MSWEA_EVENT_LOG_DIR/jev_judgements.jsonl, the
                                  sibling of summary_attempts.jsonl; 0 disables)

A judgement that still fails after the retries KEEPS its message (conservative)
and is recorded with ``error``; an authentication failure (401 / 403) or a
selection in which every judgement failed raises, so the agent's consecutive-
error cap (MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS) ends a misconfigured run
instead of silently turning the condition into full context.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_MODEL = "jev-latest"
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_KEY_FILE = Path("~/.config/agentctx/typesafe_api_key")
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_WORKERS = 8
DEFAULT_THRESHOLD = 0.5
DEFAULT_ANCHOR_BONUS = 0.15
DEFAULT_CONTEXT_TURNS = 1
DEFAULT_MAX_RETRIES = 3
LONG_CONTEXT_BYTES = 30000       # TypeSafe switches to long-context mode above ~32000 bytes of text
LONG_CONTEXT_HEADER = "TypeSafe-Danger-Zone-Long-Context"
TRUNCATED_NOTE = "[... {n} characters of this message are not shown to the judge ...]"
_RETRY_STATUSES = (408, 429, 500, 502, 503, 504, 529)
_AUTH_STATUSES = (401, 403)

QUESTION_NAME = "needed"
JUDGE_PREAMBLE = (
    "An autonomous software-engineering agent fixes a bug in a repository by running one "
    "shell command per step. Its context window is being curated: before the next step, "
    "each message of its history is judged ON ITS OWN for whether the agent still needs it. "
    "The agent will see the kept messages unchanged, in the original order, together with "
    "the task statement and its newest turn; the dropped ones are hidden from it for this "
    "step."
)
JUDGE_PREAMBLE_FULL = (
    "An autonomous software-engineering agent fixes a bug in a repository by running one "
    "shell command per step. Its context window is being curated: before the next step, "
    "each message of its history is judged, IN VIEW OF THE COMPLETE HISTORY, for whether the "
    "agent still needs it. The agent will see the kept messages unchanged, in the original "
    "order, together with the task statement and its newest turn; the dropped ones are hidden "
    "from it for this step. Judge the one candidate named at the end; the complete history is "
    "shown so that you can tell whether a later message supersedes it or repeats it."
)
NEEDED_INSTRUCTIONS = (
    "The agent still needs the candidate history message in its context window to finish "
    "the task from here."
)
NEEDED_CRITERIA = {
    "true": (
        "The message holds information the agent still needs: the location of the code to "
        "change, code it will edit or depends on, an edit it already made, an error message "
        "or test result that still informs its next step, or the record of a command it must "
        "remember having run and whose outcome still matters."
    ),
    "false": (
        "The message is superseded by a later step, is exploration that led nowhere, or is "
        "bulk output (installation logs, file listings, repeated reads) whose useful part the "
        "agent has already acted on; or it is unrelated to the task."
    ),
}
# ── 2026-11-18: the three probe wordings below (budget / score / aligned, 2026-11-17) are
# COMMENTED OUT, not deleted: the full-history ``needed`` form (MSWEA_JEV_HISTORY=full) is the
# one pursued for now. Their dispatch branches in needed_question / _preamble /
# answer_probability are commented out with them; MSWEA_JEV_QUESTION accepts ``needed`` only.
# MSWEA_JEV_QUESTION=budget (added 2026-11-17): the same noul question put as a RELATIVE,
# stage-independent judgement. Under the default wording ("needed to finish the task from
# here") every probability fell by ~0.1 as soon as the agent's newest turn was a passing
# verification, whatever the message (sympy-14531 probe: 93/98 uids lower from step 68 to
# 93), so a fixed threshold measured task progress as much as message value.
# BUDGET_PREAMBLE_NOTE = (
#     " The history is trimmed to a fixed token budget, so the question about each message is "
#     "whether it belongs on the KEPT side or the DROPPED side of that trim, relative to the "
#     "rest of a typical debugging history. How far along the task is must not change the "
#     "judgement: a nearly finished task keeps the same share of its history as one that has "
#     "just started."
# )
# BUDGET_INSTRUCTIONS = (
#     "When the agent's history is trimmed to a fixed token budget, the candidate message "
#     "belongs on the kept side rather than the dropped side, judged by its value relative to "
#     "the rest of the history and not by how far along the task is."
# )
# BUDGET_CRITERIA = {
#     "true": (
#         "Among the more valuable messages of the history: it locates the code to change, "
#         "shows code the agent edits or depends on, records an edit the agent made, or holds "
#         "an error message or test result whose content later work builds on."
#     ),
#     "false": (
#         "Among the more dispensable messages of the history: routine navigation, bulk output "
#         "(installation logs, file listings, repeated reads) whose useful part has been acted "
#         "on, exploration that led nowhere, a result that a later message repeats, or "
#         "something unrelated to the task."
#     ),
# }
# MSWEA_JEV_QUESTION=score (added 2026-11-17): TypeSafe's ``score`` primitive instead of a
# noul: ordered levels described as situations (the docs: "describe situations, not degrees";
# each level is matched on its own), from dispensable to indispensable. Jev returns the
# probability-weighted level (``score``, 0 .. len-1), the per-level ``probabilities`` and a
# ``confidence``; the primitive uses score / (len - 1) as the message's p, so the keep
# threshold and the cap ranking work unchanged (0.5 = level 2 of 0..4).
# SCORE_PREAMBLE_NOTE = (
#     " The history is trimmed to a fixed token budget. Rate how much the agent would lose if "
#     "this message were dropped, relative to the rest of the history; how far along the task "
#     "is must not change the rating."
# )
# SCORE_INSTRUCTIONS = (
#     "How much would the agent lose if the candidate history message were dropped from its "
#     "context window?"
# )
# SCORE_LEVELS = [
#     "Unrelated to the task, or bulk output (installation logs, long file listings, a "
#     "repeated read of the same file) whose useful part has already been acted on.",
#     "Routine navigation (listing directories, a search that found nothing) or exploration "
#     "that led nowhere; nothing later builds on it.",
#     "A read or a result the agent used once and that a later message repeats or supersedes; "
#     "losing it costs little.",
#     "Code the agent edits or depends on, or an error message or test result that later work "
#     "builds on; losing it would slow the agent down.",
#     "The location of the code to change, an edit the agent made, or the test command and "
#     "result that confirm its fix; losing it would make the agent redo work or risk breaking "
#     "its fix.",
# ]
# MSWEA_JEV_QUESTION=aligned (added 2026-11-17): the ``needed`` noul with the kept side
# defined as the generative selector's prompt defines it (the record of what was tried and
# ruled out, and the commands the agent must remember having run, are KEPT; only superseded
# outputs and the bulk of long outputs are dropped), and a preamble that does not tell Jev
# that a dropped message is hidden "for this step" only. Under ``needed`` Jev was told to
# drop "exploration that led nowhere" while DeepSeek was told to keep the record of it.
# ALIGNED_PREAMBLE = (
#     "An autonomous software-engineering agent fixes a bug in a repository by running one "
#     "shell command per step. Its context window is being curated: before the next step, "
#     "each message of its history is judged for whether the agent still needs it. The agent "
#     "will see the kept messages unchanged, in the original order, together with the task "
#     "statement and its newest turn; a dropped message is removed from its context and the "
#     "agent cannot ask for it back. Dropping something the agent still needs costs more than "
#     "keeping something it does not."
# )
# ALIGNED_PREAMBLE_FULL = ALIGNED_PREAMBLE + (
#     " The complete history is shown so that you can tell whether a later message supersedes "
#     "or repeats the candidate; judge the one candidate named at the end."
# )
# ALIGNED_CRITERIA = {
#     "true": (
#         "The message is part of what the agent still needs: a command or output that located "
#         "the code to change, code it read and will edit or depends on, an edit it already "
#         "made, an error message or test result that still informs its next step, the record "
#         "of what was tried and ruled out, or an assistant message whose command the agent must "
#         "remember having run."
#     ),
#     "false": (
#         "The message is an output that a later step superseded, or the bulk of a long output "
#         "(installation logs, file listings, repeated reads of the same file) whose useful part "
#         "the agent has already acted on; or it is unrelated to the task."
#     ),
# }
QUESTION_VARIANTS = ("needed",)   # 2026-11-18: the probe wordings budget / score / aligned are
                                  # commented out above (and in needed_question / _preamble /
                                  # answer_probability) while the full-history form is pursued;
                                  # the original tuple: ("needed", "budget", "score", "aligned")
UNIT_VARIANTS = ("message", "turn")


class JevAPIError(RuntimeError):
    """A non-retryable or exhausted TypeSafe API failure (``status`` is the HTTP
    status, None for a transport failure; ``detail`` the response body)."""

    def __init__(self, message: str, status: int | None = None, detail=None):
        super().__init__(message)
        self.status = status
        self.detail = detail


def resolve_provider() -> tuple[str, str]:
    """(provider, base_url): TypeSafe's API at TYPESAFE_BASE_URL (default
    DEFAULT_BASE_URL). The provider is always ``typesafe``; the pair is kept so
    the settings record names it."""
    return "typesafe", (os.environ.get("TYPESAFE_BASE_URL", "").strip() or DEFAULT_BASE_URL)


def resolve_api_key(provider: str | None = None) -> str | None:
    """The TypeSafe API key: TYPESAFE_API_KEY, else the file named by
    AGENTCTX_TYPESAFE_API_KEY_FILE (default DEFAULT_KEY_FILE)."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    path = Path(os.environ.get("AGENTCTX_TYPESAFE_API_KEY_FILE", "").strip() or DEFAULT_KEY_FILE).expanduser()
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _env_float(name: str, default: float, lo: float | None = None, hi: float | None = None) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise ValueError(f"{name} must be within {lo}..{hi}, got {raw!r}")
    return value


def _env_int(name: str, default: int, lo: int = 0) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < lo:
        raise ValueError(f"{name} must be at least {lo}, got {raw!r}")
    return value


def jev_settings() -> dict:
    """The effective Jev settings (also written to the token log; never the key)."""
    long_context = os.environ.get("MSWEA_JEV_LONG_CONTEXT", "header").strip().lower() or "header"
    if long_context not in ("header", "truncate"):
        raise ValueError(f"MSWEA_JEV_LONG_CONTEXT must be header | truncate, got {long_context!r}")
    history = os.environ.get("MSWEA_JEV_HISTORY", "none").strip().lower() or "none"
    if history not in ("none", "full"):
        raise ValueError(f"MSWEA_JEV_HISTORY must be none | full, got {history!r}")
    question = question_variant()
    provider, base_url = resolve_provider()
    unit = os.environ.get("MSWEA_JEV_UNIT", "message").strip().lower() or "message"
    if unit not in UNIT_VARIANTS:
        raise ValueError(f"MSWEA_JEV_UNIT must be one of {UNIT_VARIANTS}, got {unit!r}")
    return {
        "provider":       provider,
        "model":          os.environ.get("MSWEA_JEV_MODEL", "").strip() or DEFAULT_MODEL,
        "base_url":       base_url,
        "threshold":      _env_float("MSWEA_JEV_KEEP_THRESHOLD", DEFAULT_THRESHOLD, 0.0, 1.0),
        "anchor_bonus":   _env_float("MSWEA_JEV_ANCHOR_BONUS", DEFAULT_ANCHOR_BONUS, 0.0, 1.0),
        "context_turns":  _env_int("MSWEA_JEV_CONTEXT_TURNS", DEFAULT_CONTEXT_TURNS),
        "history":        history,
        "question":       question,
        "unit":           unit,
        "select_lines":   _env_int("MSWEA_JEV_SELECT_LINES", 0, 0),
        "workers":        _env_int("MSWEA_JEV_WORKERS", DEFAULT_WORKERS, 1),
        "timeout_s":      _env_float("MSWEA_JEV_TIMEOUT_S", DEFAULT_TIMEOUT_S, 1.0),
        "max_retries":    _env_int("MSWEA_JEV_MAX_RETRIES", DEFAULT_MAX_RETRIES),
        "long_context":   long_context,
    }


def jev_model_info() -> dict:
    """Provenance record for the token log (settings only, never the key)."""
    try:
        return jev_settings()
    except ValueError as exc:
        return {"provider": "typesafe", "error": str(exc)}


# ── judgement log (one JSON line per Jev request) ───────────────────────────
_JUDGEMENT_LOCK = threading.Lock()


def judgement_log_path() -> Path | None:
    explicit = os.environ.get("MSWEA_JEV_JUDGEMENT_LOG", "").strip()
    if explicit:
        return None if explicit.lower() in ("0", "off", "none") else Path(explicit)
    event_dir = os.environ.get("MSWEA_EVENT_LOG_DIR", "").strip()
    return Path(event_dir) / "jev_judgements.jsonl" if event_dir else None


def _log_judgement(record: dict) -> None:
    path = judgement_log_path()
    if path is None:
        return
    try:
        with _JUDGEMENT_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
    except Exception:   # noqa: BLE001 - diagnostics only
        pass


# ── client ──────────────────────────────────────────────────────────────────
class JevClient:
    """Thin ``POST /v1/systemone`` client (httpx; the openai SDK already brings it).

    ``transport(body: dict, headers: dict) -> (status: int, payload: dict, request_id)``
    replaces the HTTP call (tests, probes). Retries ``max_retries`` times on
    408 / 429 / 5xx and transport errors with exponential backoff (1, 2, 4 s);
    any other non-2xx status raises JevAPIError at once.
    """

    def __init__(self, settings: dict | None = None, transport=None):
        self.settings = settings or jev_settings()
        self._transport = transport
        self._http = None
        self._lock = threading.Lock()

    def _client(self):
        if self._http is None:
            with self._lock:
                if self._http is None:
                    import httpx
                    provider = self.settings.get("provider", "typesafe")
                    key = resolve_api_key(provider)
                    if not key:
                        raise RuntimeError(
                            "MSWEA_SELECT_BACKEND=jev needs an API key: export TYPESAFE_API_KEY or write it to "
                            f"{DEFAULT_KEY_FILE} (AGENTCTX_TYPESAFE_API_KEY_FILE)."
                        )
                    self._http = httpx.Client(
                        base_url=self.settings["base_url"], timeout=self.settings["timeout_s"],
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    )
        return self._http

    def _send(self, body: dict, headers: dict) -> tuple[int, dict, str | None]:
        if self._transport is not None:
            return self._transport(body, headers)
        resp = self._client().post("/v1/systemone", json=body, headers=headers)
        try:
            payload = resp.json()
        except ValueError:
            payload = {"detail": resp.text}
        request_id = resp.headers.get("x-request-id") or (payload.get("request_id") if isinstance(payload, dict) else None)
        return resp.status_code, payload, request_id

    def system_one(self, state: str, questions: dict, long_context: bool = False) -> dict:
        """One request; returns {"answers", "usage", "model", "request_id", "attempts"}."""
        body = {"model": self.settings["model"], "state": state, "questions": questions}
        headers = {LONG_CONTEXT_HEADER: "true"} if long_context else {}
        attempts = self.settings["max_retries"] + 1
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                status, payload, request_id = self._send(body, headers)
            except JevAPIError:
                raise
            except Exception as exc:   # noqa: BLE001 - transport error: retried
                last_exc = exc
                status, payload, request_id = None, None, None
            if status is not None and 200 <= status < 300 and isinstance(payload, dict):
                return {
                    "answers": payload.get("answers") or {}, "usage": payload.get("usage") or {},
                    "model": payload.get("model"), "request_id": request_id or payload.get("request_id"),
                    "attempts": attempt,
                }
            if status is not None and status not in _RETRY_STATUSES:
                detail = payload.get("detail") if isinstance(payload, dict) else payload
                raise JevAPIError(f"TypeSafe API returned {status}: {str(detail)[:300]}", status=status, detail=detail)
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
        if last_exc is not None:
            raise JevAPIError(f"TypeSafe request failed after {attempts} attempts: "
                              f"{type(last_exc).__name__}: {last_exc}") from last_exc
        raise JevAPIError(f"TypeSafe API kept returning a retryable status after {attempts} attempts",
                          status=status, detail=payload)


_CLIENT: JevClient | None = None
_CLIENT_LOCK = threading.Lock()


def get_jev_client() -> JevClient:
    """Process-wide client, built lazily on the first judgement."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = JevClient()
    return _CLIENT


# ── state / questions ───────────────────────────────────────────────────────
def question_variant() -> str:
    variant = os.environ.get("MSWEA_JEV_QUESTION", "needed").strip().lower() or "needed"
    if variant not in QUESTION_VARIANTS:
        raise ValueError(f"MSWEA_JEV_QUESTION must be one of {QUESTION_VARIANTS}, got {variant!r}")
    return variant


def needed_question(variant: str | None = None) -> dict:
    """The one noul question, under the ``MSWEA_JEV_QUESTION`` wording (the
    question key stays ``needed`` for both wordings)."""
    variant = variant or question_variant()
    # 2026-11-18: probe wordings disabled (constants commented out above)
    # if variant == "budget":
    #     return {QUESTION_NAME: {"type": "noul", "instructions": BUDGET_INSTRUCTIONS,
    #                             "criteria": dict(BUDGET_CRITERIA)}}
    # if variant == "score":
    #     return {QUESTION_NAME: {"type": "score", "instructions": SCORE_INSTRUCTIONS,
    #                             "criteria": list(SCORE_LEVELS)}}
    # if variant == "aligned":
    #     return {QUESTION_NAME: {"type": "noul", "instructions": NEEDED_INSTRUCTIONS,
    #                             "criteria": dict(ALIGNED_CRITERIA)}}
    return {QUESTION_NAME: {"type": "noul", "instructions": NEEDED_INSTRUCTIONS,
                            "criteria": dict(NEEDED_CRITERIA)}}


def _preamble(variant: str, full: bool) -> str:
    # 2026-11-18: probe wordings disabled (constants commented out above)
    # if variant == "aligned":
    #     return ALIGNED_PREAMBLE_FULL if full else ALIGNED_PREAMBLE
    base = JUDGE_PREAMBLE_FULL if full else JUDGE_PREAMBLE
    # return base + {"budget": BUDGET_PREAMBLE_NOTE, "score": SCORE_PREAMBLE_NOTE}.get(variant, "")
    return base


def answer_probability(answer: dict, variant: str) -> tuple[float, dict]:
    """The message's p from Jev's answer: the noul value, or for ``score`` the
    probability-weighted level divided by the top level number (0 .. 1).
    Returns (p, extras) with the score's ``score`` / ``level_probs`` /
    ``confidence`` in extras; raises JevAPIError when the answer lacks the value."""
    # 2026-11-18: the ``score`` wording is disabled (SCORE_LEVELS commented out above)
    # if variant == "score":
    #     s = answer.get("score")
    #     if not isinstance(s, (int, float)):
    #         raise JevAPIError(f"no score answer for {QUESTION_NAME!r} in {str(answer)[:200]}")
    #     top = len(SCORE_LEVELS) - 1
    #     return min(1.0, max(0.0, float(s) / top)), {
    #         "score": float(s), "level_probs": answer.get("probabilities"), "confidence": answer.get("confidence")}
    p = answer.get("noul")
    if not isinstance(p, (int, float)):
        raise JevAPIError(f"no noul answer for {QUESTION_NAME!r} in {str(answer)[:200]}")
    return float(p), {}


def judge_state(task_text: str, activity_text: str, candidate_text: str, history_text: str = "",
                variant: str | None = None) -> str:
    """The ``state`` Jev is shown for one candidate: preamble, task statement,
    the agent's newest turn (when any), the candidate. With ``history_text``
    (``MSWEA_JEV_HISTORY=full``) the complete history, rendered as the
    generative selector sees it, sits between the task statement and the
    candidate, and the candidate is repeated after it. ``variant`` (default
    ``MSWEA_JEV_QUESTION``) ``budget`` appends the relative-judgement note
    to the preamble."""
    variant = variant or question_variant()
    if history_text:
        parts = [_preamble(variant, True), f"Task statement:\n{task_text}",
                 "Complete history of the agent so far (every message, in order, each under its "
                 f"uid header; the newest turn is kept regardless):\n{history_text}"]
        if activity_text:
            parts.append(f"The agent's newest turn (its current activity; kept regardless, not the "
                         f"message to judge):\n{activity_text}")
        parts.append(f"Candidate history message to judge (repeated from the history above):\n{candidate_text}")
        return "\n\n".join(parts)
    parts = [_preamble(variant, False), f"Task statement:\n{task_text}"]
    if activity_text:
        parts.append("The agent's newest turn (its current activity; kept regardless, not the "
                     f"message to judge):\n{activity_text}")
    parts.append(f"Candidate history message to judge:\n{candidate_text}")
    return "\n\n".join(parts)


def _truncate_to(text: str, max_bytes: int) -> tuple[str, int]:
    """Head and tail of ``text`` within ``max_bytes`` (UTF-8), the note in between;
    returns (text, characters removed)."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text, 0
    room = max(0, max_bytes - len(TRUNCATED_NOTE.format(n=len(text)).encode("utf-8")) - 2)
    head_n, tail_n = room * 2 // 3, room - room * 2 // 3
    head = data[:head_n].decode("utf-8", errors="ignore")
    tail = data[len(data) - tail_n:].decode("utf-8", errors="ignore") if tail_n else ""
    removed = len(text) - len(head) - len(tail)
    return head + "\n" + TRUNCATED_NOTE.format(n=removed) + "\n" + tail, removed


# ── selection ───────────────────────────────────────────────────────────────
def judge_messages(client: JevClient, task_text: str, activity_text: str, window: list[dict],
                   render, settings: dict, progress: dict | None = None, history_text: str = "") -> list[dict]:
    """One Jev judgement per message of ``window``, in parallel (``workers``).

    ``render(msg) -> str`` is the selector's message renderer (uid header,
    numbered lines). Returns one record per message, window order: uid, index,
    p (None on error), tokens (usage), latency_s, attempts, long_context /
    truncated, model, request_id, error. ``progress`` (optional) is updated
    under a lock as results arrive (``attempts``, ``prompt_tokens``,
    ``completion_tokens``, ``response_ids``) so an exception that ends the
    selection leaves the usage of the completed judgements salvageable.
    """
    from agentctx.compression.primitives import _msg_uid   # local: primitives imports this module lazily

    lock = threading.Lock()
    variant = settings.get("question", "needed")
    question = needed_question(variant)
    fixed = judge_state(task_text, activity_text, "", history_text, variant)
    fixed_bytes = len(fixed.encode("utf-8"))

    def one(index: int, msg: dict) -> dict:
        uid = _msg_uid(msg) or "?"
        text = render(msg)
        rec = {"uid": uid, "index": index, "p": None, "input_tokens": 0, "output_tokens": 0,
               "latency_s": 0.0, "attempts": 0, "long_context": False, "truncated": 0,
               "model": None, "request_id": None, "error": None}
        if msg.get("members"):   # a turn group (MSWEA_JEV_UNIT=turn): one judgement for all of them
            rec["members"] = [_msg_uid(m) or "?" for m in msg["members"]]
        long_context = fixed_bytes + len(text.encode("utf-8")) > LONG_CONTEXT_BYTES
        if long_context and settings["long_context"] == "truncate":
            text, rec["truncated"] = _truncate_to(text, max(1000, LONG_CONTEXT_BYTES - fixed_bytes))
            long_context = False
        rec["long_context"] = long_context
        state = judge_state(task_text, activity_text, text, history_text, variant)
        t0 = time.time()
        try:
            reply = client.system_one(state, question, long_context=long_context)
            answer = (reply["answers"] or {}).get(QUESTION_NAME) or {}
            p, extras = answer_probability(answer, variant)
            usage = reply["usage"] or {}
            rec.update(extras)
            rec.update({"p": p, "input_tokens": int(usage.get("input_tokens") or 0),
                        "output_tokens": int(usage.get("output_tokens") or 0), "attempts": reply["attempts"],
                        "model": reply["model"], "request_id": reply["request_id"]})
        except JevAPIError as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["status"] = exc.status
            if exc.status in _AUTH_STATUSES:
                rec["fatal"] = True
        except Exception as exc:   # noqa: BLE001 - recorded per message
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["latency_s"] = round(time.time() - t0, 3)
        if progress is not None:
            with lock:
                progress["attempts"] = progress.get("attempts", 0) + max(1, rec["attempts"])
                progress["prompt_tokens"] = progress.get("prompt_tokens", 0) + rec["input_tokens"]
                progress["completion_tokens"] = progress.get("completion_tokens", 0) + rec["output_tokens"]
                progress.setdefault("response_ids", []).append(rec["request_id"])
        _log_judgement({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec, "state_bytes": len(state.encode("utf-8"))})
        return rec

    with ThreadPoolExecutor(max_workers=min(settings["workers"], max(1, len(window)))) as pool:
        return list(pool.map(lambda im: one(*im), enumerate(window)))


def decide(judgements: list[dict], prev_uids: set, threshold: float, anchor_bonus: float,
           budget_tokens: int | None, token_of) -> tuple[dict, dict]:
    """Keep / drop from the judgements.

    score = p + anchor_bonus (for a message in the agent's context at the
    previous step); kept when score >= threshold. An errored judgement (p None)
    is kept. Under ``budget_tokens`` the kept messages are ranked by score
    (ties: the newer first) and taken greedily while they fit (``token_of(rec)``
    gives a message's tokens; a message that does not fit is skipped and the
    smaller ones after it are still tried). Returns ({uid: None}, extras):
    extras has scores, kept_by_threshold, capped_out (uids ranked out by the
    cap), errors.
    """
    scores: dict[str, float | None] = {}
    above: list[dict] = []
    for rec in judgements:
        uid = rec["uid"]
        if rec["p"] is None:
            scores[uid] = None
            above.append(rec)
            continue
        score = rec["p"] + (anchor_bonus if uid in prev_uids else 0.0)
        scores[uid] = round(score, 4)
        if score >= threshold:
            above.append(rec)
    capped_out: list[str] = []
    if budget_tokens is None:
        chosen = {rec["uid"] for rec in above}
    else:
        ranked = sorted(above, key=lambda r: (-(2.0 if scores[r["uid"]] is None else scores[r["uid"]]), -r["index"]))
        chosen, room = set(), budget_tokens
        for rec in ranked:
            need = token_of(rec)
            if need <= room:
                chosen.add(rec["uid"]); room -= need
            else:
                capped_out.append(rec["uid"])
    selection = {rec["uid"]: None for rec in judgements if rec["uid"] in chosen}
    extras = {
        "scores": scores,
        "kept_by_threshold": len(above),
        "capped_out": capped_out,
        "errors": sum(1 for r in judgements if r["error"]),
    }
    return selection, extras


def jev_select_window(task_text: str, window: list[dict], kept: list[dict], prev_uids: set,
                      budget_tokens: int | None, render, anchor: bool, token_of,
                      progress: dict | None = None, client: JevClient | None = None,
                      ) -> tuple[dict, dict, int, int, float, list]:
    """The Jev backend of online_claude_select(): judge every message of
    ``window``, decide, and return (selection {uid: None}, record, input_tokens,
    output_tokens, wall latency_s, request_ids).

    ``kept`` is the tail kept verbatim (the newest turn[s]); its newest
    ``context_turns`` turns are shown to Jev as the agent's current activity.
    ``prev_uids`` are the uids in the agent's context at the previous step
    (the anchor bonus applies to them only when ``anchor``). Raises JevAPIError
    when any judgement hit an authentication failure or every judgement failed.
    """
    settings = jev_settings()
    client = client or get_jev_client()
    activity_text = ""
    if settings["context_turns"] and kept:
        turns = 0
        start = len(kept)
        for i in range(len(kept) - 1, -1, -1):
            if kept[i].get("role") == "assistant":
                turns += 1
                start = i
                if turns >= settings["context_turns"]:
                    break
        activity_text = "\n\n".join(render(m) for m in kept[start:]) if turns else "\n\n".join(render(m) for m in kept)
    history_text = ""
    if settings["history"] == "full":
        history_text = "\n\n".join(render(m) for m in list(window) + list(kept))
    # The judged units: every message on its own, or (MSWEA_JEV_UNIT=turn) each assistant
    # message together with the observations that follow it, kept or dropped together.
    from agentctx.compression.primitives import _msg_uid   # local: primitives imports this module lazily
    if settings["unit"] == "turn":
        groups: list[list[dict]] = []
        for m in window:
            if m.get("role") == "assistant" or not groups:
                groups.append([m])
            else:
                groups[-1].append(m)
        units = [{"role": "turn", "extra": {"uid": _msg_uid(g[0]) or "?"}, "members": g} for g in groups]
        unit_render = lambda u: "\n\n".join(render(m) for m in u["members"])   # noqa: E731
    else:
        units = list(window)
        unit_render = render
    members_of = {(_msg_uid(u) or "?"): (u["members"] if u.get("members") else [u]) for u in units}
    t0 = time.time()
    judgements = judge_messages(client, task_text, activity_text, units, unit_render, settings,
                                progress=progress, history_text=history_text)
    latency_s = time.time() - t0
    fatal = [r for r in judgements if r.get("fatal")]
    if fatal:
        raise JevAPIError(f"TypeSafe authentication failed: {fatal[0]['error']}", status=fatal[0].get("status"))
    if judgements and all(r["error"] for r in judgements):
        raise JevAPIError(f"every Jev judgement failed ({len(judgements)}); first: {judgements[0]['error']}")
    # The anchor bonus applies to a unit when any of its messages was in the previous context.
    unit_prev = {r["uid"] for r in judgements
                 if any((_msg_uid(m) or "?") in prev_uids for m in members_of[r["uid"]])} if anchor else set()
    # Line-level selection (MSWEA_JEV_SELECT_LINES): the long observations of the units
    # that pass the keep threshold are judged line by line, in parallel, BEFORE the cap
    # ranking, so the cap admits a message by its trimmed size.
    trims: dict[str, dict] = {}
    if settings["select_lines"] > 0:
        bonus = settings["anchor_bonus"] if anchor else 0.0
        candidates = []
        for r in judgements:
            if r["p"] is None or r["p"] + (bonus if r["uid"] in unit_prev else 0.0) >= settings["threshold"]:
                candidates.extend(m for m in members_of[r["uid"]]
                                  if m.get("role") != "assistant" and token_of(m) > settings["select_lines"])
        trims = trim_observations(client, task_text, window, candidates, settings, render, token_of,
                                  progress=progress)
    def unit_tokens(uid: str) -> int:
        total = 0
        for m in members_of[uid]:
            t = trims.get(_msg_uid(m) or "?")
            total += t["tokens_after"] if t and t["ranges"] is not None else token_of(m)
        return total
    tok = {r["uid"]: unit_tokens(r["uid"]) for r in judgements}
    unit_selection, extras = decide(judgements, unit_prev, settings["threshold"],
                                    settings["anchor_bonus"] if anchor else 0.0, budget_tokens,
                                    token_of=lambda r: tok[r["uid"]])
    # Expand unit-level results to message uids (identity when the unit is the message);
    # a trimmed observation is kept as its line ranges.
    chosen_uids = {(_msg_uid(m) or "?") for uid in unit_selection for m in members_of[uid]}
    selection: dict = {}
    for m in window:
        uid = _msg_uid(m) or "?"
        if uid not in chosen_uids:
            continue
        t = trims.get(uid)
        selection[uid] = None if (t is None or t["ranges"] is None) else [tuple(r) for r in t["ranges"]]
    by_uid = {(_msg_uid(m) or "?"): r for r in judgements for m in members_of[r["uid"]]}
    scores = {(_msg_uid(m) or "?"): extras["scores"][r["uid"]] for r in judgements for m in members_of[r["uid"]]}
    capped_out = [(_msg_uid(m) or "?") for uid in extras["capped_out"] for m in members_of[uid]]
    input_tokens = sum(r["input_tokens"] for r in judgements) + sum(t["input_tokens"] for t in trims.values())
    output_tokens = sum(r["output_tokens"] for r in judgements) + sum(t["output_tokens"] for t in trims.values())
    record = {
        "backend": "jev", "model": settings["model"],
        "resolved_model": next((r["model"] for r in judgements if r["model"]), None),
        "threshold": settings["threshold"],
        "anchor_bonus": settings["anchor_bonus"] if anchor else 0.0,
        "context_turns": settings["context_turns"], "history": settings["history"],
        "question": settings["question"], "unit": settings["unit"], "units": len(units),
        "requests": len(judgements), "request_attempts": sum(r["attempts"] for r in judgements),
        "errors": extras["errors"], "long_context": sum(1 for r in judgements if r["long_context"]),
        "truncated": sum(1 for r in judgements if r["truncated"]),
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "latency_s": round(latency_s, 3), "latency_sum_s": round(sum(r["latency_s"] for r in judgements), 3),
        "probs": {uid: (None if r["p"] is None else round(r["p"], 4)) for uid, r in by_uid.items()},
        "scores": scores,
        "kept_by_threshold": extras["kept_by_threshold"], "capped_out": capped_out,
        "select_lines": settings["select_lines"],
    }
    request_ids = [r["request_id"] for r in judgements]
    if settings["select_lines"] > 0:
        record.update({
            "lines": {uid: {k: v for k, v in t.items() if k != "request_ids"} for uid, t in trims.items()},
            "line_requests": sum(t["requests"] for t in trims.values()),
            "line_input_tokens": sum(t["input_tokens"] for t in trims.values()),
            "line_output_tokens": sum(t["output_tokens"] for t in trims.values()),
            "line_trimmed": sum(1 for t in trims.values() if t["ranges"] is not None),
            "line_errors": sum(1 for t in trims.values() if t["error"]),
            "line_latency_s": round(sum(t["latency_s"] for t in trims.values()), 3),
        })
        for t in trims.values():
            request_ids.extend(t["request_ids"])
    return selection, record, input_tokens, output_tokens, latency_s, request_ids


def trim_observations(client: JevClient, task_text: str, window: list[dict], observations: list[dict],
                      settings: dict, render, token_of, progress: dict | None = None) -> dict[str, dict]:
    """Line-level selection of ``observations`` (window messages, each judged
    once; MSWEA_JEV_SELECT_LINES): every output goes to jev_extract_output()
    with LINE_PREAMBLE_SELECT, the task statement and the nearest assistant
    message before it in ``window`` (the command that produced it), in
    parallel across outputs. Returns {uid: {ranges (None = kept whole, [] =
    only the omission marker stays), lines, kept_lines, tokens_before,
    tokens_after, requests, input_tokens, output_tokens, errors, latency_s,
    request_ids, error}}. A failed judgement (every request of the output
    failed, or any other error) keeps the output whole and records ``error``;
    an authentication failure raises JevAPIError.
    """
    from agentctx.compression.primitives import _msg_uid, _msg_text, apply_selection
    if not observations:
        return {}
    index_of = {id(m): i for i, m in enumerate(window)}

    def command_text(m: dict) -> str:
        i = index_of.get(id(m))
        if i is None:
            return ""
        for j in range(i - 1, -1, -1):
            if window[j].get("role") == "assistant":
                return render(window[j])
        return ""

    def one(m: dict) -> tuple[str, dict]:
        uid = _msg_uid(m) or "?"
        before = token_of(m)
        rec = {"ranges": None, "lines": len(_msg_text(m).split("\n")), "kept_lines": None,
               "tokens_before": before, "tokens_after": before, "requests": 0, "input_tokens": 0,
               "output_tokens": 0, "errors": 0, "latency_s": 0.0, "request_ids": [], "error": None}
        try:
            ranges, lrec, pt, ct, lat, ids = jev_extract_output(
                task_text, command_text(m), _msg_text(m), uid, progress=progress, client=client,
                preamble=LINE_PREAMBLE_SELECT, kind="select_lines")
            rec.update({"requests": lrec["requests"], "input_tokens": pt, "output_tokens": ct,
                        "errors": lrec["errors"], "latency_s": round(lat, 3), "request_ids": list(ids),
                        "kept_lines": lrec["kept_lines"]})
            if ranges is not None:
                rec["ranges"] = [list(r) for r in ranges]
                rec["tokens_after"] = token_of(apply_selection([m], {uid: [tuple(r) for r in ranges]})[0])
            else:
                rec["kept_lines"] = rec["lines"]
        except JevAPIError as exc:
            if exc.status in _AUTH_STATUSES:
                raise
            rec["error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:   # noqa: BLE001 - recorded per output; the output stays whole
            rec["error"] = f"{type(exc).__name__}: {exc}"
        return uid, rec

    seen: dict[int, dict] = {}
    for m in observations:          # each message once, window order
        seen.setdefault(id(m), m)
    todo = sorted(seen.values(), key=lambda m: index_of.get(id(m), 0))
    # The line judge runs its own pool per output; keep the outer fan-out modest.
    outer = max(1, min(4, settings["workers"], len(todo)))
    with ThreadPoolExecutor(max_workers=outer) as pool:
        return dict(pool.map(one, todo))


# ── Line-level output extraction (MSWEA_OUTPUT_EXTRACT_BACKEND=jev, added 2026-11-17) ──
#
# The per-output pre-extraction of the ocstx cells (primitives.extract_tool_output)
# hands every new tool output above MSWEA_OUTPUT_EXTRACT_ABOVE to the generative
# extractor, which answers with line ranges. This backend puts the same question
# to Jev, one noul PER LINE (or per block of MSWEA_JEV_LINE_BLOCK lines), all in
# ONE request per output: the state holds the task statement, the command and the
# output with every line tagged ``L0042| ``, and the questions name the lines.
# Jev reads the state once and answers the questions in parallel, so an output of
# a few hundred lines costs one state's worth of input tokens (TypeSafe's
# "line-by-line search" cookbook works the same way with a Choice over line ids).
# The kept lines are those whose probability clears MSWEA_JEV_LINE_THRESHOLD,
# widened by MSWEA_JEV_LINE_PAD lines on each side and, under
# MSWEA_JEV_LINE_MAX_FRACTION, ranked by probability and cut to that share of
# the lines; they are merged into ranges and rendered by the caller exactly as a
# generative ``keep <uid> L<a>-<b>`` reply would be. A request whose questions
# would push the request past the long-context size is split into several
# requests that each carry the whole state (MSWEA_JEV_LINE_QUESTIONS caps the
# questions per request; 0 = by size).
DEFAULT_LINE_THRESHOLD = 0.5
DEFAULT_LINE_BLOCK = 1
DEFAULT_LINE_PAD = 0
LINE_PREAMBLE = (
    "An autonomous software-engineering agent fixes a bug in a repository by running one "
    "shell command per step. The output of its newest command is being trimmed before it "
    "enters the agent's context window: every line of the output is judged for whether the "
    "agent still needs it. The kept lines stay verbatim, in order, with a marker where "
    "lines were omitted; the omitted lines are deleted and cannot be recovered. Lines worth "
    "keeping: the code the agent is looking for or will edit, the lines that name a file, "
    "function or line number it must act on, an error message with its location, a failing "
    "or passing test's verdict, and the few lines that carry a result the agent asked for. "
    "Lines to omit: installation and download noise, long listings, boilerplate, repeated "
    "or decorative output, and code unrelated to the task. Each line is tagged with its id "
    "(L0001| ...)."
)
# The wording for line-level SELECTION (MSWEA_JEV_SELECT_LINES): the output is already
# in the agent's history and is being trimmed as the context is rebuilt. Unlike the
# pre-extraction, what is omitted leaves the context window, not the history, so the
# preamble does not call the omitted lines unrecoverable. Same line guidance.
LINE_PREAMBLE_SELECT = (
    "An autonomous software-engineering agent fixes a bug in a repository by running one "
    "shell command per step. Its context window is being rebuilt from its history, and the "
    "output of one of its earlier commands is being trimmed: every line of the output is "
    "judged for whether the agent still needs it to finish the task from here. The kept "
    "lines stay verbatim, in order, with a marker where lines were omitted; the omitted "
    "lines leave the agent's context window. Lines worth "
    "keeping: the code the agent is looking for or will edit, the lines that name a file, "
    "function or line number it must act on, an error message with its location, a failing "
    "or passing test's verdict, and the few lines that carry a result the agent asked for. "
    "Lines to omit: installation and download noise, long listings, boilerplate, repeated "
    "or decorative output, code unrelated to the task, and what the agent has already acted "
    "on. Each line is tagged with its id (L0001| ...)."
)
LINE_INSTRUCTIONS_FMT = "The agent still needs line {a} of the output."
LINE_BLOCK_INSTRUCTIONS_FMT = "The agent still needs lines {a} to {b} of the output."


def line_settings() -> dict:
    """The line-extraction settings (environment, read per output)."""
    return {
        "threshold":    _env_float("MSWEA_JEV_LINE_THRESHOLD", DEFAULT_LINE_THRESHOLD, 0.0, 1.0),
        "block":        _env_int("MSWEA_JEV_LINE_BLOCK", DEFAULT_LINE_BLOCK, 1),
        "pad":          _env_int("MSWEA_JEV_LINE_PAD", DEFAULT_LINE_PAD, 0),
        "max_fraction": _env_float("MSWEA_JEV_LINE_MAX_FRACTION", 0.0, 0.0, 1.0),
        "questions":    _env_int("MSWEA_JEV_LINE_QUESTIONS", 0, 0),
    }


def line_id(n: int) -> str:
    return f"L{n:04d}"


def line_state(task_text: str, command_text: str, lines: list[str], preamble: str | None = None) -> str:
    tagged = "\n".join(f"{line_id(i)}| {line}" for i, line in enumerate(lines, 1))
    parts = [preamble or LINE_PREAMBLE, f"Task statement:\n{task_text}"]
    if command_text:
        parts.append(f"The agent's command (the message that produced the output):\n{command_text}")
    parts.append(f"The output, {len(lines)} lines:\n{tagged}")
    return "\n\n".join(parts)


def line_blocks(n_lines: int, block: int) -> list[tuple[int, int]]:
    """1-based inclusive (a, b) blocks of ``block`` lines covering 1..n_lines."""
    return [(a, min(a + block - 1, n_lines)) for a in range(1, n_lines + 1, max(1, block))]


def line_questions(blocks: list[tuple[int, int]]) -> dict:
    qs = {}
    for a, b in blocks:
        text = (LINE_INSTRUCTIONS_FMT.format(a=line_id(a)) if a == b
                else LINE_BLOCK_INSTRUCTIONS_FMT.format(a=line_id(a), b=line_id(b)))
        qs[line_id(a)] = {"type": "noul", "instructions": text}
    return qs


def decide_lines(block_probs: list[tuple[int, int, float | None]], n_lines: int, threshold: float,
                 pad: int, max_fraction: float) -> list[tuple[int, int]]:
    """Kept line ranges from per-block probabilities (None = errored, kept).
    Blocks at or above ``threshold`` are kept, widened by ``pad`` lines each
    side; with ``max_fraction`` > 0 the kept blocks are ranked by probability
    (errored first, then later blocks first on ties) and taken while the kept
    lines stay within that share of ``n_lines``. Returns merged 1-based
    inclusive ranges, [] when nothing is kept."""
    above = [(a, b, p) for a, b, p in block_probs if p is None or p >= threshold]
    if max_fraction > 0 and above:
        limit = max(1, int(round(max_fraction * n_lines)))
        ranked = sorted(above, key=lambda t: (-(2.0 if t[2] is None else t[2]), -t[0]))
        chosen, used = [], 0
        for a, b, p in ranked:
            if used + (b - a + 1) <= limit:
                chosen.append((a, b, p)); used += b - a + 1
        above = sorted(chosen)
    kept = [False] * (n_lines + 2)
    for a, b, _ in above:
        for i in range(max(1, a - pad), min(n_lines, b + pad) + 1):
            kept[i] = True
    ranges: list[tuple[int, int]] = []
    i = 1
    while i <= n_lines:
        if kept[i]:
            j = i
            while j + 1 <= n_lines and kept[j + 1]:
                j += 1
            ranges.append((i, j)); i = j + 1
        else:
            i += 1
    return ranges


def jev_extract_output(task_text: str, command_text: str, output_text: str, uid: str,
                       progress: dict | None = None, client: JevClient | None = None,
                       preamble: str | None = None, kind: str = "lines",
                       ) -> tuple[list[tuple[int, int]] | None, dict, int, int, float, list]:
    """Judge every line (block) of one tool output with Jev and return
    (ranges, record, input_tokens, output_tokens, latency_s, request_ids):
    ranges is None when every line is kept, [] when none is, else the kept
    1-based inclusive ranges. Raises JevAPIError on an authentication failure
    or when every request failed; a failed request keeps its lines.
    ``preamble`` replaces the pre-extraction wording (LINE_PREAMBLE_SELECT for
    line-level selection) and ``kind`` names the judgement-log record."""
    settings = jev_settings()
    ls = line_settings()
    client = client or get_jev_client()
    lines = output_text.split("\n")
    n = len(lines)
    blocks = line_blocks(n, ls["block"])
    state = line_state(task_text, command_text, lines, preamble)
    state_bytes = len(state.encode("utf-8"))
    questions = line_questions(blocks)
    q_bytes = {k: len(json.dumps(v).encode("utf-8")) + len(k) + 8 for k, v in questions.items()}
    # Chunk the questions so a request stays under the long-context size when the
    # state alone does; otherwise every request carries the header.
    keys = list(questions)
    per_request = ls["questions"]
    if per_request:
        chunks = [keys[i:i + per_request] for i in range(0, len(keys), per_request)]
    else:
        room = LONG_CONTEXT_BYTES - state_bytes
        chunks, cur, used = [], [], 0
        for k in keys:
            if cur and room > 0 and used + q_bytes[k] > room:
                chunks.append(cur); cur, used = [], 0
            cur.append(k); used += q_bytes[k]
            if room <= 0 and len(cur) >= 64:
                chunks.append(cur); cur, used = [], 0
        if cur:
            chunks.append(cur)
    lock = threading.Lock()
    results: dict[str, float | None] = {}
    reqs: list[dict] = []

    def one(chunk: list[str]) -> dict:
        qs = {k: questions[k] for k in chunk}
        long_context = state_bytes + sum(q_bytes[k] for k in chunk) > LONG_CONTEXT_BYTES
        rec = {"questions": len(chunk), "long_context": long_context, "input_tokens": 0, "output_tokens": 0,
               "latency_s": 0.0, "attempts": 0, "model": None, "request_id": None, "error": None}
        t0 = time.time()
        try:
            reply = client.system_one(state, qs, long_context=long_context)
            answers = reply["answers"] or {}
            got = {}
            for k in chunk:
                p = (answers.get(k) or {}).get("noul")
                got[k] = float(p) if isinstance(p, (int, float)) else None
            if all(v is None for v in got.values()):
                raise JevAPIError(f"no noul answers in {str(answers)[:200]}")
            usage = reply["usage"] or {}
            rec.update({"input_tokens": int(usage.get("input_tokens") or 0),
                        "output_tokens": int(usage.get("output_tokens") or 0), "attempts": reply["attempts"],
                        "model": reply["model"], "request_id": reply["request_id"]})
            with lock:
                results.update(got)
        except JevAPIError as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["status"] = exc.status
            if exc.status in _AUTH_STATUSES:
                rec["fatal"] = True
            with lock:
                results.update({k: None for k in chunk})
        except Exception as exc:   # noqa: BLE001
            rec["error"] = f"{type(exc).__name__}: {exc}"
            with lock:
                results.update({k: None for k in chunk})
        rec["latency_s"] = round(time.time() - t0, 3)
        if progress is not None:
            with lock:
                progress["attempts"] = progress.get("attempts", 0) + max(1, rec["attempts"])
                progress["prompt_tokens"] = progress.get("prompt_tokens", 0) + rec["input_tokens"]
                progress["completion_tokens"] = progress.get("completion_tokens", 0) + rec["output_tokens"]
                progress.setdefault("response_ids", []).append(rec["request_id"])
        with lock:
            reqs.append(rec)
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(settings["workers"], max(1, len(chunks)))) as pool:
        list(pool.map(one, chunks))
    latency_s = time.time() - t0
    if any(r.get("fatal") for r in reqs):
        bad = next(r for r in reqs if r.get("fatal"))
        raise JevAPIError(f"TypeSafe authentication failed: {bad['error']}", status=bad.get("status"))
    if reqs and all(r["error"] for r in reqs):
        raise JevAPIError(f"every Jev line request failed ({len(reqs)}); first: {reqs[0]['error']}")
    block_probs = [(a, b, results.get(line_id(a))) for a, b in blocks]
    ranges = decide_lines(block_probs, n, ls["threshold"], ls["pad"], ls["max_fraction"])
    kept_lines = sum(b - a + 1 for a, b in ranges)
    probs = {line_id(a): (None if p is None else round(p, 4)) for a, b, p in block_probs}
    record = {
        "backend": "jev", "model": settings["model"],
        "resolved_model": next((r["model"] for r in reqs if r["model"]), None),
        "line_threshold": ls["threshold"], "block": ls["block"], "pad": ls["pad"],
        "max_fraction": ls["max_fraction"], "lines": n, "blocks": len(blocks),
        "requests": len(reqs), "request_attempts": sum(r["attempts"] for r in reqs),
        "errors": sum(1 for r in reqs if r["error"]), "long_context": sum(1 for r in reqs if r["long_context"]),
        "state_bytes": state_bytes,
        "input_tokens": sum(r["input_tokens"] for r in reqs), "output_tokens": sum(r["output_tokens"] for r in reqs),
        "latency_s": round(latency_s, 3), "latency_sum_s": round(sum(r["latency_s"] for r in reqs), 3),
        "probs": probs, "kept_lines": kept_lines,
    }
    _log_judgement({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, "uid": uid,
                    **{k: v for k, v in record.items() if k != "probs"}, "probs": probs,
                    "ranges": [list(r) for r in ranges],
                    "request_ids": [r["request_id"] for r in reqs], "request_errors": [r["error"] for r in reqs if r["error"]]})
    out_ranges: list[tuple[int, int]] | None = ranges
    if kept_lines >= n:
        out_ranges = None
    return out_ranges, record, record["input_tokens"], record["output_tokens"], latency_s, [r["request_id"] for r in reqs]
