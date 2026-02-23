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
    save-pasted FILE [--min-lines N] [--msg-id ID] [--extract] [--nth N]
    verify FILE [--context N]          Compare file with backup
    restore FILE                       Restore file from backup
    backups FILE                       List all backups for file
    verify-syntax FILE                 Run language-aware syntax check

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
import pasted
import check
import verify


def print_help():
    """Print help with command examples (for AI to read correctly)."""
    print("""
fast_edit - AI file editing tool with line-number addressing
COMMANDS (all support fast-* prefix, e.g. fast-write, fast-paste):
  show FILE START END
    Show lines with line numbers (1-based, inclusive)
    Example: $FE show myfile.py 10 20
    Replace line range with new content
    Example: $FE replace myfile.py 5 7 "new content\\n"
    Insert content after line (LINE=0 for prepend)
    Example: $FE insert myfile.py 10 "import os\\n"
    Delete line range
    Example: $FE delete myfile.py 15 20
    Batch edit from JSON (multiple edits in one call)
    Example: $FE fast-batch --stdin <<< '{"file":"a.py","edits":[...]}'
  paste FILE [--stdin] [--extract] [--base64]
    Save content from clipboard/stdin to file
    Example: echo "code" | $FE fast-paste output.py --stdin
  write [--stdin] [SPEC]
    Batch write multiple files from JSON
    Example: $FE fast-write --stdin <<< '{"files":[{"file":"a.py","content":"..."}]}'
  check FILE [--checker NAME]
    Type check Python file (auto-detect: basedpyright/pyright/mypy)
    Example: $FE check myfile.py
    Save pasted content from OpenCode storage (for large pastes)
    Example: $FE save-pasted /tmp/file.py
  help
    Show this help message
  - Line numbers are 1-based and inclusive
  - Use \\n for newlines in content
  - Output is always JSON format
  - Use fast-* prefix to avoid shell builtin conflicts (write/paste/batch)
""")


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
    
    if not args or args[0] == "help":
        print_help()
        sys.exit(0)
    
    cmd = args[0]
    rest = args[1:]
    
    try:
        # Show lines
        if cmd in ("show", "fast-show") and len(rest) >= 3:
            result = edit.show(rest[0], int(rest[1]), int(rest[2]))
        
        # Replace lines
        elif cmd in ("replace", "fast-replace") and len(rest) >= 4:
            result = edit.replace(
                rest[0], int(rest[1]), int(rest[2]), 
                parse_content(rest[3])
            )
        
        # Insert after line
        elif cmd in ("insert", "fast-insert") and len(rest) >= 3:
            result = edit.insert(rest[0], int(rest[1]), parse_content(rest[2]))
        
        # Delete lines
        elif cmd in ("delete", "fast-delete") and len(rest) >= 3:
            result = edit.delete(rest[0], int(rest[1]), int(rest[2]))
        
        # Batch edit
        elif cmd in ("batch", "fast-batch"):
            if "--stdin" in rest:
                spec = json.load(sys.stdin)
            else:
                spec = json.load(open(rest[0]))
            result = edit.batch(spec)
        
        # Paste from clipboard/stdin
        elif cmd in ("paste", "fast-paste") and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            encoding = "base64" if "--base64" in rest else None
            result = paste.paste(
                filepath,
                from_stdin="--stdin" in rest,
                extract="--extract" in rest,
                encoding=encoding
            )
        
        # Write files from JSON
        elif cmd in ("write", "fast-write"):
            if "--stdin" in rest:
                spec = json.load(sys.stdin)
            else:
                spec = json.load(open(rest[0]))
            result = paste.write(spec)
        
        # Type check
        elif cmd in ("check", "fast-check") and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            checker = get_arg(rest, "--checker")
            result = check.check(filepath, checker)
        
        # Save pasted content from OpenCode storage
        elif cmd in ("save-pasted", "fast-save-pasted") and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            min_lines_str = get_arg(rest, "--min-lines")
            min_lines = int(min_lines_str) if min_lines_str else 20
            msg_id = get_arg(rest, "--msg-id")
            nth_str = get_arg(rest, "--nth")
            nth = int(nth_str) if nth_str else 1
            result = pasted.save_pasted(
                filepath,
                min_lines=min_lines,
                msg_id=msg_id,
                extract="--extract" in rest,
                nth=nth,
            )

        # Verify: compare with backup
        elif cmd in ("verify", "fast-verify") and rest:
            filepath = [x for x in rest if not x.startswith("--")][0]
            context = int(get_arg(rest, "--context") or 1)
            result = verify.verify(filepath, context)
        
        # Restore from backup
        elif cmd in ("restore", "fast-restore") and rest:
            result = verify.restore(rest[0])
        
        # List backups
        elif cmd in ("backups", "fast-backups") and rest:
            result = verify.list_backups(rest[0])
        
        # Syntax check (language-aware)
        elif cmd in ("verify-syntax", "fast-verify-syntax") and rest:
            result = verify.verify_syntax(rest[0])
        
        else:
            result = {"status": "error", "message": f"Unknown command: {cmd}"}
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        error = {"status": "error", "message": str(e)}
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
