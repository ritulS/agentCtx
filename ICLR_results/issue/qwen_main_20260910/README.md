# Qwen main evaluation audit (2026-09-10)

Scope: 35 cells under `ICLR_results/swebench/main/qwen35b`, covering the 7,893 records in the current indexes. Some 10K/20K cells contain fewer than 300 records. Archived results that have not been restored are excluded. This audit does not assess generation conditions or whether the summary bug requires regeneration.

## Conclusions

- Evaluation is required for 20 records: 10 with container image 409 invalid state errors and 10 with an undetermined resolved status and missing internal reports. The latter are not all established to be timeouts.
- Of the 20 records, 19 concern scikit-learn__scikit-learn-14710 and 1 concerns sympy__sympy-19637.
- There are 17 at 15K, 1 each for FC∞ and OTRC∞, and 1 for 20K OTRC+SU-p.
- In 1 record, the internal report matches the patch and reports True, but the index contains None: 15K SS / django__django-17087 / run_2. Synchronizing the result takes priority over retesting.
- A further 253 records need review: 46 with prediction/current submission mismatches, 140 listed in error_ids in old aggregate reports, 60 with missing evaluation reports, and 7 with verdict mismatches between old aggregate reports and the index. Resolve these by restoring old detailed logs or evaluating the current patches afresh. error_ids can include patch application failures; not all are established to be infrastructure errors.
- For 4,573 records, old aggregate reports agree with the index, but internal reports/patch.diff files are missing, leaving patch evaluation provenance unverified. Missing logs alone are not considered grounds for requiring blanket reevaluation.
- There are 667 records with matching internal reports, patches, and index verdicts; 20 with current-patch application failures; and 2,359 with patch_generated=False.

## Outputs

- `reevaluation_candidates.csv`: The 20 priority records (evaluation of existing generated patches only).
- `result_sync_candidates.csv`: The 1 candidate for result synchronization.
- `review_candidates.csv`: The 253 records above and the 4,573 with only old aggregate reports.
- `evaluation_classification.csv`: Evidence paths and classifications for all records.
- `summary.json`: Counts by cell, classifications, and index SHA256 hashes at audit time.
- `audit_evaluation.py`: Script for reproducing the audit. It only reads experiment files and writes diagnostic outputs to this audit directory.

Index SHA256 hashes were confirmed to match before and after the audit. No experiments, reevaluation, result synchronization, or outcomes updates were performed. This audit did not verify whether the existing Devstral reevaluation script can be used unchanged for Qwen.
