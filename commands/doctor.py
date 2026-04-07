"""
Doctor command for Umbra system health checks.

Performs comprehensive system health checks with colored output.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from umbra.api import api
from config.settings import SETTINGS


class Colors:
    """ANSI color codes for terminal output."""
    
    @staticmethod
    def supports_color() -> bool:
        """Check if terminal supports color."""
        term = os.environ.get("TERM", "")
        return (
            hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and
            ("color" in term or term in ("xterm", "xterm-256color", "screen"))
        )
    
    GREEN = "\033[92m" if supports_color() else ""
    RED = "\033[91m" if supports_color() else ""
    YELLOW = "\033[93m" if supports_color() else ""
    RESET = "\033[0m" if supports_color() else ""
    
    @classmethod
    def checkmark(cls, status: str) -> str:
        """Return colored checkmark or cross."""
        if status == "pass":
            return f"{cls.GREEN}[✓]{cls.RESET}"
        elif status == "fail":
            return f"{cls.RED}[✗]{cls.RESET}"
        else:  # warn
            return f"{cls.YELLOW}[!]{cls.RESET}"


def check_daemon_running() -> Tuple[str, str]:
    """Check if daemon is running via PID file."""
    try:
        pid_path = Path.home() / ".local" / "share" / "umbra" / "daemon.pid"
        if not pid_path.exists():
            return "fail", "PID file not found"
        
        pid_str = pid_path.read_text().strip()
        if not pid_str:
            return "fail", "PID file empty"
        
        pid = int(pid_str)
        os.kill(pid, 0)  # Check if process exists
        return "pass", f"Daemon running (PID: {pid})"
    except (ValueError, ProcessLookupError, OSError):
        return "fail", "Daemon not running"


def check_database_reachable() -> Tuple[str, str]:
    """Check if SQLite database is reachable."""
    try:
        db_path = Path.home() / ".local" / "share" / "umbra" / "umbra.db"
        if not db_path.exists():
            return "fail", "Database file not found"
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return "pass", "Database reachable"
    except Exception as e:
        return "fail", f"Database error: {e}"


def check_database_wal_mode() -> Tuple[str, str]:
    """Check if database is in WAL mode."""
    try:
        db_path = Path.home() / ".local" / "share" / "umbra" / "umbra.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0].lower() == "wal":
            return "pass", "WAL mode enabled"
        else:
            return "fail", f"WAL mode not enabled (current: {result[0] if result else 'None'})"
    except Exception as e:
        return "fail", f"WAL check error: {e}"


def check_stuck_tasks() -> Tuple[str, str]:
    """Check for tasks stuck in running status."""
    try:
        tasks = api.list_tasks(status="running")
        if not tasks:
            return "pass", "No stuck tasks"
        
        now = time.time()
        stuck_count = 0
        for task in tasks:
            run_at = float(task.get("run_at", 0))
            if now - run_at > 600:  # 10 minutes = 600 seconds
                stuck_count += 1
        
        if stuck_count == 0:
            return "pass", "No stuck tasks"
        else:
            return "warn", f"{stuck_count} task(s) stuck in running status"
    except Exception as e:
        return "fail", f"Stuck tasks check error: {e}"


def check_scheduler_healthy() -> Tuple[str, str]:
    """Check if APScheduler jobs table exists."""
    try:
        db_path = Path.home() / ".local" / "share" / "umbra" / "umbra.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apscheduler_jobs'")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return "pass", "APScheduler table exists"
        else:
            return "warn", "APScheduler table not found (may not be initialized yet)"
    except Exception as e:
        return "fail", f"Scheduler check error: {e}"


def check_log_file() -> Tuple[str, str]:
    """Check if log file exists and is writable."""
    try:
        if not SETTINGS.log_file.exists():
            return "warn", "Log file does not exist"
        
        # Test writability
        test_msg = "test"
        SETTINGS.log_file.write_text(test_msg, encoding="utf-8")
        SETTINGS.log_file.write_text("", encoding="utf-8")  # Clear test
        return "pass", "Log file exists and writable"
    except Exception as e:
        return "fail", f"Log file error: {e}"


def check_notify_send() -> Tuple[str, str]:
    """Check if notify-send is available."""
    if shutil.which("notify-send"):
        return "pass", "notify-send available"
    else:
        return "warn", "notify-send not found"


def check_xdg_open() -> Tuple[str, str]:
    """Check if xdg-open is available."""
    if shutil.which("xdg-open"):
        return "pass", "xdg-open available"
    else:
        return "warn", "xdg-open not found"


def check_systemd_service_installed() -> Tuple[str, str]:
    """Check if systemd user service is installed."""
    service_file = Path.home() / ".config" / "systemd" / "user" / "umbra.service"
    if service_file.exists():
        return "pass", "Systemd service file exists"
    else:
        return "warn", "Systemd service not installed"


def check_systemd_service_active() -> Tuple[str, str]:
    """Check if systemd user service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "umbra"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and "active" in result.stdout:
            return "pass", "Systemd service active"
        else:
            return "warn", "Systemd service not active"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return "warn", "systemctl not available"


def check_python_version() -> Tuple[str, str]:
    """Check Python version >= 3.10."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return "pass", f"Python {version.major}.{version.minor}.{version.micro}"
    else:
        return "fail", f"Python {version.major}.{version.minor}.{version.micro} (requires >= 3.10)"


def check_apscheduler_installed() -> Tuple[str, str]:
    """Check if APScheduler is installed."""
    try:
        import apscheduler
        return "pass", f"APScheduler {apscheduler.__version__} available"
    except ImportError:
        return "warn", "APScheduler not installed"


def check_textual_installed() -> Tuple[str, str]:
    """Check if Textual is installed."""
    try:
        import textual
        return "pass", f"Textual {textual.__version__} available"
    except ImportError:
        return "warn", "Textual not installed (needed for Phase 2 TUI)"


def run_doctor_checks() -> None:
    """Run all doctor checks and print results."""
    checks = [
        ("Daemon running", check_daemon_running),
        ("Database reachable", check_database_reachable),
        ("Database WAL mode", check_database_wal_mode),
        ("Stuck tasks", check_stuck_tasks),
        ("Scheduler healthy", check_scheduler_healthy),
        ("Log file exists and writable", check_log_file),
        ("notify-send installed", check_notify_send),
        ("xdg-open installed", check_xdg_open),
        ("systemd user service installed", check_systemd_service_installed),
        ("systemd user service active", check_systemd_service_active),
        ("Python version >= 3.10", check_python_version),
        ("APScheduler installed", check_apscheduler_installed),
        ("Textual installed", check_textual_installed),
    ]
    
    passed = 0
    failed = 0
    
    for name, check_func in checks:
        status, message = check_func()
        symbol = Colors.checkmark(status)
        print(f"{symbol} {name:<40} {message}")
        
        if status == "pass":
            passed += 1
        elif status == "fail":
            failed += 1
    
    total = passed + failed
    print(f"\n{passed} checks passed, {failed} failed.")
