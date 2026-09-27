# sympy__sympy-24661 — Group D, why compression-robust
82 runs, resolve 0.94; compression fired in 68%; median first-edit step 23.

## 1. Task shape: single-file, one-hop, self-locating
All 3 FC runs use the *identical* localisation: `find … xargs grep -l "def parse_expr"` →
`grep -n "def parse_expr" sympy_parser.py` → `sed -n '911,1100p'` → `sed -n '1100,1300p'`
(FC run_2 s1-6, run_1 s1-7, run_3 s1-5). Distinct source files opened before first edit: **1**
(`sympy/parsing/sympy_parser.py`) in all 3 FC runs; TR-b10k run_3 opened 2 (+`parsing/ast_parser.py`, s11).
Diagnosis is one command: `grep -n "ast.Compare" sympy_parser.py` → empty (FC run_2 s10) ⇒
`EvaluateFalseTransformer` has `visit_BinOp`/`visit_Call` but no `visit_Compare`. The only other
knowledge (`ast.Lt/Gt/LtE/GtE/Eq/NotEq` ↔ sympy `Lt/Gt/Le/Ge/Eq/Ne`) comes from one stateless probe
`python -c "import ast; print(ast.dump(ast.parse('1 < 2')))"`, run in every single run.
Working set = (path, lines ~1100-1250, 6-entry op map) — rebuildable in 1-2 commands. Gold is
re-derivable from PR text + that one file read.

## 2. Environment: one visible, self-healing trap
`import sympy` → `ModuleNotFoundError: No module named 'mpmath'` (FC run_2 s7); every run fixes it in
one step, `pip install mpmath -q` (FC run_2 s8, run_3 s9, TR-b10k run_3 s13, SS run_2 s9). No pytest;
`sympy.testing.pytest` / `sympy.test(...)` mostly fail (FC run_1 s30-32, run_3 s34-36, TR-b10k run_1 s28),
so agents verify with self-written repro scripts — also stateless and cheap. No run failed on env.

## 3. Compression before first edit (4 resolved runs) — clean restarts
- d05/b10k/TR run_3 (comp 18,23; edit 33): after truncation just re-runs `grep -n "Compare|Lt|…"` (s19),
  `ast.dump` (s20,24), `sed -n '1090,1190p'` (s21). Nothing pre-compression was needed.
- d05/b10k/SS run_2 (comp 18; edit 32): s19 `grep -n visit_Compare` (rc=1, empty), s20 `sed -n '1080,1200p'`
  — one read fully restores state.
- di/b10k/TRC run_3 (comp 16 = edit step, 33): unaffected, submits s38.
- di/b10k/TRC+SU run_1 (comp 18,26,34,35; edits 23,29): survived even a `git stash`/`stash pop` (s49-50).
Message 1 (PR description + submit instructions) is never wiped under any policy (msg1_wiped=False
everywhere): "what am I fixing" is never lost, only "what I already read".

## 4. Edit correctness
Gold = 23-line `visit_Compare` mapping 6 ast ops to `Lt/Le/Gt/Ge/Eq/Ne(evaluate=False)`. FC run_2's first
*and only* edit (s19) is exactly that + a `len(node.ops)==1` guard; same for TR-b10k run_3 (s33) and
TRC run_2 (s25/30) ⇒ first edit usually already gold-equivalent. Most runs *over-engineer*, adding
chained-comparison (`1<2<3` → `And(...)`) handling gold omits; that extension is where extra steps and
self-inflicted bugs live (SS run_2 hit an IndexError in its own chaining code and had to patch it).
FAIL_TO_PASS `test_issue_24288` covers only the 6 simple relations, so the extras are inert. Verification
is always the agent's own `test_issue.py` / inline `python -c` asserting type is `StrictLessThan`.

## 5. Failing runs (5)
- di/b20k/otrc-ss-partial run_3 (silent_crash, n_comp=0): bad edit s26 (`generic_visit` first, then guards on
  `isinstance(node.left, ast.Name|ast.Num)`); still `BooleanTrue` at s74; log ends mid-step, exit_status
  empty, api_calls 82 → infra death during its own debug loop. Not compression.
- di/b20k/otrc-tr run_1 (LimitsExceeded, n_comp=0): edit s28 copied the `visit_Call` idiom →
  `AttributeError: 'Compare' object has no attribute 'keywords'` (s29); never recovered, then repeated the
  *identical* `grep -n "LT|GT|LE|GE|EQ|NE" …` ~90× (s38-123) to the 125-step limit.
- d05/b20k/SS run_3 (silent_crash, comp 34): fix in place, printing its diff at s46 when the log truncates;
  exit_status empty, api_calls 48 → infra crash, fix was fine.
- d05/b10k/TR run_1 (LimitsExceeded, 10 comps): **the one genuinely compression-caused failure**. Correct fix
  verified at s27 ("The fix is working"), but repeated truncation erased the "I'm already done" state; s29-125
  wander through `git log --all --grep=22305/22098` hunting the upstream commit, never submits. submission=''.
- di/b10k/TRC run_2 (Submitted, unresolved): edit gold-equivalent and verified (s32), but submitted
  `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat …/sympy_parser.py | head -1260 | tail -70` — 70 raw source
  lines, no `--- a/ +++ b/` headers, unappliable. Protocol slip, not reasoning.
Anomaly: d05/b10k/TR run_3 is scored resolved but trajectory.json says exit_status=LimitsExceeded, submission='';
its correct patch was captured from the `Exit:` block at s54 (`git diff … > patch.txt && echo COMPLETE… && cat
patch.txt`, &&-combined so the harness did not terminate) and it then burned 80 more steps re-exploring.

## 6. Verdict
Solution state here is a *pointer, not a history*: one file path, one ~150-line region, a 6-entry AST→sympy op
map — all rebuildable from the never-compressed PR description with one grep + one sed + one `ast.dump` probe,
and verifiable by a 3-line stateless `python -c`. No policy can destroy anything the agent cannot cheaply
repurchase, so TR/SU/SS/TRC each just trigger a clean restart of the same deterministic 4-command localisation
— hence 0.94 resolve overall and 0.78 even when compression precedes the first edit. The limits are procedural,
not epistemic: (a) agents invent a chained-comparison extension beyond gold and burn steps debugging it,
(b) compression can erase the *termination* signal — TR-b10k run_1 held a correct, verified patch on disk and
still timed out because truncation repeatedly deleted the memory that it had already succeeded, and (c) a
malformed submission loses an otherwise-correct fix. For this task class compression threatens knowing *when to
stop*, not knowing *what to do*.
