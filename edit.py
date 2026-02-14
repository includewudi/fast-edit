"""
Edit operations: show, replace, insert, delete, batch.
All line numbers are 1-based and inclusive.
"""
import os
from core import (
    read_lines, write_file, 
    detect_line_ending, normalize_content, validate_range
)


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
    lines = read_lines(filepath)
    validate_range(start, end, len(lines), "replace")
    
    le = detect_line_ending(lines)
    new_content = normalize_content(content, le)
    
    # Ensure trailing newline if not at EOF
    if new_content and not new_content.endswith(("\n", "\r\n")) and end < len(lines):
        new_content += le
    
    new_lines = new_content.splitlines(True) if new_content else []
    result = lines[:start - 1] + new_lines + lines[end:]
    write_file(filepath, result)
    
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "removed": end - start + 1,
        "added": len(new_lines),
        "total": len(result)
    }


def insert(filepath, after_line, content):
    """Insert content after specified line (0 = prepend to file)."""
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
    
    for file_spec in file_specs:
        filepath = file_spec["file"]
        edits = file_spec["edits"]
        
        lines = read_lines(filepath)
        le = detect_line_ending(lines)
        
        # Sort edits from bottom to top (prevents line number shifting)
        sorted_edits = sorted(
            edits, 
            key=lambda e: -(e.get("start") or e.get("line", 0))
        )
        
        for edit in sorted_edits:
            action = edit["action"]
            
            if action == "replace-lines":
                s, e = edit["start"], edit["end"]
                validate_range(s, e, len(lines), "batch/replace")
                new_content = normalize_content(edit.get("content", ""), le)
                if new_content and not new_content.endswith(("\n", "\r\n")) and e < len(lines):
                    new_content += le
                new_lines = new_content.splitlines(True) if new_content else []
                lines = lines[:s - 1] + new_lines + lines[e:]
                
            elif action == "insert-after":
                ln = edit["line"]
                if ln < 0 or ln > len(lines):
                    raise ValueError(f"batch/insert: line ({ln}) out of range")
                new_content = normalize_content(edit.get("content", ""), le)
                if new_content and not new_content.endswith(("\n", "\r\n")):
                    new_content += le
                if ln > 0 and lines[ln - 1] and not lines[ln - 1].endswith(("\n", "\r\n")):
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
    
    return {
        "status": "ok",
        "files": len(results),
        "results": results
    }
