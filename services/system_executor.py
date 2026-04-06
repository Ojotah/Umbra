"""
System executor.

Executes only whitelisted actions mapped to OS commands.
"""

from __future__ import annotations

import subprocess
from typing import Dict, List

SystemResult = Dict[str, object]

# Whitelisted actions only.
WHITELIST: Dict[str, List[str]] = {
    "open_vscode": ["code"],
    "open_chrome": ["google-chrome"],
    "volume_up": ["amixer", "-D", "pulse", "sset", "Master", "5%+"],
    "volume_down": ["amixer", "-D", "pulse", "sset", "Master", "5%-"],
    "lock_screen": ["loginctl", "lock-session"],
}


def execute_action(action: str) -> SystemResult:
    """
    Execute a whitelisted system action.

    Uses non-blocking `Popen` so workflow execution is daemon-safe.
    """
    cmd = WHITELIST.get(action)
    if cmd is None:
        return {"success": False, "action": action, "error": "Action not whitelisted"}

    try:
        proc = subprocess.Popen(  # noqa: S603 - command comes from internal whitelist
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"success": True, "action": action, "pid": proc.pid}
    except Exception as e:  # noqa: BLE001 - boundary layer
        return {"success": False, "action": action, "error": str(e)}

