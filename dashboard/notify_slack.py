#!/usr/bin/env python3
"""Post experiment lifecycle notifications to a Slack incoming webhook.

Usage:
    notify_slack.py start <unit>
    notify_slack.py stop  <unit> <result> <exit-status> <log-path>
    notify_slack.py test  [<unit>]

``scripts/notify_run.sh`` is the normal caller; ``result`` is one of
``success`` / ``failed`` / ``killed`` and the notice is a ✅ only when the
result is ``success`` and the exit status is ``0``.

The webhook is intentionally read only from SLACK_WEBHOOK_URL, never a file.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request
from datetime import datetime


def post_to_slack(text: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("SLACK_WEBHOOK_URL is not configured")

    payload = json.dumps({"text": text}).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8", errors="replace")
                if response.status != 200:
                    raise RuntimeError(f"Slack returned HTTP {response.status}: {body}")
                return
        except Exception as exc:  # pragma: no cover - depends on network
            last_error = exc
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError(f"Slack notification failed: {last_error}")


def format_message(argv: list[str]) -> str:
    event = argv[0] if argv else "test"
    expected = {"start": 2, "stop": 5}.get(event)
    if expected is not None and len(argv) != expected:
        raise ValueError(
            f"'{event}' takes {expected - 1} argument(s), got {len(argv) - 1}: {argv[1:]} "
            "(usage: start <unit> | stop <unit> <result> <exit-status> <log-path>)"
        )
    unit = argv[1] if len(argv) > 1 else "manual-test"
    result = argv[2] if len(argv) > 2 else ""
    exit_status = argv[3] if len(argv) > 3 else ""
    log_path = argv[4] if len(argv) > 4 else ""
    host = socket.gethostname()
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    if event == "start":
        text = (
            "🧪 *ICLR27 experiment started*\n"
            f"• host: `{host}`\n• unit: `{unit}`\n• time: `{now}`"
        )
    elif event == "stop":
        successful = result == "success" and exit_status == "0"
        headline = "✅ *ICLR27 experiment completed*" if successful else "🚨 *ICLR27 experiment terminated*"
        text = (
            f"{headline}\n• host: `{host}`\n• unit: `{unit}`\n"
            f"• result: `{result or 'unknown'}`\n"
            f"• exit status: `{exit_status or 'unknown'}`\n"
            f"• log: `{log_path or 'unknown'}`\n• time: `{now}`"
        )
    else:
        text = f"🔔 *ICLR27 Experiment Notifier test*\n• host: `{host}`\n• time: `{now}`"
    return text


def main() -> int:
    post_to_slack(format_message(sys.argv[1:]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"notify_slack.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
