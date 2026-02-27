"""
Recover file content from OpenCode session storage.

Scans session message parts to find the last write operation targeting a file,
extracts the content, and optionally writes it to disk.

Storage layout:
    ~/.local/share/opencode/storage/
    ├── session/{session_id}/           # session index
    ├── message/{session_id}/{msg}.json # message metadata
    └── part/{msg_id}/{part}.json       # actual content (text, tool calls)

Supported write patterns:
    1. bash: cat > FILE << 'MARKER' ... MARKER
    2. bash: fast_edit.py (paste/write/replace/generate)
    3. edit tool: {"filePath": "...", "edits": [...]}
    4. write tool: {"filePath": "...", "content": "..."}
"""
import os
import sys
import json
import re
from datetime import datetime

STORAGE_DIR = os.path.expanduser("~/.local/share/opencode/storage")
PART_DIR = os.path.join(STORAGE_DIR, "part")
MSG_DIR = os.path.join(STORAGE_DIR, "message")
SESSION_DIR = os.path.join(STORAGE_DIR, "session")


def _list_sessions():
    """List all session IDs (ses_xxx), sorted by most recent first."""
    # Sessions are indexed in MSG_DIR as ses_xxx/ directories
    if not os.path.isdir(MSG_DIR):
        return []
    entries = []
    for sid in os.listdir(MSG_DIR):
        sd = os.path.join(MSG_DIR, sid)
        if os.path.isdir(sd) and sid.startswith('ses_'):
            mtime = os.path.getmtime(sd)
            entries.append((mtime, sid))
    return [sid for _, sid in sorted(entries, reverse=True)]


def _session_messages(session_id):
    """Get all message IDs for a session, sorted chronologically."""
    mdir = os.path.join(MSG_DIR, session_id)
    if not os.path.isdir(mdir):
        return []
    msgs = []
    for f in os.listdir(mdir):
        if f.endswith(".json"):
            msg_id = f[:-5]
            msgs.append(msg_id)
    return sorted(msgs)


def _message_parts(msg_id):
    """Get all parts for a message, sorted by filename (chronological)."""
    pdir = os.path.join(PART_DIR, msg_id)
    if not os.path.isdir(pdir):
        return []
    parts = []
    for f in sorted(os.listdir(pdir)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(pdir, f)) as fh:
                    parts.append(json.load(fh))
            except (json.JSONDecodeError, OSError):
                pass
    return parts


def _extract_bash_cat_target(cmd):
    """Extract target filepath from: cat > /path/to/file << 'MARKER'"""
    m = re.search(r"cat\s*>\s*(['\"]?)([^\s'\"]+)\1\s*<<", cmd)
    return m.group(2) if m else None


def _extract_bash_cat_content(cmd):
    """Extract heredoc content from: cat > FILE << 'MARKER'\ncontent\nMARKER"""
    # Quoted marker: << 'EOF' or << "EOF"
    m = re.search(r"<<\s*['\"]([\w]+)['\"]\s*\n(.*?)\n\1(?=\s*\n|\s*$)", cmd, re.DOTALL)
    if m:
        return m.group(2)
    # Unquoted marker: << EOF
    m = re.search(r"<<\s*([\w]+)\s*\n(.*?)\n\1(?=\s*\n|\s*$)", cmd, re.DOTALL)
    return m.group(2) if m else None


def _extract_fe_target(cmd):
    """Extract target filepath from fast_edit.py commands."""
    # fast-paste FILE, fast-replace FILE START END CONTENT
    # Handles: python3 "path/fast_edit.py" fast-paste "FILE" --stdin
    #          fe fast-paste FILE --stdin
    m = re.search(
        r"(?:fast_edit\.py|\bfe\b)['\"]?\s+(?:fast-)?(?:paste|replace|write)\s+"
        r"['\"]?([^\s'\"]+)",
        cmd
    )
    if m:
        return m.group(1)
    # generate -o FILE
    if 'generate' in cmd:
        m = re.search(r"-o\s+['\"]?([^\s'\"]+)", cmd)
        return m.group(1) if m else None
    return None


def _normalize_path(filepath):
    """Normalize to absolute path for comparison."""
    return os.path.abspath(os.path.expanduser(filepath))


def _path_matches(target, candidate):
    """Check if a candidate path matches the target (fuzzy: basename or full path)."""
    if not candidate or not target:
        return False
    target_norm = _normalize_path(target)
    candidate_norm = _normalize_path(candidate)
    # Exact match
    if target_norm == candidate_norm:
        return True
    # Basename match
    if os.path.basename(target_norm) == os.path.basename(candidate_norm):
        return True
    # Substring
    if target in candidate:
        return True
    return False


def _scan_session(session_id, target_file=None):
    """
    Scan a session for file write operations.
    Returns list of dicts sorted chronologically (newest last).
    """
    results = []
    messages = _session_messages(session_id)

    for msg_id in messages:
        parts = _message_parts(msg_id)
        for part in parts:
            if part.get("type") != "tool":
                continue
            if part.get("state", {}).get("status") != "completed":
                continue

            tool = part.get("tool", "")
            inp = part.get("state", {}).get("input", {})
            ts = part.get("state", {}).get("time", {}).get("end", 0)
            entry = None

            if tool == "bash":
                cmd = inp.get("command", "")

                # Pattern 1: cat > FILE << MARKER
                cat_target = _extract_bash_cat_target(cmd)
                if cat_target:
                    if target_file is None or _path_matches(target_file, cat_target):
                        content = _extract_bash_cat_content(cmd)
                        entry = {
                            "msg_id": msg_id,
                            "part_id": part.get("id", ""),
                            "tool": "bash/cat",
                            "target_file": cat_target,
                            "content": content,
                            "content_preview": (content or "")[:80],
                            "content_len": len(content or ""),
                            "timestamp": ts,
                        }

                # Pattern 2: fast_edit.py paste/write/replace/generate
                if not entry:
                    fe_target = _extract_fe_target(cmd)
                    if fe_target:
                        if target_file is None or _path_matches(target_file, fe_target):
                            content = _extract_bash_cat_content(cmd)
                            entry = {
                                "msg_id": msg_id,
                                "part_id": part.get("id", ""),
                                "tool": "bash/fast-edit",
                                "target_file": fe_target,
                                "content": content,
                                "content_preview": (content or "")[:80],
                                "content_len": len(content or ""),
                                "timestamp": ts,
                            }

            elif tool == "edit":
                fp = inp.get("filePath", "")
                if fp and (target_file is None or _path_matches(target_file, fp)):
                    edits = inp.get("edits", [])
                    texts = []
                    for e in edits:
                        if isinstance(e, str):
                            if e:
                                texts.append(e)
                            continue
                        t = e.get("text", e.get("new_text", ""))
                        if isinstance(t, list):
                            t = "\n".join(t)
                        if t:
                            texts.append(t)
                    combined = "\n".join(texts)
                    entry = {
                        "msg_id": msg_id,
                        "part_id": part.get("id", ""),
                        "tool": "edit",
                        "target_file": fp,
                        "content": json.dumps(inp, ensure_ascii=False),
                        "content_preview": combined[:80],
                        "content_len": len(combined),
                        "timestamp": ts,
                    }

            elif tool == "write":
                fp = inp.get("filePath", "")
                content = inp.get("content", "")
                if fp and content and (target_file is None or _path_matches(target_file, fp)):
                    entry = {
                        "msg_id": msg_id,
                        "part_id": part.get("id", ""),
                        "tool": "write",
                        "target_file": fp,
                        "content": content,
                        "content_preview": content[:80],
                        "content_len": len(content),
                        "timestamp": ts,
                    }

            if entry:
                results.append(entry)

    return results


def recover(target_file, session_id=None, nth=1, output=None, list_only=False):
    """
    Recover the last write to a file from session storage.

    Args:
        target_file: File path (or basename) to search for.
        session_id: Specific session to search. None = search recent sessions.
        nth: Which occurrence to recover (1=most recent, 2=second most recent).
        output: Output file path. None = write to target_file.
        list_only: If True, just list matching writes without recovering.

    Returns:
        JSON result dict.
    """
    sessions_to_scan = []
    if session_id:
        sessions_to_scan = [session_id]
    else:
        sessions_to_scan = _list_sessions()[:5]

    all_results = []
    for sid in sessions_to_scan:
        hits = _scan_session(sid, target_file)
        for h in hits:
            h["session_id"] = sid
        all_results.extend(hits)

    # Sort by timestamp descending (most recent first)
    all_results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)

    if not all_results:
        return {
            "status": "error",
            "message": f"No writes found for '{target_file}' in {len(sessions_to_scan)} sessions."
        }

    if list_only:
        entries = []
        for i, r in enumerate(all_results[:20], 1):
            ts = r.get("timestamp", 0)
            time_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else "?"
            entries.append({
                "nth": i,
                "session": r["session_id"],
                "tool": r["tool"],
                "target": r["target_file"],
                "content_len": r["content_len"],
                "preview": r["content_preview"],
                "time": time_str,
            })
        return {
            "status": "ok",
            "matches": len(all_results),
            "showing": len(entries),
            "entries": entries,
        }

    # Recover the nth occurrence
    if nth > len(all_results):
        return {
            "status": "error",
            "message": f"Only {len(all_results)} writes found, but --nth {nth} requested."
        }

    target_entry = all_results[nth - 1]
    content = target_entry.get("content")

    if not content:
        return {
            "status": "error",
            "message": (
                f"Found write (tool={target_entry['tool']}) but could not extract content. "
                f"Part: {target_entry['part_id']}"
            ),
        }

    # For bash/fast-edit, content is command text — show it, don't write
    if target_entry["tool"] == "bash/fast-edit":
        return {
            "status": "ok",
            "mode": "command-ref",
            "message": (
                "Found fast-edit command. Content is the bash command (not full file). "
                "Use this as reference to replay the operation."
            ),
            "target_file": target_entry["target_file"],
            "command": content,
            "time": datetime.fromtimestamp(
                target_entry["timestamp"] / 1000
            ).strftime("%Y-%m-%d %H:%M:%S"),
        }

    # For edit tool, content is the full JSON input — show it, don't write
    if target_entry["tool"] == "edit":
        return {
            "status": "ok",
            "mode": "edit-replay",
            "message": (
                "Found edit tool call. Content is the edit spec (not full file). "
                "Use this to replay the edits."
            ),
            "target_file": target_entry["target_file"],
            "edit_spec": json.loads(content),
            "time": datetime.fromtimestamp(
                target_entry["timestamp"] / 1000
            ).strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Write content to file
    out_path = output or target_entry["target_file"]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

    return {
        "status": "ok",
        "recovered_from": {
            "session": target_entry["session_id"],
            "tool": target_entry["tool"],
            "original_target": target_entry["target_file"],
            "time": datetime.fromtimestamp(
                target_entry["timestamp"] / 1000
            ).strftime("%Y-%m-%d %H:%M:%S"),
        },
        "output": os.path.abspath(out_path),
        "lines": lines,
        "bytes": len(content.encode("utf-8")),
    }
