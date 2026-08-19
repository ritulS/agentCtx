#!/usr/bin/env python3
"""Idempotently patch venv-tb's terminal_bench for rootless podman.

Adds a uid/gid-zeroing filter to DockerComposeManager._create_tar_archive so
container.put_archive doesn't lchown to unmappable host UIDs (same class of
fix as the May 2026 swebench-harness lchown patch). Venv-local: re-run this
after any `pip install`/upgrade of terminal-bench in venv-tb.

Usage: python scripts/patch_tb_lchown.py
"""

import re
import sys
from pathlib import Path

TARGET = (
    Path(__file__).resolve().parent.parent
    / "venv-tb/lib/python3.12/site-packages/terminal_bench/terminal/docker_compose_manager.py"
)

FILTER_DEF = '''    @staticmethod
    def _strip_owner(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
        # agentCtx local patch: zero uid/gid so rootless podman's copier does
        # not lchown to unmappable host UIDs (see scripts/patch_tb_lchown.py)
        tarinfo.uid = 0
        tarinfo.gid = 0
        tarinfo.uname = ""
        tarinfo.gname = ""
        return tarinfo

'''


def main() -> int:
    text = TARGET.read_text()
    if "_strip_owner" in text:
        print("already patched:", TARGET)
        return 0
    anchor = "    @staticmethod\n    def _create_tar_archive("
    if anchor not in text:
        print("ERROR: anchor not found — terminal_bench layout changed?", file=sys.stderr)
        return 1
    text = text.replace(anchor, FILTER_DEF + anchor, 1)
    text, n = re.subn(
        r"tar\.add\(((?:item|path), arcname=[^)]+)\)",
        r"tar.add(\1, filter=DockerComposeManager._strip_owner)",
        text,
    )
    if n == 0:
        print("ERROR: no tar.add call sites found", file=sys.stderr)
        return 1
    TARGET.write_text(text)
    print(f"patched {n} tar.add call sites in {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
