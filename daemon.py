"""
Umbra daemon (background runner).

V2 daemon responsibilities:
- load persisted tasks from SQLite
- schedule tasks with APScheduler
- execute scheduled reminders when due
- mark tasks completed/failed

Uses APScheduler 3.x with SQLAlchemyJobStore for persistent scheduling.
"""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Try to import APScheduler, fall back to polling if not available
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    SQLAlchemyJobStore = None
    ThreadPoolExecutor = None

from config.settings import SETTINGS
from services.logger import Logger
from storage.task_store import StorageError, get_pending_tasks, update_task_status
from umbra.api import api


# PID file path
PID_PATH = Path.home() / ".local" / "share" / "umbra" / "daemon.pid"

# Database URL for APScheduler
DB_URL = f"sqlite:///{Path.home() / '.local' / 'share' / 'umbra' / 'umbra.db'}"


@dataclass
class DaemonConfig:
    """Configuration for the daemon."""

    max_workers: int = 4


class UmbraDaemon:
    """Runs APScheduler and executes tasks when scheduled."""

    def __init__(self, *, config: DaemonConfig | None = None, logger: Logger | None = None) -> None:
        self._config = config or DaemonConfig()
        self._log = logger or Logger(SETTINGS.log_file, level="INFO")
        self._stop = False
        self._scheduler: BackgroundScheduler | None = None

    def run_forever(self) -> None:
        """Start the daemon with APScheduler or fallback polling (blocking)."""
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

        # Write PID file
        PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()))

        try:
            self._log.info("Umbra daemon started")

            if APSCHEDULER_AVAILABLE:
                self._run_with_scheduler()
            else:
                self._log.info("APScheduler not available, falling back to polling")
                self._run_with_polling()

        except Exception as e:
            self._log.error(f"Daemon error: {e}")
        finally:
            self._shutdown()

    def _run_with_scheduler(self) -> None:
        """Run daemon with APScheduler."""
        # Setup APScheduler
        jobstores = {
            'default': SQLAlchemyJobStore(url=DB_URL)
        }
        executors = {
            'default': ThreadPoolExecutor(max_workers=self._config.max_workers)
        }
        
        self._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone='UTC'
        )

        # Schedule existing pending tasks
        self._schedule_existing_tasks()

        # Start scheduler
        self._scheduler.start()
        self._log.info("APScheduler started")

        # Wait for stop signal
        while not self._stop:
            time.sleep(1)

    def _run_with_polling(self) -> None:
        """Run daemon with simple polling loop (fallback)."""
        self._log.info("Starting polling loop")
        
        while not self._stop:
            cycle_started = time.time()
            try:
                tasks = get_pending_tasks(SETTINGS.tasks_file)
                now = time.time()
                
                for task in tasks:
                    run_at = float(task.get("run_at", 0))
                    if run_at <= now:
                        task_id = str(task.get("id", ""))
                        try:
                            api.execute_task(task_id)
                        except Exception as e:
                            self._log.error(f"Task failed {task_id}: {e}")
                
            except StorageError as e:
                self._log.error(f"Storage error: {e}")
            except Exception as e:
                self._log.error(f"Unexpected daemon error: {e}")

            # Poll every second
            sleep_for = max(0.0, 1.0 - (time.time() - cycle_started))
            time.sleep(sleep_for)

    def _schedule_existing_tasks(self) -> None:
        """Schedule all pending tasks from database."""
        try:
            tasks = get_pending_tasks(SETTINGS.tasks_file)
            self._log.info(f"Scheduling {len(tasks)} pending tasks")
            
            for task in tasks:
                task_id = str(task.get("id"))
                run_at = float(task.get("run_at", 0))
                
                # Check if already scheduled
                if self._scheduler and self._scheduler.get_job(task_id):
                    continue
                
                # Schedule the task
                if self._scheduler:
                    self._scheduler.add_job(
                        func=self._execute_task_safely,
                        trigger='date',
                        run_date=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(run_at)),
                        args=[task],
                        id=task_id,
                        misfire_grace_time=60,
                        replace_existing=True
                    )
                    self._log.debug(f"Scheduled task {task_id} for {run_at}")

        except StorageError as e:
            self._log.error(f"Failed to load pending tasks: {e}")

    def _execute_task_safely(self, task: dict[str, Any]) -> None:
        """Execute a task with error handling."""
        task_id = str(task.get("id", ""))
        try:
            # Call API execute_task method
            api.execute_task(task_id)
        except Exception as e:  # noqa: BLE001 - per-task safety
            self._log.error(f"Task failed {task_id}: {e}")

    def _handle_stop_signal(self, *_: object) -> None:
        """Handle shutdown signals."""
        self._stop = True

    def _shutdown(self) -> None:
        """Clean shutdown of scheduler and PID file."""
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=True)
                self._log.info("APScheduler shutdown")
            except Exception as e:
                self._log.error(f"Error shutting down scheduler: {e}")

        # Remove PID file
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass

        self._log.info("Umbra daemon stopped")


def main() -> None:
    """CLI entry point for running the daemon directly."""
    import os
    UmbraDaemon().run_forever()


if __name__ == "__main__":
    main()

