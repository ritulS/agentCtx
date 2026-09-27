# Group C (Devstral-24B): why FC solves these tasks but compression does not

Scope: `ICLR_experiments/swebench/main/devstral24b` only (Devstral-Small-2-24B, 13
main cells: FC at unlimited budget, 11 threshold/online policies at 21k, OTRC
at unlimited). Group C = 9 tasks resolved by FC (>= 2/3) but resolved <= 1/3
in N >= 6 of the 12 compression cells. Evidence: `agent.log` (full step
history; `trajectory.json` keeps only the post-compression remnant),
`token_log.json` (`compression_event_steps`, `online_trc_clears`), gold
patch / FAIL_TO_PASS from SWE-bench Verified, eval logs where present, and
`analysis/outcomes/swebench_outcomes.csv`. One investigation agent per task
(notes in `ICLR_experiments/ICLR_analysis/groupC_devstral_notes/`); cross-task numbers computed
directly (`scratchpad/crosstask.py`).

## 0. Headline

Devstral's FC baseline is *worse* than every compressed cell on P100
(FC 55.7% vs 62-69%), so Group C runs against the grain. These 9 tasks are
not context-hungry: FC peak context median 32.9k vs 29.7k for P100. What
they share is (a) a small fix (1-6 lines, one file, except 25232's 5 hunks)
that hinges on a code fact read early and needed late, (b) a plausible
wrong fix invited by the PR text, traceback, hints or the repo's own tests,
and (c) an environment in which the real test cannot be run, so the only
correction channel is what the agent still holds in context at edit/submit
time.

Timing is the mechanism's substrate: at 21k the first compression event
fires at median step 50 (p10 36, p90 71) while the first edit is at median
step 11 (p90 17) and FC submits at median step 65. Every compressed run is
therefore compressed in the window "edit applied, not yet submitted", and
what gets dropped is exactly:

1. **Edit ledger / completion state** - "the fix is already on disk and
   verified" (failing runs run `git diff` 1.4x vs 2.0x for resolving runs;
   many never run it).
2. **Provenance of speculative edits and env hacks** - which hunks are the
   fix and which are scaffolding.
3. **A template or co-visible pair read early** - `transform()`'s guard
   (10908), L893+L931 in one window (14053), `"no_validation"` in `_base.py`
   (25232), the `_op_priority` three-hop chain (13757), `_build_repr` +
   both `__init__`s (14983), the `X = self._validate_data(...)` rebinding
   (25931).
4. **Negative evidence** - "the build always fails here", "my mock printed
   `<RepeatedKFold object at ...>`", "this sed pattern never matched".

Summaries (SU/SS) additionally *rewrite* the state: an unverified edit
becomes "fix applied successfully", the agent's own wrong hypothesis
("inherits BaseCrossValidator", "no parent_link must raise") becomes an
established requirement, and a broken file view is rendered as clean.

A large, non-mechanistic term is the **OTRC harness bug**: in devstral main
230/1200 OTRC runs (19%) have `messages[1]` (PR text + submit protocol)
overwritten by `[tool-result cleared — online-trc ...]`; 0/230 resolved. In
Group C this hits 22/108 OTRC runs (14053: 9/12, 10908: 7/12). Even
excluding them, non-wiped OTRC runs on Group C resolve 21% vs 45-55% for
threshold policies.

## 1. Environment traps are the common substrate (9/9 tasks)

| task | env trap | consequence |
|---|---|---|
| sklearn-10908, 14053, 14983, 25232, 25931 | `python` = miniconda base 3.11; in-tree `.so` are cpython-36/39; 0/39 runs per task find `envs/testbed`; `build_ext` fails on Cython/numpy 2.x; no pytest | **no run ever executes the modified code**; all "verification" is mock scripts / grep / ast; `pip install scikit-learn` (1.9) gives false PASS on 25232, 14053, false "method missing" on 10908 |
| sympy-13757, 14531 | base 3.11 cannot import sympy 1.1 (`collections.Mapping`, mpmath missing); eval uses 3.9 | 5-45 step compat detour before investigation (median ~9 / ~44 steps); partial compat edits are eval poison (14531: 3 submissions fail 4 P2P via DeprecationWarning-as-error) |
| django-12325, 17084 | no `asgiref`/`sqlparse`/pytest; `runtests.py` needs `PYTHONPATH` or `pip install -e .` | only 3/39 (12325) and 8/39 (17084) runs ever got a real test run; ad-hoc scripts need 4-8 attempts; the repo's own `test_missing_parent_link` encodes the behavior the gold patch removes |

## 2. Per-task summary

| task (FC) | gold fix | wrong prior | compressed resolve (excl. wiped) | dominant failure of compressed runs |
|---|---|---|---|---|
| django-12325 (2/3) | base.py: only `parent_link=True` O2Os enter `parent_links`; drop the raise in options.py | "prefer parent_link, else first O2O" (keeps old raise; hints + repo test) | 5/34 | Variant is a coin-flip at first edit, pre-compression in 12/16 fallback runs (strict 7/7 resolved, fallback 0/17, options-only 0/7). SS/SU summaries freeze "no parent_link must raise" as a satisfied requirement (ss r1, ss-partial r3, su-full r3); SS/SU-full restart exploration from scratch after each summary (ss r2 s59/s108, ss r3 s50, su-full r1 s50). tr r3 has the gold edit on disk from s106 and spends 111-125 satisfying its own raise-expecting test. |
| django-17084 (2/3) | wrap in subquery when a referenced annotation `contains_over_clause` (or drop `Window.contains_aggregate=False`) | mirror the neighbouring check and `raise FieldError` (turns DB error into Django error; hidden test needs the query to RUN) | 6/36 | Reject-class is a Devstral prior (FC r3 too; 12/18 reject runs chose it pre-compression) -> 13/14 wrong submissions. On the allow path compression converts successes into step-limit: 4 runs had a test-passing fix in tree (ss r2, otrc-ss-partial r3, otrc r3, otrc-tr r1) and never diffed; ss r3 summary asserts "preserving valid use cases" right after s105-106 showed `NotImplementedError`; trc-su r2 reaches the gold condition at s93-96, compression fires AT s96, s97-113 re-test the old reject patch. OTRC: 79x and 47x identical commands. |
| sklearn-10908 (3/3) | in `get_feature_names` copy `transform()`'s `if not hasattr(self,'vocabulary_'): self._validate_vocabulary()` | conditional guard / rewrite `_check_vocabulary` / `NotFittedError` (never set `fixed_vocabulary_`) | 15/29 | Guard visible at first edit -> 16/16 correct (3 FC + 13 compressed); not visible -> 3/16. In 10/13 misses the agent never read `transform()` (exploration variance, pre-compression); OTRC's 5-step window guarantees loss (otrc-su-partial r3: read s15, edit s29; otrc-tr r1 re-implements vocab parsing 11 times). ss r2 restarts exploration after each of 3 summaries. 7 runs = harness bug. |
| sklearn-14053 (3/3) | keep per-node `feature_names_` list, guard `-2` (or per-feature list + `[tree_.feature[node]]`; the two sites must agree) | swap L931 only ("list is per-feature") | 16/27 | FC applies both sites in adjacent steps right after one window showing L893+L931 (s22/23, s31/32, s24/25). Compressed S-only runs (ss-partial r2, su-full r3, trc r1) state the same false model; summary promotes "bug fixed at line 931" to fact; 0 post-compression views of L893. ss r1 summary says "fix applied" after s37 `git show HEAD:` restore. ss r2 replays wrong sed anchors after `git checkout`. 9 runs = harness bug. |
| sklearn-14983 (2/3) | `__repr__ -> _build_repr` AND `_build_repr` falls back to `cvargs` | `__repr__` only / inherit `BaseCrossValidator` (both print `n_splits=None`); hand-rolled repr in PR order (wrong sort) | 3/36 | Requires a faithful simulation of `_build_repr` against the real `__init__`s (3 regions co-visible; FC r1 s24-29) or a copied-code test printing `n_splits=None` (FC r2 s32). All 3 compressed successes saw `n_splits=None` before their first compression; 16/19 failing offline runs ran an attribute-based mock after compression (only 5 re-read `_build_repr`). Summaries record "core issue resolved". TRC clears the s7 `class _RepeatedSplits(metaclass=ABCMeta)` read -> trc-su r2 dismisses its own mock's `<RepeatedKFold object at ...>` (s47-48). OTRC r1: 26x `sed -i '1117,1118d'` deleting 2 lines per cycle. Base-rate term is large: FC r3 and the 2 zero-compression runs fail identically. |
| sklearn-25232 (3/3) | 5 hunks; `"fill_value": "no_validation"` constraint (or omit) | invented constraint strings `"numeric"`/`"string"` (ValueError at fit), `super().__init__(fill_value=)`, validation before attrs | 16/36 | Constraint idiom lives only in `_base.py` read at s3-7: 0/16 resolved runs invented a string, 5/11 failing submissions did (never viewed it, or OTRC cleared it: otrc-tr r2 seen s6 written s29). Edits after first compression: resolved median 0.5, failing median 7.5. Restore/reapply loops (4-10 restores) repeat non-matching seds after each event (tr r3: s21,30,41 then s96,99,101,106,109). 3 limit runs had a correct patch on disk (tr r1@110, trc r3@101, otrc-su-partial r1@104) and destroyed it. su-full r1 summary hides that s42 deleted `X_filled`; diff at s76 shows `-X_filled`, submitted anyway. |
| sklearn-25931 (3/3) | `_score_samples` without validation, called from `fit` | `.values`/`np.asarray` no-op; re-validate with `reset=False` (that IS the warning); drop the minus sign | 20/33 | Three facts must co-exist: L291 rebinding, L440 minus sign, `_validate_data(reset=False)` is the warning. FC r3 dropped the sign at s38 and caught it at s53 ("But wait, let me double-check") because the reads were still in context. 5/6 wrong non-OTRC edits pre-date compression; the summary then converts them into "fix applied successfully" (ss r1: s49 "Good! My fix is already applied" while the grep shows the minus line at 440) and the agent stops re-deriving. su-partial r1 summary garbles the ndarray fact -> re-inserts the warning call. otrc r1 / ss r3: correct fix on disk, 60-70 steps of re-doing failed builds, 0 submit. 3 runs = harness bug; 1 = model degeneration crash. |
| sympy-13757 (2/3) | `Poly._op_priority = 10.001` | edit `Poly.__rmul__` (dead code), `>`->`>=` in decorator, delegate in `Expr.__mul__` | 22/35 | Three-hop chain (`Expr.__mul__` -> `call_highest_priority` -> equal priorities) must be co-visible; 5/7 runs that never saw `_op_priority` are online-cleared. TRC erases edit state (trc r1 s72 re-inserts the line while THOUGHT says "revert"; 30 steps to recover) and the "these hunks are speculative" evidence (trc r3, otrc r3 ship the gold line plus a fatal extra hunk -> `NameError`/`AttributeError` in P2P). ss-partial r3 summary freezes "debug why the modified decorator is not working" -> 7 more decorator rewrites. Threshold policies still 19/24 because the edit usually precedes the event. |
| sympy-14531 (2/3) | `self._print(expr.lhs/rhs)` in `_print_Relational` charmap branch; `_print_Limit` | wrap the non-charmap `parenthesize(...)` too (double-print); audit every `%s` in str.py; submit env hacks | 17/36 | 10/15 limit runs end with the correct two-line fix on disk and 12/15 never ran `git diff`; last 30 steps are audits of irrelevant methods. SS/SU-full restart from scratch (ss r3 s67 and s118 `ls -la` after a correct patch.txt at s116); su-full r1 summary's "What Remains" list drives 30 steps of extra-method audit. TR loses edit state -> `git checkout` wipes the fix (tr r3 s97), 2 steps short at s125. 3 submissions include the collections.abc hacks (su-partial r3 summary lists core files as "modified" without marking them as hacks) -> 4 P2P fail. OTRC: `_print_Eq` hypothesis persists 60+ steps; 19x identical grep. |

## 3. Cross-task mechanisms (ranked by how many tasks they explain)

1. **The wrong variant is usually chosen before compression; compression
   removes the late correction.** 12325 12/16, 17084 12/18, 10908 8/9,
   14053 7/10, 25931 5/6, 25232 (invented constraint at s16-28 vs comp
   38-57): the decisive wrong edit predates the first event. FC has the same
   prior (FC failures: 12325 r1 options-only, 17084 r3 reject, 14983 r3
   inherit-only, 13757 r2 `__rmul__`), so FC's 2/3-3/3 includes luck. What FC
   uniquely keeps is the raw read that lets a "But wait" step fire (25931 FC
   r3 s53-57; 12325 FC r2 s37-41 debug trace; 14053 both-site window).
2. **Summaries promote hypotheses and unverified edits to facts.** "Fix has
   been applied successfully" (25931 ss r1, 14053 ss-partial r2 / su-full
   r3, 14983 ss r1 / su-partial r1, 25232 su-full r1/r2), "correctly raises
   ImproperlyConfigured" listed under passing tests (12325 ss r1, ss-partial
   r3), "inherits BaseCrossValidator" (14983 ss r3), "preserving valid use
   cases" one step after a NotImplementedError (17084 ss r3), "Files
   Modified: None" after real sed edits (25232 ss-partial r1, 14983
   su-partial r1), broken docstrings rendered as clean `"""` (10908
   su-partial r2/r3). After such a summary no run re-derived the decision;
   the remaining 15-30 steps are verification theatre (mocks, grep, ast).
3. **Completion state and provenance are lost -> correct fix never
   submitted, or submitted with poison.** Correct fix on disk at the step
   limit with no submission: 14531 10/15, 17084 4, 25232 3, 25931 2, 13757
   2 (+2 shipped with a fatal extra hunk), 12325 1 (tr r3). Failing runs
   run `git diff` 1.4x on average vs 2.0x for resolving runs; 12/15 (14531),
   12/17-ish (17084) never run it. Env-hack provenance lost: 14531 3
   submissions include core-file compat edits (4 P2P fail); 13757 trc r3 /
   otrc r3 keep a speculative global sed alongside the gold line.
4. **Full-summary restart (SS / SU-full only).** Immediately after the
   summary the agent starts over: "I'll start by exploring the repository"
   -> `ls -la`, `find`, `cat`: 12325 ss r2 (x2), ss r3, su-full r1; 14531
   ss r3 (x2), su-full r1; 10908 ss r2 (x3); 17084 su-full r1, ss r3. The
   summary itself often says "fix applied, tests pass"; the model ignores
   it. 0 of 22 partial/TR/TRC events in 14531 restarted vs 4 of 36 full
   events.
5. **Template / co-visibility loss (TR, TRC, OTRC).** The fix is a copy of
   an idiom or a two-site invariant that must be in one view: 10908 guard
   (16/16 vs 3/16), 14053 L893+L931, 25232 `"no_validation"` (0/16 vs
   5/11), 13757 three-file chain, 14983 `_build_repr` + `__init__`s, 25931
   L291. Threshold policies mostly survive because the edit precedes the
   event; OTRC's 4-5-observation window loses the read before the edit in
   nearly every run.
6. **Lost negative evidence -> repetition.** Failed builds re-run after
   every summary/clear (25931 ss r3 s15-22 = s54-56 = s96-98; otrc r1 16x
   import probe), non-matching seds re-issued (25232 tr r3 8x), destructive
   seds repeated once their result leaves the window (25232 otrc-su-partial
   r1 s105 = s122), 2-line deletes cycled 26x (14983 otrc r1), identical
   commands 79x/47x/19x (17084 otrc r2, otrc-ss-partial r2; 14531
   otrc-ss-partial r3). Max consecutive identical command: 1-2 in FC and in
   all threshold runs; >= 5 only in OTRC (14/204 failing runs, all OTRC,
   all step-limit).
7. **Edit-tool thrash amplified by lost file views.** heredoc/sed with wrong
   indentation followed by `git checkout`: 12325 otrc-su-partial r1 20
   cycles, ss-partial r2 14; 25232 tr r1 8 restores, trc-su r1 7; 14983
   su-partial r2 6 checkouts. FC hits the same corruptions (25232 FC r1 two
   restores, 10908 FC r3 garbled sed) but restores once and re-applies once
   because the failed attempt is still visible.

## 4. Where the loss is *not* compression

- **OTRC harness bug**: 22/108 Group C OTRC runs (0 resolved) lost the task
  text; they invent tasks (12325 otrc-tr r3 edits a test file; 25931
  otrc-ss-partial r2 "max_samples"), or loop on `echo SUBMIT` 42-65x.
  Cell-level: 14053 and 10908 lose 9/12 and 7/12 OTRC runs this way.
- **Base rate / exploration variance**: 10908 10/13 misses never read
  `transform()` before any compression; 14983 FC r3 and both
  zero-compression failures fail by the same unfaithful mock; 14053 5/11
  are edit slips made with the code in view; 13757 ss-partial r2 (0 events)
  abandoned the env at s17.
- **Hidden-constraint misses no policy could catch**: 25931 trc-ss r3
  unchunked scores (breaks `call_count == 3`), 10908 trc-su r1 global sed
  hitting `transform` (iterator exhaustion), 14531 otrc r3 double-print.
- **Model degeneration**: 25931 otrc-tr r3 (4096-token turns from step 1,
  crash at s25).

## 5. Cross-task numbers

| quantity | value |
|---|---|
| Group C FC peak context (median) | 32.9k (P100 median 29.7k) |
| first compression step, threshold cells (p10/p50/p90) | 36 / 50 / 71 |
| first edit step (p50/p90) | 11 / 17 |
| FC submit step (median) | 65 |
| compression fired before first edit | 0 / 216 threshold runs |
| failing compressed runs, `git diff` calls (mean) | 1.36 (resolving: 1.97; FC resolved: 1.59) |
| failing compressed runs with max identical-command streak >= 5 | 14/204, all OTRC, all step-limit |
| OTRC runs with `messages[1]` wiped, devstral main | 230/1200 (19%), 0 resolved |
| OTRC runs wiped, Group C | 22/108; non-wiped OTRC resolve 21% |
| resolve by family on Group C (n) | FC .81 (27), SU .54 (54), TR .56 (27), TRC-stack .43 (54), TRC .41 (27), SS .44 (54), OTRC .17 (108) |
| compressed resolve excl. wiped, hard core | 12325 .15, 17084 .17, 14983 .08 |
| compressed resolve excl. wiped, marginal | 25232 .44, 14531 .47, 10908 .52, 14053 .59, 25931 .61, 13757 .63 |

The last two rows split Group C: three tasks (12325, 17084, 14983) are
genuinely compression-hostile at every policy (a strong wrong prior plus a
fix that needs a late self-correction from raw reads), while six are
marginal cases where FC's 3/3 sits above a ~50% compressed rate that is
mostly base-rate variance plus the OTRC bug.

## 6. Comparison with the Qwen3.5-35B Group C note

Same substrate (untestable env, small fix, misleading prior, early template
needed late) and the same three memory classes (edit ledger, negative
evidence, early template). Differences: (i) Devstral's FC is the weakest
cell overall, so its Group C is smaller in effect size and three of nine
tasks are marginal; (ii) Devstral shows a **prior-dominates** pattern (the
wrong variant is chosen pre-compression in most runs, FC included), so the
compression-specific loss is mainly the removal of late self-correction and
of completion state rather than the induction of a wrong edit; (iii) the SS/
SU-full **restart-from-scratch** behaviour after a summary is Devstral-
specific and unique to full-summary policies; (iv) the OTRC msg[1]-wipe bug
is twice as frequent on Devstral main (19% vs 9%) and dominates the OTRC
cells for 10908 and 14053.
