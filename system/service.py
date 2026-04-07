"""
Systemd user service management for Umbra.

Provides installation and management of systemd user service.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVICE_CONTENT = """[Unit]
Description=Umbra automation daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 -m umbra.daemon
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""


def get_service_file_path() -> Path:
    """Get the systemd user service file path."""
    return Path.home() / ".config" / "systemd" / "user" / "umbra.service"


def install_service() -> None:
    """Install systemd user service."""
    try:
        service_dir = get_service_file_path().parent
        service_dir.mkdir(parents=True, exist_ok=True)
        
        service_file = get_service_file_path()
        service_file.write_text(SERVICE_CONTENT, encoding="utf-8")
        
        # Reload systemd and enable/start service
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", "umbra"], check=True, capture_output=True)
        subprocess.run(["systemctl", "--user", "start", "umbra"], check=True, capture_output=True)
        
        print("Systemd service installed and started")
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Failed to install service: {e}")


def uninstall_service() -> None:
    """Uninstall systemd user service."""
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
        
        print("Systemd service uninstalled")
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Failed to uninstall service: {e}")
