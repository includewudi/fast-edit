"""
Generate files by executing code and writing stdout as file content.

Solves the "AI output token bottleneck" for bulk file generation:
- AI writes ~70 lines of compact Python code
- Code generates ~375+ lines of file content
- fast-generate executes the code and writes the output to files

Two modes:
1. Single-file: code stdout → one file
2. Multi-file:  code stdout must be JSON {"files": [{"file": "...", "content": "..."}]}

Features:
- Atomic writes (temp+rename) via core.write_file
- Auto-creates directories
- JSON validation for .json files
- Timeout protection (default 30s)
- Captures stderr for error reporting
"""
import sys
import os
import json
import subprocess
import time
from datetime import datetime
from core import write_file
import timer as timer_mod


def generate(
    script_path=None,
    code=None,
    output_file=None,
    interpreter="python3",
    timeout=30,
    validate_json=True,
    timer_id=None,
):
    """
    Execute a script/code and write its stdout output to file(s).

    Args:
        script_path: Path to script file to execute (mutually exclusive with code)
        code: Inline code string to execute via stdin (mutually exclusive with script_path)
        output_file: Target file path. If None, stdout must be JSON multi-file spec.
        interpreter: Command to run the code (default: python3)
        timeout: Max execution time in seconds (default: 30)
        validate_json: Auto-validate .json output files (default: True)

    Returns:
        JSON result with status, files written, timing info.
    """
    start_time = time.time()
    start_dt = datetime.now().isoformat()

    if script_path and code:
        raise ValueError("Cannot specify both script_path and code")
    if not script_path and not code:
        raise ValueError("Must specify either script_path or code")

    # Build command
    if script_path:
        abs_script = os.path.abspath(script_path)
        if not os.path.isfile(abs_script):
            raise FileNotFoundError(f"Script not found: {abs_script}")
        cmd = [interpreter, abs_script]
        stdin_data = None
    else:
        cmd = [interpreter, "-"]
        stdin_data = code

    # Execute
    try:
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": f"Script timed out after {timeout}s",
            "timing": _timing(start_time, start_dt, timer_id),
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"Interpreter not found: {interpreter}",
            "timing": _timing(start_time, start_dt, timer_id),
        }

    if result.returncode != 0:
        return {
            "status": "error",
            "message": "Script execution failed",
            "exit_code": result.returncode,
            "stderr": result.stderr.strip()[:4000],
            "stdout": result.stdout.strip()[:1000],
            "timing": _timing(start_time, start_dt, timer_id),
        }

    stdout = result.stdout
    stderr = result.stderr.strip()

    # Mode 1: Single file output
    if output_file:
        return _write_single(output_file, stdout, validate_json, stderr, start_time, start_dt, timer_id)

    return _write_multi(stdout, validate_json, stderr, start_time, start_dt, timer_id)


def _write_single(output_file, content, validate_json, stderr, start_time, start_dt, timer_id=None):
    """Write stdout content to a single file."""
    abs_path = os.path.abspath(output_file)

    # Validate JSON if applicable
    if validate_json and abs_path.endswith(".json"):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"Generated content is not valid JSON: {e}",
                "file": abs_path,
                "timing": _timing(start_time, start_dt, timer_id),
            }

    write_file(abs_path, content)

    file_result = {
        "file": abs_path,
        "lines": len(content.splitlines()),
        "bytes": len(content.encode("utf-8")),
    }

    return {
        "status": "ok",
        "mode": "single",
        "files": 1,
        "results": [file_result],
        "stderr": stderr if stderr else None,
        "timing": _timing(start_time, start_dt, timer_id),
    }


def _write_multi(stdout, validate_json, stderr, start_time, start_dt, timer_id=None):
    """Parse stdout as JSON file spec and write multiple files."""
    try:
        spec = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "message": f"Script stdout is not valid JSON (multi-file mode requires JSON output): {e}",
            "stdout_preview": stdout[:500],
            "timing": _timing(start_time, start_dt, timer_id),
        }

    # Accept both {"files": [...]} and [{"file": ..., "content": ...}]
    if isinstance(spec, list):
        file_specs = spec
    elif isinstance(spec, dict) and "files" in spec:
        file_specs = spec["files"]
    else:
        return {
            "status": "error",
            "message": 'Multi-file JSON must be {"files": [...]} or a list of {"file": "...", "content": "..."}',
            "timing": _timing(start_time, start_dt, timer_id),
        }

    results = []
    errors = []

    for i, fspec in enumerate(file_specs):
        filepath = fspec.get("file")
        content = fspec.get("content", "")

        if not filepath:
            errors.append({"index": i, "error": "Missing 'file' field"})
            continue

        abs_path = os.path.abspath(filepath)

        # Validate JSON content if applicable
        if validate_json and abs_path.endswith(".json"):
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                errors.append({
                    "index": i,
                    "file": abs_path,
                    "error": f"Content is not valid JSON: {e}",
                })
                continue

        write_file(abs_path, content)

        results.append({
            "file": abs_path,
            "lines": len(content.splitlines()),
            "bytes": len(content.encode("utf-8")),
        })

    result = {
        "status": "ok" if not errors else "partial",
        "mode": "multi",
        "files": len(results),
        "results": results,
        "stderr": stderr if stderr else None,
        "timing": _timing(start_time, start_dt, timer_id),
    }

    if errors:
        result["errors"] = errors

    return result


def _timing(start_time, start_dt, timer_id=None):
    end_time = time.time()
    result = {
        "start": start_dt,
        "end": datetime.now().isoformat(),
        "elapsed_sec": round(end_time - start_time, 4),
    }
    if timer_id:
        timer_data = timer_mod.elapsed(timer_id)
        if timer_data:
            timer_start_epoch, timer_start_iso = timer_data
            result["timer_id"] = timer_id
            result["timer_start"] = timer_start_iso
            result["total_elapsed_sec"] = round(end_time - timer_start_epoch, 3)
    return result
