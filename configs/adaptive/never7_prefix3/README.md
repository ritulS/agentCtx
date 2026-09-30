# never7 prefix-3 schedules (TR × SU-free)

Adaptive schedules for `scripts/expansions/run_r2_swe_never7_adaptive.sh`:
which primitive fires at each of the first three compression events on the
7 P30S tasks Qwen3.5-35B-A3B never resolved under any fixed primitive
(`task_lists/swe_verified/p30s_qwen35b_never_resolved.json`).

File name = the primitive at event 1, 2, 3 (`t` = `truncation`, i.e. TR;
`s` = `summarization_free`, i.e. SU-free), all at budget 15k and depth 0.5.
A JSON schedule holds its last entry for every later event
(`src/agentctx/compression/ADAPTIVE.md`), so `tts` means "TR, TR, then SU-free
for the rest of the run". `ttt` and `sss` are omitted: they are the fixed
`d05__b15k__tr` and `di__b15k__su-free` cells of `data/r2/swebench/p30s/`.

Why a prefix of 3: on these tasks SU-free fired 3.1 times per run on average
(median 3, max 11) and TR 5.5 (median 4, max 15), so the six schedules here
enumerate every TR/SU-free path through the events most runs actually have.
