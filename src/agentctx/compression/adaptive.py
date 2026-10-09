"""Per-agent compression settings and user-supplied post-trigger policies.

Policies receive one event after all compression in a query and return settings for the next model
query (or None to retain the current settings). No process-wide state is changed.
"""

from dataclasses import asdict, dataclass
import importlib
import json
import math
import os
from pathlib import Path
from typing import Callable


PRIMITIVES = frozenset({
    "truncation", "summarization", "structured_summarize",
    "summarization_free", "structured_summarize_free",
    "summarization_partial", "structured_summarize_partial",
    "tool_result_clear", "scored_tool_result_clear",
    "trc_summarize", "trc_structured_summarize", "online_trc",
    "online_trc_summarize_partial", "online_trc_structured_summarize_partial",
    "staggered_alternate", "staggered_random",
})


ONLINE_PRIMITIVES = frozenset({
    "online_trc", "online_trc_summarize_partial", "online_trc_structured_summarize_partial",
})


@dataclass(frozen=True)
class CompressionConfig:
    primitive: str
    budget: int | None = None  # None disables budget fallback for online primitives
    depth: float = 0.5
    freeze_k: int = 4
    step_interval: int | None = None  # steps since last online trigger / interval change

    def __post_init__(self):
        if self.primitive not in PRIMITIVES:
            raise ValueError(f"Unknown compression primitive: {self.primitive!r}")
        if self.budget is None:
            if self.primitive not in ONLINE_PRIMITIVES:
                raise ValueError("budget is required for budget-triggered primitives")
        elif type(self.budget) is not int or self.budget <= 0:
            raise ValueError("budget must be a positive integer token count")
        if (isinstance(self.depth, bool) or not isinstance(self.depth, (int, float))
                or not math.isfinite(self.depth) or not 0 < self.depth <= 1):
            raise ValueError("depth must be finite and in (0, 1]")
        if type(self.freeze_k) is not int or self.freeze_k < 0:
            raise ValueError("freeze_k must be a nonnegative integer")
        if self.step_interval is not None:
            if self.primitive not in ONLINE_PRIMITIVES:
                raise ValueError("step_interval is only supported by online primitives")
            if type(self.step_interval) is not int or self.step_interval <= 0:
                raise ValueError("step_interval must be a positive integer")
        if self.primitive.startswith("staggered_") and self.budget not in (10000, 15000, 20000):
            raise ValueError("staggered primitives require budget 10000, 15000, or 20000")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompressionEvent:
    index: int  # 1-based policy decisions; at most one per query
    step: int  # attempted agent model calls (same convention as compression_events.jsonl)
    kind: str  # "budget" or "online_trc"
    config: CompressionConfig
    tokens_before: int
    tokens_after: int
    messages: tuple[dict, ...]  # deep copy after ALL compression in this query
    kinds: tuple[str, ...] = ()  # ordered operation kinds; may contain both online_trc and budget

    @property
    def tokens_saved(self) -> int:
        return self.tokens_before - self.tokens_after


CompressionPolicy = Callable[[CompressionEvent], CompressionConfig | None]


class CompressionSchedule:
    """Apply configs[0] initially, advance on each event, then hold the last.

    Position comes from the agent's event index, so this object can be shared
    between agents without sharing their progress.
    """

    def __init__(self, configs):
        self.configs = tuple(configs)
        if not self.configs or not all(isinstance(c, CompressionConfig) for c in self.configs):
            raise ValueError("schedule requires a nonempty sequence of CompressionConfig")

    @property
    def initial(self) -> CompressionConfig:
        return self.configs[0]

    def __call__(self, event: CompressionEvent) -> CompressionConfig:
        return self.configs[min(event.index, len(self.configs) - 1)]

    @classmethod
    def from_json(cls, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("adaptive schedule must be a JSON array of configurations")
        return cls(CompressionConfig(**entry) for entry in data)


def resolve_policy(policy=None, config=None):
    """Resolve explicit Python arguments or the subprocess environment API.

    Explicit arguments take precedence. Environment policy functions are loaded
    once per agent from 'module:function'; they must be importable in the worker.
    """
    if policy is None and config is None:
        manifest_path = os.environ.get("MSWEA_ADAPTIVE_MANIFEST")
        if manifest_path:
            from agentctx.compression.selection import load_selection, policy_source
            import hashlib
            selection = load_selection(manifest_path)
            spec = selection["spec"]
            if spec["kind"] == "schedule":
                policy = CompressionSchedule(CompressionConfig(**c) for c in spec["configs"])
                return policy, policy.initial
            source = policy_source(spec["policy"])
            source_text = source.read_text(encoding="utf-8")
            if hashlib.sha256(source_text.encode()).hexdigest() != spec["source_sha256"]:
                raise ValueError("Adaptive policy source changed after launch")
            module, name = spec["policy"].split(":", 1)
            policy = getattr(importlib.import_module(module), name)
            config = CompressionConfig(**spec["initial"])
            if not callable(policy):
                raise TypeError("adaptive policy must be callable")
            return policy, config
        schedule_path = os.environ.get("MSWEA_ADAPTIVE_SCHEDULE")
        policy_path = os.environ.get("MSWEA_ADAPTIVE_POLICY")
        if schedule_path and policy_path:
            raise ValueError("Set only one of MSWEA_ADAPTIVE_SCHEDULE and MSWEA_ADAPTIVE_POLICY")
        if schedule_path:
            policy = CompressionSchedule.from_json(schedule_path)
        elif policy_path:
            module, sep, name = policy_path.partition(":")
            if not sep or not module or not name:
                raise ValueError("MSWEA_ADAPTIVE_POLICY must be module:function")
            policy = getattr(importlib.import_module(module), name)
        else:
            return None, None
    if policy is not None and not callable(policy):
        raise TypeError("memory_policy must be callable")
    if config is None:
        if isinstance(policy, CompressionSchedule):
            config = policy.initial
        else:
            config = CompressionConfig(
                primitive=os.environ.get("MSWEA_PRIMITIVE", ""),
                budget=(int(os.environ["MSWEA_TOKEN_BUDGET"])
                        if os.environ.get("MSWEA_TOKEN_BUDGET") else None),
                depth=float(os.environ.get("MSWEA_COMPRESSION_RATIO", "0.5")),
            )
    if not isinstance(config, CompressionConfig):
        raise TypeError("memory_config must be a CompressionConfig")
    return policy, config
