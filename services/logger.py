"""
Structured JSON logger with rotation for Umbra.

Uses Python's built-in logging module with RotatingFileHandler.
All log entries are single-line JSON objects with standardized fields.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class UmbraLogger:
    """Structured JSON logger with rotation."""
    
    def __init__(self, log_file: Path, level: str = "INFO") -> None:
        self.log_file = log_file
        self.level = getattr(logging, level.upper(), logging.INFO)
        
        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup rotating file handler (5MB per file, keep 7 backups)
        self.handler = logging.handlers.RotatingFileHandler(
            filename=str(self.log_file),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=7,
            encoding='utf-8'
        )
        
        # Setup formatter for single-line JSON
        formatter = logging.Formatter('%(message)s')
        self.handler.setFormatter(formatter)
        
        # Setup logger
        self.logger = logging.getLogger('umbra')
        self.logger.setLevel(self.level)
        self.logger.addHandler(self.handler)
        
        # Also log to stderr when daemon runs in foreground
        if sys.stderr.isatty():
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def _write_log(self, level: str, event: str, **kwargs: Any) -> None:
        """Write a structured log entry."""
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": level,
            "event": event,
        }
        
        # Add optional fields
        for key, value in kwargs.items():
            if value is not None:
                log_entry[key] = value
        
        # Write as single line JSON
        try:
            self.logger.log(getattr(logging, level), json.dumps(log_entry, separators=(',', ':')))
        except Exception:
            # Fallback for JSON serialization errors
            fallback_entry = log_entry.copy()
            fallback_entry['msg'] = str(log_entry.get('msg', ''))
            fallback_entry.pop('extra', None)
            self.logger.log(getattr(logging, level), json.dumps(fallback_entry, separators=(',', ':')))


# Module-level logger instance
_log_instance: Optional[UmbraLogger] = None


def init_logger(log_file: Path, level: str = "INFO") -> UmbraLogger:
    """Initialize the global logger instance."""
    global _log_instance
    if _log_instance is None:
        _log_instance = UmbraLogger(log_file, level)
    return _log_instance


def log(event: str, **kwargs: Any) -> None:
    """Module-level logger callable."""
    global _log_instance
    if _log_instance is None:
        # Initialize with default settings if not already done
        from config.settings import SETTINGS
        init_logger(SETTINGS.log_file, "INFO")
    
    # Determine log level from event name
    level = "INFO"
    if event.startswith("task_error") or event.startswith("step_error") or event.startswith("daemon_error"):
        level = "ERROR"
    elif event.startswith("debug"):
        level = "DEBUG"
    
    _log_instance._write_log(level, event, **kwargs)


# Legacy compatibility wrapper
class Logger:
    """Legacy Logger wrapper for backward compatibility."""
    
    def __init__(self, path: Path, level: str = "INFO") -> None:
        # Initialize the new logger
        init_logger(path, level)
        self.path = path
        self.level = level
    
    def debug(self, message: str) -> None:
        log("debug", msg=message)
    
    def info(self, message: str) -> None:
        log("info", msg=message)
    
    def error(self, message: str) -> None:
        log("error", msg=message)
    
    def info_structured(self, *, task_id: str, event: str, action: str | None = None, error: str | None = None) -> None:
        log(event, task_id=task_id, action=action, error=error, msg=f"Task {event}")
    
    def error_structured(self, *, task_id: str, event: str, action: str | None = None, error: str | None = None) -> None:
        log("task_error", task_id=task_id, event=event, action=action, error=error, msg=f"Task {event}")
