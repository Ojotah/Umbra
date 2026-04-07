"""
Shell integration utilities for Umbra.

Provides shell setup and removal functionality for bash and zsh.
Standalone utility - does not import from storage/ or api.py.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


SHELL_INTEGRATION_MARKER_START = "# >>> umbra shell integration >>>"
SHELL_INTEGRATION_MARKER_END = "# <<< umbra shell integration <<<"


def detect_shell() -> str:
    """Detect user's shell from $SHELL environment variable."""
    shell_path = os.environ.get("SHELL", "")
    if "bash" in shell_path:
        return "bash"
    elif "zsh" in shell_path:
        return "zsh"
    else:
        # Default to bash if detection fails
        return "bash"


def get_rc_file_path(shell_name: str) -> Path:
    """Get the appropriate rc file path for the shell."""
    if shell_name == "bash":
        return Path.home() / ".bashrc"
    elif shell_name == "zsh":
        return Path.home() / ".zshrc"
    else:
        # Default to bashrc
        return Path.home() / ".bashrc"


def generate_integration_block() -> str:
    """Generate the shell integration block content."""
    return f"""{SHELL_INTEGRATION_MARKER_START}
# Umbra shell integration
alias ub="umbra"

# Tab completion function for umbra
_umbra_completion() {{
    local cur prev words
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    words=("${{COMP_WORDS[@]}}")

    # Basic command completion
    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "help add list status logs show retry chain daemon doctor service shell" -- "${{cur}}"))
    elif [[ ${{COMP_CWORD}} -eq 2 ]]; then
        case "${{prev}}" in
            add|list|status|logs|show|retry|chain|doctor)
                COMPREPLY=()
                ;;
            daemon)
                COMPREPLY=($(compgen -W "start stop status" -- "${{cur}}"))
                ;;
            service)
                COMPREPLY=($(compgen -W "install uninstall status" -- "${{cur}}"))
                ;;
            shell)
                COMPREPLY=($(compgen -W "setup remove" -- "${{cur}}"))
                ;;
        esac
    fi
}}

# Try argcomplete first, fallback to our completion
if command -v argcomplete >/dev/null 2>&1; then
    complete -o default -F _argcomplete umbra
else
    complete -F _umbra_completion umbra
fi

# Helper function to check daemon status
umbra_status() {{
    umbra daemon status 2>/dev/null | grep -E "(running|not running)" || echo "Unknown status"
}}

{SHELL_INTEGRATION_MARKER_END}"""


def remove_integration_block(rc_file: Path) -> bool:
    """Remove the integration block from rc file."""
    if not rc_file.exists():
        return False
    
    try:
        content = rc_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        new_lines = []
        in_block = False
        
        for line in lines:
            if SHELL_INTEGRATION_MARKER_START in line:
                in_block = True
                continue
            elif SHELL_INTEGRATION_MARKER_END in line:
                in_block = False
                continue
            elif not in_block:
                new_lines.append(line)
        
        rc_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def add_integration_block(rc_file: Path) -> bool:
    """Add or update the integration block to rc file."""
    try:
        # Remove existing block first
        remove_integration_block(rc_file)
        
        # Read current content
        if rc_file.exists():
            content = rc_file.read_text(encoding="utf-8")
        else:
            content = ""
        
        # Add new block at the end
        if not content.endswith("\n"):
            content += "\n"
        
        content += generate_integration_block() + "\n"
        
        rc_file.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


def setup_shell_integration() -> str:
    """Set up shell integration for detected shell."""
    shell_name = detect_shell()
    rc_file = get_rc_file_path(shell_name)
    
    if add_integration_block(rc_file):
        return f"Shell integration added. Run: source {rc_file.name}"
    else:
        return f"Failed to write to {rc_file}"


def remove_shell_integration() -> str:
    """Remove shell integration."""
    shell_name = detect_shell()
    rc_file = get_rc_file_path(shell_name)
    
    if remove_integration_block(rc_file):
        return f"Shell integration removed from {rc_file.name}"
    else:
        return "No integration found or failed to remove"
