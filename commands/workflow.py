"""
Workflow command (future).

Workflows are higher-level task definitions composed of multiple steps
(reminders, system commands, messages, etc.).

This file is a stub in V1.
"""

from __future__ import annotations

NAME = "workflow"
DESCRIPTION = "Run a multi-step workflow (coming soon)."
EXAMPLES = [
    'umbra "workflow morning-routine"',
]


def run_workflow(*_: object, **__: object) -> None:
    """Placeholder for future workflow runner."""
    raise NotImplementedError("Workflows are not implemented in V1.")

