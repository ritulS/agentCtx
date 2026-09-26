# django__django-12276 (Group D) — why compression-robust
87 runs, resolve 0.89 (77/87). Median first-edit 19, median first-compression 34.
## 1. Task shape: the PR text IS the localization
PR names it verbatim ("ClearableFileInput.use_required_attribute() should be moved to
FileInput.use_required_attribute()") + links widgets.py#L454; FC r3 step 2 restates the full
solution before touching the repo. One load-bearing file (django/forms/widgets.py); FC runs open
at most 1 extra source file (boundfield.py) + 3 widget templates, all optional. `grep -n
use_required_attribute widgets.py` (FC r3 step 4) + `sed -n '373,390p'` suffices — gold is
re-derivable from PR + one file read; localization is a constant, not an inference.
## 2. Environment: verifiable, two cheap traps
/testbed lacks pytz and asgiref (FC r3 steps 9,11) -> 1-2 steps (`pip install pytz`, `pip install
-e .`); then ImproperlyConfigured USE_I18N (step 13) -> settings.configure() (step 14); from step
15 a 5-line repro prints the `required` attr. Repro is local and cheap, so any restart can
re-verify. The repo suite never runs (runtests.py / `python -m django test` / pytest all fail) —
that is the sink that kills long runs (§5), but it is never needed.
## 3. Compression before first edit (4 runs, all resolved)
- trc-su b10k r2 (comp 19,31,37; edit 20): TRC wiped step 18's `sed -n '373,390p'` output; step
  19 re-issues the *identical* command, step 20 edits. Cost = 1 step. 9888->4270 tok.
- trc b10k r1 (comp 19,32,45; edit 26): TRC clears tool results only; the step-21 thought still
  carries the state ("FileInput is at line 373 ... ClearableFileInput ... line 454"). Steps 22-25
  = 4 redundant re-reads of 373-400, edit at 26.
- tr b10k r1 (comp 19,41; edit 30): truncation drops whole messages; steps 21-29 are nine
  narrowing re-reads + `grep -n "class FileInput"`, edit at 30. Priciest recovery; converges.
- su-full b10k r1 (comp 21, edit 21): summary carried a stale line number (step 24: "Line 470 ...
  in ClearableFileInput"); next `sed -n '465,485p'` showed Textarea, agent noticed ("The output
  doesn't show line 470"), re-grepped `class ClearableFileInput` -> 397, recovered by step 26.
Every recovery is "re-read one region of widgets.py", never "recover reasoning". msg1 (PR text)
survives in all resolved runs, so the goal is re-derivable after any wipe.
## 4. Edit correctness: huge equivalence class
First edit gold-equivalent in every resolved run inspected. Across 78 runs with a diff, 6 distinct
FileInput bodies were submitted and ALL resolve: `super().use_required_attribute(initial) and not
initial` (41), `not initial` (28), `not self.is_hidden and not initial` (4), `initial is None`
(1), + 4 that also gutted ClearableFileInput. 43/78 never removed the ClearableFileInput copy
(additive-only) and still resolve. Verification is always the agent's own settings.configure()
script, never the repo suite.
## 5. Failing runs (10) — none caused by lost context
- d05__b20k__tr r3 (silent_crash): agent.log ends with COMPLETE_TASK... printing the *exact gold
  patch*; trajectory.json exit_status='' submission='' -> harness recording failure.
- d05__b15k__tr r3 (submitted_unresolved): patch is gold modulo one retained blank line in
  ClearableFileInput -> grading/eval anomaly.
- d05__b20k__tr r1 (submitted_unresolved): protocol error; step 51 `echo COMPLETE... && cat
  widgets.py | sed -n '385,395p'` -> submission is raw source, not a diff. Edit itself correct.
- d05__b15k__ss-partial r3 (limits_exceeded, 0 compressions): `ls -la /testbed/tests/` (step 33)
  blew the output cap; model then emitted 0 actions and livelocked on "Expected exactly 1 action,
  found 0" to step 125. Correct edit (16,21) never submitted. Nothing to do with compression.
- 6 silent_crash (rc=-1, no exit_status, logs cut mid-output at steps 81-105): su-full b15k r3,
  su-partial b20k r3, trc b10k r3, otrc-tr r1, otrc-tr r2, otrc-su-partial r2. All had a correct
  FileInput edit on disk; all were burning steps hunting a way to run Django's suite. otrc-tr
  r1/r2 also had msg1 wiped and drifted off-goal ("Analysis complete: ClearableFileInput clear
  checkbox is correctly implemented" / "This is intentional behavior") instead of submitting;
  otrc-su-partial r2 even weakened ClearableFileInput (`sed -i '462s/ and not initial//'`).
## 6. Verdict
Robust because the task state is a pointer, not a history: the PR names file, class and method, so
all compression can destroy is the cached text of a ~20-line window of widgets.py plus some line
numbers — regenerable by one `sed -n`/`grep -n` for 1-11 steps. The edit is a 2-line insertion
verified by a self-written script needing no repo test infra, and the acceptance basin is wide (6
implementations, additive or move, all pass), so a post-compression clean restart re-derives an
*accepted* fix instead of having to reproduce the earlier one. Limits: robustness is bought by
msg1 surviving (OTRC wiped it in both otrc-tr runs -> drift, no submission) and by the agent
preferring its own repro to the repo suite (every long/killed run was chasing runtests.py). 7/10
failures are infra or grading artifacts, 1 a submission-format slip, 1 a zero-compression livelock.
