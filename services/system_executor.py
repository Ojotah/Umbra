"""
System executor.

Executes only whitelisted actions mapped to OS commands.
"""

from __future__ import annotations

import subprocess
import shutil
from typing import Dict, List

SystemResult = Dict[str, object]

# Whitelisted actions only.
WHITELIST: Dict[str, List[str]] = {
    "open_vscode": ["code"],
    "open_chrome": ["google-chrome"],
    "open_vim": ["vim"],
    "volume_up": ["amixer", "-D", "pulse", "sset", "Master", "5%+"],
    "volume_down": ["amixer", "-D", "pulse", "sset", "Master", "5%-"],
    "lock_screen": ["loginctl", "lock-session"],
}


def normalize_action(text: str) -> str:
    """
    Normalize natural language text to action name.
    
    Simple implementation that maps common phrases to whitelisted actions.
    Only returns actions that are in the whitelist for security.
    """
    if not text or not text.strip():
        return ""
    
    # Convert to lowercase and strip
    normalized = text.strip().lower()
    
    # Simple mappings
    mappings = {
        "open vscode": "open_vscode",
        "vscode": "open_vscode",
        "code": "open_vscode",
        "open chrome": "open_chrome", 
        "chrome": "open_chrome",
        "google chrome": "open_chrome",
        "open vim": "open_vim",
        "vim": "open_vim",
        "volume up": "volume_up",
        "increase volume": "volume_up",
        "volume down": "volume_down",
        "decrease volume": "volume_down",
        "lock screen": "lock_screen",
        "lock": "lock_screen",
    }
    
    mapped_action = mappings.get(normalized, "")
    # Only return if the mapped action is in our whitelist
    return mapped_action if mapped_action in WHITELIST else ""


def execute_action(action: str) -> SystemResult:
    """
    Execute a whitelisted system action.

    Uses subprocess.run with 10-second timeout for daemon safety.
    Pre-validates command existence using shutil.which.
    """
    cmd = WHITELIST.get(action)
    if cmd is None:
        return {"success": False, "action": action, "error": "Action not whitelisted"}
    
    # Pre-validate command exists
    if not shutil.which(cmd[0]):
        return {"success": False, "action": action, "error": f"Command not found: {cmd[0]}"}
    
    try:
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        return {"success": True, "action": action, "return_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "action": action, "error": "timeout"}
    except OSError as e:
        return {"success": False, "action": action, "error": str(e)}
