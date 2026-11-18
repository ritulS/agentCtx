"""CLM self-editing for mini-swe-agent (primitive ``clm``, condition ``clm``).

The mechanism of the CLM harness (context-language-models, ``clm/clm_harness``):
the agent's own history is mirrored to a file in the task container before every
command, the agent compacts it by editing that file with ordinary shell tools, and
after the command the file is read back and, when it changed, mapped back into the
conversation. There is no compression primitive that fires on its own: the budget
only produces nudges, and at the limit rolls the newest turns back and demands a
compaction (``budget.py``).

One :class:`ClmSession` belongs to one agent run. ``DefaultAgent`` builds it when
``MSWEA_PRIMITIVE=clm`` and calls four hooks:

    before_call(agent)                  before every model call: budget check, nudges,
                                        rollback; returns "stop" when the run must end
    after_call(prompt_tokens)           after the model call (calibration, off by default)
    before_actions(agent, message)      before the action runs: write the mirror
    after_actions(agent, message,       after it ran: read the mirror back, apply the
                  outputs, observations)  edit, annotate the observation

What differs from the CLM harness, on purpose:

  * Steps. Every model call counts towards the agent's step limit, as in every other
    agentCtx condition. The CLM harness does not count a pure compaction turn; here
    it does, and the prompt (``configs/config-clm.yaml``) no longer calls it free.
  * Budget ruler. Tokens are agentCtx's ``count_tokens`` (tiktoken cl100k, content
    only), so a ``b<N>k`` cell means the same number as in the other conditions.
    ``MSWEA_CLM_CALIBRATE=1`` restores the CLM harness's scaling to the served
    tokenizer.
  * Grading. Only a submitted patch is evaluated, so the run that ends at the context
    limit has no submission (exit status ``ContextBudgetExceeded``).
  * The CLM harness's step-count "FINAL TURN" notice is not ported: it is not part of
    the context mechanism and no other agentCtx condition has it.

Event log: an applied edit is one ``clm_edit`` record in ``compression_events.jsonl``.
The edited mirror is free text, so the record is a replacement of the whole editable
window: every message after the protected prefix is ``dropped`` and the messages
parsed back from the file are ``added`` with new uids (also the turns the edit left
untouched). A rollback is a ``clm_rollback`` record (rolled-back turns ``dropped``,
the pinned ledger ``added`` the first time and ``replaced`` afterwards).

Settings (environment, read once per run; defaults are the CLM harness's):

    MSWEA_TOKEN_BUDGET            context budget; empty, <= 0 or the unlimited sentinel
                                  = no budget (mirror editing only, no nudges)
    MSWEA_CLM_RESERVE_TOKENS      2048   limit = budget - reserve
    MSWEA_CLM_NUDGE_RATIOS        0.25,0.5,0.75
    MSWEA_CLM_PERSISTENT_NUDGE    adaptive | none | <fraction of the limit>
    MSWEA_CLM_MAX_RETRY_ON_LIMIT  50     rollbacks before the final turn
    MSWEA_CLM_RETRY_MARGIN_TOKENS 2048   room a rollback frees
    MSWEA_CLM_EDIT_GATE           fit | shrink   (fit: an edit may grow if it fits)
    MSWEA_CLM_CALIBRATE           0 | 1
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Any

import tiktoken

from agentctx import INFINITE_BUDGET
from agentctx.compression.clm.budget import BudgetController
from agentctx.compression.clm.context_string import parse_back, render_editable
from agentctx.compression.primitives import N_PROTECTED, count_tokens

PRIMITIVE = "clm"
CTX_DIR = "/tmp/.live_ctx"
CTX_FILE = f"{CTX_DIR}/LIVE_CTX_MAIN.txt"
EXIT_STATUS_BUDGET = "ContextBudgetExceeded"

#: An applied edit that moves fewer tokens than this is mirror noise (a trailing newline,
#: a line rewritten identically), not context management; ``clm_edits_real`` skips it.
TRIVIAL_EDIT_TOKENS = 32
TRIVIAL_EDIT_FRACTION = 0.01

_IO_TIMEOUT_S = 60
_SHRINK_RULE = "A compaction must SHRINK context"
_COMPACTION_HINT = (
    f"Compact {CTX_FILE} by locating stale regions with code (match a turn by its "
    "[[CTX_TURN i ...]] header or a block by short start/end anchors) and replacing "
    "them with summaries — do not retype the text you remove. Compact settled spans; "
    "keep anything you have not finished using."
)


def _env_int(env, name: str, default: int) -> int:
    raw = (env.get(name) or "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class ClmSettings:
    budget_tokens: int = 0                 # 0 = no budget
    reserve_tokens: int = 2048
    nudge_ratios: tuple[float, ...] = (0.25, 0.5, 0.75)
    persistent_nudge: float | str | None = "adaptive"
    max_retry_on_limit: int = 50
    retry_margin_tokens: int = 2048
    allow_edit_growth: bool = True         # "fit" gate; False = "shrink"
    calibrate: bool = False

    @classmethod
    def from_env(cls, env=None) -> "ClmSettings":
        env = os.environ if env is None else env
        budget = _env_int(env, "MSWEA_TOKEN_BUDGET", 0)
        if budget <= 0 or budget >= INFINITE_BUDGET:
            budget = 0
        ratios = env.get("MSWEA_CLM_NUDGE_RATIOS")
        nudge_ratios = (
            cls.nudge_ratios if ratios is None
            else tuple(float(x) for x in ratios.split(",") if x.strip())
        )
        raw_persistent = (env.get("MSWEA_CLM_PERSISTENT_NUDGE") or "adaptive").strip().lower()
        if raw_persistent == "adaptive":
            persistent: float | str | None = "adaptive"
        elif raw_persistent in ("none", "null", "off", "0"):
            persistent = None
        else:
            persistent = float(raw_persistent)
        gate = (env.get("MSWEA_CLM_EDIT_GATE") or "fit").strip().lower()
        if gate not in ("fit", "shrink"):
            raise ValueError(f"MSWEA_CLM_EDIT_GATE must be fit or shrink, got {gate!r}")
        settings = cls(
            budget_tokens=budget,
            reserve_tokens=_env_int(env, "MSWEA_CLM_RESERVE_TOKENS", cls.reserve_tokens),
            nudge_ratios=nudge_ratios,
            persistent_nudge=persistent,
            max_retry_on_limit=_env_int(env, "MSWEA_CLM_MAX_RETRY_ON_LIMIT", cls.max_retry_on_limit),
            retry_margin_tokens=_env_int(env, "MSWEA_CLM_RETRY_MARGIN_TOKENS", cls.retry_margin_tokens),
            allow_edit_growth=gate == "fit",
            calibrate=(env.get("MSWEA_CLM_CALIBRATE") or "0").strip().lower() in ("1", "true", "yes", "on"),
        )
        if settings.budget_tokens and settings.budget_tokens <= settings.reserve_tokens:
            raise ValueError(
                f"clm: budget {settings.budget_tokens} must exceed the reserve "
                f"{settings.reserve_tokens} (MSWEA_CLM_RESERVE_TOKENS)"
            )
        return settings


# ── Mirror transfer ─────────────────────────────────────────────────────────────
# An environment may provide write_file(path, text) / read_file(path) -> str | None
# itself. mini-swe-agent's DockerEnvironment does not, so for it the file goes through
# `<executable> exec` on stdin / stdout (a context is far larger than one argv string
# may be, so it cannot ride on the command line of env.execute()).

def _docker_target(env) -> tuple[str, str] | None:
    container = getattr(env, "container_id", None)
    executable = getattr(getattr(env, "config", None), "executable", None)
    return (executable, container) if container and executable else None


def write_mirror(env, path: str, text: str) -> None:
    if hasattr(env, "write_file"):
        env.write_file(path, text)
        return
    target = _docker_target(env)
    if target is None:
        raise RuntimeError(
            "clm needs an environment that can hold the context mirror: one with "
            "write_file/read_file, or a docker/podman container (container_id + "
            f"config.executable); got {type(env).__name__}"
        )
    executable, container = target
    quoted = shlex.quote(path)
    result = subprocess.run(
        [executable, "exec", "-i", container, "bash", "-c",
         f"mkdir -p {shlex.quote(os.path.dirname(path))} && cat > {quoted}"],
        input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=_IO_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"clm: writing the context mirror failed (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace')[:500]}"
        )


def read_mirror(env, path: str) -> str | None:
    """The mirror's text, or None when it cannot be read (deleted, container gone)."""
    try:
        if hasattr(env, "read_file"):
            return env.read_file(path)
        target = _docker_target(env)
        if target is None:
            return None
        executable, container = target
        result = subprocess.run(
            [executable, "exec", container, "cat", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=_IO_TIMEOUT_S,
        )
        if result.returncode != 0:
            return None
        return result.stdout.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - an unreadable mirror means "no edit"
        return None


def _is_observation(msg: dict[str, Any]) -> bool:
    """A command result as the text-based agent stores it (a user message whose
    ``extra`` carries the raw output), or a ``tool`` message."""
    if msg.get("role") == "tool":
        return True
    extra = msg.get("extra")
    return msg.get("role") == "user" and isinstance(extra, dict) and "raw_output" in extra


class ClmSession:
    """State of the CLM mechanism for one agent run. See the module docstring."""

    def __init__(self, settings: ClmSettings | None = None) -> None:
        self.settings = settings or ClmSettings()
        self.protect = N_PROTECTED          # grows by one when the rollback ledger is pinned
        self.budget = BudgetController(
            self.settings.budget_tokens,
            count_fn=count_tokens,
            encoder=tiktoken.get_encoding("cl100k_base"),   # the encoding count_tokens uses
            is_observation=_is_observation,
            reserve_tokens=self.settings.reserve_tokens,
            nudge_ratios=list(self.settings.nudge_ratios),
            compaction_hint=_COMPACTION_HINT,
            persistent_nudge_ratio=self.settings.persistent_nudge,
            max_num_retry_on_limit=self.settings.max_retry_on_limit,
            retry_edit_margin_tokens=self.settings.retry_margin_tokens,
            protect_prefix=self.protect,
            calibrate=self.settings.calibrate,
        )
        # One record per command that changed the mirror or tried to (token log).
        self.events: list[dict[str, Any]] = []
        self.budget_log: list[dict[str, Any]] = []
        self.n_edits = 0
        self.n_edits_real = 0
        self.n_edits_grew = 0
        self.n_edits_rejected = 0
        self.tokens_saved = 0               # signed: sum of (before - after) over applied edits
        self._ledger_index: int | None = None
        self._rolled_back_cmds: list[str] = []
        self._pending: tuple[list[dict], str] | None = None   # (history, rendered mirror)
        self._sent_raw = 0

    @classmethod
    def from_env(cls, env=None) -> "ClmSession":
        return cls(ClmSettings.from_env(env))

    @property
    def budget_label(self) -> str:
        """The ``{{context_budget}}`` of the system prompt: the enforced limit."""
        if not self.budget.enabled:
            return "your model's full context window"
        return f"{self.budget.strict_target} tokens"

    # ── before every model call ──────────────────────────────────────────────
    def before_call(self, agent) -> str:
        """Budget check on the context about to be sent. Appends a nudge or the
        final-turn notice, or rolls the newest turns back. Returns "stop" when the
        final turn has been taken and the context is still over the limit."""
        decision = self.budget.evaluate(agent.messages)
        if decision.log:
            self.budget_log.append({"step": agent.n_calls, **decision.log})
        for notice in decision.messages:
            agent.add_messages(self._notice(agent, notice["content"], decision.action))
        if decision.action == "rollback":
            self._rollback(agent)
        if self.settings.calibrate:
            self._sent_raw = self.budget.raw_count(agent.messages)
        return "stop" if decision.action == "stop" else "continue"

    def after_call(self, prompt_tokens: Any) -> None:
        self.budget.calibrate(prompt_tokens, self._sent_raw)

    @staticmethod
    def _notice(agent, content: str, kind: str) -> dict:
        kind = "nudge" if kind == "continue" else kind
        return agent.model.format_message(role="user", content=content, extra={"clm": kind})

    def _rollback(self, agent) -> None:
        evt_before = agent._evt_snapshot(agent.messages) if agent._evt_dir else None
        messages = list(agent.messages)
        dropped, after = self.budget.rollback_to_margin(messages, protect=self.protect)
        self._note_rollback(agent, messages, dropped, after)
        agent.messages = messages
        self.budget_log.append({"step": agent.n_calls, "rollback_dropped": len(dropped),
                                "tokens_after": after})
        if evt_before is not None:
            agent._evt_record_compression(
                "clm_rollback", evt_before, primitive=PRIMITIVE,
                budget=self.settings.budget_tokens, target_tokens=None,
                retry=self.budget.n_retry_on_limit, dropped_turns=len(dropped),
            )

    def _note_rollback(self, agent, messages: list[dict], dropped: list[dict], after: int) -> None:
        """Record the rollback in a ledger pinned just after the protected prefix.

        A rollback also erases the model's memory of what it just tried, so without a
        durable trace it re-issues the same command, blows the budget again and
        livelocks. The ledger survives every rollback and every context edit, and names
        the commands whose output caused the overflow."""
        for msg in dropped:
            for action in (msg.get("extra") or {}).get("actions") or []:
                cmd = " ".join(str(action.get("command", "")).split())[:70]
                if cmd and cmd not in self._rolled_back_cmds:
                    self._rolled_back_cmds.append(cmd)
        del self._rolled_back_cmds[:-5]
        content = self.budget.rollback_message(len(dropped), after, self._rolled_back_cmds)
        if self._ledger_index is None:
            self._ledger_index = self.protect
            messages.insert(self.protect, self._notice(agent, content, "rollback_ledger"))
            self.protect += 1
            self.budget.protect_prefix = self.protect
        else:
            # A new dict: the old one is also the record in the agent's complete history.
            messages[self._ledger_index] = {**messages[self._ledger_index], "content": content}

    # ── around the action ────────────────────────────────────────────────────
    def before_actions(self, agent, message: dict) -> None:
        """Write the mirror: the editable history WITHOUT the turn being executed."""
        history = list(agent.messages)
        if history and history[-1] is message:
            history.pop()
        rendered = render_editable(history, protect=self.protect)
        write_mirror(agent.env, CTX_FILE, rendered)
        self._pending = (history, rendered)

    def after_actions(self, agent, message: dict, outputs: list[dict],
                      observations: list[dict]) -> list[dict]:
        """Read the mirror back, apply an edit, and append the edit note and the
        context readout to the observation."""
        if self._pending is None:
            return observations
        history, rendered = self._pending
        self._pending = None
        commands = [str(a.get("command", "")) for a in (message.get("extra") or {}).get("actions") or []]
        command = "\n".join(commands)
        touched = "LIVE_CTX_MAIN" in command or CTX_DIR in command
        returncode = outputs[-1].get("returncode", 0) if outputs else 0
        read_back = read_mirror(agent.env, CTX_FILE)
        before = self.budget.raw_count(history)
        note = ""
        if read_back is not None and read_back.strip() != rendered.strip():
            note = self._apply_edit(agent, message, history, rendered, read_back, before, returncode)
        elif touched:
            self.events.append({"step": agent.n_calls, "outcome": "no_change",
                                "tokens_before": before, "tokens_after": before,
                                "returncode": returncode})
            if returncode != 0:
                note = (
                    f"\n[LIVE_CTX_MAIN.txt: NO change — your command exited "
                    f"{returncode} (see error above), so nothing was compacted "
                    f"(still ~{before} tokens).]"
                )
            else:
                note = (
                    f"\n[LIVE_CTX_MAIN.txt: NO change — your edit matched nothing, so "
                    f"context is still ~{before} tokens. Match text you have already "
                    f"seen, or target the real turn headers, which look like "
                    f"`[[CTX_TURN 12 role=assistant]]` (turn index first, then role).]"
                )
        if observations and isinstance(observations[-1].get("content"), str):
            observation = observations[-1]
            content = observation["content"]
            readout = ""
            if self.budget.enabled:
                shown = agent.messages          # the edited history + the turn being executed
                content = self.budget.cap_newest_output(shown, content)
                tokens_now = self.budget.count(shown + [{"role": "user", "content": content}])
                over = ("" if tokens_now <= self.budget.strict_target
                        else f" — OVER; compact {CTX_FILE} now")
                readout = f"\n[context: ~{tokens_now}/{self.budget.strict_target} tokens{over}]"
            observation["content"] = content + readout + note
        return observations

    def _apply_edit(self, agent, message: dict, history: list[dict], rendered: str,
                    read_back: str, before: int, returncode: Any) -> str:
        prefix = history[:self.protect]
        limit = self.budget.strict_target
        candidate = parse_back(read_back, prefix)
        after = self.budget.raw_count(candidate)
        # Both sides round-tripped through render/parse, so one ruler measures the edit.
        baseline = self.budget.raw_count(parse_back(rendered, prefix))
        record = {"step": agent.n_calls, "tokens_before": baseline, "tokens_after": after,
                  "returncode": returncode}
        grew = after > baseline
        allow = self.settings.allow_edit_growth
        if grew and not (allow and limit and after <= limit):
            self.n_edits_rejected += 1
            self.events.append({**record, "outcome": "rejected"})
            rule = f"An edit must FIT the {limit}-token limit" if allow and limit else _SHRINK_RULE
            return (
                f"\n[LIVE_CTX_MAIN.txt: edit REJECTED — it GREW context "
                f"~{baseline}->{after} tokens, so it was NOT applied (still ~{before}). "
                f"{rule}: you likely duplicated/appended "
                f"content — replace stale text with a SHORTER summary instead.]"
            )

        for msg in candidate[self.protect:]:
            msg["extra"] = {"origin": "clm_edit"}
        evt_before = agent._evt_snapshot(agent.messages) if agent._evt_dir else None
        agent.messages = candidate + [message]
        editable = max(baseline - self.budget.raw_count(prefix), 1)
        real = abs(baseline - after) >= max(TRIVIAL_EDIT_TOKENS, int(TRIVIAL_EDIT_FRACTION * editable))
        self.n_edits += 1
        self.n_edits_real += int(real)
        self.n_edits_grew += int(grew)
        self.tokens_saved += baseline - after
        self.budget.note_compaction()
        self.events.append({**record, "outcome": "applied", "grew": grew, "real": real,
                            "turns_before": len(history) - self.protect,
                            "turns_after": len(candidate) - self.protect})
        if evt_before is not None:
            agent._evt_record_compression(
                "clm_edit", evt_before, primitive=PRIMITIVE,
                budget=self.settings.budget_tokens, target_tokens=None,
                window_tokens_before=baseline, window_tokens_after=after,
                grew=grew, real=real,
            )
        if grew:
            return (
                f"\n[LIVE_CTX_MAIN.txt: edit applied but it GREW context "
                f"~{baseline}->{after} tokens (it fits, so it was kept). If you "
                f"meant to condense, you likely duplicated content instead of "
                f"replacing it.]"
            )
        if limit and after > limit:
            return (
                f"\n[LIVE_CTX_MAIN.txt: edit applied — context ~{before}->{after} "
                f"tokens, but STILL OVER the ~{limit}-token limit. Compact more "
                f"NOW (delete stale turns/outputs) or you'll get one final turn "
                f"and the session ends.]"
            )
        return (
            f"\n[LIVE_CTX_MAIN.txt: edit applied — context ~{before}->{after} "
            f"tokens, {len(candidate)} turns]"
        )

    # ── token log ────────────────────────────────────────────────────────────
    def token_log(self) -> dict[str, Any]:
        return {
            "clm_config": {**asdict(self.settings), "limit_tokens": self.budget.strict_target,
                           "mirror": CTX_FILE},
            "clm_events": self.events,
            "clm_edits": self.n_edits,
            "clm_edits_real": self.n_edits_real,
            "clm_edits_grew": self.n_edits_grew,
            "clm_edits_rejected": self.n_edits_rejected,
            "clm_net_tokens_saved": self.tokens_saved,
            "clm_nudges": self.budget.n_nudges,
            "clm_rollbacks": self.budget.n_retry_on_limit,
            "clm_turns_rolled_back": self.budget.n_turns_rolled_back,
            "clm_budget_finalized": self.budget.finalized,
            "clm_tok_ratio": round(self.budget.tok_ratio, 4),
            "clm_budget_log": self.budget_log,
        }
