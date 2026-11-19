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
    # online-jev-full-select (2026-11-17 as online-jev-select / ojs, renamed 2026-11-18; cell
    # tag ojfs): the online_claude_select primitive with the selector backend switched to
    # TypeSafe's Jev decision model (MSWEA_SELECT_BACKEND=jev; agentctx.compression.jev_select).
    # Instead of one generative call over the complete history, ONE Jev request per selection
    # (chunked when the questions are many, MSWEA_JEV_SELECT_QUESTIONS) whose state is the task
    # statement, the COMPLETE history (window and kept tail, rendered as the generative
    # selector sees it, every message under its uid header) and the agent's newest turn, and
    # whose questions are one noul per history message, keyed by uid ("the agent still needs
    # history message m00042 to finish the task"); Jev reads the state once and answers them
    # all, and can tell a superseded or repeated message (the "full" of the name; the local
    # form, one request per message with the candidate alone, was the ojs / ojst cells until
    # 2026-11-18 and was removed: AUC 0.62 against the generative selector's keep/drop vs
    # 0.76-0.85 with the history shown). A message is kept
    # whole when its probability clears MSWEA_JEV_KEEP_THRESHOLD (0.5), plus the
    # MSWEA_JEV_ANCHOR_BONUS (0.15) for a message that was in the agent's context at the
    # previous step (the anchoring, MSWEA_SELECT_ANCHOR=1, is a hysteresis here: no tags, no
    # prompt). Under the 30000-token cap (as ocsa) the kept messages are ranked by probability
    # and taken while they fit: no reply is ever rejected or re-queried. Jev returns typed
    # values only, so there are no line ranges and it never writes a word the agent reads.
    # The state exceeds TypeSafe's long-context size as soon as the history does; a selection
    # costs one state's input. Needs TYPESAFE_API_KEY (or ~/.config/agentctx/typesafe_api_key);
    # the OpenRouter / Anthropic extractor settings are unused.
    {"condition": "online-jev-full-select", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "30000"}},
    # online-jev-full-select-budget (2026-11-18, cell tag ojfsb): ojfs with the noul put in the
    # `budget` wording (MSWEA_JEV_QUESTION=budget; BUDGET_INSTRUCTIONS / BUDGET_CRITERIA in
    # jev_select.py): "when the history is trimmed to a fixed token budget, message <uid>
    # belongs on the kept side, judged relative to the rest of the history and not by how far
    # along the task is". Same per-step firing, hysteresis (+0.15) and 30000 cap as ojfs. Why a
    # separate cell: under the default `needed` wording ("the agent still needs it to finish
    # the task from here") Jev's probabilities fall with task progress (median 0.1-0.3 late in
    # a run, a handful of messages above 0.5), so the 0.5 threshold keeps almost nothing and
    # the kept amount is set by the threshold, not by Jev; on 12 ocst / ocsa firings of 6 runs
    # the `budget` wording's share of tokens with p >= 0.5 tracked the generative selector's
    # kept share (correlation 0.81) at a slightly weaker ranking (AUC 0.62-0.84 vs 0.72-0.90).
    # The first per-step Jev cell to run (the ojfs cells before it were threshold-fired).
    {"condition": "online-jev-full-select-budget", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "30000",
             "MSWEA_JEV_QUESTION": "budget"}},
    # online-jev-full-select-budget-lines (2026-11-18, cell tag ojfsbl): ojfsb plus the ojfstl
    # LINE-LEVEL selection (MSWEA_JEV_SELECT_LINES=1000 with the ranking line rule: threshold 0,
    # top 15% of the lines, 1-line pad): at every firing each kept observation above 1000
    # tokens is also judged line by line by Jev and kept as line ranges, the Jev counterpart
    # of ocsa's `keep <uid> L<a>-<b>`. Under MSWEA_SELECT_SOURCE=full nothing is deleted: an
    # omitted line only leaves the context and can return at a later firing. The per-step
    # pilot of 2026-11-18 runs this cell (the user's choice: the ocsa comparison includes
    # line keeps); ojfsb is the whole-message form.
    {"condition": "online-jev-full-select-budget-lines", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "30000",
             "MSWEA_JEV_QUESTION": "budget", "MSWEA_JEV_SELECT_LINES": "1000",
             "MSWEA_JEV_LINE_THRESHOLD": "0", "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1"}},
    # online-jev-full-select-budget-lines-stuck (2026-11-18 evening, cell tag ojfsblg): ojfsbl plus
    # the stuck gate (MSWEA_JEV_STUCK_GATE=4; jev_select.py STUCK_*): every selection also asks
    # Jev, in the same request, whether the agent is stuck (its newest steps repeat steps it has
    # already taken); when that reads >= 0.5 the newest 4 turns of the window are kept whole
    # whatever their own p, on top of the verbatim kept tail. Why: in the ojfsbl pilot
    # sympy-14531's context froze at 21 early messages and the agent repeated test / pip install
    # 250 times; no wording made Jev keep a repeated message (consequence / record framings
    # 0.2-0.5), but the stuck question read 0.93-0.97 on that history and 0.18-0.38 on a healthy
    # history of the same task, so the detection is Jev's and the keep rule is ours. Offline on
    # the collapsed history the gate adds the 4-turn test / pip cycle (~550 tokens, 28 messages
    # kept instead of 20) and leaves the healthy history unchanged. The per-step value
    # judgement, the line rule, the hysteresis and the cap are those of ojfsbl.
    {"condition": "online-jev-full-select-budget-lines-stuck", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "30000",
             "MSWEA_JEV_QUESTION": "budget", "MSWEA_JEV_SELECT_LINES": "1000",
             "MSWEA_JEV_LINE_THRESHOLD": "0", "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1",
             "MSWEA_JEV_STUCK_GATE": "4"}},
    # online-jev-full-select-threshold-budget-lines-stuck (2026-11-19, cell tag ojfstblg): the
    # THRESHOLD form (fired like ocst: above 30000 tokens, rebuilt under a 20000 cap that is only
    # an upper bound) with the parts that held up in the 2026-11-18/19 probes: the `budget`
    # wording with criteria (ranking AUC 0.75-0.95 against the Claude gold), the amount read
    # from Jev as the p >= 0.5 share (0.8-1.9x the gold share, right direction every time;
    # distribution-based rules and direct "how much" questions were worse), MSWEA_JEV_UNIT=turn
    # (a command and its observations kept or dropped together: in the per-step runs 45% of
    # kept observations had lost their command), the ojfstl line rule unchanged, and the stuck
    # gate (k=4) as insurance at the firing. Between firings the context is append-only, so the
    # agent always sees its recent attempts (the per-step form's collapse cannot occur) and the
    # Jev cost is a few firings per run. The user's choice 2026-11-19 after the per-step pilots
    # (ojfsbl 2/4, ojfsblg 0/1 on sympy-14531): keep the amount adaptive, not fixed by the cap.
    {"condition": "online-jev-full-select-threshold-budget-lines-stuck", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "20000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "30000", "MSWEA_JEV_QUESTION": "budget", "MSWEA_JEV_UNIT": "turn",
             "MSWEA_JEV_SELECT_LINES": "1000", "MSWEA_JEV_LINE_THRESHOLD": "0",
             "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1", "MSWEA_JEV_STUCK_GATE": "4"}},
    # online-jev-full-select-threshold-15k-budget-lines-stuck (2026-11-19, cell tag ojfstblg15):
    # ojfstblg with the firing threshold halved (MSWEA_EXTRACT_FIRE_ABOVE=15000) and the cap
    # lowered in the same 2:3 proportion (MSWEA_SELECT_CAP=10000), as ocstx15 / ojfst15 are to
    # their 30k cells. The user's request after the ojfstblg pilot (4/4 at $0.23, but two of the
    # four tasks never crossed 30k and ran as FC): at 15k every ocst4 task engages Jev.
    {"condition": "online-jev-full-select-threshold-15k-budget-lines-stuck", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "10000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "15000", "MSWEA_JEV_QUESTION": "budget", "MSWEA_JEV_UNIT": "turn",
             "MSWEA_JEV_SELECT_LINES": "1000", "MSWEA_JEV_LINE_THRESHOLD": "0",
             "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1", "MSWEA_JEV_STUCK_GATE": "4"}},
    # online-jev-full-select-threshold (2026-11-17, cell tag ojfst): the Jev backend fired like ocst,
    # only while the context exceeds 30000 tokens, rebuilding it under a 20000-token cap, so
    # the context is append-only between firings (prefix cache) and the per-message
    # judgements run a few times per run instead of before every step.
    {"condition": "online-jev-full-select-threshold", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "20000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "30000"}},
    # online-jev-full-select-threshold-15k (2026-11-18, cell tag ojfst15): ojfst with the firing
    # threshold halved and the cap lowered in the same 2:3 proportion, as ocstx15 is to ocstx.
    {"condition": "online-jev-full-select-threshold-15k", "primitive": "online_claude_select", "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "10000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "15000"}},
    # online-jev-full-select-threshold-output-extract (2026-11-17, cell tag ojfstx): ojfst plus the
    # ocstx per-output pre-extraction (MSWEA_OUTPUT_EXTRACT_ABOVE=1000), which still goes to
    # the generative extractor model (claude_extract.py: both keys are needed). Jev decides
    # which messages stay; the extractor trims long outputs to their useful lines, so the
    # whole-message-only backend is not left keeping or dropping 5000-line outputs as a unit.
    {"condition": "online-jev-full-select-threshold-output-extract", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "20000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "30000", "MSWEA_OUTPUT_EXTRACT_ABOVE": "1000"}},
    # online-jev-full-select-threshold-lines (2026-11-18, cell tag ojfstl): ojfst with LINE-LEVEL
    # selection by Jev itself (MSWEA_JEV_SELECT_LINES=1000; jev_select.trim_observations): at
    # a firing, every observation that passes the keep threshold and exceeds 1000 tokens is
    # also judged line by line (the line judge of the per-output pre-extraction, with the
    # task statement and the command that produced the output) and kept as line ranges,
    # rendered like a generative `keep <uid> L<a>-<b>`; the cap admits it by its trimmed
    # size. Line rule: no probability threshold (Jev's absolute line probabilities are low:
    # p >= 0.5 kept 1-3% of the lines where DeepSeek kept 4-14%), the top 15% of the lines
    # by probability (MSWEA_JEV_LINE_MAX_FRACTION), widened by one line each side
    # (MSWEA_JEV_LINE_PAD). Omitted lines leave the context, not the history (source=full):
    # a later firing can bring them back. Jev only, one key; nothing is deleted.
    {"condition": "online-jev-full-select-threshold-lines", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "20000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "30000", "MSWEA_JEV_SELECT_LINES": "1000",
             "MSWEA_JEV_LINE_THRESHOLD": "0", "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1"}},
    # online-jev-full-select-threshold-15k-lines (2026-11-18, cell tag ojfstl15): ojfstl at the
    # ojfst15 firing threshold and cap (15000 / 10000). The 15k firing keeps the history Jev
    # reads under its 32k per-question default context.
    {"condition": "online-jev-full-select-threshold-15k-lines", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "10000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "15000", "MSWEA_JEV_SELECT_LINES": "1000",
             "MSWEA_JEV_LINE_THRESHOLD": "0", "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1"}},
    # online-jev-full-select-threshold-jev-output-extract (2026-11-18, cell tag ojfstxj): ojfstx with
    # the per-output pre-extraction answered by Jev too (MSWEA_OUTPUT_EXTRACT_BACKEND=jev,
    # jev_select.jev_extract_output: one request per new output above 1000 tokens, one noul
    # per line, same line rule as ojfstl), so the whole cell runs on the one Jev key and the
    # extractor model is unused. Unlike ojfstl the omitted lines are deleted from the history
    # (the ocstx semantics); the threshold selection itself stays whole-message.
    {"condition": "online-jev-full-select-threshold-jev-output-extract", "primitive": "online_claude_select",
     "budget": INFINITE_BUDGET,
     "env": {"MSWEA_SELECT_BACKEND": "jev", "MSWEA_SELECT_ANCHOR": "1", "MSWEA_SELECT_CAP": "20000",
             "MSWEA_EXTRACT_FIRE_ABOVE": "30000", "MSWEA_OUTPUT_EXTRACT_ABOVE": "1000",
             "MSWEA_OUTPUT_EXTRACT_BACKEND": "jev",
             "MSWEA_JEV_LINE_THRESHOLD": "0", "MSWEA_JEV_LINE_MAX_FRACTION": "0.15", "MSWEA_JEV_LINE_PAD": "1"}},
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
