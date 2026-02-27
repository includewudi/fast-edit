"""Outline: extract Python symbols (functions/classes/methods) via stdlib ast."""

import ast
import os



def _decorator_aware_start_line(node):
    decorators = getattr(node, "decorator_list", None) or []
    if decorators:
        # Per requirements: use first decorator lineno (source-order preserved)
        return decorators[0].lineno
    return node.lineno


def _span(node):
    return {
        "start_line": _decorator_aware_start_line(node),
        "end_line": node.end_lineno,
    }


def _symbol(kind, name, qualname, node):
    span = _span(node)
    return {
        "kind": kind,
        "name": name,
        "qualname": qualname,
        "symbol": qualname,
        "span": span,
    }


def _extract_symbols(tree):
    symbols = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            symbols.append(_symbol("function", node.name, node.name, node))
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(_symbol("async_function", node.name, node.name, node))
        elif isinstance(node, ast.ClassDef):
            class_qualname = node.name
            symbols.append(_symbol("class", node.name, class_qualname, node))

            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    meth_qualname = f"{class_qualname}.{child.name}"
                    symbols.append(_symbol("method", child.name, meth_qualname, child))
                elif isinstance(child, ast.AsyncFunctionDef):
                    meth_qualname = f"{class_qualname}.{child.name}"
                    symbols.append(_symbol("async_method", child.name, meth_qualname, child))

    # Ordering: symbols appear in source order by decorator-aware start_line
    symbols.sort(key=lambda s: s["span"]["start_line"])
    return symbols


def _format_tree(symbols):
    lines = []
    for sym in symbols:
        kind = sym["kind"]
        name = sym["name"]
        span = sym["span"]
        prefix = "  " if kind in ("method", "async_method") else ""
        lines.append(f"{prefix}{name} ({kind}) L{span['start_line']}-{span['end_line']}")
    return "\n".join(lines) + ("\n" if lines else "")


def outline(filepath, fmt="json"):
    if not filepath.lower().endswith(".py"):
        raise ValueError("outline: only .py files supported")

    abs_path = os.path.abspath(filepath)

    try:
        with open(abs_path, "r", encoding="utf-8", newline="") as f:
            src = f.read()
        tree = ast.parse(src, filename=abs_path)
    except SyntaxError as e:
        raise ValueError(f"outline: syntax error at line {e.lineno}: {e.msg}")

    symbols = _extract_symbols(tree)

    if fmt == "json":
        return {
            "status": "ok",
            "file": abs_path,
            "symbols": symbols,
        }
    elif fmt == "tree":
        return {
            "status": "ok",
            "file": abs_path,
            "tree": _format_tree(symbols),
        }
    else:
        raise ValueError(f"outline: unknown format: {fmt}")

