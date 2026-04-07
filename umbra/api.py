"""
Umbra Core API.

This module provides the single internal interface that every caller (CLI, daemon,
TUI, GUI) must use. No caller is allowed to import from storage/ or services/
directly after this refactor.

The Core API exposes exactly these methods:
  - Task management: add_task, list_tasks, get_task, delete_task, retry_task
  - Execution: execute_task (called by daemon scheduler)
  - Daemon control: start_daemon, stop_daemon, daemon_status
  - Log access: get_recent_logs
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from commands.daemon import get_daemon_pid, is_daemon_running, start_daemon, stop_daemon
from commands.remind import ReminderRequest, build_reminder_task
from config.settings import SETTINGS
from core.chains.chain_engine import parse_chain
from services.dispatcher import dispatch_task
from services.logger import Logger
from storage.task_store import (
    StorageError,
    Task,
    add_task,
    get_pending_tasks,
    load_tasks,
    remove_task,
    update_task_status,
)

# PID file path for daemon control
PID_PATH = Path.home() / ".local" / "share" / "umbra" / "daemon.pid"

# Duration parsing regex
_DURATION_RE = re.compile(r"^\s*(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s*$", re.I)


class UmbraAPI:
    """Core API for Umbra task automation."""

    def __init__(self) -> None:
        self._log = Logger(SETTINGS.log_file, level="INFO")

    # Task management methods

    def add_task(
        self,
        type: str,
        message: str,
        action: Optional[str] = None,
        run_at: Optional[float] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Add a new task to the system."""
        now = time.time()
        
        if run_at is None:
            run_at = now + 1.0  # Default to 1 second from now
        
        task: Task = {
            "id": str(uuid.uuid4()),
            "type": type,
            "status": "pending",
            "run_at": run_at,
            "created_at": now,
        }
        
        if message:
            task["message"] = message
        if action:
            task["action"] = action
        if steps:
            task["steps"] = steps
        
        try:
            add_task(SETTINGS.tasks_file, task)
            return task
        except StorageError as e:
            raise RuntimeError(f"Failed to add task: {e}") from e

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        try:
            tasks = load_tasks(SETTINGS.tasks_file)
            
            if status:
                tasks = [t for t in tasks if t.get("status") == status]
            
            # Sort by run_at ascending
            return sorted(tasks, key=lambda t: t.get("run_at", 0))
        except StorageError as e:
            raise RuntimeError(f"Failed to list tasks: {e}") from e

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID."""
        try:
            tasks = load_tasks(SETTINGS.tasks_file)
            for task in tasks:
                if task.get("id") == task_id:
                    return task
            return None
        except StorageError as e:
            raise RuntimeError(f"Failed to get task: {e}") from e

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID."""
        try:
            removed = remove_task(SETTINGS.tasks_file, task_id)
            return removed is not None
        except StorageError as e:
            raise RuntimeError(f"Failed to delete task: {e}") from e

    def retry_task(self, task_id: str) -> Dict[str, Any]:
        """Retry a failed task by creating a new task with the same parameters."""
        original_task = self.get_task(task_id)
        if not original_task:
            raise ValueError(f"Task not found: {task_id}")
        
        now = time.time()
        
        # Create a new task with reset status
        retry_task_data = {
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
            retry_task_data["steps"] = steps
        
        try:
            add_task(SETTINGS.tasks_file, retry_task_data)
            return retry_task_data
        except StorageError as e:
            raise RuntimeError(f"Failed to retry task: {e}") from e

    # Execution methods (called by daemon scheduler)

    def execute_task(self, task_id: str) -> None:
        """Execute a task by ID (called by daemon scheduler)."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Mark as running first to prevent duplicates
        if not update_task_status(SETTINGS.tasks_file, task_id, "running"):
            return
        
        self._log.info(f"Executing task {task_id} ({task.get('type')})")
        
        try:
            result = dispatch_task(task, SETTINGS.tasks_file)
            if not bool(result.get("success")):
                raise RuntimeError(str(result.get("error", "Task dispatch failed")))
            
            update_task_status(SETTINGS.tasks_file, task_id, "done")
            self._log.info(f"Task done {task_id}")
            
        except Exception as e:
            try:
                update_task_status(SETTINGS.tasks_file, task_id, "failed", error=str(e))
            except Exception:
                pass
            self._log.error(f"Task failed {task_id}: {e}")
            raise

    # Daemon control methods

    def start_daemon(self) -> None:
        """Start the Umbra daemon."""
        if is_daemon_running():
            raise RuntimeError("Daemon is already running")
        
        result = start_daemon()
        if "successfully" not in result.lower():
            raise RuntimeError(f"Failed to start daemon: {result}")

    def stop_daemon(self) -> None:
        """Stop the Umbra daemon."""
        if not is_daemon_running():
            raise RuntimeError("Daemon is not running")
        
        result = stop_daemon()
        if "successfully" not in result.lower():
            raise RuntimeError(f"Failed to stop daemon: {result}")

    def daemon_status(self) -> Dict[str, Any]:
        """Get daemon status information."""
        running = is_daemon_running()
        pid = get_daemon_pid() if running else None
        
        status = {
            "running": running,
            "pid": pid,
            "uptime": None,
        }
        
        # Calculate uptime if daemon is running
        if running and pid and PID_PATH.exists():
            try:
                # Get process start time (this is a simplified approach)
                # In a real implementation, you might use psutil for more accurate info
                status["uptime"] = "unknown"
            except Exception:
                pass
        
        return status

    # Log access methods

    def get_recent_logs(self, n: int = 100) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        try:
            if not SETTINGS.log_file.exists():
                return []
            
            lines = SETTINGS.log_file.read_text(encoding="utf-8").splitlines()
            recent_lines = list(reversed(lines[-n:]))
            
            # Parse log lines into structured format
            logs = []
            for line in recent_lines:
                # Simple parsing - assumes format: "timestamp - level - message"
                parts = line.split(" - ", 2)
                if len(parts) >= 3:
                    logs.append({
                        "timestamp": parts[0],
                        "level": parts[1],
                        "message": parts[2].strip(),
                    })
                else:
                    logs.append({
                        "timestamp": "",
                        "level": "INFO",
                        "message": line.strip(),
                    })
            
            return logs
        except OSError as e:
            raise RuntimeError(f"Failed to read logs: {e}") from e

    # Convenience methods for common operations

    def add_reminder(self, message: str, delay_seconds: int) -> Dict[str, Any]:
        """Add a reminder task with delay in seconds."""
        reminder_req = ReminderRequest(delay_seconds=delay_seconds, message=message)
        task = build_reminder_task(reminder_req)
        
        try:
            add_task(SETTINGS.tasks_file, task)
            return task
        except StorageError as e:
            raise RuntimeError(f"Failed to add reminder: {e}") from e

    def add_chain_task(self, command: str, delay_seconds: int = 1) -> Dict[str, Any]:
        """Add a chain task for immediate execution."""
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
        
        task = self.add_task(
            type="chain",
            action=command,
            message=f"chain:{command}",
            run_at=now + delay_seconds,
            steps=steps,
        )
        
        return task

    def parse_duration(self, duration_token: str) -> int:
        """Parse duration token like '10s', '5m', '1h' to seconds."""
        m = _DURATION_RE.match(duration_token)
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


# Global API instance for easy import
api = UmbraAPI()
