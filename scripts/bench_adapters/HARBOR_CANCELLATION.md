# Harbor Timeout Handling (2026-09-06)

Previously, cancellation only stopped waiting for `asyncio.to_thread(agent.run, ...)`,
leaving synchronous model calls, retries, and the agent loop running.

`CompressionAgent` now starts a separate child process for each task.
Model calls (including summarization calls for compression) run in the child process,
which requests Harbor container operations from the parent process over a dedicated socket.

On timeout or cancellation, SIGKILL is sent to the child process's dedicated process group.
CancelledError is re-raised only after the child process is confirmed to have exited.
Harbor's time limits and the conditions for raising AgentTimeoutError are unchanged.
The child process is also reaped after normal completion, so no library background threads remain.
The legacy `tbench.harbor_adapter` uses the same implementation.

Additional logs saved:

- `worker_process.json`: Child process PID, exit code, and `reaped: true`.
- `worker.log`: Child process stdout and stderr.
- `worker_checkpoint.json`: Most recently saved call counts and token statistics.

Trajectories and checkpoints are saved by replacing the destination with a temporary file
to prevent forced termination from corrupting existing JSON. The parent saves the final
token_log/exit_info after the child process exits. Unsaved token counts from interrupted
inference or summarization calls are not included.
Because CancelledError in `exit_info.json` also includes manual cancellation, use
exception_info in Harbor's result.json to determine whether a timeout occurred.

Validation command (requires local sockets, but no GPU, Docker, or external API):

```bash
venv-harbor/bin/python -m unittest scripts.bench_adapters.test_harbor_cancellation -v
```

The tests cover normal submission, connection closure on timeout while waiting for inference,
cancellation during container operations, isolation from other tasks, cancellation immediately
after startup, and abnormal termination.

These tests do not verify that GPU requests are released on a real vLLM server. The chat
completions routes in both installed versions handle cancellation on client disconnect.
Terminating the child process closes the client connection, but the time it takes to release
GPU processing must be checked with a small trial on actual hardware. Harbor's environment
implementation remains responsible for cleaning up commands running inside containers.

Check cancellation on a real vLLM server (start the target server and run with no other experiments active):

```bash
venv-harbor/bin/python -m scripts.bench_adapters.check_vllm_cancellation glm
venv-harbor/bin/python -m scripts.bench_adapters.check_vllm_cancellation devstral
```

GLM uses port 8003, and Devstral uses port 8002. Check logs are saved to
`logs/cancellation_checks/` and are not added to experiment results.

These changes apply to newly started experiments. They do not stop threads from older agents
that are already running. Before resuming, stop old experiment processes and clear unwanted
inference requests, then run a few tasks to confirm that workers disappear after their deadlines
and vLLM's Running count decreases. vLLM's Running count measures inference requests, so it
does not necessarily match the number of concurrent experiment tasks.
