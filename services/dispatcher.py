"""
Task dispatcher.

Routes task execution by type. Workflows are expanded by the workflow engine and
system steps execute through the whitelisted system executor.
"""

from __future__ import annotations

from typing import Any, Dict

from core.workflows.workflow_engine import run_workflow
from services.notifier import notify
from services.system_executor import execute_action
from storage.task_store import Task


def dispatch_task(task: Task) -> Dict[str, Any]:
    """Dispatch a task and return structured execution metadata."""
    task_type = str(task.get("type"))

    if task_type == "remind":
        message = str(task.get("message", "")).strip()
        notify("Umbra Reminder", message or "Reminder")
        return {"success": True, "type": "remind"}

    if task_type == "system":
        action = str(task.get("action", "")).strip()
        if not action:
            return {"success": False, "type": "system", "error": "Missing action"}
        return dispatch_system_action(action)

    if task_type == "workflow":
        action = str(task.get("action", "")).strip()
        if not action:
            return {"success": False, "type": "workflow", "error": "Missing action"}
        summary = run_workflow(action)
        ok = int(summary.get("failed", 0)) == 0
        return {"success": ok, "type": "workflow", "summary": summary}

    return {"success": False, "type": task_type, "error": f"Unsupported task type: {task_type}"}


def dispatch_system_action(action: str) -> Dict[str, Any]:
    """Dispatch a single system action through the whitelisted executor."""
    return execute_action(action)

