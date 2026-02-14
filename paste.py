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
    try:
        if sys.platform == "darwin":
            cmd = ["pbpaste"]
        else:
            cmd = ["xclip", "-selection", "clipboard", "-o"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout
    except Exception:
        return None


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
    
    return {
        "status": "ok",
        "file": os.path.abspath(filepath),
        "lines": len(content.splitlines()),
        "bytes": len(content.encode("utf-8"))
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
    file_specs = spec.get("files", [spec])
    results = []
    
    for file_spec in file_specs:
        filepath = file_spec["file"]
        content = file_spec.get("content", "")
        encoding = file_spec.get("encoding")
        
        content = decode_content(content, encoding)
        
        if file_spec.get("extract", False):
            content = extract_code_blocks(content)
        
        write_file(filepath, content)
        
        results.append({
            "file": os.path.abspath(filepath),
            "lines": len(content.splitlines()),
            "bytes": len(content.encode("utf-8"))
        })
    
    return {
        "status": "ok",
        "files": len(results),
        "results": results
    }
