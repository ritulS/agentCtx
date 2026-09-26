# sympy__sympy-16450 (posify drops is_finite) — Group D note
84 runs, resolve 0.95; compression in 60%; 11 runs compressed before first edit (resolve 0.73).

## 1. Task shape — single-site, self-locating
PR names the API (`posify`) and shows the exact symptom. Every run's step-1 command greps
`def posify` → `sympy/simplify/simplify.py`; the buggy line (`reps = {s: Dummy(s.name,
positive=True) ...}`, L254) is visible in the step-2 `grep -A 60 "def posify"`. FC opened 3 real
source files pre-edit (simplify.py, core/symbol.py, core/assumptions.py; r3 only 2) — only
simplify.py is load-bearing; the others are optional "what can Dummy take / what is the
assumption lattice" reading, each re-derivable in one command. Gold is re-derivable from PR
text + one grep; localization cost ~0.

## 2. Environment — one trivial, self-healing trap
`import sympy` → `ImportError: SymPy now depends on mpmath` (FC r1 step 3), fixed in one step
(`pip install mpmath -q`, step 4), never revisited. Then the repro is a 3-line `python -c` and is
fully verifying: PR transcript reproduces ("BUG CONFIRMED: finite assumption was lost!", FC r1
step 5) and the fix checks the same way (`xp.is_finite: True`). `pytest` is absent but
`python -c "from sympy.simplify.tests.test_simplify import test_posify; test_posify()"` works
(otrc-ss-partial r3 step 20). Environment cost is constant, not context-dependent.

## 3. Compression-before-edit runs — clean restarts that reconverge
- d05__b10k__ss r3 (comp @19: 10212→1817 tok, @36): all file reads wiped; recovery took 3 steps
  and needed nothing from before — step 21 re-ran `python -c "...x._assumptions"`, 22
  `grep -n "def posify"`, 23 `sed -n '202,280p'`. Edit @35, verified @36, resolved. The injected
  SS summary (trajectory msg[2]) is partly corrupted — it splices the prose line "I need to
  preserve other assumptions from the original symbol" *into* a quoted code block — and it did
  not matter, because the agent re-read ground truth off disk at step 38.
- di__b15k__trc r1 (comp @20,@41): TRC drops tool outputs; agent re-greps posify, edits @23.
  di__b10k__trc-ss r1: comp @19 fired on the same step as the edit; the plan lived in the
  assistant message so the edit went through; 2nd edit @22; resolved.
- `messages[1]` (`<pr_description>`) is preserved everywhere (msg1_wiped=False incl. all
  failures). Since the PR text alone re-specifies the task, compression = cheap restart.

## 4. Edit correctness — huge equivalence class, first edit usually already gold-equivalent
No two resolved runs submitted the same patch, none matched gold textually, all resolved: FC r1
filtered `s._assumptions` by exclusion list; FC r2 filtered `s.assumptions0`; FC r3 enumerated
`if s.is_finite/is_integer/...`; b15k-trc r1 enumerated 6 keys; ss r3 another exclusion list.
Gold is `**s.assumptions0`. Any patch forwarding surviving assumptions passes. First edit was
already gold-equivalent in FC r1/r2/r3 and tr r1 (step 11). Pre-submit ritual: re-run PR
transcript, run test_posify + test_noncommutative.test_posify, `git diff > patch.txt`.

## 5. Failing runs (4)
- di__b15k__otrc-ss-partial r3 (submitted_unresolved, **n_comp=0**): submit-protocol failure, not
  a fix failure. Step 24 ran `echo COMPLETE... && cat simplify.py | sed -n '250,255p'`, so preds/
  model_patch is a raw 6-line excerpt, not a diff; eval log shows `error_instances: 1`,
  `empty_patch_instances: 0` — patch never applied. On-disk edit (`Dummy(s.name, positive=True,
  finite=s.is_finite)`) did preserve finite. Compression uninvolved.
- d05__b10k__tr r1 (LimitsExceeded, 7 comps): gold-equivalent patch applied @11 (`s.assumptions0`,
  still in `git diff` near step 120) but never submitted — from ~step 33 it looped
  `git log --oneline --all -- simplify.py | head -5` 27× hunting an upstream fix, to 125.
- d05__b10k__tr r2 (LimitsExceeded, 8 comps): 120 steps re-reading the same regions
  (`sed -n '330,350p' core/symbol.py` 11×, `sed -n '202,300p' simplify.py` 3×); at step 122 it
  announces "Now I've confirmed the bug" — re-confirming step ~6. First edit @123; no room to submit.
- di__b10k__trc r2 (LimitsExceeded, 9 comps): working fix @29 (finite/infinite/integer/rational/
  prime/even/odd), then from step 54 looped `git log --oneline --all -p -- simplify.py | grep ...`
  20× to "check the official fix"; hit 125 with the fix on disk, unsubmitted.

## 6. Verdict
Robust because everything needed sits in the never-compressed first message and the rest lives on
disk one grep away: PR names the function, the function is 55 lines in one file, the repro is
three lines, and the accepted-fix set is enormous (five mutually different patches all resolved).
A compression event costs ~3 steps of re-grepping, not knowledge — a clean restart that
reconverges even when the injected summary is partly hallucinated (ss r3). The failures mark the
limit, and it is not about solving: all 4 had a working or near-working edit on disk. What
compression destroys is the record of *what the agent already did*, i.e. the stop-and-submit
decision: at b10k under TR/TRC the remnant is too small to hold "I already fixed and verified
this", so the agent re-enters the investigation loop (one command repeated 20-27×) and burns the
step limit. Compression-robustness here = solvability survives; run success is then gated by
termination discipline (and, in otrc-ss-partial r3, by emitting a real diff at submit time).
