# sympy__sympy-24213 — why compression-robust (Group D)

97 runs, resolve 0.99 (1 failure). Compression in only 20% of runs; median first edit step 12.
## 1. Task shape: one-line fix, fully specified by the PR text
PR gives a runnable repro AND the traceback with file+line (`unitsystem.py", line 179,
in _collect_factor_and_dimension`). So the search space is one function.
All 3 FC runs open exactly **2 source files** before the first edit: `unitsystem.py`
(full cat, step 2) and `dimensions.py` (full cat, step 6). The only non-PR fact needed is
the *name* of the helper: FC run_3 step 7 `grep -n "equivalent_dims" dimensions.py` → 428,
step 8 reads it (`deps1 == deps2`), step 9 reads unitsystem 165-185, step 10 edits.
Fix is re-derivable from PR + `unitsystem.py` + one grep. Edit is a 1-line sed on 1 file.
## 2. Environment: repro works, one trivial trap
Trap: `mpmath` missing → `import sympy` fails (FC run_3 step 3). Costs exactly 1 step
(`pip install mpmath -q`, step 4); every run hits and clears it the same way. After that the
PR repro runs verbatim and prints the exact PR error, so the agent has a cheap, deterministic
oracle. Secondary variance: pytest absent in the b15k container (TR run_1 step 20:
"No module named pytest") but present in the Sep-9 SS container (pytest-9.1.1). Did not matter
for the fix; it only lengthened the TR verification detour.
## 3. Compression before first edit — 1 run, clean and cheap
`di__b10k__trc-su/run_1` (comp step 14, 10035→4564 tok; `summarization_prompt_tokens: 0`, so
pure TRC, SU never engaged). Lost: all old tool outputs incl. the full `cat unitsystem.py`
(step 2) and `cat dimensions.py` (step 6). Kept: system + msg1 (PR text, N_PROTECTED=2) and
**all assistant reasoning** — step 14's own THOUGHT already states the conclusion verbatim:
"The DimensionSystem class has an `equivalent_dims` method... I need to use this method".
Recovery = 1 step: step 15 re-reads `sed -n '150,220p' unitsystem.py`, step 16 applies the
gold edit via a python string-replace. Never re-read the PR (it was never gone). Not a
restart — the plan survived in assistant turns, only the file bytes had to be re-fetched.
## 4. Edit correctness
First edit gold-equivalent in FC run_1/2/3 (steps 11/10/10), TRC+SU run (step 16), TR run
(step 14). All 6 submitting runs produce a patch **byte-identical to gold**
(`if not self.get_dimension_system().equivalent_dims(dim, addend_dim):`) — no alternative
fixes observed; the codebase hands you the one right helper.
TRC+SS run_1's step-14 `sed -i '177s/.../'` silently no-opped (wrong line number, rc=0, empty
output); step 15 re-read 173-185, saw the old text, step 16 redid it content-addressed. Verification is
always the PR repro (`Result: (-47.0000000000000, Dimension(acceleration*time))`) plus
`git diff`; several runs also ran the units test suite.
## 5. Failing run (1)
- `d05__b15k__ss/run_3` (silent_crash, 69+ steps, comps at 30 and 59, edit at 14, no submit):
  **not a wrong fix — the gold patch was on disk from step 14 and never reverted.** At step 30
  a 100-line pytest dump (all 72 tests PASS) pushed context to 16901; SS compressed to 1718 tok
  (~90% drop). Step 31 → format error (42 code blocks); step 32 the agent has amnesia about its
  own authorship: "The user is trying to run a test...". The remnant state literally reasons
  "the code... handles Add by checking `equivalent_dims`... The issue has already been fixed /
  there's a specific condition I'm not reproducing". It then spends steps 32-72 hunting a bug it
  had already fixed, and dies in a format-error loop with `info.submission` absent.
  Root cause: over-aggressive SS lost *edit authorship*, not *task knowledge*.
## 6. Verdict
Robust because the task's entire state is externally re-derivable and cheap to re-fetch: the PR
message (never compressible, N_PROTECTED=2) pins file+line+repro; the fix needs one identifier
(`equivalent_dims`) recoverable by one grep; the edit touches one line in one file; and the repro
script on disk is a deterministic pass/fail oracle that does not depend on context. Compression
therefore costs ~1 re-read step (TRC+SU run: comp@14 → edit@16) and never changes the answer.
Its limit is shown by the one failure: compression can't corrupt the *solution*, but it can erase
the fact that the solution was already applied. Once the agent no longer remembers editing, the
now-passing repro becomes evidence that "the bug doesn't exist", and the task flips from trivial
to unfalsifiable — a submission-side, not a fix-side, failure. TRC (keeps assistant turns, clears
only tool bodies) avoids this; aggressive whole-history summarization at a 90% ratio does not.
