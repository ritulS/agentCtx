# django__django-15741 — why compression-robust (Group D)
81 runs, resolve 0.86; compression fired in 51%; median first-edit step 27.
## 1. Task shape: single-file, single-line, PR names everything
PR gives module (`django.utils.formats.get_format`), exact exception (`TypeError: getattr(): attribute name must
be string`) and trigger (lazy arg). Gold = one line `format_type = str(format_type)`. Fully re-derivable from
**PR text + one `sed -n '100,145p' django/utils/formats.py`**: that read shows `getattr(module, format_type)`
(L128) and `getattr(settings, format_type)` (L134) — the whole diagnosis. Files FC opened before first edit:
run_3 3 (formats.py, encoding.py, global_settings.py) + `git show 659d2421c7adb`; run_1 5; run_2 4. Everything
past formats.py is a detour — the agent hunts for `force_str`'s definition instead of just using `str()`. Search
fan-out ~0: step 1 in all 3 FC runs is `find|xargs grep -l get_format`, which lands on formats.py at once.
## 2. Environment: reproducible, but the test runner is a trap
`python reproduce_issue.py` → `ModuleNotFoundError: asgiref` (FC r3 s14), fixed by `pip install -e .` (s15) or
`pip install asgiref` (trc-ss r2 s11); then `ImproperlyConfigured: Requested setting USE_I18N` (s16). Escapes:
in-script `settings.configure(...)`, or `DJANGO_SETTINGS_MODULE=django.conf.global_settings` (FC r3 s29).
**Trap**: `/testbed/tests/settings.py` doesn't exist (Django uses `tests/runtests.py`), so `find -name
settings.py -path "*/tests/*"` yields only per-app fixtures. Only FC r1 found the real runner (`cd
/testbed/tests && python runtests.py i18n.tests.FormattingTests`, s58-62). Biggest step sink; proximate cause
of 3 of 11 failures.
## 3. Compression-before-edit recovery = a 1-command re-read
trc-ss b10k r2 (comp @21,38,46,49,50,51; edits @27-34; resolved): comp@21 hit mid-`force_str` lookup; s22
re-runs `grep -n getattr formats.py`, s23 re-runs `sed -n '100,145p'` — state restored in 2 cheap commands, no
back-reference to anything pre-21. trc b20k r3 (comp@35, edit@36): TRC clears tool *outputs* but keeps assistant
turns, and the agent's own s35 THOUGHT restates the diagnosis with line numbers ("1. L117 cache_key… 2. L128
getattr(module, format_type)… 4. L134"), so the s36 edit needs nothing that was cleared. **Mechanism: the agent
restates the full diagnosis in every THOUGHT = a rolling self-summary; compression deletes only regenerable tool
output.** msg[1] (PR description, 5867 chars) survived in all 13 compressed runs (msg1_wiped=False) — the one
non-re-derivable item is never dropped. Post-compression behaviour is a clean restart that converges anyway.
## 4. Edit correctness: first edit is already gold-equivalent everywhere
Two accepted spellings: gold's `format_type = str(format_type)` (FC r2 s46, ss-partial b20k) and
`force_str(format_type)` + added `from django.utils.encoding import force_str` (FC r1/r3, trc-ss r2, trc b10k);
position varies (gold after `lang = get_language()`, agents as first statement) — both pass. No run ever produced
a wrong fix. Verification = hand-written `reproduce_issue.py` with `settings.configure`; only FC r1 ran real
`runtests.py`. Most steps go to `sed -i` line-number fumbling (FC r3 s39→42 rewrites via /tmp/fix.py; FC r2 does
`git checkout formats.py` twice at s53/s57 to undo bad inserts).
## 5. Failing runs (11) — 9 of 11 had a gold-equivalent fix on disk and still scored 0
- d05_b15k_tr r2 submitted_unresolved: correct fix in tree; submitted `cat formats.py|head -150|tail -50` not a diff.
- d05_b20k_ss-partial r2 submitted_unresolved, **n_comp=0**: printed the exact gold diff at s37, then submitted file text.
- di_b10k_trc r2 limits_exceeded: gold-equivalent `git diff` at s70 + "the fix is working", 54 more re-verify steps, never submitted.
- di_b10k_trc r3 limits_exceeded: fix applied and verified ("Testing get_format → Result: N j, Y"), never submitted.
- di_b15k_trc-ss r1 limits_exceeded: 15 edit steps, ends looping on `find settings.py` / `ls tests/i18n/`.
- d05_b20k_ss r2 limits_exceeded: fix in tree, ends in the settings-module hunt loop.
- d05_b15k_su-full r1 silent_crash (exit_status=''): fix in tree, rabbit-holes into `get_format_lazy = lazy(get_format,…)` to s100.
- di_b10k_otrc-tr r1 silent_crash: fix in tree; s105 re-runs `git show 659d2421c7 --stat`, already run ~70 steps earlier.
- d05_b10k_tr r3 silent_crash: correct fix at s19-20, then **self-edit amnesia** — final turn reads its own patch and disowns
  it ("`str(format_type)` is called… Wait, looking at the code again… check if `getattr` is called before the conversion").
- d05_b10k_tr r2 limits_exceeded, **no edit ever**: 10 comps, 10k→~5k each; remnant restates the correct diagnosis at msgs
  2,4,8,10,14,16,18,22,24,26,28 with not one `sed -i`. Analysis loop, not knowledge loss.
- d05_b15k_ss r2 limits_exceeded, no edit: format collapse — emits a bash block *and* `<tool_call>{"name":…}</tool_call>` ⇒
  "Expected exactly 1 action, found 2"; malformed turns stay in context and the model imitates them.
## 6. Verdict
Compression-robust because **the entire solution state is re-derivable from the one message compression never touches**. The
PR names function and exception; a 45-line read exposes both `getattr(…, format_type)` calls; the fix is one line with two
interchangeable spellings. No cross-file invariant, no accumulated search result, no test output has to cross a compression
event, so TR/TRC/SU/SS delete only cheap regenerable content, while the agent's per-THOUGHT diagnosis restatement keeps the
conclusion inside the surviving window. The limit: cheap re-derivability is exactly what makes it loop. At 10k (ctx halved to
~5k ≈ 8-12 steps headroom, compression every ~12-15 steps) the agent loses not the knowledge but the *fact that it already
acted* — re-reading and disowning its own patch (tr b10k r3), or re-analysing forever without editing (tr b10k r2: 8 comps,
0 edits). Compression here never causes a wrong answer; it causes non-termination and submission-protocol misses. The real
bottleneck under compression is the stopping rule (emit `git diff > patch.txt` and submit), not the reasoning — and one such
failure (ss-partial b20k r2) happened with no compression at all.
