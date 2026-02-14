#!/usr/bin/env python3
"""
fast_edit — AI file editing tool with line-number addressing.

Commands:
    show FILE START END              Show lines with line numbers
    replace FILE START END CONTENT   Replace line range
    insert FILE LINE CONTENT         Insert after line (0=prepend)
    delete FILE START END            Delete line range
    batch [--stdin] [SPEC]           Batch edit from JSON
    paste FILE [--stdin] [--extract] [--base64]  Save from clipboard/stdin
    write [--stdin] [SPEC]           Batch write files from JSON
    check FILE [--checker NAME]      Type check Python file

Line numbers: 1-based, inclusive. Output: JSON.
"""
import sys
import os
import json

# Add script directory to path for sibling imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import edit
import paste
import check


def parse_content(text):
    """Parse CLI content argument, expanding escape sequences."""
    return text.replace("\\n", "\n").replace("\\t", "\t")


def get_arg(args, flag):
    """Get argument value after a flag, or None if not present."""
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except (ValueError, IndexError):
        return None


def main():
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        sys.exit(0)
    
    cmd = args[0]
    rest = args[1:]
    
    try:
        # Show lines
        if cmd == "show" and len(rest) >= 3:
            result = edit.show(rest[0], int(rest[1]), int(rest[2]))
        
        # Replace lines
        elif cmd == "replace" and len(rest) >= 4:
            result = edit.replace(
                rest[0], int(rest[1]), int(rest[2]), 
                parse_content(rest[3])
            )
        
        # Insert after line
        elif cmd == "insert" and len(rest) >= 3:
            result = edit.insert(rest[0], int(rest[1]), parse_content(rest[2]))
        
        # Delete lines
        elif cmd == "delete" and len(rest) >= 3:
            result = edit.delete(rest[0], int(rest[1]), int(rest[2]))
        
        # Batch edit
        elif cmd == "batch":
            if "--stdin" in rest:
                spec = json.load(sys.stdin)
            else:
                spec = json.load(open(rest[0]))
            result = edit.batch(spec)
        
        # Paste from clipboard/stdin
        elif cmd == "paste" and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            encoding = "base64" if "--base64" in rest else None
            result = paste.paste(
                filepath,
                from_stdin="--stdin" in rest,
                extract="--extract" in rest,
                encoding=encoding
            )
        
        # Write files from JSON
        elif cmd == "write":
            if "--stdin" in rest:
                spec = json.load(sys.stdin)
            else:
                spec = json.load(open(rest[0]))
            result = paste.write(spec)
        
        # Type check
        elif cmd == "check" and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            checker = get_arg(rest, "--checker")
            result = check.check(filepath, checker)
        
        else:
            result = {"status": "error", "message": f"Unknown command: {cmd}"}
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        error = {"status": "error", "message": str(e)}
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
