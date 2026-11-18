"""Default compression conditions and their context-window budgets."""

import copy

from agentctx import INFINITE_BUDGET, WORKSPACE_ROOT

# Experimental conditions.
# "condition" is used as directory name and result key component.
# primitive   = value passed to MSWEA_PRIMITIVE env var
# budget      = value passed to MSWEA_TOKEN_BUDGET env var (context window tokens)
CONDITIONS = [
    {"condition": "full-context",         "primitive": "truncation",           "budget": INFINITE_BUDGET},
    {"condition": "truncation",           "primitive": "truncation",           "budget": 15_000},
    {"condition": "summarization",        "primitive": "summarization",        "budget": 15_000},
    {"condition": "structured-summarize", "primitive": "structured_summarize", "budget": 15_000},
    {"condition": "tool-result-clear",    "primitive": "tool_result_clear",    "budget": 15_000},
    # online-trc: freeze-window clearing (k=4), no budget gate
    {"condition": "online-trc", "primitive": "online_trc", "budget": INFINITE_BUDGET,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    # Stacked primitives: TRC (KEEP_RECENT=3) fires first; second primitive is fallback
    {"condition": "trc-su",  "primitive": "trc_summarize",           "budget": 15_000},
    {"condition": "trc-ss",  "primitive": "trc_structured_summarize","budget": 15_000},
    # trc-tr = existing tool-result-clear (already has truncation fallback built-in)
    # Partial summary primitives: summarize the head, keep budget-fitting tail verbatim
    {"condition": "summarization-partial",        "primitive": "summarization_partial",        "budget": 15_000},
    {"condition": "structured-summarize-partial", "primitive": "structured_summarize_partial", "budget": 15_000},
    # Length-free summaries: same LLM call as SU-full / SS but no word target in the
    # prompt, so compression_ratio does not engage (depth-invariant).
    {"condition": "summarization-free",        "primitive": "summarization_free",        "budget": 15_000},
    {"condition": "structured-summarize-free", "primitive": "structured_summarize_free", "budget": 15_000},
    # OTRC stacked variants: per-step freeze-window clearing + budget-triggered fallback.
    # All three reuse configs/config-online-trc.yaml (since 2026-10-25 an empty delta: the agent
    # prompt is the benchmark default in every condition; the file stays for the -c chain shape).
    {"condition": "otrc-tr",         "primitive": "online_trc",                              "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-su-partial", "primitive": "online_trc_summarize_partial",            "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-ss-partial", "primitive": "online_trc_structured_summarize_partial", "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    # online-claude-extract: after every model call, Claude (claude_extract.py) rewrites the
    # history after system prompt + task statement into the task-relevant extract; no
    # budget gate, no length target. Needs ANTHROPIC_API_KEY (or the key file).
    {"condition": "online-claude-extract", "primitive": "online_claude_extract", "budget": INFINITE_BUDGET,
     "config": WORKSPACE_ROOT / "configs/config-online-claude-extract.yaml"},
    # online-claude-select: before every model call, Claude picks which messages / output
    # lines of the COMPLETE history the agent still needs (ids + line ranges, no prose) and
    # the context is rebuilt from the original text; no budget, no length target, no prompt
    # delta (the agent prompt is the benchmark default). Needs the same key as the extract.
    {"condition": "online-claude-select", "primitive": "online_claude_select", "budget": INFINITE_BUDGET},
    # online-claude-select-anchored (2026-10-27): the same primitive and prompt with two
    # additions through the run environment ("env" is applied on top of the run's
    # variables): every history message is tagged with whether it was in the agent's
    # context at the previous step and the selector is told to start from that selection
    # (MSWEA_SELECT_ANCHOR), and the selected history must fit MSWEA_SELECT_CAP tokens
    # (an over-budget reply is rejected with a correction and re-queried). Answer to the
    # plain cell's step-to-step volatility (Jaccard ~0.5 between consecutive selections)
    # and its context overflows (selections of 60k+ tokens on a 65k server).
    {"condition": "online-claude-select-anchored", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "30000"}},
    # online-claude-select-incremental (2026-11-07): the same primitive and directive grammar,
    # but the selector is handed the agent's CURRENT context (what the previous selection
    # kept, trimmed outputs included, plus the newest turn) instead of the complete history
    # (MSWEA_SELECT_SOURCE=context): the context can only shrink, a dropped message or line
    # never returns, and the selector prompt is context-sized rather than history-sized
    # (the extractive counterpart of online-claude-extract's input window). A line range on
    # an already-trimmed output counts the lines of the trimmed text. No anchor tags (every
    # message shown was in context last step) and no cap; MSWEA_SELECT_CAP can be added.
    {"condition": "online-claude-select-incremental", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_SOURCE": "context"}},
    # online-claude-select-threshold (2026-11-12): the anchored, capped selector, but it
    # fires only while the context exceeds MSWEA_EXTRACT_FIRE_ABOVE tokens (DefaultAgent's
    # online hook) instead of before every call. Between firings the context is append-only
    # (every agent prompt extends the previous one, so Devstral's prefix cache serves it; the
    # per-step ocsa cell left ~57% of its prompt tokens uncached because in-place drops,
    # line-range changes and revivals moved text every step), and at a firing the selector
    # sees the complete history and rebuilds the context under the cap, which is set below
    # the firing threshold so the context has room to grow before the next firing
    # (30000 -> <= 20000: ~3 firings per run on the fc25 ocsa trajectories). Same prompt,
    # grammar and logs as ocsa, except that the anchoring uses the prompt-cache-friendly
    # "trailing" form (MSWEA_SELECT_ANCHOR=trailing: the previous-context uids and the budget
    # figure sit in the trailing block, so the history blocks are byte-identical from call to
    # call and the selector's own prompt cache serves them; ocsa's per-header tags hit only
    # ~6%); the selector call count drops from one per step to a few per run.
    {"condition": "online-claude-select-threshold", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_ANCHOR": "trailing", "MSWEA_SELECT_CAP": "20000", "MSWEA_EXTRACT_FIRE_ABOVE": "30000"}},
    # online-claude-select-threshold-output-extract (2026-11-12, cell tag ocstx): ocst plus a
    # per-output pre-extraction. Every NEW tool output above MSWEA_OUTPUT_EXTRACT_ABOVE tokens
    # (1000) is handed, right after it is added to the history, to the same extractor model
    # with the task statement and the agent message that issued the command, and the lines it
    # keeps replace the output IN PLACE (memory.extract_tool_output, DefaultAgent._output_extract;
    # same directive grammar as the selector, a fixed one-line "pre-extracted" note above the
    # kept lines, "[... N lines omitted ...]" where it cut). The omitted lines leave the context,
    # the complete history the threshold selector later re-selects from, and the trajectory at
    # once: unlike every other online-claude-select cell, dropped output text can never return.
    # The threshold selector itself is unchanged (fires above 30000, cap 20000, trailing anchor).
    {"condition": "online-claude-select-threshold-output-extract", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_ANCHOR": "trailing", "MSWEA_SELECT_CAP": "20000", "MSWEA_EXTRACT_FIRE_ABOVE": "30000",
             "MSWEA_OUTPUT_EXTRACT_ABOVE": "1000"}},
    # online-claude-select-threshold-output-extract-15k (2026-11-12, cell tag ocstx15): the
    # ocstx cell with the firing threshold halved (MSWEA_EXTRACT_FIRE_ABOVE 30000 -> 15000)
    # and the cap lowered in the same 2:3 proportion (20000 -> 10000) so the rebuilt context
    # still has room to grow before the next firing; the per-output pre-extraction (1000) is
    # unchanged. On the ocst4 pilot the 30k cell fired the selector 0-2 times per run with
    # contexts peaking at 24-33k; this cell asks what halving that envelope does.
    {"condition": "online-claude-select-threshold-output-extract-15k", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_ANCHOR": "trailing", "MSWEA_SELECT_CAP": "10000", "MSWEA_EXTRACT_FIRE_ABOVE": "15000",
             "MSWEA_OUTPUT_EXTRACT_ABOVE": "1000"}},
    # online-claude-select-threshold-output-extract-15k-phase (2026-11-12, cell tag ocstx15p):
    # ocstx15 with a phase-boundary gate on the threshold firing (MSWEA_PHASE_GATE=1;
    # memory.judge_phase_boundary, DefaultAgent._phase_gate). Once the context exceeds the
    # 15000-token threshold, a due firing is first put to the same extractor model as a
    # question: shown the task statement and the agent's current context, is the newest turn
    # a natural break in the work (a phase completed: cause identified, edit applied and
    # confirmed, test result read and acted on) or is the agent mid-operation? The selector
    # fires only on "boundary"; on "continue" the step runs with the context untouched and
    # the question is asked again before the next step. Above MSWEA_PHASE_GATE_FORCE_ABOVE
    # (30000, the ocst threshold) the selector fires without asking, so a judge that never
    # sees a boundary cannot let the context grow past Devstral's window. The judge never
    # writes a word the agent reads: verdicts and reasons go to the token log
    # (phase_judge_events). Cap, pre-extraction and anchoring as in ocstx15.
    {"condition": "online-claude-select-threshold-output-extract-15k-phase", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_ANCHOR": "trailing", "MSWEA_SELECT_CAP": "10000", "MSWEA_EXTRACT_FIRE_ABOVE": "15000",
             "MSWEA_OUTPUT_EXTRACT_ABOVE": "1000",
             "MSWEA_PHASE_GATE": "1", "MSWEA_PHASE_GATE_FORCE_ABOVE": "30000"}},
    # clm (2026-11-10): CLM self-editing, ported from context-language-models. The agent's
    # history is mirrored to /tmp/.live_ctx/LIVE_CTX_MAIN.txt in the task container before
    # every command and the agent compacts it by editing that file; nothing fires on its
    # own. The budget is a hard limit enforced without truncation: nudges below it, and at
    # the limit the newest turns are rolled back and a compaction is demanded
    # (src/agentctx/compression/clm/). The ONLY condition whose agent system prompt differs
    # from the benchmark default: configs/config-clm.yaml appends the mirror-editing
    # instructions (the user's decision 2026-11-10). Every model call counts as a step.
    {"condition": "clm", "primitive": "clm", "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-clm.yaml"},
    # Staggered: at each compression event, pick one of the oracle-optimal pair (TR + budget-best).
    # Pair is fixed by budget inside default.py: 10k→TR+TRC+SS, 15k→TR+SU-partial, 20k→TR+TRC+SS.
    {"condition": "staggered-alternate", "primitive": "staggered_alternate", "budget": 15_000},
    {"condition": "staggered-random",    "primitive": "staggered_random",    "budget": 15_000},
]


def default_conditions() -> list[dict]:
    """Return a fresh, mutable copy of CONDITIONS.

    A run rewrites budgets (--budget), swaps OTRC configs (--otrc-config) and
    filters the list (--conditions). Callers get a copy so CONDITIONS above
    stays the pristine definition for every other consumer in the process.
    """
    return copy.deepcopy(CONDITIONS)
