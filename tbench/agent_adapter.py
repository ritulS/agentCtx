"""Terminal-Bench agent adapter for the agentCtx compression experiments.

Runs the fork's DefaultAgent (mini-swe-agent, branch agentctx-customizations)
inside terminal-bench's harness via ``--agent-import-path
tbench.agent_adapter:CompressionAgent``. The compression code path
(DefaultAgent.query + memory.py primitives, driven by MSWEA_* env vars) is
identical to the SWE-bench experiments; only the runner and environment differ.

Design constraints this file encodes:

- Commands run against the tb-managed task container via ``docker exec``
  (same semantics as the fork's DockerEnvironment on SWE-bench: fresh
  subshell per command, no tmux state). The container comes from the
  harness-provided TmuxSession.
- One tb process = one condition. MSWEA_PRIMITIVE / MSWEA_TOKEN_BUDGET /
  MSWEA_COMPRESSION_RATIO are process-wide (ratio is read at ``import
  memory`` time), so scripts/run_tbench.py invokes tb once per condition.
- tb runs trials concurrently in one process, so per-task outputs cannot go
  through the MSWEA_TOKEN_LOG_PATH env var (leave it UNSET: the in-agent
  flush then no-ops). This adapter writes trajectory.json and
  token_log.json to per-task dirs under MSWEA_TB_OUTPUT_DIR itself, using
  memory.token_log_dict() so the schema can't drift.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import memory  # noqa: E402  (agentCtx repo root)
from minisweagent.agents.default import DefaultAgent  # noqa: E402
from minisweagent.config import get_config_from_spec  # noqa: E402
from minisweagent.models import get_model  # noqa: E402
from minisweagent.exceptions import Submitted  # noqa: E402
from minisweagent.utils.serialize import recursive_merge  # noqa: E402

from terminal_bench.agents.base_agent import AgentResult, BaseAgent  # noqa: E402
from terminal_bench.agents.failure_mode import FailureMode  # noqa: E402
from terminal_bench.terminal.tmux_session import TmuxSession  # noqa: E402

# Model config first, TB prompt config second: the TB file must win on the
# agent section (step_limit 100, TB templates) while the model file's
# model_name/model_kwargs survive (disjoint keys, recursive merge).
DEFAULT_CONFIG_SPECS = [
    str(REPO_ROOT / "configs" / "config-qwen-vllm.yaml"),
    str(REPO_ROOT / "configs" / "config-tbench.yaml"),
]


class TbContainerEnvironmentConfig(BaseModel):
    cwd: str = ""
    env: dict[str, str] = {}
    timeout: int = 60
    executable: str = os.getenv("MSWEA_DOCKER_EXECUTABLE", "docker")
    interpreter: list[str] = ["bash", "-c"]


class TbContainerEnvironment:
    """mini-swe-agent Environment protocol over an existing tb task container.

    Mirrors minisweagent.environments.docker.DockerEnvironment.execute /
    _check_finished, but attaches to the harness-managed container instead of
    starting its own (no _start_container, no cleanup — tb owns the
    container lifecycle).
    """

    def __init__(self, container, *, config_class: type = TbContainerEnvironmentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.container_id = container.id
        if not self.config.cwd:
            workdir = (container.attrs or {}).get("Config", {}).get("WorkingDir") or "/"
            self.config.cwd = workdir

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        command = action.get("command", "")
        cwd = cwd or self.config.cwd

        cmd = [self.config.executable, "exec", "-w", cwd]
        for key, value in self.config.env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend([self.container_id, *self.config.interpreter, command])

        try:
            result = subprocess.run(
                cmd,
                text=True,
                timeout=timeout or self.config.timeout,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = {"output": result.stdout, "returncode": result.returncode, "exception_info": ""}
        except Exception as e:
            raw_output = getattr(e, "output", None)
            raw_output = (
                raw_output.decode("utf-8", errors="replace") if isinstance(raw_output, bytes) else (raw_output or "")
            )
            output = {
                "output": raw_output,
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {e}",
                "extra": {"exception_type": type(e).__name__, "exception": str(e)},
            }
        self._check_finished(output)
        return output

    def _check_finished(self, output: dict):
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
        return recursive_merge(self.config.model_dump(), platform.uname()._asdict(), kwargs)

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "environment": self.config.model_dump(mode="json"),
                    "environment_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }


class CompressionAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "mswea-compression"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        os.environ.setdefault("MSWEA_COST_TRACKING", "ignore_errors")
        specs = os.environ.get("MSWEA_TB_CONFIGS")
        self._config_specs = specs.split(",") if specs else DEFAULT_CONFIG_SPECS

    @staticmethod
    def _task_id_from_logging_dir(logging_dir: Path | None) -> str:
        # trial dir name is "<task_id>.<i>-of-<n>.<run_id>"; task ids may
        # themselves contain dots (e.g. "crack-7z-hash.easy"), so split on
        # the ".<i>-of-<n>." trial marker rather than the first dot.
        if logging_dir is None:
            return "unknown-task"
        import re

        name = logging_dir.parent.name
        m = re.search(r"\.\d+-of-\d+\.", name)
        return name[: m.start()] if m else name.split(".")[0]

    def perform_task(
        self,
        instruction: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
    ) -> AgentResult:
        task_id = self._task_id_from_logging_dir(logging_dir)
        run_num = os.environ.get("MSWEA_TB_RUN_NUM", "1")
        out_root = os.environ.get("MSWEA_TB_OUTPUT_DIR")
        if out_root:
            out_dir = Path(out_root) / task_id / f"run_{run_num}"
        elif logging_dir is not None:
            out_dir = Path(logging_dir)
        else:
            out_dir = Path.cwd() / "tb-agent-out" / task_id
        out_dir.mkdir(parents=True, exist_ok=True)

        config = recursive_merge(*[get_config_from_spec(spec) for spec in self._config_specs])
        model = get_model(config=config.get("model", {}))
        env = TbContainerEnvironment(session.container, **config.get("environment", {}))

        agent_config = dict(config.get("agent", {}))
        agent_config["output_path"] = out_dir / "trajectory.json"
        agent = DefaultAgent(model, env, **agent_config)

        exit_info: dict = {}
        failure = FailureMode.NONE
        try:
            exit_info = agent.run(instruction)
        except Exception as e:  # step-level uncaught errors re-raise from run()
            failure = FailureMode.UNKNOWN_AGENT_ERROR
            exit_info = {"exit_status": type(e).__name__, "submission": ""}
        finally:
            try:
                (out_dir / "token_log.json").write_text(
                    json.dumps(memory.token_log_dict(agent), indent=2)
                )
                (out_dir / "exit_info.json").write_text(
                    json.dumps(
                        {
                            "task_id": task_id,
                            "run_num": run_num,
                            "exit_status": exit_info.get("exit_status", ""),
                            "n_calls": agent.n_calls,
                            "primitive": os.environ.get("MSWEA_PRIMITIVE", ""),
                            "token_budget": os.environ.get("MSWEA_TOKEN_BUDGET", ""),
                            "compression_ratio": os.environ.get("MSWEA_COMPRESSION_RATIO", ""),
                        },
                        indent=2,
                    )
                )
            except Exception:
                pass

        return AgentResult(
            total_input_tokens=agent._mem_prompt_tokens,
            total_output_tokens=agent._mem_completion_tokens,
            failure_mode=failure,
        )
