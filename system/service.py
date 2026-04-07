"""
Systemd service management for Umbra.

Provides installation and management of systemd user service.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVICE_CONTENT = """[Unit]
Description=Umbra Task Automation Daemon
After=network.target

[Service]
Type=simple
ExecStart={exec_path}
Restart=always
RestartSec=5
User={user}
Environment=PYTHONPATH={python_path}

[Install]
WantedBy=default.target
"""


def get_service_file_path() -> Path:
    """Get the systemd user service file path."""
    return Path.home() / ".config" / "systemd" / "user" / "umbra.service"


def generate_service_content() -> str:
    """Generate the systemd service file content."""
    exec_path = sys.executable
    user = os.environ.get("USER", "umbra")
    python_path = str(Path(__file__).parent.parent)
    
    return SERVICE_CONTENT.format(
        exec_path=exec_path,
        user=user,
        python_path=python_path
    )


def install_service() -> str:
    """Install the systemd user service."""
    try:
        service_dir = get_service_file_path().parent
        service_dir.mkdir(parents=True, exist_ok=True)
        
        service_file = get_service_file_path()
        service_file.write_text(generate_service_content(), encoding="utf-8")
        
        # Reload systemd and enable the service
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", "umbra"], check=True, capture_output=True)
        
        return "Systemd service installed and enabled"
    except (subprocess.CalledProcessError, OSError) as e:
        return f"Failed to install service: {e}"


def uninstall_service() -> str:
    """Uninstall the systemd user service."""
    try:
        service_file = get_service_file_path()
        
        # Stop and disable the service first
        subprocess.run(["systemctl", "--user", "stop", "umbra"], check=False, capture_output=True)
        subprocess.run(["systemctl", "--user", "disable", "umbra"], check=False, capture_output=True)
        
        # Remove the service file
        if service_file.exists():
            service_file.unlink()
        
        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        
        return "Systemd service uninstalled"
    except (subprocess.CalledProcessError, OSError) as e:
        return f"Failed to uninstall service: {e}"


def get_service_status() -> str:
    """Get the status of the systemd user service."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "umbra"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return "active"
        elif "inactive" in result.stdout:
            return "inactive"
        else:
            return "failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
