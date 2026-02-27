"""
Paste and write operations.
- paste: Save content from clipboard or stdin to a single file
- write: Batch write multiple files from JSON spec (zero-token creation)
"""
import sys
import os
import subprocess
import re
import base64
import time
from datetime import datetime
from core import write_file


def decode_content(content: str, encoding: str = None) -> str:
    """
    Decode content based on encoding type.
    
    Args:
        content: Raw content string
        encoding: Encoding type ('base64' or None for plain text)
    
    Returns:
        Decoded content string
    """
    if encoding == "base64":
        # Handle base64 with possible whitespace/newlines
        cleaned = content.strip().replace("\n", "").replace("\r", "")
        return base64.b64decode(cleaned).decode("utf-8")
    return content


def read_clipboard():
    """Read content from system clipboard (macOS/Linux)."""
    if sys.platform == "darwin":
        cmd = ["pbpaste"]
        tool_name = "pbpaste"
        install_hint = "pbpaste is built into macOS — it should always be available."
    elif sys.platform == "win32":
        raise EnvironmentError(
            "Clipboard reading is not supported on Windows. Use --stdin instead."
        )
    else:
        cmd = ["xclip", "-selection", "clipboard", "-o"]
        tool_name = "xclip"
        install_hint = "Install with: sudo apt install xclip (Debian/Ubuntu) or sudo pacman -S xclip (Arch)"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise EnvironmentError(
                f"{tool_name} failed (exit {result.returncode}): {stderr or 'no output'}. "
                f"Use --stdin as alternative."
            )
        return result.stdout
    except FileNotFoundError:
        raise EnvironmentError(
            f"Clipboard tool '{tool_name}' not found. {install_hint} "
            f"Or use --stdin to read from stdin instead."
        )
    except subprocess.TimeoutExpired:
        raise EnvironmentError(
            f"{tool_name} timed out after 5s. Clipboard may be locked. "
            f"Use --stdin as alternative."
        )


def extract_code_blocks(text):
    """
    Extract content from fenced code blocks (```...```).
    Returns original text if no code blocks found.
    
    Regex pattern matches: ```lang\ncontent``` or ```\ncontent```
    """
    pattern = r"```[\w]*\n?([\s\S]*?)```"
    blocks = re.findall(pattern, text)
    if blocks:
        return "\n".join(blocks)
    return text


def paste(filepath, from_stdin=False, extract=False, encoding=None):
    """
    Save content to file from clipboard or stdin.
    
    Args:
        filepath: Target file path
        from_stdin: Read from stdin instead of clipboard
        extract: Extract code from ```...``` blocks
        encoding: Content encoding ('base64' or None)
    """
    start_time = time.time()
    start_dt = datetime.now().isoformat()
    
    if from_stdin:
        content = sys.stdin.read()
    else:
        content = read_clipboard()
    
    if not content or not content.strip():
        raise ValueError("No content (clipboard/stdin empty)")
    
    content = decode_content(content, encoding)
    
    if extract:
        content = extract_code_blocks(content)
    
    write_file(filepath, content)
    
    end_time = time.time()
    end_dt = datetime.now().isoformat()
    elapsed_sec = round(end_time - start_time, 4)
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "lines": len(content.splitlines()),
        "bytes": len(content.encode("utf-8")),
        "timing": {
            "start": start_dt,
            "end": end_dt,
            "elapsed_sec": elapsed_sec
        }
    }


def write(spec):
    """
    Write multiple files from JSON spec.
    Useful for zero-token file creation when user pastes content to input.
    
    JSON format:
        Single file:  {"file": "/path/to/file", "content": "...", "extract": false, "encoding": "base64"}
        Multi file:   {"files": [{"file": "...", "content": "...", "extract": false, "encoding": "base64"}, ...]}
    
    Args:
        spec: JSON spec with file(s) to write
    """
    start_time = time.time()
    start_dt = datetime.now().isoformat()
    file_specs = spec.get("files", [spec])
    results = []
    for file_spec in file_specs:
        file_start_time = time.time()
        filepath = file_spec["file"]
        content = file_spec.get("content", "")
        encoding = file_spec.get("encoding")
        content = decode_content(content, encoding)
        if file_spec.get("extract", False):
            content = extract_code_blocks(content)
        write_file(filepath, content)
        file_end_time = time.time()
        file_elapsed_sec = round(file_end_time - file_start_time, 4)
        results.append({
            "file": os.path.abspath(filepath),
            "lines": len(content.splitlines()),
            "bytes": len(content.encode("utf-8")),
            "elapsed_sec": file_elapsed_sec
        })
    
    end_time = time.time()
    end_dt = datetime.now().isoformat()
    total_elapsed_sec = round(end_time - start_time, 4)
    return {
        "status": "ok",
        "files": len(results),
        "results": results,
        "timing": {
            "start": start_dt,
            "end": end_dt,
            "elapsed_sec": total_elapsed_sec
        }
    }