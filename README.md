# Fast Edit

[English](README.md) | [中文](README_CN.md)

A fast, line-number-based file editing tool designed to bypass LSP latency, permission prompts, and history database overhead. Ideal for AI-assisted editing workflows.

## Motivation

If you've used AI coding tools like Cursor, Claude Code, or OpenCode, you've probably experienced this:

> AI says "Let me edit this file", and then you wait…
>
> 3 seconds… 5 seconds… 10 seconds…
>
> Finally done, but there are two more places to change.
>
> Another 10 seconds… another 10 seconds…

A simple three-location fix shouldn't take 30 seconds. Here's why the built-in Edit tool is slow:

1. **String matching overhead** — AI must output both the old and new content as full strings. For a 500-line file with 3 edits, that's potentially thousands of tokens.
2. **LSP synchronization** — After each edit, the editor waits for the Language Server to sync and check types. This typically takes 1–5 seconds per call.
3. **Multiple round-trips** — 3 edits = 3 separate Edit calls, each with network latency + LSP wait.

**Fast Edit takes a fundamentally different approach**: line-number addressing instead of string matching, batch operations instead of repeated calls, and direct file I/O that bypasses LSP entirely. The result? **100x faster editing** — a 500-line file with 3 edits drops from ~15 seconds to under 0.1 seconds.

## Features

- **Line-number editing**: Show, replace, insert, and delete specific line ranges
- **Batch operations**: Apply multiple edits to a file in a single JSON request
- **Clipboard/stdin support**: Paste content from clipboard or stdin, with markdown code block extraction and base64 decoding
- **Multi-file writing**: Create multiple files from a single JSON specification
- **Type checking**: Auto-detects and runs available Python type checkers (basedpyright, pyright, mypy)
- **Zero external dependencies**: Pure Python, uses only standard library

## Installation

```bash
# Clone the repository
git clone https://github.com/includewudi/fast-edit.git
cd fast-edit

# No installation required - just run the script
python3 fast_edit.py
```

For type checking support, optionally install one of:
```bash
pip install basedpyright  # Recommended (fastest)
# or
pip install pyright
# or
pip install mypy
```

## Quick Start

```bash
# Set alias for convenience
export FE="python3 /path/to/fast-edit/fast_edit.py"

# Show lines 1-10
$FE show myfile.py 1 10

# Replace lines 5-7
$FE replace myfile.py 5 7 "new content\n"

# Insert after line 3
$FE insert myfile.py 3 "inserted line\n"

# Delete lines 8-10
$FE delete myfile.py 8 10

# Batch edit
$FE batch edit_spec.json

# Paste from stdin
echo "print('hello')" | $FE paste output.py --stdin

# Write multiple files
$FE write files_spec.json

# Type check
$FE check myfile.py
```

## Commands

### `show FILE START END`

Display lines with line numbers.

```bash
$FE show script.py 10 20
```

### `replace FILE START END CONTENT`

Replace a line range with new content.

```bash
$FE replace script.py 5 7 "def new_function():\n    pass\n"
```

- Line numbers are 1-based and inclusive
- Use `\n` for newlines
- Content is expanded (e.g., `\n` becomes newline, `\t` becomes tab)

### `insert FILE LINE CONTENT`

Insert content after a specific line.

```bash
$FE insert script.py 10 "import logging\n"
```

- Use `LINE=0` to insert at the beginning of the file

### `delete FILE START END`

Delete a line range.

```bash
$FE delete script.py 15 20
```

### `batch [--stdin] [SPEC]`

Apply multiple edits in a single operation.

```bash
# From JSON file
$FE batch edits.json

# From stdin
echo '{"file":"a.py","edits":[...]}' | $FE batch --stdin
```

**Batch JSON format:**

```json
{
  "file": "/path/to/file.py",
  "edits": [
    {
      "action": "replace-lines",
      "start": 10,
      "end": 12,
      "content": "new content\n"
    },
    {
      "action": "insert-after",
      "line": 25,
      "content": "# comment\n"
    },
    {
      "action": "delete-lines",
      "start": 40,
      "end": 42
    }
  ]
}
```

For multiple files:

```json
{
  "files": [
    {
      "file": "a.py",
      "edits": [...]
    },
    {
      "file": "b.py",
      "edits": [...]
    }
  ]
}
```

### `paste FILE [--stdin] [--extract] [--base64]`

Save content to a file from clipboard or stdin.

```bash
# From clipboard (requires pbpaste on macOS, xclip on Linux)
$FE paste output.py

# From stdin
echo "print('hello')" | $FE paste output.py --stdin

# Extract markdown code block
$FE paste output.py --stdin --extract << 'EOF'
Here's some code:
```python
def hello():
    print("world")
```
EOF

# Decode base64 content (useful for special characters)
echo "cHJpbnQoJ2hlbGxvJyk=" | $FE paste output.py --stdin --base64
```

- `--extract`: Automatically extract content from ````python`...```` code blocks
- `--base64`: Decode base64-encoded content before writing

### `write [--stdin] [SPEC]`

Create multiple files from a JSON specification.

```bash
# From JSON file
$FE write files.json

# From stdin
$FE write --stdin << 'EOF'
{
  "files": [
    {
      "file": "/tmp/a.py",
      "content": "def a():\n    pass\n"
    },
    {
      "file": "/tmp/b.py",
      "content": "```python\ndef b(): pass\n```",
      "extract": true
    },
    {
      "file": "/tmp/c.py",
      "content": "ZGVmIGMoKTogcGFzcwo=",
      "encoding": "base64"
    }
  ]
}
EOF
```

**Write JSON format:**

- `file`: Path to the file to create
- `content`: Content to write
- `extract` (optional): If `true`, extract content from markdown code blocks
- `encoding` (optional): If `"base64"`, decode content before writing

### `check FILE [--checker NAME]`

Run type checker on a Python file.

```bash
# Auto-detect available checker
$FE check myfile.py

# Use specific checker
$FE check myfile.py --checker mypy
```

Auto-detection order: `basedpyright` → `pyright` → `mypy`

## Use Cases

| Scenario | Command |
|----------|---------|
| Small changes in large files (100+ lines) | `replace` / `batch` |
| Multiple edits in same file | `batch` |
| User pastes code into input field, save single file | `paste --stdin` |
| User pastes code with special characters | `paste --stdin --base64` |
| User pastes multiple code blocks, save multiple files | `write --stdin` |
| Save from clipboard | `paste` |
| Type check after editing | `check` |

## Typical Workflows

### User pastes code to input field

```
User: Save this to /tmp/app.py
```python
def main():
    print("hello")
```

AI executes:
echo '<user content>' | $FE paste /tmp/app.py --stdin --extract
```

### User pastes code with special characters (recommended)

When code contains quotes, `$variables`, backslashes, etc., use base64 to avoid shell escaping issues:

```bash
# User pastes: print('hello $USER')
# AI base64-encodes first, then passes to fast-edit
echo -n "print('hello \$USER')" | base64 | xargs -I{} sh -c 'echo {} | $FE paste /tmp/app.py --stdin --base64'
```

### User pastes multiple code blocks

```
User: Save these two files
file1.py:
```python
def a(): pass
```
file2.py:
```python
def b(): pass
```

AI constructs and executes:
$FE write --stdin << 'EOF'
{"files": [
  {"file": "file1.py", "content": "def a(): pass\n"},
  {"file": "file2.py", "content": "def b(): pass\n"}
]}
EOF
```

## Performance Comparison

| Scenario | Edit Tool | fast-edit |
|----------|-----------|-----------|
| 500-line file, 3 edits | ~15s (3 calls) | **<0.1s** (batch) |
| AI Token Output | old+new strings | **only line numbers + content** |
| LSP Wait | 0-5s per call | **0** |

## File Structure

```
fast-edit/
├── fast_edit.py   # CLI entry point (121 lines)
├── core.py        # File I/O operations
├── edit.py        # Edit operations (show, replace, insert, delete, batch)
├── paste.py       # Paste/write operations
├── check.py       # Type checking
├── skill.md       # Detailed usage documentation
├── TEST_PLAN.md   # Test plan and results
├── requirements.txt  # Optional dependencies
├── .gitignore
└── README.md
```

## Testing

Run the test plan:

```bash
# View test plan
cat TEST_PLAN.md

# Run tests manually
FE="python3 /path/to/fast-edit/fast_edit.py"
TEST_DIR="/tmp/fast-edit-test"
mkdir -p $TEST_DIR

# ... follow TEST_PLAN.md ...
```

## Verification

**Recommended**: After editing, use `lsp_diagnostics` to check for type errors (if LSP is available).

**Alternative**: If LSP is not available, use fast-edit's built-in check command:

```bash
$FE check /path/to/edited_file.py
```

| Method | Pros | Cons |
|--------|------|------|
| `lsp_diagnostics` | Fast (LSP warm start), supports all languages | Requires LSP server running |
| `$FE check` | Standalone, no dependencies | Python only, cold startup slower |

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

[wudi](https://github.com/includewudi)
