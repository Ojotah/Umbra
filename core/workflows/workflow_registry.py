"""
Workflow registry.

Provides built-in fallback workflows and helpers for merging JSON-loaded
workflows from disk.
"""

from __future__ import annotations

from typing import Dict, List

WorkflowMap = Dict[str, List[str]]

# Static fallback workflows (used when file is missing/invalid).
WORKFLOWS: WorkflowMap = {
    "morning": ["open_vscode", "open_chrome", "volume_up"],
    "night": ["volume_down", "lock_screen"],
}


def default_workflows() -> WorkflowMap:
    """Return a copy of default workflows."""
    return {k: list(v) for k, v in WORKFLOWS.items()}

