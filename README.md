# Umbra

Umbra is a Python-based automation assistant for Ubuntu. **V1 focuses on smart reminders** (time-based), implemented with a **daemon-based architecture**:

- **CLI** (`umbra ...`) parses input and **writes tasks** to JSON
- **Daemon** runs continuously and **executes due tasks** (notifications)

## Quickstart (no install)

Start the daemon (in one terminal):

```bash
python3 daemon.py
```

Schedule a reminder (in another terminal):

```bash
python3 main.py "remind me in 10 seconds test"
```

List available commands:

```bash
python3 main.py --list-commands
```

## Architecture (V1)

- **CLI flow**: input → `core/parser.py` → build task → `storage/tasks.json` → exit
- **Daemon flow**: load tasks → claim due tasks → execute → remove (or re-add on failure)

## Install as a real CLI (`umbra`)

From the repo root:

```bash
pip install -e .
```

Then:

```bash
umbra --help
umbra --list-commands
umbra "remind me in 10 seconds test"
```

Run the daemon:

```bash
python3 daemon.py
```

## Notes

- **Notifications** use `notify-send`. On Ubuntu, install it with:

```bash
sudo apt install libnotify-bin
```

