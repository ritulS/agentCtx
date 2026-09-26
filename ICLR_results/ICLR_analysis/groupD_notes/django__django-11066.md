# django__django-11066 — why compression-robust (Group D)
103/103 Submitted, 103/103 resolved. Every submission is a byte-identical 1-file
1-hunk diff == gold (`content_type.save(using=db, update_fields={'model'})`).
Compression fired in only 1/103 runs (2 events), never before an edit. Peak
context med 4.7k tok (max 14.8k) vs budgets 10k/15k/20k; median run 9 steps.
## 1. Task shape — the PR description *is* the patch
Problem statement gives file path, line number and the literal before/after
("should be `content_type.save(using=db, update_fields={'model'})`"). FC run_1:
step1 `find ...contenttypes/management/__init__.py`, step2 `cat` it, step3
`sed -i` the fix. **One source file opened before first edit in all 3 FC runs**;
run_3 step1 states the fix verbatim before any tool call. Gold is fully
re-derivable from the PR text alone — the file read is confirmation, not search.
First-edit step across 103 runs: 2(x4), 3(x57), 4(x25), 5(x7), 6(x3), 7(x2),
other-form(5) — median 3, max 7.
## 2. Environment — verification is impossible, and irrelevant
FAIL_TO_PASS `test_existing_content_type_rename_other_database` does **not exist**
pre-patch (test_operations.py has only `_rename`, `_rename_ignore`,
`_rename_conflict`), so the decisive test is unrunnable by construction. Runner
also trapped: `python -m django test --settings=tests.settings` →
`ModuleNotFoundError: pytz` (TRC run_2 step7); after `pip install pytz` → `No
module named 'tests.settings'` (step8); `python tests/runtests.py tests.content
types_tests.test_operations` → `ValueError: Available apps isn't a subset of
installed apps, extra apps: contenttypes_tests` / `Ran 0 tests` (otrc-su-partial
b15k run_2 step21). No run found the correct `cd /testbed/tests && python
runtests.py contenttypes_tests...`. The trap cost steps (26- and 50-step runs)
but never the outcome — the edit was already on disk. FC run_2 dodged it with a
fake "test" (step4) that regex-greps the source for `using=db`; run_1/run_3
verify by `cat` + `git diff` only.
## 3. Compression-before-edit — 0 runs
Median first-compression step 11 vs median first-edit step 3; 102/103 runs finish
without hitting the budget. The compression window opens ~8 steps after the patch
is already written.
## 4. The one compressed run: di__b10k__trc run_2 (26 steps, comp @11, @20)
Edit at step3; steps 5–11 burned on the runner trap. Comp@11 (11.3k→6.2k) wipes
all tool outputs. Step12 is a **clean cold restart** — "Let me start by
understanding the issue. According to the PR description..." → re-`cat`s the
file. Step13: "the issue ... has already been fixed ... shows
`content_type.save(using=db, ...)`" — it recovers its own work from the
*filesystem*, not context; `git status` confirms. Steps 14–23 idle due-diligence
(other `.save(` in `contenttypes/fields.py`, `0002_remove_content_type_name.py`,
both correctly ruled out at steps 20–21). Comp@20 (10.0k→4.6k) changes nothing;
step24 `git diff`, submit 25/26. Nothing pre-compression was needed: the task
description survives TRC and the patch lives on disk.
## 5. Edit correctness / 6. Failures
First edit == gold in every run; no run made a second or alternative edit; all
103 submissions identical, so no evidence of multiple valid fixes. Pre-submit
verification is always `cat`/`git diff` self-inspection, never a real test.
Failing runs: none (0/103).
## Verdict
The whole solution is carried by the *immutable* part of the context and executed
before budget pressure exists: the PR description is a literal spec of a one-token
diff, so zero accumulated state is needed — location is one `find`, the fix is
quoted in the prompt, the edit lands at step 3 of a 9-step run, ~8 steps before
the earliest possible compression at 10k. Once executed the result is persisted
in the *environment*, which no primitive can touch; TRC run_2 steps 12–13 show
compression's worst case (total history amnesia) degrading into a harmless
re-derivation that converges on the already-correct disk state. Limit: the
robustness comes from the task being verification-free. The environment is in
fact hostile (FAIL_TO_PASS absent pre-patch, runner broken), so a variant that
*required* iterating on test feedback would have to carry long tool-output
history across compressions and would look like Group C. Here the trap only
inflates steps and token cost, never correctness.
