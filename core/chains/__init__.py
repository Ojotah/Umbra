"""
Chain execution system.

Replaces the static workflow system with dynamic natural language parsing
and sequential action execution.
"""

from __future__ import annotations

from .chain_engine import parse_chain, run_chain

__all__ = ["parse_chain", "run_chain"]
