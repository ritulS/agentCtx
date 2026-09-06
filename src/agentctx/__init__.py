"""agentCtx experiment support package."""

from pathlib import Path

# Repository root: src/agentctx/__init__.py -> src/agentctx -> src -> <repo>.
# Single definition for the whole package; submodules import it rather than
# recomputing their own parents[N], which silently breaks when a file moves.
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
