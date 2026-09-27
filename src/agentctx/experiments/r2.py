"""Result paths for the r2 extension campaign (the project that follows ICLR).

r2 runs are kept apart from the canonical ICLR tree but use the same
``<benchmark>/<section>/<model>/<cell>`` layout and the same cell validation
(``agentctx.experiments.iclr``), so every ICLR analysis tool can be pointed at
this tree unchanged. The tree lives under ``data/`` and is gitignored.
"""

from __future__ import annotations

from agentctx import WORKSPACE_ROOT
from agentctx.experiments.iclr import ICLR_SECTIONS

R2_ROOT = WORKSPACE_ROOT / "data" / "r2"
R2_ROOTS = {
    "swe-bench": R2_ROOT / "swebench",
    "terminal-bench": R2_ROOT / "terminalbench",
}
# The ICLR sections plus the r2-only cohort sections:
#   p30s  SWE-bench, the 30-task stratified cohort task_lists/p30_swe_stratified.json
#         (self-summarized, like main/ablation).
R2_SECTIONS = (*ICLR_SECTIONS, "p30s")
