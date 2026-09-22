"""Unix subprocess boundary for synchronous agents, including blocking LLM calls.

Only the parent touches Harbor's async environment. A private socket carries
command requests; stdout/stderr are kept separate in worker.log.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


def write_json(path: Path, value: Any) -> None:
    """Keep the previous checkpoint valid if the worker is killed mid-write."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


async def run_worker(environment: Any, logs_dir: Path, payload: dict) -> dict:
    parent, child = socket.socketpair()
    parent.setblocking(False)
    process = None
    loop = asyncio.get_running_loop()
    buffer = bytearray()

    async def send(value: dict) -> None:
        await loop.sock_sendall(parent, json.dumps(value).encode() + b"\n")

    async def receive() -> dict:
        while b"\n" not in buffer:
            chunk = await loop.sock_recv(parent, 65536)
            if not chunk:
                raise RuntimeError("Agent worker disconnected; see worker.log")
            buffer.extend(chunk)
        line, _, rest = buffer.partition(b"\n")
        buffer[:] = rest
        return json.loads(line)

    try:
        # Popen is deliberately synchronous: cancellation cannot lose the handle
        # between starting the process and assigning it to `process`.
        with (logs_dir / "worker.log").open("ab") as worker_log:
            process = subprocess.Popen(
                [sys.executable, "-m", "scripts.bench_adapters.harbor_adapter",
                 "--worker", str(child.fileno())],
                cwd=Path(__file__).resolve().parents[2],
                pass_fds=(child.fileno(),),
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
            )
        child.close()
        write_json(logs_dir / "worker_process.json", {"pid": process.pid})
        await send(payload)
        while True:
            message = await receive()
            if message["type"] == "done":
                return message["exit_info"]
            if message["type"] == "error":
                raise RuntimeError(message["error"])
            if message["type"] != "exec":
                raise RuntimeError(f"Unknown worker message: {message['type']}")
            try:
                result = await environment.exec(**message["kwargs"])
                response = {
                    "output": (result.stdout or "") + (result.stderr or ""),
                    "returncode": result.return_code,
                    "exception_info": "",
                }
            except Exception as exc:
                response = {
                    "output": "", "returncode": -1,
                    "exception_info": f"An error occurred while executing the command: {exc}",
                    "extra": {"exception_type": type(exc).__name__, "exception": str(exc)},
                }
            await send(response)
    finally:
        # CancelledError must propagate to Harbor, but only AFTER the worker and
        # its HTTP connections are gone. Kill the group to include descendants.
        child.close()
        parent.close()
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

            async def reap() -> None:
                while process.poll() is None:
                    await asyncio.sleep(0.01)

            cleanup = asyncio.create_task(reap())
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            write_json(logs_dir / "worker_process.json", {
                "pid": process.pid, "returncode": process.returncode, "reaped": True,
            })
            if cancelled:
                raise asyncio.CancelledError
