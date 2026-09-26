# scikit-learn__scikit-learn-13142 — why compression-robust (Group D)
75 runs, resolve 0.83; compression in 61%; 34 runs compress before first edit (resolve 0.76).

## 1. Shape: one file, one 20-line window
Gold = pure REORDER of 5 existing lines in `fit_predict` (`sklearn/mixture/base.py`): move `_, log_resp = self._e_step(X)` below `self._set_parameters(best_params)`. All 3 FC runs take the identical path and open only 2 source files before editing: s1 `find|xargs grep -l GaussianMixture` -> s2-3 `cat gaussian_mixture.py` -> s4 `cat base.py` -> `grep -n "def fit_predict"` -> `sed -n '255,275p'`. First edit: run_1 s24, run_2 s22, run_3 s27. The whole solvable state is ONE tool result — that window shows `_e_step` above `_set_parameters`, and the adjacent comment states the invariant. Re-derivable from (PR title + one `sed`) with zero carried context; that is the robustness mechanism.

## 2. Environment: verification is IMPOSSIBLE, and that is load-bearing
/testbed ships `_check_build.cpython-36m-*.so` under python 3.11, so every `import sklearn` from /testbed dies: "scikit-learn has not been built correctly" (FC run_2 s11). Rebuild fails — numpy missing (s12), then `CompileError: sklearn/ensemble/_gradient_boosting.pyx` (s14). `pip install scikit-learn` gives 1.2.0-1.8.0, which ALREADY CONTAINS the fix, so any repro that does run PASSES (FC run_2 s18, after `mv /testbed/sklearn /testbed/sklearn_src`: "the installed version doesn't have the bug"). No run ever observed the bug. Resolved runs win by abandoning verification (trc/run_3 s77: "The test is still passing... let me just look at the code and make the fix"); runs that refuse burn the whole step budget (sec. 5).

## 3. Compression before first edit: clean restart, ~3-command recovery
`di__b10k__trc/run_3` (comp [7,21,39,55,59,68,78], first edit s78): post-compression it loses the filename (s52 `cat sklearn/mixture/_base.py` -> No such file), recovers via s53 `ls -la /testbed`, s58 `grep -n "def fit" .../base.py` -> "base.py:194: def fit_predict", s59 `cat base.py`, s60-61 sed ranges, s77 `sed -n '255,275p'`, s78 edit. Recovery = 3 commands; nothing pre-compression was needed. `di__b10k__trc-su/run_1` (comp [7,22,38,45], edit s37) identical shape. msg[1] (7816-char PR description + submit protocol) survives TRC/TRC+SU intact — only tool results become `[TOOL OUTPUT CLEARED — N tokens — step k]` — so each restart re-enters with the full spec. Compression deletes only env-fighting debris: exactly what successful runs discard voluntarily.

## 4. Edit correctness: first edit already gold-equivalent; >=4 valid variants
FC run_1's submission is byte-identical to gold. FC run_3 and trc-su/run_1 move `_set_parameters` up instead (equivalent); trc/run_3 puts `_e_step` between `_set_parameters` and `self.n_iter_=`; otrc-tr/run_2 uses `return self.predict(X)`. All satisfy the single invariant "_e_step after _set_parameters(best_params)" -> wide acceptance region. Pre-submit "verification" is only a `sed -n '255,280p'` re-read (FC run_2 s23); no test ever gated a submit.

## 5. Failing runs (13), root cause each
- d05/b20k/ss-partial/r1 (Sub, 0 comp): "fix already in place in commit 036dfdde2"; empty patch.
- d05/b20k/su-full/r1 (exit=''): infra crash, log truncated mid tool-output, 63 api_calls.
- di/b15k/otrc-tr/r3 (Sub, 0 comp): same "already in place"; `cat patch.txt` -> no such file.
- di/b15k/trc-ss/r1 (LimitsExc): correct patch applied s22-28, then s30-125 pip-installing 10+ sklearn versions to verify it; never issued the submit sentinel.
- di/b20k/otrc-su-partial/r2 (LimitsExc, 0 comp): 125 steps of failing `pip install scikit-learn==0.20.2` under py3.11; edit at s45 never submitted.
- di/b15k/trc-su/r1 (Sub): never edited; "fix already present (lines 260-263)"; empty diff.
- d05/b15k/ss/r3 (Sub, unresolved): had the GOLD fix at s25; comp at s29; s32 `git checkout base.py` "to verify the original had the bug" -> repro still PASSES -> s73 "fix already in place" -> s75 overwrites patch.txt with prose. Compression-induced self-revert.
- d05/b15k/ss-partial/r1 (Sub): never edited; "No patch file to submit - fix already in place".
- d05/b15k/su-full/r2 (exit=''): infra crash after a format-error loop, 111 api_calls.
- di/b10k/otrc-tr/r1 & r2 (LimitsExc, msg1_wiped): OTRC cleared message[1] ("[tool-result cleared — online-trc — 2194 tok — step 36]"), losing PR + submit protocol; both had a fix on disk but looped `echo "Task complete: ..."` to the limit. r1's `del lines[273]` had also deleted `return log_resp.argmax(axis=1)`, so its patch was broken anyway.
- d05/b10k/tr/r3 (LimitsExc, 12 comps): 140 steps entirely on the build/import trap, 0 edits.
- di/b10k/trc/r1 (LimitsExc): edits s24,s30 then `git checkout base.py`, then ~90 steps of pip thrash; at s125 still `grep -n "def predict" gaussian_mixture.py` (wrong file).

## 6. Verdict
Robust because the entire solvable state is a single 20-line window reachable in ~3 commands from the PR title, and that title survives every policy that keeps msg[1]. Compression deletes only the useless build-failure transcript; each restart re-derives the diagnosis and converges, and the wide acceptance region absorbs restart-to-restart variation. Two limits. (a) No oracle: /testbed is unimportable and the pip fallback is already patched, so nothing contradicts "it's already fixed" — 4/13 failures submit exactly that, abetted by the in-source comment that *asserts* the invariant and by real commit 036dfdde2 in history. Because the fix is a reordering, a correctly-patched file is indistinguishable from a never-buggy one, which makes amnesia of one's own edit uniquely lethal (ss/r3: gold at s25, comp at s29, `git checkout` at s32). (b) 5/13 failures are the step limit spent on the unwinnable build and 2/13 are OTRC wiping message[1] — task-spec loss, not context loss. Net: robustness = cheap re-derivability; residual failures = absent ground truth plus policies that clear the task description itself.
