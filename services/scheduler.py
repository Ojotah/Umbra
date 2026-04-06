"""
Scheduling service.

V1 provides a simple, replaceable scheduler that runs callbacks after a delay.
This module deliberately avoids heavy dependencies and can later be swapped for:
- APScheduler
- systemd timers
- cron integration
- a persistent job queue
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable


Callback = Callable[..., None]


@dataclass(frozen=True)
class ScheduledJob:
    """A scheduled unit of work."""

    id: str
    run_at_epoch_seconds: float


class Scheduler:
    """Scheduler interface."""

    def schedule(self, delay_seconds: float, callback: Callback, *args: Any, **kwargs: Any) -> ScheduledJob:
        """
        Schedule a callback to run after `delay_seconds`.

        `*args`/`**kwargs` are passed to the callback when it runs.
        """
        raise NotImplementedError


class SleepScheduler(Scheduler):
    """
    A minimal scheduler implemented using threads + time.sleep.

    Each job runs in its own daemon thread. This is simple and good enough for V1.
    """

    def schedule(self, delay_seconds: float, callback: Callback, *args: Any, **kwargs: Any) -> ScheduledJob:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")

        job_id = str(uuid.uuid4())
        run_at = time.time() + delay_seconds

        def runner() -> None:
            time.sleep(delay_seconds)
            callback(*args, **kwargs)

        t = threading.Thread(target=runner, name=f"umbra-job-{job_id}", daemon=True)
        t.start()

        return ScheduledJob(id=job_id, run_at_epoch_seconds=run_at)

