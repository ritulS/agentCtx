# Group A: why FC fails these tasks while most compression policies solve them

Scope: `ICLR_experiments/swebench/main/devstral24b` only (Devstral-Small-2-24B, P100
main cells: FC@inf, OTRC@inf, 11 compressed policies at the calibrated 21k
budget, 3 runs each). Group A = tasks where FC resolves <= 1/3 and >= 7 of the
12 compression policies resolve a majority of their 3 runs:
django-12276 (N=11), sklearn-14710 (N=11), sympy-18211 (N=10), sympy-17139 (N=9).
Evidence: `agent.log` / `token_log.json` / `trajectory.json` per run, per-cell
`eval/` reports and `eval/logs/run_evaluation/*/test_output.txt`, the
2026-09-10 re-evaluation archive, the archived pre-rerun FC run_2/3
(`archives/devstral_fc_r23_before_rerun_20260910`), and gold patches from
SWE-bench Verified. Per-task deep dives in `ICLR_experiments/ICLR_analysis/groupA_notes/`.
Companion to `ICLR_experiments/ICLR_analysis/groupC_fc_vs_compression.md` (Qwen, FC wins) and
`ICLR_experiments/ICLR_analysis/groupD_why_compression_robust.md`.

## 0. Headline

None of the four Group A tasks is a case where compression *helps* the agent.

1. **sklearn-14710 is an evaluation artifact.** All three FC patches are
   byte-identical to each other and (up to quote style) to the resolved
   compressed patches. FC run_1 and run_3 are `error_ids` in the harness report
   (docker "container name already in use" at container creation), were never
   re-evaluated, and are recorded as `resolved=False`. The compressed cells hit
   the same error on 14710 (every cell) and were fixed by the 2026-09-10
   re-evaluation; the FC cell has **zero** re-evaluated records. Same
   asymmetry hits django-14915 FC run_2.
2. **The other three are "fork" tasks.** Every submitted patch falls into two
   or three shapes, and the shape predicts pass/fail perfectly:

   | task | passing shape (gold) | failing shape(s) | resolved by shape |
   |---|---|---|---|
   | sympy-17139 | early return `if not rv.exp.is_real: return rv` | prepend `rv.exp.is_real and` to the `<0` / `>max` comparisons | early-return 26/26, guard 0/10 |
   | sympy-18211 | `try: solve_univariate_inequality(...) except NotImplementedError: return ConditionSet(x, self, S.Reals)` | route equations to `solveset(...)`; or pick the domain by `x.is_real` (-> Complexes) | try/except 22/22, solveset 1/7 (the 1 is a mislabel, gold-equivalent), Complexes 0/7 |
   | django-12276 | move `use_required_attribute` to `FileInput` with `and not initial` | add `is_initial(value)` = `bool(value and getattr(value,'url',False))` copied from `ClearableFileInput` | simple 30/30, is_initial 0/4 |

   FC chose the failing shape in 7 of its 7 genuinely-evaluated failing runs.
3. **The shape is chosen at the first edit, at small context, before any
   compression could act.** Decision steps sit at 9-15k prompt tokens
   (18211: FC r1 step 33 = 11.8k, FC r2 = 13.3k, tr r2 = 9.9k; 17139: FC edits at
   steps 14-22, peak context 14-21k for all three FC runs), i.e. below the 21k
   budget. In 17/17 resolved threshold-compressed runs of 18211 the gold edit
   precedes the compression event. Runs in compressed cells where compression
   never fired (FC-equivalent runs) resolve 12276 17/20 and 17139 20/24; for
   18211 they are 0/5 but n=2 in threshold cells and both on the FC path.
4. **Extra samples flip the "FC fails" label.** The archived pre-rerun FC
   run_2/3 (generated 2026-08-29, replaced by the 2026-09-10 rerun) resolved
   12276 r2+r3 (simple shape), 17139 r2 (early return; r3 also early return but
   eval error), and 18211 r2 (try/except). Pooling all FC samples: 12276 3/5,
   17139 2/4 evaluated, 18211 1/5, 14710 1/1 evaluated. Group A is what
   selecting on a 3-sample FC estimate over 100 tasks produces: with the
   FC-equivalent pool as the per-task success rate, the expected number of
   Group A tasks from FC sampling noise alone is ~0.7 among the 32 tasks with a
   usable pool, and the archived samples show the specific 0/3 and 1/3 draws
   were not reproducible.
5. **What actually decides the fork is a verification blind spot, not
   context.** In all three tasks the agent's own reproduction cannot
   distinguish the shapes: `simplify(cos(x)**I)` only exercises the `pow=False`
   path (17139); a repro with `Symbol('n', real=True)` hides the Complexes
   domain and nobody tried the `sqrt` case (18211); a repro with a
   FieldFile-like object that has `.url` hides the plain-string initial
   (12276). No run in any condition tested the discriminating input. Two 17139
   guard runs (FC r3, trc-ss r3) saw `simplify(cos(x)**I)` return `1` and still
   reported "All tests passed"; 18211 tr r2 asserted the wrong domain
   (`Complexes`) and printed "PR test case passed!".

## 1. Per-task evidence

### sklearn-14710 (evaluation artifact)

- Gold: index `y_small_train` / `y_val` through `self.classes_` before scoring
  when `is_classifier(self)`. FC r1/r2/r3 submissions are byte-identical
  (`hasattr(self, 'classes_')` guard, same 4 lines); d05__b21k__tr run_1 differs
  only in quote style and is resolved.
- FC r2 resolved. FC r1 and r3: harness report `error_ids`; `run_instance.log`
  shows `500 Server Error ... container name "sweb.eval.scikit-learn__scikit-learn-14710...__r1" is already in use`
  (2026-08-29 and 2026-09-10). Every compressed cell has the same error on
  14710 in its original `eval/` report; those were re-evaluated on 2026-09-10
  (`reevaluation.report_path` in `experiment_results.json`, F2P
  `test_string_target_early_stopping[None]` success) and are `resolved=True`.
  `di__binf__fc/experiment_results.json` has 0 records with a `reevaluation`
  field. The archived FC r2/r3 (08-29) also died with the same eval error.
- Unre-evaluated `resolved=False` + `error_ids` records in the FC cell:
  14710 r1, 14710 r3, django-14915 r2. These should be re-evaluated
  (`scripts/build_reevaluation_candidates.py --model devstral24b` already
  classifies them as `evaluation_error_recorded_as_false`).

### sympy-17139 (fork: early return vs guarded comparisons)

See `ICLR_experiments/ICLR_analysis/groupA_notes/sympy__sympy-17139.md`.

- Mechanism (from FC r1 `test_output.txt`): with only the two ordering
  comparisons guarded, `T(sin(x)**I, sin, cos, h, 4, True)` falls through
  `== 2`, `== 4`, `pow=True` -> `perfect_power(I)` -> `ValueError: I is not an
  integer`. `test_issue_17137` (the PR's `simplify(cos(x)**I)`) passes under the
  guard patch; only `test__TR56`'s new `pow=True` assertion fails. The guard
  patch is a correct fix of the issue as filed and fails the hidden test.
- FC r1 (54 steps, edit at 22): read the whole `_TR56` twice, step 18 THOUGHT
  says "If it's not real, I should return the expression unchanged", then
  empirically checked `I == 2`, `I % 2`, `I // 2` (not `perfect_power`) and
  concluded "the only issue is with the `<` and `>` comparisons". FC r2 (32
  steps, edit at 16): grep'd `rv.exp <` / `rv.exp >`, "there are two
  problematic comparisons"; patch byte-identical to r1. FC r3 (51 steps, edit
  at 14): wrapped every visible `rv.exp` use, which makes `simplify(cos(x)**I)`
  return `1`; observed `Result: 1` at steps 34/36/46 and wrote "All tests
  passed".
- Resolved never-compressed runs (tr r1-3, su-full r1-3, ss r1-3) read the
  same lines and ran the same `cos(x)**I` repro. The difference is one
  sentence at the edit step: tr r2 step 9 enumerated all five checks including
  "check if exponent is even or a perfect power" -> step 12 "add a check right
  after the `rv.is_Pow` check ... return the original expression"; tr r3 step
  17 listed `perfect_power(rv.exp)` -> step 18 "not designed to handle complex
  exponents ... return early". ss r2 made FC r2's "only two comparisons"
  observation and still wrote an early return, so it is a tendency, not a rule.
- The 7 compressed guard runs: OTRC runs had tool results cleared from step 0
  (only the last 4 visible) and produced FC's exact patch with FC's exact
  reasoning ("there are only two problematic comparisons", otrc-su-partial r2
  step 24); trc-su r1 edited at 23-26 with compression at 57; trc-ss r3 never
  compressed. No compression event precedes any guard decision.
- Exploration volume is the same band in both groups (FC first edit at
  22/16/14 with 6/4/3 fu.py reads; resolved runs first edit at 13-23 with 3-7
  reads). Guard rate ~10/37 per run; three guard draws in a row for FC has
  p ~ 0.02 under independence, and the archived FC r2/r3 both drew early
  return.

### sympy-18211 (fork: try/except -> ConditionSet(Reals) vs "agree with solveset")

See `ICLR_experiments/ICLR_analysis/groupA_notes/sympy__sympy-18211.md`.

- Mechanisms (eval `test_output.txt` lines 964/967, checked against sympy):
  (a) domain by `x.is_real` -> `Complexes` because the test's `x` is a plain
  Symbol (`is_real is None`), 7/7 fail; (b) `solveset(self, x)` default domain is
  Complexes, fail; (c) `solveset(self, x, domain=S.Reals)` passes the cos case
  but squares away the radical in the sqrt case
  (`ConditionSet(x, Eq(x**4 + 2*x**2*sin(x) - 2*x + sin(x)**2, 0), Reals)`),
  FC r3 and ss-partial r2 fail here; (d) FC r2 returned `solveset(e, gen,
  domain)` inside `solve_univariate_inequality` after the code has replaced
  `gen` by a `Dummy('gen', extended_real=True)` (visible in its own step-19
  output) so the Dummy leaks into the ConditionSet.
- Why the failing runs passed their own tests: 5/7 Complexes-domain runs used
  `Symbol('n', real=True)` in the repro (FC r1 step 61 "Result matches expected
  ConditionSet!"); tr r2 step 39 asserted `result.args[2] == Complexes` and
  printed "PR test case passed!"; nobody tested a sqrt input.
- The apparent "compression fired -> resolved" association (fired 23/31,
  not-fired 0/5) is a selection artifact. In all 17 resolved threshold-
  compressed runs the try/except edit precedes the compression event (tr r1
  42<62, tr r3 31<50, ss r1 54<63, ss r2 35<51, ss r3 33<55, ss-partial r1
  46<62, r3 32<47, su-full r1 40<52, r3 27<47, su-partial r1 26<45, trc r2
  24<50, r3 38<57, trc-ss r1 32<55, r2 29<42, trc-su r1 31<38, r3 35<49) and
  every su/ss summary already states "Files Modified: relational.py - catch
  NotImplementedError and return ConditionSet". The failing designs were fixed
  at 9.9-14.7k tokens (FC r1 step 33 "as_set() doesn't use solveset() - it
  uses solve_univariate_inequality() which is designed for inequalities"), below
  the budget; the two not-fired compressed failures are simply the same path
  in shorter runs.
- The only documented design changes go gold -> broken and happen despite or
  after compression: trc-ss r3 wrote the gold fix at step 38, read solveset's
  domain logic at 46-49, and rewrote it with `S.Reals if x.is_real else
  S.Complexes` at step 50 (the compression step); trc-su r2 wrote gold at 53,
  compression at 67 preserved it (68 "Our change is exactly what we
  intended"), then a self-written "consistency with solveset" test at 74-79 led
  to "to be consistent with solveset(), I should use S.Complexes".
- Compression's one visible effect on a resolved run is negative: ss r1 step
  64 (right after compression) "I'll start by exploring the repository
  structure" and 25 steps re-deriving a fix already on disk before resubmitting
  the unchanged diff.
- FC r3 shows how solveset routing arises without any budget pressure: step
  32 unconditional `if rel_op == '==': return ConditionSet(x, self, S.Reals)`;
  step 45 `pytest test_relational.py` -> `test_univariate_relational_as_set`
  fails (`Eq(x, 0)` must give `FiniteSet(0)`); step 47 "my fix is too broad ...
  implement a more sophisticated fix"; step 51 (21.2k) routes to
  `solveset(Reals)` with ConditionSet fallback. It never tried wrapping the
  existing `solve_univariate_inequality` call.

### django-12276 (fork: `not initial` vs copied `is_initial`)

See `ICLR_experiments/ICLR_analysis/groupA_notes/django__django-12276.md`.

- Mechanism: `is_initial` returns `bool(value and getattr(value, 'url', False))`;
  both gold tests pass the plain string `'resume.txt'`, which has no `.url`, so
  `use_required_attribute('resume.txt')` stays True and the form still renders
  `required`. The simple `and not initial` shape (verbatim move of the
  ClearableFileInput method) passes 30/30.
- The design is a one-shot framing choice made early and at small context in
  every run: failing runs decided at 9.1-13.3k tokens (FC r1 step 24 @13.3k;
  FC r3 step 22 @~10k; ss r2 step 16 @~10.6k; su-full r3 step 24 @~9.4k),
  resolved runs at 3.8-13.3k (FC r2 step 25 @13.3k; tr r1 step 14; su-partial
  r1 step 14; trc-ss r1 step 15; otrc-tr r1 step 13 @3.8k). FC r2 resolved at
  the same context size at which FC r1 failed. Seeing
  `ClearableFileInput.is_initial` does not discriminate either: all 9 examined
  runs had it in context from their first read of the class block (steps 5-13),
  before any edit. Framing: "move the method" -> verbatim copy;
  "detect initial file data" -> `is_initial` (FC r1 step 23: "is_initial checks
  if the value has a url attribute, which is typical for file objects that have
  been saved to storage"; su-full r3 step 23: "I need to understand how
  ClearableFileInput.is_initial() works so I can implement the same logic").
- FC's long runs (94/107 steps, 35-37k peak) are edit thrash *after* the
  decision: FC r1 steps 25-73 (5 backup restores) and FC r3 steps 22-64 and
  80-103 (3 git checkouts) fighting sed/python patch application; resolved tr
  r1 had the same thrash (steps 37-63) with the correct design. Length neither
  caused nor was caused by the design.
- The two FC failures falsified their own design and rationalised it: FC r1
  step 21 (pre-fix) saw `ClearableFileInput.use_required_attribute('existing_file.pdf')`
  -> False, step 74 (post-fix) saw it flip to True, step 75 "is_initial ... is
  not working correctly for string values", step 77 "This is actually the
  correct behavior! ... String values like 'existing_file.pdf' don't represent
  actual file objects with URLs". FC r3 saw the same flip (steps 15 -> 65),
  printed "String without url -> True" at step 67 and moved on. The two
  compressed failures never tested a non-empty string (ss r2 only a FakeFile
  with `.url`; su-full r3 only `''` and an object without `.url`).
- No failing run ran `test_fileinput.py` / `test_forms.py` (pytest absent,
  `django test` unconfigured: FC r1 79-80, FC r3 68/69/75, ss r2 35-38); all fell
  back to self-written mock-with-`.url` scripts that pass by construction. The
  only explicit is_initial-vs-not-initial reasoning is in resolved FC r2 step
  49, after it cat'd `tests/forms_tests/widget_tests/test_fileinput.py` (step
  36): "the use_required_attribute() logic is intentionally simpler than
  is_initial() ... Given that the existing test only checks None and
  'resume.txt'".
- su-full r3's single compression event fired at step 68, 44 steps after the
  design; the summary carried the `is_initial` code forward verbatim and
  claimed "Verified that existing Django tests still pass". No causal role.
- Base rate of the failing shape ~10% (4/39 patches); the 17 never-fired
  compressed runs are the same trajectory distribution as FC and produced 1
  `is_initial`. Weak caveat: 3 of 4 failures come from the 09-09/09-10 batch
  vs 0 of ~20 from 08-31/09-01 (FC r1 is 08-28).

## 2. Cross-task numbers

| task | FC (current) | FC (archived 08-29 r2/r3) | FC-equivalent runs (compressed cell, never fired) | compressed, fired |
|---|---|---|---|---|
| django-12276 | 1/3 | 2/2 | 17/20 | 13/14 |
| sklearn-14710 | 1/3 (2 eval errors) | 0/2 (2 eval errors) | 9/11 | 23/25 |
| sympy-18211 | 0/3 | 1/2 (r3 no submission) | 0/5 | 23/31 |
| sympy-17139 | 0/3 | 1/2 (r3 early return, eval error) | 20/24 | 7/13 |

Run configuration is identical across cells (same `config-devstral-vllm.yaml`,
temperature 0.2, same system/instance messages byte-for-byte; FC is the
`truncation` code path with an unreachable budget). No server-level shift was
found between the FC batches (08-28, 09-10) and the compressed batches
(08-31..09-03, 09-09/10): `scripts/serving/start_vllm_devstral.sh` unchanged since
08-28, per-step completion length and format-error rate flat across batches.
A batch effect therefore cannot be excluded but has no positive evidence.

Chance model: with the FC-equivalent pool as each task's success rate, the
expected number of tasks with N>=7 policies passing and FC<=1/3 from FC's three
draws alone is 0.68 over the 32 tasks with a usable pool. 12276 and 17139
individually have q~0.01 under that model, which is why the archived FC r2/r3
matter: they show the 0/3 and 1/3 were draws, not a property of FC.

## 3. What this means for the paper

- Group A on Devstral is **not** evidence for "compression beyond the budget".
  The mechanism that decides these tasks (which fix shape the model commits to
  at its first edit, and whether its own reproduction can tell the shapes
  apart) operates at 10-15k tokens, before any primitive fires, and no
  primitive changes it. The three deep dives found zero cases where a
  compression event moved a run from a failing shape to the passing shape, and
  two cases (18211) where a post-compression exploration moved it the other
  way.
- Two data-quality actions: (1) re-evaluate the FC cell's
  `evaluation_error_recorded_as_false` records (14710 r1/r3, 14915 r2) so FC is
  treated the same as the compressed cells; (2) for per-task FC-vs-policy
  claims, either pool FC with never-fired runs from threshold cells (they are
  the same process) or report FC with >= 5 seeds. With 3 seeds, a 100-task
  sweep will always contain a handful of Group A / Group C tasks by selection.
- The "fork" pattern itself (17139, 18211, 12276) is a reusable
  characterisation: outcome determined by fix shape, shape chosen once, hidden
  test discriminates shapes that the PR's own reproduction does not. It is a
  property of the task + model prior, orthogonal to context management.
