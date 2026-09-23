"""Summarization model settings shared by the runner and agent.

Keep this module independent of tokenizers and model clients so metadata can
be resolved without loading inference dependencies.
"""

import os
from pathlib import Path

from agentctx import WORKSPACE_ROOT


def _resolve_config_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute() and not p.exists():
        alt = WORKSPACE_ROOT / p
        if alt.exists():
            return alt
    return p


def summary_model_config() -> dict | None:
    """Return the `model:` config dict for the summarization model, or None
    when no override is set (→ use the agent's model)."""
    cfg_path = os.environ.get("MSWEA_SUMMARY_MODEL_CONFIG", "").strip()
    name     = os.environ.get("MSWEA_SUMMARY_MODEL_NAME", "").strip()
    api_base = os.environ.get("MSWEA_SUMMARY_API_BASE", "").strip()
    if not (cfg_path or name or api_base):
        return None

    cfg: dict = {}
    if cfg_path:
        import yaml
        path = _resolve_config_path(cfg_path)
        if not path.exists():
            raise FileNotFoundError(
                f"MSWEA_SUMMARY_MODEL_CONFIG points at a missing file: {cfg_path}"
            )
        cfg = dict((yaml.safe_load(path.read_text()) or {}).get("model", {}) or {})
    if name:
        cfg["model_name"] = name
    if api_base:
        cfg.setdefault("model_kwargs", {})
        cfg["model_kwargs"] = {**cfg["model_kwargs"], "api_base": api_base}
    if not cfg.get("model_name"):
        raise ValueError(
            "Summarization model override is set but no model_name could be "
            "resolved (check MSWEA_SUMMARY_MODEL_CONFIG / MSWEA_SUMMARY_MODEL_NAME)."
        )
    cfg.setdefault("model_class", "litellm_textbased")
    cfg.setdefault("cost_tracking", "ignore_errors")
    return cfg


def summary_model_info() -> dict:
    """Small provenance record for the token log / result rows."""
    cfg = summary_model_config()
    if cfg is None:
        return {"source": "agent_model"}
    return {
        "source":      "override",
        "config_path": os.environ.get("MSWEA_SUMMARY_MODEL_CONFIG", "").strip() or None,
        "model_name":  cfg.get("model_name"),
        "api_base":    (cfg.get("model_kwargs") or {}).get("api_base"),
    }
