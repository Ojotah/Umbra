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


def format_help_sections() -> str:
    sections = [
        (
            "Core Commands",
            [
                ("umbra help", "Show this help"),
                ("umbra add \"message\" in 10s", "Schedule a reminder task"),
                ("umbra workflow list", "List available workflows"),
                ("umbra workflow morning", "Schedule workflow task"),
            ],
        ),
        (
            "Task Management",
            [
                ("umbra list", "List all tasks"),
                ("umbra status", "Show task status summary"),
            ],
        ),
        (
            "System Commands",
            [
                ("umbra logs", "Show latest daemon logs (newest first)"),
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


def format_workflow_list(names: Sequence[str]) -> str:
    if not names:
        return "No workflows available."
    lines = ["Available workflows:"]
    lines.extend(f"- {name}" for name in names)
    return "\n".join(lines)

