# sympy__sympy-19954 — why compression-robust (95 runs, resolve 0.98)
## 1. Task shape: the PR description IS the localization
PR ships a full traceback (`perm_groups.py:2207, minimal_blocks(), del num_blocks[i], blocks[i]`)
plus a 3-line repro: file, function, line, failing statement all given; no search needed. All 3 FC
runs open exactly ONE source file (`/testbed/sympy/combinatorics/perm_groups.py`) before first edit,
always a `sed -n` window in 2140-2250 (FC run_1: step 2 `find -name perm_groups.py`, step 3
`sed -n '2190,2230p'`, done). Working set = the 19-line loop 2196-2214 (trc-ss run_1 reads exactly
`2196,2214p` at step 8, edits at 9). Gold fix re-derivable from PR traceback + one 20-line read: yes.
## 2. Environment: clean repro, one benign trap
`mpmath` missing; each run hits it once and fixes it (`pip install mpmath -q` — FC run_1 step 7,
tr run_2 step 5, ss run_1 step 8). `pytest` also missing (FC run_1 step 14) and `python -m
sympy.testing.runtests` silently reports "0 passed" (step 16); recovered via `pip install pytest`
(step 17: `test_sylow_subgroup PASSED`, `59 passed, 2 skipped`). 1-3 steps, never fatal, fully
re-discoverable post-compression. Repro is 3 deterministic lines (IndexError vs "Success!").
## 3. Compression before first edit (4 runs, resolve 1.00)
- tr b10k run_2 (comp step 10, 11706->4380 tok): step 11 re-reads `sed -n '2180,2250p'` — one command
  restores the whole working set; edit at 12. Only real loss is the name of its own scratch file:
  step 13 `python /testbed/test_fix.py` -> "No such file" (pre-compression it had written
  `reproduce_issue.py`); step 14 recreates the repro from the PR text in msg 1. Cost: 1 step.
- trc-ss b10k run_1 (comp 8, 11): step 8's tool result (the 19 lines) survives, edit at 9 in the same
  breath. Second compression lands after the edit — irrelevant, the edit is on disk; step 11 just
  `cat -n ... 2196,2220p` to re-verify.
- su-full b10k run_2 (comp 11): the injected `[COMPRESSED HISTORY SUMMARY]` literally contains the
  finished patch as a code block ("collect all indices ... delete in reverse order") — the diagnosis
  is ~15 lines, so summarization preserved the entire solution.
- ss b10k run_1 (comp 15, 12392->2656, ratio 0.21): summary kept only analysis; step 16 confabulates
  "The fix has been applied successfully", runs the repro, IndexError reappears — the environment
  falsifies the false belief in ONE step; 17 re-reads the file, 18 applies the real fix.
Nothing pre-compression was ever *needed*: msg 1 (PR + submit protocol) survives (msg1_wiped=False)
and the edit target is one 20-line window. Post-compression = clean restart that converges.
## 4. Edit correctness: one strong attractor, many syntaxes
Every resolved run writes the same *semantic* fix — defer deletions, apply in reverse index order —
and none matches gold syntactically (gold uses `blocks_remove_mask`). FC run_1/2/3 and trc-su run_3
add `indices_to_remove`/`indices_to_delete`, keeping the old `rep_blocks = [r for r in rep_blocks if
r not in to_remove]`; ss b10k run_1 and trc-ss b15k run_3 instead `del num_blocks[i], blocks[i],
rep_blocks[i]` in reverse. All pass FAIL_TO_PASS -> multiple valid fixes. First edit already
gold-equivalent in FC run_1 (10), tr run_2 (12), trc-ss run_1 (9); verified by PR repro then tests.
## 5. Failing runs (2/95)
- d05__b15k__ss run_3 — harness crash, not a fix failure: `exit_status=''`, submission `''`, log ends
  mid-step-49. Correct patch was on disk and verified (`test_sylow_subgroup ok`, `58 passed`) BEFORE
  the step-23 compression (15119->1738, ratio 0.11), which erased "I already fixed this": step 30
  "The test passed, which means the issue might have been fixed already in the repo", then ~20 steps
  of `git log --grep=IndexError` archaeology + format errors ("found 0 actions") until it died.
- di__b10k__otrc-tr run_2 — task-description wipe: msg[1] is `[tool-result cleared — online-trc —
  1528 tok — step 16]`, i.e. online-TRC cleared the instance prompt, taking the
  `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` protocol (agent.log line 224, only in msg 1) with it.
  It had already edited (steps 14, 23); from ~step 30 to 124 it loops `echo "Bug fix complete..."` /
  "Task completed", never emits the sentinel -> LimitsExceeded, submission ''. 117 online clears,
  4 truncations (17/61/86/116). Broken submit channel, not a broken repair.
## 6. Verdict
Robust because the whole state is externalized and cheap to re-acquire: the traceback pins
file+line+function, the defect is a 19-line self-contained loop, the fix is a stock Python idiom
(don't delete while enumerating -> defer + reverse) re-derived from scratch each time, and the
oracle is a 3-line script. The durable artifacts — edited file and repro script — live in the
container, not in context, so a compression costs one `sed -n` re-read (tr run_2 step 11) and even
helps by dropping the debug-print dumps that dominate pre-edit context. Limits: it needs (a) msg 1
to survive, since that carries both traceback and submit protocol — wipe it (otrc-tr run_2) and the
agent repairs the bug but can never hand it in; (b) the loop to terminate, since ratio-0.11
summarization (ss b15k run_3) deletes the *completion* signal, not the *localization* signal.
Compression never produced a wrong patch here — it only broke the knowledge that it was done.
