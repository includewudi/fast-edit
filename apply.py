"""Apply: symbol-targeted edits (replace/delete/insert by symbol).

This module implements the `apply` subcommand used by fast_edit.py. It resolves
Python symbols (functions / classes / methods) via `outline._extract_symbols()`
and then delegates line-based mutations to edit.replace/delete/insert.

MVP actions:
- replace-symbol
- delete-symbol
- insert-before-symbol
- insert-after-symbol

Only stdlib is used (ast, os).
"""

import ast
import os

import edit
from outline import _extract_symbols


def _err(message, **extra):
    ret = {"status": "error", "message": message}
    ret.update(extra)
    return ret


def _parse_syntax(filepath):
    """Read and ast.parse() a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            src = f.read()
        tree = ast.parse(src, filename=filepath)
        return src, tree, None
    except SyntaxError as e:
        return None, None, _err("apply: syntax error at line %s: %s" % (e.lineno, e.msg))


def _available_symbols(symbols):
    return [s.get("qualname") or s.get("name") for s in symbols]


def _resolve_symbol(symbols, query):
    """Resolve a symbol string to exactly one symbol dict.

    Resolution strategy:
    1. Exact qualname match → if unique, return it.
       BUT if query is a bare name (no dot), also check if other symbols share
       the same bare name. If so, report ambiguity with all qualnames.
    2. If no qualname match, try bare name match.
    3. If multiple qualname matches (e.g., getter/setter same qualname),
       disambiguate with line numbers.
    """
    # --- Phase 1: qualname exact match ---
    exact = [s for s in symbols if s.get("qualname") == query]

    if len(exact) == 1:
        # If query is a bare name (no dot), check for name collisions
        # e.g., query="process" matches qualname "process" (top-level),
        # but "Foo.process" also has name "process" → ambiguity
        if "." not in query:
            same_name = [s for s in symbols if s.get("name") == query]
            if len(same_name) > 1:
                cands = sorted(
                    set(s.get("qualname") or s.get("name") for s in same_name),
                    key=lambda x: (x != query, x),
                )
                return None, _err(f"apply: ambiguous symbol {query!r}", candidates=cands)
        return exact[0], None

    if len(exact) > 1:
        # Multiple symbols with same qualname (e.g., @property getter + setter)
        # Disambiguate with line numbers
        cands = []
        for s in exact:
            q = s.get("qualname") or s.get("name")
            span = s.get("span") or {}
            sl = span.get("start_line", "?")
            el = span.get("end_line", "?")
            cands.append(f"{q} (L{sl}-{el})")
        return None, _err(f"apply: ambiguous symbol {query!r}", candidates=cands)

    # --- Phase 2: bare name fallback ---
    bare = [s for s in symbols if s.get("name") == query]
    if len(bare) == 1:
        return bare[0], None
    if len(bare) > 1:
        cands = sorted(
            set(s.get("qualname") or s.get("name") for s in bare),
            key=lambda x: (x != query, x),
        )
        return None, _err(f"apply: ambiguous symbol {query!r}", candidates=cands)

    return None, _err("apply: symbol %r not found" % query, available=_available_symbols(symbols))


def _validate_spec(spec):
    if not isinstance(spec, dict):
        return None, _err("apply: spec must be an object")

    filepath = spec.get("file")
    if not isinstance(filepath, str) or not filepath:
        return None, _err("apply: 'file' must be a non-empty string")

    if not filepath.lower().endswith(".py"):
        return None, _err("apply: only .py files supported")

    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        return None, _err(f"apply: file not found: {abs_path}")

    mode = spec.get("mode", "dry-run")
    if mode not in ("dry-run", "apply"):
        return None, _err(f"apply: unknown mode {mode!r}")

    ops = spec.get("ops")
    if not isinstance(ops, list) or not ops:
        return None, _err("apply: 'ops' must be a non-empty list")

    return {"file": abs_path, "mode": mode, "ops": ops}, None


def _op_needs_content(action):
    return action in ("replace-symbol", "insert-before-symbol", "insert-after-symbol")


def _resolve_ops(symbols, ops):
    resolved = []
    for op in ops:
        if not isinstance(op, dict):
            return None, _err("apply: each op must be an object")

        action = op.get("action")
        if not isinstance(action, str) or not action:
            return None, _err("apply: op missing 'action'")

        symbol = op.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            return None, _err("apply: op missing 'symbol'")

        if action not in (
            "replace-symbol",
            "delete-symbol",
            "insert-before-symbol",
            "insert-after-symbol",
        ):
            return None, _err(f"apply: unknown action {action!r}")

        if _op_needs_content(action) and (
            "content" not in op or not isinstance(op.get("content"), str)
        ):
            return None, _err(f"apply: 'content' required for {action}")

        sym, sym_err = _resolve_symbol(symbols, symbol)
        if sym_err:
            return None, sym_err

        span = sym.get("span") or {}
        start_line = span.get("start_line")
        end_line = span.get("end_line")
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            return None, _err(f"apply: invalid span for symbol {symbol!r}")

        resolved.append(
            {
                "action": action,
                "symbol": symbol,
                "qualname": sym.get("qualname"),
                "span": {"start_line": start_line, "end_line": end_line},
                "content": op.get("content"),
            }
        )

    resolved.sort(key=lambda r: r["span"]["start_line"], reverse=True)
    return resolved, None


def _format_syntax_error(err):
    line = getattr(err, "lineno", None)
    msg = getattr(err, "msg", str(err))
    if line:
        return f"line {line}: {msg}"
    return msg


def apply(spec):
    """Apply symbol-targeted edits to a Python file."""
    parsed, spec_err = _validate_spec(spec)
    if spec_err:
        return spec_err

    filepath = parsed["file"]
    mode = parsed["mode"]
    ops = parsed["ops"]

    _src, tree, parse_err = _parse_syntax(filepath)
    if parse_err:
        return parse_err

    symbols = _extract_symbols(tree)
    resolved_ops, res_err = _resolve_ops(symbols, ops)
    if res_err:
        return res_err

    if mode == "dry-run":
        return {
            "status": "ok",
            "mode": "dry-run",
            "file": filepath,
            "ops_resolved": [
                {"action": op["action"], "symbol": op["symbol"], "span": op["span"]}
                for op in resolved_ops
            ],
        }

    edit._maybe_backup(filepath)

    applied = 0
    for op in resolved_ops:
        action = op["action"]
        start_line = op["span"]["start_line"]
        end_line = op["span"]["end_line"]
        content = op.get("content")

        if action == "replace-symbol":
            edit.replace(filepath, start_line, end_line, content)
        elif action == "delete-symbol":
            edit.delete(filepath, start_line, end_line)
        elif action == "insert-before-symbol":
            edit.insert(filepath, start_line - 1, content)
        elif action == "insert-after-symbol":
            edit.insert(filepath, end_line, content)
        else:
            return _err(f"apply: unknown action {action!r}")

        applied += 1

    syntax_valid = True
    syntax_error = None
    total_lines = None
    try:
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            new_src = f.read()
        ast.parse(new_src, filename=filepath)
        total_lines = len(new_src.splitlines())
    except SyntaxError as e:
        syntax_valid = False
        syntax_error = _format_syntax_error(e)
        total_lines = len(new_src.splitlines())

    ret = {
        "status": "ok",
        "mode": "apply",
        "file": filepath,
        "ops_applied": applied,
        "total_lines": total_lines,
        "syntax_valid": syntax_valid,
    }
    if not syntax_valid:
        ret["syntax_error"] = syntax_error
    return ret
