"""Jev-backed per-message relevance judge for ``online_claude_select``
(``MSWEA_SELECT_BACKEND=jev``; added 2026-11-17).

The default selector backend hands the COMPLETE history to one generative model
call (DeepSeek / Nemotron / Claude through ``claude_extract.py``) and parses its
keep/drop directives. This backend asks TypeSafe's Jev decision model
(https://docs.typesafe.ai, ``POST /v1/systemone``) ONE REQUEST PER SELECTION
whose ``state`` is the task statement, the COMPLETE history (window and kept
tail, rendered as the generative selector sees it, every message under its uid
header) and the agent's newest turn (its current activity), and whose
``questions`` are one ``noul`` per history message, keyed by uid ("the agent
still needs history message m00042 to finish the task", with NEEDED_CRITERIA as
the noul's structured criteria and followed by the message's own text, its
first MSWEA_JEV_QUESTION_LINES lines); Jev reads the state
once and answers every question with a probability in [0, 1] (the request is
chunked into several, each carrying the whole state, when the questions are
many: MSWEA_JEV_SELECT_QUESTIONS). The primitive keeps the messages whose probability
clears ``MSWEA_JEV_KEEP_THRESHOLD`` and, under a cap (``MSWEA_SELECT_CAP``),
ranks them by probability and keeps the top ones that fit, so a cap never
needs a re-query. Jev returns typed values only, never text, so the context
is rebuilt from the original messages exactly as under the default backend.
Whole messages by default; with ``MSWEA_JEV_SELECT_LINES`` (added 2026-11-18)
a kept observation above that many tokens is judged line by line too and kept
as line ranges (see below), and the per-output pre-extraction
``MSWEA_OUTPUT_EXTRACT_ABOVE`` (``MSWEA_OUTPUT_EXTRACT_BACKEND=jev``) trims a
new output once, as it enters the history.

The state carries the complete history, so Jev can tell that a message is
superseded by a later one or repeats an earlier one (the judgement is not
local), and the state exceeds TypeSafe's long-context size as soon as the
history does; a selection costs one state (plus one per extra chunk), so its
input grows linearly with the history. Until 2026-11-18 the default was the
LOCAL form (one request per message, the candidate alone;
``MSWEA_JEV_HISTORY=none``; cells ojs / ojst / ...), removed when the
sympy-14531 probes showed its agreement with the generative selector at AUC
0.62 against 0.76-0.85 with the history shown (the probes' ``full`` form put
the complete history into every per-message request: the same information at
N times the cost, growing with the square of the history); the cells were
renamed ojfs / ojfst / ... (``online-jev-full-select...``) and the same day
the full form became this one-request form.

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
  MSWEA_JEV_QUESTION              needed (default) | budget: the wording of the noul
                                  question. ``needed``: "the agent still needs the
                                  message to finish the task from here" (NEEDED_*): the
                                  better ranking (AUC 0.72-0.90 against the generative
                                  selector on 12 firings, 2026-11-18) but its level falls
                                  with task progress (median p 0.1-0.2, almost nothing
                                  above 0.5), so it needs a cap or a relative rule.
                                  ``budget``: "on the kept side of a budget trim, relative
                                  to the rest of the history, whatever the task's progress"
                                  (BUDGET_*; retired 2026-11-18 morning with the local
                                  form, revived the same evening): a slightly weaker
                                  ranking (AUC 0.62-0.84) whose level is usable: the
                                  share of tokens with p >= 0.5 tracked the generative
                                  selector's kept share across those 12 firings
                                  (correlation 0.81; 19-65% vs 12-66%), i.e. the AMOUNT
                                  comes from Jev. score / aligned (2026-11-17) stay in
                                  comments in this module. The record carries ``question``.
  MSWEA_JEV_UNIT                  message (default) | turn: with turn, each assistant
                                  message and the observations that follow it are judged
                                  as ONE unit (rendered together) and kept or dropped
                                  together; the cap ranks units by their total tokens and
                                  the anchor bonus applies when any member was in the
                                  previous context (added 2026-11-17: judged alone, a
                                  bare command gets the same probability whether the
                                  generative selector kept or dropped it). The question
                                  names the turn's members; the selection record expands
                                  the unit's p to every member uid.
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
  MSWEA_JEV_QUESTION_CRITERIA     1 (default): every noul carries NEEDED_CRITERIA as its
                                  structured ``criteria`` (true / false definitions), as the
                                  per-message form did, besides the prose in the preamble;
                                  0 = instructions only. Added 2026-11-18 when the first
                                  one-request probes (criteria in the preamble only) fell to
                                  AUC 0.75 / 0.63 against the generative selector
                                  (sympy-14531, steps 68 / 93) from the per-message form's
                                  0.83 / 0.76; with the criteria on every question they
                                  came back to 0.79 / 0.73-0.75 (one question per request:
                                  0.81). The record carries ``question_criteria``.
  MSWEA_JEV_ANCHOR_TAGS           1: when MSWEA_SELECT_ANCHOR is on, the previous selection is
                                  passed to Jev as ocsa passes it to the generative selector:
                                  every header in the state says whether the message was in
                                  the agent's context at the previous step (the newest turn:
                                  "new this step"), the preamble gets ANCHOR_PREAMBLE_NOTE
                                  (continuity has value; the record of a recent action stays
                                  even when it repeats an earlier one) and the question is
                                  asymmetric: a message in the context is asked whether it
                                  STAYS, one outside whether it RETURNS, each with its own
                                  criteria (ANCHOR_STAY_* / ANCHOR_RETURN_*; the variant's
                                  templates and criteria are not used, its preamble is).
                                  Default 0 (the previous selection acts only through the
                                  +0.15 bonus, which still applies with 1). Added 2026-11-18
                                  after the ojfsbl pilot, where sympy-14531's context froze
                                  at 21 early messages and the agent repeated test / pip
                                  install 250 times (see ANCHOR_PREAMBLE_NOTE's comment). The
                                  record carries ``anchor_tags``.
  MSWEA_JEV_STUCK_GATE            k > 0: one extra noul per selection, about the agent ("the
                                  agent is stuck: its most recent steps repeat steps it has
                                  already taken", STUCK_*), in the same request as the
                                  per-message questions; when its p clears
                                  MSWEA_JEV_STUCK_THRESHOLD (0.5) the newest k turns of the
                                  window are kept whole whatever their own p, ranked first
                                  under the cap and never line-trimmed (the agent's record
                                  of what it has just tried, on top of the verbatim kept
                                  tail). Default 0 (off). Added 2026-11-18 after the ojfsbl
                                  sympy-14531 collapse (see STUCK_INSTRUCTIONS' comment):
                                  the question read 0.94-0.96 in the loop and 0.18-0.38 on
                                  a healthy history of the same task. The record carries
                                  ``stuck``, ``stuck_gate``, ``stuck_threshold`` and
                                  ``stuck_forced`` (uids kept by the gate).
  MSWEA_JEV_ACTIVITY_QUESTION     1: a second noul per unit ("<uid>#next": the agent's next step
                                  is likely to need it, NEXT_*) rides in the same request, and
                                  the unit's p is the larger of the value and activity answers,
                                  so a message is kept when either clears the threshold (the
                                  record carries ``probs_value`` / ``probs_activity`` beside
                                  ``probs``; the judgement log has both keys). Default 0. Added
                                  2026-11-19 so the per-step form follows the agent's current
                                  work (the `budget` wording is stage-independent by design and
                                  never moved; on a hand-labelled step this question read AUC
                                  0.96, 0 false positives at 0.5). Costs the second question's
                                  bytes.
  MSWEA_JEV_QUESTION_LINES        each question quotes the message it asks about (the unit's
                                  members rendered as in the state, every one cut to its
                                  first N lines with a note of the total; default 12;
                                  0 = the question names the uid only). Added 2026-11-18 on
                                  the guess that Jev had to find the message in a 100+ KB
                                  state; the probes above moved by 0.00 / +0.02 with it
                                  (the whole text, or none, no better), so it is kept as a
                                  cheap option. The quoted text is charged as question
                                  input on top of the state; the record carries
                                  ``question_lines`` and ``question_bytes``.
  MSWEA_JEV_SELECT_QUESTIONS      questions per selection request (default 0 = by size:
                                  while the state alone is under the long-context size a
                                  request stays under it; once it is not, which the
                                  complete history makes the rule, every request carries
                                  the header and takes up to 64 questions or ~30 KB of
                                  question text, each request re-sending the whole state)
  MSWEA_JEV_WORKERS               parallel requests (selection chunks, line requests;
                                  default 8)
  MSWEA_JEV_TIMEOUT_S             per-request timeout (default 60)
  MSWEA_JEV_MAX_RETRIES           retries per request on 408/429/5xx and transport
                                  errors, exponential backoff (default 3)
  (long context)                  a request above ~30000 bytes of text is sent with
                                  TypeSafe-Danger-Zone-Long-Context: true (TypeSafe's
                                  long-context mode: slower, less accurate; recorded as
                                  ``long_context`` on the judgement). With the complete
                                  history in every request this is every selection
                                  request; the former MSWEA_JEV_LONG_CONTEXT=truncate
                                  (cut the candidate to fit) was removed with the local
                                  form on 2026-11-18.
  MSWEA_JEV_JUDGEMENT_LOG         where every request is appended as one JSON line
                                  (``kind: select`` with its uids and probs, ``select_lines``
                                  / ``lines`` for the line judges; default
                                  MSWEA_EVENT_LOG_DIR/jev_judgements.jsonl, the sibling of
                                  summary_attempts.jsonl; 0 disables)

A request that still fails after the retries KEEPS every message it carried
(conservative) and is recorded with ``error`` (so is a message whose answer is
missing from a reply); an authentication failure (401 / 403) or a selection in
which every request failed raises, so the agent's consecutive-
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
_RETRY_STATUSES = (408, 429, 500, 502, 503, 504, 529)
_AUTH_STATUSES = (401, 403)

# Until 2026-11-18 the state held ONE candidate (alone, or repeated after the complete
# history) and the request one ``needed`` noul with NEEDED_CRITERIA as its criteria; since
# 2026-11-18 (the "batched" form) the state holds the complete history once and the request
# one noul PER MESSAGE, named by uid, so the criteria moved into the preamble.
JUDGE_PREAMBLE_HEAD = (
    "An autonomous software-engineering agent fixes a bug in a repository by running one "
    "shell command per step. Its context window is being curated: before the next step, "
    "the messages of its history are judged, IN VIEW OF THE COMPLETE HISTORY, for whether "
    "the agent still needs each of them. The agent will see the kept messages unchanged, in "
    "the original order, together with the task statement and its newest turn; the dropped "
    "ones are hidden from it for this step. The complete history is shown once, every "
    "message under a header with its uid (for example [m00042 user, 12 lines]); each question "
    "names one message by that uid and quotes it (its first lines when it is long), so that "
    "you can tell whether a later message supersedes or repeats it."
)
NEEDED_INSTRUCTIONS = (   # the proposition of every per-message noul; {uid} names the message
    "The agent still needs history message {uid} in its context window to finish the task "
    "from here."
)
TURN_INSTRUCTIONS = (     # MSWEA_JEV_UNIT=turn: one noul per assistant message and its observations
    "The agent still needs turn {uid} of its history (assistant message {uid} together with "
    "the observations that follow it: {members}) in its context window to finish the task "
    "from here."
)
QUESTION_EXCERPT_FMT = (   # appended to the question when MSWEA_JEV_QUESTION_LINES > 0 (added 2026-11-18):
    # the unit's own text, so Jev need not find the uid in the state. On the sympy-14531 probes
    # it changed the agreement with the generative selector by 0.00 (step 68) / +0.02 (step 93);
    # the structured ``criteria`` on every question (MSWEA_JEV_QUESTION_CRITERIA) was what the
    # one-request form had lost against the per-message form (+0.04 / +0.10).
    "\n\nThe message as it stands in the history{cut}:\n{excerpt}"
)
QUESTION_EXCERPT_CUT_FMT = " (its first {shown} of {total} lines; the rest is in the history)"
DEFAULT_QUESTION_LINES = 12
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
JUDGE_PREAMBLE = (
    JUDGE_PREAMBLE_HEAD
    + " A message the agent still needs: " + NEEDED_CRITERIA["true"]
    + " A message it no longer needs: " + NEEDED_CRITERIA["false"]
)
# ── 2026-11-18: the three probe wordings below (budget / score / aligned, 2026-11-17) are
# COMMENTED OUT, not deleted: the full-history ``needed`` form (MSWEA_JEV_HISTORY=full) is the
# one pursued for now. Their dispatch branches in needed_question / _preamble /
# answer_probability are commented out with them; MSWEA_JEV_QUESTION accepts ``needed`` only.
# MSWEA_JEV_QUESTION=budget (added 2026-11-17): the same noul question put as a RELATIVE,
# stage-independent judgement. Under the default wording ("needed to finish the task from
# here") every probability fell by ~0.1 as soon as the agent's newest turn was a passing
# verification, whatever the message (sympy-14531 probe: 93/98 uids lower from step 68 to
# 93), so a fixed threshold measured task progress as much as message value.
# 2026-11-18 (evening): ``budget`` REVIVED in the one-request form (per-uid questions, the
# criteria as the noul's structured field) to see whether the fraction of messages above 0.5
# tracks the generative selector's kept fraction across firings, which ``needed`` cannot (its
# level falls with task progress). The ``{uid}`` templates replace the "candidate" wording.
BUDGET_PREAMBLE_NOTE = (
    " The history is trimmed to a fixed token budget, so the question about each message is "
    "whether it belongs on the KEPT side or the DROPPED side of that trim, relative to the "
    "rest of a typical debugging history. How far along the task is must not change the "
    "judgement: a nearly finished task keeps the same share of its history as one that has "
    "just started."
)
BUDGET_INSTRUCTIONS = (
    "When the agent's history is trimmed to a fixed token budget, history message {uid} "
    "belongs on the kept side rather than the dropped side, judged by its value relative to "
    "the rest of the history and not by how far along the task is."
)
BUDGET_TURN_INSTRUCTIONS = (
    "When the agent's history is trimmed to a fixed token budget, turn {uid} of its history "
    "(assistant message {uid} together with the observations that follow it: {members}) "
    "belongs on the kept side rather than the dropped side, judged by its value relative to "
    "the rest of the history and not by how far along the task is."
)
BUDGET_CRITERIA = {
    "true": (
        "Among the more valuable messages of the history: it locates the code to change, "
        "shows code the agent edits or depends on, records an edit the agent made, or holds "
        "an error message or test result whose content later work builds on."
    ),
    "false": (
        "Among the more dispensable messages of the history: routine navigation, bulk output "
        "(installation logs, file listings, repeated reads) whose useful part has been acted "
        "on, exploration that led nowhere, a result that a later message repeats, or "
        "something unrelated to the task."
    ),
}
BUDGET_PREAMBLE = (
    JUDGE_PREAMBLE_HEAD + BUDGET_PREAMBLE_NOTE
    + " A message on the kept side: " + BUDGET_CRITERIA["true"]
    + " A message on the dropped side: " + BUDGET_CRITERIA["false"]
)
# MSWEA_JEV_ANCHOR_TAGS=1 (added 2026-11-18 evening, after the ojfsbl pilot): the previous
# selection is PASSED TO JEV, as ocsa passes it to the generative selector, instead of acting
# only as the +0.15 hysteresis of decide(). Every header in the state says whether the
# message was in the agent's context at the previous step (ANCHOR_TAG_IN / _OUT; the newest
# turn: _NEW), the preamble gets ANCHOR_PREAMBLE_NOTE, and the question is asymmetric: a
# message in the context is asked whether it STAYS (ANCHOR_STAY_*), one outside whether it
# RETURNS (ANCHOR_RETURN_*), each with its own criteria; the variant's own templates and
# criteria are not used then (its preamble is). Why: in the ojfsbl pilot (per-step firing,
# budget wording, +0.15 only) sympy-14531 collapsed: from step ~45 no new message scored
# 0.5, the context froze at 21 early messages, and the agent repeated test / pip install
# 250 times because it never saw that it had already done so; Jev, seeing only the history,
# rated every repeated message as dispensable (p 0.06-0.14), which is correct as information
# but wrong as the agent's record of its own actions. The +0.15 bonus still applies
# (MSWEA_JEV_ANCHOR_BONUS; set 0 to rely on the wording alone).
ANCHOR_TAG_IN = "in the agent's context at the previous step"
ANCHOR_TAG_OUT = "not in the agent's context at the previous step"
ANCHOR_TAG_NEW = "new this step; kept regardless"
ANCHOR_PREAMBLE_NOTE = (
    " Every header also says whether the message was in the agent's context at the previous "
    "step. Continuity has value: the context should change only as much as the agent's "
    "progress requires. A message that is in the context stays unless it has been superseded "
    "or will not be needed again; a message outside it returns only when the agent's current "
    "activity calls for it. The record of what the agent did most recently, and of what came "
    "of it, stays even when it repeats an earlier attempt: the agent must be able to see what "
    "it has already tried."
)
ANCHOR_STAY_INSTRUCTIONS = (
    "History message {uid}, which is in the agent's context now, stays in it for the next step "
    "rather than being dropped."
)
ANCHOR_STAY_TURN_INSTRUCTIONS = (
    "Turn {uid} of the history (assistant message {uid} together with the observations that "
    "follow it: {members}), which is in the agent's context now, stays in it for the next step "
    "rather than being dropped."
)
ANCHOR_RETURN_INSTRUCTIONS = (
    "History message {uid}, which is not in the agent's context now, is brought back into it "
    "for the next step."
)
ANCHOR_RETURN_TURN_INSTRUCTIONS = (
    "Turn {uid} of the history (assistant message {uid} together with the observations that "
    "follow it: {members}), which is not in the agent's context now, is brought back into it "
    "for the next step."
)
ANCHOR_STAY_CRITERIA = {
    "true": (
        "It still earns its place: it locates or shows code the agent works on, records an "
        "edit the agent made, holds an error message or test result its next step builds on, "
        "or is the record of a recent command and its outcome that the agent must remember "
        "having run, even when it repeats an earlier attempt."
    ),
    "false": (
        "It has been superseded by a later message, its useful content has been acted on and "
        "will not be consulted again, or it is bulk output whose relevant part the context "
        "holds elsewhere."
    ),
}
ANCHOR_RETURN_CRITERIA = {
    "true": (
        "The agent's current activity has turned back to it: it holds code, a result or an "
        "error message the agent needs now and that nothing in the context provides."
    ),
    "false": (
        "Nothing in the agent's newest turn calls for it; the context already holds what it "
        "would add; or it remains superseded, exploration that led nowhere, or bulk output."
    ),
}
# MSWEA_JEV_STUCK_GATE=<k turns> (added 2026-11-18 evening): ONE extra noul per selection, about
# the agent rather than a message ("the agent is stuck: its most recent steps repeat steps it
# has already taken"), in the same request as the per-message questions (the state is shared,
# so it costs one question's bytes). When its probability clears MSWEA_JEV_STUCK_THRESHOLD
# (0.5) the newest k turns of the window (assistant message + its observations, counted back
# from the kept tail) are kept WHOLE regardless of their own p, ranked first under the cap and
# exempt from line trimming. Why: in the ojfsbl sympy-14531 run every repeated test / pip
# message scored 0.06-0.14 under the value question, so the context lost the agent's record
# of its own recent attempts and the agent repeated them 250 times; probes on that history
# showed Jev cannot be talked into keeping such a message by any wording (consequence /
# record framings 0.2-0.5) but detects the situation reliably (this question: 0.94 / 0.96
# in the loop, 0.18-0.38 on a healthy history of the same task; the per-message "this is a
# repeated attempt" question: 0.8-0.99 vs 0.1-0.4), so the detection is asked of Jev and
# the keep rule is ours. k turns from the window come on top of the verbatim kept tail.
STUCK_KEY = "stuck"
STUCK_INSTRUCTIONS = (
    "The agent is stuck: its most recent steps repeat steps it has already taken, without new "
    "information."
)
STUCK_CRITERIA = {
    "true": (
        "The newest turns re-run commands, re-install packages or redo edits that earlier turns "
        "already did, with the same outcomes."
    ),
    "false": (
        "The newest turns do something the agent has not done before, or act on new information."
    ),
}
DEFAULT_STUCK_THRESHOLD = 0.5
# MSWEA_JEV_ACTIVITY_QUESTION=1 (added 2026-11-19): a SECOND noul per unit, keyed "<uid>#next",
# about the unit's relevance to the agent's CURRENT activity ("the agent's next step is likely to
# need it"), in the same request as the value question; the unit's p is the larger of the two
# (keep when either clears the threshold). Why: the per-step `budget` form froze (its wording is
# stage-independent by construction, so a message's p never moved when the agent's work turned
# to it: str.py messages 0.5-0.6 before and during the str.py edits of the ojfsblg 14531 run),
# while on a hand-labelled step (step 56 of that run, 27 messages needed for the current edit vs
# 71 not) this question separated them at AUC 0.96 with no false positive at 0.5 (12/27 vs
# 0/71; `budget` 0.83 with 14/71). The activity shown is the newest MSWEA_JEV_CONTEXT_TURNS
# turns (1 or 3 made no difference in the probe). Costs the second question's bytes only.
ACTIVITY_SUFFIX = "#next"
NEXT_INSTRUCTIONS = (
    "The agent's next step is likely to need history message {uid} in its context window."
)
NEXT_TURN_INSTRUCTIONS = (
    "The agent's next step is likely to need turn {uid} of its history (assistant message {uid} "
    "together with the observations that follow it: {members}) in its context window."
)
NEXT_CRITERIA = {
    "true": (
        "Given what the agent's newest turn is doing, it will refer back to this message next: "
        "the code it is editing, the error it is fixing, the result it is checking."
    ),
    "false": (
        "The newest turn has moved on to something this message does not bear on, or the "
        "context already holds what it would add."
    ),
}
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
QUESTION_VARIANTS = ("needed", "budget")   # 2026-11-18: score / aligned are commented out above
                                           # (and in _preamble / answer_probability); budget was
                                           # revived the same evening (see above)
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
        "question":       question,
        "unit":           unit,
        "select_lines":   _env_int("MSWEA_JEV_SELECT_LINES", 0, 0),
        "select_questions": _env_int("MSWEA_JEV_SELECT_QUESTIONS", 0, 0),
        "question_lines": _env_int("MSWEA_JEV_QUESTION_LINES", DEFAULT_QUESTION_LINES, 0),
        "question_criteria": _env_int("MSWEA_JEV_QUESTION_CRITERIA", 1, 0) > 0,
        "anchor_tags":    _env_int("MSWEA_JEV_ANCHOR_TAGS", 0, 0) > 0,
        "stuck_gate":     _env_int("MSWEA_JEV_STUCK_GATE", 0, 0),
        "stuck_threshold": _env_float("MSWEA_JEV_STUCK_THRESHOLD", DEFAULT_STUCK_THRESHOLD, 0.0, 1.0),
        "activity_question": _env_int("MSWEA_JEV_ACTIVITY_QUESTION", 0, 0) > 0,
        "workers":        _env_int("MSWEA_JEV_WORKERS", DEFAULT_WORKERS, 1),
        "timeout_s":      _env_float("MSWEA_JEV_TIMEOUT_S", DEFAULT_TIMEOUT_S, 1.0),
        "max_retries":    _env_int("MSWEA_JEV_MAX_RETRIES", DEFAULT_MAX_RETRIES),
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


def message_excerpt(members: list[dict], render, lines: int) -> str:
    """The text quoted in a unit's question: every member rendered as in the
    state (uid header, numbered lines), each cut to its first ``lines`` body
    lines with a note of how many it has (``QUESTION_EXCERPT_CUT_FMT``)."""
    parts = []
    for m in members:
        head, _, body = render(m).partition("\n")
        body_lines = body.split("\n") if body else []
        if len(body_lines) > lines:
            cut = QUESTION_EXCERPT_CUT_FMT.format(shown=lines, total=len(body_lines))
            body_lines = body_lines[:lines]
        else:
            cut = ""
        parts.append(QUESTION_EXCERPT_FMT.format(cut=cut, excerpt="\n".join([head] + body_lines)))
    return "".join(parts)


def message_questions(units: list[dict], variant: str | None = None, render=None,
                      lines: int | None = None, criteria: bool | None = None,
                      prev_uids: set | None = None, anchor_tags: bool = False,
                      activity: bool = False) -> dict:
    """One noul question per unit, keyed by the unit's uid (the question key IS
    the uid): ``NEEDED_INSTRUCTIONS`` for a message, ``TURN_INSTRUCTIONS`` for
    a turn group (``members``), followed, when ``render`` is given and ``lines``
    (default ``MSWEA_JEV_QUESTION_LINES``) is > 0, by the unit's own text cut
    to that many lines per member (``message_excerpt``), so the question carries
    what it asks about. ``variant`` defaults to ``MSWEA_JEV_QUESTION``.
    With ``anchor_tags`` (MSWEA_JEV_ANCHOR_TAGS) the question is asymmetric: a
    unit with a member in ``prev_uids`` (the agent's context at the previous
    step) gets the STAY question and criteria, any other the RETURN ones
    (``ANCHOR_*``), whatever the variant."""
    from agentctx.compression.primitives import _msg_uid   # local: primitives imports this module lazily
    variant = variant or question_variant()
    if lines is None:
        lines = _env_int("MSWEA_JEV_QUESTION_LINES", DEFAULT_QUESTION_LINES, 0)
    if criteria is None:
        criteria = _env_int("MSWEA_JEV_QUESTION_CRITERIA", 1, 0) > 0
    prev_uids = prev_uids or set()
    qs: dict = {}
    for u in units:
        uid = _msg_uid(u) or "?"
        members = u["members"] if u.get("members") else [u]
        member_list = ", ".join(_msg_uid(m) or "?" for m in members)
        if anchor_tags:
            in_context = any((_msg_uid(m) or "?") in prev_uids for m in members)
            if u.get("members"):
                template = ANCHOR_STAY_TURN_INSTRUCTIONS if in_context else ANCHOR_RETURN_TURN_INSTRUCTIONS
            else:
                template = ANCHOR_STAY_INSTRUCTIONS if in_context else ANCHOR_RETURN_INSTRUCTIONS
            crit = ANCHOR_STAY_CRITERIA if in_context else ANCHOR_RETURN_CRITERIA
        elif u.get("members"):
            template = BUDGET_TURN_INSTRUCTIONS if variant == "budget" else TURN_INSTRUCTIONS
            crit = BUDGET_CRITERIA if variant == "budget" else NEEDED_CRITERIA
        else:
            template = BUDGET_INSTRUCTIONS if variant == "budget" else NEEDED_INSTRUCTIONS
            crit = BUDGET_CRITERIA if variant == "budget" else NEEDED_CRITERIA
        text = template.format(uid=uid, members=member_list)
        if render is not None and lines > 0:
            text += message_excerpt(members, render, lines)
        qs[uid] = {"type": "noul", "instructions": text}
        if criteria:   # MSWEA_JEV_QUESTION_CRITERIA (default on): the structured criteria on every noul
            qs[uid]["criteria"] = dict(crit)
        if activity:   # MSWEA_JEV_ACTIVITY_QUESTION: the second question, relevance to the current activity
            tmpl = NEXT_TURN_INSTRUCTIONS if u.get("members") else NEXT_INSTRUCTIONS
            atext = tmpl.format(uid=uid, members=member_list)
            if render is not None and lines > 0:
                atext += message_excerpt(members, render, lines)
            qs[uid + ACTIVITY_SUFFIX] = {"type": "noul", "instructions": atext}
            if criteria:
                qs[uid + ACTIVITY_SUFFIX]["criteria"] = dict(NEXT_CRITERIA)
    return qs


def _preamble(variant: str, anchor_tags: bool = False) -> str:
    # 2026-11-18: score / aligned disabled (constants commented out above)
    # if variant == "aligned":
    #     return ALIGNED_PREAMBLE_FULL
    # if variant == "score":
    #     return JUDGE_PREAMBLE + SCORE_PREAMBLE_NOTE
    base = BUDGET_PREAMBLE if variant == "budget" else JUDGE_PREAMBLE
    return base + ANCHOR_PREAMBLE_NOTE if anchor_tags else base


def answer_probability(answer: dict, variant: str, key: str = "?") -> tuple[float, dict]:
    """A message's p from Jev's answer to its question: the noul value (or,
    for the retired ``score`` wording, the probability-weighted level divided
    by the top level number). Returns (p, extras); raises JevAPIError when the
    answer lacks the value."""
    # 2026-11-18: the ``score`` wording is disabled (SCORE_LEVELS commented out above)
    # if variant == "score":
    #     s = answer.get("score")
    #     if not isinstance(s, (int, float)):
    #         raise JevAPIError(f"no score answer for {key!r} in {str(answer)[:200]}")
    #     top = len(SCORE_LEVELS) - 1
    #     return min(1.0, max(0.0, float(s) / top)), {
    #         "score": float(s), "level_probs": answer.get("probabilities"), "confidence": answer.get("confidence")}
    p = answer.get("noul")
    if not isinstance(p, (int, float)):
        raise JevAPIError(f"no noul answer for {key!r} in {str(answer)[:200]}")
    return float(p), {}


def judge_state(task_text: str, activity_text: str, history_text: str, variant: str | None = None,
                anchor_tags: bool = False) -> str:
    """The ``state`` of a selection request: preamble, task statement, the
    complete history (``history_text``: window and kept tail, rendered as the
    generative selector sees it, every message under its uid header) and the
    agent's newest turn (when any). The same state serves every question of the
    selection; nothing is repeated. ``variant`` defaults to ``MSWEA_JEV_QUESTION``;
    ``anchor_tags`` appends ``ANCHOR_PREAMBLE_NOTE`` (the headers of
    ``history_text`` then carry the previous-context tags)."""
    variant = variant or question_variant()
    parts = [_preamble(variant, anchor_tags), f"Task statement:\n{task_text}",
             "Complete history of the agent so far (every message, in order, each under its "
             f"uid header; the newest turn is kept regardless):\n{history_text}"]
    if activity_text:
        parts.append(f"The agent's newest turn (its current activity; kept regardless, not a "
                     f"message to judge):\n{activity_text}")
    return "\n\n".join(parts)


# ── requests: one state, many noul questions, chunked ───────────────────────
def _chunk_questions(keys: list[str], q_bytes: dict[str, int], state_bytes: int, per_request: int) -> list[list[str]]:
    """Split the question keys into requests. ``per_request`` > 0 caps the
    questions per request; 0 = by size: while the state alone is under the
    long-context size, a request stays under it (so a short history avoids the
    header); once the state alone exceeds it (every selection request does,
    with the complete history), every request carries the header and takes up
    to 64 questions or LONG_CONTEXT_BYTES of question text, whichever first
    (the quoted excerpts make the questions large)."""
    if not keys:
        return []
    if per_request:
        return [keys[i:i + per_request] for i in range(0, len(keys), per_request)]
    room = LONG_CONTEXT_BYTES - state_bytes
    chunks: list[list[str]] = []
    cur: list[str] = []
    used = 0
    for k in keys:
        if cur and room > 0 and used + q_bytes[k] > room:
            chunks.append(cur); cur, used = [], 0
        cur.append(k); used += q_bytes[k]
        if room <= 0 and (len(cur) >= 64 or used >= LONG_CONTEXT_BYTES):
            chunks.append(cur); cur, used = [], 0
    if cur:
        chunks.append(cur)
    return chunks


def _ask(client: JevClient, state: str, questions: dict, chunks: list[list[str]], workers: int,
         progress: dict | None = None, variant: str = "needed") -> tuple[dict, list[dict]]:
    """Send the chunks in parallel (each carries the whole ``state``) and
    collect one p per question key (None when its request failed or its
    answer lacked the value). Returns (results {key: p | None}, requests):
    one record per request with ``keys``, ``questions``, ``long_context``,
    usage, ``attempts``, ``latency_s``, ``model``, ``request_id``, ``error``
    (``status``, ``fatal`` on 401 / 403) and ``answer_errors`` (keys whose
    answer was missing or malformed). ``progress`` (optional) is updated under
    a lock as requests complete (``attempts``, ``prompt_tokens``,
    ``completion_tokens``, ``response_ids``) so an exception that ends the
    selection leaves the usage of the completed requests salvageable."""
    state_bytes = len(state.encode("utf-8"))
    q_bytes = {k: len(json.dumps(v).encode("utf-8")) + len(k) + 8 for k, v in questions.items()}
    lock = threading.Lock()
    results: dict[str, float | None] = {}
    reqs: list[dict] = []

    def one(chunk: list[str]) -> dict:
        qs = {k: questions[k] for k in chunk}
        long_context = state_bytes + sum(q_bytes[k] for k in chunk) > LONG_CONTEXT_BYTES
        rec = {"keys": list(chunk), "questions": len(chunk), "question_bytes": sum(q_bytes[k] for k in chunk),
               "long_context": long_context, "input_tokens": 0,
               "output_tokens": 0, "latency_s": 0.0, "attempts": 0, "model": None, "request_id": None,
               "error": None, "answer_errors": []}
        t0 = time.time()
        try:
            reply = client.system_one(state, qs, long_context=long_context)
            answers = reply["answers"] or {}
            got: dict[str, float | None] = {}
            for k in chunk:
                try:
                    got[k] = answer_probability(answers.get(k) or {}, variant, k)[0]
                except JevAPIError:
                    got[k] = None
                    rec["answer_errors"].append(k)
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
        except Exception as exc:   # noqa: BLE001 - recorded per request
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

    if chunks:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(chunks)))) as pool:
            list(pool.map(one, chunks))
    return results, reqs


def _raise_if_failed(reqs: list[dict], what: str) -> None:
    """JevAPIError on an authentication failure in any request, or when every request failed."""
    bad = next((r for r in reqs if r.get("fatal")), None)
    if bad is not None:
        raise JevAPIError(f"TypeSafe authentication failed: {bad['error']}", status=bad.get("status"))
    if reqs and all(r["error"] for r in reqs):
        raise JevAPIError(f"every Jev {what} request failed ({len(reqs)}); first: {reqs[0]['error']}")


# ── selection ───────────────────────────────────────────────────────────────
def judge_messages(client: JevClient, task_text: str, activity_text: str, units: list[dict],
                   settings: dict, history_text: str, progress: dict | None = None, render=None,
                   prev_uids: set | None = None) -> tuple[list[dict], list[dict], str]:
    """Judge every unit of the window in ONE request (or a few, when the
    questions are chunked): the state holds the complete history once and the
    request one noul per unit, keyed by uid and quoting the unit's first
    ``question_lines`` lines when ``render`` is given (``message_questions``).

    Returns (judgements, requests, state, extras): one judgement per unit, window
    order, with uid, index, p (None when its request failed or its answer was
    missing), error (the request's error, or ``answer missing`` for a lone
    bad answer), request_id, long_context, ``members`` for a turn group; the
    request records of ``_ask``; the state sent; and extras with ``stuck`` (the
    p of the MSWEA_JEV_STUCK_GATE question, None when not asked or failed).
    The judgement log gets one ``kind: select`` record per request (uids,
    probs, usage).
    """
    from agentctx.compression.primitives import _msg_uid   # local: primitives imports this module lazily
    variant = settings.get("question", "needed")
    anchor_tags = bool(settings.get("anchor_tags")) and prev_uids is not None   # MSWEA_JEV_ANCHOR_TAGS, anchored only
    state = judge_state(task_text, activity_text, history_text, variant, anchor_tags=anchor_tags)
    questions = message_questions(units, variant, render=render, lines=settings.get("question_lines"),
                                  criteria=settings.get("question_criteria"),
                                  prev_uids=prev_uids, anchor_tags=anchor_tags,
                                  activity=bool(settings.get("activity_question")))
    if settings.get("stuck_gate"):   # MSWEA_JEV_STUCK_GATE: one question about the agent, same state
        questions[STUCK_KEY] = {"type": "noul", "instructions": STUCK_INSTRUCTIONS, "criteria": dict(STUCK_CRITERIA)}
    keys = list(questions)
    q_bytes = {k: len(json.dumps(v).encode("utf-8")) + len(k) + 8 for k, v in questions.items()}
    chunks = _chunk_questions(keys, q_bytes, len(state.encode("utf-8")), settings.get("select_questions", 0))
    results, reqs = _ask(client, state, questions, chunks, settings["workers"], progress=progress, variant=variant)
    req_of = {k: r for r in reqs for k in r["keys"]}
    judgements: list[dict] = []
    for index, u in enumerate(units):
        uid = _msg_uid(u) or "?"
        r = req_of.get(uid) or {}
        error = r.get("error")
        if error is None and uid in r.get("answer_errors", ()):
            error = f"answer missing for {uid!r}"
        rec = {"uid": uid, "index": index, "p": results.get(uid), "error": error,
               "request_id": r.get("request_id"), "long_context": bool(r.get("long_context"))}
        if settings.get("activity_question"):   # p = max(value, activity): kept when either clears the threshold
            pa = results.get(uid + ACTIVITY_SUFFIX)
            rec["p_value"], rec["p_activity"] = rec["p"], pa
            if pa is not None:
                rec["p"] = pa if rec["p"] is None else max(rec["p"], pa)
        if u.get("members"):
            rec["members"] = [_msg_uid(m) or "?" for m in u["members"]]
        judgements.append(rec)
    probs = {k: (None if results.get(k) is None else round(results[k], 4)) for k in keys}
    for r in reqs:
        _log_judgement({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": "select", "uids": r["keys"],
                        **{k: v for k, v in r.items() if k != "keys"},
                        "probs": {k: probs[k] for k in r["keys"]}, "state_bytes": len(state.encode("utf-8"))})
    extras = {"stuck": results.get(STUCK_KEY) if STUCK_KEY in questions else None}
    return judgements, reqs, state, extras


def decide(judgements: list[dict], prev_uids: set, threshold: float, anchor_bonus: float,
           budget_tokens: int | None, token_of, forced: set | None = None) -> tuple[dict, dict]:
    """Keep / drop from the judgements.

    score = p + anchor_bonus (for a message in the agent's context at the
    previous step); kept when score >= threshold. An errored judgement (p None)
    is kept. Under ``budget_tokens`` the kept messages are ranked by score
    (ties: the newer first) and taken greedily while they fit (``token_of(rec)``
    gives a message's tokens; a message that does not fit is skipped and the
    smaller ones after it are still tried). Returns ({uid: None}, extras):
    extras has scores, kept_by_threshold, capped_out (uids ranked out by the
    cap), errors. ``forced`` uids (the stuck gate's newest turns) are kept
    whatever their score and ranked first under the cap, like an errored
    judgement; their scores are recorded unchanged.
    """
    forced = forced or set()
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
        if score >= threshold or uid in forced:
            above.append(rec)
    capped_out: list[str] = []
    if budget_tokens is None:
        chosen = {rec["uid"] for rec in above}
    else:
        def rank(r):
            sc = scores[r["uid"]]
            return (-(2.0 if (sc is None or r["uid"] in forced) else sc), -r["index"])
        ranked = sorted(above, key=rank)
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
    ``window`` (one request per selection, one noul per message; chunked when
    the questions are many), decide, and return (selection {uid: None},
    record, input_tokens, output_tokens, wall latency_s, request_ids).

    ``kept`` is the tail kept verbatim (the newest turn[s]); its newest
    ``context_turns`` turns are shown to Jev as the agent's current activity.
    ``prev_uids`` are the uids in the agent's context at the previous step
    (the anchor bonus applies to them only when ``anchor``). Raises JevAPIError
    when any request hit an authentication failure or every request failed.
    """
    settings = jev_settings()
    client = client or get_jev_client()
    plain_render = render
    anchor_tags = bool(settings["anchor_tags"]) and anchor
    if anchor_tags:   # MSWEA_JEV_ANCHOR_TAGS: the previous context marked in every header
        kept_ids = {id(m) for m in kept}

        def render(m, _r=plain_render):   # noqa: E306  (shadows the parameter on purpose)
            from agentctx.compression.primitives import _msg_uid as _uid
            tag = ANCHOR_TAG_NEW if id(m) in kept_ids else (ANCHOR_TAG_IN if (_uid(m) or "?") in prev_uids else ANCHOR_TAG_OUT)
            return _r(m, tag=tag)
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
    # The state carries the complete history (window and kept tail), rendered as the
    # generative selector sees it, so the judgement is not local.
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
    else:
        units = list(window)
    members_of = {(_msg_uid(u) or "?"): (u["members"] if u.get("members") else [u]) for u in units}
    t0 = time.time()
    judgements, reqs, state, jm_extras = judge_messages(client, task_text, activity_text, units, settings,
                                                        history_text, progress=progress, render=render,
                                                        prev_uids=set(prev_uids) if anchor_tags else None)
    latency_s = time.time() - t0
    _raise_if_failed(reqs, "selection")
    # Stuck gate (MSWEA_JEV_STUCK_GATE=k): when Jev's "the agent is stuck" probability clears
    # MSWEA_JEV_STUCK_THRESHOLD, the newest k turns of the window are kept whole regardless
    # of their own p (the agent's record of what it has just tried), on top of the kept tail.
    stuck_p = jm_extras.get("stuck")
    stuck_forced_msgs: set[str] = set()
    if settings["stuck_gate"] and stuck_p is not None and stuck_p >= settings["stuck_threshold"]:
        turns_seen = 0
        for m in reversed(window):
            stuck_forced_msgs.add(_msg_uid(m) or "?")
            if m.get("role") == "assistant":
                turns_seen += 1
                if turns_seen >= settings["stuck_gate"]:
                    break
    forced_units = {r["uid"] for r in judgements
                    if any((_msg_uid(m) or "?") in stuck_forced_msgs for m in members_of[r["uid"]])}
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
            if r["uid"] in forced_units:   # the stuck gate's turns stay whole
                continue
            if r["p"] is None or r["p"] + (bonus if r["uid"] in unit_prev else 0.0) >= settings["threshold"]:
                candidates.extend(m for m in members_of[r["uid"]]
                                  if m.get("role") != "assistant" and token_of(m) > settings["select_lines"])
        trims = trim_observations(client, task_text, window, candidates, settings, plain_render, token_of,
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
                                    token_of=lambda r: tok[r["uid"]], forced=forced_units)
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
    input_tokens = sum(r["input_tokens"] for r in reqs) + sum(t["input_tokens"] for t in trims.values())
    output_tokens = sum(r["output_tokens"] for r in reqs) + sum(t["output_tokens"] for t in trims.values())
    record = {
        "backend": "jev", "model": settings["model"],
        "resolved_model": next((r["model"] for r in reqs if r["model"]), None),
        "threshold": settings["threshold"],
        "anchor_bonus": settings["anchor_bonus"] if anchor else 0.0,
        "context_turns": settings["context_turns"], "history": "full",
        "question": settings["question"], "question_lines": settings["question_lines"],
        "question_criteria": settings["question_criteria"], "anchor_tags": anchor_tags,
        "stuck_gate": settings["stuck_gate"], "stuck_threshold": settings["stuck_threshold"],
        "stuck": stuck_p, "stuck_forced": sorted(stuck_forced_msgs),
        "activity_question": bool(settings["activity_question"]),
        "unit": settings["unit"], "units": len(units),
        "requests": len(reqs), "request_attempts": sum(r["attempts"] for r in reqs),
        "request_errors": sum(1 for r in reqs if r["error"]), "questions": len(judgements),
        "state_bytes": len(state.encode("utf-8")),
        "question_bytes": sum(r.get("question_bytes", 0) for r in reqs),
        "errors": extras["errors"], "long_context": sum(1 for r in reqs if r["long_context"]),
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "latency_s": round(latency_s, 3), "latency_sum_s": round(sum(r["latency_s"] for r in reqs), 3),
        "probs": {uid: (None if r["p"] is None else round(r["p"], 4)) for uid, r in by_uid.items()},
        **({"probs_value": {uid: (None if r.get("p_value") is None else round(r["p_value"], 4)) for uid, r in by_uid.items()},
            "probs_activity": {uid: (None if r.get("p_activity") is None else round(r["p_activity"], 4)) for uid, r in by_uid.items()}}
           if settings["activity_question"] else {}),
        "scores": scores,
        "kept_by_threshold": extras["kept_by_threshold"], "capped_out": capped_out,
        "select_lines": settings["select_lines"],
    }
    request_ids = [r["request_id"] for r in reqs]
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
    chunks = _chunk_questions(list(questions), q_bytes, state_bytes, ls["questions"])
    t0 = time.time()
    results, reqs = _ask(client, state, questions, chunks, settings["workers"], progress=progress)
    latency_s = time.time() - t0
    _raise_if_failed(reqs, "line")
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
