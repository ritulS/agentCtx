"""agentCtx experiment support package."""

from pathlib import Path

# Repository root: src/agentctx/__init__.py -> src/agentctx -> src -> <repo>.
# Single definition for the whole package; submodules import it rather than
# recomputing their own parents[N], which silently breaks when a file moves.
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# Sentinel MSWEA_TOKEN_BUDGET for the uncompressed baselines (full-context and
# online-trc): a budget so large the threshold gate never fires. Conditions,
# the runner, the ICLR cell grammar and the benchmark adapters all test against
# it, so it lives here rather than as a literal in each of them.
INFINITE_BUDGET = 999_999_999
