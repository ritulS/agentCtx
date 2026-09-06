"""Harbor bridge for the repository's compression-aware mini-swe-agent.

This is intentionally independent of ``scripts.bench_adapters.agent_adapter``. Harbor owns
the task environment; the repository's DefaultAgent runs on the host and uses
a killable child process, forwarding commands to Harbor in the parent process.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, override


REPO_ROOT = Path(__file__).resolve().parents[2]
MINI_SWE_AGENT_SRC = REPO_ROOT / "mini-swe-agent" / "src"
for import_root in (REPO_ROOT, MINI_SWE_AGENT_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import memory  # noqa: E402
from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.environments.base import BaseEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402
from minisweagent.agents.default import DefaultAgent  # noqa: E402
from minisweagent.config import get_config_from_spec  # noqa: E402
from minisweagent.exceptions import Submitted  # noqa: E402
from minisweagent.models import get_model  # noqa: E402
from minisweagent.utils.serialize import recursive_merge  # noqa: E402
from scripts.bench_adapters.harbor_process import run_worker, write_json  # noqa: E402


DEFAULT_CONFIG_SPECS = [
    str(REPO_ROOT / "configs" / "config-qwen-vllm.yaml"),
    str(REPO_ROOT / "configs" / "config-tbench.yaml"),
]
DEFAULT_EXEC_TIMEOUT = 60


class HarborContainerEnvironment:
    """The mini-swe-agent environment protocol over a Harbor environment."""

    def __init__(
        self,
        connection: Any,
        *,
        timeout: int = DEFAULT_EXEC_TIMEOUT,
        env: dict[str, str] | None = None,
    ) -> None:
        self._connection = connection
        self._timeout = timeout
        self._env = env or {}

    def execute(
        self, action: dict, cwd: str = "", *, timeout: int | None = None
    ) -> dict[str, Any]:
        request = {"type": "exec", "kwargs": {
            "command": action.get("command", ""),
            "cwd": cwd or None,
            "env": self._env or None,
            "timeout_sec": timeout or self._timeout,
        }}
        self._connection.write(json.dumps(request).encode() + b"\n")
        self._connection.flush()
        line = self._connection.readline()
        if not line:
            # Do not let the agent retry after its owner disappears.
            raise SystemExit("Harbor parent disconnected")
        output = json.loads(line)
        self._check_finished(output)
        return output

    @staticmethod
    def _check_finished(output: dict) -> None:
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if (
            lines
            and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            and output["returncode"] == 0
        ):
            submission = "".join(lines[1:])
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,
                    "extra": {"exit_status": "Submitted", "submission": submission},
                }
            )

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return recursive_merge(platform.uname()._asdict(), kwargs)

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "environment_type": (
                        f"{self.__class__.__module__}.{self.__class__.__name__}"
                    )
                }
            }
        }


class CompressionAgent(BaseAgent):
    """Run the repository's DefaultAgent without installing it in the task."""

    @staticmethod
    @override
    def name() -> str:
        return "mswea-compression"

    @override
    def version(self) -> str | None:
        return "1.1.0"

    def __init__(
        self, logs_dir: Path, model_name: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        os.environ.setdefault("MSWEA_COST_TRACKING", "ignore_errors")
        specs = os.environ.get("MSWEA_TB_CONFIGS")
        self._config_specs = specs.split(os.pathsep) if specs else DEFAULT_CONFIG_SPECS

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        return

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.logs_dir / "worker_checkpoint.json", {})
        exit_info: dict = {}
        try:
            exit_info = await run_worker(environment, self.logs_dir, {
                "config_specs": self._config_specs,
                "logs_dir": str(self.logs_dir.resolve()),
                "instruction": instruction,
            })
        except asyncio.CancelledError:
            exit_info = {"exit_status": "CancelledError"}
            raise  # Harbor converts its own deadline cancellation to AgentTimeoutError.
        except Exception as exc:
            exit_info = {"exit_status": type(exc).__name__, "error": str(exc)}
            raise
        finally:
            # The worker has been reaped. It cannot overwrite these final logs.
            checkpoint = self.logs_dir / "worker_checkpoint.json"
            state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
            tokens = state.get("token_log", {})
            context.n_input_tokens = tokens.get("total_prompt_tokens", 0)
            context.n_output_tokens = tokens.get("total_completion_tokens", 0)
            write_json(self.logs_dir / "token_log.json", tokens)
            write_json(self.logs_dir / "exit_info.json", {
                "exit_status": exit_info.get("exit_status", ""),
                "n_calls": state.get("n_calls"),
                "primitive": os.environ.get("MSWEA_PRIMITIVE", ""),
                "token_budget": os.environ.get("MSWEA_TOKEN_BUDGET", ""),
                "compression_ratio": os.environ.get("MSWEA_COMPRESSION_RATIO", ""),
                "error": exit_info.get("error"),
                "stats_scope": "last_checkpoint; in-flight inference may be uncounted",
            })


class CheckpointAgent(DefaultAgent):
    """Keep valid partial logs even when killed inside a synchronous model call."""

    def checkpoint(self) -> None:
        path = self.config.output_path
        write_json(path.parent / "worker_checkpoint.json", {
            "n_calls": self.n_calls,
            "token_log": memory.token_log_dict(self),
        })

    def query(self) -> dict:
        # Save the initial state too, in case the first model call hangs.
        self.save(self.config.output_path)
        try:
            return super().query()
        finally:
            self.save(self.config.output_path)

    def save(self, path: Path | None, *extra_dicts) -> dict:
        data = self.serialize(*extra_dicts)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, data)
            self.checkpoint()
        return data


def worker_main(fd: int) -> None:
    with socket.socket(fileno=fd) as sock, sock.makefile("rwb") as connection:
        payload = json.loads(connection.readline())
        try:
            config = recursive_merge(
                *[get_config_from_spec(spec) for spec in payload["config_specs"]]
            )
            model = get_model(config=config.get("model", {}))
            agent_config = dict(config.get("agent", {}))
            agent_config["output_path"] = Path(payload["logs_dir"]) / "trajectory.json"
            agent = CheckpointAgent(model, HarborContainerEnvironment(connection), **agent_config)
            result = agent.run(payload["instruction"])
            message = {"type": "done", "exit_info": result}
        except BaseException as exc:
            traceback.print_exc()
            message = {"type": "error", "error": f"{type(exc).__name__}: {exc}"}
        connection.write(json.dumps(message).encode() + b"\n")
        connection.flush()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("This module is launched by the Harbor adapter")
    worker_main(int(sys.argv[2]))
