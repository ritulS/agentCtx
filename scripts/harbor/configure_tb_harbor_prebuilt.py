#!/usr/bin/env python3
"""Point a migrated Harbor task at images prebuilt by rootless Podman."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def qualify_image(image: str) -> str:
    """Make Docker Hub explicit when no short-name registry is configured."""
    if "/" not in image:
        return f"docker.io/{image}"
    first = image.split("/", 1)[0]
    if first == "localhost" or "." in first or ":" in first:
        return image
    return f"docker.io/{image}"


def set_task_image(config_path: Path, image: str) -> None:
    text = config_path.read_text()
    line = f'docker_image = "{image}"'
    lines = text.splitlines()
    in_environment = False
    replaced = False
    output: list[str] = []
    for current in lines:
        if current.startswith("["):
            in_environment = current == "[environment]"
        if in_environment and current.startswith("docker_image ="):
            output.append(line)
            replaced = True
        else:
            output.append(current)
    if not replaced:
        index = output.index("[environment]") + 1
        output.insert(index, line)
    config_path.write_text("\n".join(output) + "\n")


def set_compose_images(compose_path: Path, images: dict[str, str]) -> None:
    if not compose_path.exists():
        return
    payload = yaml.safe_load(compose_path.read_text()) or {}
    services = payload.get("services", {})
    for service in services.values():
        image = service.get("image")
        if image:
            service["image"] = qualify_image(image)
    for service, image in images.items():
        if service not in services:
            raise SystemExit(f"compose service not found: {service} ({compose_path})")
        services[service].pop("build", None)
        services[service]["image"] = image
    compose_path.write_text(yaml.safe_dump(payload, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--main-image", required=True)
    parser.add_argument(
        "--service-image",
        action="append",
        default=[],
        metavar="SERVICE=IMAGE",
    )
    args = parser.parse_args()

    task_dir = args.task_dir.resolve()
    images = {"main": args.main_image}
    for item in args.service_image:
        service, separator, image = item.partition("=")
        if not separator or not service or not image:
            raise SystemExit(f"invalid --service-image value: {item}")
        images[service] = image

    set_task_image(task_dir / "task.toml", args.main_image)
    set_compose_images(task_dir / "environment" / "docker-compose.yaml", images)


if __name__ == "__main__":
    main()
