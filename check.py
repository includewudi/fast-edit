"""
Type checking for Python files.
Auto-detects available checker: basedpyright > pyright > mypy
"""
import os
import subprocess
import re


CHECKERS = [
    ("basedpyright", ["basedpyright", "--version"]),
    ("pyright", ["pyright", "--version"]),
    ("mypy", ["mypy", "--version"]),
]


def find_checker():
    """Find first available type checker."""
    for name, version_cmd in CHECKERS:
        try:
            subprocess.run(version_cmd, capture_output=True, timeout=5)
            return name
        except Exception:
            continue
    return None


def parse_output(output, filepath):
    """Parse checker output into structured diagnostics."""
    diagnostics = []
    basename = os.path.basename(filepath)
    
    for line in output.split("\n"):
        # Skip lines not about our file
        if filepath not in line and basename not in line:
            continue
        
        # Extract line:col from output
        match = re.search(r":(\d+):(\d+)?", line)
        if not match:
            continue
        
        line_num = int(match.group(1))
        col = int(match.group(2)) if match.group(2) else 1
        
        # Determine severity
        severity = "error" if "error" in line.lower() else "warning"
        
        # Extract message
        if " - " in line:
            message = line.split(" - ", 1)[-1]
        else:
            message = line.split(": ", 1)[-1]
        
        diagnostics.append({
            "line": line_num,
            "col": col,
            "severity": severity,
            "message": message.strip()
        })
    
    return diagnostics


def check(filepath, checker=None):
    """
    Run type checker on Python file.
    
    Args:
        filepath: Path to Python file
        checker: Specific checker to use (auto-detect if None)
    
    Returns:
        Dict with status, checker used, error/warning counts, and diagnostics
    """
    abs_path = os.path.abspath(filepath)
    
    # Validate file exists
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")
    
    # Skip non-Python files
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".py", ".pyi"):
        return {
            "status": "ok",
            "file": abs_path,
            "message": f"Type checking not supported for {ext} files"
        }
    
    # Find checker
    if not checker:
        checker = find_checker()
    
    if not checker:
        return {
            "status": "ok",
            "file": abs_path,
            "message": "No type checker found (install basedpyright, pyright, or mypy)"
        }
    
    # Build command
    if checker == "mypy":
        cmd = [checker, "--no-error-summary", abs_path]
    else:
        cmd = [checker, abs_path]
    
    # Run checker
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(abs_path) or "."
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "file": abs_path,
            "checker": checker,
            "message": "Type checker timed out after 60s"
        }
    except Exception as e:
        return {
            "status": "error",
            "file": abs_path,
            "checker": checker,
            "message": f"Failed to run checker: {e}"
        }
    
    # Parse output
    diagnostics = parse_output(output, filepath)
    errors = sum(1 for d in diagnostics if d["severity"] == "error")
    warnings = len(diagnostics) - errors
    
    return {
        "status": "ok",
        "file": abs_path,
        "checker": checker,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics
    }
