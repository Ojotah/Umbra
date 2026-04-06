"""
Command parsing for Umbra.

V1 aims for predictable, testable parsing without NLP libraries. The parser
turns a raw user string into a structured command with:
- intent (e.g., "remind")
- time (currently: a delay in seconds)
- message (free text)

This module is pure logic (no I/O), which makes it easy to unit test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


class ParseError(ValueError):
    """Raised when a user command cannot be parsed."""


@dataclass(frozen=True)
class ParsedCommand:
    """Structured representation of a user command."""

    intent: str
    delay_seconds: Optional[int]
    message: str


_REMIND_RE = re.compile(
    r"^\s*remind\s+me\s+in\s+(?P<amount>\d+)\s*(?P<unit>seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\s+(?P<msg>.+?)\s*$",
    re.IGNORECASE,
)


def parse(text: str) -> ParsedCommand:
    """
    Parse a user string into a `ParsedCommand`.

    Supported V1 command:
        "remind me in 10 seconds <message>"

    Raises:
        ParseError: if the command is not recognized or invalid.
    """
    if not text or not text.strip():
        raise ParseError('Empty command. Example: umbra "remind me in 10 seconds test"')

    m = _REMIND_RE.match(text)
    if m:
        amount = int(m.group("amount"))
        unit = m.group("unit").lower()
        msg = m.group("msg").strip()
        if not msg:
            raise ParseError("Reminder message cannot be empty.")

        delay_seconds = _to_seconds(amount, unit)
        return ParsedCommand(intent="remind", delay_seconds=delay_seconds, message=msg)

    raise ParseError(
        'Unrecognized command. Supported V1: umbra "remind me in 10 seconds <message>"'
    )


def _to_seconds(amount: int, unit: str) -> int:
    """Convert amount + unit into seconds."""
    if amount < 0:
        raise ParseError("Time amount must be >= 0")

    if unit in {"second", "seconds", "sec", "secs", "s"}:
        return amount
    if unit in {"minute", "minutes", "min", "mins", "m"}:
        return amount * 60
    if unit in {"hour", "hours", "hr", "hrs", "h"}:
        return amount * 60 * 60

    raise ParseError(f"Unsupported time unit: {unit}")

