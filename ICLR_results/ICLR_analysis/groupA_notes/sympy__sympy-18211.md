# sympy__sympy-18211 — why "compression fired" correlates with success (Devstral-24B)

Sources: `ICLR_results/swebench/main/devstral24b/<cell>/sympy__sympy-18211/*/run_N/{agent.log,token_log.json,trajectory.json}`,
eval logs under `<cell>/eval/logs/run_evaluation/sympy__sympy-18211__*/…/test_output.txt`, and local sympy 1.14 for mechanism checks.

## Summary (causal story)

1. Outcome is fully determined by the patch style, and the style is chosen at the **first edit**, which in every resolved
   threshold-compressed run (17/17) happened **before** the compression event (e.g. tr r1 edit@42 < comp@62; ss r1 54<63;
   trc r2 24<50; trc-ss r1 32<55). Every su/ss summary already reads "Files Modified: relational.py — catch
   NotImplementedError and return ConditionSet". Compression therefore did not *produce* the minimal design.
2. The failing designs were also chosen early and at small context (FC r1 @step 33 = 11.8k tokens; FC r2 @29 = 14.4k;
   tr r2 @26 = 11.3k; ss-partial r2 @54 = 14.7k), well below the 21k budget — a threshold compressor could not have intervened.
3. The two "compressed cell but never fired" failures (tr r2, ss-partial r2) are on exactly the FC path (cat solveset.py
   first, then "for equations, use solveset"). They did not fire simply because they were shorter/quieter (peak 18.4k / 19.9k).
   n=2, both failures: consistent with chance (7 failures among 30 threshold runs).
4. Where the trajectory *does* show a design change, it goes the wrong way and compression does not stop it: trc-ss r3 and
   trc-su r2 wrote the gold try/except→Reals first (steps 38 and 53), then after further solveset exploration replaced
   Reals with `S.Reals if x.is_real else S.Complexes` (step 50 = the compression step; step 79, twelve steps *after*
   compression at 67: "to be consistent with solveset(), I should use S.Complexes").
5. Compression's only visible effect on a resolved run is negative: ss r1 restarted exploration from scratch at step 64
   ("I'll start by exploring the repository structure…") and spent 25 steps re-deriving a fix already on disk.
6. Failure mechanisms are three concrete sympy behaviours (Complexes default when `x.is_real is None`; radical-squaring
   in solveset for the sqrt case; a Dummy symbol leaking out of `solve_univariate_inequality`), each reachable only by
   the "make as_set agree with solveset" line of thought. Agents fell into it because their own repro used
   `Symbol('n', real=True)` or because they wrote a "consistency with solveset" self-test.

## Failure mechanisms (from eval `test_output.txt` line numbers; verified with local sympy)

Test lines: 964 = cos case (`ConditionSet(x, Eq(x*cos(x)-3*sin(x),0), Reals)`), 967 = sqrt case.

| style | runs | fails at | mechanism |
|---|---|---|---|
| ConditionSet w/ `x.is_real` domain | fc r1, su-partial r2, trc r1, trc-ss r3, trc-su r2, otrc-tr r1, otrc r2 | 964 (7/7) | test uses plain `x`; `x.is_real is None` → Complexes. Local check: `S.Reals if x.is_real else S.Complexes` → `Complexes`. |
| `solveset(self, x)` (default domain) | tr r2, otrc-tr r3, otrc-ss-partial r2 | 964 | solveset default domain is Complexes (fc r1 log step 43: `def solveset(f, symbol=None, domain=S.Complexes)`). tr r2 step 39 even *asserted* `result.args[2] == Complexes` and printed "PR test case passed!". |
| `solveset(self, x, domain=S.Reals)` | fc r3, ss-partial r2 | 967 | cos case passes (local: equal to expected), but for `x**2+sqrt(2)*sqrt(x)+sin(x)` solveset's radical handling squares the root: returns `ConditionSet(x, Eq(x**4 + 2*x**2*sin(x) - 2*x + sin(x)**2, 0), Reals)` ≠ expected. Nobody tested a sqrt input (only ss r3 and tr r1 ever put `sqrt` in a self-test, and not this one). |
| patch `inequalities.py` to return `solveset(e, gen, domain)` | fc r2 | 964 | fc r2's own step-19 output shows `gen = Dummy('gen', extended_real=True); expr = expr.xreplace({_gen: gen})` (line 87). Returning inside that block leaks the Dummy: local check gives `ConditionSet(_gen, Eq(_gen*cos(_gen) - 3*sin(_gen), 0), Reals)` ≠ expected. |
| (labelled route-to-solveset, resolved) | otrc-su-partial r1 | — | actually returns `ConditionSet(_gen, expr.xreplace({gen: _gen}), domain)` in inequalities.py — substitutes the symbol back, so it is gold-equivalent. Label is a misclassification. |
| "other" | su-full r2 (125-step limit), otrc r1, otrc r3 | — | no valid patch; not analysed further. |

Why the Complexes-domain runs passed their own tests: 5/7 used `Symbol('n', real=True)` in the repro (fc r1 steps 18/22/47/60;
su-partial r2 12-33; trc r1 10-22; otrc-tr r1 7-28; otrc r2 17-23), so `is_real` was True locally. fc r1 step 61:
"✅ Result matches expected ConditionSet!" — with a real symbol.

## FC runs

### fc run_1 (65 steps, peak 22.6k) — is_real domain, fails 964
Path: steps 3-10 grep/cat `solveset.py`, finds `solvify` raising NotImplementedError on ConditionSet (step 9: "I found the issue! At line 2138…").
Steps 11-17 boolalg.py → relational.py `_eval_as_set`. Step 18 repro with `n = Symbol('n', real=True)`; step 23 output:
as_set → NotImplementedError, `solveset(eq, n)` → `ConditionSet(n, …, Complexes)`. Step 26 (10.7k ctx): "The issue is that
`as_set()` doesn't use `solveset()` - it uses `solve_univariate_inequality()` which is designed for inequalities, not equations."
Step 33 (11.8k): dispatches `isinstance(self, Equality)` → `solveset(self, x)`. Step 38-39 sees Complexes, step 43 reads solveset's
signature, step 44: "This suggests that `as_set()` should use the Reals domain when the symbol is real" → `S.Reals if x.is_real else S.Complexes`.
Never considered try/except; never tested a plain Symbol. Ran `sympy/core/tests/test_relational.py` (step 53, old tests only) — passed.
Files read: solveset.py, boolalg.py, relational.py (not inequalities.py, not conditionset.py).

### fc run_2 (64 steps, peak 25.0k) — patch inequalities.py, fails 964
Steps 5-8 cat solveset.py / solvify. Steps 18-20 read `solve_univariate_inequality` (incl. the Dummy substitution, step 19). Step 21:
"If `solvify` raises a `NotImplementedError` … then `solve_univariate_inequality` also raises". Step 26 (13.3k): "The proper fix is to modify
`solve_univariate_inequality` to handle the case where `solvify` raises `NotImplementedError` by catching it and returning the result from
`solveset` directly." Edit steps 29-34. All tests with `Symbol('n', real=True)`. Ran only `test_bool_as_set` via python -c (step 46); never
ran test_relational.py. Never considered the relational.py try/except.

### fc run_3 (74 steps, peak 32.5k) — `rel_op=='=='` → solveset(Reals) w/ ConditionSet fallback, fails 967
Only FC run using a plain `symbols('n')` (step 6). Step 32 (12.1k) first edit = **unconditional** `if self.rel_op == '==': return ConditionSet(x, self, S.Reals)`.
Step 45 runs `pytest sympy/core/tests/test_relational.py -v` → `test_univariate_relational_as_set FAILED` (`Eq(x,0).as_set()` must be `FiniteSet(0)`).
Step 47: "my fix is too broad … it should only return `ConditionSet` for equations that cannot be solved symbolically … Let me revert my change
and implement a more sophisticated fix". Step 51 (21.2k): "1. For equations (`rel_op == '=='`), try to solve them using `solveset` 2. … 3. If
`solveset` can't solve them, return a `ConditionSet`". It never tried wrapping the *existing* `solve_univariate_inequality` call — it swapped the
solver. Steps 63-68 looked at `test_solve_sqrt_fail` (an XFAIL) but never tested a sqrt equation through as_set. Step 70 final check compares
only "is ConditionSet", not the exact form.

## Not-fired compressed failures

- **tr run_2** (53 steps, peak 18.4k): same path as fc r1 (cat solveset.py step 7, solvify at 9, relational.py at 14, repro with
  `Symbol('n', real=True)` at 16). Step 20 (9.9k): "For equations, it should call `solveset` instead." sed edit at step 26 → `solveset(self, x)`
  (default Complexes). Step 39 asserts `result.args[2] == Complexes` → "PR test case passed!". Ran test_univariate_relational_as_set (34). Identical to FC.
- **ss-partial run_2** (79 steps, peak 19.9k): reads solveset.py deeply (steps 6-12, `_solveset`), relational.py 15, boolalg 44-47. Plain
  `Symbol('n')`. Step 51 (13.9k): "This is what we want as_set() to return: `solveset(expr, n, S.Reals)`". Step 54 dispatch `is_Equality` →
  `solveset(self, x, S.Reals)`. Step 75 compares to exact expected form for the cos case and matches — fails only on the sqrt case (line 967).
  Never tested sqrt. Same design as fc r3.

## Resolved fired runs (before/after evidence)

| run | 1st edit (try/except) | comp step | ctx at edit | post-compression |
|---|---|---|---|---|
| tr r1 | 42 (sed, `except NotImplementedError: return ConditionSet(x, self, S.Reals)`) | 62 | — | 63: "Let me also run tests for solveset" (testing only) |
| tr r3 | 31 | 50 | — | tests/submit |
| ss r1 | 54 | 63 | — | summary: "Files Modified: relational.py — catch NotImplementedError and return ConditionSet"; step 64 *restarts* exploration ("I'll start by exploring the repository structure"), steps 64-88 re-derive, resubmits unchanged diff (step 85: "Based on my analysis, the fix was implemented in relational.py") |
| ss r2 | 35 | 51 | — | summary: fix implemented and tested |
| ss r3 | 33 | 55, 78 | — | summary: "The implementation is complete and working as expected" |
| trc r2 | 24 (THOUGHT: "Modify `_eval_as_set` to catch `NotImplementedError` and return `ConditionSet`") | 50 | — | 51: XFAIL triage, submit |
| trc r3 | 38 | 57 | — | 55-77 reads solveset.py / runs test_solveset, keeps Reals |
| trc-ss r1 | 32 (boolalg.py try/except around `r._eval_as_set()`) | 55 | — | 56: runs test_bool_as_set, submit |
| su-full r1/r3, su-partial r1/r3, ss-partial r1/r3, trc-ss r2, trc-su r1/r3 | 40/27, 26/40, 46/32, 29, 31/35 | 52/47, 45/63, 62/47, 42, 38/49 | all < 21k | all summaries describe the try/except fix as already made (su-partial r3: decided at 30, script failed, re-applied after comp) |

No resolved run contains a post-compression THOUGHT of the form "the simplest fix is…"; post-compression steps are test triage,
patch creation, or (ss r1) redundant re-exploration. For trc/trc-ss/trc-su the compression only replaced old tool outputs with
`[TOOL OUTPUT CLEARED — N tokens — step k]`; assistant THOUGHTs (and hence the plan) survive verbatim, and no second-stage
summary ever fired in those runs.

## Fired-but-failed runs

- **trc-ss r3**: step 38 gold try/except→Reals (ctx 19.1k). Steps 46-49 "Let me look at how solveset determines the domain" → writes
  `get_domain_from_symbol` (`S.Reals if symbol.is_real else S.Complexes`). Step 50 (= compression step, ctx after clear 10.4k) rewrites the fix
  with that domain. Step 54: "The `solveset` function defaults to `S.Complexes`. This is intentional behavior." Design degraded at the compression
  boundary, driven by solveset reading, not by the summary (none exists for trc-ss).
- **trc-su r2**: step 53 gold (ctx 15.8k): "in `_solveset`, when `solve_univariate_inequality` raises a `NotImplementedError`, it catches it and
  returns a `ConditionSet`. This is exactly what we need". Compression at 67 (tool outputs cleared, plan intact: step 68 "Our change is exactly what
  we intended"). Step 74 writes `test_consistency_with_solveset`; 76-78 sees Reals vs Complexes mismatch; step 79 (17.1k): "to be consistent with
  `solveset()`, I should use `S.Complexes`" → is_real domain. Degradation is **post-compression** and compression carried the gold plan forward.
- **trc r1**: is_real domain chosen at steps 33-36 (ctx 18.4k, "When the symbol has `is_real=True`, we should use `S.Reals`, otherwise
  `S.Complexes`") before compression at 52. Plan preserved through clearing.
- **su-partial r2**: step 23 saw `_solveset`'s pattern, step 26 "the domain should be `S.Reals` for real symbols", step 30 edit with is_real
  domain (16.9k) before compression at 41; summary carries "Domain selection: `S.Reals` for real symbols, `S.Complexes` otherwise" forward.
- **otrc-tr r1**: step 38 `Equality` → ConditionSet with is_real/is_complex domain; 46-58 chases the domain with a real symbol; step 58 "The
  default domain is `S.Complexes`. Let me update my fix to use `S.Complexes` as the default". Design set at 38 (continuous clearing from step ~4).
- **otrc-tr r3** (step 27) and **otrc-ss-partial r2** (step 30): "For equations (==), use solveset" → `solveset(self, x)`; same as tr r2.
- **otrc r2**: adds `Equality._eval_as_set` with is_real domain (46), step 87 "So `solveset` already handles this correctly… my implementation
  should do the same".

Common thread: every failure includes a phase of reading `solveset.py` *for the domain rule* or self-testing "as_set == solveset" and then
aligning to solveset's Complexes default. In the resolved runs solveset.py was read too (usually first, because the PR title names it),
but the edit was written straight from `_eval_as_set`/`solve_univariate_inequality` and not revisited.

## Table

| run | res | style | comp steps | 1st edit | design step | solveset.py read before design | exact expected form tested w/ plain symbol |
|---|---|---|---|---|---|---|---|
| fc r1 | F | is_real domain | – | 36 | 27/33, domain 44 | y (6-10) | n (real=True, step 60-61) |
| fc r2 | F | ineq.py→solveset | – | 29-34 | 26 | y (5-8, 21-22) | n |
| fc r3 | F | =='→solveset(Reals) | – | 32, 51 | 32, 51 | y (10) | n (isinstance only, 70) |
| tr r2 | F | solveset default | – (peak 18.4k) | 26 | 20 | y (7-9) | n (asserted Complexes, 39) |
| ss-partial r2 | F | solveset(Reals) | – (peak 19.9k) | 54 | 51 | y (6-12) | cos only (75); no sqrt |
| tr r1 | T | try/except | 62 | 42 | 42 | y (6-8) | n |
| tr r3 | T | try/except | 50 | 31 | 31 | y (6-9) | n |
| ss r1 | T | try/except | 63 | 54 | 54 | y (10-24) | n |
| ss r2 | T | try/except | 51 | 35 | 35 | y (5, 22-28) | n |
| ss r3 | T | try/except | 55, 78 | 33 | 33 | y (6-8) | y (74) |
| ss-partial r1 | T | try/except (boolalg) | 62 | 46 | 46 | y (9-15) | n |
| ss-partial r3 | T | try/except | 47 | 32 | 32 | y (9-15) | n |
| su-full r1 | T | try/except | 52 | 40 | 40 | y (5-12) | n |
| su-full r3 | T | try/except | 47 | 27 | 27 | y (10) | n |
| su-partial r1 | T | try/except | 45 | 26 | 26 | y (5, 23) | n |
| su-partial r2 | F | is_real domain | 41 | 30 | 26-30 | y (5, 20-22) | n |
| su-partial r3 | T | try/except (boolalg) | 63 | 40 | 30 | y (6-7) | y (85) |
| trc r1 | F | is_real domain | 52, 72 | 36 | 33-36 | y (25-28) | n |
| trc r2 | T | try/except | 50 | 24 | 24 | y (4-7, 18-20) | y (42) |
| trc r3 | T | try/except | 57 | 38 | 38 | y (6) | n |
| trc-ss r1 | T | try/except (boolalg) | 55 | 32 | 32 | y (7-8, 26-28) | n |
| trc-ss r2 | T | try/except | 42 | 29 | 29 | y (5, 17-23) | n |
| trc-ss r3 | F | is_real domain | 50 | 38 (gold) → 50 | 50 | y (5-10, 46) | n |
| trc-su r1 | T | try/except | 38 | 31 | 17-31 | y (5-16) | n |
| trc-su r2 | F | is_real domain | 67, 93 | 53 (gold) → 79 | 79 | y (6-12, 50-52, 70) | n (consistency-with-solveset test, 74) |
| trc-su r3 | T | try/except | 49 | 35 | 35 | y (6-13) | n |
| otrc-tr r1 | F | is_real domain | online | 38 | 38, 58 | y (5) | n |
| otrc-tr r2 | T | try/except | online | 26-28 | 26 | y (6-8) | n |
| otrc-tr r3 | F | solveset default | online | 27 | 27 | y (5-9) | n |
| otrc-ss-partial r1 | T | try/except | online | 29 | 29 | y (6) | y (38, 47) |
| otrc-ss-partial r2 | F | solveset default | online | 30 | 30 | y (6-12) | n |
| otrc-ss-partial r3 | T | try/except | online | 31 | 31 | y (5, 25-27) | n |
| otrc-su-partial r1 | T | ineq.py ConditionSet(_gen) | online | 44 | 8-44 | y (5, 27-49) | n |
| otrc-su-partial r2 | T | try/except | online | 48 | 27 | y (4-5) | n |
| otrc-su-partial r3 | T | try/except | online | 70 | 24 | y (7-13) | y (91) |
| otrc r2 | F | is_real domain | online | 46 | 46 | y (6, 24-29) | n |
| su-full r2, otrc r1, otrc r3 | – | no valid patch | – | – | – | y | – |

Caveat: `d05__b21k__ss/eval/...__r3/report.json` (Aug 31) says resolved=False, but it evaluated an earlier run_3 (boolalg.py + UniversalSet);
the current run_3 log (Sep 9) is the try/except one, matching the run table's True. Same date mismatch for ss r2 and su-full r2/r3.

## Bottom line

Does the evidence support "long uncompressed exploration leads to an over-engineered solveset design, and compression resets the agent to the
minimal try/except"? **No, not on this task.**

Contradicts it:
- In all 17 resolved threshold runs the try/except edit precedes the compression event; all 8 su/ss summaries already record the fix as done.
- The over-engineered designs were chosen at 10-17k context, below the budget; FC runs did not become over-engineered *because* they were long —
  they were long because they kept validating the wrong design.
- The two documented design changes (trc-ss r3 @50, trc-su r2 @79) go from gold to broken, and the second happens after compression; trc-style
  clearing preserves the plan and the summaries preserve it too (su-partial r2 carried "S.Reals for real symbols, S.Complexes otherwise").
- Compression's one visible behavioural effect (ss r1 @64) is a wasteful restart, not a simplification.

Supports it (weakly):
- The failure mechanism *is* "continued reading of solveset.py for a domain rule / self-imposed consistency with solveset" after the core
  bug is understood, i.e. over-engineering from extra exploration is real — it just is not gated by the 21k budget.
- The 5 non-fired runs (3 FC + 2) all fail and all reached the solveset design; but this is n=2 for compressed cells and both decided
  at ~11-15k, so it is consistent with the base failure rate (7/30 threshold runs) rather than with a compression effect.

Net: the fired/not-fired split on this task is a selection artefact (which runs got long enough to cross 21k), not a mechanism.
