"""Exercise Harbor worker cancellation against an idle local vLLM server."""

import argparse
import asyncio
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from scripts.bench_adapters.harbor_adapter import CompressionAgent
from harbor.models.agent.context import AgentContext


class NoCommands:
    async def exec(self, **kwargs):
        raise RuntimeError("This check does not execute model-generated commands")


def pending(base):
    with urllib.request.urlopen(base + "/metrics", timeout=3) as response:
        lines = response.read().decode().splitlines()
    counts = {}
    for name in ("vllm:num_requests_running", "vllm:num_requests_waiting"):
        values = [float(line.split()[1]) for line in lines
                  if line.startswith(name + "{") or line.startswith(name + " ")]
        if not values:
            raise RuntimeError(f"Missing metric: {name}")
        counts[name] = sum(values)
    return sum(counts.values())


async def check(model):
    root = Path(__file__).resolve().parents[2]
    port = 8003 if model == "glm" else 8002
    base = f"http://localhost:{port}"
    if pending(base) != 0:
        raise RuntimeError("Server is busy. Stop other experiments before this check.")
    logs = root / "logs" / "cancellation_checks" / f"{model}-{datetime.now():%Y%m%d-%H%M%S-%f}"
    logs.mkdir(parents=True)
    override = logs / "check_config.yaml"
    override.write_text(json.dumps({"agent": {
        "system_template": "You are testing long text generation. Follow the user instruction.",
        "instance_template": "{{task}}", "step_limit": 2, "cost_limit": 0,
    }}))
    config = "config-glm47flash-vllm.yaml" if model == "glm" else "config-devstral-vllm.yaml"
    agent = CompressionAgent(logs, mcp_servers=[])
    agent._config_specs = [str(root / "configs" / config), str(override)]
    task = asyncio.create_task(agent.run(
        "Write the integers from 1 to 10000, one per line. Do not abbreviate or use tools.",
        NoCommands(), AgentContext(),
    ))
    print(f"Logs: {logs}", flush=True)
    try:
        deadline = time.monotonic() + 90
        while pending(base) == 0:
            if task.done():
                await task
                raise RuntimeError("Worker finished before active inference was observed; inconclusive.")
            if time.monotonic() > deadline:
                raise RuntimeError("No active inference observed within 90 seconds; inconclusive.")
            await asyncio.sleep(0.1)
        print("Active inference observed; triggering timeout.", flush=True)
        try:
            await asyncio.wait_for(task, timeout=0.05)
        except asyncio.TimeoutError:
            pass
        else:
            raise RuntimeError("Worker completed before timeout; inconclusive, retry the check.")
        state = json.loads((logs / "worker_process.json").read_text())
        assert state["reaped"], state
        try:
            os.kill(state["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError("Worker PID still exists")
        assert json.loads((logs / "exit_info.json").read_text())["exit_status"] == "CancelledError"
        deadline = time.monotonic() + 30
        while pending(base) != 0:
            if time.monotonic() > deadline:
                raise RuntimeError("vLLM requests remain 30 seconds after timeout")
            await asyncio.sleep(0.5)
        before = {p.name: p.read_bytes() for p in logs.glob("*.json")}
        for _ in range(20):
            await asyncio.sleep(0.5)
            if pending(base) != 0:
                raise RuntimeError("New vLLM activity after cancellation")
        assert before == {p.name: p.read_bytes() for p in logs.glob("*.json")}, "Logs changed after cancellation"
        print("PASS: worker gone; vLLM running/waiting = 0; no new activity for 10 seconds.")
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=["glm", "devstral"])
    args = parser.parse_args()
    asyncio.run(check(args.model))
