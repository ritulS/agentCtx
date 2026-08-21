"""Harbor agent adapter for the agentCtx compression experiments.

Terminal-Bench 2.0 dropped the standalone ``terminal-bench`` (tb) CLI in
favor of Harbor (``pip install harbor``; the old tb package/registry tops
out at terminal-bench-core 0.1.1, no 2.0 dataset). This adapter is Harbor's
analog of ``tbench/agent_adapter.py``: it runs the fork's DefaultAgent
(mini-swe-agent, branch agentctx-customizations) inside Harbor's harness via
``--agent tbench.harbor_adapter:CompressionAgent``. The compression code
path (DefaultAgent.query + memory.py primitives, driven by MSWEA_* env
vars) is identical to the SWE-bench and TB-1.0 experiments; only the
container-exec plumbing differs.

Design constraints this file encodes:

- Harbor's built-in "mini-swe-agent" agent (harbor.agents.installed.
  mini_swe_agent) installs vanilla PyPI mini-swe-agent *inside* the task
  container and drives it as an opaque CLI — it never touches our fork or
  memory.py, so it's not usable here. We instead run our fork's DefaultAgent
  in-process on the host (same as the old tb adapter) and only reach into
  the container to execute shell commands.
- Harbor's ``BaseAgent.run()`` is a coroutine, but DefaultAgent's run/step
  loop is synchronous (it blocks on each ``env.execute()``). We run the
  whole DefaultAgent loop in a worker thread via ``asyncio.to_thread`` and
  bounce each ``execute()`` call back onto Harbor's event loop with
  ``run_coroutine_threadsafe`` so ``environment.exec()`` (a coroutine) can
  still be awaited from Harbor's async machinery. Mirrors what the old
  adapter's ``TbContainerEnvironment`` did with ``docker exec`` subprocesses,
  minus the subprocess — Harbor's ``environment.exec()`` already talks to
  whatever backend (docker/podman/cloud) is configured.
- One Harbor process = one condition, same as before: MSWEA_PRIMITIVE /
  MSWEA_TOKEN_BUDGET / MSWEA_COMPRESSION_RATIO are process-wide (ratio is
  read at ``import memory`` time), so the orchestrator invokes ``harbor
  run`` once per condition.
- Harbor already isolates each trial under its own ``jobs/<job>/trials/
  <trial>/agent/`` directory (passed in as ``logs_dir``), so — unlike the
  old tb adapter, which had to parse a task id out of the trial dirname
  because tb ran all trials in one shared output tree — we just write
  trajectory.json / token_log.json / exit_info.json straight into
  ``self.logs_dir``. The orchestrator maps trials back to task ids from
  Harbor's own job results file after the run.
"""

import asyncio
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, override

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import memory  # noqa: E402  (agentCtx repo root)
from minisweagent.agents.default import DefaultAgent  # noqa: E402
from minisweagent.config import get_config_from_spec  # noqa: E402
from minisweagent.models import get_model  # noqa: E402
from minisweagent.exceptions import Submitted  # noqa: E402
from minisweagent.utils.serialize import recursive_merge  # noqa: E402

from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.environments.base import BaseEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402

# Model config first, TB prompt config second: the TB file must win on the
# agent section (step_limit 100, TB submission-protocol templates) while the
# model file's model_name/model_kwargs survive (disjoint keys, recursive
# merge). Same config-tbench.yaml as the TB-1.0 adapter — the submission
# protocol (echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT) is dataset-agnostic
# prompt engineering, not tied to the old tb harness.
DEFAULT_CONFIG_SPECS = [
    str(REPO_ROOT / "configs" / "config-qwen-vllm.yaml"),
    str(REPO_ROOT / "configs" / "config-tbench.yaml"),
]

DEFAULT_EXEC_TIMEOUT = 60


class HarborContainerEnvironment:
    """mini-swe-agent Environment protocol, backed by a Harbor BaseEnvironment.

    Only the three methods DefaultAgent actually calls on ``self.env`` are
    implemented: ``execute(action)``, ``get_template_vars()``, ``serialize()``.
    """

    def __init__(
        self,
        environment: BaseEnvironment,
        loop: asyncio.AbstractEventLoop,
        *,
        timeout: int = DEFAULT_EXEC_TIMEOUT,
        env: dict[str, str] | None = None,
    ):
        self._environment = environment
        self._loop = loop
        self._timeout = timeout
        self._env = env or {}

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        command = action.get("command", "")
        coro = self._environment.exec(
            command=command,
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
        except Exception as e:
            output = {
                "output": "",
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {e}",
                "extra": {"exception_type": type(e).__name__, "exception": str(e)},
            }
        self._check_finished(output)
        return output

    def _check_finished(self, output: dict) -> None:
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" and output["returncode"] == 0:
            submission = "".join(lines[1:])
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,
                    "extra": {"exit_status": "Submitted", "submission": submission},
                }
            )

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        return recursive_merge(platform.uname()._asdict(), kwargs)

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "environment_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }


class CompressionAgent(BaseAgent):
    @staticmethod
    @override
    def name() -> str:
        return "mswea-compression"

    @override
    def version(self) -> str | None:
        return "1.0.0"

    def __init__(self, logs_dir: Path, model_name: str | None = None, **kwargs: Any) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        os.environ.setdefault("MSWEA_COST_TRACKING", "ignore_errors")
        specs = os.environ.get("MSWEA_TB_CONFIGS")
        self._config_specs = specs.split(",") if specs else DEFAULT_CONFIG_SPECS

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        return  # nothing to install — DefaultAgent runs on the host, not in-container

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
            config = recursive_merge(*[get_config_from_spec(spec) for spec in self._config_specs])
            model = get_model(config=config.get("model", {}))
            agent_config = dict(config.get("agent", {}))
            agent_config["output_path"] = self.logs_dir / "trajectory.json"
            agent = DefaultAgent(model, env_wrapper, **agent_config)
            exit_info = await asyncio.to_thread(agent.run, instruction)
        except Exception as e:  # step-level uncaught errors re-raise from run()
            exit_info = {"exit_status": type(e).__name__, "submission": ""}
        finally:
            if agent is not None:
                context.n_input_tokens = agent._mem_prompt_tokens
                context.n_output_tokens = agent._mem_completion_tokens
                try:
                    (self.logs_dir / "token_log.json").write_text(
                        json.dumps(memory.token_log_dict(agent), indent=2)
                    )
                except Exception:
                    pass
            try:
                (self.logs_dir / "exit_info.json").write_text(
                    json.dumps(
                        {
                            "exit_status": exit_info.get("exit_status", ""),
                            "n_calls": agent.n_calls if agent is not None else None,
                            "primitive": os.environ.get("MSWEA_PRIMITIVE", ""),
                            "token_budget": os.environ.get("MSWEA_TOKEN_BUDGET", ""),
                            "compression_ratio": os.environ.get("MSWEA_COMPRESSION_RATIO", ""),
                        },
                        indent=2,
                    )
                )
            except Exception:
                pass
