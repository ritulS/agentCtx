"""Per-run physical resource sampling for the SWE-bench runner.

While ``SweBench._run_agent`` waits for a mini-swe-agent subprocess, a
``ResourceMonitor`` thread samples, every ``AGENTCTX_RESOURCE_SAMPLE_S``
seconds (default 10):

- host RAM of the agent process tree (RSS summed over the agent's python
  process and its descendants, read from ``/proc``);
- memory of the task container (cgroup v2 ``memory.current`` / ``memory.stat``
  of the ``minisweagent-<hex>`` container the agent reports in ``agent.log``;
  ``docker stats`` is the fallback);
- GPU memory and utilization of every GPU (``nvidia-smi``), machine-wide;
- vLLM ``/metrics`` (KV-cache usage, running/waiting requests) of the model
  endpoints named in the agent config chain, machine-wide.

The GPU and vLLM readings are shared by every monitor of the runner process
(one ``nvidia-smi``/HTTP fetch per ~2 s at most) and are the same for all runs
concurrent on the machine: they describe the load the run was part of, not the
run's own share. Everything is best effort; a probe that fails is recorded as
``null`` and never affects the run.

Samples go to ``<run_dir>/resource_log.jsonl`` (one JSON object per line) and
``ResourceMonitor.stop()`` returns the summary fields (``peak_agent_rss_mb``,
``peak_container_mem_mb``, ``peak_gpu_mem_used_mb``, ...) that the runner
merges into the run's row of ``experiment_results.json``.

``<run_dir>/serving_info.json`` is written once at the start of the run: the
``/v1/models`` listing and the ``vllm:*_info`` gauges (cache config: block
size, number of GPU blocks, KV dtype, prefix caching) of every endpoint, plus
the startup lines of the live vLLM logs under ``logs/servers/`` ("GPU KV cache
size: N tokens", "Available KV cache memory", "Maximum concurrency", ...).
Together with ``step_prompt_tokens`` / ``step_completion_tokens`` in
``token_log.json`` this is what a later analysis needs to turn a run's context
length into the KV-cache memory it occupied (bytes per token = KV cache memory
/ KV cache size in tokens).

Set ``AGENTCTX_RESOURCE_MONITOR=0`` to disable; ``AGENTCTX_VLLM_METRICS_URLS``
(comma-separated) overrides the metrics endpoints derived from the configs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from agentctx import WORKSPACE_ROOT

ENABLE_ENV = "AGENTCTX_RESOURCE_MONITOR"
INTERVAL_ENV = "AGENTCTX_RESOURCE_SAMPLE_S"
METRICS_URLS_ENV = "AGENTCTX_VLLM_METRICS_URLS"
# The summarizer may be served separately (--summary-config → MSWEA_SUMMARY_MODEL_CONFIG,
# or a bare MSWEA_SUMMARY_API_BASE); both are read by agentctx.summary_config.
SUMMARY_CONFIG_ENV = "MSWEA_SUMMARY_MODEL_CONFIG"
SUMMARY_API_BASE_ENV = "MSWEA_SUMMARY_API_BASE"
DEFAULT_INTERVAL_S = 10.0
LOG_NAME = "resource_log.jsonl"
SERVING_INFO_NAME = "serving_info.json"
SERVING_INFO_MAX_AGE_S = 600.0     # re-capture per runner process at most this often
SERVER_LOG_HEAD_BYTES = 4 * 1024 * 1024  # startup lines sit at the top of each vLLM log
SERVER_LOG_LINE = re.compile(
    r"KV cache|Maximum concurrency|GPU blocks|kv_cache_dtype|enable_prefix_caching|"
    r"gpu_memory_utilization|max_model_len|block_size|Model loading took|Loading model weights took|"
    r"vLLM API server version|Uvicorn running|Initializing a|tensor_parallel_size|quantization|dtype=",
    re.I,
)
SERVER_LOG_MAX_LINES = 200          # startup/config lines kept per log
SERVER_LOG_TAIL_BYTES = 256 * 1024  # the periodic usage lines are read from the end of the log
SERVER_LOG_PERIODIC = re.compile(r"Avg prompt throughput|KV cache usage|Prefix cache hit rate")
SERVER_LOG_PERIODIC_LINES = 5       # most recent periodic lines kept
_INFO_METRIC_LINE = re.compile(r"^(vllm:[a-z_]*_info)\{([^}]*)\}\s+\S+")
_LABEL = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:[^"\\]|\\.)*)"')

# mini-swe-agent's DockerEnvironment logs this (INFO) right after `docker run`;
# stdout+stderr of the agent go to agent.log, so the name can be read from there.
CONTAINER_LINE = re.compile(r"Started container (minisweagent-[0-9a-f]+)")
CONTAINER_LOG_READ_BYTES = 256 * 1024
API_BASE_LINE = re.compile(r"""^\s*api_base\s*:\s*["']?(https?://[^"'\s]+)""", re.MULTILINE)

_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
_MB = 1024 * 1024


# ── Configuration ───────────────────────────────────────────────────────────────


def enabled(env: dict | None = None) -> bool:
    value = (env if env is not None else os.environ).get(ENABLE_ENV, "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def sample_interval_s(env: dict | None = None) -> float:
    value = (env if env is not None else os.environ).get(INTERVAL_ENV, "")
    try:
        interval = float(value)
    except ValueError:
        return DEFAULT_INTERVAL_S
    return interval if interval > 0 else DEFAULT_INTERVAL_S


def metrics_url(api_base: str) -> str:
    return re.sub(r"/v\d+/?$", "", api_base.strip().rstrip("/")) + "/metrics"


def metrics_urls(config_paths: list[str | Path], env: dict | None = None) -> list[str]:
    """vLLM ``/metrics`` URLs: the env override, else one per ``api_base`` in the agent
    config chain and in the summarizer override (``MSWEA_SUMMARY_MODEL_CONFIG`` file,
    ``MSWEA_SUMMARY_API_BASE``), in that order, de-duplicated."""
    environ = env if env is not None else os.environ
    override = environ.get(METRICS_URLS_ENV)
    if override is not None:
        return [url.strip() for url in override.split(",") if url.strip()]
    paths = list(config_paths)
    summary_config = environ.get(SUMMARY_CONFIG_ENV, "").strip()
    if summary_config:
        path = Path(summary_config)
        if not path.is_absolute() and not path.exists() and (WORKSPACE_ROOT / path).exists():
            path = WORKSPACE_ROOT / path  # same resolution as agentctx.summary_config
        paths.append(path)
    urls: list[str] = []
    for path in paths:
        try:
            text = Path(path).read_text()
        except OSError:
            continue
        for api_base in API_BASE_LINE.findall(text):
            if metrics_url(api_base) not in urls:
                urls.append(metrics_url(api_base))
    summary_api_base = environ.get(SUMMARY_API_BASE_ENV, "").strip()
    if summary_api_base and metrics_url(summary_api_base) not in urls:
        urls.append(metrics_url(summary_api_base))
    return urls


# ── Probes ──────────────────────────────────────────────────────────────────────


def process_tree_rss_bytes(root_pid: int) -> int | None:
    """RSS summed over ``root_pid`` and all its descendants, from /proc."""
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/stat") as handle:
                stat = handle.read()
            with open(f"/proc/{pid}/statm") as handle:
                statm = handle.read()
        except OSError:
            continue  # process vanished between listdir and open
        # comm may contain spaces/parentheses; fields resume after the last ')'.
        fields = stat[stat.rfind(")") + 2:].split()
        try:
            ppid = int(fields[1])
            rss[pid] = int(statm.split()[1]) * _PAGE_SIZE
        except (IndexError, ValueError):
            continue
        children.setdefault(ppid, []).append(pid)
    if root_pid not in rss:
        return None
    total = 0
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        total += rss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return total


def find_container_name(log_file: Path) -> str | None:
    """The ``minisweagent-<hex>`` container named in the agent log, once it appears."""
    try:
        with log_file.open("rb") as handle:
            head = handle.read(CONTAINER_LOG_READ_BYTES)
    except OSError:
        return None
    match = CONTAINER_LINE.search(head.decode("utf-8", "replace"))
    return match.group(1) if match else None


def container_cgroup_dir(container: str, docker: str, env: dict) -> Path | None:
    """cgroup v2 directory of a running container, via its init PID."""
    try:
        completed = subprocess.run(
            [docker, "inspect", "-f", "{{.State.Pid}}", container],
            capture_output=True, text=True, timeout=15, env=env,
        )
        pid = int(completed.stdout.strip())
        if completed.returncode != 0 or pid <= 0:
            return None
        cgroup = Path(f"/proc/{pid}/cgroup").read_text()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    for line in cgroup.splitlines():
        if line.startswith("0::"):
            path = Path("/sys/fs/cgroup") / line[3:].lstrip("/")
            return path if (path / "memory.current").exists() else None
    return None


def cgroup_memory(cgroup_dir: Path) -> dict | None:
    """``memory.current`` (everything, incl. page cache) and the anon part, in bytes."""
    try:
        current = int((cgroup_dir / "memory.current").read_text())
    except (OSError, ValueError):
        return None
    anon = None
    try:
        for line in (cgroup_dir / "memory.stat").read_text().splitlines():
            if line.startswith("anon "):
                anon = int(line.split()[1])
                break
    except (OSError, ValueError):
        pass
    return {"current": current, "anon": anon}


def docker_stats_memory_bytes(container: str, docker: str, env: dict) -> int | None:
    """Fallback: ``docker stats --no-stream`` usage (the part before the slash)."""
    try:
        completed = subprocess.run(
            [docker, "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
            capture_output=True, text=True, timeout=30, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return parse_size(completed.stdout.strip().split("/")[0])


_SIZE_UNITS = {"b": 1, "kb": 1e3, "kib": 1024, "mb": 1e6, "mib": 1024 ** 2,
               "gb": 1e9, "gib": 1024 ** 3, "tb": 1e12, "tib": 1024 ** 4}


def parse_size(text: str) -> int | None:
    match = re.fullmatch(r"\s*([0-9.]+)\s*([A-Za-z]*)\s*", text or "")
    if not match:
        return None
    unit = match.group(2).lower() or "b"
    if unit not in _SIZE_UNITS:
        return None
    return int(float(match.group(1)) * _SIZE_UNITS[unit])


def nvidia_smi_query(nvidia_smi: str = "nvidia-smi") -> str | None:
    try:
        completed = subprocess.run(
            [nvidia_smi, "--query-gpu=index,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def parse_nvidia_smi(text: str) -> list[dict]:
    gpus = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            gpus.append({
                "index": int(parts[0]),
                "mem_used_mb": float(parts[1]),
                "mem_total_mb": float(parts[2]),
                "util_pct": float(parts[3]) if parts[3].replace(".", "", 1).isdigit() else None,
            })
        except ValueError:
            continue
    return gpus


def fetch_text(url: str, timeout: float = 3.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception:
        return None


_METRIC_LINE = re.compile(r"^(vllm:[a-z_]+)(\{[^}]*\})?\s+([-+0-9.eE]+|NaN|nan)\s*$")


def parse_vllm_metrics(text: str) -> dict:
    """KV-cache usage (%) and request counts from a vLLM Prometheus scrape."""
    usage: list[float] = []
    running = waiting = 0.0
    seen_counts = False
    for line in text.splitlines():
        match = _METRIC_LINE.match(line)
        if not match:
            continue
        name, value = match.group(1), match.group(3)
        try:
            number = float(value)
        except ValueError:
            continue
        if number != number:  # NaN
            continue
        if name in ("vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"):
            usage.append(number)
        elif name == "vllm:num_requests_running":
            running += number
            seen_counts = True
        elif name == "vllm:num_requests_waiting":
            waiting += number
            seen_counts = True
    return {
        "kv_cache_usage_pct": round(max(usage) * 100, 2) if usage else None,
        "requests_running": running if seen_counts else None,
        "requests_waiting": waiting if seen_counts else None,
    }


def parse_info_metrics(text: str) -> dict[str, dict[str, str]]:
    """Labels of the ``vllm:*_info`` gauges (cache config, engine config) of a scrape."""
    info: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        match = _INFO_METRIC_LINE.match(line)
        if match:
            info[match.group(1)] = {key: value for key, value in _LABEL.findall(match.group(2))}
    return info


def extract_server_log_lines(path: Path, *, limit: int = SERVER_LOG_MAX_LINES) -> list[str]:
    """Startup/config lines of a vLLM log (KV cache size and memory, concurrency, flags).

    Read from the head of the log, where a launch writes them once. The
    periodic throughput/usage lines vLLM prints every few seconds match the
    same words ("GPU KV cache usage") but are excluded here, so they can never
    push the startup lines out of the cap; ``extract_server_log_periodic_lines``
    keeps the most recent few of those separately.
    """
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(SERVER_LOG_HEAD_BYTES)
    except OSError:
        return []
    lines = [
        line.rstrip() for line in head.decode("utf-8", "replace").splitlines()
        if SERVER_LOG_LINE.search(line) and not SERVER_LOG_PERIODIC.search(line)
    ]
    return lines[:limit]


def extract_server_log_periodic_lines(path: Path, *, limit: int = SERVER_LOG_PERIODIC_LINES) -> list[str]:
    """The last few periodic vLLM stats lines (throughput, KV cache usage, prefix hit rate)."""
    try:
        with Path(path).open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - SERVER_LOG_TAIL_BYTES))
            tail = handle.read()
    except OSError:
        return []
    lines = [line.rstrip() for line in tail.decode("utf-8", "replace").splitlines() if SERVER_LOG_PERIODIC.search(line)]
    return lines[-limit:]


def _pid_alive(pid_file: Path) -> bool | None:
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False if pid_file.exists() else None


def capture_serving_info(metrics_urls: list[str], servers_log_dir: Path | None) -> dict:
    """What a later KV-cache analysis needs: endpoint config plus live vLLM startup lines."""
    endpoints = {}
    for url in metrics_urls:
        scrape = fetch_text(url)
        models = fetch_text(re.sub(r"/metrics/?$", "", url) + "/v1/models")
        try:
            models = json.loads(models) if models is not None else None
        except ValueError:
            models = None
        endpoints[url] = {
            "reachable": scrape is not None,
            "models": models,
            "info_metrics": parse_info_metrics(scrape) if scrape is not None else None,
        }
    logs = []
    if servers_log_dir is not None:
        for latest in sorted(Path(servers_log_dir).glob("vllm_*.latest.log")):
            name = latest.name[: -len(".latest.log")]
            try:
                target = latest.resolve()
                mtime = datetime.fromtimestamp(target.stat().st_mtime).isoformat(timespec="seconds")
            except OSError:
                continue
            logs.append({
                "server": name,
                "log": target.name,
                "mtime": mtime,
                "server_alive": _pid_alive(latest.with_name(f"{name}.pid")),
                "lines": extract_server_log_lines(target),
                "recent_stats_lines": extract_server_log_periodic_lines(target),
            })
    return {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "endpoints": endpoints,
        "server_logs": logs,
    }


class SharedProbes:
    """Machine-wide readings cached across the monitors of one runner process."""

    def __init__(self, min_age_s: float = 2.0):
        self.min_age_s = min_age_s
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, object]] = {}

    def get(self, key: str, probe, min_age_s: float | None = None):
        max_age = self.min_age_s if min_age_s is None else min_age_s
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and time.monotonic() - entry[0] < max_age:
                return entry[1]
        value = probe()
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
        return value

    def gpus(self) -> list[dict] | None:
        def probe():
            if shutil.which("nvidia-smi") is None:
                return None
            text = nvidia_smi_query()
            return parse_nvidia_smi(text) if text is not None else None
        return self.get("gpus", probe)

    def vllm(self, url: str) -> dict | None:
        def probe():
            text = fetch_text(url)
            return parse_vllm_metrics(text) if text is not None else None
        return self.get(f"vllm:{url}", probe)

    def serving_info(self, metrics_urls: list[str], servers_log_dir: Path | None) -> dict:
        key = f"serving:{','.join(metrics_urls)}:{servers_log_dir}"
        return self.get(key, lambda: capture_serving_info(metrics_urls, servers_log_dir), SERVING_INFO_MAX_AGE_S)


SHARED = SharedProbes()


# ── Monitor ─────────────────────────────────────────────────────────────────────


class ResourceMonitor:
    def __init__(
        self,
        *,
        pid: int,
        run_dir: Path,
        agent_log: Path | None = None,
        env: dict | None = None,
        metrics_urls: list[str] | None = None,
        interval_s: float | None = None,
        probes: SharedProbes | None = None,
        servers_log_dir: Path | None = None,
    ):
        self.pid = pid
        self.run_dir = Path(run_dir)
        self.agent_log = agent_log
        self.env = dict(env) if env is not None else dict(os.environ)
        self.docker = self.env.get("MSWEA_DOCKER_EXECUTABLE", "docker")
        self.metrics_urls = list(metrics_urls or [])
        self.interval_s = interval_s if interval_s is not None else sample_interval_s(self.env)
        self.probes = probes or SHARED
        self.servers_log_dir = Path(servers_log_dir) if servers_log_dir is not None else None
        self.log_path = self.run_dir / LOG_NAME
        self.serving_info_path = self.run_dir / SERVING_INFO_NAME
        self.samples: list[dict] = []
        self.container: str | None = None
        self._cgroup_dir: Path | None = None
        self._container_gone = False
        self._docker_available = shutil.which(self.docker) is not None
        self._stop = threading.Event()
        # Guards samples + resource_log.jsonl: once stop() has closed the monitor
        # nothing is appended, so the summary and the log cover the same samples.
        self._lock = threading.Lock()
        self._closed = False
        self.stop_join_timeout_s = max(60.0, self.interval_s * 2)
        self.serving_info_join_timeout_s = 30.0
        # Captured on its own thread so slow endpoints / big logs never delay
        # the first memory sample (a short run would otherwise have no RSS at all).
        self._serving_thread = threading.Thread(
            target=self._write_serving_info, name=f"resmon-serving-{pid}", daemon=True,
        )
        self._thread = threading.Thread(target=self._loop, name=f"resmon-{pid}", daemon=True)
        self._started = time.monotonic()

    # ── lifecycle ──
    def start(self) -> "ResourceMonitor":
        self._thread.start()
        self._serving_thread.start()
        return self

    def stop(self) -> dict:
        """Stop sampling (taking a last sample) and return the summary fields.

        The thread normally finishes its last sample within the join timeout
        (every probe has a timeout of its own). If it is still inside a probe
        after that, the monitor is closed: that sample is discarded rather than
        appended to the log after the summary was taken.
        """
        self._stop.set()
        self._thread.join(timeout=self.stop_join_timeout_s)
        self._serving_thread.join(timeout=self.serving_info_join_timeout_s)
        with self._lock:
            self._closed = True
            samples = list(self.samples)
        return self.summary(samples)

    def _loop(self) -> None:
        try:
            self.log_path.unlink(missing_ok=True)
            self._sample()
            while not self._stop.wait(self.interval_s):
                self._sample()
            self._sample()
        except Exception:  # never let monitoring take the run down
            pass

    def _write_serving_info(self) -> None:
        try:
            info = self.probes.serving_info(self.metrics_urls, self.servers_log_dir)
            self.serving_info_path.write_text(json.dumps(info, indent=1))
        except Exception:
            pass

    # ── sampling ──
    def _sample(self) -> None:
        sample = {
            "t": datetime.now().isoformat(timespec="seconds"),
            "elapsed_s": round(time.monotonic() - self._started, 1),
            "agent_rss_mb": self._agent_rss_mb(),
        }
        container = self._container_memory()
        sample["container"] = self.container
        sample["container_mem_mb"] = container.get("mem_mb") if container else None
        sample["container_anon_mb"] = container.get("anon_mb") if container else None
        sample["gpus"] = self.probes.gpus()
        sample["vllm"] = {url: self.probes.vllm(url) for url in self.metrics_urls} or None
        with self._lock:
            if self._closed:
                return
            self.samples.append(sample)
            try:
                with self.log_path.open("a") as handle:
                    handle.write(json.dumps(sample) + "\n")
            except OSError:
                pass

    def _agent_rss_mb(self) -> float | None:
        rss = process_tree_rss_bytes(self.pid)
        return round(rss / _MB, 1) if rss is not None else None

    def _container_memory(self) -> dict | None:
        if self._container_gone or not self._docker_available:
            return None
        if self.container is None:
            if self.agent_log is None:
                return None
            self.container = find_container_name(self.agent_log)
            if self.container is None:
                return None
        if self._cgroup_dir is None:
            self._cgroup_dir = container_cgroup_dir(self.container, self.docker, self.env)
        if self._cgroup_dir is not None:
            memory = cgroup_memory(self._cgroup_dir)
            if memory is None:  # cgroup removed: the container has stopped
                self._container_gone = True
                return None
            return {
                "mem_mb": round(memory["current"] / _MB, 1),
                "anon_mb": round(memory["anon"] / _MB, 1) if memory["anon"] is not None else None,
            }
        usage = docker_stats_memory_bytes(self.container, self.docker, self.env)
        return {"mem_mb": round(usage / _MB, 1), "anon_mb": None} if usage is not None else None

    # ── summary ──
    def summary(self, samples: list[dict] | None = None) -> dict:
        samples = list(self.samples) if samples is None else samples

        def values(key):
            return [s[key] for s in samples if s.get(key) is not None]

        def peak(key):
            found = values(key)
            return round(max(found), 1) if found else None

        def mean(items):
            return round(sum(items) / len(items), 1) if items else None

        gpu_used = [sum(g["mem_used_mb"] for g in s["gpus"]) for s in samples if s.get("gpus")]
        gpu_util = [
            mean([g["util_pct"] for g in s["gpus"] if g["util_pct"] is not None])
            for s in samples if s.get("gpus")
        ]
        gpu_util = [u for u in gpu_util if u is not None]
        kv, running = [], []
        for sample in samples:
            for metrics in (sample.get("vllm") or {}).values():
                if not metrics:
                    continue
                if metrics.get("kv_cache_usage_pct") is not None:
                    kv.append(metrics["kv_cache_usage_pct"])
                if metrics.get("requests_running") is not None:
                    running.append(metrics["requests_running"])
        return {
            "resource_samples": len(samples),
            "resource_sample_interval_s": self.interval_s,
            "peak_agent_rss_mb": peak("agent_rss_mb"),
            "container_name": self.container,
            "peak_container_mem_mb": peak("container_mem_mb"),
            "peak_container_anon_mb": peak("container_anon_mb"),
            "peak_gpu_mem_used_mb": round(max(gpu_used), 1) if gpu_used else None,
            "mean_gpu_util_pct": mean(gpu_util),
            "peak_kv_cache_usage_pct": round(max(kv), 2) if kv else None,
            "mean_kv_cache_usage_pct": round(sum(kv) / len(kv), 2) if kv else None,
            "mean_vllm_requests_running": mean(running),
        }


def start_for_process(
    pid: int,
    run_dir: Path,
    *,
    agent_log: Path | None,
    env: dict,
    config_paths: list[str | Path],
    servers_log_dir: Path | None = None,
) -> ResourceMonitor | None:
    """Start a monitor for the agent subprocess ``pid``, or None when disabled."""
    if not enabled(env):
        return None
    monitor = ResourceMonitor(
        pid=pid, run_dir=run_dir, agent_log=agent_log, env=env,
        metrics_urls=metrics_urls(config_paths, env), servers_log_dir=servers_log_dir,
    )
    return monitor.start()
