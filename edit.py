"""
Edit operations: show, replace, insert, delete, batch.
All line numbers are 1-based and inclusive.
"""
import os
from core import (
    read_lines, write_file, 
    detect_line_ending, normalize_content, validate_range
)


_BRACKETS = {"(": ")", "[": "]", "{": "}"}
_OPEN = set(_BRACKETS.keys())
_CLOSE = set(_BRACKETS.values())


def _bracket_balance(text):
    """Count net bracket balance: positive = more opens, negative = more closes."""
    counts = {}
    in_string = None
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch in ("\"", "'"):
            if in_string == ch:
                in_string = None
            elif in_string is None:
                in_string = ch
            continue
        if in_string:
            continue
        if ch in _OPEN or ch in _CLOSE:
            counts[ch] = counts.get(ch, 0) + 1
    # Net balance per bracket type
    balance = {}
    for o, c in _BRACKETS.items():
        balance[o + c] = counts.get(o, 0) - counts.get(c, 0)
    return balance


def _check_replace_warnings(old_lines, new_lines, result_lines, start, end):
    """
    Check for common AI editing mistakes after a replace operation.
    Returns list of warning strings (empty if no issues).
    
    Checks:
    1. Duplicate line: last line of new content == first surviving line after edit
    2. Bracket balance change: replacement changed the file bracket balance
    """
    warnings = []
    
    # --- Check 1: Duplicate line at boundary ---
    if new_lines and end <= len(result_lines):
        # new_lines[-1] is the last inserted line, result_lines[len(old_lines[:start-1]) + len(new_lines)] is next surviving
        last_new = new_lines[-1].rstrip()
        # Position of first surviving line after the edit in result
        surviving_idx = (start - 1) + len(new_lines)
        if surviving_idx < len(result_lines):
            first_surviving = result_lines[surviving_idx].rstrip()
            if last_new and last_new == first_surviving:
                warnings.append(
                    f"DUPLICATE_LINE: line {surviving_idx + 1} is identical to the last replaced line "
                    f"(possible off-by-one in END). Content: {repr(last_new[:80])}"
                )
    
    # --- Check 2: Bracket balance change ---
    old_text = "".join(old_lines)
    new_text = "".join(new_lines)
    old_balance = _bracket_balance(old_text)
    new_balance = _bracket_balance(new_text)
    
    for pair, old_net in old_balance.items():
        new_net = new_balance.get(pair, 0)
        diff = new_net - old_net
        if diff != 0:
            direction = "more opens" if diff > 0 else "more closes"
            warnings.append(
                f"BRACKET_BALANCE: {pair[0]}...{pair[1]} changed by {diff:+d} ({abs(diff)} {direction}). "
                f"Replacement may have mismatched brackets."
            )
    
    return warnings


_auto_backup = True


def _maybe_backup(filepath):
    """Create backup before editing if auto_backup is enabled."""
    if not _auto_backup:
        return None
    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        return None
    try:
        import verify
        return verify.backup(filepath)
    except Exception:
        return None  # backup failure should never block editing


def show(filepath, start, end):
    """Show lines with line numbers (for preview before editing)."""
    lines = read_lines(filepath)
    total = len(lines)
    
    # Clamp to valid range
    start = max(1, start)
    end = min(total, end)
    
    # Format with line numbers
    output = []
    for i in range(start - 1, end):
        output.append(f"{i + 1}\t{lines[i].rstrip()}")
    
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "start": start,
        "end": end,
        "total": total,
        "content": "\n".join(output)
    }


def replace(filepath, start, end, content):
    """Replace lines start..end with new content."""
    _maybe_backup(filepath)
    lines = read_lines(filepath)
    validate_range(start, end, len(lines), "replace")

    le = detect_line_ending(lines)
    new_content = normalize_content(content, le)

    # Ensure trailing newline if not at EOF
    if new_content and not new_content.endswith(("\
", "\\r\
")) and end < len(lines):
        new_content += le

    new_lines = new_content.splitlines(True) if new_content else []
    old_lines = lines[start - 1:end]
    result = lines[:start - 1] + new_lines + lines[end:]
    write_file(filepath, result)

    # Check for common AI editing mistakes
    warnings = _check_replace_warnings(old_lines, new_lines, result, start, end)

    ret = {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "removed": end - start + 1,
        "added": len(new_lines),
        "total": len(result)
    }
    if warnings:
        ret["warnings"] = warnings
    return ret


def insert(filepath, after_line, content):
    """Insert content after specified line (0 = prepend to file)."""
    _maybe_backup(filepath)
    lines = read_lines(filepath)
    
    if after_line < 0 or after_line > len(lines):
        raise ValueError(f"insert: line ({after_line}) out of range (0..{len(lines)})")
    
    le = detect_line_ending(lines)
    new_content = normalize_content(content, le)
    
    # Ensure trailing newline
    if new_content and not new_content.endswith(("\n", "\r\n")):
        new_content += le
    
    # Ensure previous line has newline
    if after_line > 0 and lines[after_line - 1] and not lines[after_line - 1].endswith(("\n", "\r\n")):
        lines[after_line - 1] += le
    
    new_lines = new_content.splitlines(True) if new_content else []
    result = lines[:after_line] + new_lines + lines[after_line:]
    write_file(filepath, result)
    
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "after": after_line,
        "added": len(new_lines),
        "total": len(result)
    }


def delete(filepath, start, end):
    """Delete lines start..end."""
    _maybe_backup(filepath)
    lines = read_lines(filepath)
    validate_range(start, end, len(lines), "delete")
    
    result = lines[:start - 1] + lines[end:]
    write_file(filepath, result)
    
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "removed": end - start + 1,
        "total": len(result)
    }

def _edit_range(edit):
    """Extract (start, end) range for an edit. insert-after is treated as a point (line, line)."""
    action = edit["action"]
    if action in ("replace-lines", "delete-lines"):
        return (edit["start"], edit["end"])
    elif action == "insert-after":
        ln = edit["line"]
        return (ln, ln)
    return (0, 0)


def _check_overlapping_edits(sorted_edits, filename=""):
    """
    Detect overlapping edit ranges and raise ValueError if found.
    sorted_edits should already be sorted by start position (descending).
    """
    # Build list of (start, end, edit_index) for range-based edits
    ranges = []
    for i, edit in enumerate(sorted_edits):
        s, e = _edit_range(edit)
        if s > 0:  # skip insert-after at line 0
            ranges.append((s, e, i, edit["action"]))

    # Sort by start ascending for overlap detection
    ranges.sort(key=lambda r: (r[0], r[1]))

    for i in range(len(ranges) - 1):
        s1, e1, idx1, act1 = ranges[i]
        s2, e2, idx2, act2 = ranges[i + 1]
        # Two insert-after on same line is fine (they don't conflict)
        if act1 == "insert-after" and act2 == "insert-after":
            continue
        # Overlap: s2 starts within or at s1..e1
        if s2 <= e1:
            prefix = f"[{filename}] " if filename else ""
            raise ValueError(
                f"{prefix}batch: overlapping edits detected — "
                f"{act1} [{s1}-{e1}] overlaps with {act2} [{s2}-{e2}]. "
                f"Split into separate batch calls or adjust line ranges."
            )

def batch(spec):
    """
    Execute multiple edits atomically.
    Edits are auto-sorted back-to-front to prevent line number shifts.
    
    JSON format:
        {"file": "...", "edits": [...]}
        or {"files": [{"file": "...", "edits": [...]}, ...]}
    
    Edit actions:
        {"action": "replace-lines", "start": N, "end": M, "content": "..."}
        {"action": "insert-after", "line": N, "content": "..."}
        {"action": "delete-lines", "start": N, "end": M}
    """
    file_specs = spec.get("files", [spec])
    results = []
    all_warnings = []

    for file_spec in file_specs:
        filepath = file_spec["file"]
        edits = file_spec["edits"]

        _maybe_backup(filepath)
        lines = read_lines(filepath)
        le = detect_line_ending(lines)

        # Sort edits from bottom to top (prevents line number shifting)
        sorted_edits = sorted(
            edits,
            key=lambda e: -(e.get("start") or e.get("line", 0))
        )


        # Check for overlapping edit ranges
        _check_overlapping_edits(sorted_edits, os.path.basename(filepath))

        for edit in sorted_edits:
            action = edit["action"]

            if action == "replace-lines":
                s, e = edit["start"], edit["end"]
                validate_range(s, e, len(lines), "batch/replace")
                new_content = normalize_content(edit.get("content", ""), le)
                if new_content and not new_content.endswith(("\
", "\\r\
")) and e < len(lines):
                    new_content += le
                new_lines = new_content.splitlines(True) if new_content else []
                old_lines = lines[s - 1:e]
                lines = lines[:s - 1] + new_lines + lines[e:]
                # Check warnings for this replace
                w = _check_replace_warnings(old_lines, new_lines, lines, s, e)
                for msg in w:
                    all_warnings.append(f"[{os.path.basename(filepath)}:{s}-{e}] {msg}")

            elif action == "insert-after":
                ln = edit["line"]
                if ln < 0 or ln > len(lines):
                    raise ValueError(f"batch/insert: line ({ln}) out of range")
                new_content = normalize_content(edit.get("content", ""), le)
                if new_content and not new_content.endswith(("\
", "\\r\
")):
                    new_content += le
                if ln > 0 and lines[ln - 1] and not lines[ln - 1].endswith(("\
", "\\r\
")):
                    lines[ln - 1] += le
                new_lines = new_content.splitlines(True) if new_content else []
                lines = lines[:ln] + new_lines + lines[ln:]

            elif action == "delete-lines":
                s, e = edit["start"], edit["end"]
                validate_range(s, e, len(lines), "batch/delete")
                lines = lines[:s - 1] + lines[e:]

            else:
                raise ValueError(f"Unknown action: {action}")

        write_file(filepath, lines)
        results.append({
            "file": os.path.abspath(filepath),
            "edits": len(edits),
            "total": len(lines)
        })

    ret = {
        "status": "ok",
        "files": len(results),
        "results": results
    }
    if all_warnings:
        ret["warnings"] = all_warnings
    return ret
