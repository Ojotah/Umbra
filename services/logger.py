"""
Lightweight file logger.

Umbra intentionally avoids heavy frameworks. This logger provides:
- log levels (DEBUG/INFO/ERROR)
- append-only file output to `logs/umbra.log`
- best-effort behavior (logging must never crash the daemon)
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


Level = Literal["DEBUG", "INFO", "ERROR"]


@dataclass(frozen=True)
class Logger:
    """Simple file logger."""

    path: Path
    level: Level = "INFO"

    def debug(self, message: str) -> None:
        self._log("DEBUG", message)

    def info(self, message: str) -> None:
        self._log("INFO", message)

    def error(self, message: str) -> None:
        self._log("ERROR", message)
    
    def info_structured(self, *, task_id: str, event: str, action: str | None = None, error: str | None = None) -> None:
        """Log structured JSON line for task events."""
        log_entry = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "task_id": task_id,
            "event": event,
            "action": action,
            "error": error,
        }
        self._log_json("INFO", log_entry)
    
    def error_structured(self, *, task_id: str, event: str, action: str | None = None, error: str | None = None) -> None:
        """Log structured JSON line for task errors."""
        log_entry = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "task_id": task_id,
            "event": event,
            "action": action,
            "error": error,
        }
        self._log_json("ERROR", log_entry)
    
    def _log_json(self, level: Level, data: dict) -> None:
        """Write structured JSON log entry."""
        if not _should_log(self.level, level):
            return
        
        timestamp = _dt.datetime.now().isoformat(timespec="seconds")
        line = f"{timestamp} [{level}] {json.dumps(data)}\n"
        
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Logging must never crash the daemon.
            return

    def _log(self, level: Level, message: str) -> None:
        if not _should_log(self.level, level):
            return

        timestamp = _dt.datetime.now().isoformat(timespec="seconds")
        line = f"{timestamp} [{level}] {message}\n"

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Logging must never crash the daemon.
            return


def _should_log(min_level: Level, level: Level) -> bool:
    order = {"DEBUG": 10, "INFO": 20, "ERROR": 30}
    return order[level] >= order[min_level]

