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
is rebuilt from the original messages exactly as under the default backend
(whole messages only: no line ranges; combine with the per-output
pre-extraction, ``MSWEA_OUTPUT_EXTRACT_ABOVE``, to trim long outputs).

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
_RETRY_STATUSES = (408, 429, 500, 502, 503, 504)
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


class JevAPIError(RuntimeError):
    """A non-retryable or exhausted TypeSafe API failure (``status`` is the HTTP
    status, None for a transport failure; ``detail`` the response body)."""

    def __init__(self, message: str, status: int | None = None, detail=None):
        super().__init__(message)
        self.status = status
        self.detail = detail


def resolve_api_key() -> str | None:
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
    return {
        "provider":       "typesafe",
        "model":          os.environ.get("MSWEA_JEV_MODEL", "").strip() or DEFAULT_MODEL,
        "base_url":       os.environ.get("TYPESAFE_BASE_URL", "").strip() or DEFAULT_BASE_URL,
        "threshold":      _env_float("MSWEA_JEV_KEEP_THRESHOLD", DEFAULT_THRESHOLD, 0.0, 1.0),
        "anchor_bonus":   _env_float("MSWEA_JEV_ANCHOR_BONUS", DEFAULT_ANCHOR_BONUS, 0.0, 1.0),
        "context_turns":  _env_int("MSWEA_JEV_CONTEXT_TURNS", DEFAULT_CONTEXT_TURNS),
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
                    key = resolve_api_key()
                    if not key:
                        raise RuntimeError(
                            "MSWEA_SELECT_BACKEND=jev needs a TypeSafe API key: export TYPESAFE_API_KEY "
                            f"or write it to {DEFAULT_KEY_FILE} (AGENTCTX_TYPESAFE_API_KEY_FILE)."
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
def needed_question() -> dict:
    return {QUESTION_NAME: {"type": "noul", "instructions": NEEDED_INSTRUCTIONS,
                            "criteria": dict(NEEDED_CRITERIA)}}


def judge_state(task_text: str, activity_text: str, candidate_text: str) -> str:
    """The ``state`` Jev is shown for one candidate: preamble, task statement,
    the agent's newest turn (when any), the candidate."""
    parts = [JUDGE_PREAMBLE, f"Task statement:\n{task_text}"]
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
                   render, settings: dict, progress: dict | None = None) -> list[dict]:
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
    fixed = judge_state(task_text, activity_text, "")
    fixed_bytes = len(fixed.encode("utf-8"))

    def one(index: int, msg: dict) -> dict:
        uid = _msg_uid(msg) or "?"
        text = render(msg)
        rec = {"uid": uid, "index": index, "p": None, "input_tokens": 0, "output_tokens": 0,
               "latency_s": 0.0, "attempts": 0, "long_context": False, "truncated": 0,
               "model": None, "request_id": None, "error": None}
        long_context = fixed_bytes + len(text.encode("utf-8")) > LONG_CONTEXT_BYTES
        if long_context and settings["long_context"] == "truncate":
            text, rec["truncated"] = _truncate_to(text, max(1000, LONG_CONTEXT_BYTES - fixed_bytes))
            long_context = False
        rec["long_context"] = long_context
        state = judge_state(task_text, activity_text, text)
        t0 = time.time()
        try:
            reply = client.system_one(state, needed_question(), long_context=long_context)
            answer = (reply["answers"] or {}).get(QUESTION_NAME) or {}
            p = answer.get("noul")
            if not isinstance(p, (int, float)):
                raise JevAPIError(f"no noul answer for {QUESTION_NAME!r} in {str(reply['answers'])[:200]}")
            usage = reply["usage"] or {}
            rec.update({"p": float(p), "input_tokens": int(usage.get("input_tokens") or 0),
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
    t0 = time.time()
    judgements = judge_messages(client, task_text, activity_text, window, render, settings, progress=progress)
    latency_s = time.time() - t0
    fatal = [r for r in judgements if r.get("fatal")]
    if fatal:
        raise JevAPIError(f"TypeSafe authentication failed: {fatal[0]['error']}", status=fatal[0].get("status"))
    if judgements and all(r["error"] for r in judgements):
        raise JevAPIError(f"every Jev judgement failed ({len(judgements)}); first: {judgements[0]['error']}")
    by_uid = {r["uid"]: r for r in judgements}
    tok = {r["uid"]: token_of(window[r["index"]]) for r in judgements}
    selection, extras = decide(judgements, prev_uids if anchor else set(), settings["threshold"],
                               settings["anchor_bonus"] if anchor else 0.0, budget_tokens,
                               token_of=lambda r: tok[r["uid"]])
    input_tokens = sum(r["input_tokens"] for r in judgements)
    output_tokens = sum(r["output_tokens"] for r in judgements)
    record = {
        "backend": "jev", "model": settings["model"],
        "resolved_model": next((r["model"] for r in judgements if r["model"]), None),
        "threshold": settings["threshold"],
        "anchor_bonus": settings["anchor_bonus"] if anchor else 0.0,
        "context_turns": settings["context_turns"],
        "requests": len(judgements), "request_attempts": sum(r["attempts"] for r in judgements),
        "errors": extras["errors"], "long_context": sum(1 for r in judgements if r["long_context"]),
        "truncated": sum(1 for r in judgements if r["truncated"]),
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "latency_s": round(latency_s, 3), "latency_sum_s": round(sum(r["latency_s"] for r in judgements), 3),
        "probs": {uid: (None if r["p"] is None else round(r["p"], 4)) for uid, r in by_uid.items()},
        "scores": extras["scores"],
        "kept_by_threshold": extras["kept_by_threshold"], "capped_out": extras["capped_out"],
    }
    request_ids = [r["request_id"] for r in judgements]
    return selection, record, input_tokens, output_tokens, latency_s, request_ids
