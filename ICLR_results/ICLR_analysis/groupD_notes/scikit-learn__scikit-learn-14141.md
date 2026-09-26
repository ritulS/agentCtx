# scikit-learn__scikit-learn-14141 — why compression-robust (Group D)

Fix = one line: add `"joblib",` to the `deps` list in `_get_deps_info()`, `sklearn/utils/_show_versions.py`.
96/96 qwen35b runs Submitted + resolved (also 39/39 devstral24b, 39/39 glm47flash = 174/174).

## 1. Task shape — PR description IS the localization
PR text names the symbol (`show_versions`) and the fix ("joblib should be added to the dependencies listed").
All 3 FC runs use the same 3-move opening: `ls` -> one grep for `show_versions` -> `cat sklearn/utils/_show_versions.py` -> edit.
**Exactly one source file is opened before the first edit** in every FC run. Extra reads are confirmatory, not
localizing: setup.py (run_1 s4, run_2 s6), ISSUE_TEMPLATE.md (run_3 s6), `grep -r "import joblib"`.
First edits: run_1 s5, run_3 s7, run_2 s10 (run_2 detoured into build attempts first).
Gold is fully re-derivable from (PR description + one file read). Search state is worth ~0 tokens.

## 2. Environment — trap present, irrelevant
`/testbed` sklearn is NOT built: `ModuleNotFoundError: sklearn.__check_build._check_build` (only a
`cpython-36m` .so exists, interpreter is py3.11). FC run_1 s8 hits it; s9/s11 `python setup.py build_ext --inplace`
fails (Cython + `_distutils_hack` `AssertionError: /opt/miniconda3/lib/python3.11/distutils/core.py`).
`pip install numpy cython` (s10) does not help. FAIL_TO_PASS test is therefore **never runnable** in any run.
It didn't matter: the agent verifies by *reading the file back* (s15-s17 `sed -n '40,55p'`, `grep -A10 "deps = \["`),
then `git diff > patch.txt`, `cat patch.txt`, submit (s18-s20). For a literal list insertion, textual
verification is sound — this is the key reason the broken env costs nothing here.
The build failure is also the sole token driver: it is the 2865-token tool output at step 12 that pushes
trc-ss run_2 over 10k.

## 3. Compression before edit: none; compression at all: rare
Only 12/96 runs ever compress, **all at budget 10k** (max step_prompt_tokens over all runs ~10.4k).
At 15k and 20k the whole trajectory fits — compression is a no-op for the entire depth/budget grid above 10k.
All compression events land at steps 13-20, i.e. 5-15 steps *after* the edit (median first-edit step 6).
`di__b10k__trc-ss/run_2` (edit s8, comp s13+s24): TRC replaces tool outputs with
`[TOOL OUTPUT CLEARED — N tokens — step k]` but keeps system + the 5660-char PR message + all assistant
reasoning. Recovery = re-read disk: s16 `grep -A10 "def _get_deps_info"`, s18 `cat _show_versions.py`,
s25 `git diff`, s28 submit. Nothing from before the compression was needed.
`d05__b10k__ss-partial/run_2` (edit s5, comp s15): after compression only 3 messages remain
(system, PR description, one "summary"). **The injected SS summary is corrupted** — it is a verbatim echo
of the previous assistant turn with a mangled tail: `<returncode>0</0</returncode>` ... `"p完成了`.
`d05__b10k__su-full/run_1` (comp s14) is the same pathology: `[COMPRESSED HISTORY SUMMARY]` is a 558-char
verbatim echo, not a summary. Both still resolve. In su-full the agent re-reads and says
"joblib is already in the deps list" — a clean amnesic restart that re-derives state from the filesystem,
recognizes the work is done, and does **not** double-insert (every submission has exactly one `+joblib` line).

## 4. Edit correctness — first edit always final, and position-free
The first edit is the only edit in every run (edit_steps is a singleton everywhere). No run ever revises it.
But only **68/96 submissions are byte-identical to gold**. The other 28 insert `"joblib",` at a different
index in the same list: 23 after `"scipy"`, 2 after `"Cython"`, 1 after `"sklearn"`, 1 identical-but-headerless.
All pass, because FAIL_TO_PASS `test_get_deps_info` only asserts key presence in the returned dict —
the list is order-insensitive. One run (FC-family) also edited `ISSUE_TEMPLATE.md` (the PR's second, optional
suggestion); the extra hunk is inert w.r.t. the test. So the task has a whole *family* of gold-equivalent fixes.

## 5. Failing runs
None. 0 failures in the qwen35b 96-run grid (and 0 in devstral24b / glm47flash).

## 6. Verdict
Robustness is over-determined by four independent margins. (a) The prompt-resident PR description is itself
the full spec AND the localization, and no primitive evicts it — the only irreplaceable context is
structurally immune. (b) Working set = one file reachable in one grep, so post-compression recovery costs
1-2 commands and is indistinguishable from a fresh start. (c) The product lives on disk, not in context:
amnesia is repaired by `grep`/`git diff`, and the agent can tell done from not-done by reading, so it
neither redoes nor double-applies the edit. (d) Acceptance is a loose equivalence class (any list position),
a large target for a degraded agent. The one thing compression could have broken — verification — was
already broken by the unbuildable env, and the textual fallback is compression-proof. Limit: this task never
stresses compression. At 15k/20k the primitive never fires; at 10k the summarizers emit demonstrable garbage
(verbatim echoes, `p完成了`) at zero cost. A floor case — not evidence that SU/SS preserve information, but
that when the spec is un-evictable and the state is on disk, summary quality is irrelevant.
