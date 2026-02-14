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

    structural = _extract_structural_content(text)
    if structural is not None:
        return structural

    return text


def _extract_structural_content(text):
    """Detect and extract JSON/XML/array content from mixed text.

    JSON/array: bracket depth tracking for { } [ ].
    XML: first-last matching tag (e.g. <root>...</root>).
    Returns the largest region if it covers >= 80% of total lines.
    """
    lines = text.splitlines()
    if not lines:
        return None

    OPENERS = {'{': '}', '[': ']'}
    best = None

    scan_from = 0
    while scan_from < len(lines):
        start_idx = None
        opener_char = None
        for i in range(scan_from, len(lines)):
            stripped = lines[i].lstrip()
            if stripped and stripped[0] in OPENERS:
                start_idx = i
                opener_char = stripped[0]
                break

        if start_idx is None or opener_char is None:
            break

        closer_char = OPENERS[opener_char]
        depth = 0
        end_idx = None
        in_string = False
        escape_next = False

        for i in range(start_idx, len(lines)):
            for ch in lines[i]:
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == opener_char:
                    depth += 1
                elif ch == closer_char:
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            if end_idx is not None:
                break

        if end_idx is None:
            break

        span = end_idx - start_idx + 1
        if best is None or span > best[0]:
            best = (span, start_idx, end_idx)

        scan_from = end_idx + 1

    xml = _find_xml_region(lines)
    if xml is not None:
        if best is None or xml[0] > best[0]:
            best = xml

    if best is None:
        return None

    span, start_idx, end_idx = best
    total_lines = len(lines)
    if total_lines > 0 and span / total_lines < 0.8:
        return None

    return "\n".join(lines[start_idx:end_idx + 1])


def _find_xml_region(lines):
    xml_open = re.compile(r'^\s*<([a-zA-Z][\w.:_-]*)[\s>]')
    start_idx = None
    tag_name = None

    for i, line in enumerate(lines):
        m = xml_open.match(line)
        if m:
            start_idx = i
            tag_name = m.group(1)
            break

    if start_idx is None or tag_name is None:
        return None

    close_pat = re.compile(r'</\s*' + re.escape(tag_name) + r'\s*>')
    end_idx = None
    for i in range(len(lines) - 1, start_idx - 1, -1):
        if close_pat.search(lines[i]):
            end_idx = i
            break

    if end_idx is None or end_idx == start_idx:
        return None

    span = end_idx - start_idx + 1
    return (span, start_idx, end_idx)


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
