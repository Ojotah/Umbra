"""
CLI output formatting helpers.

Placed under `services` so editable installs that already include the services
package can import it reliably.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Iterable, Sequence


def short_id(task_id: str) -> str:
    return str(task_id)[:8]


def format_time(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def format_relative_time(timestamp: float, *, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    diff = float(timestamp) - float(now)
    abs_diff = abs(int(diff))

    if abs_diff < 60:
        value, unit = abs_diff, "second"
    elif abs_diff < 3600:
        value, unit = abs_diff // 60, "minute"
    elif abs_diff < 86400:
        value, unit = abs_diff // 3600, "hour"
    else:
        value, unit = abs_diff // 86400, "day"

    plural = "" if value == 1 else "s"
    if diff >= 0:
        return f"in {value} {unit}{plural}"
    return f"{value} {unit}{plural} ago"


def format_task_scheduled(*, task_id: str, run_at: float, message: str) -> str:
    relative = format_relative_time(run_at)
    if relative.endswith("ago"):
        runs_in = "now"
    else:
        runs_in = relative[3:] if relative.startswith("in ") else relative
    return (
        "✔ Task scheduled\n"
        f"ID: {short_id(task_id)}\n"
        f"Runs in: {runs_in}\n"
        f"Message: {message}"
    )


def format_task_table(tasks: Sequence[dict]) -> str:
    if not tasks:
        return "No tasks found."

    rows = []
    for t in tasks:
        run_at = float(t.get("run_at", 0))
        display_message = str(t.get("message") or t.get("action") or "")
        rows.append(
            {
                "ID": short_id(str(t.get("id", ""))),
                "Type": str(t.get("type", "")),
                "Message": display_message,
                "Status": str(t.get("status", "")),
                "Run time": f"{format_time(run_at)} ({format_relative_time(run_at)})",
            }
        )

    columns = ["ID", "Type", "Message", "Status", "Run time"]
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            widths[c] = max(widths[c], len(row[c]))

    def line(row: dict) -> str:
        return "  ".join(row[c].ljust(widths[c]) for c in columns)

    header = line({c: c for c in columns})
    divider = "  ".join("-" * widths[c] for c in columns)
    body = "\n".join(line(r) for r in rows)
    return f"{header}\n{divider}\n{body}"


def format_status_summary(tasks: Sequence[dict]) -> str:
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    for t in tasks:
        s = str(t.get("status", ""))
        if s in counts:
            counts[s] += 1

    total = len(tasks)
    return (
        "Umbra task status\n"
        f"- total:   {total}\n"
        f"- pending: {counts['pending']}\n"
        f"- running: {counts['running']}\n"
        f"- done:    {counts['done']}\n"
        f"- failed:  {counts['failed']}"
    )


def format_logs(lines: Iterable[str]) -> str:
    out: list[str] = []
    for line in lines:
        clean = line.rstrip("\n")
        if "[ERROR]" in clean:
            out.append(f"!! {clean}")
        else:
            out.append(f"   {clean}")
    return "\n".join(out) if out else "No logs available."


def format_task_show(task: dict) -> str:
    """Format detailed task information for the show command."""
    task_id = str(task.get("id", ""))
    task_type = str(task.get("type", ""))
    status = str(task.get("status", ""))
    run_at = float(task.get("run_at", 0))
    message = str(task.get("message", ""))
    
    lines = [
        f"Task: {short_id(task_id)}",
        f"Type: {task_type}",
        f"Status: {status}",
        f"Run at: {format_time(run_at)} ({format_relative_time(run_at)})",
        f"Message: {message}",
    ]
    
    # Show steps if it's a chain task with steps
    if task_type == "chain" and "steps" in task:
        lines.append("")
        lines.append("Steps:")
        steps = task.get("steps", [])
        for i, step in enumerate(steps, 1):
            action = str(step.get("action", ""))
            step_status = str(step.get("status", ""))
            error = step.get("error")
            
            # Status symbols
            if step_status == "done":
                symbol = "✅"
            elif step_status == "failed":
                symbol = "❌"
            elif step_status == "running":
                symbol = "⏳"
            else:
                symbol = "⏸️"
            
            step_line = f"{i}. {action.ljust(20)} {symbol}"
            if error:
                step_line += f" ({error})"
            lines.append(step_line)
    
    # Show error if task failed
    if status == "failed" and "error" in task:
        lines.append("")
        lines.append("Error:")
        lines.append(str(task.get("error", "")))
    
    return "\n".join(lines)


def format_help_sections() -> str:
    sections = [
        (
            "Core Commands",
            [
                ("umbra help", "Show this help"),
                ("umbra add \"message\" in 10s", "Schedule a reminder task"),
                ("umbra chain \"open vscode then open chrome\"", "Execute a command chain"),
            ],
        ),
        (
            "Task Management",
            [
                ("umbra list", "List all tasks"),
                ("umbra status", "Show task status summary"),
                ("umbra show <task_id>", "Show detailed task information"),
                ("umbra retry <task_id>", "Retry a failed task"),
            ],
        ),
        (
            "System Commands",
            [
                ("umbra logs", "Show latest daemon logs (newest first)"),
                ("umbra daemon status", "Check if daemon is running"),
                ("umbra daemon start", "Start the daemon"),
                ("umbra daemon stop", "Stop the daemon"),
            ],
        ),
    ]

    usage_width = max(len(u) for _, cmds in sections for u, _ in cmds)
    lines = ["Umbra CLI", ""]
    for title, cmds in sections:
        lines.append(f"{title}:")
        for usage, desc in cmds:
            lines.append(f"  {usage.ljust(usage_width)}  {desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
