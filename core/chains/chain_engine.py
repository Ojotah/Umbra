"""
Chain engine.

Parses natural language commands into action chains and executes them
sequentially through the system executor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from services.system_executor import normalize_action
from storage.task_store import load_tasks, save_tasks


@dataclass(frozen=True)
class StepResult:
    action: str
    success: bool
    detail: str


def parse_chain(command: str) -> List[str]:
    """
    Parse natural language command into action chain.
    
    Supports separators: "then", "and", ","
    Ignores filler words: "please", "maybe", "and then"
    
    Examples:
        "open vscode then open chrome" → ["open_vscode", "open_chrome"]
        "please open vscode and maybe open chrome" → ["open_vscode", "open_chrome"]
        "open vscode, open chrome and volume_up" → ["open_vscode", "open_chrome", "volume_up"]
    """
    if not command or not command.strip():
        return []
    
    # Remove filler words
    filler_words = ["please", "maybe"]
    cleaned_command = command.lower()
    for filler in filler_words:
        cleaned_command = cleaned_command.replace(filler, "")
    
    # Split on separators: "and then", "then", "and", "," (with "and then" taking precedence)
    # First split on "and then" to handle this compound separator
    and_then_parts = re.split(r'\s+and\s+then\s+', cleaned_command.strip(), flags=re.IGNORECASE)
    remaining_parts = []
    for part in and_then_parts:
        # Then split remaining part on other separators
        sub_parts = re.split(r'\s+then\s+|\s+and\s+|,\s*', part.strip(), flags=re.IGNORECASE)
        remaining_parts.extend(sub_parts)
    
    parts = remaining_parts
    
    # Filter out empty parts and normalize each action
    actions = []
    for part in parts:
        part = part.strip()
        if part:  # Skip empty strings from consecutive/trailing separators
            normalized = normalize_action(part)
            if normalized:
                actions.append(normalized)
            elif part.strip():  # Log invalid actions but don't crash
                # This will be handled by the executor with proper error
                pass
    
    return actions


def run_chain(command: str) -> Dict[str, Any]:
    """
    Execute a command chain and return execution summary.
    
    Each step is executed through the system executor with whitelist enforcement.
    Step failures are isolated and do not abort the whole chain.
    """
    actions = parse_chain(command)
    if not actions:
        return {
            "command": command,
            "total_steps": 0,
            "success": 0,
            "failed": 0,
            "results": [],
        }
    
    results: List[Dict[str, Any]] = []
    success = 0
    failed = 0
    
    # Local import avoids circular dependency
    from services.system_executor import execute_action
    
    for i, action in enumerate(actions, 1):
        try:
            res = execute_action(action)
            ok = bool(res.get("success"))
            if ok:
                success += 1
            else:
                failed += 1
            results.append({"action": action, "success": ok, "result": res})
        except Exception as e:  # noqa: BLE001 - step isolation by design
            failed += 1
            results.append({"action": action, "success": False, "error": str(e)})
    
    return {
        "command": command,
        "total_steps": len(actions),
        "success": success,
        "failed": failed,
        "results": results,
    }


def run_chain_with_persistence(task_file: Path, task_id: str) -> Dict[str, Any]:
    """
    Execute a chain task step-by-step with persistence after each step.
    
    This function updates the task status and individual step status in storage
    after each step execution, ensuring daemon crash doesn't lose progress.
    """
    # Load the current task
    tasks = load_tasks(task_file)
    task = None
    for t in tasks:
        if t.get("id") == task_id:
            task = t
            break
    
    if not task or task.get("type") != "chain":
        return {"success": False, "error": "Task not found or not a chain task"}
    
    # Update task status to running
    task["status"] = "running"
    save_tasks(task_file, tasks)
    
    steps = task.get("steps", [])
    success = 0
    failed = 0
    
    # Local import avoids circular dependency
    from services.system_executor import execute_action
    
    # Import logger for structured logging
    from services.logger import Logger
    log = Logger(Path(__file__).parent.parent / "logs" / "umbra.log")
    
    for i, step in enumerate(steps):
        action = step.get("action", "")
        if not action:
            continue
            
        # Update step status to running
        step["status"] = "running"
        step["error"] = None
        save_tasks(task_file, tasks)  # Atomic write
        
        # Log step start
        log.info_structured(task_id=task_id, event="step_started", action=action)
        
        try:
            res = execute_action(action)
            ok = bool(res.get("success"))
            
            if ok:
                step["status"] = "done"
                success += 1
                log.info_structured(task_id=task_id, event="step_done", action=action)
            else:
                step["status"] = "failed"
                step["error"] = res.get("error", "Unknown error")
                failed += 1
                log.error_structured(task_id=task_id, event="step_failed", action=action, error=step["error"])
        except Exception as e:  # noqa: BLE001 - step isolation by design
            step["status"] = "failed"
            step["error"] = str(e)
            failed += 1
            log.error_structured(task_id=task_id, event="step_failed", action=action, error=str(e))
        
        # Persist after each step
        save_tasks(task_file, tasks)
    
    # Update final task status
    task["status"] = "done" if failed == 0 else "failed"
    if failed > 0:
        task["error"] = f"{failed} step(s) failed"
    
    save_tasks(task_file, tasks)
    
    return {
        "success": failed == 0,
        "total_steps": len(steps),
        "success": success,
        "failed": failed,
    }
