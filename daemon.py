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
from pathlib import Path
from typing import Iterable

from config.settings import SETTINGS
from services.dispatcher import dispatch_task
from services.logger import Logger
from storage.task_store import Task, StorageError, get_pending_tasks, prune_done_tasks, update_task_status


@dataclass
class DaemonConfig:
    """Configuration for the daemon loop."""

    poll_interval_seconds: float = SETTINGS.poll_interval_seconds


class UmbraDaemon:
    """Runs a polling loop and executes due tasks."""

    def __init__(self, *, config: DaemonConfig | None = None, logger: Logger | None = None) -> None:
        self._config = config or DaemonConfig()
        self._log = logger or Logger(SETTINGS.log_file, level="INFO")
        self._stop = False

    def run_forever(self) -> None:
        """Start the daemon loop (blocking)."""
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

        self._log.info("Umbra daemon started")

        while not self._stop:
            cycle_started = time.time()
            try:
                tasks = get_pending_tasks(SETTINGS.tasks_file)
                due = list(get_due_tasks(tasks, now=time.time()))
                if due:
                    self._log.debug(f"Due tasks: {len(due)}")
                for task in due:
                    self._execute_task_safely(task)

                removed = prune_done_tasks(SETTINGS.tasks_file)
                if removed:
                    self._log.debug(f"Pruned done tasks: {removed}")
            except StorageError as e:
                self._log.error(f"Storage error: {e}")
            except Exception as e:  # noqa: BLE001 - daemon must not crash
                self._log.error(f"Unexpected daemon error: {e}")

            sleep_for = max(0.0, self._config.poll_interval_seconds - (time.time() - cycle_started))
            time.sleep(sleep_for)

    def _execute_task_safely(self, task: Task) -> None:
        task_id = str(task.get("id", ""))
        try:
            # Mark as running first to prevent duplicates on restart.
            if not update_task_status(SETTINGS.tasks_file, task_id, "running"):
                return
            self._log.info(f"Executing task {task_id} ({task.get('type')})")

            execute_task(task, SETTINGS.tasks_file)

            update_task_status(SETTINGS.tasks_file, task_id, "done")
            self._log.info(f"Task done {task_id}")
        except Exception as e:  # noqa: BLE001 - per-task safety
            try:
                update_task_status(SETTINGS.tasks_file, task_id, "failed", error=str(e))
            except Exception:
                pass
            self._log.error(f"Task failed {task_id}: {e}")

    def _handle_stop_signal(self, *_: object) -> None:
        self._stop = True


def get_due_tasks(tasks: Iterable[Task], *, now: float) -> Iterable[Task]:
    """
    Return tasks that are due and pending.

    Tasks with status running/done/failed are not returned.
    """
    for t in tasks:
        try:
            if str(t.get("status")) != "pending":
                continue
            if float(t.get("run_at", 0)) <= now:
                yield t
        except Exception:
            continue


def execute_task(task: Task, task_file: Path) -> None:
    """Execute a single task (may raise)."""
    result = dispatch_task(task, task_file)
    if not bool(result.get("success")):
        raise RuntimeError(str(result.get("error", "Task dispatch failed")))


def main() -> None:
    """CLI entry point for running the daemon directly."""
    UmbraDaemon().run_forever()


if __name__ == "__main__":
    main()

