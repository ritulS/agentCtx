# django__django-12143 — why compression-robust (Group D)
99 runs, resolve 0.86. **97/99 runs submitted the byte-identical patch** (md5 a5ef69ae, 715 B)
— the gold-equivalent one-token change. Only 2 submissions differ at all.
## 1. Task shape: the PR description *is* the patch
PR names the file (`admin/options.py`), quotes the buggy line verbatim, gives the line number
(L1634 via the GitHub link), and states the fix ("use `re.escape()`").
- Distinct source files opened before first edit, all 3 FC runs: **1** (`django/contrib/admin/
  options.py`). FC run_1: step 2 `find ... options.py`, step 3 `sed -n '1620,1650p'`, step 4
  already states the complete fix. Re-derivable from **PR text + one 10-line read**; no callers,
  no tests, no second file. Gold's 3-line reformat is cosmetic.
- Median first edit step 7, median steps 26 — ~20 of those steps are post-fix.
## 2. Environment: in-container verification is impossible, and irrelevant
- `import django` → `ModuleNotFoundError: No module named 'pytz'` (FC run_1 step 13); `asgiref`
  also missing; no `tests.settings`; `runtests.py` lives in `/testbed/tests/`, not `/testbed/`.
- The FAIL_TO_PASS test isn't in the repo yet — agents guess class names and get `No module
  named 'admin_changelist.ListEditableViewsTests'` (di__b15k__trc r1 step 34). **No run ever
  executed the real test.**
- Trap fully absorbed: the fix is checkable by a pure-`re` simulation. Every run writes a
  stdlib-only script re-implementing both patterns and confirms `form-1.2.3` no longer matches
  `form-1X2Y3-1-id` (FC run_1 step 14, PASS). Sound proxy → verification never blocks.
## 3. Compression never touches the load-bearing phase
Only **17/99 runs compressed at all**; earliest event step 15; **0** compressions before first
edit. Every event lands in the post-fix "try to run the real suite" flail.
- msg1 (PR description) is protected: `msg1_wiped=False` in all 99 runs — the full spec survives
  TR/TRC/SU/SS alike.
- Durable state is on disk (line 1634 + `git diff`); recovery = one re-read. d05__b10k__tr r3:
  comp@25 → step 25 continues the test-runner hunt unfazed; comp@48 → step 48 opens "The fix has
  been applied correctly" and re-verifies via `sed -n '1634p'`. Resolved.
- SU summaries are lossy *and garbled* without harm: d05__b10k__su-full r2 comp@32 injects a
  `[COMPRESSED HISTORY SUMMARY]` whose embedded tool output is spliced mid-line ("`for key,
  value in no other similar patterns...`"), yet its prose restates the exact fixed line and the
  agent's very next action is `sed -n '1628,1640p'` — ground truth from disk. Clean restart.
## 4. Edit correctness
First *successful* edit is always gold-equivalent; friction is sed quoting, not logic. FC run_1:
step 9 `sed -i 's/pk_pattern = .../'` returns rc=0 but changes nothing; step 10 re-read shows the
old line; step 11 line-addressed `sed -i '1634s/...'` works; step 12 confirms. Same 2-3 step
self-correction in FC run_3 (edits 8,11,12) and b10k tr r3 — read-back-after-edit is what makes
silent sed failures survivable. One semantically different fix also resolves: di__b15k__trc-ss r3
escapes both args (`re.escape(self.model._meta.pk.name)` too), a no-op on identifier pk names.
## 5. Failing runs (14): 13 label artifacts + 1 real error
- **13 × silent_crash** (b10k su-full r1/r2, b10k tr r1/r2, b20k ss r1/r2, b20k su-full r1/r2,
  b20k tr r2, b10k trc r1/r2, b20k trc r1/r2): **eval/aggregation dropout** — each
  `trajectory.json` has `exit_status='Submitted'` + the canonical a5ef69ae patch, but the
  outcomes CSV row has empty `exit_status`/`step_count`/`patch_generated`. Not agent failures.
- **1 × submitted_unresolved** (d05__b20k__su-full r3, 30 steps, n_comp=0): submission is
  byte-identical (a5ef69ae) to resolved FC runs → **eval anomaly**, not a wrong fix.
- **1 genuine failure**, di__b10k__trc r2 (also mislabeled silent_crash): fix correct on disk,
  but step 38 submitted `echo COMPLETE... && cat options.py | sed -n '1630,1640p'` — patch.txt
  never created, so the submission is raw file text (570 B), not a diff. Submit-protocol slip; it
  had printed a correct `git diff` at step 36, so nothing was missing from context (comp fired 17
  steps earlier, at 21).
## 6. Verdict
Everything needed sits in the never-wiped first user message plus one file read, and the only
state that matters lives on disk, not in context. A single-token edit at a line number the PR
hands over puts the container in a correct state by step ~7-9, long before any budget can be
exceeded (earliest compression step 15). What compression deletes is a post-fix verification
phase *guaranteed to fail anyway* (broken env, test not yet in repo) — losing it is a pure win,
and re-entry costs one idempotent command (`sed -n '1634p'`, `git diff`) that every primitive
leaves available. The limits shown are not about context: the sole real failure is a submit-format
slip. Against Group C the discriminators are (a) spec completeness, (b) disk-recoverable one-line
state, (c) a sound context-free verification proxy, (d) first edit landing long before the first
compression event.
