"""
Reminder command implementation.

In daemon-based mode, the CLI should not execute reminders. This module provides
helpers for building a standardized reminder task dictionary that the CLI can
persist and the daemon can execute.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from storage.task_store import Task

NAME = "remind"
DESCRIPTION = "Schedule a reminder (time-based)."
EXAMPLES = [
    'umbra "remind me in 10 seconds stretch"',
    'umbra "remind me in 10 minutes to drink water"',
]


@dataclass(frozen=True)
class ReminderRequest:
    """Normalized reminder request."""

    delay_seconds: int
    message: str


def build_reminder_task(req: ReminderRequest) -> Task:
    """
    Build a standardized reminder task dictionary.

    The CLI is expected to persist this task and exit; the daemon executes it.
    """
    if req.delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")
    if not req.message.strip():
        raise ValueError("message cannot be empty")

    now = time.time()
    return {
        "id": str(uuid.uuid4()),
        "type": "remind",
        "message": req.message.strip(),
        "run_at": now + float(req.delay_seconds),
        "created_at": now,
        "status": "pending",
    }

