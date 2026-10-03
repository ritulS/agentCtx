"""Run with venv-harbor/bin/python -m pytest tests/test_harbor_cancellation.py.

Needs Harbor and mini-swe-agent; the lightweight runner-equivalence
environment skips this module.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
# ROOT itself provides the `memory` alias the pinned mini-swe-agent imports.
for entry in (ROOT, ROOT / "src", ROOT / "mini-swe-agent" / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

try:
    from harbor.models.agent.context import AgentContext
    from minisweagent.models.test_models import DeterministicModel, make_output
except ImportError as exc:  # pragma: no cover - depends on the installed venv
    raise unittest.SkipTest(f"Harbor / mini-swe-agent not installed: {exc}")

from agentctx.benchmarks.harbor_adapter import CheckpointAgent, CompressionAgent  # noqa: E402
from agentctx.compression import primitives as memory  # noqa: E402


class FlakySummarizerModel(DeterministicModel):
    """First query: a rejected (empty) summary carrying a provider id.
    Second query: a transport error, as a dropped connection would raise."""

    def __init__(self, **kwargs):
        super().__init__(outputs=[], **kwargs)
        self.calls = 0

    def query(self, messages, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("transport failed")
        return {"role": "assistant", "content": "",
                "extra": {"response": {"id": "chatcmpl-first",
                                       "usage": {"prompt_tokens": 10, "completion_tokens": 1}}}}


class CheckpointSalvageTests(unittest.TestCase):
    """CheckpointAgent persists through checkpoint(), not _write_token_log(),
    so the salvage of an interrupted summarizer event must happen there."""

    def test_checkpoint_keeps_ids_of_interrupted_summarizer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "MSWEA_PRIMITIVE": "summarization", "MSWEA_TOKEN_BUDGET": "100",
            "MSWEA_TOKEN_LOG_PATH": "", "MSWEA_EVENT_LOG_DIR": "",
        }):
            output = Path(tmp) / "trajectory.json"
            model = FlakySummarizerModel()
            agent = CheckpointAgent(model, SimpleNamespace(
                get_template_vars=lambda: {}, serialize=lambda: {}, execute=None,
            ), system_template="system", instance_template="task", output_path=output)
            agent.add_messages({"role": "system", "content": "system"}, {"role": "user", "content": "task"})
            for i in range(6):
                agent.add_messages({"role": "assistant", "content": f"command {i}"},
                                   {"role": "user", "content": "output " * 100,
                                    "extra": {"raw_output": "output", "returncode": 0}})
            with self.assertRaisesRegex(RuntimeError, "transport failed"):
                agent.query()   # query()'s finally saves and checkpoints
            self.assertEqual(model.calls, 2)
            self.assertIsNone(agent._mem_active_compression)
            self.assertIsNone(memory.pop_summary_outcome())   # consumed, not leaked
            checkpoint = json.loads((output.parent / "worker_checkpoint.json").read_text())
            outcomes = checkpoint["token_log"]["summary_outcomes"]
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0]["response_ids"], ["chatcmpl-first"])
            self.assertEqual(outcomes[0]["interrupted"], "RuntimeError")
            self.assertEqual(outcomes[0]["interrupted_attempt"], 2)
            self.assertFalse(outcomes[0]["accepted"])
            self.assertEqual(outcomes[0]["primitive"], "summarization")
            agent.checkpoint()   # idempotent: no duplicate entry
            checkpoint = json.loads((output.parent / "worker_checkpoint.json").read_text())
            self.assertEqual(len(checkpoint["token_log"]["summary_outcomes"]), 1)


class BlockingSocketModel(DeterministicModel):
    """Stand-in for a synchronous inference request that never responds."""

    def query(self, messages, **kwargs):
        port = int(self.config.model_name.split(":")[1])
        with socket.create_connection(("127.0.0.1", port)) as connection:
            connection.sendall(b"inference-request\n")
            connection.recv(1)
        raise AssertionError("The blocked model call should have been killed")


class WorkThenBlockModel(BlockingSocketModel):
    """Produce tool observations, then block in inference after compression."""

    def query(self, messages, **kwargs):
        if self.current_index + 1 < len(self.config.outputs):
            return DeterministicModel.query(self, messages, **kwargs)
        return super().query(messages, **kwargs)


class Environment:
    def __init__(self, block=False):
        self.calls = []
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.block = block

    async def exec(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        if self.block:
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()
        return SimpleNamespace(
            stdout="COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nsubmitted", stderr="", return_code=0,
        )


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Workers import the fake models by module name in a fresh interpreter.
        model_path = os.pathsep.join(filter(None, (str(ROOT / "tests"), os.environ.get("PYTHONPATH"))))
        model_imports = patch.dict(os.environ, {"PYTHONPATH": model_path})
        model_imports.start()
        self.addCleanup(model_imports.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def agent(self, name="trial", model=None):
        logs = self.root / name
        logs.mkdir()
        config = self.root / f"{name}.yaml"
        config.write_text(json.dumps({
            "agent": {"system_template": "Test", "instance_template": "{{task}}", "cost_limit": 0},
            "model": model or {
                "model_class": "deterministic", "model_name": "deterministic",
                "outputs": [make_output("submit", [{"command": "submit"}])],
            },
        }))
        agent = CompressionAgent(logs, mcp_servers=[])
        agent._config_specs = [str(config)]
        return agent

    def assert_reaped(self, agent):
        state = json.loads((agent.logs_dir / "worker_process.json").read_text())
        self.assertTrue(state["reaped"])
        with self.assertRaises(ProcessLookupError):
            os.kill(state["pid"], 0)

    async def test_normal_submission_and_checkpoint(self):
        agent = self.agent()
        env = Environment()
        await asyncio.wait_for(agent.run("test", env, AgentContext()), 30)
        self.assertEqual(env.calls[0]["command"], "submit")
        self.assertEqual(env.calls[0]["timeout_sec"], 60)
        result = json.loads((agent.logs_dir / "exit_info.json").read_text())
        self.assertEqual(result["exit_status"], "Submitted")
        self.assertEqual(result["n_calls"], 1)
        self.assert_reaped(agent)

    async def test_timeout_closes_blocking_inference_socket(self):
        connected, disconnected = asyncio.Event(), asyncio.Event()

        async def inference(reader, writer):
            try:
                await reader.readline()
                connected.set()
                self.assertEqual(await reader.read(), b"")
                disconnected.set()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(inference, "127.0.0.1", 0)
        async with server:
            agent = self.agent(model={
                "model_class": "test_harbor_cancellation.BlockingSocketModel",
                "model_name": f"blocking:{server.sockets[0].getsockname()[1]}", "outputs": [],
            })
            task = asyncio.create_task(agent.run("test", Environment(), AgentContext()))
            try:
                await asyncio.wait_for(connected.wait(), 30)
                # Exercise the same wait_for cancellation used by Harbor.
                with self.assertRaises(asyncio.TimeoutError):
                    await asyncio.wait_for(task, 0.05)
                await asyncio.wait_for(disconnected.wait(), 2)
                self.assert_reaped(agent)
                before = {p.name: p.read_bytes() for p in agent.logs_dir.glob("*.json")}
                await asyncio.sleep(0.1)
                self.assertEqual(before, {p.name: p.read_bytes() for p in agent.logs_dir.glob("*.json")})
                result = json.loads((agent.logs_dir / "exit_info.json").read_text())
                self.assertEqual(result["exit_status"], "CancelledError")
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_timeout_after_tr_preserves_pre_inference_checkpoint(self):
        # With an older turn, TR reduces tokens; without one, it must report zero
        # reduction. In both cases the latest large result remains over budget.
        for older_turn in (False, True):
            with self.subTest(older_turn=older_turn), patch.dict(os.environ, {
                "MSWEA_PRIMITIVE": "truncation", "MSWEA_TOKEN_BUDGET": "1000",
                "MSWEA_COMPRESSION_RATIO": "0.5", "MSWEA_TOKEN_LOG_PATH": "",
                "MSWEA_EVENT_LOG_DIR": "",
            }):
                connected, disconnected = asyncio.Event(), asyncio.Event()

                async def inference(reader, writer):
                    try:
                        await reader.readline()
                        connected.set()
                        await reader.read()
                        disconnected.set()
                    finally:
                        writer.close()
                        await writer.wait_closed()

                class OutputEnvironment(Environment):
                    async def exec(self, **kwargs):
                        self.calls.append(kwargs)
                        content = "old context " * 100 if older_turn and len(self.calls) == 1 else "large output " * 1500
                        return SimpleNamespace(stdout=content, stderr="", return_code=0)

                server = await asyncio.start_server(inference, "127.0.0.1", 0)
                async with server:
                    agent = self.agent(f"tr-{older_turn}", model={
                        "model_class": "test_harbor_cancellation.WorkThenBlockModel",
                        "model_name": f"blocking:{server.sockets[0].getsockname()[1]}",
                        "outputs": [make_output("inspect", [{"command": "inspect"}])
                                    for _ in range(1 + int(older_turn))],
                    })
                    task = asyncio.create_task(agent.run("test", OutputEnvironment(), AgentContext()))
                    try:
                        await asyncio.wait_for(connected.wait(), 30)
                        checkpoint = json.loads((agent.logs_dir / "worker_checkpoint.json").read_text())
                        tokens = checkpoint["token_log"]
                        self.assertEqual(tokens["compression_events"], 1)
                        self.assertEqual(len(tokens["tr_events"]), 1)
                        event = tokens["tr_events"][0]
                        self.assertEqual(event["target_tokens"], 500)
                        self.assertTrue(event["target_not_met"])
                        self.assertTrue(event["budget_exceeded"])
                        self.assertEqual(event["zero_reduction"], not older_turn)
                        self.assertEqual(tokens["tr_zero_reduction_events"], int(not older_turn))
                        self.assertEqual(tokens["tr_target_not_met_events"], 1)
                        self.assertEqual(tokens["tr_budget_exceeded_events"], 1)
                        self.assertEqual(event["tokens_saved"], tokens["total_tokens_saved"])
                        # Timeout goes through Harbor's parent cancellation path,
                        # which SIGKILLs the worker: its query finally cannot run.
                        with self.assertRaises(asyncio.TimeoutError):
                            await asyncio.wait_for(task, 0.05)
                        await asyncio.wait_for(disconnected.wait(), 2)
                        self.assert_reaped(agent)
                        final = json.loads((agent.logs_dir / "token_log.json").read_text())
                        self.assertEqual(final, tokens)
                        self.assertEqual(json.loads((agent.logs_dir / "exit_info.json").read_text())["exit_status"],
                                         "CancelledError")
                    finally:
                        if not task.done():
                            task.cancel()
                        await asyncio.gather(task, return_exceptions=True)

    async def test_cancel_environment_command_and_preserve_other_trial(self):
        agent = self.agent("cancelled")
        env = Environment(block=True)
        task = asyncio.create_task(agent.run("test", env, AgentContext()))
        try:
            await asyncio.wait_for(env.started.wait(), 30)
            other = self.agent("other")
            other_task = asyncio.create_task(other.run("test", Environment(), AgentContext()))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(env.cancelled.is_set())
            self.assert_reaped(agent)
            trajectory = json.loads((agent.logs_dir / "trajectory.json").read_text())
            self.assertEqual(trajectory["info"]["model_stats"]["api_calls"], 1)
            await asyncio.wait_for(other_task, 30)
            self.assert_reaped(other)
            self.assertEqual(json.loads((other.logs_dir / "exit_info.json").read_text())["exit_status"], "Submitted")
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_worker_error_is_reported_and_reaped(self):
        agent = self.agent(model={"model_class": "deterministic", "model_name": "deterministic", "outputs": []})
        with self.assertRaisesRegex(RuntimeError, "IndexError"):
            await asyncio.wait_for(agent.run("test", Environment(), AgentContext()), 30)
        self.assert_reaped(agent)

    async def test_cancel_during_worker_startup(self):
        agent = self.agent()
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(agent.run("test", Environment(), AgentContext()), 0.01)
        self.assert_reaped(agent)


if __name__ == "__main__":
    unittest.main()
