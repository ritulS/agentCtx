"""Unit tests for agentctx.resource_monitor (the per-run physical-resource sampler)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentctx import resource_monitor as rm  # noqa: E402


class ParsingTests(unittest.TestCase):
    def test_container_name_is_read_from_agent_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "agent.log"
            log.write_text(
                "minisweagent.environment: INFO: Started container minisweagent-f8d43bb7 with ID \n"
                "e267b9876f7708a6b49af8bf5f7863f5ef7c945d92d1205d7200352bbc7f4b98\n"
            )
            self.assertEqual(rm.find_container_name(log), "minisweagent-f8d43bb7")
            log.write_text("nothing yet\n")
            self.assertIsNone(rm.find_container_name(log))
            self.assertIsNone(rm.find_container_name(Path(tmp) / "missing.log"))

    def test_nvidia_smi_csv(self):
        gpus = rm.parse_nvidia_smi("0, 61234, 81920, 87\n1, 14, 81920, 0\nbad line\n")
        self.assertEqual([g["index"] for g in gpus], [0, 1])
        self.assertEqual(gpus[0]["mem_used_mb"], 61234.0)
        self.assertEqual(gpus[0]["util_pct"], 87.0)

    def test_vllm_metrics(self):
        text = (
            "# HELP vllm:kv_cache_usage_perc GPU KV-cache usage. 1 means 100 percent usage.\n"
            'vllm:kv_cache_usage_perc{engine="0",model_name="Qwen/Qwen3.5-35B-A3B"} 0.4275\n'
            'vllm:num_requests_running{engine="0",model_name="Qwen/Qwen3.5-35B-A3B"} 12.0\n'
            'vllm:num_requests_waiting{engine="0",model_name="Qwen/Qwen3.5-35B-A3B"} 3.0\n'
        )
        metrics = rm.parse_vllm_metrics(text)
        self.assertEqual(metrics, {"kv_cache_usage_pct": 42.75, "requests_running": 12.0, "requests_waiting": 3.0})
        self.assertEqual(rm.parse_vllm_metrics("")["kv_cache_usage_pct"], None)

    def test_metrics_urls_derived_from_config_chain_or_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp) / "agent.yaml"
            agent.write_text('model:\n  model_kwargs:\n    api_base: "http://localhost:8000/v1"\n')
            summary = Path(tmp) / "summary.yaml"
            summary.write_text("model:\n  model_kwargs:\n    api_base: http://localhost:8001/v1\n")
            urls = rm.metrics_urls([agent, summary, agent, Path(tmp) / "missing.yaml"], env={})
            self.assertEqual(urls, ["http://localhost:8000/metrics", "http://localhost:8001/metrics"])
            self.assertEqual(rm.metrics_urls([agent], env={rm.METRICS_URLS_ENV: ""}), [])
            # A separately served summarizer (--summary-config / MSWEA_SUMMARY_API_BASE) is included.
            self.assertEqual(rm.metrics_urls([agent], env={rm.SUMMARY_CONFIG_ENV: str(summary)}),
                             ["http://localhost:8000/metrics", "http://localhost:8001/metrics"])
            self.assertEqual(rm.metrics_urls([agent], env={rm.SUMMARY_API_BASE_ENV: "http://localhost:8002/v1"}),
                             ["http://localhost:8000/metrics", "http://localhost:8002/metrics"])
            self.assertEqual(rm.metrics_urls([agent], env={rm.SUMMARY_CONFIG_ENV: str(summary),
                                                           rm.SUMMARY_API_BASE_ENV: "http://localhost:8001/v1"}),
                             ["http://localhost:8000/metrics", "http://localhost:8001/metrics"])
            self.assertEqual(rm.metrics_urls([agent], env={rm.SUMMARY_CONFIG_ENV: str(Path(tmp) / "nope.yaml")}),
                             ["http://localhost:8000/metrics"])
            self.assertEqual(rm.metrics_urls([agent], env={rm.METRICS_URLS_ENV: "http://h:1/metrics, http://h:2/metrics"}),
                             ["http://h:1/metrics", "http://h:2/metrics"])

    def test_info_metrics_labels(self):
        text = (
            'vllm:cache_config_info{block_size="16",cache_dtype="auto",enable_prefix_caching="True",'
            'gpu_memory_utilization="0.9",num_gpu_blocks="34567",sliding_window="None"} 1.0\n'
            'vllm:kv_cache_usage_perc{engine="0"} 0.1\n'
        )
        info = rm.parse_info_metrics(text)
        self.assertEqual(list(info), ["vllm:cache_config_info"])
        self.assertEqual(info["vllm:cache_config_info"]["num_gpu_blocks"], "34567")
        self.assertEqual(info["vllm:cache_config_info"]["block_size"], "16")

    def test_server_log_startup_lines_and_serving_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            servers = Path(tmp)
            log = servers / "vllm_qwen35_a3b_20260926_142800.log"
            log.write_text(
                "INFO 09-26 14:28:00 [api_server.py] vLLM API server version 0.11.0\n"
                "INFO 09-26 14:28:01 [config.py] Initializing a V1 LLM engine (v0.11.0) with config: model='Qwen/Qwen3.5-35B-A3B', tensor_parallel_size=4, enable_prefix_caching=True\n"
                "INFO 09-26 14:29:10 [kv_cache_utils.py] Available KV cache memory: 45.12 GiB\n"
                "INFO 09-26 14:29:10 [kv_cache_utils.py] GPU KV cache size: 1,234,567 tokens\n"
                "INFO 09-26 14:29:10 [kv_cache_utils.py] Maximum concurrency for 32,768 tokens per request: 37.68x\n"
                "INFO 09-26 14:29:20 Uvicorn running on http://0.0.0.0:8000\n"
                "INFO 09-26 14:30:00 [loggers.py] Avg prompt throughput: 1000 tokens/s, GPU KV cache usage: 3.0%\n"
                "INFO 09-26 14:30:10 Received request chatcmpl-1\n"
                + "".join(
                    f"INFO 09-26 15:{i:02d}:00 [loggers.py] Avg prompt throughput: 900 tokens/s, "
                    f"GPU KV cache usage: {i}.0%, Prefix cache hit rate: 80.0%\n" for i in range(300)
                )  # a server that has been up for a while
            )
            (servers / "vllm_qwen35_a3b.latest.log").symlink_to(log.name)
            (servers / "vllm_qwen35_a3b.pid").write_text("999999999\n")  # not a live process
            lines = rm.extract_server_log_lines(log)
            self.assertTrue(any("GPU KV cache size: 1,234,567 tokens" in line for line in lines))
            self.assertTrue(any("Available KV cache memory" in line for line in lines))
            self.assertTrue(any("Maximum concurrency" in line for line in lines))
            self.assertFalse(any("Received request" in line for line in lines))
            self.assertFalse(any("KV cache usage" in line for line in lines))  # periodic stats kept apart
            periodic = rm.extract_server_log_periodic_lines(log)
            self.assertEqual(len(periodic), rm.SERVER_LOG_PERIODIC_LINES)
            self.assertIn("GPU KV cache usage: 299.0%", periodic[-1])

            info = rm.capture_serving_info([], servers)
            self.assertEqual(len(info["server_logs"]), 1)
            entry = info["server_logs"][0]
            self.assertEqual(entry["server"], "vllm_qwen35_a3b")
            self.assertEqual(entry["log"], log.name)
            self.assertIs(entry["server_alive"], False)
            self.assertEqual(entry["lines"], lines)
            self.assertEqual(entry["recent_stats_lines"], periodic)
            self.assertEqual(info["endpoints"], {})

    def test_size_parsing(self):
        self.assertEqual(rm.parse_size("240KiB"), 240 * 1024)
        self.assertEqual(rm.parse_size("1.5GiB"), int(1.5 * 1024 ** 3))
        self.assertIsNone(rm.parse_size("--"))

    def test_enable_and_interval_env(self):
        self.assertTrue(rm.enabled({}))
        self.assertFalse(rm.enabled({rm.ENABLE_ENV: "0"}))
        self.assertFalse(rm.enabled({rm.ENABLE_ENV: "off"}))
        self.assertEqual(rm.sample_interval_s({}), rm.DEFAULT_INTERVAL_S)
        self.assertEqual(rm.sample_interval_s({rm.INTERVAL_ENV: "2.5"}), 2.5)
        self.assertEqual(rm.sample_interval_s({rm.INTERVAL_ENV: "-1"}), rm.DEFAULT_INTERVAL_S)


class NoProbes(rm.SharedProbes):
    """Machine-wide probes stubbed out so the test neither shells out nor opens sockets."""

    def gpus(self):
        return [{"index": 0, "mem_used_mb": 1000.0, "mem_total_mb": 81920.0, "util_pct": 50.0}]

    def vllm(self, url):
        return {"kv_cache_usage_pct": 12.5, "requests_running": 4.0, "requests_waiting": 0.0}

    def serving_info(self, metrics_urls, servers_log_dir):
        return {"captured_at": "stub", "endpoints": {url: {"reachable": True} for url in metrics_urls}, "server_logs": []}


class MonitorTests(unittest.TestCase):
    def test_samples_process_tree_and_writes_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            # A child that itself forks a grandchild holding ~8 MB, so the tree sum matters.
            code = (
                "import subprocess, sys, time\n"
                "p = subprocess.Popen([sys.executable, '-c', 'x = bytearray(8 << 20); import time; time.sleep(1.0)'])\n"
                "time.sleep(1.0); p.wait()\n"
            )
            child = subprocess.Popen([sys.executable, "-c", code])
            try:
                monitor = rm.ResourceMonitor(
                    pid=child.pid, run_dir=run_dir, agent_log=None, env={rm.ENABLE_ENV: "1"},
                    metrics_urls=["http://stub/metrics"], interval_s=0.1, probes=NoProbes(),
                ).start()
                child.wait(timeout=30)
            finally:
                if child.poll() is None:
                    child.kill()
            summary = monitor.stop()

            self.assertGreaterEqual(summary["resource_samples"], 5)
            self.assertGreater(summary["peak_agent_rss_mb"], 8.0)
            self.assertIsNone(summary["container_name"])
            self.assertIsNone(summary["peak_container_mem_mb"])
            self.assertEqual(summary["peak_gpu_mem_used_mb"], 1000.0)
            self.assertEqual(summary["mean_gpu_util_pct"], 50.0)
            self.assertEqual(summary["peak_kv_cache_usage_pct"], 12.5)
            self.assertEqual(summary["mean_vllm_requests_running"], 4.0)

            serving = json.loads((run_dir / rm.SERVING_INFO_NAME).read_text())
            self.assertEqual(serving["endpoints"], {"http://stub/metrics": {"reachable": True}})

            lines = (run_dir / rm.LOG_NAME).read_text().splitlines()
            self.assertEqual(len(lines), summary["resource_samples"])
            first = json.loads(lines[0])
            self.assertEqual(first["vllm"], {"http://stub/metrics": NoProbes().vllm("")})
            self.assertGreaterEqual(first["elapsed_s"], 0.0)

    def test_summary_covers_exactly_the_logged_samples_when_a_probe_hangs(self):
        """stop() must not return a summary that the thread then outgrows in the log."""

        class SlowProbes(NoProbes):
            def __init__(self):
                super().__init__()
                self.release = threading.Event()
                self.calls = 0

            def gpus(self):
                self.calls += 1
                if self.calls >= 2:
                    self.release.wait(10)  # from the 2nd sample on, block inside a probe
                return super().gpus()

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
            probes = SlowProbes()
            monitor = rm.ResourceMonitor(pid=child.pid, run_dir=run_dir, env={}, interval_s=0.05, probes=probes)
            monitor.stop_join_timeout_s = 0.2
            try:
                monitor.start()
                deadline = time.monotonic() + 5
                while probes.calls < 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
                summary = monitor.stop()  # the join times out while sample #2 is stuck
                probes.release.set()
                monitor._thread.join(timeout=10)
            finally:
                child.kill()
            lines = (run_dir / rm.LOG_NAME).read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(summary["resource_samples"], 1)  # the stuck sample is discarded, not logged late

    def test_serving_info_capture_does_not_delay_the_first_sample(self):
        class SlowServingProbes(NoProbes):
            def __init__(self):
                super().__init__()
                self.release = threading.Event()

            def serving_info(self, metrics_urls, servers_log_dir):
                self.release.wait(10)  # slow endpoint / huge server log
                return super().serving_info(metrics_urls, servers_log_dir)

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
            probes = SlowServingProbes()
            monitor = rm.ResourceMonitor(pid=child.pid, run_dir=run_dir, env={}, interval_s=0.05, probes=probes).start()
            child.wait()
            self.assertGreaterEqual(len(monitor.samples), 3)  # sampled while serving info was still pending
            self.assertTrue(all(s["agent_rss_mb"] is not None for s in monitor.samples[:3]))
            self.assertFalse((run_dir / rm.SERVING_INFO_NAME).exists())
            probes.release.set()
            summary = monitor.stop()  # waits (bounded) for the serving info to land
            self.assertEqual(summary["resource_samples"], len((run_dir / rm.LOG_NAME).read_text().splitlines()))
            self.assertTrue((run_dir / rm.SERVING_INFO_NAME).exists())

    def test_stop_waits_for_the_last_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
            monitor = rm.ResourceMonitor(pid=child.pid, run_dir=run_dir, env={}, interval_s=0.05, probes=NoProbes()).start()
            child.wait()
            summary = monitor.stop()
            lines = (run_dir / rm.LOG_NAME).read_text().splitlines()
            self.assertEqual(len(lines), summary["resource_samples"])
            self.assertFalse(monitor._thread.is_alive())

    def test_start_for_process_respects_disable_env(self):
        self.assertIsNone(rm.start_for_process(1, Path("."), agent_log=None, env={rm.ENABLE_ENV: "0"}, config_paths=[]))

    def test_summary_of_a_monitor_without_samples(self):
        monitor = rm.ResourceMonitor(pid=1, run_dir=Path("."), env={}, interval_s=1.0, probes=NoProbes())
        summary = monitor.summary()
        self.assertEqual(summary["resource_samples"], 0)
        self.assertIsNone(summary["peak_agent_rss_mb"])
        self.assertIsNone(summary["peak_gpu_mem_used_mb"])


if __name__ == "__main__":
    unittest.main()
