"""
Task dispatcher.

Routes task execution by type. Chains are parsed and executed sequentially by the
chain engine and system steps execute through the whitelisted system executor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.chains.chain_engine import run_chain_with_persistence
from services.notifier import notify
from services.system_executor import execute_action
from storage.task_store import Task


def dispatch_task(task: Task, task_file: Path | None = None) -> Dict[str, Any]:
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

    if task_type == "chain":
        task_id = str(task.get("id", ""))
        command = str(task.get("action", "")).strip()
        if not command:
            return {"success": False, "type": "chain", "error": "Missing command"}
        
        # Use persistent execution if task_file is provided
        if task_file:
            summary = run_chain_with_persistence(task_file, task_id)
        else:
            # Fallback to non-persistent execution
            from core.chains.chain_engine import run_chain
            summary = run_chain(command)
        
        ok = bool(summary.get("success", False))
        return {"success": ok, "type": "chain", "summary": summary}

    return {"success": False, "type": task_type, "error": f"Unsupported task type: {task_type}"}


def dispatch_system_action(action: str) -> Dict[str, Any]:
    """Dispatch a single system action through the whitelisted executor."""
    return execute_action(action)

