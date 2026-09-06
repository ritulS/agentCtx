"""Benchmark adapters used by the experiment runner.

To add a benchmark, implement the same small interface as ``SweBench`` and
register it in ``BENCHMARKS`` below.  The experiment runner itself should not
need benchmark-specific branches.
"""

from .swe_bench import SweBench
from .terminal_bench import TerminalBench


BENCHMARKS = {
    "swe-bench": SweBench,
    "terminal-bench": TerminalBench,
}


def create_benchmark(name: str, **kwargs):
    """Create a configured benchmark adapter by its command-line name."""
    try:
        benchmark_class = BENCHMARKS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(BENCHMARKS))
        raise ValueError(f"Unknown benchmark {name!r}. Available: {choices}") from exc
    return benchmark_class(**kwargs)
