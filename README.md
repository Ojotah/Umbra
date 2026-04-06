# Umbra

Umbra is a Python-based automation assistant for Ubuntu with a daemon-first architecture.

Core idea:
- **CLI** (`umbra ...`) creates or inspects tasks
- **Daemon** (`python3 daemon.py`) executes due tasks in the background
- **Storage** (`storage/tasks.json`) persists task state safely

Umbra currently supports:
- Reminder tasks
- Workflow tasks (multi-step system actions)
- Task visibility commands (`list`, `status`, `logs`)
- Safe task lifecycle (`pending`, `running`, `done`, `failed`)

## Install and run

### 1) Install CLI (editable mode)

From the project root:

```bash
pip install -e .
```

### 2) Start the daemon

```bash
python3 daemon.py
```

Keep this running in a terminal.

### 3) Use CLI in another terminal

```bash
umbra help
```

## Architecture and flow

### CLI flow
1. Parse command input
2. Build task payload
3. Save task to `storage/tasks.json`
4. Exit immediately

### Daemon flow
1. Load tasks from storage
2. Select due `pending` tasks
3. Mark task `running`
4. Dispatch task by type (`remind`, `system`, `workflow`)
5. Mark task `done` or `failed`
6. Continue loop safely

## Task model

Each task has structured state:

```json
{
  "id": "uuid",
  "type": "remind | system | workflow",
  "run_at": 1712345678.0,
  "status": "pending | running | done | failed",
  "created_at": 1712345600.0
}
```

`remind` tasks include `message`; `system` and `workflow` tasks use `action`.

## Commands (full guide)

### `umbra help`
**What it does**  
Shows grouped command help with usage examples.

**Usage**
```bash
umbra help
```

---

### `umbra add "message" in <duration>`
**What it does**  
Creates a reminder task for daemon execution.

**Supported duration formats**
- `10s`, `30sec`, `45 seconds`
- `5m`, `2min`, `10 minutes`
- `1h`, `2hr`, `3 hours`

**Usage**
```bash
umbra add "drink water" in 10m
umbra add "stand up" in 45s
```

**Result**
- Task is stored with status `pending`
- Daemon executes at due time
- CLI prints:
  - short task ID
  - relative run time
  - message

---

### `umbra list`
**What it does**  
Shows all tasks in a readable table.

**Displayed columns**
- Short ID (first 8 chars)
- Type
- Message/action
- Status
- Run time (absolute + relative)

**Usage**
```bash
umbra list
```

---

### `umbra status`
**What it does**  
Shows task counts by lifecycle state.

**Displayed counts**
- total
- pending
- running
- done
- failed

**Usage**
```bash
umbra status
```

---

### `umbra logs`
**What it does**  
Shows latest daemon log lines (newest first, up to 50 lines).

**Formatting**
- `ERROR` entries are highlighted
- intended for quick diagnostics

**Usage**
```bash
umbra logs
```

---

### `umbra workflow list`
**What it does**  
Lists available workflow names from:
- built-in defaults
- `data/workflows.json`

**Usage**
```bash
umbra workflow list
```

---

### `umbra workflow <name>`
**What it does**  
Schedules a workflow task for daemon execution.

The daemon expands workflow steps and dispatches each step through the system dispatcher and whitelist-based system executor.

**Usage**
```bash
umbra workflow morning
umbra workflow dev_mode
```

---

### Backward-compatible natural language command
Umbra still supports:

```bash
umbra "remind me in 10 seconds test"
```

This maps to a reminder task creation path.

## Features and how to use them

### Reminder feature
- Create reminder tasks with `umbra add ...`
- Run daemon continuously
- Receive Linux notifications at due time

### Workflow feature
- Define workflows in `data/workflows.json`
- List workflows with `umbra workflow list`
- Schedule one with `umbra workflow <name>`
- Daemon executes steps through dispatcher + whitelist

### Observability feature
- Use `umbra status` for quick health snapshot
- Use `umbra list` for detailed task view
- Use `umbra logs` for daemon activity and errors

### Safety and reliability feature
- Atomic storage writes
- Task status lifecycle prevents duplicate execution
- Per-task error isolation keeps daemon alive on failures

## Workflow file format

`data/workflows.json`:

```json
{
  "morning": ["open_vscode", "open_chrome", "volume_up"],
  "dev_mode": ["open_vscode", "open_chrome"]
}
```

Each entry is declarative: workflow name -> list of action names.

## Linux requirements

Install desktop notification dependency:

```bash
sudo apt install libnotify-bin
```

Optional for some system actions:
- `google-chrome`
- `code` (VS Code CLI)
- `amixer`/PulseAudio-compatible volume tools

## Troubleshooting

- **`umbra` command not found**
  - run `pip install -e .` again in project root

- **Task created but nothing happens**
  - ensure `python3 daemon.py` is running
  - check `umbra logs`

- **Notification not shown**
  - install `libnotify-bin`
  - verify desktop session supports notifications

