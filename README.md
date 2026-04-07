# Umbra v2 - Production-Ready Local Automation

Umbra is a Python-based automation assistant for Ubuntu with a daemon-first architecture. It provides reliable task scheduling, chain execution, and comprehensive observability.

## 🚀 What's New in v2

### Enhanced Observability
- **Task Inspection** - `umbra show <task_id>` for detailed task information
- **Structured Logging** - JSON-formatted logs for better debugging and monitoring
- **Step-by-Step Tracking** - Individual action status with progress indicators

### Improved Reliability
- **Persistent Chain Execution** - Step state survives daemon crashes
- **Retry Functionality** - `umbra retry <task_id>` for failed tasks
- **Atomic Storage Operations** - Prevents data corruption

### Better Execution Safety
- **Command Pre-Validation** - Checks if commands exist before execution
- **Execution Timeout** - 10-second timeout prevents hanging processes
- **Enhanced Error Handling** - Graceful failure handling without daemon crashes

### Enhanced Debuggability
- **Dry Run Mode** - `umbra chain "command" --dry-run` for execution planning
- **Robust Parser** - Handles filler words and complex separators
- **Daemon Control** - Start, stop, and check daemon status
- **Dynamic App Execution** - Open ANY installed application without manual configuration

## 🏗️ Architecture

### Core Components
- **CLI** (`umbra ...`) creates, inspects, and manages tasks
- **Daemon** (`python3 daemon.py`) executes due tasks in background
- **Storage** (`storage/tasks.json`) persists task state safely
- **Chain Engine** (`core/chains/`) parses and executes action sequences
- **System Executor** (`services/system_executor.py`) executes whitelisted and dynamic actions safely
- **Action Manager** (`services/action_manager.py`) handles dynamic app detection and security

### Task Types
- **Reminder tasks** - Desktop notifications at scheduled time
- **System tasks** - Single whitelisted system actions
- **Chain tasks** - Multi-step action sequences with natural language parsing and dynamic app support

### Task Model
```json
{
  "id": "uuid",
  "type": "remind | system | chain",
  "status": "pending | running | done | failed",
  "run_at": 1712345678.0,
  "created_at": 1712345600.0,
  "message": "task description",
  "action": "command or action",
  "steps": [                    // Chain tasks only
    {
      "action": "open_vscode",
      "status": "pending | running | done | failed",
      "error": null
    }
  ]
}
```

## 📦 Installation and Setup

### 1) Install CLI (editable mode)

From the project root:

```bash
pip install -e .
```

### 3) Use CLI in another terminal
```bash
umbra help
```

## 🎯 Commands (Complete Guide)

### Task Management

#### `umbra add "message" in <duration>`
**What it does**  
Creates a reminder task for daemon execution.

**Supported duration formats**
- `10s`, `30sec`, `45 seconds`
- `5m`, `2min`, `10 minutes`
- `1h`, `2hr`, `3 hours`

**Usage examples**
```bash
umbra add "drink water" in 10m
umbra add "stand up" in 45s
umbra add "meeting reminder" in 1h
```

#### `umbra show <task_id>`
**What it does**  
Shows detailed task information with step-by-step progress.

**Display information**
- Task ID, type, status
- Run time and message
- Step details (for chain tasks)
- Error information (for failed tasks)

**Usage examples**
```bash
umbra show abc12345
umbra show 6a76af08-5674-42ff-a67f-da2fe6daaaaa
```

**Status symbols**
- ✅ Step completed successfully
- ❌ Step failed with error
- ⏳ Step currently running
- ⏸️ Step pending

#### `umbra retry <task_id>`
**What it does**  
Clones a failed task with a new ID and resets all steps to pending.

**Behavior**
- Creates new task with original configuration
- Resets all chain steps to `pending` status
- Schedules immediate execution (1-second delay)
- Original task remains in logs for reference

**Usage examples**
```bash
umbra retry abc12345
umbra retry 6a76af08-5674-42ff-a67f-da2fe6daaaaa
```

#### `umbra list`
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

#### `umbra status`
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

### Chain Commands

#### `umbra chain "command sequence"`
**What it does**  
Creates a chain task for executing multiple system actions sequentially.

**Supported separators**
- `then` - sequential execution
- `and` - sequential execution  
- `,` - sequential execution

**Natural language parsing**
The chain engine converts natural language to actions with both static and dynamic support:

**Static Actions (Traditional)**
- `"open vscode"` → `"open_vscode"`
- `"open chrome"` → `"open_chrome"`
- `"open vim"` → `"open_vim"`
- `"volume up"` → `"volume_up"`
- `"volume down"` → `"volume_down"`
- `"lock screen"` → `"lock_screen"`

**Dynamic Application Support (NEW)**
- `"open firefox"` → `"dynamic_app:firefox"`
- `"launch spotify"` → `"dynamic_app:spotify"`
- `"start calculator"` → `"dynamic_app:calculator"`
- `"open terminal"` → `"dynamic_app:terminal"`

**Supported Dynamic Patterns**
- `open <app_name>` - Opens any installed application
- `launch <app_name>` - Alternative syntax for opening apps
- `start <app_name>` - Another alternative for opening apps

**Filler words ignored**
- `please`, `maybe`

**Compound separator**
- `and then` (takes precedence over individual `and` and `then`)

**Usage examples**
```bash
umbra chain "open vscode then open chrome"
umbra chain "please open vscode and maybe open vim"
umbra chain "open vscode, open chrome and volume_up"
umbra chain "open vscode and then open chrome"

# Dynamic app examples (NEW)
umbra chain "open firefox then launch spotify"
umbra chain "start calculator, open terminal, open chrome"
umbra chain "open firefox and volume_up"
```

#### `umbra chain "command" --dry-run`
**What it does**  
Shows execution plan without executing commands.

**Benefits**
- Validate parsing and action normalization
- Check which actions are valid
- Preview execution sequence
- No system changes

**Usage examples**
```bash
umbra chain "open vscode then open chrome" --dry-run
umbra chain "please open vscode and open vim" --dry-run
```

**Example output**
```
Plan:
1. open_vscode
2. open_chrome
```

### System Commands

#### `umbra daemon status`
**What it does**  
Checks if the Umbra daemon is running.

**Output**
- Shows "Daemon is running (PID: 12345)" if active
- Shows "Daemon is not running" if stopped

**Usage**
```bash
umbra daemon status
```

#### `umbra daemon start`
**What it does**  
Starts the Umbra daemon in the background.

**Behavior**
- Starts daemon as background process
- Detaches from terminal
- Returns success/failure message

**Usage**
```bash
umbra daemon start
```

#### `umbra daemon stop`
**What it does**  
Stops a running Umbra daemon gracefully.

**Behavior**
- Attempts graceful shutdown (SIGTERM)
- Falls back to force kill (SIGKILL) if needed
- Returns success/failure message

**Usage**
```bash
umbra daemon stop
```

#### `umbra logs`
**What it does**  
Shows latest daemon log lines (newest first, up to 50 lines).

**Log formats**
- **Traditional**: `timestamp [LEVEL] message`
- **Structured**: `timestamp [LEVEL] {"json": "data"}`

**Log events**
- `step_started` - Action execution began
- `step_done` - Action completed successfully
- `step_failed` - Action failed with error

**Formatting**
- `ERROR` entries are highlighted
- Intended for quick diagnostics

**Usage**
```bash
umbra logs
```

### Help Command

#### `umbra help`
**What it does**  
Shows grouped command help with usage examples.

**Usage**
```bash
umbra help
```

### Backward Compatibility

#### Natural Language Reminder
Umbra still supports the original natural language format:

```bash
umbra "remind me in 10 seconds test"
```

This maps to a reminder task creation path.

## 🔒 Security Model

### Whitelist Enforcement
- Only predefined actions can execute
- No arbitrary command execution
- All actions go through system executor

### Available Actions
- `open_vscode` - Launch VS Code (`code`)
- `open_chrome` - Launch Google Chrome (`google-chrome`)
- `open_vim` - Launch Vim (`vim`)
- `volume_up` - Increase system volume by 5% (`amixer`)
- `volume_down` - Decrease system volume by 5% (`amixer`)
- `lock_screen` - Lock current session (`loginctl`)

### Pre-Validation
- Commands checked with `shutil.which()` before execution
- Clear error messages for missing commands
- Prevents "No such file or directory" errors

### Execution Safety
- 10-second timeout on all system actions
- Process isolation prevents hanging
- Atomic storage writes prevent corruption

## 📋 Chain Execution Examples

### Development Workflow
```bash
umbra chain "open vscode then open chrome"
```
This launches VS Code and Chrome sequentially.

### Session Management
```bash
umbra chain "volume_down and lock_screen"
```
This lowers volume and locks the screen.

### Multiple Applications
```bash
umbra chain "open vscode, open chrome, volume_up"
```
This launches both apps and increases volume.

### Dry Run Planning
```bash
umbra chain "open vscode then open chrome" --dry-run
```
Shows execution plan without running commands.

## 🔧 Troubleshooting

### Common Issues

#### `umbra` command not found
```bash
pip install -e .
```

#### Task created but nothing happens
```bash
python3 daemon.py  # Ensure daemon is running
umbra logs          # Check for errors
```

#### Notification not shown
```bash
sudo apt install libnotify-bin  # Install notification support
```

#### Chain step fails
```bash
umbra show <task_id>  # Check step status and errors
umbra logs             # Review structured logs
```

#### Daemon won't start
```bash
pkill -f "python.*daemon.py"  # Kill existing daemon
python3 daemon.py           # Start fresh
```

## 🖥️ Linux Requirements

### Required Dependencies
```bash
sudo apt install libnotify-bin  # Desktop notifications
```

### Optional for Actions
- `google-chrome` - Web browser
- `code` - VS Code CLI
- `amixer`/PulseAudio - Volume control

## 🏗️ Development Notes

### Chain Engine Architecture
The chain system replaces static workflows with dynamic natural language parsing:

1. **Parsing**: Natural language → action list using separators
2. **Normalization**: Text → whitelisted action names
3. **Execution**: Sequential dispatch through system executor
4. **Error handling**: Per-step isolation with detailed reporting

### Security Model
- **Static Actions**: Only pre-approved system commands can execute
- **Dynamic Apps**: Sanitized app names with multiple execution methods
- **No Shell Execution**: All commands use list-based subprocess (no shell=True)
- **Input Sanitization**: Blocks dangerous characters (`; & | ` $ ( ) < > " '` )
- **Length Limits**: Maximum 50 characters for app names
- **Fallback Methods**: Tries `xdg-open`, `gtk-launch`, and direct execution

### Configuration
- **JSON-based**: `config/actions.json` for easy customization  
- **Runtime Loading**: Changes apply without daemon restart
- **Desktop Scanning**: Auto-discovers installed applications
- **Backward Compatible**: All existing workflows preserved

### Storage Safety
- Atomic file operations prevent corruption
- Task status lifecycle prevents duplicates
- Step-by-step persistence survives crashes
- JSON schema validation ensures consistency

## 📊 Monitoring and Observability

### Task Lifecycle
1. `pending` - Scheduled, waiting for execution
2. `running` - Currently executing
3. `done` - Completed successfully
4. `failed` - Failed with error details

### Structured Logging Format
```json
{
  "timestamp": "2026-04-07T05:04:28",
  "task_id": "abc12345",
  "event": "step_started | step_done | step_failed",
  "action": "open_vscode",
  "error": null | "error message"
}
```

### Log Analysis
```bash
# View recent logs
umbra logs

# Watch logs in real-time
tail -f logs/umbra.log

# Filter for errors
grep "ERROR" logs/umbra.log

# Filter for specific task
grep "abc12345" logs/umbra.log
```

## ⚙️ Configuration

### Actions Configuration
Umbra uses `config/actions.json` for dynamic action management:

```json
{
  "static_actions": {
    "volume_up": ["amixer", "sset", "Master", "10%+"],
    "lock_screen": ["loginctl", "lock-session"]
  },
  "natural_language_mappings": {
    "volume up": "volume_up",
    "lock screen": "lock_screen"
  },
  "dynamic_app_patterns": ["open", "launch", "start"],
  "security": {
    "blocked_chars": [";", "&", "|", "`", "$", "(", ")", "<", ">", "\"", "'"],
    "max_app_name_length": 50
  },
  "desktop_scan": {
    "enabled": true,
    "paths": ["/usr/share/applications", "~/.local/share/applications"]
  }
}
```

### Customizing Actions
1. **Add Static Actions**: Edit `static_actions` object
2. **Add Natural Language**: Update `natural_language_mappings` 
3. **Modify Security**: Adjust `blocked_chars` and limits
4. **Disable Scanning**: Set `desktop_scan.enabled: false`

### Dynamic App Discovery
Automatically scans desktop application directories for installed apps. Discovered apps become available as:
- `open <app_name>` 
- `launch <app_name>`
- `start <app_name>`

---

**Umbra v2** is now production-ready with comprehensive observability, reliability, and safety features for local automation tasks.
