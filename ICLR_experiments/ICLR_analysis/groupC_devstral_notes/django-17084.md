# django__django-17084 — Devstral-Small-24B, ICLR_experiments/swebench/main/devstral24b

Outcomes (39 runs): FC 2/3 resolved (r3 step-limit). Compressed 6/36 resolved: ss r1, su-full r2, tr r1, otrc-ss-partial r1, trc r2, trc-ss r3.
14 submitted-unresolved, 16 LimitsExceeded (step cap 125). No OTRC run has the messages[1]-wipe bug; all failures genuine.

## Gold fix & hidden constraints
- Gold: `sql/query.py::get_aggregation` adds `refs_window` (any referenced annotation has `contains_over_clause`) to the
  "wrap in AggregateQuery subquery" condition. Test `test_referenced_window_requires_wrapping` asserts the query RUNS
  (1 query, 2 SELECTs, `{'sum_avg_publisher_pages': 1100.0, 'books_count': 2}`). The fix must ALLOW aggregate-over-window.
- Two patch classes pass the hidden test: (A) query.py subquery-wrap on `contains_over_clause` (gold-like; trc r2, otrc-ss-partial r1);
  (B) drop `Window.contains_aggregate = False` (expressions.py:1702) so `Window(Avg(..))` reports contains_aggregate=True ->
  `has_existing_aggregation` already forces the subquery (FC r1, FC r2, ss r1, su-full r2, tr r1, trc-ss r3). Both resolve.
- Wrong-but-plausible class (R): mirror `Aggregate.resolve_expression`'s existing "Cannot compute X: Y is an aggregate" check and
  `raise FieldError(... is a window function)` on `contains_over_clause`. Turns the DB error into a Django error; hidden test fails.
  13/14 unresolved submissions are class R (the 14th, su-partial r2, is class B broken by a bad global edit).

## Environment
- `python` = /opt/miniconda3/bin/python 3.11.5 with Django deps missing: `asgiref` (34/39 runs pip-install it), `sqlparse`; no pytest; no PostgreSQL.
- SQLite reproduces the bug as `OperationalError: misuse of window function SUM()` (25 runs saw it) — a usable oracle, but the reject-class
  runs treat "now it raises FieldError instead" as success.
- `python tests/runtests.py expressions_window` fails `No module named 'django'` until `PYTHONPATH=/testbed` or `pip install -e .`;
  guessed `--settings=tests.settings` fails. Only 8/39 runs ever got a real "Ran N tests" line. The verification step is a step sink.

## FC success path
- FC r2 (69 steps, class B): s7 reads Window class (sees `contains_aggregate = False` + comment); s27 grep contains_aggregate -> s28 "Now I understand";
  s33/s52 edit (cached_property delegating to source_expression); s54 own SQLite repro prints `Success! Aggregates: {... 'cumul_DJR_total': 100.0}`;
  s65 PR example passes; s66-69 git diff/patch/submit. Never ran the test suite.
- FC r1 (106 steps, class B): s41-43 same insight, s58 `sed -i '1702d'`, s85 flips `assertFalse->assertTrue` in tests, s104-106 submit. Early Window read (s5) is what is reused at s41/s58.
- FC r3 (LimitsExceeded, class R): s76-78 adds validation to aggregates.py, s80-112 spends 30 steps making the FieldError fire in the summarize=True path,
  s119 finally runs suite (PYTHONPATH), s122-125 cleanup; cap hit before `git diff`. Would have been unresolved anyway. So class R is a Devstral prior, not a compression artifact.

## Taxonomy of failing compressed runs (comp = compression steps; OTRC = per-step clears)
| cell/run | outcome | patch class | comp | dominant mechanism |
|---|---|---|---|---|
| ss r2 | limit | B in tree, never submitted | 69 | post-comp verification churn on own synthetic script (F has no contains_aggregate) s70-125 |
| ss r3 | unresolved | R (Func.as_sql raise) | 32,78,107 | s105 finds fix breaks valid `Sum` inside `Window`; comp@107 summary says "preserving valid use cases"; s109 submits "based on the context summary" |
| ss-partial r1 | limit | A-like query.py rewrite | 53,91 | 12 failed sed/py edits of get_aggregation (s47-125), each re-copying backup |
| ss-partial r2 | limit | wrong: add `F.get_refs` | 58,110 | chased artifact of own unresolved-expression test; 10 edit attempts s96-125 |
| ss-partial r3 | limit | R | 51,85,109 | s93 "accidentally removed most of the file"; check placement churn; test-runner flail s119-125 |
| su-full r1 | limit | R | 60,111 | s57-59 sed corrupts file; comp@60; s61 restarts `ls -la`, s71-99 repairs syntax it no longer remembers causing |
| su-full r3 | unresolved | R | 50 | reject chosen s47 (pre-comp); FieldError seen as success s62 |
| su-partial r1 | unresolved | R | 54 | reject chosen s31 (pre-comp) |
| su-partial r2 | unresolved | B + BaseExpression override | 56 | s30 `sed -i '/def _resolve_output_field/i ...'` inserted property in 5 classes; after comp, s79-81 treats stray BaseExpression property as Django code and "fixes" it |
| su-partial r3 | unresolved | R | 32,65,101 | reject chosen s32 |
| tr r2 | limit | R | 51,64,86,107 | 11 patch_aggregatesN.py iterations s97-125 trying to make check fire under summarize=True |
| tr r3 | unresolved | R | 59,102 | reject chosen s18 |
| otrc-ss-partial r2 | limit | none | clears | 47 consecutive identical `grep -B30 -A30 "if val.contains_aggregate"` s79-125 |
| otrc-ss-partial r3 | limit | A in tree (s74; s88 Success) | clears | 33 steps s92-125 failing to run suite; never `git diff`/submit |
| otrc-su-partial r1 | unresolved | R | clears | reject s57; suite ran OK s96-100 (suite does not cover the bug) |
| otrc-su-partial r2 | limit | A attempts + compiler.py | clears,122 | 5 patch iterations, s121-125 near-identical debug scripts |
| otrc-su-partial r3 | unresolved | R + query.py raise | clears | reject s51 |
| otrc-tr r1 | limit | B (s65-71) then R added s108 | clears | correct fix, then adds rejection on top; suite flail s112-121 |
| otrc-tr r2 | limit | wrong: F class props | clears | 4 identical failed `fix_f_class.py` s100-111 |
| otrc-tr r3 | limit | B at s23, reverted s51 | clears | "Let me revert this change and think differently" after losing the reasoning; churn to 125 |
| otrc r1 | limit | R applied/reverted x3 | clears | s124 realizes "we should be able to aggregate" (right insight) at step 124 |
| otrc r2 | limit | none | clears | 79 consecutive identical `cat > test_window_aggregate.py` s47-125 (empty obs each time) |
| otrc r3 | limit | B in tree (s106; s108 Success) | clears | derails on pre-existing test expectations s109-120, edits compiler.py error text |
| trc r1 | unresolved | R | 44,80 | reject chosen s45-47 right after comp@44 |
| trc r3 | unresolved | R | 27,67 | reject chosen s44 |
| trc-ss r1 | unresolved | R | 47,80 | reject chosen s40 (pre-comp) |
| trc-ss r2 | limit | R | 47,81,89,111,119 | `query is None` guard churn from own no-query test; 6 checkouts |
| trc-su r1 | unresolved | R | 48,71 | reject s29; suite ran OK s42/66 |
| trc-su r2 | unresolved | R | 55,81,92,96,108,110 | s93-96 finds gold site (`has_existing_aggregation` lacks over_clause); comp fires AT s96; s97-113 only re-tests old R patch, submits |
| trc-su r3 | unresolved | R | 50 | reject s47-50 |

## Mechanisms (step-cited)
1. Approach prior, not compression: reject-class decision predates first compression in 12/18 R runs (tr r3 s18, su-partial r1 s31, trc-ss r1 s40,
   trc-su r1 s29, ...) and FC r3 also chose R. Allow-class (A/B) was chosen in 14/36 compressed runs vs 2/3 FC; FC's 2/3 is partly sample luck.
2. Compression kills convergence on the allow path: allow-path runs resolve 6/14 under compression vs 2/2 FC; 7/14 hit the cap. Four of those had a
   test-passing fix already in the tree (ss r2 s43/s121, otrc-ss-partial r3 s88, otrc r3 s108, otrc-tr r1 s71) and never ran `git diff > patch.txt`.
   Post-compression the agent forgets it already verified and re-enters "verify with the real suite", which the env makes expensive (mechanism in Environment).
3. Summary overwrites negative evidence (ss r3): s105-106 show `Test 4: Valid case - Sum inside Window -> NotImplementedError`; the s107 summary
   asserts the fix "correctly handles ... while preserving valid use cases (aggregates inside window functions)"; s109 "Based on the context summary,
   the only file modified is expressions.py" -> submit.
4. Lost edit provenance (su-partial r2): s30 global sed inserted `contains_aggregate` property before every `_resolve_output_field`; after comp@56 the
   agent reads line 319 (s79) as pre-existing Django code, "makes it robust" (s81), notices "changes to multiple classes" (s90) but rationalizes and submits.
   The BaseExpression override returns False for Coalesce(Window) -> subquery not triggered.
5. Insight discarded at compression boundary (trc-su r2): s93-96 reasoning reaches the gold condition; step 96 is a compression event; every step after
   (97-113) verifies the older reject patch and submits it. No query.py edit ever made.
6. Restart-from-scratch after full summarization: su-full r1 s61 (`ls -la`) and ss r3 s79 (`ls -la`) re-explore; su-full r1 then repairs syntax
   errors (s71-99) whose cause (s57-59 sed) is no longer in context.
7. OTRC degenerate loops: with tool results cleared and the current observation empty (`cat >` writes nothing), otrc r2 repeats one command 79x
   (s47-125), otrc-ss-partial r2 47x (s79-125), otrc-tr r2 4x identical failing script. FC/threshold cells max consecutive identical = 1-2.
8. Synthetic-test artifacts steer edits (ss r2 s66-121, ss-partial r2 s96, trc-ss r2 s91, otrc-tr r2 s100-119): the agent's own scripts call
   `resolve_expression()`/`contains_aggregate` on unresolved `F`/no-query objects, then "fixes" Django to tolerate them. FC r1 hit the same error
   (s65) and moved on because it still had the s41-43 reasoning in context.

## Root cause
Devstral splits roughly evenly between an allow fix (drop `Window.contains_aggregate = False` or subquery-wrap on `contains_over_clause`) and a
reject fix (raise FieldError like the neighboring aggregate check); the reject choice is a prior visible in FC r3 and in 12/18 reject runs before
any compression, and it is always unresolved because the hidden test requires the query to run. Compression does not flip that prior, but on the
allow path it converts would-be successes into step-limit failures: after a compression event the agent loses that it already verified
(`Success! Aggregates ... 100.0`) and re-enters a verification loop the container makes costly (missing asgiref/sqlparse/pytest, runtests.py needing
PYTHONPATH), or loses the provenance of its own edits and "repairs" them into a broken patch, while OTRC's empty-observation state produces
47-79-step identical-command loops. Net: 2/2 FC allow-path runs submitted a passing patch; 6/14 compressed allow-path runs did.
