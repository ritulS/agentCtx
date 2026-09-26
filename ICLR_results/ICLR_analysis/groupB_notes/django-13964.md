# Group B: django__django-13964 — why FC fails but a few compression policies succeed

Scope: `ICLR_results/swebench/main/devstral24b` only (Devstral-Small-24B, 13
cells x 3 runs = 39 runs, budget 21k, step limit 125). Group B label: FC
resolves 1/3; only su-partial reaches a majority (2/3); su-full and trc-ss get
1/3 each; the other 9 compression cells get 0/3. Evidence: `agent.log` (full
step history), `trajectory.json` (submission), `token_log.json`, the gold
patch / FAIL_TO_PASS / PASS_TO_PASS from SWE-bench Verified, and the Django
source at the base commit (fetched from GitHub to check test semantics; docker
is not accessible from this account so nothing was re-evaluated).

## 0. Headline

**The outcome is determined by which of three fix hypotheses the agent
commits to, not by compression.** The patch family predicts resolve almost
perfectly, in every model:

| patch family (submitted diff) | devstral24b | qwen35b | glm47flash |
|---|---|---|---|
| "empty" — `in field.empty_values` / `is None or == ""` / `not getattr(...)` in `base.py` | **5/5 resolved** | 26/26 | 1/1 (with descriptor change) |
| "resync" — `elif getattr(self, field.attname) != obj.pk` (or bare `else:`) in `base.py` | 0/15 | 1/11 (the 1 uses `target_field.attname`, not `obj.pk`) | 0/1 |
| "descriptor" — guard `ForwardManyToOneDescriptor.__set__` in `related_descriptors.py` | 0/6 (+0/3 combined with an "empty" base.py edit) | – | 0/6 |
| no submission (LimitsExceeded) | 10 | 35 | 31 |

Devstral chooses "empty" in 5 of 30 submissions (17%); Qwen chooses it in
26 of 38 (68%). That difference is why this task is Group B for Devstral and
trivially solved for Qwen. With 3 runs per cell and a ~17% per-run hit rate,
FC at 1/3 and su-partial at 2/3 are the same coin: the N=1 label is sampling
noise on a narrow-basin task, not a compression effect.

## 1. Why only the "empty" family passes (verified against test source)

Gold fix (one line, `django/db/models/base.py` `_prepare_related_fields_for_save`):
`elif getattr(self, field.attname) is None:` → `elif ... in field.empty_values:`.
FAIL_TO_PASS is a single test (`test_save_fk_after_parent_with_non_numeric_pk_set_on_child`);
PASS_TO_PASS is the 36 existing `many_to_one` tests, two of which involve a
`to_field` FK (`ToFieldChild.parent -> Parent.name`):

- **resync (`!= obj.pk`)**: for `ToFieldChild(parent=Parent(name='jeff'))` the
  attname holds `'jeff'`; after `parent.save()`, `obj.pk` is the integer id,
  so `'jeff' != 1` fires and `parent_id` is overwritten with the integer.
  Breaks `test_save_nullable_fk_after_parent_with_to_field` (asserts
  `child.parent_id == parent.name`) and
  `test_cached_foreign_key_with_to_field_not_cleared_by_save` (the cache is
  deleted, `assertNumQueries(0)` fails). The one Qwen resync patch that
  resolved used `getattr(obj, field.target_field.attname)` instead of
  `obj.pk`, confirming the mechanism.
- **descriptor (skip attname when `value._state.adding` / `value.pk is None`)**:
  the F2P test passes, but `ToFieldChild(parent=Parent(name='jeff'))` now leaves
  `parent_id = None`; at save time the untouched `is None` branch assigns
  `obj.pk` (integer id) instead of `parent.name`. Same P2P test breaks. This is
  exactly what tr/run_1 saw at step 83 ("ERROR:
  test_save_nullable_fk_after_parent_with_to_field") and diagnosed at step 93
  ("We're setting `child.parent_id` to 1, but the foreign key is to the `name`
  field, so it should be 'jeff'") — then thrashed for 30 steps and never
  submitted.
- The three "empty + descriptor" runs carry a correct base.py edit but the
  descriptor edit on top breaks the same test; none tested base.py alone.

## 2. The decision is made early and without the discriminating test

Across all 39 runs:

- **Diagnosis is not the problem.** 36/39 runs reproduced the bug in their
  own sqlite script within ~15 steps and explicitly observed `product_id ==
  ''`. In the 14 resync runs, 13 said "empty string"; three got within one
  sentence of the gold fix and then implemented the other half (tr/run_2
  step 43: "check if the foreign key field is either None or an empty string,
  and if the related object's primary key is different from the current
  value" → code keeps only `!= obj.pk`). No run considered and rejected
  `empty_values` on the merits; the slide from "is empty" to "differs from pk"
  went unnoticed.
- **The descriptor family is chosen before base.py is read.** All 6
  descriptor-only runs fixed on `__set__` by step 20-26; two of them later
  read `_prepare_related_fields_for_save` and dismissed it ("only runs during
  save()", ss-partial/run_3 step 23, trc/run_2 step 30). FC run_2 and run_3
  never reached that function at all (0 mentions in run_2's log).
- **Only 1 of 39 runs ever ran `tests/runtests.py many_to_one`** (tr/run_1,
  which saw the failure and then lost track of its own disk state). The rest
  either never attempted a suite, or tried `pytest` (not installed) /
  `python -m django test` (no settings) / `runtests.py` from the wrong cwd,
  failed 1-10 times, and fell back to a hand-written single-scenario repro.
  Two runs ran `model_fields` and saw green, which does not cover the
  to_field save path. Every pre-submit THOUGHT asserts minimality of the
  diff; none asserts non-regression.
- **Timing vs compression.** In the 10 threshold-compressed resync runs the
  wrong edit precedes the first compression in 8; in the 6 descriptor runs
  the decision precedes compression in all 6 (decision steps 20-26 vs
  compression at 34-54). In the 4 resolved compressed runs the empty-string
  diagnosis, the edit and the repro re-check all precede compression too
  (su-partial r1: diagnosis 31, edit 49, comp 52; su-partial r2: 44/51/63;
  trc-ss r2: 23/39/50; su-full r3: diagnosis 70, comp 71, edit 77). Compression
  neither caused the wrong choice nor produced the right one; it only had to
  avoid destroying a conclusion already reached, and every primitive did.

## 3. What FC actually did (1/3)

- run_1 (resolved, 84 steps): reached `_prepare_related_fields_for_save` at
  step 20, diagnosed "it's an empty string!" at 22, then grepped
  `Field.empty_values` and `validators.EMPTY_VALUES` (steps 29-32) and shipped
  `in field.target_field.empty_values`. Lost 20 steps to `patch`/`sed`
  mechanics. Never ran the suite.
- run_2 (descriptor, unresolved, 79 steps): localised exclusively in
  `related.py`/`related_descriptors.py`, committed to the descriptor at
  step 25, discovered `value.pk == ''` at 41 and fixed the guard rather than
  moving to base.py. Its own script showed the regression at step 60
  ("Unsaved parent test FAIL: Child matching query does not exist") and it
  dismissed it at 63/67 as a test-construction problem.
- run_3 (LimitsExceeded): three hypotheses in `related.py`
  (`get_db_prep_value`, two `pre_save` variants), ~28 steps of sed-repair
  ping-pong, `git checkout` of all work at step 115, then a 7-step
  sed-quoting loop until the limit. Never opened
  `_prepare_related_fields_for_save`.

FC's unlimited context did not help because nothing needed to be retained:
the whole problem is a 1-line edit whose correctness hinges on a P2P test the
agent never runs. FC's failures are the same hypothesis-choice and
verification failures as the compressed runs.

## 4. Why the compressed cells look different from each other

- **su-partial 2/3, su-full 1/3, trc-ss 1/3**: each success is a run that
  happened to pick "empty" before compression. su-full/run_3's step-71
  summary ("change the condition ... from checking `is None` to checking for
  falsy values") is the only case where the summary shaped the patch wording
  (`not getattr(...)`, still passing) and flagged a stale `_save_table` hunk
  for cleanup; its step-42 compression cost ~25 steps re-entering a dead end.
- **9 cells at 0/3**: 21 submissions in the resync/descriptor families plus
  9 LimitsExceeded. Of the LimitsExceeded runs, ss/run_1 had the
  gold-equivalent `is None or == ""` on disk from step 44 to the end and spent
  steps 114-125 debugging its own flaky test script instead of submitting.
- **OTRC cells (otrc-tr / otrc-ss-partial / otrc-su-partial / binf-otrc)**:
  5 of 12 runs have `messages[1]` (the PR description + submission protocol,
  1591 tok) replaced by `[tool-result cleared — online-trc — 1591 tok — step 0]`
  — the same positional-overwrite harness bug documented for qwen35b in
  `groupC_notes/_label_note.md`. All 5 hit LimitsExceeded with total topic
  drift (Decimal handling, mysql features, an invented `get_db_prep_value`
  fix) and invented submission rituals (`echo "SUBMIT: ..."` x49). The 7
  non-wiped OTRC runs behave like the threshold cells (3 resync submissions,
  2 descriptor, 2 LimitsExceeded). So OTRC's 0/12 here is half harness bug,
  half the same hypothesis lottery.

## 5. Takeaways for the paper

1. django-13964 is a **narrow-acceptance-basin** task with a **strong wrong
   prior**: the PR literally says the parent "does not see the primary key's
   change", which invites "resync when it differs" and "don't copy an unsaved
   pk", both of which break `to_field` FKs. Only the framing "'' is an empty
   value like None" passes, and Devstral reaches it ~17% of the time regardless
   of context policy.
2. The Group B label (N=1) for this task is **not evidence that su-partial
   preserves something FC loses**. With a 17% per-run hit rate and 3 runs per
   cell, the expected spread between cells is exactly what is observed.
3. The one structural factor that would move the number is **verification
   against the existing test module**, which 38/39 runs skipped because the
   sandbox test-runner invocation kept failing. That is an agent-scaffold
   property, orthogonal to compression.
4. The OTRC message-1 wipe bug affects Devstral too (5/12 runs on this task)
   and should be excluded or corrected before any OTRC-vs-FC comparison on
   this model.
