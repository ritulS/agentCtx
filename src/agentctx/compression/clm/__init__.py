"""CLM self-editing (primitive ``clm``): the agent compacts its own context by
editing a mirror file in the task container. See ``session.py``.

``context_string.py`` is copied unchanged and ``budget.py`` is ported from
context-language-models (``clm/clm_harness``), which is licensed CC BY-NC 4.0;
both keep the original copyright header, and ``budget.py`` lists its changes.
"""

from agentctx.compression.clm.session import (
    CTX_DIR,
    CTX_FILE,
    EXIT_STATUS_BUDGET,
    PRIMITIVE,
    ClmSession,
    ClmSettings,
)

__all__ = ["CTX_DIR", "CTX_FILE", "EXIT_STATUS_BUDGET", "PRIMITIVE", "ClmSession", "ClmSettings"]
