"""Verify all swebench task images are cached locally in podman.

Reads a task-list JSON file (list of {instance_id, repo}), computes the
swebench image tag for each, and runs `podman image exists` on each.
Prints any missing images. Exit code 0 if all cached, 1 if any missing.
"""
import json, subprocess, sys
from pathlib import Path

PODMAN = Path.home() / ".local/bin/podman"
if not PODMAN.exists():
    PODMAN = "podman"  # fall back to PATH

def task_to_image(instance_id):
    # owner__repo-id  →  docker.io/swebench/sweb.eval.x86_64.<owner>_1776_<repo-id>:latest
    owner, _, rest = instance_id.partition("__")
    return f"docker.io/swebench/sweb.eval.x86_64.{owner}_1776_{rest}:latest"

def main():
    if len(sys.argv) != 2:
        print("usage: check_image_cache.py <task-list.json>", file=sys.stderr)
        sys.exit(2)
    tasks = json.loads(Path(sys.argv[1]).read_text())
    missing = []
    for t in tasks:
        iid = t["instance_id"] if isinstance(t, dict) else t
        img = task_to_image(iid)
        r = subprocess.run([str(PODMAN), "image", "exists", img], capture_output=True)
        if r.returncode != 0:
            missing.append((iid, img))

    print(f"Total tasks: {len(tasks)}")
    print(f"Cached: {len(tasks) - len(missing)}")
    print(f"Missing: {len(missing)}")
    if missing:
        print("\nMissing images:")
        for iid, img in missing:
            print(f"  {iid}  →  {img}")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
