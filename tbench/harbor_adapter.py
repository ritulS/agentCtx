"""Harbor bridge for the repository's compression-aware mini-swe-agent.

This is intentionally independent of ``tbench.agent_adapter``.  Harbor owns
the task environment; the repository's DefaultAgent runs on the host and uses
this small synchronous wrapper to execute commands through Harbor's async
environment API.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, override


REPO_ROOT = Path(__file__).resolve().parent.parent
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


DEFAULT_CONFIG_SPECS = [
    str(REPO_ROOT / "configs" / "config-qwen-vllm.yaml"),
    str(REPO_ROOT / "configs" / "config-tbench.yaml"),
]
DEFAULT_EXEC_TIMEOUT = 60


class HarborContainerEnvironment:
    """The mini-swe-agent environment protocol over a Harbor environment."""

    def __init__(
        self,
        environment: BaseEnvironment,
        loop: asyncio.AbstractEventLoop,
        *,
        timeout: int = DEFAULT_EXEC_TIMEOUT,
        env: dict[str, str] | None = None,
    ) -> None:
        self._environment = environment
        self._loop = loop
        self._timeout = timeout
        self._env = env or {}

    def execute(
        self, action: dict, cwd: str = "", *, timeout: int | None = None
    ) -> dict[str, Any]:
        coro = self._environment.exec(
            command=action.get("command", ""),
            cwd=cwd or None,
            env=self._env or None,
            timeout_sec=timeout or self._timeout,
        )
        try:
            result = asyncio.run_coroutine_threadsafe(coro, self._loop).result()
            output = {
                "output": (result.stdout or "") + (result.stderr or ""),
                "returncode": result.return_code,
                "exception_info": "",
            }
        except Exception as exc:
            output = {
                "output": "",
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {exc}",
                "extra": {"exception_type": type(exc).__name__, "exception": str(exc)},
            }
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
        return "1.0.0"

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
        loop = asyncio.get_running_loop()
        env_wrapper = HarborContainerEnvironment(environment, loop)
        agent = None
        exit_info: dict = {}
        try:
            config = recursive_merge(
                *[get_config_from_spec(spec) for spec in self._config_specs]
            )
            model = get_model(config=config.get("model", {}))
            agent_config = dict(config.get("agent", {}))
            agent_config["output_path"] = self.logs_dir / "trajectory.json"
            agent = DefaultAgent(model, env_wrapper, **agent_config)
            exit_info = await asyncio.to_thread(agent.run, instruction)
        except Exception as exc:
            exit_info = {"exit_status": type(exc).__name__, "submission": ""}
        finally:
            if agent is not None:
                context.n_input_tokens = agent._mem_prompt_tokens
                context.n_output_tokens = agent._mem_completion_tokens
                (self.logs_dir / "token_log.json").write_text(
                    json.dumps(memory.token_log_dict(agent), indent=2)
                )
            (self.logs_dir / "exit_info.json").write_text(
                json.dumps(
                    {
                        "exit_status": exit_info.get("exit_status", ""),
                        "n_calls": agent.n_calls if agent is not None else None,
                        "primitive": os.environ.get("MSWEA_PRIMITIVE", ""),
                        "token_budget": os.environ.get("MSWEA_TOKEN_BUDGET", ""),
                        "compression_ratio": os.environ.get(
                            "MSWEA_COMPRESSION_RATIO", ""
                        ),
                    },
                    indent=2,
                )
            )
