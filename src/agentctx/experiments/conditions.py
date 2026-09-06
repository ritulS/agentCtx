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
    # OTRC stacked variants: per-step freeze-window clearing + budget-triggered fallback.
    # All three reuse configs/config-online-trc.yaml (agent prompts expect cleared tool stubs).
    {"condition": "otrc-tr",         "primitive": "online_trc",                              "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-su-partial", "primitive": "online_trc_summarize_partial",            "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-ss-partial", "primitive": "online_trc_structured_summarize_partial", "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
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

