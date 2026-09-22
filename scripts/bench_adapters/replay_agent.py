"""Harbor agent that replays a saved mini-swe-agent trajectory, without a model.

Terminal-Bench has no "patch": the agent's product is the final state of the
task container, which Harbor deletes after the verifier ran. When the verifier
itself failed (typically ``VerifierTimeoutError``), the only way to grade the
same generation again is to rebuild that state by re-executing the agent's
commands, in order, in a fresh container, and to let Harbor verify the result.
This agent does exactly that:

* it reads ``REPLAY_TRAJECTORY`` (a ``trajectory.json`` written by the
  compression-aware DefaultAgent), takes every ``extra.actions[].command`` of
  the assistant turns and runs them through ``environment.exec`` with the same
  per-command timeout and environment variables the original run used
  (``REPLAY_CONFIG_SPECS``, default ``configs/config-tbench.yaml``);
* it never calls a language model, and it keeps going after a command error
  or timeout, as the original agent did;
* it records, per command, whether the output and return code matched the
  observation stored in the trajectory (``replay_log.json``) and a summary
  (``replay_summary.json``) that ``scripts/replay_reverify_tb.py`` uses as
  evidence.

Only trajectories whose assistant turns are all present can be replayed; the
runner checks that before launching Harbor (see ``analyze_trajectory`` there).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.environments.base import BaseEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402
from scripts.bench_adapters.harbor_process import write_json  # noqa: E402

DEFAULT_CONFIG_SPECS = [str(REPO_ROOT / "configs" / "config-tbench.yaml")]
DEFAULT_EXEC_TIMEOUT = 60


def load_environment_settings(specs: list[str]) -> tuple[dict[str, str], int]:
    """(env, timeout) of the ``environment`` section merged across config files."""
    env: dict[str, str] = {}
    timeout = DEFAULT_EXEC_TIMEOUT
    for spec in specs:
        payload = yaml.safe_load(Path(spec).read_text()) or {}
        section = payload.get("environment") or {}
        env.update({str(k): str(v) for k, v in (section.get("env") or {}).items()})
        if section.get("timeout") is not None:
            timeout = int(section["timeout"])
    return env, timeout


def extract_actions(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    """Commands of every assistant turn, paired with the recorded observation.

    ``original`` is None when the observation was cleared by a compression
    primitive (no ``extra.raw_output``) or when the turn issued several
    commands (their outputs are merged in one observation).
    """
    messages = trajectory.get("messages") or []
    actions: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        commands = [
            action.get("command", "")
            for action in ((message.get("extra") or {}).get("actions") or [])
        ]
        observation = messages[index + 1] if index + 1 < len(messages) else {}
        extra = observation.get("extra") if observation.get("role") == "user" else None
        for position, command in enumerate(commands):
            original = None
            if len(commands) == 1 and isinstance(extra, dict) and "raw_output" in extra:
                original = {"raw_output": extra.get("raw_output"), "returncode": extra.get("returncode")}
            actions.append({
                "turn": index, "position": position, "command": command,
                "original": original,
            })
    return actions


def normalize_output(text: str | None) -> str:
    return "\n".join(line.rstrip() for line in (text or "").strip().splitlines())


def compare_with_original(original: dict[str, Any] | None, output: str, returncode: int) -> dict[str, Any]:
    if original is None:
        return {"output_match": None, "returncode_match": None}
    return {
        "output_match": normalize_output(original.get("raw_output")) == normalize_output(output),
        "returncode_match": original.get("returncode") == returncode,
    }


class ReplayAgent(BaseAgent):
    """Re-execute a saved command sequence; Harbor then runs the verifier."""

    @staticmethod
    def name() -> str:
        return "mswea-replay"

    def version(self) -> str | None:
        return "1.0.0"

    def __init__(self, logs_dir: Path, model_name: str | None = None, **kwargs: Any) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        trajectory = kwargs.get("trajectory") or os.environ.get("REPLAY_TRAJECTORY")
        if not trajectory:
            raise RuntimeError("REPLAY_TRAJECTORY must point at a trajectory.json")
        self.trajectory_path = Path(trajectory)
        specs = kwargs.get("config_specs") or os.environ.get("REPLAY_CONFIG_SPECS")
        self.config_specs = specs.split(os.pathsep) if isinstance(specs, str) else (specs or DEFAULT_CONFIG_SPECS)
        self.env, self.timeout = load_environment_settings(self.config_specs)

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        del instruction  # the task prompt is not needed to replay commands
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        raw = self.trajectory_path.read_bytes()
        trajectory = json.loads(raw)
        actions = extract_actions(trajectory)
        summary = {
            "trajectory": str(self.trajectory_path),
            "trajectory_sha256": hashlib.sha256(raw).hexdigest(),
            "config_specs": self.config_specs,
            "exec_timeout_sec": self.timeout,
            "n_actions": len(actions),
            "n_executed": 0,
            "n_errors": 0,
            "n_compared": 0,
            "n_output_matched": 0,
            "n_returncode_matched": 0,
            "started_at": time.time(),
            "finished_at": None,
            "complete": False,
        }
        log: list[dict[str, Any]] = []
        write_json(self.logs_dir / "replay_summary.json", summary)
        try:
            for step, action in enumerate(actions):
                started = time.time()
                exception = ""
                try:
                    result = await environment.exec(
                        command=action["command"], cwd=None,
                        env=self.env or None, timeout_sec=self.timeout,
                    )
                    output = (result.stdout or "") + (result.stderr or "")
                    returncode = result.return_code
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # timeouts and exec failures: continue like the agent did
                    output, returncode = "", -1
                    exception = f"{type(exc).__name__}: {exc}"
                    summary["n_errors"] += 1
                comparison = compare_with_original(action["original"], output, returncode)
                if comparison["output_match"] is not None:
                    summary["n_compared"] += 1
                    summary["n_output_matched"] += int(comparison["output_match"])
                    summary["n_returncode_matched"] += int(comparison["returncode_match"])
                summary["n_executed"] += 1
                log.append({
                    "step": step, "turn": action["turn"], "command": action["command"],
                    "returncode": returncode, "exception": exception,
                    "duration_s": round(time.time() - started, 3),
                    "output_head": output[:2000],
                    **comparison,
                })
                write_json(self.logs_dir / "replay_log.json", log)
                write_json(self.logs_dir / "replay_summary.json", summary)
            summary["complete"] = summary["n_executed"] == summary["n_actions"]
        finally:
            summary["finished_at"] = time.time()
            write_json(self.logs_dir / "replay_summary.json", summary)
            context.n_input_tokens = 0
            context.n_output_tokens = 0
