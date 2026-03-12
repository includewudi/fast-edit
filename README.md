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
- **Code generation**: Execute code to generate file content, achieving 5x+ token compression for bulk file creation
- **End-to-end timing**: Built-in timer tracks total elapsed time from skill load to task completion, including AI thinking time

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

## Use with OpenCode (Replace Built-in Edit/Write)

Fast Edit can be installed as an [OpenCode](https://github.com/anthropics/opencode) skill to **completely replace the built-in Edit and Write tools**. Two integration methods are available:

| Method | How It Works | Setup Effort | Transparency |
|--------|-------------|--------------|--------------|
| **A: Rules-based** | AI reads rules → loads skill → uses `fe` commands via Bash | Add rules block | AI explicitly calls fast-edit |
| **B: Custom Tool Overlay** | Custom tools override built-in Edit/Write → fast-edit runs under the hood | Copy 2 files | Fully transparent — AI uses Edit/Write as usual |

### Method A: Rules-based (Explicit)

#### Step 1: Install the skill

```bash
# Clone to your skills directory
git clone https://github.com/includewudi/fast-edit.git ~/.config/opencode/skills/fast-edit
```

#### Step 2: Add to your OpenCode rules

Add the following to your project's `.opencode/rules` or global rules file (`~/.config/opencode/rules`):

```
[FAST-EDIT]
When you need to edit, create, write, or save files:
1. Load the fast-edit skill first: skill("fast-edit")
2. Use fast-edit commands (show/replace/insert/delete/batch/paste/write/generate) instead of the built-in Edit/Write tools.
3. For batch edits or multi-file writes, prefer fast-batch and fast-write.
4. For user-pasted content, prefer save-pasted (zero token, zero escaping).
Fast-edit is 100x faster than built-in tools. NEVER use Edit/Write when fast-edit can do the job.
Trigger: any intent to create, modify, save, or write a file.
```

**Optional: Enable debug timing**

Add `debug-timer: true` to the rules block to enable end-to-end timing. When enabled, the AI will automatically run `fe timer start` on skill load and attach `--timer` to generate commands, reporting total elapsed time (including AI thinking time) in the output.

```
debug-timer: true
```

#### What changes for the AI agent?

| Operation | Before (built-in) | After (fast-edit) |
|-----------|-------------------|-------------------|
| Edit a file | `Edit` tool → string match → LSP wait | `fe replace` / `fe batch` → instant |
| Create a file | `Write` tool → full content output | `fe paste --stdin` or `fe fast-generate` |
| Multiple edits | 3× Edit calls (~15s) | 1× `fe batch` (<0.1s) |
| Large file (200+ lines) | Write full content (token limit) | `fe fast-generate` (~70 lines code → 300+ lines output) |
| Save user paste | Write tool + escape headaches | `fe save-pasted` (zero token) |

The AI agent loads the skill once per session, then all file operations go through fast-edit automatically.

### Method B: Custom Tool Overlay (Seamless)

Method B replaces OpenCode's built-in Edit and Write tools at the tool level. The AI doesn't need to know about fast-edit — it calls Edit/Write as usual, and fast-edit runs transparently under the hood.

#### How It Works: Description-Based Routing

OpenCode exposes each tool's `description` string to the AI as part of the tool schema. The AI reads the description to decide **when** and **how** to use the tool. Custom tools (TypeScript files in `~/.config/opencode/tools/`) override same-named built-in tools completely — including their descriptions.

Our custom tools modify the descriptions with routing hints:

**Built-in Edit description** (simplified):
> Performs exact string replacements in files. The oldString must match exactly...

**Custom Edit description** (with fast-edit routing):
> Performs exact string replacements in files. ...
> **STOP: If you need to replace a large block (>80 lines)** with repetitive/structured content, do NOT output the full newString here — you will waste tokens. Instead: `skill('fast-edit')`, then use `fe fast-batch --stdin` or `fe fast-generate` via Bash.

**Built-in Write description** (simplified):
> Writes a file to the local filesystem. Overwrites existing files...

**Custom Write description** (with fast-edit routing):
> Writes a file to the local filesystem. ...
> **STOP: For NEW files >150 lines** with repetitive/structured content, do NOT use this tool — you will waste tokens. Instead: `skill('fast-edit')`, then `fe fast-generate --stdin -o FILE` with ≤80 lines of Python generator code.

#### Routing Flow

```
AI task: edit or write a file
  │
  ├─ Small edit (<80 lines)
  │    → AI calls Edit tool
  │    → edit.ts intercepts: oldString → findLineRange → fe fast-batch --stdin
  │    → Result returned to AI (transparent)
  │
  ├─ Small write (<150 lines)
  │    → AI calls Write tool
  │    → write.ts intercepts: content → fe fast-paste --stdin
  │    → Result returned to AI (transparent)
  │
  ├─ Large edit (>80 lines, structured)
  │    → AI reads Edit description → sees STOP hint
  │    → AI loads skill('fast-edit') → uses fe fast-generate via Bash
  │
  └─ Large write (>150 lines, structured)
       → AI reads Write description → sees STOP hint
       → AI loads skill('fast-edit') → uses fe fast-generate via Bash
```

#### Step 1: Install the skill

```bash
git clone https://github.com/includewudi/fast-edit.git ~/.config/opencode/skills/fast-edit
```

#### Step 2: Copy custom tools

```bash
cp ~/.config/opencode/skills/fast-edit/opencode-tools/*.ts ~/.config/opencode/tools/
```

This installs two files:
- `edit.ts` — Overrides built-in Edit. Translates string-match edits into `fe fast-batch` line-number operations.
- `write.ts` — Overrides built-in Write. Delegates file writes to `fe fast-paste --stdin`.

#### Step 3 (Optional): Add rules for large file support

Method B handles small/medium edits transparently. For large file generation (>150 lines), the description hints tell the AI to load the skill. You can optionally add a minimal rules block to reinforce this:

```
[FAST-EDIT]
For user-pasted content, prefer save-pasted (zero token, zero escaping).
```

No `skill("fast-edit")` trigger needed — the custom tools handle routing automatically.

#### What the AI Experiences

| Operation | What AI Does | What Actually Happens |
|-----------|-------------|----------------------|
| Edit a file | Calls Edit tool normally | `edit.ts` → `fe fast-batch` (instant, with backup) |
| Write a file | Calls Write tool normally | `write.ts` → `fe fast-paste` (with backup) |
| Write >150 lines | Sees STOP hint in description | AI loads skill, uses `fe fast-generate` |
| Edit >80 lines | Sees STOP hint in description | AI loads skill, uses `fe fast-batch`/`fe fast-generate` |

## Quick Start

```bash
# Define function for convenience
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }

# Show lines 1-10
fe show myfile.py 1 10

# Replace lines 5-7
fe replace myfile.py 5 7 "new content\n"

# Insert after line 3
fe insert myfile.py 3 "inserted line\n"

# Delete lines 8-10
fe delete myfile.py 8 10

# Batch edit
fe batch edit_spec.json

# Paste from stdin
echo "print('hello')" | fe paste output.py --stdin

# Write multiple files
fe write files_spec.json

# Type check
fe check myfile.py

# Generate file from code
echo 'import json; print(json.dumps({"key": "value"}))' | fe generate --stdin -o output.json

# Generate multiple files from code
python3 gen_script.py | fe generate --stdin

# Start end-to-end timer
fe timer start
```

## Commands

### `show FILE START END`

Display lines with line numbers.

```bash
fe show script.py 10 20
```

### `replace FILE START END CONTENT`

Replace a line range with new content.

```bash
fe replace script.py 5 7 "def new_function():\n    pass\n"
```

- Line numbers are 1-based and inclusive
- Use `\n` for newlines
- Content is expanded (e.g., `\n` becomes newline, `\t` becomes tab)

### `insert FILE LINE CONTENT`

Insert content after a specific line.

```bash
fe insert script.py 10 "import logging\n"
```

- Use `LINE=0` to insert at the beginning of the file

### `delete FILE START END`

Delete a line range.

```bash
fe delete script.py 15 20
```

### `batch [--stdin] [SPEC]`

Apply multiple edits in a single operation.

```bash
# From JSON file
fe batch edits.json

# From stdin
echo '{"file":"a.py","edits":[...]}' | fe batch --stdin
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
fe paste output.py

# From stdin
echo "print('hello')" | fe paste output.py --stdin

# Extract markdown code block
fe paste output.py --stdin --extract << 'EOF'
Here's some code:
```python
def hello():
    print("world")
```
EOF

# Decode base64 content (useful for special characters)
echo "cHJpbnQoJ2hlbGxvJyk=" | fe paste output.py --stdin --base64
```

- `--extract`: Automatically extract content from ````python`...```` code blocks
- `--base64`: Decode base64-encoded content before writing

### `write [--stdin] [SPEC]`

Create multiple files from a JSON specification.

```bash
# From JSON file
fe write files.json

# From stdin
fe write --stdin << 'EOF'
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
fe check myfile.py

# Use specific checker
fe check myfile.py --checker mypy
```

Auto-detection order: `basedpyright` → `pyright` → `mypy`

### `timer start` / `timer stop TIMER_ID`

Track end-to-end elapsed time, including AI thinking time.

```bash
# Start a timer (returns a timer_id)
fe timer start
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "started_at": "2025-01-01T12:00:00.000000"}

# Stop and get total elapsed time
fe timer stop t_a1b2c3d4
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "elapsed_sec": 42.5}
```

When used with `generate --timer`, the timing output includes both script execution time (`elapsed_sec`) and total time from timer start (`total_elapsed_sec`). This captures the full cycle: skill load → AI reasoning → code execution → file write.

Timer data is stored in `/tmp/fe-timers/` and cleaned up on stop.

### `generate [--stdin] [-o FILE] [SCRIPT] [--timeout N] [--interpreter CMD] [--no-validate]`

Execute code and write stdout output as file content. Solves the AI output token bottleneck for bulk file generation.

```bash
# Single file: code stdout → one file
echo 'import json; print(json.dumps({"data": [1,2,3]}))' | fe generate --stdin -o output.json

# Multi-file: code stdout must be JSON spec
python3 gen_files.py | fe generate --stdin

# Script file mode
fe generate script.py -o output.json

# With options
fe generate --stdin -o out.json --timeout 60 --interpreter python3.12 --no-validate
```

**Two modes:**

1. **Single-file** (`-o FILE`): Script stdout is written directly to the target file
2. **Multi-file** (no `-o`): Script stdout must be JSON: `{"files": [{"file": "path", "content": "..."}]}`

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--stdin` | Read code from stdin | - |
| `-o FILE` | Single-file output target | Multi-file mode |
| `--timeout N` | Execution timeout in seconds | 30 |
| `--interpreter CMD` | Command to run the code | `python3` |
| `--no-validate` | Skip JSON validation for .json files | Validate |
| `--timer ID` | Attach a timer (from `fe timer start`) for end-to-end timing | - |

**Why use generate?** When AI needs to create large files (200+ lines), the LLM output token limit becomes the bottleneck. All file-writing tools require the LLM to output full content. `generate` lets the LLM write compact code (~70 lines) that *generates* the content (~375+ lines) — a 5x+ compression ratio.

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
| AI generates large/bulk files (200+ lines) | `generate --stdin -o FILE` or `generate --stdin` |
| Measure end-to-end task time (incl. AI thinking) | `timer start` → work → `generate --timer ID` |

## Typical Workflows

### User pastes code to input field

```
User: Save this to /tmp/app.py
```python
def main():
    print("hello")
```

AI executes:
echo '<user content>' | fe paste /tmp/app.py --stdin --extract
```

### User pastes code with special characters (recommended)

When code contains quotes, `$variables`, backslashes, etc., use base64 to avoid shell escaping issues:

```bash
# User pastes: print('hello $USER')
# AI base64-encodes first, then passes to fast-edit
echo -n "print('hello \$USER')" | base64 | xargs -I{} sh -c 'echo {} | fe paste /tmp/app.py --stdin --base64'
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
fe write --stdin << 'EOF'
{"files": [
  {"file": "file1.py", "content": "def a(): pass\n"},
  {"file": "file2.py", "content": "def b(): pass\n"}
]}
EOF
```

### AI generates large files using code

When AI needs to create files with 200+ lines, use `generate` to achieve 5x+ token compression:

```bash
# AI writes ~30 lines of Python, generates 200+ lines of output
python3 << 'PYEOF' | fe generate --stdin -o /path/to/config.json
import json

config = {
    "items": [
        {"id": i, "name": f"Item {i}", "settings": {"enabled": True, "priority": i % 3}}
        for i in range(1, 101)
    ]
}
print(json.dumps(config, indent=2))
PYEOF
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
├── fast_edit.py   # CLI entry point
├── core.py        # File I/O operations
├── edit.py        # Edit operations (show, replace, insert, delete, batch)
├── paste.py       # Paste/write operations
├── pasted.py      # OpenCode storage extraction
├── generate.py    # Code generation → file writing
├── check.py       # Type checking
├── verify.py      # Verify/backup/restore/syntax check
├── timer.py       # End-to-end timing (timer start/stop)
├── opencode-tools/  # Custom tool overlays for OpenCode (edit.ts, write.ts)
├── skill.md       # Detailed usage documentation (Chinese)
├── TEST_PLAN.md   # Test plan and results
├── requirements.txt  # Optional dependencies
├── .gitignore
├── README.md
└── README_CN.md
```

## Testing

Run the test plan:

```bash
# View test plan
cat TEST_PLAN.md

# Run tests manually
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }
TEST_DIR="/tmp/fast-edit-test"
mkdir -p $TEST_DIR

# ... follow TEST_PLAN.md ...
```

## Verification

**Recommended**: After editing, use `lsp_diagnostics` to check for type errors (if LSP is available).

**Alternative**: If LSP is not available, use fast-edit's built-in check command:

```bash
fe check /path/to/edited_file.py
```

| Method | Pros | Cons |
|--------|------|------|
| `lsp_diagnostics` | Fast (LSP warm start), supports all languages | Requires LSP server running |
| `fe check` | Standalone, no dependencies | Python only, cold startup slower |

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

[wudi](https://github.com/includewudi)
