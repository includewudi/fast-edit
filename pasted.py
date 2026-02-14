"""
save-pasted: Extract user-pasted content from OpenCode's part storage
(~/.local/share/opencode/storage/part/) and save to file.
Bypasses AI token output bottleneck for large pastes.
"""
import os
import json
import re
from pathlib import Path
from core import write_file


PART_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage" / "part"
MSG_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage" / "message"
DEFAULT_MIN_LINES = 20


def _find_user_msg_ids(limit=50):
    if not MSG_STORAGE.exists():
        return []

    session_dirs = sorted(
        [d for d in MSG_STORAGE.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    user_msg_ids = []
    for session_dir in session_dirs[:5]:
        msg_files = sorted(
            session_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for mf in msg_files:
            try:
                meta = json.loads(mf.read_text("utf-8"))
                if meta.get("role") == "user":
                    user_msg_ids.append(meta["id"])
            except (json.JSONDecodeError, KeyError):
                continue
            if len(user_msg_ids) >= limit:
                break
        if len(user_msg_ids) >= limit:
            break

    return user_msg_ids


def _get_parts_for_msg(msg_id):
    part_dir = PART_STORAGE / msg_id
    if not part_dir.is_dir():
        return []

    parts = []
    for pf in part_dir.glob("*.json"):
        try:
            data = json.loads(pf.read_text("utf-8"))
            if data.get("type") == "text" and data.get("text"):
                parts.append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    parts.sort(
        key=lambda p: p.get("time", {}).get("start", 0),
        reverse=True,
    )
    return parts


def _extract_pasted_content(text):
    """Heuristic extraction: [Pasted ~N lines] marker > fenced code blocks > raw text."""
    # [Pasted ~N lines] marker from OpenCode's paste detection
    marker_match = re.search(r'\[Pasted\s+~?\d+\s+lines?\]', text)
    if marker_match:
        pasted = text[marker_match.end():].strip()
        if pasted:
            return pasted

    code_pattern = r"```[\w]*\n?([\s\S]*?)```"
    blocks = re.findall(code_pattern, text)
    if blocks:
        return max(blocks, key=len)

    return text


def extract_code_blocks(text):
    pattern = r"```[\w]*\n?([\s\S]*?)```"
    blocks = re.findall(pattern, text)
    if blocks:
        return "\n".join(blocks)
    return text


def find_large_paste(min_lines=DEFAULT_MIN_LINES, msg_id=None, nth=1):
    """
    Find the nth most recent large pasted content from OpenCode storage.
    
    Args:
        min_lines: Minimum line count to qualify as "large paste"
        msg_id: Specific message ID to look in (skip scanning)
        nth: Which large paste to return (1=most recent, 2=second, etc.)
    
    Returns:
        dict with keys: text, msg_id, part_id, lines, bytes
    
    Raises:
        FileNotFoundError: If OpenCode storage not found
        ValueError: If no qualifying paste found
    """
    if not PART_STORAGE.exists():
        raise FileNotFoundError(
            f"OpenCode part storage not found at {PART_STORAGE}. "
            "Is OpenCode installed?"
        )

    if msg_id:
        parts = _get_parts_for_msg(msg_id)
        for part in parts:
            text = part["text"]
            content = _extract_pasted_content(text)
            if len(content.splitlines()) >= min_lines:
                return {
                    "text": content,
                    "msg_id": msg_id,
                    "part_id": part["id"],
                    "lines": len(content.splitlines()),
                    "bytes": len(content.encode("utf-8")),
                }
        raise ValueError(
            f"No paste >= {min_lines} lines found in message {msg_id}"
        )

    user_msg_ids = _find_user_msg_ids(limit=50)
    if not user_msg_ids:
        raise ValueError("No user messages found in OpenCode storage")

    found_count = 0
    for uid in user_msg_ids:
        parts = _get_parts_for_msg(uid)
        for part in parts:
            text = part["text"]
            content = _extract_pasted_content(text)
            if len(content.splitlines()) >= min_lines:
                found_count += 1
                if found_count == nth:
                    return {
                        "text": content,
                        "msg_id": uid,
                        "part_id": part["id"],
                        "lines": len(content.splitlines()),
                        "bytes": len(content.encode("utf-8")),
                    }

    raise ValueError(
        f"No paste >= {min_lines} lines found in recent {len(user_msg_ids)} "
        f"user messages (searched {PART_STORAGE})"
    )


def save_pasted(filepath, min_lines=DEFAULT_MIN_LINES, msg_id=None,
                extract=False, nth=1):
    """
    Find the latest large paste and save it to a file.
    
    Args:
        filepath: Target file path
        min_lines: Minimum lines to qualify as large paste
        msg_id: Specific message ID (optional)
        extract: Extract code from ```...``` blocks
        nth: Which large paste (1=most recent)
    
    Returns:
        dict with status, file, lines, bytes, msg_id, part_id
    """
    result = find_large_paste(min_lines=min_lines, msg_id=msg_id, nth=nth)
    content = result["text"]

    if extract:
        content = extract_code_blocks(content)

    write_file(filepath, content)

    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "lines": len(content.splitlines()),
        "bytes": len(content.encode("utf-8")),
        "msg_id": result["msg_id"],
        "part_id": result["part_id"],
    }
