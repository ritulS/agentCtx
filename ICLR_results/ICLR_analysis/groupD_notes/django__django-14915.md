# django__django-14915 — why compression-robust (Group D)

Step N = `agent.log` step N; token_log/brief steps are 0-indexed (log N = brief N-1).
97 runs, 95 resolved. Compression fired in 9 runs (8/9 resolved). 0 runs compressed before first edit.
## 1. Task shape: single-symbol, single-file, PR-sufficient
- PR names the class (`ModelChoiceIteratorValue`) AND the discriminating symptom ("`value in dict` → unhashable,
  `value in list` works") — a textbook `__hash__` diagnosis needing zero repo knowledge.
- FC run_1 step 1 `find /testbed -name "*.py" | xargs grep -l "ModelChoiceIteratorValue"` → exactly
  `django/forms/models.py`; steps 2-5 read only that file. **1 distinct source file opened before first edit.**
  All 3 FC runs open identically (grep → `cat models.py` → `grep -n class` → `sed -n '1161,1200p'`).
- Gold is re-derivable from PR + one file read: 3-line edit, one file, no cross-file coupling. Median first edit =
  step 10 vs median first compression = step 27 — the edit is ~17 steps upstream, so compression can only fire post-edit.
## 2. Environment: two traps, both non-blocking
- Trap A: bare `python` lacks asgiref. FC run_1 step 7 `ModuleNotFoundError: No module named 'asgiref'` → step 8
  `pip install asgiref -q` → step 9 repro prints `ERROR: unhashable type: 'ModelChoiceIteratorValue'`. Cost 2 steps
  (other runs used `pip install -e .`). Self-healable.
- Trap B: Django test-runner invocation. `pytest tests/...`, `python -m django test --settings=tests.settings`,
  `python runtests.py tests.model_forms...` all fail (no `tests/settings.py`); correct is
  `cd tests && python runtests.py model_forms.test_modelchoicefield`. FC run_3 burned steps 18-47 here, TR run_3
  steps 19-31. **Irrelevant to correctness**: a 6-line standalone repro (`ModelChoiceIteratorValue(1,None) in
  {1:[...]}`) fully verifies the fix. Runs that got the invocation right saw "Ran 23 tests ... OK".
## 3. Compression before first edit: none (0/97). Post-edit compression = free restart
- TR run_3 (b10k; comp at log steps 29/32/41/59/80, ratio ~0.50, 10.2k→4.8k ctx): after the step-32 truncation the
  agent literally restarts — step 32 THOUGHT *"Let me analyze the PR description first: The issue is about
  ModelChoiceIteratorValue not being hashable... Let me first find the relevant files"*. Re-runs the same `grep -r`,
  re-reads the class (33), and at step 34 concludes *"`ModelChoiceIteratorValue` already has a `__hash__` method
  defined at line 1174-1175"*; then `cat`s its own leftover `test_reproduce.py` and re-runs it (35) → "SUCCESS".
  Recovery = 4 steps; nothing from before the compression was needed.
- Mechanism: **all task state is externalised to the filesystem** — patched source, repro script, `git diff` all
  survive. Compression destroys the memory of having edited; it cannot destroy the edit.
- trc-ss run_3 (comp 24/25/29): TRC leaves `[TOOL OUTPUT CLEARED — N tokens — step k]` placeholders, msg1 kept.
  Step 27 `sed -n '1161,1180p'` → *"The fix is already in place"*; step 28 `git diff`; submit step 32.
- su-full run_3's injected summary is degenerate: `[COMPRESSED HISTORY SUMMARY] Let me run the tests without the
  -v flag ... [END SUMMARY]` — a truncated verbatim tail, i.e. near-total history loss. Agent recovered anyway.
- msg1 (PR text) survived under TR/TRC/SU in every compressed run, so re-localisation costs one grep.
## 4. Edit correctness: first edit already gold-equivalent everywhere
- Every run's first edit is the same `sed -i '117Xa\ ... def __hash__: return hash(self.value)'`; no run re-edited
  for semantic reasons (FC run_2 step 28 `sed -i '1174d'` was cosmetic blank-line cleanup).
- All 95 resolved submissions touch only `django/forms/models.py`, add ≤4 lines, and place `__hash__` **after**
  `__eq__` where gold places it **before** — semantically identical; FAIL_TO_PASS only asserts `hash(value)`. The
  fix is placement-invariant: a whole family of edits passes, so the agent cannot get it subtly wrong.
- Verification: standalone repro (fail→pass), then a 6-8 assertion `test_comprehensive.py` (set membership, hash/eq
  consistency, str/None/tuple values), then `git diff`.
## 5. Failing runs (2/97, both submission-protocol, neither caused by compression)
- `di__binf__fc/.../full-context/run_2`: fix correct on disk (step 33 `git diff` = exact gold hunk), but step 35
  submitted `echo COMPLETE... && cat django/forms/models.py | sed -n '1161,1180p'` → a **source listing, not a
  diff** → empty patch at eval.
- `d05__b15k__su-full/.../run_3` (submitted_unresolved): identical — step 76 `git diff` correct, step 77 submits
  `... && cat django/forms/models.py | grep -A 25 "class ModelChoiceIteratorValue"`.
- Only 2 of 97 `info.submission` values don't start with `diff`; one FC, one compressed → mode is orthogonal to
  compression. Both were long tails (35 / 77 steps) after heavy runner flailing. Contrast TR run_3 steps 86-88:
  same `cat patch.txt` miss, but it recovered via `git diff ... > patch.txt` and submitted a valid diff.
## 6. Verdict
Robust because the solution state is (a) fully recoverable from message 1 alone and (b) already externalised on
disk before any compression can fire. The PR is a self-contained spec: one grep localises the class, one read shows
`__eq__` with no `__hash__`, the fix is 3 lines in one file — first edit at step 10 vs first compression at step 27,
so 0/97 runs were compressed pre-edit. After compression the agent needs to remember nothing: it re-greps, re-reads,
finds its own `__hash__` already present and its repro script still on disk, converging in ~4 steps (TR run_3 32-35)
— a clean restart landing in the same place because the search is deterministic and the goal state idempotent. The
limit lies elsewhere: both failures were long low-information tails (30-70 steps fighting Django's test runner)
ending in a malformed submit that printed source instead of `git diff`. On tasks of this shape compression's real
risk is not losing the fix but lengthening the tail — extra steps in which the agent drifts off the msg1 protocol.
