# Summary handoff verification

2026-09-08. This review covers the 645 runs from the preceding audit and the current `memory.py`. Experiment code and results were not modified.

## Findings

The message structure behaves as intended. However, structured summaries do not consistently follow the specified output format. Passing these responses through without validation also breaks the assumptions used by downstream code to identify summaries. These findings alone do not establish the cause of the repeated-summarization FormatErrors in 33 runs.

## Behavior that matches the intended design

- `memory.py:14-18, 224-225, 304` preserves the original system message and initial task, replacing the compressible history with a summary. The partial variant also appends the original tail (`424-426`).
- The system/user prompts requesting a summary are passed only to the separate `query_summary` call (`243-283`). There is no code that adds those prompts themselves to the agent's conversation.
- Commit `f669241` on 2026-09-07 disabled only the action parser for summary calls. It did not change summary formatting or the message role. Returning summaries with the `user` role predates that fix.

## Mismatches between response content and code assumptions

1. `memory.py:256-276` explicitly specifies the heading order and prohibits text outside the `[CONTEXT SUMMARY]` block.
2. `memory.py:286-302` turns the entire `response.content` into a user message. It does not extract the marked block, remove preambles, or validate the output format. The code is not concatenating a separate reasoning field; it passes through the preamble already present in `content`.
3. All 220 structured summary messages found in the saved trajectories contain nonempty text before the opening marker, and 219 contain `</think>`. This violates the requested output format. However, the saved trajectories do not preserve every compression event.
4. TRC in `memory.py:461-471` protects summaries using `content.startswith`. An SS response with a preamble fails this check and becomes eligible for clearing as tool output. A similar check appears at `609-619`. SU behaves differently because the code adds its outer markers (`195-197`).

## Local reproduction without model calls

The current `structured_summarize` was run unchanged with a FakeModel returning a reasoning preamble about preparing a summary, followed by `</think>` and a summary block.

- Original system/task preserved: True
- Summary-request prompt itself included in the resulting conversation: False
- Response forwarded exactly, including its preamble: True
- Summary role: `user`

Four agent/tool turns were appended after that summary, then `tool_result_clear(..., target_tokens=1, fallback_truncate=False)` was called.

- Summary with the preamble: replaced with `[TOOL OUTPUT CLEARED]`.
- The same summary with only the text before the opening marker removed: protected.

This test reproduces a mismatch with the format expected by downstream code. It does not demonstrate that TRC actually cleared summaries in the 33 runs. Those runs also include other SS-family conditions, and controlled comparisons are needed to establish a causal link to repeated-summarization failures.

## Assessment

No implementation error was found in which the agent loses the original task or receives the summary-request prompt itself as the latest instruction. Model output-format violations do occur. There is also an interface mismatch: these nonconforming responses are passed through unchanged, while downstream code assumes the expected format. The evidence therefore does not justify attributing every case solely to agent capability or invalidating every case as a recurrence of the old summary bug.

There is a technical basis for improving format handling, such as extracting the summary block and identifying summaries explicitly. Improvements through additional continuation instructions or prompt optimization should be treated separately as changes to the experimental method. This review did not modify the implementation or rerun experiments.

## Clarification on API request coverage in the logs

This run has 10 compression events. `trajectory.json` stores the post-compression conversation, rather than a sequential record of every API request. Because SS-partial retains earlier messages in the tail, a FormatError immediately following a summary in the final trajectory does not establish that it came from the API response immediately after that summary was newly generated. The earlier claim that it happened "immediately afterward" is withdrawn. The logs independently establish the presence of a summary preamble and an agent response that produced a summary and was rejected, but their temporal relationship remains unconfirmed.

The code confirms that summary calls use separate system/user prompts, and that the normal agent receives the system message, original task, summary (`user`), and retained tail. The full history supplied to the summarizer and the API payload immediately after compression have not been fully reconstructed from this run's saved files alone.
