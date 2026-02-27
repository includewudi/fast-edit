"""
Verify and restore operations for fast-edit.
- backup: create snapshot before editing
- verify: compare current file with backup, report line-level diff
- restore: roll back to backup
- verify-syntax: run language-aware syntax check (go build, python -m py_compile, etc.)

Backup storage: ~/.fast-edit-backups/<md5(abspath)>/<timestamp>
"""
import os
import sys
import hashlib
import shutil
import time
import difflib
from datetime import datetime
from core import read_lines

BACKUP_DIR = os.path.expanduser("~/.fast-edit-backups")
MAX_BACKUPS_PER_FILE = 10


def _file_key(filepath):
    """Generate a stable directory name from absolute path."""
    abs_path = os.path.abspath(filepath)
    return hashlib.md5(abs_path.encode("utf-8")).hexdigest()


def _backup_dir(filepath):
    """Get backup directory for a given file."""
    return os.path.join(BACKUP_DIR, _file_key(filepath))


def _latest_backup(filepath):
    """Find latest backup for a file. Returns (path, timestamp) or (None, None)."""
    bdir = _backup_dir(filepath)
    if not os.path.isdir(bdir):
        return None, None
    entries = sorted(os.listdir(bdir), reverse=True)
    for entry in entries:
        full = os.path.join(bdir, entry)
        if os.path.isfile(full) and not entry.endswith(".meta"):
            return full, entry
    return None, None


def backup(filepath, max_backups=MAX_BACKUPS_PER_FILE):
    """
    Create a timestamped backup of the file.
    Returns backup path.
    """
    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Cannot backup: file not found: {abs_path}")

    bdir = _backup_dir(filepath)
    os.makedirs(bdir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = os.path.join(bdir, ts)
    shutil.copy2(abs_path, backup_path)

    # Write a metadata sidecar so we know the original path
    meta_path = backup_path + ".meta"
    with open(meta_path, "w") as f:
        f.write(abs_path)

    # Prune old backups
    _cleanup_old_backups(filepath)

    return backup_path


def _cleanup_old_backups(filepath):
    """Remove old backups, keeping only the most recent MAX_BACKUPS_PER_FILE."""
    bdir = _backup_dir(filepath)
    if not os.path.isdir(bdir):
        return
    entries = sorted(
        [e for e in os.listdir(bdir) if not e.endswith('.meta')],
        reverse=True
    )
    # Keep the newest MAX_BACKUPS_PER_FILE, delete the rest
    for old_entry in entries[MAX_BACKUPS_PER_FILE:]:
        old_path = os.path.join(bdir, old_entry)
        meta_path = old_path + '.meta'
        try:
            os.remove(old_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)
        except OSError:
            pass  # best-effort cleanup


def verify(filepath, context=1):
    """
    Compare current file against its latest backup.
    Returns structured diff report with line-level changes.

    Args:
        filepath: file to verify
        context: number of context lines around each change (default 1)
    """
    abs_path = os.path.abspath(filepath)
    backup_path, backup_ts = _latest_backup(filepath)

    if backup_path is None:
        return {
            "status": "error",
            "message": f"No backup found for {abs_path}"
        }

    if not os.path.isfile(abs_path):
        return {
            "status": "error",
            "message": f"Current file missing: {abs_path}"
        }

    # Read both versions
    with open(backup_path, "r", encoding="utf-8", newline="") as f:
        old_lines = f.readlines()
    with open(abs_path, "r", encoding="utf-8", newline="") as f:
        new_lines = f.readlines()

    old_stripped = [l.rstrip("\r\n") for l in old_lines]
    new_stripped = [l.rstrip("\r\n") for l in new_lines]

    # Identical check
    if old_stripped == new_stripped:
        return {
            "status": "ok",
            "file": abs_path,
            "backup": backup_path,
            "result": "identical",
            "old_lines": len(old_lines),
            "new_lines": len(new_lines),
            "changes": []
        }

    # Compute unified diff
    diff = list(difflib.unified_diff(
        old_stripped, new_stripped,
        fromfile="backup", tofile="current",
        lineterm="", n=context
    ))

    # Parse hunks into structured changes
    changes = []
    current_hunk = None

    for line in diff:
        if line.startswith("@@"):
            # Parse @@ -old_start,old_count +new_start,new_count @@
            if current_hunk:
                changes.append(current_hunk)
            import re
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                current_hunk = {
                    "old_start": int(m.group(1)),
                    "old_count": int(m.group(2) or 1),
                    "new_start": int(m.group(3)),
                    "new_count": int(m.group(4) or 1),
                    "lines": []
                }
            else:
                current_hunk = {"header": line, "lines": []}
        elif current_hunk is not None:
            if line.startswith("---") or line.startswith("+++"):
                continue
            current_hunk["lines"].append(line)

    if current_hunk:
        changes.append(current_hunk)

    # Summary stats
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return {
        "status": "ok",
        "file": abs_path,
        "backup": backup_path,
        "backup_time": backup_ts,
        "result": "changed",
        "old_lines": len(old_lines),
        "new_lines": len(new_lines),
        "added": added,
        "removed": removed,
        "changes": changes
    }


def restore(filepath):
    """
    Restore file from its latest backup.
    Creates a forward backup of current state before restoring.
    """
    abs_path = os.path.abspath(filepath)
    backup_path, backup_ts = _latest_backup(filepath)

    if backup_path is None:
        return {
            "status": "error",
            "message": f"No backup found for {abs_path}"
        }

    # Save current state as forward backup (so we can undo the undo)
    if os.path.isfile(abs_path):
        bdir = _backup_dir(filepath)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_pre_restore"
        pre_restore_path = os.path.join(bdir, ts)
        shutil.copy2(abs_path, pre_restore_path)

    # Restore
    shutil.copy2(backup_path, abs_path)

    # Read restored content for line count
    with open(abs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    return {
        "status": "ok",
        "file": abs_path,
        "restored_from": backup_path,
        "backup_time": backup_ts,
        "lines": len(lines)
    }


def verify_syntax(filepath):
    """
    Run language-aware syntax check based on file extension.
    Supported: .go, .py, .js/.ts, .rs, .c/.cpp, .java
    """
    import subprocess

    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")

    ext = os.path.splitext(abs_path)[1].lower()
    dir_path = os.path.dirname(abs_path)

    commands = {
        ".go":   (["go", "vet", abs_path], "go vet"),
        ".py":   (["python3", "-m", "py_compile", abs_path], "py_compile"),
        ".rs":   (["rustc", "--edition", "2021", "--crate-type", "lib", abs_path, "-o", "/dev/null"], "rustc"),
        ".c":    (["cc", "-fsyntax-only", abs_path], "cc"),
        ".cpp":  (["c++", "-fsyntax-only", abs_path], "c++"),
        ".java": (["javac", "-d", "/tmp", abs_path], "javac"),
    }

    # TypeScript/JavaScript — try tsc, fall back to node --check
    if ext in (".ts", ".tsx"):
        commands[ext] = (["tsc", "--noEmit", abs_path], "tsc")
    elif ext in (".js", ".jsx", ".mjs"):
        commands[ext] = (["node", "--check", abs_path], "node")

    if ext not in commands:
        return {
            "status": "ok",
            "file": abs_path,
            "checker": "none",
            "message": f"No syntax checker for {ext} files"
        }

    cmd, checker_name = commands[ext]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=dir_path or "."
        )
        output = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            return {
                "status": "ok",
                "file": abs_path,
                "checker": checker_name,
                "syntax_valid": True,
                "output": output[:2000] if output else ""
            }
        else:
            return {
                "status": "ok",
                "file": abs_path,
                "checker": checker_name,
                "syntax_valid": False,
                "exit_code": result.returncode,
                "output": output[:4000]
            }
    except FileNotFoundError:
        return {
            "status": "error",
            "file": abs_path,
            "checker": checker_name,
            "message": f"Checker not found: {cmd[0]}"
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "file": abs_path,
            "checker": checker_name,
            "message": f"Syntax check timed out after 30s"
        }


def list_backups(filepath):
    """List all backups for a file."""
    abs_path = os.path.abspath(filepath)
    bdir = _backup_dir(filepath)

    if not os.path.isdir(bdir):
        return {
            "status": "ok",
            "file": abs_path,
            "backups": []
        }

    entries = sorted(os.listdir(bdir), reverse=True)
    backups = []
    for entry in entries:
        full = os.path.join(bdir, entry)
        if os.path.isfile(full) and not entry.endswith(".meta"):
            stat = os.stat(full)
            backups.append({
                "name": entry,
                "path": full,
                "size": stat.st_size,
                "time": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    return {
        "status": "ok",
        "file": abs_path,
        "backups": backups
    }
