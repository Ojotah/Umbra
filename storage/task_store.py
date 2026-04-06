"""
Task persistence layer (JSON).

Umbra persists scheduled work to a JSON file so the daemon can restore tasks
across restarts.

This module intentionally provides a small, explicit API:
- `load_tasks()` / `save_tasks()` for raw operations
- convenience helpers (`add_task`, `get_pending_tasks`, `remove_task`)

Task format (standardized):
{
  "id": "uuid",
  "type": "remind",
  "message": "test",
  "run_at": 1712345678.0,
  "created_at": 1712345600.0
}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import fcntl


class StorageError(RuntimeError):
    """Raised when tasks cannot be loaded/saved."""


Task = Dict[str, Any]

TaskStatus = str  # "pending" | "running" | "done" | "failed"


def load_tasks(path: Path) -> List[Task]:
    """
    Load tasks from disk.

    Returns an empty list if the file does not exist or is empty.
    """
    try:
        if not path.exists():
            return []

        with _lock(path, exclusive=False):
            raw = _read_tasks_file(path)
        if not raw.strip():
            return []

        data = json.loads(raw)
        if isinstance(data, dict) and "tasks" in data:
            tasks = data["tasks"]
        else:
            # Backward-compatible: allow older files that were just a list.
            tasks = data

        if not isinstance(tasks, list):
            raise StorageError("tasks.json must contain a list (or an object with a 'tasks' list)")

        normalized: List[Task] = []
        for obj in tasks:
            if not isinstance(obj, dict):
                continue

            migrated = _maybe_migrate_legacy_task(obj)
            if migrated is None:
                continue

            _validate_task(migrated)
            normalized.append(migrated)
        return normalized
    except json.JSONDecodeError as e:
        raise StorageError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise StorageError(f"Failed reading {path}: {e}") from e


def save_tasks(path: Path, tasks: List[Task]) -> None:
    """Persist tasks to disk using an atomic write."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload = {"tasks": tasks}
        # Lock to avoid races with readers/writers.
        with _lock(path, exclusive=True):
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp_path, path)  # atomic on POSIX
    except OSError as e:
        raise StorageError(f"Failed writing {path}: {e}") from e


def add_task(path: Path, task: Task) -> None:
    """Append a task to storage."""
    with _lock(path, exclusive=True):
        _validate_task(task)
        tasks = _load_tasks_unlocked(path)
        tasks.append(task)
        _save_tasks_unlocked(path, tasks)


def get_pending_tasks(path: Path) -> List[Task]:
    """Return all tasks currently pending (everything in storage)."""
    return load_tasks(path)


def remove_task(path: Path, task_id: str) -> Optional[Task]:
    """
    Remove a task by id.

    Returns the removed task, or None if not found.
    """
    with _lock(path, exclusive=True):
        tasks = _load_tasks_unlocked(path)
        kept: List[Task] = []
        removed: Optional[Task] = None
        for t in tasks:
            if removed is None and str(t.get("id")) == task_id:
                removed = t
                continue
            kept.append(t)
        if removed is None:
            return None
        _save_tasks_unlocked(path, kept)
        return removed


def update_task_status(path: Path, task_id: str, status: TaskStatus, *, error: Optional[str] = None) -> bool:
    """
    Update a task status in-place.

    Returns True if updated, False if not found.
    """
    if status not in {"pending", "running", "done", "failed"}:
        raise StorageError(f"Invalid status: {status}")

    with _lock(path, exclusive=True):
        tasks = _load_tasks_unlocked(path)
        updated = False
        for t in tasks:
            if str(t.get("id")) == task_id:
                t["status"] = status
                if error is not None:
                    t["error"] = str(error)
                elif "error" in t and status != "failed":
                    t.pop("error", None)
                updated = True
                break
        if not updated:
            return False
        _save_tasks_unlocked(path, tasks)
        return True


def prune_done_tasks(path: Path) -> int:
    """
    Remove tasks with status == done.

    Returns the number of removed tasks.
    """
    with _lock(path, exclusive=True):
        tasks = _load_tasks_unlocked(path)
        kept = [t for t in tasks if str(t.get("status")) != "done"]
        removed = len(tasks) - len(kept)
        if removed:
            _save_tasks_unlocked(path, kept)
        return removed


def _validate_task(task: Task) -> None:
    required = ["id", "type", "run_at", "created_at", "status"]
    for k in required:
        if k not in task:
            raise StorageError(f"Task missing required field: {k}")
    if not str(task["id"]).strip():
        raise StorageError("Task 'id' must be a non-empty string")
    if not str(task["type"]).strip():
        raise StorageError("Task 'type' must be a non-empty string")
    task_type = str(task["type"])
    if task_type == "remind":
        if "message" not in task:
            raise StorageError("Reminder task missing required field: message")
        task["message"] = str(task["message"])
    else:
        # Non-reminder tasks may use `action` instead of `message`.
        if "action" in task:
            task["action"] = str(task["action"])
        if "message" in task:
            task["message"] = str(task["message"])
    task["run_at"] = float(task["run_at"])
    task["created_at"] = float(task["created_at"])
    task["status"] = str(task["status"])
    if task["status"] not in {"pending", "running", "done", "failed"}:
        raise StorageError(f"Invalid task status: {task['status']}")


def _maybe_migrate_legacy_task(obj: Task) -> Optional[Task]:
    """
    Migrate older task formats into the standardized schema.

    Legacy schema (previous versions) stored:
    - type: "reminder"
    - status: "scheduled"/"completed"/...
    - created_at_epoch_seconds, run_at_epoch_seconds
    - payload: { "message": ... }

    We only migrate tasks that are still pending/scheduled.
    Completed legacy tasks are ignored.
    """
    # Already in new format
    if {"id", "type", "message", "run_at", "created_at"}.issubset(obj.keys()):
        if "status" not in obj:
            obj["status"] = "pending"
        return obj

    # Legacy format
    if "run_at_epoch_seconds" in obj and "created_at_epoch_seconds" in obj:
        status = str(obj.get("status", "scheduled")).lower()
        if status != "scheduled":
            return None

        payload = obj.get("payload") or {}
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("message", ""))

        return {
            "id": str(obj.get("id", "")),
            "type": "remind",
            "message": message,
            "run_at": float(obj["run_at_epoch_seconds"]),
            "created_at": float(obj["created_at_epoch_seconds"]),
            "status": "pending",
        }

    # Unknown format: skip silently (keeps daemon robust)
    return None


def _save_tasks_unlocked(path: Path, tasks: List[Task]) -> None:
    """
    Save tasks assuming the caller already holds the exclusive lock.

    This avoids nested locking when implementing read-modify-write helpers.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = {"tasks": tasks}
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)

class _Lock:
    def __init__(self, lock_file):
        self._lock_file = lock_file

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            self._lock_file.close()


def _lock(path: Path, *, exclusive: bool) -> _Lock:
    """
    Acquire a lock for safe concurrent CLI/daemon access.

    We lock a sibling `.lock` file to avoid issues with atomic replace of the
    actual `tasks.json`.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)

    # Ensure the tasks file exists for readers/writers.
    if not path.exists():
        path.write_text(json.dumps({"tasks": []}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return _Lock(lock_file)


def _read_tasks_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_tasks_unlocked(path: Path) -> List[Task]:
    """
    Load tasks assuming the caller already holds a lock.
    """
    raw = _read_tasks_file(path)
    if not raw.strip():
        return []

    data = json.loads(raw)
    if isinstance(data, dict) and "tasks" in data:
        tasks = data["tasks"]
    else:
        tasks = data

    if not isinstance(tasks, list):
        raise StorageError("tasks.json must contain a list (or an object with a 'tasks' list)")

    normalized: List[Task] = []
    for obj in tasks:
        if not isinstance(obj, dict):
            continue

        migrated = _maybe_migrate_legacy_task(obj)
        if migrated is None:
            continue

        _validate_task(migrated)
        normalized.append(migrated)
    return normalized

