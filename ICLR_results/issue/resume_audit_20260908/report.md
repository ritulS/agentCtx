# Resumed-run log audit — 2026-09-08

This audit covers Qwen SWE-bench from its resumption at 2026-09-07 20:01:53 CDT through the latest saved result at 2026-09-08 12:55:43 CDT. The 645 newly completed runs in the parent-process log were cross-checked against 645 updated trajectories and timestamps in the result index. Earlier results, other models, and other machines are outside the scope of this audit. Experiment code and results were not modified.

## Findings

- Saved trajectories contain 767 FormatError events across 337/645 runs. These include general action-format violations; not every event indicates a summary bug.
- Rejected responses containing summary markers appear in 33 runs, totaling 42 events. In 31 events, the immediately preceding user message contains a summary and `</think>`. In an example, the saved conversation already contains a summary, followed by an agent response that generates another summary and triggers `Expected exactly 1 action, found 0`.
- Of the 220 saved structured summary messages, 219 retain a preamble containing `</think>`, and 9 lack the closing marker. These counts cover only messages retained in the final trajectories, not a quality review of all 2085 compression events. Reasoning text in the summary may induce repeated summarization, but causality remains unconfirmed.
- In the current `memory.py`, `query_summary` queries a copy with its parser disabled, while preserving the normal agent's parser. Local mock responses also confirmed that a summary is accepted by the summary call, while the same text returned by the normal agent produces a FormatError. This cannot be established as a recurrence of the old bug; the content handed back to the agent and the continuation instructions need improvement.
- The agent's 1500-second timeout affected 152/645 runs (23.6%). The rate was particularly high for main OTRC+SS-partial at 52/89 (58.4%) and ablation d03/10k SS at 22/46 (47.8%). Of the 152 runs, 151 have an empty `exit_status`; one has `Submitted` but timed out while waiting for the process to exit. Timeout rows are also added to the index, and `run_all_agents` skips runs based solely on key existence, so a normal resume does not rerun them.
- Eight evaluations hit the 600-second timeout, all for `scikit-learn__scikit-learn-14710`. These are ERROR cases (`resolved=null`), not FAILED cases. They also occur in conditions that do not use summaries, including TRC, FC, and OTRC, and require separate investigation on the evaluation side. The TRC r3 evaluation log stops while copying `eval.sh` into the container.
- No ERROR or HTTP 400/500 entries were recorded from the resumed vLLM process (`pid=2552238`) onward. All 645 runs have readable trajectory/token-log JSON, with no missing result-index entries or mismatched step-token array lengths.

## Interpretation limits

- Compression removes earlier messages from trajectories, so error counts are lower bounds based on retained records.
- The old audit's call-accounting formula flags two runs here, but differences caused by trajectory and token-log saves at different times cannot be ruled out. These flags are not treated as proof of the old summary-call bug.
- Many `Traceback` strings in `agent.log` come from test output produced during tasks. The 8319 string matches must not be interpreted as the number of experiment-infrastructure exceptions.
- The latest parent-process log ends at 90/90 for ablation d07/10k SS-partial. Subsequent evaluation or overall completion lines have not been confirmed. The logs visible in this environment alone cannot establish whether the host processes are currently running.

## Priority actions

1. Validate a change that removes reasoning preambles from summaries and explicitly identifies them as historical information while instructing the agent to continue the original task.
2. Investigate why timeouts concentrate in particular conditions and decide how to treat runs cut off by the 1500-second limit in the experiment. This affects comparisons across conditions, so simply rerunning every case does not resolve the issue.
3. Investigate the evaluation environment for scikit-learn-14710 and reevaluate the eight affected runs.

## Evidence files

- `summary_marker_events.csv`: trajectory paths and zero-based message indices for the 42 events.
- `agent_timeouts.csv`: conditions, run keys, exit statuses, and timings for the 152 timeout cases.
- `audited_runs.csv`: the 645 audited runs.
- `counts.json`: counts by condition. `log_tracebacks` counts string matches, not failures.

Representative example: in `ICLR_results/swebench/ablation/qwen35b/d03__b10k__ss-partial/django__django-11299/structured-summarize-partial/run_3/trajectory.json`, `messages[2]` contains a summary and `messages[3]` contains the FormatError for a response that summarizes again.

Code references: `memory.py:73`, `memory.py:283`, `memory.py:300`; `scripts/run_experiment.py:204`, `scripts/run_experiment.py:282`; `scripts/bench_adapters/swe_bench.py:193`.
Parent-process log lines for evaluation timeouts: 915, 982, 1019, 1073, 1118, 1421, 1520, 1557.
