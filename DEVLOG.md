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

## 2026-04-06 — Phase A — Stability upgrade

- **Why the polling loop was refactored**:
  - The daemon loop was reorganized into explicit steps (load → due → running → execute → done/failed → sleep) to reduce accidental complexity and improve correctness.
  - Each cycle now accounts for time spent executing tasks to avoid CPU waste.
- **Why task states were introduced**:
  - Tasks now carry a `status`: `pending | running | done | failed`.
  - The daemon sets `running` before execution and `done/failed` afterward so tasks do not execute twice.
- **Why logging was added**:
  - A small file logger writes to `logs/umbra.log` and records daemon lifecycle, task execution, failures, and storage errors.
  - Logging is best-effort and never crashes the daemon.
- **Why atomic storage writes matter**:
  - JSON writes are atomic (temp file + replace) to avoid corrupting `tasks.json`.
  - File locking is used to reduce races between CLI writers and the daemon.
- **Crash safety**:
  - Exceptions are caught per task and per cycle; the daemon continues running.
  - On restart, tasks in `running` state are not re-executed, preventing duplicates.

Execution lifecycle (diagram):

CLI → parse → task(`pending`) → storage  
Daemon → load → due(`pending`) → mark `running` → execute → mark `done/failed` → prune `done`

## 2026-04-06 — Phase B — UX Polish

- **Why CLI output was redesigned**:
  - Added structured command surfaces (`help`, `add`, `list`, `status`, `logs`) so daily usage is predictable and easier to scan.
  - Replaced terse single-line outputs with consistent, multi-line summaries for scheduling confirmation.
- **Why human-readable time formatting matters**:
  - Added `format_time()` and `format_relative_time()` so users see phrases like “in 2 minutes” instead of raw timestamps.
  - List views now include both absolute and relative run times for faster decision-making.
- **Why formatting/logic separation improves maintainability**:
  - Moved presentation code into `utils/formatter.py` and kept command behavior in `commands/cli_tasks.py`.
  - This keeps CLI UX changes isolated from storage and daemon logic.
- **Why a structured help system was introduced**:
  - Added `umbra help` with grouped sections (Core Commands, Task Management, System Commands).
  - Command usage and short descriptions are aligned for readability.

