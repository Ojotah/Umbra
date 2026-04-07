"""
System executor.

Executes actions through the dynamic action manager.
Provides backward compatibility with existing code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .action_manager import ActionManager

SystemResult = Dict[str, object]

# Global action manager instance
_action_manager: ActionManager | None = None


def get_action_manager() -> ActionManager:
    """Get or create the global action manager instance."""
    global _action_manager
    if _action_manager is None:
        _action_manager = ActionManager()
    return _action_manager


def get_whitelist() -> Dict[str, List[str]]:
    """Get whitelist for backward compatibility."""
    return get_action_manager().static_actions


def normalize_action(text: str) -> str:
    """
    Normalize natural language text to action name.
    
    Delegates to ActionManager for both static and dynamic actions.
    """
    return get_action_manager().normalize_action(text)


def execute_action(action: str) -> SystemResult:
    """
    Execute a system action.
    
    Delegates to ActionManager for both static and dynamic actions.
    """
    return get_action_manager().execute_action(action)


# Backward compatibility aliases
WHITELIST = get_whitelist()
