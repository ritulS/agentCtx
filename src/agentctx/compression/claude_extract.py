"""Claude-backed context extractor for the ``online_claude_extract`` and
``online_claude_select`` primitives.

``online_claude_extract`` (``primitives.online_claude_extract``) fires once after every agent
model call. It hands the compressible window of the history (everything
after the protected system prompt and task statement) to Claude and replaces
that window with the task-relevant information Claude extracts. Everything
about *talking to Claude* lives here; the primitive itself only builds the
prompt and splices the reply into the history.

``ClaudeExtractModel`` is a small adapter with the two methods the summary
machinery in ``primitives.py`` relies on, ``query(messages)`` and
``format_message(role, content)``, and it returns the reply in the same
dict shape mini-swe-agent's litellm models return
(``{"role", "content", "extra": {"response": {...}}}``). That lets the
primitive reuse ``request_summary()`` unchanged: marker validation, retries,
the per-thread outcome record and ``summary_attempts.jsonl``.

``online_claude_select`` (``primitives.online_claude_select``) is the
extractive variant: Claude is shown the agent's complete history with message
ids and numbered output lines and replies with keep/drop directives; the
primitive rebuilds the context from the original text, so Claude never writes
a word the agent reads. Its prompt is a list of text blocks with a cache
breakpoint on the last history block (``_request`` passes block lists
through), so the growing history is served from the prompt cache.

Settings (all environment variables, read once per process):

  ANTHROPIC_API_KEY                 API key. When unset, the file named by
                                    AGENTCTX_ANTHROPIC_API_KEY_FILE
                                    (default ~/.config/agentctx/anthropic_api_key)
                                    is read instead, so the key need not be
                                    exported in every launcher shell.
  MSWEA_EXTRACT_MODEL               default claude-opus-5-5
  MSWEA_EXTRACT_EFFORT              low | medium | high | xhigh | max (default medium)
  MSWEA_EXTRACT_MAX_TOKENS          default 16000
  MSWEA_EXTRACT_TIMEOUT_S           per-request timeout (default 600)
  MSWEA_EXTRACT_FALLBACKS           1 (default) sends the server-side refusal
                                    fallback (`fallbacks: "default"`, beta
                                    server-side-fallback-2026-07-01); 0 disables it.

The adapter does not cost-track: the extractor's usage is reported in the
reply's ``usage`` (prompt/completion tokens plus the cache fields) and the
agent adds it to ``summarization_prompt_tokens`` like any other summarizer.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 16000
DEFAULT_TIMEOUT_S = 600.0
DEFAULT_KEY_FILE = Path("~/.config/agentctx/anthropic_api_key")

_EFFORTS = ("low", "medium", "high", "xhigh", "max")


def resolve_api_key() -> str | None:
    """ANTHROPIC_API_KEY, else the contents of the key file, else None."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    raw = os.environ.get("AGENTCTX_ANTHROPIC_API_KEY_FILE", "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_KEY_FILE.expanduser()
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return key or None


def extract_settings() -> dict:
    """The effective extractor settings (also written to the token log)."""
    effort = os.environ.get("MSWEA_EXTRACT_EFFORT", DEFAULT_EFFORT).strip().lower() or DEFAULT_EFFORT
    if effort not in _EFFORTS:
        raise ValueError(f"MSWEA_EXTRACT_EFFORT must be one of {_EFFORTS}, got {effort!r}")
    fallbacks = os.environ.get("MSWEA_EXTRACT_FALLBACKS", "1").strip().lower() not in ("0", "off", "false", "no")
    return {
        "model":      os.environ.get("MSWEA_EXTRACT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "effort":     effort,
        "max_tokens": int(os.environ.get("MSWEA_EXTRACT_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)) or DEFAULT_MAX_TOKENS),
        "timeout_s":  float(os.environ.get("MSWEA_EXTRACT_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)) or DEFAULT_TIMEOUT_S),
        "fallbacks":  fallbacks,
    }


class ClaudeExtractModel:
    """Minimal model adapter around ``anthropic.Anthropic().beta.messages``.

    ``query(messages)`` takes mini-swe-agent style messages (``role`` in
    system/user/assistant, ``content`` str). System messages become the
    request's ``system`` blocks (cached); the rest are sent as-is. The
    reply is a mini-swe-agent style message whose ``extra["response"]``
    mirrors the OpenAI-compatible shape that ``primitives._response_*``
    read: ``id``, ``usage.prompt_tokens`` / ``completion_tokens`` and
    ``choices[0].finish_reason``. Anthropic stop reasons map to
    ``end_turn -> stop``, ``max_tokens -> length``; a ``refusal`` is returned
    as finish_reason ``refusal`` with empty content, which the marker check
    rejects, so the agent's history is left unchanged for that step.
    """

    def __init__(self, settings: dict | None = None, client=None):
        self.settings = settings or extract_settings()
        self._client = client
        self._lock = threading.Lock()

    # ── mini-swe-agent model surface ────────────────────────────────────────
    def format_message(self, role: str, content: str, **extra) -> dict:
        return {"role": role, "content": content, **({"extra": extra} if extra else {})}

    def get_template_vars(self) -> dict:   # parity with mini-swe-agent models
        return {}

    def serialize(self) -> dict:
        return {"extract_model": dict(self.settings)}

    # ── Anthropic client ────────────────────────────────────────────────────
    def client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import anthropic
                    key = resolve_api_key()
                    if not key:
                        raise RuntimeError(
                            "online_claude_extract needs an Anthropic API key: export ANTHROPIC_API_KEY "
                            f"or write it to {DEFAULT_KEY_FILE} (AGENTCTX_ANTHROPIC_API_KEY_FILE)."
                        )
                    self._client = anthropic.Anthropic(
                        api_key=key, timeout=self.settings["timeout_s"], max_retries=3,
                    )
        return self._client

    def _request(self, messages: list[dict]) -> dict:
        system_blocks = []
        chat = []
        for msg in messages:
            content = msg.get("content") or ""
            if (isinstance(content, list) and content
                    and all(isinstance(b, dict) and b.get("type") == "text" for b in content)):
                # Already Anthropic text blocks (online_claude_select builds
                # them so a cache breakpoint can sit inside the history):
                # pass through, cache_control included.
                blocks = [dict(b) for b in content]
                if msg.get("role") == "system":
                    system_blocks.extend(blocks)
                else:
                    chat.append({"role": msg.get("role", "user"), "content": blocks})
                continue
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if msg.get("role") == "system":
                system_blocks.append({"type": "text", "text": content})
            else:
                chat.append({"role": msg.get("role", "user"), "content": content})
        if system_blocks:
            # Stable prefix: cache the instructions across the run's calls.
            system_blocks[-1]["cache_control"] = {"type": "ephemeral"}
        request = {
            "model":         self.settings["model"],
            "max_tokens":    self.settings["max_tokens"],
            "thinking":      {"type": "adaptive"},
            "output_config": {"effort": self.settings["effort"]},
            "messages":      chat,
        }
        if system_blocks:
            request["system"] = system_blocks
        if self.settings["fallbacks"]:
            # Server-side refusal fallback: a safety decline is re-run on the
            # routed fallback model inside the same call. Passed through
            # extra_body because the installed SDK predates the parameter.
            request["betas"] = ["server-side-fallback-2026-07-01"]
            request["extra_body"] = {"fallbacks": "default"}
        return request

    def query(self, messages: list[dict], **kwargs) -> dict:
        request = self._request(messages)
        response = self.client().beta.messages.create(**request)
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        stop_reason = getattr(response, "stop_reason", None)
        finish_reason = {"end_turn": "stop", "max_tokens": "length"}.get(stop_reason, stop_reason)
        if stop_reason == "refusal":
            text = ""   # never let a refusal explanation into the agent's history
        usage = getattr(response, "usage", None)
        # Anthropic reports input_tokens *excluding* cached reads/writes; the
        # total input the request processed is the sum of the three.
        _uncached = getattr(usage, "input_tokens", 0) or 0
        _cache_rd = getattr(usage, "cache_read_input_tokens", None)
        _cache_wr = getattr(usage, "cache_creation_input_tokens", None)
        usage_dict = {
            "prompt_tokens":     _uncached + (_cache_rd or 0) + (_cache_wr or 0),
            "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
            "uncached_input_tokens":       _uncached,
            "cache_read_input_tokens":     _cache_rd,
            "cache_creation_input_tokens": _cache_wr,
        }
        stop_details = getattr(response, "stop_details", None)
        return {
            "role": "assistant",
            "content": text,
            "extra": {
                "response": {
                    "id":      getattr(response, "id", None),
                    "model":   getattr(response, "model", None),
                    "usage":   usage_dict,
                    "stop_reason":  stop_reason,
                    "stop_details": (stop_details.to_dict() if hasattr(stop_details, "to_dict")
                                     else stop_details),
                    "choices": [{
                        "finish_reason": finish_reason,
                        "message": {"role": "assistant", "content": text},
                    }],
                },
            },
        }


_EXTRACT_MODEL = None
_EXTRACT_MODEL_LOCK = threading.Lock()


def get_extract_model() -> ClaudeExtractModel:
    """Process-wide extractor, built lazily on the first extraction."""
    global _EXTRACT_MODEL
    with _EXTRACT_MODEL_LOCK:
        if _EXTRACT_MODEL is None:
            _EXTRACT_MODEL = ClaudeExtractModel()
    return _EXTRACT_MODEL


def extract_model_info() -> dict:
    """Provenance record for the token log (settings only, never the key)."""
    try:
        settings = extract_settings()
    except ValueError as exc:
        return {"error": str(exc)}
    return {"provider": "anthropic", **settings}
