"""
Dynamic action manager for Umbra.

Handles both static whitelisted actions and dynamic app launching
with security enforcement and desktop app discovery.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set

SystemResult = Dict[str, object]


class ActionManager:
    """Manages both static and dynamic actions with security."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize action manager with config file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "actions.json"
        
        self.config_path = config_path
        self.static_actions: Dict[str, List[str]] = {}
        self.natural_language_mappings: Dict[str, str] = {}
        self.dynamic_app_patterns: List[str] = []
        self.blocked_chars: Set[str] = set()
        self.max_app_name_length: int = 50
        self.discovered_apps: Set[str] = set()
        
        self._load_config()
        self._scan_desktop_apps()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            self.static_actions = config.get("static_actions", {})
            self.natural_language_mappings = config.get("natural_language_mappings", {})
            self.dynamic_app_patterns = config.get("dynamic_app_patterns", [])
            
            security_config = config.get("security", {})
            self.blocked_chars = set(security_config.get("blocked_chars", []))
            self.max_app_name_length = security_config.get("max_app_name_length", 50)
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Fallback to basic configuration
            self.static_actions = {
                "volume_up": ["amixer", "sset", "Master", "10%+"],
                "volume_down": ["amixer", "sset", "Master", "10%-"],
                "lock_screen": ["loginctl", "lock-session"],
            }
            self.natural_language_mappings = {
                "volume up": "volume_up",
                "increase volume": "volume_up",
                "volume_up": "volume_up",
                "volume down": "volume_down", 
                "decrease volume": "volume_down",
                "volume_down": "volume_down",
                "lock screen": "lock_screen",
                "lock": "lock_screen",
            }
            self.dynamic_app_patterns = ["open", "launch", "start"]
            self.blocked_chars = {";", "&", "|", "`", "$", "(", ")", "<", ">", "\"", "'"}
    
    def _scan_desktop_apps(self) -> None:
        """Scan desktop applications for auto-discovery."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            if not config.get("desktop_scan", {}).get("enabled", False):
                return
            
            scan_paths = config.get("desktop_scan", {}).get("paths", [])
            
            for scan_path in scan_paths:
                if not os.path.exists(scan_path):
                    continue
                
                for desktop_file in Path(scan_path).glob("*.desktop"):
                    try:
                        with open(desktop_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Extract app name from Desktop file
                        for line in content.split('\n'):
                            if line.startswith('Name='):
                                app_name = line[5:].strip()
                                if app_name and len(app_name) <= self.max_app_name_length:
                                    self.discovered_apps.add(app_name.lower())
                                break
                            elif line.startswith('Exec='):
                                exec_line = line[5:].strip()
                                # Extract command name (before first space or parameter)
                                exec_name = exec_line.split()[0].split('/')[-1]
                                if exec_name and len(exec_name) <= self.max_app_name_length:
                                    self.discovered_apps.add(exec_name.lower())
                                break
                    except (UnicodeDecodeError, IOError):
                        continue
                        
        except Exception:
            # Desktop scanning is optional, fail silently
            pass
    
    def _sanitize_app_name(self, app_name: str) -> Optional[str]:
        """Sanitize app name for security."""
        if not app_name or not app_name.strip():
            return None
        
        sanitized = app_name.strip().lower()
        
        # Check length
        if len(sanitized) > self.max_app_name_length:
            return None
        
        # Check for blocked characters
        for char in self.blocked_chars:
            if char in sanitized:
                return None
        
        # Remove any remaining shell-like patterns
        sanitized = re.sub(r'[;&|`$()<>"]', '', sanitized)
        
        # Only allow alphanumeric, spaces, hyphens, and underscores
        sanitized = re.sub(r'[^a-z0-9 _-]', '', sanitized)
        
        return sanitized.strip() if sanitized.strip() else None
    
    def _is_dynamic_app_command(self, text: str) -> Optional[str]:
        """Check if text matches dynamic app pattern."""
        text_lower = text.lower().strip()
        
        for pattern in self.dynamic_app_patterns:
            if text_lower.startswith(pattern + " "):
                app_name = text_lower[len(pattern):].strip()
                sanitized = self._sanitize_app_name(app_name)
                if sanitized:
                    return sanitized
        
        return None
    
    def normalize_action(self, text: str) -> str:
        """
        Normalize natural language text to action name.
        
        First tries static mappings, then falls back to dynamic app detection.
        """
        if not text or not text.strip():
            return ""
        
        # Convert to lowercase and strip
        normalized = text.strip().lower()
        
        # Check static mappings first
        mapped_action = self.natural_language_mappings.get(normalized, "")
        if mapped_action in self.static_actions:
            return mapped_action
        
        # Check dynamic app patterns
        dynamic_app = self._is_dynamic_app_command(normalized)
        if dynamic_app:
            return f"dynamic_app:{dynamic_app}"
        
        return ""
    
    def execute_action(self, action: str) -> SystemResult:
        """
        Execute a whitelisted system action or dynamic app.
        
        Uses subprocess.run with 10-second timeout for daemon safety.
        Pre-validates command existence using shutil.which.
        """
        if action.startswith("dynamic_app:"):
            return self._execute_dynamic_app(action[12:])  # Remove "dynamic_app:" prefix
        
        # Static action
        cmd = self.static_actions.get(action)
        if cmd is None:
            return {"success": False, "action": action, "error": "Action not found"}
        
        # Pre-validate command exists
        if not shutil.which(cmd[0]):
            return {"success": False, "action": action, "error": f"Command not found: {cmd[0]}"}
        
        try:
            result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
            return {
                "success": True, 
                "action": action, 
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "action": action, "error": "timeout"}
        except OSError as e:
            return {"success": False, "action": action, "error": str(e)}
    
    def _execute_dynamic_app(self, app_name: str) -> SystemResult:
        """Execute dynamic application using xdg-open."""
        # Additional security check
        sanitized = self._sanitize_app_name(app_name)
        if not sanitized:
            return {"success": False, "action": f"dynamic_app:{app_name}", "error": "Invalid app name"}
        
        # Try multiple methods to open the app
        methods = [
            [sanitized],  # Direct execution
            ["xdg-open", sanitized],  # Default open handler
            ["gtk-launch", sanitized],  # GTK app launcher
        ]
        
        for cmd in methods:
            if shutil.which(cmd[0]):
                try:
                    result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
                    return {
                        "success": True,
                        "action": f"dynamic_app:{sanitized}",
                        "return_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "method": cmd[0]
                    }
                except (subprocess.TimeoutExpired, OSError):
                    continue
        
        return {"success": False, "action": f"dynamic_app:{app_name}", "error": f"App not found: {sanitized}"}
    
    def get_available_actions(self) -> Dict[str, str]:
        """Get all available actions for help/documentation."""
        actions = {}
        
        # Static actions
        for action in self.static_actions:
            actions[action] = "static"
        
        # Discovered apps
        for app in sorted(self.discovered_apps):
            actions[f"dynamic_app:{app}"] = "dynamic"
        
        return actions
