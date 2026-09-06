#!/usr/bin/env python3
"""CLI entry point for context-compression experiments.

Shared execution lives in agentctx.experiments.runner; condition definitions
live in agentctx.experiments.conditions.
"""

import sys
from pathlib import Path

AGENTCTX_SRC = Path(__file__).resolve().parents[1] / "src"
if str(AGENTCTX_SRC) not in sys.path:
    sys.path.insert(0, str(AGENTCTX_SRC))

from agentctx.experiments.runner import main  # noqa: E402


if __name__ == "__main__":
    main()
