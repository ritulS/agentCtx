"""Compatibility alias for ``agentctx.compression.primitives``.

The compression primitives moved into the ``agentctx`` package. The
mini-swe-agent fork pinned by the submodule (dec8de2) still performs
``import memory`` from inside its compression hook, so this module resolves
that name to the real module object: every attribute, including module-level
state such as the cached summary model, is shared with
``agentctx.compression.primitives``.

Drop this file once the submodule imports ``agentctx.compression.primitives``
directly (mini-swe-agent commit 90624a1 on ``agentctx-customizations``; its
whole diff is the two ``import memory`` lines in agents/default.py).
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentctx.compression import primitives as _primitives  # noqa: E402

sys.modules[__name__] = _primitives
