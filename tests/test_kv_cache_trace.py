"""KV ownership accounting, lifecycle, and step joins without a GPU."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentctx.kv_cache_trace import block_bytes, export_steps, ownership_snapshot, request_matches
from agentctx.vllm_kv_trace import TraceRecorder, _TracingMixin, TracingScheduler


def block(number, null=False):
    return NS(block_id=number, is_null=null)


class Manager:
    def __init__(self, allocations):
        self.allocations = allocations

    def get_blocks(self, rid):
        return NS(blocks=self.allocations.get(rid, ()))


def scheduler(manager):
    return NS(kv_cache_manager=manager, requests=dict.fromkeys(manager.allocations),
              kv_cache_config=NS(num_blocks=100, kv_cache_tensors=[NS(size=10000), NS(size=20000)],
                                 kv_cache_groups=[]),
              parallel_config=NS(tensor_parallel_size=4, pipeline_parallel_size=1))


class OwnershipTests(unittest.TestCase):
    def test_shared_exclusive_hybrid_duplicates_and_null(self):
        mgr = Manager({"A": [[block(0, True), block(1), block(2)], [block(3), block(1)]],
                       "B": [[block(1), block(4)]], "waiting": []})
        rows = ownership_snapshot(mgr, mgr.allocations, 100)
        self.assertEqual(rows["A"]["exclusive_blocks"], 2)
        self.assertEqual(rows["A"]["shared_blocks"], 1)
        self.assertEqual(rows["A"]["total_bytes_per_worker"], 300)
        self.assertEqual(rows["B"]["exclusive_bytes_per_worker"], 100)
        self.assertEqual(rows["waiting"]["total_blocks"], 0)
        # B finishing changes A's classification without changing A's blocks.
        rows = ownership_snapshot(mgr, ["A"], 100)
        self.assertEqual(rows["A"]["exclusive_blocks"], 3)
        self.assertEqual(rows["A"]["shared_blocks"], 0)

    def test_pool_bytes_and_unknown_layout(self):
        s = scheduler(Manager({}))
        self.assertEqual(block_bytes(s.kv_cache_config, s.parallel_config), (300, "available"))
        s.parallel_config.pipeline_parallel_size = 2
        self.assertEqual(block_bytes(s.kv_cache_config, s.parallel_config),
                         (None, "unsupported_pipeline_parallelism"))
        rows = ownership_snapshot(Manager({"A": [[block(1)]]}), ["A"], None)
        self.assertIsNone(rows["A"]["total_bytes_per_worker"])
        self.assertEqual(rows["A"]["total_blocks"], 1)

    def test_lifecycle_and_step_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = "chatcmpl-a-1234abcd", "cmpl-b-0-5678abcd"
            summ = "chatcmpl-sum-9abcdef0"  # summarizer request on the same server
            mgr = Manager({a: [[block(1), block(2)]], b: [[block(1), block(3)]]})
            s = scheduler(mgr)
            recorder = TraceRecorder(s, root, "test")
            self.addCleanup(recorder.stream.close)
            recorder.capture("after_schedule")
            recorder.capture("after_schedule")  # unchanged, no duplicate rows
            del s.requests[b]
            recorder.capture("after_finish_requests")
            del s.requests[a]
            recorder.capture("after_output")
            mgr.allocations[summ] = [[block(1), block(5), block(6)]]
            s.requests[summ] = None
            recorder.capture("after_schedule")
            del s.requests[summ]
            recorder.capture("after_output")
            (root / "token_log.json").write_text(json.dumps({
                "model_call_records": [
                    {"step": 1, "response_id": "chatcmpl-a"},
                    {"step": 2, "response_id": "cmpl-b"},
                    {"step": 3, "response_id": None},
                    {"step": 4, "response_id": "chatcmpl-other"}],
                "summary_outcomes": [
                    {"step": 2, "primitive": "summarization", "accepted": True,
                     "response_ids": ["chatcmpl-rejected", "chatcmpl-sum"]},
                    {"step": 3, "primitive": "summarization", "accepted": False}]}))
            result = export_steps(root, root)
            self.assertEqual(result["schema_version"], 2)
            self.assertTrue(any("shared" in n for n in result["notes"]))
            first, second, missing, absent = result["steps"]
            rejected, accepted = result["summary_calls"]
            self.assertEqual(rejected["status"], "not_found")
            self.assertEqual((rejected["attempt"], accepted["attempt"]), (1, 2))
            self.assertEqual(accepted["status"], "complete")
            self.assertEqual(accepted["request_id"], summ)
            # Per-attempt acceptance: the rejected first query is not "accepted".
            self.assertEqual((rejected["attempt_accepted"], rejected["event_accepted"]), (False, True))
            self.assertEqual((accepted["attempt_accepted"], accepted["event_accepted"]), (True, True))
            self.assertIsNone(accepted["interrupted"])
            self.assertEqual(accepted["peak_exclusive_blocks"], 3)  # a already finished
            self.assertEqual(accepted["primitive"], "summarization")
            # Outcomes logged before response ids existed are reported, not guessed.
            self.assertEqual(len(result["summary_calls"]), 2)
            self.assertTrue(any("summary_outcomes[1]" in w for w in result["warnings"]))
            self.assertEqual(first["status"], "complete")
            self.assertEqual(len(first["samples"]), 2)
            self.assertEqual(first["peak_exclusive_bytes_per_worker"], 600)
            self.assertEqual(first["peak_shared_bytes_per_worker"], 300)
            self.assertEqual(first["peak_total_bytes_per_worker"], 600)
            self.assertEqual(second["status"], "complete")
            self.assertEqual(missing["status"], "missing_response_id")
            self.assertEqual(absent["status"], "not_found")

    def test_strict_request_matching(self):
        self.assertTrue(request_matches("chatcmpl-A", "chatcmpl-A"))
        self.assertTrue(request_matches("cmpl-A", "cmpl-A-0-1234abcd"))
        self.assertFalse(request_matches("chatcmpl-A", "chatcmpl-AB"))
        self.assertFalse(request_matches("cmpl-A", "cmpl-A-1-1234abcd"))
        self.assertFalse(request_matches("chatcmpl-A", "chatcmpl-A_1"))

    def test_partial_trace_error_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "token_log.json").write_text(json.dumps({"model_call_records": [
                {"step": 1, "response_id": "chatcmpl-a"}]}))
            record = {"type": "snapshot", "request_id": "chatcmpl-a", "total_blocks": 2}
            path = root / "kv-cache-test.jsonl"
            path.write_text(json.dumps(record) + '\n{"type":')
            result = export_steps(root, root)
            self.assertEqual(result["steps"][0]["status"], "partial")
            self.assertEqual(len(result["warnings"]), 1)
            (root / "kv-cache-other.jsonl").write_text(json.dumps(record) + "\n")
            self.assertEqual(export_steps(root, root)["steps"][0]["status"], "ambiguous_request")

    def test_trace_failure_does_not_stop_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = scheduler(Manager({"A": [[block(1)]]}))
            rec = TraceRecorder(s, Path(tmp), "test")
            self.addCleanup(rec.stream.close)
            with patch.object(s.kv_cache_manager, "get_blocks", side_effect=RuntimeError("bad layout")):
                with self.assertLogs("agentctx.vllm_kv_trace", level="ERROR"):
                    rec.capture("after_schedule")
            self.assertTrue(rec.disabled)
            self.assertEqual(json.loads(rec.path.read_text().splitlines()[-1])["type"], "error")


@unittest.skipUnless(importlib.util.find_spec("vllm"), "vLLM not installed")
class RealVllmTests(unittest.TestCase):
    def test_real_block_manager_shares_then_releases_prefix(self):
        import torch
        from vllm.sampling_params import SamplingParams
        from vllm.v1.request import Request
        from vllm.v1.core.kv_cache_manager import KVCacheManager
        from vllm.v1.kv_cache_interface import FullAttentionSpec, KVCacheConfig, KVCacheGroupSpec, KVCacheTensor
        spec = FullAttentionSpec(block_size=16, num_kv_heads=2, head_size=32, dtype=torch.float16)
        config = KVCacheConfig(num_blocks=100,
            kv_cache_tensors=[KVCacheTensor(size=100 * spec.page_size_bytes, shared_by=["layer"])],
            kv_cache_groups=[KVCacheGroupSpec(layer_names=["layer"], kv_cache_spec=spec)])
        manager = KVCacheManager(config, max_model_len=1024, hash_block_size=16)
        params = SamplingParams(max_tokens=10)
        a = Request("A", [1] * 32, params, None)
        b = Request("B", [1] * 16 + [2] * 16, params, None)
        # First block hashes equal; the second block diverges.
        a.block_hashes = [b"a" * 32, b"b" * 32]
        b.block_hashes = [b"a" * 32, b"c" * 32]
        self.assertIsNotNone(manager.allocate_slots(a, 32))
        cached, count = manager.get_computed_blocks(b)
        self.assertEqual(count, 16)
        self.assertIsNotNone(manager.allocate_slots(b, 16, count, cached))
        rows = ownership_snapshot(manager, ["A", "B"], spec.page_size_bytes)
        self.assertEqual(rows["A"]["shared_blocks"], 1)
        self.assertEqual(rows["A"]["exclusive_blocks"], 1)
        manager.free(b)
        rows = ownership_snapshot(manager, ["A"], spec.page_size_bytes)
        self.assertEqual(rows["A"]["exclusive_blocks"], 2)

    def test_factory_preserves_sync_and_async_scheduler(self):
        from vllm.v1.core.sched.scheduler import Scheduler
        from vllm.v1.core.sched.async_scheduler import AsyncScheduler
        for asynchronous, base in ((False, Scheduler), (True, AsyncScheduler)):
            config = NS(scheduler_config=NS(async_scheduling=asynchronous))
            # Use installed classes and factory, without starting an engine.
            with patch.object(_TracingMixin, "__init__", return_value=None):
                obj = TracingScheduler(vllm_config=config)
            self.assertIsInstance(obj, base)


if __name__ == "__main__":
    unittest.main()
