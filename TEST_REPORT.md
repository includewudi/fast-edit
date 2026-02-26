# Fast Edit — Test Report

> **Version**: v2 (with `generate` command)  
> **Date**: 2026-02-26  
> **Environment**: macOS (darwin), Python 3.x  
> **Result**: **37/37 PASS** ✅

## Summary

| Phase | Scope | Tests | Pass | Fail |
|-------|-------|-------|------|------|
| 1 — Core & Edit | show, replace, insert, delete, batch | 12 | 12 | 0 |
| 2 — Paste & Write | stdin paste, extract, base64, multi-file write | 5 | 5 | 0 |
| 3 — Generate | single/multi-file, timeout, validation, large file | 9 | 9 | 0 |
| 4 — Verify & Restore | diff, rollback, backups, syntax check | 5 | 5 | 0 |
| 5 — Edge Cases | unknown cmd, missing args, CRLF, unicode, prefix | 6 | 6 | 0 |
| **Total** | | **37** | **37** | **0** |

## Bugs Found & Fixed

### Test 33: Missing required args (FIXED)

**Bug**: `python3 fast_edit.py show` (no filepath) returned `"Unknown command: show"` instead of a helpful error.

**Root cause**: The CLI dispatcher in `fast_edit.py` used `and len(rest) >= N` guards on each command branch. When a known command was called with insufficient args, it fell through all branches to the catch-all `else`, which reported "Unknown command".

**Fix**: Replaced the catch-all `else` with a two-step check:
1. Look up the command (stripping `fast-` prefix) in a known-commands table
2. If found → return `"Missing arguments for {cmd}. Usage: {cmd} {usage}"`
3. If not found → return `"Unknown command: {cmd}"`

**Verification**: `show`, `fast-show`, `replace`, `fast-verify` all return proper usage messages when called without args. Unknown commands still report "Unknown command".

---

## Phase 1: Core & Edit (12 tests)

| # | Test | Expected | Status | Notes |
|---|------|----------|--------|-------|
| 1 | help command | Lists all commands including `generate` | ✅ PASS | |
| 2 | show basic | Shows lines 3-7 with line numbers | ✅ PASS | |
| 3 | show out-of-range | Clamps to 1-10, no error | ✅ PASS | |
| 4 | replace basic | Lines 2-3 replaced, total=4 | ✅ PASS | |
| 5 | backup created | `.fast-edit-backup` exists after replace | ✅ PASS | |
| 6 | DUPLICATE_LINE warning | `warnings` contains DUPLICATE_LINE | ✅ PASS | |
| 7 | BRACKET_BALANCE warning | `warnings` contains BRACKET_BALANCE | ✅ PASS | |
| 8 | insert at line 0 | "prepended" is first line | ✅ PASS | |
| 9 | insert in middle | "middle" after line 2 | ✅ PASS | |
| 10 | delete range | Only lines 1 and 5 remain | ✅ PASS | |
| 11 | batch single file | Edits applied correctly | ✅ PASS | * |
| 12 | batch multi-file | Both files edited | ✅ PASS | * |

\* Tests 11-12: Batch JSON requires `"action": "replace-lines"` (not `"type": "replace"`).

## Phase 2: Paste & Write (5 tests)

| # | Test | Expected | Status | Notes |
|---|------|----------|--------|-------|
| 13 | paste stdin basic | File contains "hello from stdin" | ✅ PASS | |
| 14 | paste extract | Only extracted code in file | ✅ PASS | |
| 15 | paste base64 | File contains "Hello World" (decoded) | ✅ PASS | |
| 16 | fast-write multi-file | Both files created | ✅ PASS | * |
| 17 | fast-write extract | Code block content extracted | ✅ PASS | * |

\* Tests 16-17: `fast-write --stdin` requires properly escaped JSON (`\\n` not shell-interpreted `\n`).

## Phase 3: Generate (9 tests)

| # | Test | Expected | Status | Notes |
|---|------|----------|--------|-------|
| 18 | single-file generate | Valid JSON file with indentation | ✅ PASS | |
| 19 | multi-file generate | Both files created correctly | ✅ PASS | |
| 20 | script file mode | File contains script output | ✅ PASS | |
| 21 | invalid JSON → error | Error: "Generated content is not valid JSON" | ✅ PASS | |
| 22 | --no-validate | File created with invalid content | ✅ PASS | |
| 23 | stderr captured | `exit_code: 1`, stderr captured | ✅ PASS | |
| 24 | timeout enforcement | Timed out after ~2s (not 10s) | ✅ PASS | 2.003s |
| 25 | large file generation | 802 lines output, valid JSON | ✅ PASS | 73x compression |
| 26 | partial failure | Valid file created, invalid rejected | ✅ PASS | |

## Phase 4: Verify & Restore (5 tests)

| # | Test | Expected | Status | Notes |
|---|------|----------|--------|-------|
| 27 | verify shows diff | Shows diff with added/removed counts | ✅ PASS | |
| 28 | restore rollback | File restored to pre-edit content | ✅ PASS | |
| 29 | backups list | Lists backup entries with timestamps | ✅ PASS | |
| 30 | verify-syntax Python | OK → `syntax_valid: true`, BAD → SyntaxError | ✅ PASS | |
| 31 | verify with no backup | Error: "No backup found" | ✅ PASS | |

## Phase 5: Edge Cases (6 tests)

| # | Test | Expected | Status | Notes |
|---|------|----------|--------|-------|
| 32 | unknown command | Error: "Unknown command: nonexistent-command" | ✅ PASS | |
| 33 | missing required args | Error: "Missing arguments for show. Usage: ..." | ✅ PASS | Fixed (see above) |
| 34 | file not found | Error with "No such file or directory" | ✅ PASS | |
| 35 | CRLF preservation | Lines 1,3 retain `\r\n` endings | ✅ PASS | xxd verified |
| 36 | unicode/emoji | Chinese/Japanese/emoji all preserved | ✅ PASS | |
| 37 | fast-* prefix equivalence | `fast-show` == `show`, `fast-replace` == `replace` | ✅ PASS | |

---

## Test Observations

### Batch JSON Format
The correct batch JSON format uses `"action": "replace-lines"` (not `"type": "replace"`). Supported actions:
- `replace-lines` — replace a line range
- `insert-after` — insert after a line
- `delete-lines` — delete a line range

### Shell Escaping with fast-write --stdin
When piping JSON via `echo`, `\n` in JSON strings gets interpreted by the shell as actual newlines, producing invalid JSON. Solutions:
- Use `printf '%s'` instead of `echo`
- Use heredoc with `<< 'EOF'` (single-quoted marker prevents expansion)
- Use `python3 -c "json.dump(...)"` for complex JSON

### Generate Compression Ratio
Test 25 demonstrated **73x compression**: an 11-line Python prompt generated 802 lines of valid JSON output. This validates the `generate` command's purpose — bypassing AI output token limits for bulk file creation.

### CRLF Handling
fast-edit preserves CRLF (`\r\n`) line endings in lines that are not modified during a replace operation. Replaced lines use whatever line endings the new content specifies.
