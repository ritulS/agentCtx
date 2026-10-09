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
#   p30s        SWE-bench, the 30-task stratified cohort
#               task_lists/swe_verified/p30_stratified.json (self-summarized,
#               like main/ablation).
#   p30s_never7 SWE-bench, the 7 P30S tasks Qwen3.5-35B-A3B never resolved under
#               any fixed primitive (task_lists/swe_verified/p30s_qwen35b_never_resolved.json);
#               holds the adaptive primitive-order cells (``adaptive-*``, see
#               scripts/expansions/run_r2_swe_never7_adaptive.sh).
#   p100_minus_p30s SWE-bench, the 70 P100 tasks outside P30S
#               (task_lists/swe_verified/p100_minus_p30s.json; self-summarized,
#               launched with R2_SECTION=p100_minus_p30s scripts/expansions/run_r2_swe_p30s.sh).
#   p100_minus_p30s_never13 SWE-bench, the 13 P100-minus-P30S tasks Qwen3.5-35B-A3B
#               never resolved under any fixed primitive
#               (task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json);
#               the same adaptive primitive-order cells as p30s_never7, launched with
#               R2_SECTION=p100_minus_p30s_never13 scripts/expansions/run_r2_swe_never7_adaptive.sh.
#   p100_fc_only4 SWE-bench, the 4 P100 tasks Qwen3.5-35B-A3B resolved under full
#               context but never under fixed TR or SU-free
#               (task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json); all
#               eight prefix-3 primitive-order cells (the six mixed ones plus
#               ttt / sss) at 10 runs per task and raised limits (400 steps,
#               7200 s per run), launched with
#               R2_SECTION=p100_fc_only4 scripts/expansions/run_r2_swe_never7_adaptive.sh.
R2_SECTIONS = (*ICLR_SECTIONS, "p30s", "p30s_never7", "p100_minus_p30s",
               "p100_minus_p30s_never13", "p100_fc_only4")
