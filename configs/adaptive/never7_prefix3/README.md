# never7 prefix-3 schedules (TR × SU-free)

Adaptive schedules for `scripts/expansions/run_r2_swe_never7_adaptive.sh`:
which primitive fires at each of the first three compression events on the
7 P30S tasks Qwen3.5-35B-A3B never resolved under any fixed primitive
(`task_lists/swe_verified/p30s_qwen35b_never_resolved.json`).

File name = the primitive at event 1, 2, 3 (`t` = `truncation`, i.e. TR;
`s` = `summarization_free`, i.e. SU-free), all at budget 15k and depth 0.5.
A JSON schedule holds its last entry for every later event
(`src/agentctx/compression/ADAPTIVE.md`), so `tts` means "TR, TR, then SU-free
for the rest of the run". The never7 / never13 sections do not run `ttt` and
`sss`: there they are the fixed `d05__b15k__tr` and `di__b15k__su-free` cells
of `data/r2/swebench/p30s/`.

The same six schedules serve the 13 P100-minus-P30S tasks the model never
resolved (`task_lists/swe_verified/p100_minus_p30s_qwen35b_never_resolved.json`,
launched with `R2_SECTION=p100_minus_p30s_never13`); their fixed `ttt` / `sss`
counterparts are the `d05__b15k__tr` / `di__b15k__su-free` cells of
`data/r2/swebench/p100_minus_p30s/`.

`ttt.json` and `sss.json` (TR only / SU-free only) exist for the
`p100_fc_only4` section: the 4 P100 tasks the model resolved under full context
but never under fixed TR or SU-free
(`task_lists/swe_verified/p100_qwen35b_fc_not_tr_su-free.json`), where all
eight orders run at 10 runs per task through the same adaptive condition, so
the uniform orders have the same run count and code path as the mixed ones.
That section also raises the per-run limits to 400 steps / 7200 s (runner
default 300 / 5400), so its cells are not comparable run-for-run with the
fixed cells of `p30s` / `p100_minus_p30s`.

Why a prefix of 3: on these tasks SU-free fired 3.1 times per run on average
(median 3, max 11) and TR 5.5 (median 4, max 15), so the six schedules here
enumerate every TR/SU-free path through the events most runs actually have.
