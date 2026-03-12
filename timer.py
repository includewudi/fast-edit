"""
Timer module for tracking end-to-end elapsed time across tool invocations.

Workflow:
1. AI loads skill → immediately runs `fe timer start` → gets timer_id
2. AI thinks, plans, writes code...
3. AI runs `fe fast-generate --timer <timer_id> ...`
4. Output includes both execution timing AND total elapsed since timer start

Storage: /tmp/fe-timers/<timer_id>.json
"""
import os
import json
import time
import uuid
from datetime import datetime

TIMER_DIR = "/tmp/fe-timers"


def _ensure_dir():
    os.makedirs(TIMER_DIR, exist_ok=True)


def _timer_path(timer_id):
    return os.path.join(TIMER_DIR, f"{timer_id}.json")


def start():
    """
    Start a new timer. Returns timer_id and start timestamp.
    """
    _ensure_dir()
    timer_id = f"t_{uuid.uuid4().hex[:8]}"
    now = time.time()
    data = {
        "timer_id": timer_id,
        "start_epoch": now,
        "start_iso": datetime.now().isoformat(),
    }
    with open(_timer_path(timer_id), "w") as f:
        json.dump(data, f)

    return {
        "status": "ok",
        "timer_id": timer_id,
        "started_at": data["start_iso"],
    }


def stop(timer_id):
    """
    Stop a timer. Returns elapsed time.
    """
    path = _timer_path(timer_id)
    if not os.path.isfile(path):
        return {"status": "error", "message": f"Timer not found: {timer_id}"}

    with open(path) as f:
        data = json.load(f)

    now = time.time()
    elapsed = round(now - data["start_epoch"], 3)

    os.remove(path)

    return {
        "status": "ok",
        "timer_id": timer_id,
        "started_at": data["start_iso"],
        "stopped_at": datetime.now().isoformat(),
        "total_elapsed_sec": elapsed,
    }


def elapsed(timer_id):
    """
    Read elapsed time without stopping the timer.
    Used by other commands (generate, batch, etc.) via --timer flag.

    Returns (start_epoch, start_iso) or None if timer not found.
    """
    path = _timer_path(timer_id)
    if not os.path.isfile(path):
        return None

    with open(path) as f:
        data = json.load(f)

    return data["start_epoch"], data["start_iso"]
