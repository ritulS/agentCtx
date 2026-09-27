# r2 Experiment Log

Second campaign, after the ICLR 2027 submission. Runs live under `data/r2/`;
the ICLR runs stay frozen under `data/iclr26/` (currently
`ICLR_experiments/{swebench,terminalbench}`).

Entries record code as it was at the time.

## 2026-09-26 — Summary cleaning, validation and structural tagging

Commits: `56a4093` (cleaning, validation, retry, tag; submodule `65659cb`
for the online TRC) and the following commit (outcome tracking; submodule
`9ca02a0`). Submodule commits are on `event-log` of
`takeshiho0531/mini-swe-agent`, not yet pushed.

Origin: `ICLR_experiments/open_issues/resume_audit_20260908/` found the
model's inline `</think>` preamble on 219/220 saved structured summaries,
and 33 runs where the agent produced another summary right after one. The
preamble hid the marker line from TRC's `content.startswith` guard, so
summaries could be cleared as tool output. Whether the preamble caused the
re-summarizing is a hypothesis; the audit could not confirm it.

Reference implementations checked before designing the fix: Terminus 2
(`harbor.agents.terminus_2`) and the OpenHands SDK
(`openhands.sdk.context.condenser`). Both separate reasoning at the LLM
layer (`reasoning_content`, i.e. a server-side reasoning parser) and identify
summaries structurally (fixed slot in the chat / typed `Condensation` event),
not by parsing content; neither validates the summary text. Our vLLM servers
run without a reasoning parser (mini-swe-agent parses raw text), so the
separation has to happen in the primitives.

Changes (`src/agentctx/compression/primitives.py`, "Summary message handling"):

- `clean_summary_text(raw, open, close)` normalizes newlines, recognizes
  markers only as standalone lines, removes the reasoning preamble per
  `_reasoning_end()` (a response opening with `<think>` ends at the first
  `</think>`; a `</think>` with no marker line before it is an implicit-open
  preamble; a marked body that quotes `</think>` is left intact), extracts
  the body from the marker spans and re-wraps it in the canonical markers.
- Validation is separate from marking: rejected as `empty_body`,
  `unterminated_reasoning` (open `<think>` never closed) or
  `ambiguous_reasoning` (`</think>` present but no marker line, undecidable).
- `request_summary()` re-queries with the same prompt up to
  `MSWEA_SUMMARY_MAX_ATTEMPTS` (default 2); when every attempt is rejected,
  SU / SS / SU-partial / SS-partial fall back to `truncate()` instead of
  replacing the history with a non-summary.
- SU now asks for `[COMPRESSED HISTORY SUMMARY]` / `[END SUMMARY]` marker
  lines, like SS asks for `[CONTEXT SUMMARY]` / `[END CONTEXT SUMMARY]`.
- Summary messages carry `extra.kind = "summary"` and
  `extra.summary_format` (`had_think_preamble`, `had_open_marker`,
  `had_close_marker`, `rejected`, `attempts`). `is_summary_message()` checks
  the tag first and the marker prefix second (old trajectories). Used by
  `tool_result_clear`, `scored_tool_result_clear` and the online TRC in
  `mini-swe-agent/src/minisweagent/agents/default.py`.
- Tracking: every summary request leaves a `summary_outcome` record
  (`attempts`, `accepted`, `rejections`, `fallback`) that the agent stores in
  `compression_events.jsonl` (per event, `null` when no summary was
  requested) and in `token_log.json` (`summary_outcomes`,
  `summary_fallback_events`). `scripts/maintenance/reconstruct_context.py
  --event K` prints it.

Not changed: `truncate()` still drops summaries like any other compressible
message (TR semantics). vLLM reasoning parser stays off; enabling it
(`--reasoning-parser`) would also strip the agent's own thinking from the
history and is a separate ablation decision.

Known limit: a summarizer reply with no marker line that contains `</think>`
is rejected rather than guessed at; if the summarizer ignores the marker
instruction often, fallbacks rise. `summary_fallback_events` shows the rate.

Tests: `tests/test_summary_cleaning.py` (38 tests, FakeModel; run with
`uvx --with tiktoken --with pyyaml pytest tests/test_summary_cleaning.py`).

Open: whether the re-summarizing loop disappears in real runs. Check the
first r2 SS / SS-partial / TRC+SS / OTRC+SS-partial pilot for FormatErrors
following a summary, and the `rejections` / `fallback` counts.
