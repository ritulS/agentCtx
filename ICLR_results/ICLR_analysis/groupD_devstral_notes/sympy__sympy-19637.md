# sympy__sympy-19637 — why compression-robust (Devstral-24B, ICLR_results/swebench/main/devstral24b)

Outcome: FC 3/3. Compressed 35/36 resolved; **threshold compression fired in 0/24 threshold-cell runs**; OTRC clearing active in 12/12 OTRC runs (23–120 clears); 1 no-submission run (otrc-ss-partial r2, LimitsExceeded @124); 0 msg[1] wipes. One eval artifact (otrc-su-partial r2: eval-dir json = `error_ids`, re-evaluated 2026-09-11 → resolved, `experiment_results.json` `resolved: True`).

## 1. Task shape: the PR is the fix spec
PR text = 4 lines: `from sympy.core.sympify import kernS`, the input `"(2*x)/(x-1)"`, the failing line `// hit = kern in s`, and `UnboundLocalError: local variable 'kern' referenced before assignment`. File (`sympy/core/sympify.py`), function (`kernS`), line and exception are all named. Gold = 3 lines: indent `hit = kern in s` into the `if ' ' in s:` block and add `else: hit = False`. FAIL_TO_PASS `test_kernS` adds exactly the PR example (`assert kernS("(2*x)/(x-1)") == 2*x/(x-1)`).

Canonical path, identical in all 39 runs (`files_before_edit=1`, `gold_first_open=1` everywhere): `ls`/`find sympy -name "*sympify*"` (steps 1–3) → `cat sympy/core/sympify.py` (step 3–7; head/tail-elided, "7463 characters elided", `kernS` body lands in the tail) → write repro script from the PR (step 4–7) → `python repro.py` → `No module named 'mpmath'` → `pip install mpmath` (31 runs) or `pip install -e .` (9 runs; 1 run did both) → repro prints the `UnboundLocalError` (all 39 runs, 1–16 occurrences each) → `grep -n "hit = kern in s"` / `sed -n '490,530p'` → edit. First source edit: median step 13 (range 6–24); FC median 11, threshold cells 13, OTRC 14.5. Diagnosis is stated before any edit in every run, e.g. fc r1 step 5: "`kern` ... is only assigned inside an `if` block (`if ' ' in s:`), but it's referenced later ... `hit = kern in s` ... If the `if ' ' in s:` condition is False, `kern` will never be assigned".

## 2. Environment: real oracle available, and it was used
- `/opt/miniconda3` Python 3.11.5; sympy is pure Python, importable from `/testbed` once `mpmath` is installed (network works: `pip install mpmath`, `pip install pytest` succeed; pytest-9.1.1).
- The repro script is a **true oracle**: every run saw the `UnboundLocalError` before the edit and its disappearance after. 38/39 runs also ran `pytest sympy/core/tests/test_sympify.py` (41 passed, 2 failed) and 33 ran `::test_kernS` / `-k kern` alone; some called `test_kernS()` by direct import (otrc-ss-partial r3 step 41, otrc-tr r3 step 20).
- Only traps: (a) two pre-existing failures `test_evaluate_false` (39 logs) and `test_issue_17811` (33 logs); runs that checked with `git stash` (trc-su r2 steps 47–53, otrc r1 steps 29–31) confirmed they fail on the clean tree; nobody was derailed. (b) `git checkout sympy/core/sympify.py` returns rc 255 with "error: unable to create file ... File exists" while still printing "Updated 1 path from the index" — the restore works; some runs re-issue it (otrc-tr r2 steps 20–21). (c) sed quoting/indentation is the real step sink (see §3), independent of compression.

## 3. Timing: no threshold event ever fired; OTRC clears from step 5
**Why context stays under 21k.** The trigger is `memory.count_tokens(self.messages)` = cl100k count of message text, checked before each model call; `step_prompt_tokens` is Devstral's server-side count (system prompt + chat template). Two facts keep the estimate below 21,000:
1. Observations are capped: `mini.yaml` keeps `output[:5000]` + `output[-5000:]` chars, so the 540-line `cat sympify.py` costs ~2.9k tokens (fc r1: 2947 → 5807 at step 5) and every later `sed -n` window / script output is a few hundred tokens. Growth is 300–720 tok/step (median ≈ 460), i.e. ≥42 steps are needed to reach 21k from the 1.4–1.7k start.
2. Runs are short (20–65 steps; median 33) because the one-line fix is verified by the repro script within ~5 steps of the edit.

Server-side peak exceeded 21k in 4 runs, always on the **final (submit) step**; the cl100k estimate at that point was still below the budget:

| run | server peak (last step) | cl100k(final msgs) | steps |
|---|---|---|---|
| trc-ss r1 | 21935 | 20582 | 29 |
| su-full r3 | 21732 | 20811 | 46 |
| trc-su r1 | 21557 | 20382 | 65 |
| ss-partial r1 | 21303 | 20446 | 55 |

So the 24 threshold-cell runs are, mechanically, FC runs; `token_log.compression_event_steps=[]` in all of them.

**OTRC (12 runs)**: first clear at step 5 (`flag_from_step 0`), then every step. The `cat` at step 4/5 is cleared at step 9/10 and **all 12 runs immediately re-read the function with `sed -n` at steps 9–14** (otrc-tr r1 9–10, otrc-ss-partial r3 10–14, otrc r2 11–13). Family means: re-reads 13.8 (OTRC) vs 6.0 (threshold cells) vs 8.3 (FC); steps 49 vs 37 vs 38; edit commands 6.7 vs 3.5 vs 6.0; restores 1.7 vs 1.0 vs 1.7. The window costs steps, not information.

Concrete post-clearing recoveries:
- **otrc-tr r1** (28 steps, gold-identical fix): cat@4 cleared at 9 → step 9 `sed -n '490,520p'`, step 10 `sed -n '516,530p'` ("Now I understand the issue! The code only assigns to `kern` inside the `if ' ' in s:` block ... tries to use `kern` in line 516 regardless"), step 11–12 `/testbed/fix.py` → V2 (= gold), step 13 repro passes, 20 `pytest ::test_kernS`, 28 submit. Re-grounding tax: 2 steps.
- **otrc r2** (binf, 87 steps, resolved): 14 `sed -i '510i kern = None'`, 16 botched multi-line `sed c\`, 18 `git checkout`, 19 `fix_kernS.py` (regex no match, prints "Fix applied successfully"; repro still fails at 20), 25–26 v2 same, 34 sed insert, 37 still fails, 44 inserts after `while True:` (line 499), 47 inserts after `hit = False` (line 477, wrong indent → IndentationError at 49/54), 58 repro passes; 75 `git diff` shows three `kern = None` sites → 76 `git checkout`, 77 re-apply with a literal `\n` (import error 79), 80 checkout, 81 `apply_fix.py`, 84 passes → V5. Each retry re-read a fresh `sed -n` window because the previous one had been cleared.
- **otrc-ss-partial r3** (49 steps): 15 sed on a non-matching line (no-op; repro still fails 16), 20 `kern = None` after `hit = False` (L471) → 22 `TypeError: 'in <string>' requires string as left operand, not NoneType`, 25/27 sed on wrong line numbers (no-ops), 31 correct line 517 `hit = kern is not None and s.find(kern) != -1`, 33 passes, 41 `test_kernS()` passes. V13.
- Threshold/TR cells show the same churn without any compression: **tr r3** 10 sed quoting error, 11 python edit, 12 `ImportError` (bad indent), 14 `mv backup`, 15 quoting error again, 18 python edit, 20 `TypeError`, 23 `mv backup` fails ("No such file"), 25 `git restore`, 27 python edit, 29 passes (V11). **ss r3** 11 sed, 13 view, 14 `git checkout`, 16 sed, 18 `git checkout`, 19 python edit, 21 passes (V4). **FC r3** is the worst churner of all: 8 edit commands, 5 restores, first pass at step 41 (V22).

## 4. Edit correctness: 23 textually distinct fixes, 38/38 submissions pass
Core `sympify.py` hunks cluster as (n = submitted runs):

| class | variant | n | why it passes |
|---|---|---|---|
| gold | indent + `else: hit = False` (V2) | 6 | = gold |
| indent-only | indent `hit = kern in s` (V0) | 3 | `hit = False` already set at function top (L471) |
| None-guard | `kern = None` + `hit = kern is not None and kern in s` / `s.find` / `if kern is not None:` (V3,5,13,15,18,19,23) | 13 | guard short-circuits |
| None+indent | `kern = None` + indent (V8,9,14,16) | 5 | as gold |
| sentinel | `kern = ""` (V10) or `kern = "_"` hoisted before the `if` (V1,11,17,20,21,22) | 9 | `"" in s` → `hit=True` but `expr.subs({Symbol(''):1})` is a no-op; `'_' in s` is False for the test strings |
| hit=True | `hit = True` inside the `if` (V4,6,7) | 3 | relies on top-level `hit = False` |

Acceptance basin: anything that (i) removes the unbound read and (ii) leaves the space-kern substitution path intact passes `test_kernS` + 40 PASS_TO_PASS. `gold_cov` is therefore meaningless here (0.0 for 21 resolved runs). Wrong-but-plausible variants exist in principle — `hit = False` unconditionally, or deleting the `if ' ' in s:` line — but the only one ever created (otrc-ss-partial r2 step 26, see §5) was caught by `pytest ::test_kernS` (`Interval(-1,-2 - 4*(-3))` → `EmptySet`) at step 36 and reverted at 47. No submitted patch touched any other file.

## 5. Failing / no-submission runs
Only one of 39.

**di__b21k__otrc-ss-partial/run_2** — LimitsExceeded @124, no submission. Classification: **step-limit loop (edit-placement/indentation loop), OTRC-amplified; not a harness bug** (msg[1] intact; 120 clears).
- 14–31: `kern = None` at L510 + `hit = kern is not None and kern in s`; sed hits the wrong line (19: guard landed inside the `for` loop), 20 checkout, 23–24 redo, **26 `sed -i '511d'` deletes the `if ' ' in s:` line** (agent thought it was removing a mis-indented `kern = None`), 31 repro passes (kern substitution now unconditional).
- 36 `pytest ::test_kernS` FAILS; 40–43 debug ("kernS result: EmptySet"), 46 `git diff` shows `-if ' ' in s:` / `+kern = None`, 47 `git checkout`. Correct diagnosis, correct revert.
- 49–125: 24 insertions of `kern = None` at 12/16/20 spaces into lines 506–515 (inside the `while True:`/`for j` loop bodies), each followed by a 6–9-line `sed -n '507,515p'`/`cat -A` window, 7 more checkouts (57, 65, 72, 84, 103, 109), 2 repro runs (94, 122) both still `UnboundLocalError` because the inserted line sits in a loop body never executed for `(2*x)/(x-1)`. Beliefs are wrong by construction: step 94 "correct indentation level (12 spaces)", step 122 "(16 spaces), inside the `if nest == 0:` block" — `if ' ' in s:` is at 8 spaces. No `git diff` after step 46.
- OTRC's role: the two full-function reads (44, 123) are cleared 5 steps later; the final live context (msgs 230–250) contains only cleared markers and 6-line windows, so the enclosing-block structure is never in view when an indent is chosen. The wrong indentation model is the agent's, but the window prevents it from ever being corrected by a wide read.

**di__b21k__otrc-su-partial/run_2** — resolved (V5, identical to 6 other resolved runs); listed only because `eval/devstral-2.sympy__sympy-19637__otrc-su-partial__r2.json` has `error_ids=[task]` (harness error on first eval). `experiment_results.json` carries `reevaluation.report_path` (2026-09-11) and `resolved: True`. Eval artifact, not an agent failure.

## 6. Verdict
This task is robust because the whole solution is in message 1: file, function, line and exception are named, the fix is one line with a very wide acceptance basin (23 distinct patches, all pass — the top-level `hit = False` even makes the indent-only edit correct), and sympy is importable, so the PR example is a real oracle that every run used before submitting. Compression never had a chance to matter: with observations capped at 10k chars and ~460 tokens/step, a 20–65-step run peaks at 13–22k server-side and the cl100k trigger estimate never crossed 21,000, so all 24 threshold-cell runs ran as full context. OTRC's 5-step window does bite — the `cat` is gone by step 9 and every OTRC run re-reads the function (13.8 vs 6 re-reads, +12 steps on average) — but the lost content is regenerable with one `sed -n`, so 11/12 OTRC runs still resolve. What breaks it is not forgetting the task but an edit-placement loop: when the agent holds a wrong indentation model, stops running `git diff`, and the window hides the enclosing block, it can burn 78 steps inserting one line into the wrong loop body (otrc-ss-partial r2). The same sed/indentation churn exists in FC (fc r3: 8 edits, 5 restores) — compression only removes the wide view that would have ended it.
