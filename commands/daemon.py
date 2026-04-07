"""
Daemon control commands.

Provides status, start, and stop commands for Umbra daemon management.
Uses PID file for reliable daemon tracking.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PID_PATH = Path.home() / ".local" / "share" / "umbra" / "daemon.pid"


def get_daemon_pid() -> int | None:
    """Get the PID of running Umbra daemon from PID file."""
    try:
        if not PID_PATH.exists():
            return None
        
        pid_str = PID_PATH.read_text().strip()
        if not pid_str:
            return None
        
        pid = int(pid_str)
        
        # Check if process is actually running
        try:
            os.kill(pid, 0)  # Send signal 0 to check if process exists
            return pid
        except ProcessLookupError:
            # Process not running, clean up stale PID file
            PID_PATH.unlink(missing_ok=True)
            return None
    except (ValueError, OSError):
        return None


def is_daemon_running() -> bool:
    """Check if Umbra daemon is running."""
    return get_daemon_pid() is not None


def start_daemon() -> str:
    """Start the Umbra daemon in background."""
    if is_daemon_running():
        pid = get_daemon_pid()
        return f"Daemon is already running (PID: {pid})"
    
    try:
        # Start daemon in background with proper Python path
        # Use the directory containing this file as the daemon working directory
        daemon_dir = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env['PYTHONPATH'] = str(daemon_dir)
        subprocess.Popen(
            [sys.executable, "daemon.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=daemon_dir,
            env=env
        )
        time.sleep(1)  # Give it time to start
        
        if is_daemon_running():
            pid = get_daemon_pid()
            return f"Daemon started successfully (PID: {pid})"
        else:
            return "Failed to start daemon"
    except Exception as e:
        return f"Error starting daemon: {e}"


def stop_daemon() -> str:
    """Stop the running Umbra daemon."""
    pid = get_daemon_pid()
    if pid is None:
        return "Daemon is not running"
    
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)  # Give it time to stop gracefully
        
        # Check if it's still running
        if is_daemon_running():
            os.kill(pid, signal.SIGKILL)  # Force kill
            return "Daemon stopped (forced)"
        else:
            return "Daemon stopped successfully"
    except ProcessLookupError:
        return "Daemon is not running"
    except Exception as e:
        return f"Error stopping daemon: {e}"
