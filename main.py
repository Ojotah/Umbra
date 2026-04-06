"""
Umbra CLI entry point.

V1 supports a single command:
    umbra "remind me in 10 seconds test"

This module coordinates:
- argument parsing (CLI plumbing)
- command parsing (domain parsing in `core.parser`)
- dispatch to the appropriate command module (e.g., `commands.remind`)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
import time

from commands import format_command_list, list_commands
from commands.remind import ReminderRequest, build_reminder_task
from config.settings import SETTINGS
from core.parser import ParseError, parse
from storage.task_store import StorageError, add_task


def _humanize_seconds(seconds: int) -> str:
    """
    Convert a duration (seconds) into a human-friendly phrase.

    Examples:
        1 -> "1 second"
        60 -> "1 minute"
        90 -> "1 minute 30 seconds"
    """
    if seconds < 0:
        return f"{seconds} seconds"
    if seconds == 0:
        return "0 seconds"

    parts: list[str] = []
    remaining = seconds

    hours = remaining // 3600
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
        remaining %= 3600

    minutes = remaining // 60
    if minutes:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
        remaining %= 60

    if remaining:
        parts.append(f"{remaining} second" + ("s" if remaining != 1 else ""))

    return " ".join(parts)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="umbra",
        description="Umbra is a small automation assistant for Ubuntu (daemon-based reminders).",
        epilog=(
            "Examples:\n"
            '  umbra "remind me in 10 seconds stretch"\n'
            '  umbra --list-commands\n'
            "Tip: Run the background daemon with: python3 daemon.py\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "text",
        nargs="?",
        help='Command text, e.g. "remind me in 10 seconds test"',
    )
    p.add_argument(
        # kept for backward compatibility; now the default behavior
        "--no-foreground-schedule",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "--list-commands",
        action="store_true",
        help="List available commands and examples.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.list_commands:
        print(format_command_list(list_commands()), end="")
        return 0

    if not args.text:
        print('Run `umbra --help` or try: umbra "remind me in 10 seconds test"', file=sys.stderr)
        return 2

    try:
        cmd = parse(args.text)
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 2

    if cmd.intent == "remind":
        if cmd.delay_seconds is None:
            print("Reminder requires a delay (e.g., 'in 10 seconds').", file=sys.stderr)
            return 2

        task = build_reminder_task(ReminderRequest(delay_seconds=cmd.delay_seconds, message=cmd.message))
        try:
            add_task(SETTINGS.tasks_file, task)
        except StorageError as e:
            print(f"Failed to save task: {e}", file=sys.stderr)
            return 1

        run_at = _dt.datetime.fromtimestamp(float(task["run_at"])).strftime("%H:%M:%S")
        print(f"\u23f3 Task scheduled: \"{cmd.message}\" at {run_at} (in {_humanize_seconds(cmd.delay_seconds)})")
        print("It will be executed by the Umbra daemon.")
        return 0

    print(f"Unsupported intent: {cmd.intent}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

