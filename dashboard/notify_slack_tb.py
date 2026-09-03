#!/usr/bin/env python3
"""Post experiment lifecycle notifications to a Slack incoming webhook.

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


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "test"
    unit = sys.argv[2] if len(sys.argv) > 2 else "manual-test"
    result = sys.argv[3] if len(sys.argv) > 3 else ""
    exit_status = sys.argv[4] if len(sys.argv) > 4 else ""
    log_path = sys.argv[5] if len(sys.argv) > 5 else ""
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

    post_to_slack(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"notify_slack.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
