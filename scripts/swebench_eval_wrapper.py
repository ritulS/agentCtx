#!/usr/bin/env python3
"""Run ``swebench.harness.run_evaluation`` with two local fixes for our serving setup.

Usage: python scripts/swebench_eval_wrapper.py <run_evaluation arguments...>

1. Thread caps inside evaluation containers. The harness creates instance
   containers without any environment, so OpenMP / BLAS libraries spawn one
   thread per host core (128 here). Small-data test suites such as
   scikit-learn__scikit-learn-14710 then spend their time in thread
   synchronisation and never finish within the harness timeout. This wrapper
   patches the Docker SDK's ``ContainerCollection.create`` to add
   ``OMP_NUM_THREADS`` and friends (``SWEBENCH_EVAL_THREADS``, default 8);
   ``exec_run`` inherits the container environment, so the cap applies to the
   test command too.

2. Rootless podman file copies. ``copy_to_container`` tars the patch / eval
   script with ``tarfile.add``, which records the host uid/gid of the file
   (here an AD uid such as 1741623211). Rootless podman with a single-UID user
   namespace (no subuid range) cannot ``lchown`` to that uid inside the
   container and ``put_archive`` fails with ``lchown ...: invalid argument``,
   so every instance ends under ``error_ids`` without a verdict. The wrapper
   replaces ``swebench.harness.docker_utils.copy_to_container`` with the same
   function plus a tar filter that zeroes uid/gid (container root), which is
   what the venv-local harness patch did before 2026-09-27; keeping it here
   survives venv rebuilds. Harmless under Docker.

Then it runs the harness entry point unchanged.
"""
from __future__ import annotations

import os
import runpy
import sys
import tarfile
from pathlib import PurePosixPath

from docker.models.containers import Container, ContainerCollection
from swebench.harness import docker_utils

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


def _reset_owner(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    return tarinfo


def copy_to_container(container: Container, src, dst) -> None:
    """``swebench.harness.docker_utils.copy_to_container`` (4.1.0) with owner-less tar entries."""
    dst = PurePosixPath(dst)
    if os.path.dirname(dst) == "":
        raise ValueError(f"Destination path parent directory cannot be empty!, dst: {dst}")
    tar_path = src.with_suffix(".tar")
    with tarfile.open(tar_path, "w") as tar:
        tar.add(src, arcname=dst.name, filter=_reset_owner)
    with open(tar_path, "rb") as tar_file:
        data = tar_file.read()
    container.exec_run(f"mkdir -p {dst.parent}")
    container.put_archive(os.path.dirname(dst), data)
    tar_path.unlink()


def install() -> None:
    ContainerCollection.create = _create
    # run_evaluation / docker_build bind the name at import time; they are
    # imported by runpy below, after this patch, so they pick up the replacement.
    docker_utils.copy_to_container = copy_to_container
    for name in ("swebench.harness.run_evaluation", "swebench.harness.docker_build"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "copy_to_container"):
            module.copy_to_container = copy_to_container


if __name__ == "__main__":
    if not THREADS.isdigit() or int(THREADS) < 1:
        raise SystemExit(f"SWEBENCH_EVAL_THREADS must be a positive integer, got {THREADS!r}")
    install()
    sys.argv = ["swebench.harness.run_evaluation", *sys.argv[1:]]
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__", alter_sys=True)
