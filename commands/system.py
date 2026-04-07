"""
System command execution (future).

Planned capabilities:
- allow safe execution of whitelisted system commands
- capture output, return codes, and errors
- support chaining via chain commands

This file is a stub in V1.
"""

from __future__ import annotations

NAME = "system"
DESCRIPTION = "Run a system command safely (coming soon)."
EXAMPLES = [
    'umbra "system uptime"',
]


def run_system_command(*_: object, **__: object) -> None:
    """Placeholder for future system command execution."""
    raise NotImplementedError("System command execution is not implemented in V1.")

