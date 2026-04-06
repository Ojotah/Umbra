"""
Workflow loader.

Loads workflow definitions from `data/workflows.json` and merges them over
registry defaults. Failures are handled safely; callers always receive a
dictionary and daemon execution can continue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from core.workflows.workflow_registry import WorkflowMap, default_workflows


def load_workflows(path: Path) -> WorkflowMap:
    """
    Load workflows from disk and merge with defaults.

    File workflows override defaults by key.
    """
    merged = default_workflows()
    data = _load_json_safe(path)
    for name, steps in data.items():
        if isinstance(name, str) and _is_step_list(steps):
            merged[name] = [str(s) for s in steps]
    return merged


def _load_json_safe(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return {}
        return obj
    except (OSError, json.JSONDecodeError):
        return {}


def _is_step_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)

