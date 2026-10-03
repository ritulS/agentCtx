# Impact of reasoning separation — 2026-09-29

## When it was enabled

Commit `647beeaba8bb16378721160570eef8186d22daf3` in the current repository (2026-09-26 23:33:45 CDT) added `--reasoning-parser qwen3` as a default in the Qwen vLLM launch script. This enabled an existing vLLM feature rather than implementing a new parser. It can be disabled with `REASONING_PARSER=none`.

The old workspace is `/home/ak58925/ICLR27/agentCtx`. Its `logs/vllm_qwen35_a3b.log` records a launch with `reasoning_parser=''`. In the old trajectories, `assistant.content` contains thinking, `</think>`, and final content together, with no separate `reasoning_content` field.

## What actually happened in the old data

The comparison selects the same 30 tasks in the current `task_lists/p30_swe_stratified.json`, using run_1 from `ICLR_results/swebench/main/qwen35b/di__binf__fc`. Timestamps in the old result index range from 2026-03-31 to 2026-05-03.

| Metric | Old FC (no separation) | Current FC (with separation) |
|---|---:|---:|
| Runs | 30 | 30 |
| Agent calls | 1,790 | 2,711 |
| Format errors | 57 (3.18%) | 232 (8.56%) |
| Stored accepted assistant responses | 1,733 | 2,479 |
| step_limit | 125 | 300 |
| max_tokens | 4,096 | 4,096 |
| resolved | 17/30 | 18/30 |

Of the 1,733 accepted responses in the old data, 221 had no `</think>` and contained exactly one command in the required format. Of these, 220 were immediately followed by tool output and 1 ended with submission. The old approach therefore actually executed actions from outputs of the form that the current parser treats as reasoning.

The old approach had 57 format errors: 55 with zero actions and 2 with two actions. Raw failed-response text was saved, but usage and `finish_reason` were not, so the number of responses truncated at 4096 tokens cannot be reconstructed with the same precision as in the current data.

This is not a controlled experiment varying only the parser. The step limit, execution dates, server conditions, and other factors differ. Differences in success and format-error rates must not be interpreted as the parser's causal effect. A more recent old prefix-cache FC cell was also examined, but it shared only three tasks with P30S, so the table prioritizes the same 30 tasks.

## Re-parsing the current saved responses without separation

For all 13,193 calls, `reasoning_content` and `content` from the API responses saved in `events.jsonl` were joined with a closing think boundary between them. The same action-regex rules used by both the old and current versions were then applied (`re.DOTALL`, exactly one `mswea_bash_command` block). No commands were executed and the model was not queried again.

- Of the current 800 format errors, 422 become accepted: 420 with empty content and `finish_reason=stop`, plus 2 with `finish_reason=length`.
- Of the 12,393 currently accepted responses, 19 become rejected because joining the fields introduces multiple commands or other format violations.
- On this fixed set of responses, the rejection count changes from 800 to 397.

| Condition | Current rejections | Rejected now, accepted without separation | Accepted now, rejected without separation | Rejections after re-parsing without separation |
|---|---:|---:|---:|---:|
| TR | 166 | 81 | 5 | 90 |
| SU-free | 175 | 99 | 7 | 83 |
| TRC | 227 | 159 | 2 | 70 |
| FC | 232 | 83 | 5 | 154 |

These numbers show only differences in how responses are interpreted. Running the experiment without separation would change the history, executed commands, and subsequent responses from the first divergence onward. These counts therefore do not predict error counts or success rates in a rerun. Acceptance does not guarantee that a command is semantically correct.

## Impact on compression experiments

Both the old and current `count_tokens` implementations count content. Without separation, thinking is included in content and therefore contributes to the 15k compression threshold. After separation, it moves to another field and is excluded from that threshold calculation. The summarizer's `history_text` is also built from content, so the information it receives changes. Turning the parser on or off changes an experimental condition affecting compression timing and summarizer input, not just response presentation.

## Next decision

If continuity with the old experiments is the priority, a small comparison with the parser disabled to match the old setup is reasonable before changing the prompt. To isolate the cause, first change only the parser, keeping `max_tokens` and the prompt fixed. Treat 4096 → 32768 as a separate comparison. Because the agent and summarizer share the same vLLM server, changing the server-side parser affects both.

This investigation did not modify old or new data, code, or server settings, and did not restart the server or rerun generation.
