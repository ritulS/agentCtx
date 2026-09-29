"""Opt-in vLLM V1 scheduler instrumentation; see KV_CACHE_TRACE.md.

Loaded by --scheduler-cls agentctx.vllm_kv_trace.TracingScheduler. This factory
preserves vLLM's sync/async scheduler selection and never changes allocation.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
import uuid

from agentctx.kv_cache_trace import block_bytes, ownership_snapshot

logger = logging.getLogger(__name__)


class TraceRecorder:
    def __init__(self, scheduler, directory: Path, version: str):
        self.scheduler = scheduler
        self.previous = {}
        self.tick = 0
        self.disabled = False
        self.bytes_per_block, status = block_bytes(
            scheduler.kv_cache_config, scheduler.parallel_config
        )
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"kv-cache-{os.getpid()}-{uuid.uuid4().hex}.jsonl"
        self.stream = self.path.open("x", buffering=1)
        self.write({"type": "metadata", "schema_version": 1,
                    "vllm_version": version, "pid": os.getpid(),
                    "scope": "per_request_per_worker", "bytes_status": status,
                    "bytes_per_block_per_worker": self.bytes_per_block,
                    "tensor_parallel_size": scheduler.parallel_config.tensor_parallel_size,
                    "pipeline_parallel_size": scheduler.parallel_config.pipeline_parallel_size,
                    "cache_group_types": [type(g.kv_cache_spec).__name__
                                          for g in scheduler.kv_cache_config.kv_cache_groups],
                    "measurement": "allocated_pool_slots_including_padding",
                    "sampling": "allocation_changes_at_scheduler_boundaries"})

    def write(self, record):
        self.stream.write(json.dumps({"time": time.time(), **record}) + "\n")

    def capture(self, phase):
        if self.disabled:
            return
        try:
            self.tick += 1
            current = ownership_snapshot(self.scheduler.kv_cache_manager,
                                         self.scheduler.requests, self.bytes_per_block)
            for rid, row in current.items():
                if self.previous.get(rid) != row:
                    self.write({"type": "snapshot", "tick": self.tick,
                                "phase": phase, "request_id": rid, **row})
            for rid in self.previous.keys() - current.keys():
                # Removed from scheduler, including aborts; not a success claim.
                self.write({"type": "finished", "tick": self.tick,
                            "phase": phase, "request_id": rid})
            self.previous = current
        except Exception as exc:
            self.disabled = True
            logger.exception("KV ownership tracing stopped; inference continues")
            try:
                self.write({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
            except OSError:
                pass


class _TracingMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from vllm import __version__

        directory = os.environ.get("AGENTCTX_KV_TRACE_DIR")
        if not directory:
            raise ValueError("TracingScheduler requires AGENTCTX_KV_TRACE_DIR")
        self._kv_trace = TraceRecorder(self, Path(directory), __version__)

    def schedule(self, *args, **kwargs):
        result = super().schedule(*args, **kwargs)
        self._kv_trace.capture("after_schedule")
        return result

    def update_from_output(self, *args, **kwargs):
        result = super().update_from_output(*args, **kwargs)
        self._kv_trace.capture("after_output")
        return result

    def finish_requests(self, *args, **kwargs):
        result = super().finish_requests(*args, **kwargs)
        self._kv_trace.capture("after_finish_requests")
        return result


class TracingScheduler:
    def __new__(cls, *args, **kwargs):
        config = kwargs.get("vllm_config") or args[0]
        if config.scheduler_config.async_scheduling:
            from vllm.v1.core.sched.async_scheduler import AsyncScheduler as Base
        else:
            from vllm.v1.core.sched.scheduler import Scheduler as Base

        class SchedulerWithTrace(_TracingMixin, Base):
            pass

        return SchedulerWithTrace(*args, **kwargs)
