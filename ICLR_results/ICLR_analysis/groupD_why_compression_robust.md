# Group D: why these 19 tasks stay solved under every compression policy

Scope: `ICLR_results/swebench/main/qwen35b` only (Qwen3.5-35B-A3B, P100 main
cells, 35 cells x 3 runs). Group D = 19 tasks resolved by FC and unresolved
under 0 of 12 compression policies. Evidence: `agent.log` (full pre-compression
history), `token_log.json` (compression_event_steps), `trajectory.json`
(submission), the per-cell `eval/*.json` reports, gold patches from SWE-bench
Verified, and `analysis/outcomes/swebench_outcomes.csv`. One investigation
agent per task (notes in `ICLR_results/ICLR_analysis/groupD_notes/`); cross-task numbers computed
directly over all 1613 compressed runs + 57 FC runs. Companion to
`ICLR_results/ICLR_analysis/groupC_fc_vs_compression.md`.

## 0. Headline

Group D tasks are robust not because the agent retains information across
compression but because **nothing needs to be retained**. In all 19 tasks the
complete solution state is a *pointer* (one file, one ~20-line window, a
1-6 line edit) that is re-derivable from message 1 (the PR description +
submit protocol, which every threshold primitive preserves) plus one
`grep`/`sed -n`. Compression therefore triggers a clean restart of a short,
deterministic localisation path that re-converges on an accepted fix. Three
further margins stack on top:

1. **Compression rarely fires at all.** Group D runs are short (median 35
   steps vs 63 for the rest of P100; FC peak context 17k vs 27-30k), so 59% of
   compressed-cell runs never hit the budget (76% at 20k, 52% at 15k, 38% at
   10k), and when it fires the first edit usually precedes it (70% of runs
   where compression fired).
2. **The product lives on disk, not in context.** After a wipe the agent
   re-reads the file, finds its own edit already there, and `git diff`
   regenerates the patch. Filesystem = external memory that no primitive
   touches.
3. **Wide acceptance basins.** In 12/19 tasks several textually different
   patches all pass FAIL_TO_PASS (only 48% of resolved submissions contain
   every gold `+` line), so a restart does not have to reproduce the earlier
   edit, only land anywhere in the basin.

Corrected for evaluation artifacts (section 5), Group D resolve is 0.97 over
1561 valid compressed runs; the 53 genuine failures are almost all
*termination/submission* failures with a correct fix already on disk (47/53),
not wrong reasoning, and 14 are the online-TRC task-description wipe bug
documented in the Group C report.

## 1. Task shape vs Group C and the rest of P100 (FC runs, task-level medians)

| | Group D (19) | Group C (9) | other (72) |
|---|---|---|---|
| FC steps | 37 | 63 | 58 |
| first edit step | 16 | 28 | 27 |
| distinct source files read before first edit | 1 | 2 | 2 |
| step at which the gold file is first opened | 2 | 2 | 3 |
| gold files == 1 | 19/19 | 7/9 | 90% |
| gold `+` lines | 3 | 4 | 5 |
| PR names the gold file (basename) | 53% | 44% | 28% |
| FC peak context (tokens) | 17.3k | 28.3k | 26.4k |
| tasks with FC peak < 15k | 37% | 0% | 11% |
| FC resolve | 0.98 | 0.81 | 0.32 |

Group C tasks are *also* one-file, gold-file-at-step-2 tasks (see the Group C
report). The discriminators are therefore not localisation but: (a) Group D
edits are re-derivable from the PR alone (in 11/19 the PR literally states the
fix: 11066, 12143, 12276, 10844, 12585, 13439, 14141, 14894, 15349, 24213,
18189 give file+line or the replacement text); (b) no negative evidence or
edit ledger has to survive; (c) the run is over before budget pressure.

## 2. Per-task summary

| task | gold | what the PR gives | env | FC steps / first edit / peak | comp fired | comp before edit (n, resolve) | resolve raw -> corrected | genuine fails |
|---|---|---|---|---|---|---|---|---|
| django-11066 | 1 line `using=db` | file+line+literal before/after | runner broken, F2P test absent; irrelevant | 7 / 3 / 4.7k | 1% | 0 | 1.00 -> 1.00 | 0 |
| django-12143 | `re.escape()` 1 token | file, line, buggy line, fix | pytz/asgiref missing, F2P not in repo; pure-`re` proxy | 24 / 9 / 8.5k | 18% | 0 | 0.85 -> 1.00 | 0 |
| django-12276 | move `use_required_attribute` | names class+method+line | 2 cheap traps; own repro works | 44 / 18 / 16k | 52% | 6 (1.00) | 0.88 -> 1.00 | 0 |
| django-14915 | add `__hash__` | class + "unhashable" symptom | asgiref; 6-line repro | 35 / 11 / 11k | 10% | 0 | 0.99 -> 1.00 | 0 |
| django-15741 | `str(format_type)` | function + exception | asgiref + settings; runner hunt is the sink | 65 / 38 / 21k | 53% | 13 (0.85) | 0.86 -> 0.92 | 6 |
| sklearn-10297 | kwarg + `super()` pass-through | class, TypeError, docstring promise | sklearn unimportable; static verify only | 41 / 20 / 24k | 64% | 12 (0.67) | 0.88 -> 0.91 | 7 |
| sklearn-10844 | replace one formula | file:line + "I propose ..." | unimportable; numpy proxy | 27 / 16 / 17k | 35% | 6 (1.00) | 0.82 -> 0.97 | 2 |
| sklearn-12585 | 1 line `isinstance(estimator, type)` | file, line, exact fix | unimportable | 39 / 16 / 25k | 58% | 10 (1.00) | 0.87 -> 1.00 | 0 |
| sklearn-13135 | `centers.sort()` | traceback + cause | unimportable; KMeans sim | 42 / 20 / 21k | 59% | 21 (0.86) | 0.80 -> 0.96 | 3 |
| sklearn-13142 | reorder 5 lines in `fit_predict` | title + repro | unimportable; pip sklearn already fixed | 46 / 24 / 25k | 64% | 34 (0.76) | 0.82 -> 0.91 | 6 |
| sklearn-13439 | `__len__` on Pipeline | title *is* the fix | unimportable | 45 / 28 / 16k | 54% | 19 (0.89) | 0.93 -> 0.95 | 4 |
| sklearn-14141 | add `"joblib"` to a list | symbol + fix | unimportable; textual verify | 20 / 7 / 11k | 13% | 0 | 1.00 -> 1.00 | 0 |
| sklearn-14894 | guard n_SV == 0 | file, function, line, expected result | unimportable; pip 1.9 already fixed | 49 / 25 / 30k | 57% | 26 (0.77) | 0.85 -> 0.87 | 10 |
| sympy-15349 | flip one sign | file#L489 + repro | mpmath 1 step; stale in-repo test | 25 / 9 / 13k | 46% | 8 (1.00) | 0.93 -> 0.94 | 5 |
| sympy-16450 | forward `assumptions0` | API + symptom | mpmath 1 step; 3-line repro | 34 / 15 / 19k | 62% | 11 (0.73) | 0.95 -> 0.96 | 3 |
| sympy-18189 | pass `permute=permute` | function + args + repro | mpmath 1 step; 4-line oracle | 37 / 11 / 19k | 47% | 19 (0.84) | 0.91 -> 0.95 | 4 |
| sympy-19954 | defer list deletes | traceback + repro | mpmath/pytest 1-3 steps | 22 / 12 / 13k | 35% | 4 (1.00) | 0.98 -> 0.99 | 1 |
| sympy-24213 | use `equivalent_dims` | traceback file+line + repro | mpmath 1 step | 24 / 10 / 12k | 20% | 1 (1.00) | 0.99 -> 1.00 | 0 |
| sympy-24661 | add `visit_Compare` | function + repro | mpmath 1 step; own repro | 43 / 20 / 22k | 71% | 9 (0.78) | 0.94 -> 0.97 | 2 |

"corrected" counts eval-report-resolved runs as resolved and drops eval-error /
missing-eval silent_crash rows (section 5). "genuine fails" = eval unresolved
or LimitsExceeded.

## 3. Mechanisms, with evidence

**M1. Message 1 is the whole spec and survives every threshold primitive.**
`msg1_wiped=False` in all TR/SU/SS/TRC/stacked runs; in 11/19 tasks the PR
text contains the fix (12585: "change base.py line 51 to `elif not
hasattr(estimator, 'get_params') or isinstance(estimator, type):`"; 10844:
"I propose to use `np.sqrt(tk / pk) * np.sqrt(tk / qk)`"; 11066 quotes the
before/after line). Post-compression steps literally restart from it
("Let me start by understanding the issue. According to the PR description..."
12585 su-full r1 s18; 14915 tr r3 s32) and re-converge.

**M2. Recovery is 1-3 idempotent commands.** Compression-before-edit runs
(199 in D, resolve 0.78 vs 0.38 in C) re-issue the same `grep -n`/`sed -n`:
24213 trc-su r1 comp@14 -> s15 `sed -n '150,220p'` -> s16 edit; 10844 trc-ss
r1 comp@28 -> s29 one `sed -n '855,865p'` -> s30 edit; 18189 tr r2 re-reads
the same 20-line window after each of 7 truncations. Median steps from first
compression to first edit: 6-7 (SU/SS, TRC-stack), 11 (TR).

**M3. State is on disk.** After amnesia the agent finds its own fix
("`ModelChoiceIteratorValue` already has a `__hash__` method", 14915 tr r3
s34; "the issue ... has already been fixed", 11066 trc r2 s13) and `git diff`
regenerates the patch. TRC additionally keeps assistant THOUGHTs, which in
this task class restate the whole diagnosis each turn (15741 trc r3 s35 lists
the line numbers; 24213 trc-su s14 names `equivalent_dims`), so clearing tool
bodies loses nothing.

**M4. Verification is either cheap and stateless or impossible and
irrelevant.** sympy/django tasks: a 3-10 line repro after a one-step
`pip install mpmath`/`asgiref` (the install persists in the container across
compressions). All 8 sklearn tasks: `/testbed` is unimportable (cpython-36
`.so` under py3.11) and `pip install scikit-learn` pulls a version that already
contains the fix, so **no sklearn run in any condition ever executed its own
patch**, including the resolved FC runs; agents verify by re-reading the file
or by a standalone numpy simulation. Because the edit is a literal
transcription of the PR, textual verification is sound, and the broken env
only inflates step counts.

**M5. Wide acceptance basins.** 12276: 6 distinct `use_required_attribute`
bodies all resolve, 43/78 additive-only patches resolve; 16450: five
mutually different patches, none textually gold, all resolve; 14141: 28/96
insert `"joblib"` at a different list index; 19954: no resolved run matches
gold syntax. Exceptions with a single narrow target: 11066 (103/103
byte-identical), 15349 (all resolved byte-identical; one wrong-sign-site
failure), 24213, 12143.

**M6. Summaries can be garbage at zero cost.** SU/SS summaries on D tasks show
the same pathologies as in Group C (verbatim echo of the last turn ending in
`p完成了`, 14141 ss-partial r2; spliced code blocks, 16450 ss r3; stale line
number, 12276 su-full r1) and the agent recovers because it re-reads ground
truth from disk on the next step. This is why SU/SS look fine on D: summary
quality is never load-bearing.

## 4. What still fails (53 genuine failures / 1561 valid runs)

| bucket | n | evidence |
|---|---|---|
| correct fix on disk, never submitted: termination loops after compression erased "I already did this" | ~22 | 16450 tr r1 `git log` 27x, trc r2 20x; 24661 tr r1 verified s27 then 96 steps of `git log --grep`; 15741 trc r2/r3; 13135 su-full r3 reads the upstream `centers.sort()` at s125 |
| OTRC wiped message 1 (submit protocol gone) | 14 | 15349 binf-otrc r3 / otrc-tr r3, 13439 otrc-tr b15k r1 / b20k r3, 19954 otrc-tr r2, 10844 otrc-su-partial x2: fix applied, then ~100x `echo "Task completed"`; one goal-drift case (10297 otrc-tr r2 invents a `_RidgeGCV` bug) |
| malformed submission (raw source / path-scoped diff / hand-typed patch) | ~10 | 14915 fc r2 + su-full r3, 12143 trc r2, 15741 tr r2 + ss-partial r2 (0 comps), 13439 ss r2 + su-full r2 (stale patch.txt), 14894 otrc-tr r1 + trc r3 (`diff -u` vs backup tree), 15349 su-partial r1 + trc-su r3 (`git diff <test file>`), 16450 otrc-ss-partial r3 (0 comps), 18189 binf-otrc r2, 24661 trc r2, 12276 tr r1 |
| self-revert after compression (`git checkout` own fix to "verify the original had the bug") | 3 | 13439 trc-ss b15k r2 + b10k r2; 13142 ss r3 (gold at s25, comp@29 ratio 0.22, checkout s32) |
| "already fixed" false belief, no submit | ~5 | 13142 x4 (reorder fix is indistinguishable from never-buggy, and pip sklearn passes); 24213 ss r3 |
| wrong fix | ~9 | 14894 x6 (`indptr = np.arange`, wrong guard variable; FC r3 made the same mistake at s17 and self-corrected at s34), 10844 trc r3, 18189 trc r2 + otrc-su-partial r1 (`merge_solution` lock-in), 15349 otrc-ss-partial r3 (m21 instead of m12) |
| env/step-limit with 0 edits | ~5 | 13142 tr r3 (140 steps on build trap), 14894 otrc-su-partial r2, 10297 tr x3 |

12 of the 53 have `n_comp == 0`, so at least a fifth of Group D's residual
failures are not compression effects at all. Resolve does decay with the
number of compression events (0.95 at 0, 0.88 at 2, 0.71 at 3-4, 0.53 at 5-8,
0.33 at 9+; the rest of P100: 0.58 -> 0.11), but the mechanism is
non-termination and protocol loss, never a lost diagnosis: 47/53 genuine
failures had an edit on disk.

By family: OTRC 26 genuine failures (20 LimitsExceeded), TR 9, TRC 6,
TRC-stack 8, SS 3, SU-partial 1. Threshold stacking (TRC+SU/SS) is the safest
on D (0.96-0.98) because TRC alone usually reaches the target and the
summariser never runs (`summarization_prompt_tokens: 0` in 24213/10844
stacked runs).

## 5. Data-quality findings (affect resolve rates, not just Group D)

Cross-checking the 142 outcomes-CSV failures against `<cell>/eval/*.json`:

| CSV label | eval says resolved | eval error (docker) | no eval file | eval unresolved |
|---|---|---|---|---|
| limits_exceeded (42) | 3 | 0 | 39 | 0 |
| silent_crash (69) | 39 | 17 | 13 | 0 |
| submitted_unresolved (31) | 4 | 13 | 0 | 14 |

- 46 "failures" are resolved per their own eval report (12143: 13 of 14; 12585:
  all 10; 13135: 11 of 16; 10844: 4 stale + 8 error). Review1.csv agrees with
  the eval report for 31 of them, so `analysis/outcomes/swebench_outcomes.csv`
  is the stale source. 30 more are `error_instances=1` (all in b20k cells,
  Aug 19 17:53 cluster) with gold-identical patches.
- 13439 `d05__b10k__tr/run_3`: on-disk log (125 steps, 10 comps,
  LimitsExceeded) does not match `experiment_results.json` run 3 (53 steps,
  Submitted, resolved); per-run log<->outcome joins in that cell are suspect.
- 24661 `d05__b10k__tr/run_3` scored resolved with `exit_status=LimitsExceeded`
  because the patch was captured from an `&&`-combined submit at s54.
- `info.submission` not starting with `diff` is a cheap detector for the
  malformed-submission bucket (21 D runs; 7 of them nonetheless resolved).
- In all sklearn D tasks the F2P test is never executed; 11066's F2P test does
  not exist pre-patch. "Verified before submit" in these logs means read-back.

## 6. Implications for the paper spine

- Group D is the floor case of "compression beyond the budget": the budget is
  rarely reached, and when it is, the task's information requirement is
  ~200 tokens held in message 1 + the filesystem. It shows what compression
  *cannot* break (a spec-given, single-site, disk-persisted fix) and what it
  still does break: the stopping rule and the submit protocol. The
  protected, append-only edit ledger proposed in the Group C report would
  also remove most of Group D's residual losses (self-reverts, "already
  fixed" loops, `git log` archaeology).
- The OTRC message-1 wipe is the single largest residual failure mode here
  too (14/53), reinforcing that OTRC cost numbers must be corrected before
  the token-cost claim.
- Any resolve-rate table built from `analysis/outcomes/swebench_outcomes.csv`
  understates D cells by ~5 points and the 20k cells more, because of the
  eval-error and dropout rows above; rebuild from the eval reports.
