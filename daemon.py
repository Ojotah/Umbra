"""
Umbra daemon (background runner).

V1 daemon responsibilities:
- load persisted tasks from JSON
- execute scheduled reminders when due
- mark tasks completed/failed

This is intentionally simple and uses polling + sleep. It can later be replaced
with a more robust mechanism (systemd timers, APScheduler, etc.).
"""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Optional

from config.settings import SETTINGS
from services.notifier import notify
from storage.task_store import Task, add_task, get_pending_tasks, remove_task


@dataclass
class DaemonConfig:
    """Configuration for the daemon loop."""

    poll_interval_seconds: float = 1.0


class UmbraDaemon:
    """Runs a polling loop and executes due tasks."""

    def __init__(self, *, store: Optional[JsonTaskStore] = None, config: Optional[DaemonConfig] = None) -> None:
        self._config = config or DaemonConfig()
        self._stop = False

    def run_forever(self) -> None:
        """Start the daemon loop (blocking)."""
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

        while not self._stop:
            now = time.time()
            for task in get_pending_tasks(SETTINGS.tasks_file):
                if float(task["run_at"]) <= now:
                    self._claim_and_execute(task)
            time.sleep(self._config.poll_interval_seconds)

    def _claim_and_execute(self, task: Task) -> None:
        """
        Prevent duplicate execution by claiming the task (removing it) first.

        If execution fails, we re-add the task with the same id and timestamps,
        but a short delay, so it can be retried.
        """
        task_id = str(task["id"])
        claimed = remove_task(SETTINGS.tasks_file, task_id)
        if claimed is None:
            return  # already claimed by another daemon instance

        try:
            self._execute(claimed)
        except Exception as e:  # noqa: BLE001 - boundary layer; persist error
            # Re-add for retry; keep schema stable.
            retry = dict(claimed)
            retry["run_at"] = time.time() + 5.0
            add_task(SETTINGS.tasks_file, retry)

    def _execute(self, task: Task) -> None:
        task_type = str(task["type"])
        if task_type == "remind":
            message = str(task.get("message", "")).strip()
            notify("Umbra Reminder", message or "Reminder")
            return

        raise RuntimeError(f"Unsupported task type: {task_type}")

    def _handle_stop_signal(self, *_: object) -> None:
        self._stop = True


def main() -> None:
    """CLI entry point for running the daemon directly."""
    UmbraDaemon().run_forever()


if __name__ == "__main__":
    main()

