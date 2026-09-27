# Group C: why FC solves these tasks but compression does not

Scope: `ICLR_experiments/swebench/main/qwen35b` only (Qwen3.5-35B-A3B, P100 main
cells). Group C = 9 tasks resolved by full-context (FC) but unresolved under
>= 6 of 12 compression policies. Evidence comes from `agent.log` (full step
history; `trajectory.json` only stores the post-compression remnant), the
gold patch / FAIL_TO_PASS from SWE-bench Verified, and
`analysis/outcomes/swebench_outcomes.csv`. Per-task deep dives were done by
one investigation agent per task; cross-task numbers were computed directly.

## 0. Headline

Group C tasks are not context-hungry: FC peak context is ~30k tokens
(median) vs ~25k for the rest of P100, so every P100 task exceeds the
10k-20k budgets. What distinguishes Group C is *what* the needed context
is. In every one of the 9 tasks the correct fix is small (1-6 lines, one
file), the PR/traceback suggests a plausible WRONG fix, and the environment
makes verification impossible or misleading. Success therefore depends on
keeping three kinds of low-salience memory in view until the edit/submit
step:

1. **Edit ledger** - "I already applied the fix" (the edited line looks like
   ordinary code; failing runs run `git diff` 0-2 times).
2. **Negative evidence** - "the build always fails", "the PR-literal
   placement already raised TypeError", "this test was failing before my
   edit", "reverting the compat files breaks the import".
3. **A template read early and needed late** - `"no_validation"` in
   `_base.py`, the `transform()` idiom 40 lines away, the `transform_*`
   naming convention, `__eq__`'s `if other == 0`, the pip-installed newer
   sklearn's `np.inf` line.

All compression primitives drop exactly these first (large build tracebacks
and old file reads for TR/TRC/OTRC; everything except a "plan" for SU/SS),
while the PR description with its misleading suggestion survives. FC
succeeds because it holds the full chain at decision time; its own failures
(26194 r1, 17318 r2, 11299 r1) show the same mechanisms, so FC's 2/3-3/3 is
partly luck against a strong wrong prior.

## 1. Environment traps are the common substrate (7/9 tasks)

| task | env trap | consequence |
|---|---|---|
| sklearn-9288 | testbed sklearn unimportable (cpython-36 .so under py3.11), build_ext fails, pip pulls 1.x | nothing can be executed; must edit blind |
| sklearn-10908 | same; pip sklearn lacks `get_feature_names` and already has the fix | no verification; false "already fixed" |
| sklearn-12682 | same | no test signal for a multi-site plumbing change |
| sklearn-25232 | no numpy in container; pip sklearn >= 1.3 already has `fill_value` | tests from /tmp PASS regardless of patch (false positive) |
| sklearn-26194 | same; pip sklearn 1.8 already has `np.inf` | the only evidence for the gold fix is an accidental leak from site-packages |
| sympy-14711 | default python 3.11 cannot import sympy (`collections.Mapping`); eval uses 3.9 | 15-50 step compat side-quest dirtying 5-14 files; only 1/75 runs found `conda activate testbed` |
| django-12304 | sandbox py3.11 vs eval py3.6: `boundary=` kwarg failure pre-exists | agent "fixes" a sandbox-only error; hard-coded `boundary=boundary` breaks eval (6/6 unresolved) |

The two remaining tasks (django-11299, sympy-17318) have no env trap but
share the misleading-prior property (harness invocation hunting; traceback
points at `radsimp` instead of `_sqrt_match`).

## 2. Per-task summary

| task | gold fix | wrong prior | dominant failure of compressed runs (n failing) |
|---|---|---|---|
| sklearn-26194 (FC 2/3) | `np.r_[np.inf, thresholds]` | PR says "clip to 1" | ~65/73 submit clip/min variants; 8/8 resolved patches contain `np.inf`, 0/73 failing do. Resolving requires a 3-link chain (testbed unimportable -> import resolves to site-packages 1.8 -> that source uses `np.inf`); links 1-2 live in build tracebacks that are dropped first; the surviving bare `inf` printout reads as the bug symptom. 17/57 compressed runs say "fix already applied" post-compression. |
| sympy-17318 (FC 2/3) | gate `split_surds` call inside `_sqrt_match` so it returns `[]` | traceback + hints point at `radsimp._split_gcd` | 60/73 submit a radsimp-only fix (incl. FC r2 and all 3 unlimited-OTRC); 11 never submit. 66/77 runs *read* `_sqrt_match`, only 5 patched it. Truncation snaps the plan back to the traceback frame (d05__b10k__tr r1: step 87 "fix in `_sqrt_match`", TR@90, step 92 "fix in `_split_gcd`"); SS summary fabricated a still-failing observation and the agent re-edited its own correct fix into a broken form. |
| sklearn-9288 (FC 3/3) | hoist `seeds=` above the `n_jobs` branch (6 lines) | none; env-trap | 38/41 LimitsExceeded: 19 never edited (20-60 build/pip attempts), 14 had the correct fix in tree at step 125 and never submitted, 7 drifted to unrelated edits. At 10k each ~3k-token build log refills the budget in 2-3 steps (15 compressions/125 steps); post-compression the agent retries builds it already saw fail. di__b15k__trc r2 says "fix has already been applied" 18 times, then claims the opposite. |
| sklearn-10908 (FC 2/3) | unconditional `if not hasattr(self,'vocabulary_'): self._validate_vocabulary()` in `get_feature_names` (copy of `transform()` idiom) | "trailing comma" red herring; `NotFittedError` not imported | 17 step-limit runs, 12 of them with the gold edit already in the file; 12 wrong submissions (conditional variant 4, NameError `NotFittedError` 3, validate in `__init__` 2, ...). SU summary in d05__b15k__su-full r2 is ~100 lines of fabricated `raise NotFittedError` code; 22 steps then hallucinate `[user] <output>` blocks. OTRC: 59 consecutive identical `build_ext` commands. Runs that lost the `transform()` view before editing wrote the conditional variant. |
| sklearn-25232 (FC 3/3) | 4 edits incl. `_parameter_constraints["fill_value"] = "no_validation"` | none; token lives in `_base.py` | 19 complete patches with an invented constraint (`["no_validation"]`, `["array-like", None]`, `"number"`, ...); in 16/19 the `_base.py` read was already evicted at write time (OTRC clears after 4 steps by construction). 18 empty-patch loops. Verification is a false positive (pip sklearn already has the feature), so the error is never caught; only 3 runs ever saw the real validation error. |
| sklearn-12682 (FC 3/3) | add kwarg named exactly `transform_max_iter`, store via `_set_sparse_coding_params`, pass to `transform` | name unstated; two other positional callers | 10 wrong-name (`max_iter`) patches, ALL in TRC/OTRC cells; 9 broken plumbing (positional insert breaks DL/MBDL, deleted `self.n_components` while editing by line offset with the file out of view, then "patch looks correct"); 10 re-read loops with 0 edits (all 3 d05__b10k__tr). SU r3 had every site edited by step 57, summary@60, step 88 "SparseCoder already has `transform_max_iter`... so I need to add `transform_tol`". |
| django-11299 (FC 2/3) | pass `simple_col` into recursive `_add_q` call (1 token) | PR points at SQLite/migrations; runtests invocation non-obvious | 25 LimitsExceeded; **18 applied the exact gold edit and never submitted** (17 still in tree at 125). Post-compression restarts from the PR ("Let me understand the issue from the PR description" opens 5/10 post-compression steps in d05__b10k__tr r3); harness lesson learned at step 79 is gone after compression@83 -> 37 wrong invocations. SS summary says "Files Modified: None" though the edit existed since step 94. 38x identical grep across 3 compressions. |
| django-12304 (FC 3/3) | `cls.do_not_call_in_templates = True` in `ChoicesMeta.__new__` | PR literally says "declare on the Choices classes" (class body -> Enum member -> TypeError) | 10 class-body submissions (4 with zero compression events -> model prior), 6 `boundary=boundary` (5/6 compressed before edit), 6 OTRC runs with the task message wiped (see 4). Truncation removed five failed class-body attempts (d05__b20k__tr r1 steps 12-26), so the agent then "fixed" the sandbox-only boundary error. FC r2 did `git stash`/runtests/`stash pop` to prove the failure pre-existed. |
| sympy-14711 (FC 2/3) | `if other == 0: return self` in `Vector.__add__` | traceback misread as `sympy/vector`; compat side-quest | 8 runs submitted the correct fix PLUS 3-14 compat files (all 40 resolved runs submitted vector.py only; 8/8 with compat files failed: NameError `Iterable`, DeprecationWarning-as-error). 9 compat-thrash step-limit runs (>= 5 with correct edit in place), 5 wrong-module drift (0/125 steps touch physics/). SU summary: "primary objective is to fix Python 3.11 compatibility... secondary objective to fix Vector". TRC: revert -> import fails -> re-apply -> revert loop across compressions. Capped outputs mean no compressed run could see the whole diff it submitted. |

Across the 383 failing compressed runs, the buckets are roughly: submitted a
plausible-but-wrong fix that follows the PR/traceback prior (~150, dominated
by 26194 and 17318); correct fix present in the working tree but never
submitted or submitted with collateral (~70); invented/incomplete variant of
a template that was out of view (~50); no edit at all, re-read/build loops
until the step limit (~80); infra kills / label anomalies (~35).

## 3. Primitive-specific pathologies (with evidence)

- **TR (truncation)**: drops the oldest turns = early file reads and the
  agent's own failed attempts. At 10k it fires every ~5 steps, producing
  restart loops ("Let me start by understanding the codebase", d05__b10k__tr
  in 12682/25232/9288: 0 edits in 125 steps, 122 read commands) and plan
  flips back to the traceback frame (17318).
- **SU / SS (LLM summaries by the same Qwen)**: the summary is frequently not
  a summary: a role-played assistant turn with a fabricated tool output
  (11299 su-full r2, 17318 ss r2 "Error: tuple index out of error (still in
  progress)"), a task rewrite (14711 "fix Python 3.11 compatibility"; 11299
  "understand Django's test infrastructure", "Files Modified: None"), a
  stale-correctness claim ("All tests passed", "issue is already fixed"), or
  ~100 lines of repeated hallucinated code (10908). Consequences: the agent
  re-edits its own correct fix, drifts to `transform_tol`, or spends the rest
  of the budget re-verifying. Format-error bursts (6-22 consecutive
  "Expected exactly 1 action, found 0") follow summaries in several runs,
  because the model answers the summary with prose.
- **TRC / OTRC (tool-result clearing)**: keeps the agent's thoughts but
  removes what they refer to, so the model copies its previous turn: 59
  consecutive identical `build_ext` (10908 binf otrc r3), 38x identical grep
  (11299), 14x identical `sed -n` with byte-identical THOUGHT (25232), 25-49
  `echo "Task complete"` steps without ever submitting. Edits made with the
  file view cleared produce wrong names (12682: all 10 `max_iter` patches in
  TRC/OTRC cells), invented constraints (25232: 10/19 in OTRC), and
  off-screen global seds.
- **Format errors** are a background nuisance in every condition including FC
  (~0.5-1.5 per 100 steps) and are only weakly clustered after threshold
  compressions; they are 2-3x more frequent in OTRC state and burst after
  SU/SS summaries.

## 4. Harness bug: online-TRC can wipe the task description (verified)

`mini-swe-agent/src/minisweagent/agents/default.py` (online TRC hook)
overwrites `self.messages[-9]` by position, assuming strict assistant/user
alternation. A format-error turn inserts an extra user message (and
threshold compression changes list length), so the target can land on
`messages[1]` = PR description + submission protocol, which becomes
`[tool-result cleared — online-trc — N tok — step 0]`.

Across all qwen35b main OTRC cells (from trajectory.json remnants):

| cell | wiped / runs | resolve (not wiped) | resolve (wiped) |
|---|---|---|---|
| di__b10k__otrc-tr | 111 / 300 | 0.57 | 0.00 |
| di__b10k__otrc-ss-partial | 4 / 88 | 0.75 | 0.00 |
| di__b10k__otrc-su-partial | 2 / 100 | 0.69 | 0.00 |
| di__b15k__otrc-tr | 25 / 300 | 0.49 | 0.00 |
| di__b15k__otrc-ss-partial | 21 / 300 | 0.51 | 0.00 |
| di__b15k__otrc-su-partial | 29 / 300 | 0.54 | 0.00 |
| di__b20k__otrc-tr | 12 / 300 | 0.50 | 0.00 |
| di__b20k__otrc-ss-partial | 9 / 250 | 0.56 | 0.00 |
| di__b20k__otrc-su-partial | 4 / 245 | 0.56 | 0.00 |
| di__binf__otrc | 8 / 300 | 0.53 | 0.00 |
| **all** | **225 / 2483 (9%)** | **0.544** | **0/225; 75% LimitsExceeded** |

Wiped runs solve whatever problem is still visible (e.g. the py3.11
`boundary` error in 12304) and never issue the submit command. This
depresses every OTRC cell, most severely di__b10k__otrc-tr (cell mean ~0.36
vs 0.57 for unaffected runs). Fix: locate the clear target by scanning for
the oldest *user tool-result* message outside the freeze window (skip
index 1 and any format-error / summary messages) rather than by fixed
offset, and re-run or exclude the affected runs.

## 5. Data-quality notes

- `failure_mode == silent_crash` mislabels runs that submitted: in qwen35b
  main, 134 of 1121 silent_crash rows have `trajectory.json`
  `exit_status == "Submitted"` with a patch; 5 of those in 12682 have patches
  equivalent to FC-resolved ones. The evaluation apparently did not complete.
- Real infra kills cluster in time (10908: d05__b15k__ss r2+r3 at Sep 7
  20:32-33; d05__b20k__ss r1 + di__b15k__trc-su r2 at Aug 19 17:53); several
  had the gold edit in place. They are censored runs, not agent failures.
- Possible eval noise worth re-running: django-12304 d05__b20k__ss r3
  (module-level patch semantically identical to resolved FC r1).
- Submission-format slips exist in FC too (11299 FC r1 submitted a 5-line
  `sed -n` snippet; 14711 di__b20k__trc-ss r3 and 12682 di__b15k__trc r2
  likewise), so `Submitted`/unresolved is not always a wrong patch.
- mini-swe-agent's output cap (~10.6k chars) truncates `git diff` /
  `cat patch.txt`, so long-diff runs (14711) never see the full diff they
  submit.

## 6. Implications for the paper spine

- The "compression beyond the budget" phenomenon in Group C is a
  *memory-of-negative-evidence and edit-ledger* effect, not a raw context-size
  effect. A cheap mitigation that all primitives lack is a protected,
  append-only scratch record of (files edited, commands known to fail,
  templates copied) that survives compression; TRC-family primitives lose
  it by clearing results, SU/SS lose it by hallucinating the summary.
- Threshold stacking (TRC+SU, TRC+SS) wins on resolve rate in these tasks
  mainly because TRC delays the first summary and the summary then has fewer
  raw tracebacks to garble; it does not fix the ledger problem (12682 trc-su
  r2, 17318 trc-su r2 show the same "fix already applied?" loops).
- OTRC numbers need correction for the bug in section 4 before being used
  for the token-cost claim.
