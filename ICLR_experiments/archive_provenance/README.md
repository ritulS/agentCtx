# archive_provenance — what was retired from the run tree, and why

Provenance for every batch of run data that was moved out of
`ICLR_experiments/{swebench,terminalbench}` (notes, task lists, selection CSVs
and the scripts that did the move). **No run data lives here.** The moved runs
themselves sit in `<repo>/archives/<same name>/` on the runtime clone
(`/home/ak58925/agentCtx`), which is gitignored; the scripts below still write
there (`--root <repo>` → `<repo>/archives/<name>`).

Until 2026-09-26 these directories were tracked in place under `archives/`;
paths inside the READMEs that say `/home/ak58925/agentCtx/archives/...` are the
original locations and are kept verbatim.

| Directory | What it records | Where the story is told |
|---|---|---|
| `summary_bug_rerun_tooling_20260907_175359_CDT/` | Tooling for the summary-call bug reruns (`scripts/`, the rerun list) and `ARCHIVE_LOG.md`, the ledger of every archive under `archives/` | `EXPERIMENT_LOG_SWE.md`, `EXPERIMENT_LOG_TB.md` |
| `summary-bug-audit-20260907_185802_CDT/` | Local SWE-bench audit that selected the 2,359 `summary_marker_error` runs and the 5,119 rerun candidates | `EXPERIMENT_TIMELINE_DETAIL_SWE.md` (09/07 rows) |
| `{qwen35b,devstral24b,glm47flash}_summary_bug_rerun2_20260908_*/` | Terminal-Bench rerun targets per model (README + `tasks.tsv`) | `EXPERIMENT_LOG_TB.md` |
| `devstral_since_20260905_145630_CDT/`, `glm_since_20260905_145712_CDT/` | Terminal-Bench results backed up after the 2026-09-05 afternoon resume | `EXPERIMENT_LOG_TB.md` |

Run-data archives that have no record directory here (for example
`archives/swebench_summary_marker_error_20260907_192635_CDT/`,
`archives/reeval_*`, `archives/devstral_fc_r23_before_rerun_20260910/`) carry
their own `README.md` / `status.json` next to the data and are listed in
`summary_bug_rerun_tooling_20260907_175359_CDT/ARCHIVE_LOG.md`.

`scripts/maintenance/archive_qwen_ablation_seeded.sh` reads the audit's
rerun list and the archiver from this directory.
