"""
Umbra configuration.

V1 keeps configuration intentionally small and explicit. As the project grows
(daemon mode, persistence, AI, voice), prefer adding new config here rather than
spreading constants across modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application settings container."""

    app_name: str = "Umbra"
    storage_dir: Path = Path(__file__).resolve().parent.parent / "storage"
    tasks_file: Path = Path(__file__).resolve().parent.parent / "storage" / "tasks.json"
    logs_dir: Path = Path(__file__).resolve().parent.parent / "logs"
    log_file: Path = Path(__file__).resolve().parent.parent / "logs" / "umbra.log"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    workflows_file: Path = Path(__file__).resolve().parent.parent / "data" / "workflows.json"
    poll_interval_seconds: float = 1.0


SETTINGS = Settings()

