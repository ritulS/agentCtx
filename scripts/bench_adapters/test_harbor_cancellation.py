"""Run with venv-harbor/bin/python -m unittest scripts.bench_adapters.test_harbor_cancellation."""

import asyncio
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.bench_adapters.harbor_adapter import CompressionAgent
from harbor.models.agent.context import AgentContext
from minisweagent.models.test_models import DeterministicModel, make_output


class BlockingSocketModel(DeterministicModel):
    """Stand-in for a synchronous inference request that never responds."""

    def query(self, messages, **kwargs):
        port = int(self.config.model_name.split(":")[1])
        with socket.create_connection(("127.0.0.1", port)) as connection:
            connection.sendall(b"inference-request\n")
            connection.recv(1)
        raise AssertionError("The blocked model call should have been killed")


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

    def test_legacy_entry_point_uses_same_adapter(self):
        from tbench.harbor_adapter import CompressionAgent as LegacyAgent
        self.assertIs(LegacyAgent, CompressionAgent)

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
                "model_class": "scripts.bench_adapters.test_harbor_cancellation.BlockingSocketModel",
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
