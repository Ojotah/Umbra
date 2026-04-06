"""Umbra CLI entry point."""

from __future__ import annotations

import argparse
import sys

from commands.cli_tasks import (
    list_workflow_names,
    parse_duration_to_seconds,
    read_logs,
    schedule_task,
    schedule_workflow_task,
    status_counts,
)
from commands.cli_tasks import list_tasks as list_tasks_cmd
from config.settings import SETTINGS
from core.parser import ParseError, parse
from services.formatter import (
    format_help_sections,
    format_logs,
    format_status_summary,
    format_task_scheduled,
    format_task_table,
    format_workflow_list,
)
from storage.task_store import StorageError


def build_arg_parser() -> argparse.ArgumentParser:
    """Build Umbra CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="umbra",
        description="Umbra CLI (daemon-based task scheduler).",
        add_help=True,
    )
    sub = p.add_subparsers(dest="command")

    sub.add_parser("help", help="Show structured Umbra help.")

    p_add = sub.add_parser("add", help='Add a reminder task. Example: umbra add "test" in 10s')
    p_add.add_argument("message", help="Reminder message.")
    p_add.add_argument("in_kw", nargs="?", default="in", help=argparse.SUPPRESS)
    p_add.add_argument("duration", nargs="?", help="Duration token like 10s, 5m, 1h.")

    sub.add_parser("list", help="List all tasks.")
    sub.add_parser("status", help="Show task status summary.")
    sub.add_parser("logs", help="Show newest daemon logs.")
    p_workflow = sub.add_parser("workflow", help="Workflow commands.")
    p_workflow.add_argument("target", nargs="?", default="list", help='Workflow name or "list".')

    # Backward-compatible natural language input:
    # umbra "remind me in 10 seconds test"
    p.add_argument("text", nargs="?", help=argparse.SUPPRESS)
    p.add_argument("extra", nargs="*", help=argparse.SUPPRESS)
    p.add_argument("--list-commands", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv: list[str] | None = None) -> int:
    """Run Umbra CLI and return process exit code."""
    args = build_arg_parser().parse_args(argv)

    if args.list_commands or args.command == "help":
        print(format_help_sections(), end="")
        return 0

    if args.command == "add":
        duration_token = _resolve_duration_token(args.in_kw, args.duration)
        if duration_token is None:
            print('Usage: umbra add "message" in 10s', file=sys.stderr)
            return 2
        try:
            delay_seconds = parse_duration_to_seconds(duration_token)
            task = schedule_task(SETTINGS.tasks_file, message=args.message, delay_seconds=delay_seconds)
        except (ValueError, StorageError) as e:
            print(str(e), file=sys.stderr)
            return 2
        print(
            format_task_scheduled(
                task_id=str(task["id"]),
                run_at=float(task["run_at"]),
                message=str(task["message"]),
            )
        )
        return 0

    if args.command == "list":
        try:
            tasks = list_tasks_cmd(SETTINGS.tasks_file)
        except StorageError as e:
            print(f"Failed to load tasks: {e}", file=sys.stderr)
            return 1
        print(format_task_table(tasks))
        return 0

    if args.command == "status":
        try:
            tasks = status_counts(SETTINGS.tasks_file)
        except StorageError as e:
            print(f"Failed to load tasks: {e}", file=sys.stderr)
            return 1
        print(format_status_summary(tasks))
        return 0

    if args.command == "logs":
        try:
            lines = read_logs(SETTINGS.log_file, limit=50)
        except StorageError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(format_logs(lines))
        return 0

    if args.command == "workflow":
        target = str(args.target).strip()
        if target.lower() == "list":
            names = list_workflow_names(SETTINGS.workflows_file)
            print(format_workflow_list(names))
            return 0

        try:
            available = set(list_workflow_names(SETTINGS.workflows_file))
            if target not in available:
                print(f"Unknown workflow: {target}", file=sys.stderr)
                return 2
            task = schedule_workflow_task(SETTINGS.tasks_file, workflow_name=target)
        except StorageError as e:
            print(str(e), file=sys.stderr)
            return 1

        print(
            format_task_scheduled(
                task_id=str(task["id"]),
                run_at=float(task["run_at"]),
                message=f"workflow:{target}",
            )
        )
        return 0

    # Backward-compatible natural language path
    natural_text = _build_natural_text(args.text, args.extra)
    if natural_text:
        return _handle_natural_text(natural_text)

    print(format_help_sections(), end="")
    return 0


def _resolve_duration_token(in_kw: str | None, duration: str | None) -> str | None:
    if duration is not None:
        if in_kw and in_kw.lower() != "in":
            return None
        return duration
    if in_kw and in_kw.lower() != "in":
        return in_kw
    return None


def _build_natural_text(text: str | None, extra: list[str]) -> str | None:
    if text is None:
        return None
    parts = [text] + list(extra)
    return " ".join(parts).strip() or None


def _handle_natural_text(text: str) -> int:
    try:
        cmd = parse(text)
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 2

    if cmd.intent != "remind" or cmd.delay_seconds is None:
        print(f"Unsupported intent: {cmd.intent}", file=sys.stderr)
        return 2

    try:
        task = schedule_task(SETTINGS.tasks_file, message=cmd.message, delay_seconds=cmd.delay_seconds)
    except (ValueError, StorageError) as e:
        print(str(e), file=sys.stderr)
        return 1

    print(
        format_task_scheduled(
            task_id=str(task["id"]),
            run_at=float(task["run_at"]),
            message=str(task["message"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

