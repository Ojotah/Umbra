"""
Task persistence layer (SQLite).

Umbra persists scheduled work to a SQLite database so the daemon can restore tasks
across restarts.

This module intentionally provides a small, explicit API that matches the old
JSON-based interface for compatibility.

Task format (standardized):
{
  "id": "uuid",
  "type": "remind",
  "message": "test",
  "run_at": 1712345678.0,
  "created_at": 1712345600.0,
  "status": "pending"
}
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class StorageError(RuntimeError):
    """Raised when tasks cannot be loaded/saved."""


Task = Dict[str, Any]

TaskStatus = str  # "pending" | "running" | "done" | "failed"

# Database path
DB_PATH = Path.home() / ".local" / "share" / "umbra" / "umbra.db"

# Legacy JSON path for migration
LEGACY_JSON_PATH = Path.home() / ".local" / "share" / "umbra" / "tasks.json"


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init_database() -> None:
    """Initialize database tables if they don't exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                action TEXT,
                run_at REAL,
                created_at REAL,
                error TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT
            )
        """)
        
        conn.commit()


def _migrate_from_json() -> None:
    """Migrate tasks from legacy JSON file to SQLite."""
    if not LEGACY_JSON_PATH.exists():
        return
    
    # Check if already migrated
    migrated_path = LEGACY_JSON_PATH.with_suffix(".json.migrated")
    if migrated_path.exists():
        return
    
    try:
        # Load legacy JSON
        with open(LEGACY_JSON_PATH, 'r', encoding='utf-8') as f:
            raw = f.read()
        
        if not raw.strip():
            # Empty file, just mark as migrated
            LEGACY_JSON_PATH.rename(migrated_path)
            return
        
        data = json.loads(raw)
        if isinstance(data, dict) and "tasks" in data:
            tasks = data["tasks"]
        else:
            tasks = data
        
        if not isinstance(tasks, list):
            tasks = []
        
        # Migrate to SQLite
        with _get_connection() as conn:
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                
                # Normalize task
                normalized = _maybe_migrate_legacy_task(task)
                if normalized is None:
                    continue
                
                _validate_task(normalized)
                
                # Insert task
                conn.execute("""
                    INSERT OR REPLACE INTO tasks 
                    (id, type, status, message, action, run_at, created_at, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    normalized["id"],
                    normalized["type"],
                    normalized["status"],
                    normalized.get("message"),
                    normalized.get("action"),
                    normalized["run_at"],
                    normalized["created_at"],
                    normalized.get("error")
                ))
                
                # Insert steps if present
                if "steps" in normalized:
                    for i, step in enumerate(normalized["steps"]):
                        step_id = str(uuid.uuid4())
                        conn.execute("""
                            INSERT OR REPLACE INTO task_steps
                            (id, task_id, position, action, status, error)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            step_id,
                            normalized["id"],
                            i,
                            step.get("action", ""),
                            step.get("status", "pending"),
                            step.get("error")
                        ))
            
            conn.commit()
        
        # Mark as migrated
        LEGACY_JSON_PATH.rename(migrated_path)
        
    except Exception:
        # Migration failed, don't block startup
        pass


def _row_to_task(row: sqlite3.Row) -> Task:
    """Convert a database row to a task dictionary."""
    task = {
        "id": row["id"],
        "type": row["type"],
        "status": row["status"],
        "run_at": row["run_at"],
        "created_at": row["created_at"],
    }
    
    if row["message"]:
        task["message"] = row["message"]
    if row["action"]:
        task["action"] = row["action"]
    if row["error"]:
        task["error"] = row["error"]
    
    return task


def load_tasks(path: Path) -> List[Task]:
    """Load tasks from database (path parameter kept for compatibility)."""
    _init_database()
    _migrate_from_json()
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, type, status, message, action, run_at, created_at, error
                FROM tasks
                ORDER BY created_at DESC
            """)
            
            tasks = []
            for row in cursor:
                task = _row_to_task(row)
                
                # Load steps if this is a chain task
                if task["type"] == "chain":
                    step_cursor = conn.execute("""
                        SELECT id, position, action, status, error
                        FROM task_steps
                        WHERE task_id = ?
                        ORDER BY position
                    """, (task["id"],))
                    
                    steps = []
                    for step_row in step_cursor:
                        step = {
                            "id": step_row["id"],
                            "position": step_row["position"],
                            "action": step_row["action"],
                            "status": step_row["status"],
                        }
                        if step_row["error"]:
                            step["error"] = step_row["error"]
                        steps.append(step)
                    
                    task["steps"] = steps
                
                tasks.append(task)
            
            return tasks
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to load tasks: {e}") from e


def save_tasks(path: Path, tasks: List[Task]) -> None:
    """Save tasks to database (path parameter kept for compatibility)."""
    _init_database()
    
    try:
        with _get_connection() as conn:
            # Clear existing tasks
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM task_steps")
            
            # Insert all tasks
            for task in tasks:
                _validate_task(task)
                
                conn.execute("""
                    INSERT INTO tasks 
                    (id, type, status, message, action, run_at, created_at, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task["id"],
                    task["type"],
                    task["status"],
                    task.get("message"),
                    task.get("action"),
                    task["run_at"],
                    task["created_at"],
                    task.get("error")
                ))
                
                # Insert steps if present
                if "steps" in task:
                    for i, step in enumerate(task["steps"]):
                        step_id = step.get("id", str(uuid.uuid4()))
                        conn.execute("""
                            INSERT INTO task_steps
                            (id, task_id, position, action, status, error)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            step_id,
                            task["id"],
                            i,
                            step.get("action", ""),
                            step.get("status", "pending"),
                            step.get("error")
                        ))
            
            conn.commit()
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to save tasks: {e}") from e


def add_task(path: Path, task: Task) -> None:
    """Append a task to storage (path parameter kept for compatibility)."""
    _init_database()
    _validate_task(task)
    
    try:
        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks 
                (id, type, status, message, action, run_at, created_at, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task["id"],
                task["type"],
                task["status"],
                task.get("message"),
                task.get("action"),
                task["run_at"],
                task["created_at"],
                task.get("error")
            ))
            
            # Insert steps if present
            if "steps" in task:
                for i, step in enumerate(task["steps"]):
                    step_id = step.get("id", str(uuid.uuid4()))
                    conn.execute("""
                        INSERT INTO task_steps
                        (id, task_id, position, action, status, error)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        step_id,
                        task["id"],
                        i,
                        step.get("action", ""),
                        step.get("status", "pending"),
                        step.get("error")
                    ))
            
            conn.commit()
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to add task: {e}") from e


def get_pending_tasks(path: Path) -> List[Task]:
    """Return all tasks currently pending (path parameter kept for compatibility)."""
    _init_database()
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, type, status, message, action, run_at, created_at, error
                FROM tasks
                WHERE status = 'pending'
                ORDER BY run_at ASC
            """)
            
            tasks = []
            for row in cursor:
                task = _row_to_task(row)
                
                # Load steps if this is a chain task
                if task["type"] == "chain":
                    step_cursor = conn.execute("""
                        SELECT id, position, action, status, error
                        FROM task_steps
                        WHERE task_id = ?
                        ORDER BY position
                    """, (task["id"],))
                    
                    steps = []
                    for step_row in step_cursor:
                        step = {
                            "id": step_row["id"],
                            "position": step_row["position"],
                            "action": step_row["action"],
                            "status": step_row["status"],
                        }
                        if step_row["error"]:
                            step["error"] = step_row["error"]
                        steps.append(step)
                    
                    task["steps"] = steps
                
                tasks.append(task)
            
            return tasks
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to get pending tasks: {e}") from e


def remove_task(path: Path, task_id: str) -> Optional[Task]:
    """Remove a task by id (path parameter kept for compatibility)."""
    _init_database()
    
    try:
        with _get_connection() as conn:
            # Get the task first
            cursor = conn.execute("""
                SELECT id, type, status, message, action, run_at, created_at, error
                FROM tasks
                WHERE id = ?
            """, (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            task = _row_to_task(row)
            
            # Load steps if this is a chain task
            if task["type"] == "chain":
                step_cursor = conn.execute("""
                    SELECT id, position, action, status, error
                    FROM task_steps
                    WHERE task_id = ?
                    ORDER BY position
                """, (task["id"],))
                
                steps = []
                for step_row in step_cursor:
                    step = {
                        "id": step_row["id"],
                        "position": step_row["position"],
                        "action": step_row["action"],
                        "status": step_row["status"],
                    }
                    if step_row["error"]:
                        step["error"] = step_row["error"]
                    steps.append(step)
                
                task["steps"] = steps
            
            # Delete the task (steps will be deleted by cascade)
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            
            return task
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to remove task: {e}") from e


def update_task_status(path: Path, task_id: str, status: TaskStatus, *, error: Optional[str] = None) -> bool:
    """Update a task status in-place (path parameter kept for compatibility)."""
    if status not in {"pending", "running", "done", "failed"}:
        raise StorageError(f"Invalid status: {status}")
    
    _init_database()
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                UPDATE tasks
                SET status = ?, error = ?
                WHERE id = ?
            """, (status, error, task_id))
            
            conn.commit()
            return cursor.rowcount > 0
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to update task status: {e}") from e


def prune_done_tasks(path: Path) -> int:
    """Remove tasks with status == done (path parameter kept for compatibility)."""
    _init_database()
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE status = 'done'")
            conn.commit()
            return cursor.rowcount
    
    except sqlite3.Error as e:
        raise StorageError(f"Failed to prune done tasks: {e}") from e


def _validate_task(task: Task) -> None:
    """Validate task structure."""
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
    """Migrate older task formats into the standardized schema."""
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

