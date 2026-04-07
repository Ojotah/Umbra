"""
CLI task command handlers.

These handlers implement CLI-facing task operations while leaving formatting to
`services.formatter` and using the UmbraAPI for all operations.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List

from umbra.api import api

_DURATION_RE = re.compile(r"^\s*(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s*$", re.I)


def parse_duration_to_seconds(token: str) -> int:
    """Parse duration tokens like `10s`, `2m`, `1h`."""
    return api.parse_duration(token)


def schedule_task(task_file: Path, *, message: str, delay_seconds: int) -> Dict[str, Any]:
    """Build and persist a reminder task."""
    # task_file parameter kept for compatibility but not used
    return api.add_reminder(message, delay_seconds)


def schedule_chain_task(task_file: Path, *, command: str) -> Dict[str, Any]:
    """Persist an immediate chain task for daemon execution."""
    # task_file parameter kept for compatibility but not used
    return api.add_chain_task(command)


def list_tasks(task_file: Path) -> List[Dict[str, Any]]:
    """Load tasks sorted by run time ascending."""
    # task_file parameter kept for compatibility but not used
    return api.list_tasks()


def status_counts(task_file: Path) -> List[Dict[str, Any]]:
    """Load all tasks for status summarization."""
    # task_file parameter kept for compatibility but not used
    return api.list_tasks()


def get_task_by_id(task_file: Path, *, task_id: str) -> Dict[str, Any] | None:
    """Load a specific task by its ID."""
    # task_file parameter kept for compatibility but not used
    return api.get_task(task_id)


def dry_run_chain(command: str) -> None:
    """Parse and display chain execution plan without executing."""
    from core.chains.chain_engine import parse_chain
    
    actions = parse_chain(command)
    if not actions:
        print("No valid actions found in command.")
        return
    
    print("Plan:")
    for i, action in enumerate(actions, 1):
        print(f"{i}. {action}")
    return


def retry_task(task_file: Path, *, task_id: str) -> Dict[str, Any]:
    """Clone a task for retry with new ID and reset status."""
    # task_file parameter kept for compatibility but not used
    return api.retry_task(task_id)


def read_logs(log_file: Path, *, limit: int = 50) -> list[str]:
    """Read latest log lines (newest first)."""
    # log_file parameter kept for compatibility but not used
    logs = api.get_recent_logs(limit)
    return [f"{log.get('timestamp', '')} - {log.get('level', 'INFO')} - {log.get('message', '')}" for log in logs]

