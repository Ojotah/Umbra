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
from core.chains.chain_engine import parse_chain
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


def schedule_chain_task(task_file: Path, *, command: str) -> Task:
    """Persist an immediate chain task for daemon execution."""
    now = time.time()
    
    # Parse the chain to get steps
    actions = parse_chain(command)
    steps = [
        {
            "action": action,
            "status": "pending",
            "error": None,
        }
        for action in actions
    ]
    
    task: Task = {
        "id": str(uuid.uuid4()),
        "type": "chain",
        "action": command,
        "message": f"chain:{command}",
        "run_at": now + 1.0,  # Add 1 second delay to avoid race condition
        "created_at": now,
        "status": "pending",
        "steps": steps,
    }
    add_task(task_file, task)
    return task


def list_tasks(task_file: Path) -> list[Task]:
    """Load tasks sorted by run time ascending."""
    tasks = load_tasks(task_file)
    return sorted(tasks, key=lambda t: float(t.get("run_at", 0.0)))


def status_counts(task_file: Path) -> list[Task]:
    """Load all tasks for status summarization."""
    return load_tasks(task_file)


def get_task_by_id(task_file: Path, *, task_id: str) -> Task | None:
    """Load a specific task by its ID."""
    tasks = load_tasks(task_file)
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def dry_run_chain(command: str) -> None:
    """Parse and display chain execution plan without executing."""
    actions = parse_chain(command)
    if not actions:
        print("No valid actions found in command.")
        return
    
    print("Plan:")
    for i, action in enumerate(actions, 1):
        print(f"{i}. {action}")
    return


def retry_task(task_file: Path, *, task_id: str) -> Task:
    """Clone a task for retry with new ID and reset status."""
    tasks = load_tasks(task_file)
    original_task = None
    
    for task in tasks:
        if task.get("id") == task_id:
            original_task = task
            break
    
    if not original_task:
        raise ValueError(f"Task not found: {task_id}")
    
    now = time.time()
    
    # Create a new task with reset status
    retry_task = {
        "id": str(uuid.uuid4()),
        "type": original_task.get("type"),
        "action": original_task.get("action", ""),
        "message": original_task.get("message", ""),
        "run_at": now + 1.0,  # Schedule immediately
        "created_at": now,
        "status": "pending",
    }
    
    # Handle chain tasks with steps
    if original_task.get("type") == "chain" and "steps" in original_task:
        steps = []
        for step in original_task.get("steps", []):
            steps.append({
                "action": step.get("action", ""),
                "status": "pending",  # Reset all steps to pending
                "error": None,
            })
        retry_task["steps"] = steps
    
    add_task(task_file, retry_task)
    return retry_task


def read_logs(log_file: Path, *, limit: int = 50) -> list[str]:
    """Read latest log lines (newest first)."""
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise StorageError(f"Failed reading log file: {e}") from e
    return list(reversed(lines[-limit:]))

