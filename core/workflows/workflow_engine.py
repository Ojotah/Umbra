"""
Workflow engine.

Expands declarative workflow steps into executable system actions through the
dispatcher layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from config.settings import SETTINGS
from core.workflows.workflow_loader import load_workflows


@dataclass(frozen=True)
class StepResult:
    action: str
    success: bool
    detail: str


def run_workflow(name: str, *, workflows_file: Path | None = None) -> Dict[str, Any]:
    """
    Run a workflow by name and return execution summary.

    Each step is dispatched as a system action; step failures are isolated and
    do not abort the whole workflow.
    """
    workflows_file = workflows_file or SETTINGS.workflows_file
    workflows = load_workflows(workflows_file)
    if name not in workflows:
        raise ValueError(f"Workflow not found: {name}")

    actions = workflows[name]
    results: List[Dict[str, Any]] = []
    success = 0
    failed = 0

    # Local import avoids circular dependency (dispatcher -> workflow_engine).
    from services.dispatcher import dispatch_system_action

    for action in actions:
        try:
            res = dispatch_system_action(action)
            ok = bool(res.get("success"))
            if ok:
                success += 1
            else:
                failed += 1
            results.append({"action": action, "success": ok, "result": res})
        except Exception as e:  # noqa: BLE001 - step isolation by design
            failed += 1
            results.append({"action": action, "success": False, "error": str(e)})

    return {
        "workflow": name,
        "total_steps": len(actions),
        "success": success,
        "failed": failed,
        "results": results,
    }

