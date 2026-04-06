"""
Umbra command registry.

Umbra supports "natural language" style commands (parsed in `core.parser`).
This registry exists for discovery/UX:
- show available commands via `umbra --list-commands`
- provide descriptions and examples without importing heavy dependencies
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from commands import message, remind, system, workflow


@dataclass(frozen=True)
class CommandInfo:
    """Metadata used for help and discovery."""

    name: str
    description: str
    examples: Sequence[str]


REGISTRY: dict[str, CommandInfo] = {
    remind.NAME: CommandInfo(remind.NAME, remind.DESCRIPTION, tuple(remind.EXAMPLES)),
    message.NAME: CommandInfo(message.NAME, message.DESCRIPTION, tuple(message.EXAMPLES)),
    system.NAME: CommandInfo(system.NAME, system.DESCRIPTION, tuple(system.EXAMPLES)),
    workflow.NAME: CommandInfo(workflow.NAME, workflow.DESCRIPTION, tuple(workflow.EXAMPLES)),
}


def list_commands() -> list[CommandInfo]:
    """Return all known commands, sorted by name."""
    return [REGISTRY[name] for name in sorted(REGISTRY.keys())]


def format_command_list(infos: Iterable[CommandInfo]) -> str:
    """Format a human-friendly command list for printing to the console."""
    lines: list[str] = ["Available commands:"]
    for info in infos:
        lines.append(f"- {info.name} \u2192 {info.description}")
        if info.examples:
            lines.append(f"  Example: {info.examples[0]}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


