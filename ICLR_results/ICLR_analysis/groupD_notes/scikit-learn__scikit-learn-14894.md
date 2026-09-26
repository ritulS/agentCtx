# scikit-learn__scikit-learn-14894 — why compression-robust (85 runs, resolve 0.86, 12 fails)
## 1. Task shape — fully specified by the PR text
PR gives file (`sklearn/svm/base.py`), function (`_sparse_fit`), failing expression
(`dual_coef_indices.size / n_class`), cause (n_SV=0) AND the intended fix ("Expected
Results ... `self.dual_coef_ = sp.csr_matrix([])`"). All 3 FC runs opened exactly **one**
source file before the first edit (base.py; run_1 step1 `grep -l _sparse_fit` -> step2
`cat base.py` -> edit step25). libsvm.pyx/tests were read only *after* the edit and never
changed it. Gold is re-derivable from PR + one `sed -n '285,300p' base.py`; working set is
~10 lines, so re-materialising it costs one command.
## 2. Environment — verification is impossible, and it didn't matter
/testbed sklearn is unbuilt (`_check_build.cpython-36m*.so` vs py3.11); numpy absent. Every
run burns 5-20 steps on the trap (FC run_3 steps 5-11: `ModuleNotFoundError: numpy` -> pip
-> `ImportError: No module named 'sklearn.__check_build._check_build'` -> `setup.py
build_ext` fails -> `pip install Cython` fails). Escape is always `pip install
scikit-learn` -> **1.9.0**, where the bug is already fixed, tested from /tmp. So
verification is vacuous: FC run_3 step12 prints "Sparse fit successful!" *before any edit*;
step20 copies base.py to `/opt/miniconda3/.../sklearn/svm/base.py` (a path 1.9.0 never
imports); step43 pytests the pip package. **The submitted /testbed patch is never executed
in any run.** The only real check is a standalone scipy simulation of the csr construction
(trc-su b15k run_1 steps 22/31/32, `test_fix(n_SV, n_class)` in /tmp).
## 3. Compression before first edit — clean restart, reconverges in one step
TRC keeps msg[1] (PR description) and stubs tool outputs to 43 chars (`[TOOL OUTPUT CLEARED
— 271 tokens — step 0]`), so the invariant content survives.
- trc-su b10k run_3 (comp 19,30,34,42; edit 38): recovery after comp@30 is a single step34
  `grep -n "dual_coef_indices.size / n_class" -B5 -A5`; step35 restates the diagnosis
  verbatim; edits at 38. Nothing from before the compression was needed.
- trc b10k run_2 (comp 13,22,31,38; edit 31): re-issues `sed -n '280,300p' base.py` at
  steps 21,28,30,37. Resolved in 40 steps.
- Every post-compression trace is the same 3-step plan restarted: re-read window -> restate
  diagnosis -> write guard. Compression also *helps*, evicting the huge failed-build
  tracebacks that otherwise keep pulling the agent back into the env rabbit hole.
## 4. Edit correctness — wide acceptance basin, one narrow trap
FAIL_TO_PASS only asserts `not model.dual_coef_.data.size`. Every resolved run submitted a
non-gold but valid patch: `sp.csr_matrix((n_class, 0))` (FC run_1/2, tr b10k r3, trc b10k
r2, trc-su b10k r3, trc-ss b15k r3, trc b20k r3) or `indptr = np.zeros(n_class+1,
dtype=np.intp)` (FC run_3, trc-su b15k r1). Gold's `sp.csr_matrix([])` appears only in
di__b10k__trc r3, which failed on diff format. First edit was not always right: FC run_3
step17 wrote the buggy `indptr = np.arange(n_class + 1)` and self-corrected at step34 by
pure reasoning ("This creates [0,1,...] which is wrong. It should be all zeros") — that
self-review step is what the unlimited budget buys.
## 5. Failing runs (12)
- d05__b15k__ss r3 / di__b10k__trc-ss r3 / di__b10k__otrc-ss-partial r2: `indptr =
  np.arange(n_class+1)` = [0,1] with empty indices -> csr still raises. Exactly the mistake
  FC run_3 caught at step34; these submitted it.
- di__b20k__otrc-ss-partial r3: else-branch `indptr=[0]` (len 1 for 1 row) -> invalid.
- di__b10k__otrc-su-partial r1: `sp.csr_matrix((data, [], []), (n_class,0))` -> invalid.
- di__b10k__trc-ss r1 guards `n_class == 0`; di__b10k__otrc-tr r3 guards `n_class > 0` —
  **wrong variable** (n_class=1 in regression), both no-ops.
- di__b10k__otrc-tr r1: submission is raw Python source, not a diff -> unappliable.
- di__b10k__trc r3: code is **gold-exact** (`if not n_SV: sp.csr_matrix([])`) but the patch
  came from `diff -u /tmp/original_base.py /testbed/sklearn_bak/svm/base.py` (steps
  116-121): headers name `sklearn_bak/...`, no `diff --git` -> won't apply. Patch-emission
  failure, not reasoning.
- di__b10k__otrc-tr r2 (limits, msg1_wiped): env trap steps 8-29, OTRC comp@13 wiped the
  task description; step32 "Bug fix verified: ... works in scikit-learn 1.3.0"; steps
  101-125 loop `echo "Task completed successfully"` / "What would you like to work on
  today?". Never edited, empty submission.
- di__b20k__otrc-su-partial r2 (limits, 0 comps, 124 steps): stuck in build loop, no edit.
- d05__b10k__tr r1 (limits, 10 comps, edits 34/98/111): plausible edit at 34, then 90 steps
  of env chasing incl. `sed -i 's/np\.float/np.float64/' linear_model/least_angle.py` (98)
  and `sed -i 's/if n_SV == 0:/if n_SV == 0 or n_class == 0:/'` (111). Cap hit, empty.
Taxonomy: 6 wrong fix-variants, 2 patch-emission failures, 3 env/step-limit, 1 msg1 wipe.
## 6. Verdict
Compression-robust because the entire task state lives in the one message compression never
touches: the PR description is a complete spec (file, function, failing line, cause, desired
post-condition) and the only extra context is a 15-line window of `_sparse_fit` that one
`sed`/`grep` restores. Compression destroys nothing durable — each post-compression trace is
the same three-step plan restarted, converging because the plan was never long enough to
hold state worth losing — and a lenient test (`not dual_coef_.data.size`) lets several
independent variants pass, so gold need not be reproduced. The failures are not about losing
context: (a) verification blindness — /testbed is unbuilt, no run executes its own patch, so
a subtly wrong `indptr` or wrong guard variable survives to submission, and FC escapes only
by spending extra steps on self-review; (b) patch emission rather than content (trc b10k r3
had gold code, lost on diff headers); (c) OTRC wiping msg[1], deleting the one thing this
task depends on and turning the run into an amnesic echo loop. Mechanism: short,
self-contained, description-specified working set. Limits: verification blindness and the
primitive's handling of the first message.
