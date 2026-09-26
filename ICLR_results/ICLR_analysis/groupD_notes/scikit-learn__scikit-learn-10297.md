# scikit-learn__scikit-learn-10297 — why compression-robust
81 runs, resolve 0.89; compression fired in 62%; 12 runs compressed before first edit (resolve 0.67).

## 1. Task shape: fully specified by the PR text
PR names the class (`RidgeClassifierCV`), the symptom (`TypeError: __init__() got an unexpected keyword argument 'store_cv_values'`), and quotes the docstring that already promises the flag. Fix = 2 lines, ONE file, ONE function.
All 3 FC runs and every compressed run open the same single source file with a byte-identical opening (steps 1-6): `find|grep -l RidgeClassifierCV` -> `cat ridge.py` -> `grep -n "class RidgeClassifierCV"` -> `sed -n '1247,1400p'` -> `grep -n "class _BaseRidgeCV"` -> `sed -n '1087,1250p'`. **Zero** other source files before the first edit (test_ridge.py only read afterwards as confirmation).
Re-derivable from PR + one grep: FC run_1 step 15 states it before any edit — "`RidgeClassifierCV` doesn't accept `store_cv_values` ... but it should pass it to the parent class".

## 2. Environment: reproduction IMPOSSIBLE — and it didn't matter
/testbed sklearn is unbuilt (`_check_build.cpython-36m*.so` vs conda python3.11). 81/81 runs hit `ImportError: No module named 'sklearn.__check_build._check_build'` (3426 occurrences, ~42/run). `pip install -e .` fails ("Multiple top-level packages discovered in a flat-layout"), `setup.py build_ext` fails (Cython/numpy.distutils), `pip install scikit-learn` pulls 1.8.0 which shadows /testbed. FC run_1 burns steps 8-14 here, run_2/3 steps 8-17, trc-su/run_1 steps 39-57.
**No run ever imported the patched code.** Verification is always static: `git diff`, `py_compile`, re-`sed`, reading `test_ridgecv_store_cv_values` as a template. This trap is the largest step sink and the direct cause of every step-limit failure.

## 3. Compression before first edit — recovery = 2-3 step re-grounding
- `di__b10k__trc/run_3` (comp 15, edit 23): steps 16-18 replay steps 3-6 verbatim, then edit at 23. Cost 3 steps.
- `di__b10k__trc-su/run_1` (9 comps, first at 14): step 15 re-issues `sed -n '1247,1400p'`, step 16 `sed -n '1087,1246p'`; edits 18-28. After comp@27 it loses track of what it applied, at **step 32 runs `git checkout sklearn/linear_model/ridge.py`** ("The sed command created a mess. Let me restore the file"), step 33 re-states the fix from memory as 3 bullets, re-applies at 34. Resolved.
- `di__b10k__trc-ss/run_2` (comps 13/24/37, edits 15/18/21): no visible disruption; 41 steps, resolved.
Nothing from before a compression was ever needed: the only state that matters is (file, class, 2 edits), regenerable from message 1 + one grep. Post-compression behaviour is a clean restart that re-converges.

## 4. Edit correctness
First *successful* edit is already gold-equivalent everywhere. FC run_1: step 16 `sed -i` with `\n` is a no-op; step 18 python `str.replace` lands the exact gold signature + `super()` change. Every resolved submission carries the identical functional hunk (`store_cv_values=False` in signature; `store_cv_values=store_cv_values` into `super().__init__`); only added-docstring wording differs (gold's RidgeCV backtick reformat is cosmetic, never needed). Effectively ONE valid fix. Pre-submit verification = `git diff` (+ sometimes `py_compile`); no run added the FAIL_TO_PASS test.

## 5. Failing runs (9) — root causes
- `d05__b20k__tr/run_1` (Submitted, unresolved): tree was **gold-correct at step 58**; step 60 submit was `... | git diff --no-index /dev/null - | grep -E "^\+.*store_cv_values" || git diff ...` -> emitted a grep listing, not a diff. Pure submission-formatting failure.
- `d05__b10k__tr/run_1,2,3` (LimitsExceeded, 124/125/125 steps, 13/9/11 comps): TR wipes edit history; agent re-runs the canonical opening from scratch (run_1 steps 119-123 = steps 2-6) and cycles through the build trap (run_1 steps 107-114 try sklearn 0.19.1/0.20.0/0.20.3/0.21.0/0.21.1/0.20.4/1.2.0).
- `di__b10k__otrc-tr/run_2` (msg1 wiped, comp@37): goal drift — steps 44-47 invent a *different* bug in `_RidgeGCV.fit` ("cv_values_ stores the predictions, not the scores") and edit that; steps 71-125 repeat `echo "Fix complete: ..."` because the `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` protocol went with message 1.
- `di__b10k__otrc-tr/run_3`, `di__b15k__otrc-su-partial/run_3` (msg1 wiped): identical degenerate tail, `echo "Task completed: RidgeClassifierCV now supports store_cv_values parameter"` steps ~108-125. Fix was in the tree; only the exit protocol was lost.
- `d05__b15k__su-full/run_1` (LimitsExceeded, 125): same revert-and-rebuild move as trc-su/run_1 but too late — `git checkout ridge.py` at step 118, re-applies at 124, hits the limit at 125.
- `di__b20k__trc-su/run_2` (LimitsExceeded): stuck comparing /testbed/ridge.py against the pip-installed sklearn 1.8 copy (steps 111-125), never submits.

## 6. Verdict
Compression-robust because the *entire* solution state is (a) carried in message 1 and (b) regenerable in ~3 commands: one file, one class, a 2-line signature/super() change, no cross-file reasoning, no dependence on any observation made earlier in the trajectory. Losing context costs a fixed 2-3 step re-grounding tax, not information — trc-su/run_1 even `git checkout`s its own work away at step 32 and still converges. The dominant risk is therefore not forgetting the fix but running out of steps: the unbuildable-sklearn trap already eats ~40% of every run, so any primitive that also forces repeated restarts (TR@10k: 9-13 compressions) or destroys message 1 (OTRC: all 3 msg1-wiped runs die in an `echo "Task completed"` loop, one after drifting to the wrong function) exhausts the 125-step budget. Two further failures are exit-path bugs on an already-correct tree. Limit of the mechanism: cheap re-derivation protects the *content* of the fix, not the *task statement* or the *submission protocol*, and is only free while steps remain.
