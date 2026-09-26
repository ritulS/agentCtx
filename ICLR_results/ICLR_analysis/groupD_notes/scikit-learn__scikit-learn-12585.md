# scikit-learn__scikit-learn-12585 — why compression-robust
**Degenerate case: the PR description CONTAINS the gold patch** ("Possible fix: change base.py line 51 to `elif not hasattr(estimator, 'get_params') or isinstance(estimator, type):`"), and msg1 is never wiped (msg1_wiped=False in all 82 runs). 1 line, 1 file, 1 `sed`.

## 1. Task shape
- PR text gives file, line, exact old string, exact new string. Nothing to discover.
- FC opens exactly **one** source file before first edit (`/testbed/sklearn/base.py`): run_1 s1 `find -name base.py`, s2 `cat base.py|head -100`, edit s12; run_2/run_3 same shape (edits s16 / s28). Gold is re-derivable from PR description + zero file reads; the read only confirms the line number.

## 2. Environment: a trap that never mattered
- `python` = `/opt/miniconda3/bin/python` (3.11); /testbed sklearn is built cpython-36, so `import sklearn` ALWAYS fails (`ModuleNotFoundError: sklearn.__check_build._check_build`; FC run_1 s8, su-full run_1 s17, ss-partial run_2 s15). Rebuild dies: no numpy (s4), then after `pip install numpy scipy Cython` → `CompileError: sklearn/ensemble/_gradient_boosting.pyx` (s7). `python -m pytest` → "No module named pytest". No log mentions `/opt/miniconda3/envs/testbed`.
- **No run ever executed the real test.** Distractor: some runs `pip install scikit-learn` (FC run_3 s11) then "verify" against installed 1.8.x which already has the fix (su-full run_1 s17: "the installed version of sklearn (1.8.0) already handles this case correctly"). Irrelevant — correctness came from the PR text, not from verification.

## 3. Compression-before-edit runs: clean restart, converges anyway
Recovery move is context-free: re-`grep` the one line, or `git diff sklearn/base.py`.
- `d05__b10k__tr/run_3` (comp 16,23,44; edit 27): s19 re-`cat base.py|head -80`, s26 `grep -n "elif not hasattr(estimator, 'get_params'):" sklearn/base.py`, s27 sed; s54 `git diff sklearn/base.py` restores full state.
- `d05__b10k__su-full/run_1` (comp 17,32,42): s18 textbook restart — "Let me start by understanding the issue. The PR description mentions that `clone` fails when…" → re-read base.py → edit s27. Nothing pre-compression was needed.
- `d05__b10k__ss/run_2` (comp 17,24): re-read base.py s15, edit s17 quoting the PR's exact replacement. `d05__b10k__ss-partial/run_2` (comp 14,26; edit 24): same.
- Long runs are churn, not confusion: `di__b15k__trc-su/run_1` (9 comps, 86 steps) broke its own scratch `clone` at s52 (`safe=safe`) and reverted — self-inflicted, not compression.

## 4. Edit correctness
- First edit gold-identical in essentially every run. 3 accepted variants: (a) gold line only (majority, blob 34998270c); (b) `+ if isinstance(estimator, type): return estimator` (FC run_2, d05__b10k__tr/run_1, di__b10k__trc/run_2); (c) `elif isinstance(estimator, type): return copy.deepcopy(estimator)` (di__b15k__trc-su/run_1). All pass because `copy.deepcopy(cls) is cls` and `test_clone_estimator_types` is identity-based — the target is wide.
- Pre-submit verification = standalone copy of `clone()` run under `python -c`, plus `git diff sklearn/base.py`; both history-independent. Near-miss: FC run_2 s30 overwrote all of base.py with a heredoc, recovered s31 via `git checkout sklearn/base.py`.

## 5. Failing runs — **all 10 are eval/bookkeeping artifacts, zero agent failures**
All 10 have `exit_status='Submitted'` and a correct patch in trajectory.json.
- `d05__b10k__tr/run_1,run_2` and `di__b10k__trc/run_1,run_2`: eval report `resolved_ids=[task]` (**resolved**) but the `experiment_results.json` record has `resolved=None, exit_status=None` → CSV `silent_crash`. Aggregation dropout.
- `d05__b20k__tr/run_1,run_2`, `d05__b20k__ss/run_2`, `di__b20k__trc/run_1,run_2`: eval report `error_instances=1, error_ids=[task]` = docker/eval-harness error, not a test failure; patches byte-identical to gold (blob 34998270c).
- `d05__b15k__su-partial/run_3` (`submitted_unresolved`): eval report says `resolved_instances: 1, resolved_ids=[task]` while experiment_results.json says `resolved: False` — stale flag from the 2026-08-23 re-run. **Genuinely resolved.**
- → True resolve = **82/82 = 1.00**, not 0.88; the 0.60 for "compression before first edit" is entirely this artifact.

## 6. Verdict
Robustness comes from **zero required context depth, not from good recovery**. The one message compression cannot touch (msg1 / PR text) already holds file, line, search string and replacement string. Working set = one line of one file; the edit is an idempotent `sed`; state is recoverable at any moment by `git diff`; the acceptance test is identity-based so several non-gold edits also pass. Compression therefore deletes only redundant exploration (failed builds, failed imports, scratch reimplementations of `clone`), and the post-compression agent restarts from the PR text and converges in ~10 steps. The limits this task exposes are not about compression at all: the container is un-buildable (no importable sklearn, no pytest) so no run could empirically verify, and the only "failures" are harness errors and stale result flags. Group-D membership here is evidence that **when the fix is stated in the prompt, context budget is irrelevant** — plus a warning that `silent_crash`/`submitted_unresolved` labels in `analysis/outcomes/swebench_outcomes.csv` can be 100% spurious and must be cross-checked against `<cell>/eval/*.json`.
