#!/usr/bin/env python3
"""Run ``swebench.harness.run_evaluation`` with thread caps inside evaluation containers.

Usage: python scripts/swebench_eval_wrapper.py <run_evaluation arguments...>

The harness creates instance containers without any environment, so OpenMP /
BLAS libraries spawn one thread per host core (128 here). Small-data test
suites such as scikit-learn__scikit-learn-14710 then spend their time in
thread synchronisation and never finish within the harness timeout. This
wrapper patches the Docker SDK's ``ContainerCollection.create`` to add
``OMP_NUM_THREADS`` and friends (``SWEBENCH_EVAL_THREADS``, default 8) and
then runs the harness entry point unchanged; ``exec_run`` inherits the
container environment, so the cap applies to the test command too.
"""
from __future__ import annotations

import os
import runpy
import sys

from docker.models.containers import ContainerCollection

THREADS = os.environ.get("SWEBENCH_EVAL_THREADS", "8")
THREAD_ENV = {
    "OMP_NUM_THREADS": THREADS,
    "OPENBLAS_NUM_THREADS": THREADS,
    "MKL_NUM_THREADS": THREADS,
    "NUMEXPR_NUM_THREADS": THREADS,
}


def with_thread_caps(environment):
    """Merge THREAD_ENV into a docker ``environment`` value (dict, list, or None)."""
    if isinstance(environment, list):
        present = {item.split("=", 1)[0] for item in environment}
        return environment + [f"{k}={v}" for k, v in THREAD_ENV.items() if k not in present]
    merged = dict(THREAD_ENV)
    merged.update(environment or {})
    return merged


_original_create = ContainerCollection.create


def _create(self, image, command=None, **kwargs):
    kwargs["environment"] = with_thread_caps(kwargs.get("environment"))
    return _original_create(self, image, command, **kwargs)


def install() -> None:
    ContainerCollection.create = _create


if __name__ == "__main__":
    if not THREADS.isdigit() or int(THREADS) < 1:
        raise SystemExit(f"SWEBENCH_EVAL_THREADS must be a positive integer, got {THREADS!r}")
    install()
    sys.argv = ["swebench.harness.run_evaluation", *sys.argv[1:]]
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__", alter_sys=True)
