"""
Core file I/O utilities for fast-edit.
Provides atomic file operations with cross-platform support.
"""
import sys
import os
import tempfile
import shutil


def read_lines(filepath):
    """Read file and return list of lines (preserving line endings)."""
    abs_path = os.path.abspath(filepath)
    with open(abs_path, "r", encoding="utf-8", newline="") as f:
        return f.readlines()


def write_file(filepath, content):
    """
    Atomic write: write to temp file, then rename.
    Supports both string content and list of lines.
    """
    abs_path = os.path.abspath(filepath)
    dir_path = os.path.dirname(abs_path) or "."
    
    # Ensure directory exists
    os.makedirs(dir_path, exist_ok=True)
    
    # Write to temp file first
    fd, tmp_path = tempfile.mkstemp(dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            if isinstance(content, list):
                f.writelines(content)
            else:
                f.write(content)
        
        # Preserve original file permissions if exists
        if os.path.exists(abs_path):
            os.chmod(tmp_path, os.stat(abs_path).st_mode)
        
        # Windows requires removing target first
        if sys.platform == "win32" and os.path.exists(abs_path):
            os.remove(abs_path)
        
        # Atomic rename
        shutil.move(tmp_path, abs_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def detect_line_ending(lines):
    """Detect dominant line ending style (LF or CRLF)."""
    if not lines:
        return "\n"
    crlf_count = sum(1 for line in lines if line.endswith("\r\n"))
    return "\r\n" if crlf_count > len(lines) // 2 else "\n"


def normalize_content(content, line_ending):
    """Normalize content to use consistent line endings."""
    if not content:
        return ""
    result = []
    for line in content.splitlines(True):
        stripped = line.rstrip("\r\n")
        result.append(stripped + line_ending)
    return "".join(result)


def validate_range(start, end, total, command):
    """Validate line range for edit operations."""
    if start < 1:
        raise ValueError(f"{command}: start must be >= 1, got {start}")
    if end < start:
        raise ValueError(f"{command}: end ({end}) must be >= start ({start})")
    if start > total:
        raise ValueError(f"{command}: start ({start}) exceeds file length ({total} lines)")
    if end > total:
        raise ValueError(f"{command}: end ({end}) exceeds file length ({total} lines)")
