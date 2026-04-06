"""
CLI task command handlers.

These handlers implement CLI-facing task operations while leaving formatting to
`services.formatter` and storage correctness to `storage.task_store`.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from commands.remind import ReminderRequest, build_reminder_task
from core.workflows.workflow_loader import load_workflows
from storage.task_store import StorageError, Task, add_task, load_tasks

_DURATION_RE = re.compile(r"^\s*(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s*$", re.I)


def parse_duration_to_seconds(token: str) -> int:
    """Parse duration tokens like `10s`, `2m`, `1 hour`."""
    m = _DURATION_RE.match(token)
    if not m:
        raise ValueError("Invalid duration. Example: 10s, 5m, 1h")

    amount = int(m.group(1))
    unit = m.group(2).lower()
    if unit in {"s", "sec", "secs", "second", "seconds"}:
        return amount
    if unit in {"m", "min", "mins", "minute", "minutes"}:
        return amount * 60
    if unit in {"h", "hr", "hrs", "hour", "hours"}:
        return amount * 3600
    raise ValueError("Unsupported duration unit")


def schedule_task(task_file: Path, *, message: str, delay_seconds: int) -> Task:
    """Build and persist a reminder task."""
    task = build_reminder_task(ReminderRequest(delay_seconds=delay_seconds, message=message))
    add_task(task_file, task)
    return task


def schedule_workflow_task(task_file: Path, *, workflow_name: str) -> Task:
    """Persist an immediate workflow task for daemon execution."""
    now = time.time()
    task: Task = {
        "id": str(uuid.uuid4()),
        "type": "workflow",
        "action": workflow_name,
        "message": f"workflow:{workflow_name}",
        "run_at": now,
        "created_at": now,
        "status": "pending",
    }
    add_task(task_file, task)
    return task


def list_workflow_names(workflows_file: Path) -> list[str]:
    """Return sorted workflow names from merged defaults + file workflows."""
    workflows = load_workflows(workflows_file)
    return sorted(workflows.keys())


def list_tasks(task_file: Path) -> list[Task]:
    """Load tasks sorted by run time ascending."""
    tasks = load_tasks(task_file)
    return sorted(tasks, key=lambda t: float(t.get("run_at", 0.0)))


def status_counts(task_file: Path) -> list[Task]:
    """Load all tasks for status summarization."""
    return load_tasks(task_file)


def read_logs(log_file: Path, *, limit: int = 50) -> list[str]:
    """Read latest log lines (newest first)."""
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise StorageError(f"Failed reading log file: {e}") from e
    return list(reversed(lines[-limit:]))

