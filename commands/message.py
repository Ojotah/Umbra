"""
Message command (future).

Planned V1+ capability:
- send WhatsApp messages (via Selenium) from natural CLI commands.

This module is intentionally a stub in V1. We keep the file so the architecture
stays stable and extension points are obvious.
"""

from __future__ import annotations

NAME = "message"
DESCRIPTION = "Send a message (coming soon)."
EXAMPLES = [
    'umbra "message mom hello from umbra"',
]


def send_message(*_: object, **__: object) -> None:
    """Placeholder for future message sending functionality."""
    raise NotImplementedError("Message command is not implemented in V1.")

