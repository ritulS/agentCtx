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
    # Length-free summary: the SU-full summarizer call with no word target in the
    # prompt, so compression_ratio does not engage (depth-invariant).
    {"condition": "summarization-free",        "primitive": "summarization_free",        "budget": 15_000},
    # online-claude-select: before every model call, Claude picks which messages / output
    # lines of the COMPLETE history the agent still needs (ids + line ranges, no prose) and
    # the context is rebuilt from the original text; no budget, no length target, no prompt
    # delta (the agent prompt is the benchmark default). Needs ANTHROPIC_API_KEY (or the key
    # file), or MSWEA_EXTRACT_PROVIDER=openrouter with OPENROUTER_API_KEY.
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
]
# Removed 2026-11-19 (the user's decision; git history before that commit has the
# definitions and the primitives): online-claude-extract (oce), online-claude-select-
# incremental (ocsi), -threshold (ocst), -threshold-output-extract (ocstx), -15k
# (ocstx15), -15k-phase (ocstx15p); summarization (su-full), summarization-partial,
# structured-summarize (ss), structured-summarize-partial, structured-summarize-free
# (ss-free), tool-result-clear (trc), trc-su, trc-ss, online-trc (otrc), otrc-tr,
# otrc-su-partial, otrc-ss-partial, the twelve online-jev-full-select* cells
# (ojfs, ojfsb, ojfsbl, ojfsblg, ojfstblg, ojfstblg15, ojfst, ojfst15, ojfstx,
# ojfstl, ojfstl15, ojfstxj), clm, staggered-alternate and staggered-random.



def default_conditions() -> list[dict]:
    """Return a fresh, mutable copy of CONDITIONS.

    A run rewrites budgets (--budget) and
    filters the list (--conditions). Callers get a copy so CONDITIONS above
    stays the pristine definition for every other consumer in the process.
    """
    return copy.deepcopy(CONDITIONS)
