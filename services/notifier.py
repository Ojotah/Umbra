"""
Notification service.

V1 uses Linux desktop notifications via `notify-send`. This is intentionally
isolated behind a small API so it can be replaced later (e.g., logging,
push notifications, custom UI).
"""

from __future__ import annotations

import shutil
import subprocess


class NotificationError(RuntimeError):
    """Raised when a notification cannot be delivered."""


def notify(title: str, message: str) -> None:
    """
    Send a desktop notification using `notify-send`.

    Raises:
        NotificationError: if notify-send is unavailable or fails.
    """
    if shutil.which("notify-send") is None:
        raise NotificationError(
            "notify-send not found. On Ubuntu, install it with: sudo apt install libnotify-bin"
        )

    # Keep `notify-send` usage minimal and robust.
    result = subprocess.run(
        ["notify-send", title, message],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise NotificationError(f"notify-send failed (exit {result.returncode}): {stderr}")

