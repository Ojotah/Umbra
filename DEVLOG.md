## 2026-04-06 — Project initialized

- **Setup**: Created a Python-first repository layout with a CLI entry point (`main.py`) and a background runner (`daemon.py`).
- **Core architecture**:
  - `core/`: pure parsing + domain logic (no I/O), starting with `core/parser.py`
  - `commands/`: intent handlers, starting with `commands/remind.py`
  - `services/`: replaceable side-effect boundaries, starting with `services/scheduler.py` and `services/notifier.py`
  - `storage/`: persistence layer, starting with JSON-backed `storage/task_store.py` and `storage/tasks.json`
  - `config/`: centralized settings in `config/settings.py`
- **Why modular design**:
  - Keeps parsing, scheduling, persistence, and notification concerns independent and testable
  - Makes it easy to extend later (daemon improvements, WhatsApp via Selenium, workflows, AI/NLP) without rewriting the core flow
  - Keeps side effects (disk writes, subprocess calls) behind small interfaces so they can be mocked in tests

## 2026-04-06 — CLI + UX improvements

- **CLI refactor (argparse)**:
  - Added a proper argparse-based CLI with `--help`, positional command text, and `--list-commands`.
  - Why argparse: standardized UX, consistent help output, and an easy place to add flags as Umbra grows.
- **Command discovery/help**:
  - Introduced a command registry in `commands/__init__.py`.
  - Each command module exposes `NAME`, `DESCRIPTION`, and `EXAMPLES` for discovery and future docs.
- **User-friendly output**:
  - Reminder scheduling output is now human-readable (e.g., “Reminder set… in 1 minute 30 seconds”).
  - Internal task IDs remain in JSON for persistence, but are intentionally hidden from the CLI output.
- **Scheduler abstraction**:
  - Scheduler interface now supports passing `*args`/`**kwargs` to callbacks (`Scheduler.schedule(...)`).
  - This makes future replacements (APScheduler/systemd timers) easier without changing call sites.

## 2026-04-06 — Daemon architecture introduction

- **Why a daemon**:
  - Reminders must fire even after the CLI exits, so execution moved into a long-running process.
  - The CLI is now fast and non-blocking: it only parses input and persists tasks.
- **New execution flow**:
  - CLI: user input → parse → build standardized task dict → append to `storage/tasks.json` → exit
  - Daemon: poll tasks (1s) → claim due tasks → execute → remove (or re-add on failure)
- **Separation of responsibilities**:
  - `main.py`: task creation + UX output only (no `sleep`, no scheduling threads)
  - `daemon.py`: task execution + retries + notifications
- **Persistence enables background execution**:
  - Tasks live in JSON, so daemon restarts are safe: it reloads pending tasks on boot.
- **Task schema standardization**:
  - Tasks were normalized to a simple dict schema: `id`, `type`, `message`, `run_at`, `created_at`.
  - Storage includes lightweight legacy migration for older task entries.
- **Tradeoffs**:
  - Uses simple polling (1s) instead of an event-driven system; polling is easy to reason about and dependency-free.
  - To avoid double execution across restarts, the daemon *claims* a due task by removing it before executing.
    If execution fails, the task is re-added with a short delay for retry.

## 2026-04-06 — Initial production commit

### What was done
- Prepared repository for first production-grade commit
- Added `.gitignore` for Python and system safety
- Cleaned runtime artifacts from version control
- Structured repository for maintainability

### Why this was done
- To ensure clean separation between runtime data and source code
- To prepare Umbra for public or portfolio usage
- To follow standard software engineering practices

### How it works
- Git tracks only source files
- Runtime state (`storage/tasks.json`) is excluded via `.gitignore`
- Only deterministic code is version controlled

### Outcome
- Clean initial commit ready for collaboration or deployment

