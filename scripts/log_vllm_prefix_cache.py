#!/usr/bin/env python3
"""Record timestamped vLLM prefix-cache Prometheus samples without inference."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


class PrefixCacheRecorder:
    def __init__(self, url: str, output: Path, interval: float = 10.0):
        if interval <= 0:
            raise ValueError("metrics interval must be positive")
        self.url = url
        self.output = output.resolve()
        protected = (Path(__file__).resolve().parent.parent / "ICLR_results").resolve()
        if self.output.is_relative_to(protected):
            raise ValueError("metrics output must be outside ICLR_results")
        self.interval = interval
        self.session_id = str(uuid.uuid4())
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def snapshot(self, phase: str, *, required: bool = False) -> None:
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "phase": phase,
            "url": self.url,
            "scope": "server-wide; includes other clients; counters reset on server restart",
            "error": None,
            "prometheus_lines": None,
        }
        try:
            with urlopen(self.url, timeout=5) as response:
                lines = response.read().decode().splitlines()
            record["prometheus_lines"] = [
                line for line in lines
                if any(key in line for key in (
                    "prefix_cache", "cache_config", "process_start_time_seconds",
                ))
            ]
            # Keep HELP/TYPE, model/engine labels and original values intact.
            # Missing counters and failed scrapes must never appear as zero hits.
            samples = [line for line in lines if not line.startswith("#")]
            if not all(any(f"prefix_cache_{kind}" in line for line in samples)
                       for kind in ("hits", "queries")):
                raise ValueError("/metrics did not expose prefix-cache hits and queries")
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        if record["error"]:
            print(f"[metrics] {record['error']}", file=sys.stderr, flush=True)
            if required:
                raise RuntimeError(f"prefix-cache recording unavailable: {record['error']}")

    def _poll(self) -> None:
        while not self.stop.wait(self.interval):
            self.snapshot("periodic")

    def __enter__(self):
        self.snapshot("start", required=True)
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop.set()
        if self.thread:
            self.thread.join()
        self.snapshot("end" if exc_type is None else "interrupted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="e.g. http://localhost:8003/metrics")
    parser.add_argument("--output", required=True, type=Path, help="append-only JSONL outside ICLR_results")
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    recorder = PrefixCacheRecorder(args.url, args.output, args.interval)
    if args.once:
        recorder.snapshot("once", required=True)
        return
    signal.signal(signal.SIGTERM, lambda *_: recorder.stop.set())
    signal.signal(signal.SIGINT, lambda *_: recorder.stop.set())
    with recorder:
        recorder.stop.wait()


if __name__ == "__main__":
    main()
