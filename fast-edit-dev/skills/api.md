    ---
    name: api
    description: CLI 命令、JSON 协议与返回格式
    ---

    # API

    > fast-edit 的 CLI 接口与 JSON 协议说明，覆盖命令参数、返回结构与错误格式。

    ## 接口总览

    | 命令 | 作用 | 入口函数 | 主要输出 |
    |---|---|---|---|
    | show | 预览文件行号 | `edit.show` | 行号 + 内容 | 
    | replace | 替换行范围 | `edit.replace` | added/removed + warnings | 
    | insert | 插入内容 | `edit.insert` | added/after | 
    | delete | 删除行范围 | `edit.delete` | removed | 
    | batch | 批量编辑 | `edit.batch` | results + warnings | 
    | paste | 粘贴单文件 | `paste.paste` | 行数/字节/耗时 | 
    | write | 多文件写入 | `paste.write` | 多文件 results | 
    | generate | 代码生成写文件 | `generate.generate` | 单/多文件 results | 
    | check | Python 类型检查 | `check.check` | diagnostics | 
    | save-pasted | 提取 OpenCode 粘贴 | `pasted.save_pasted` | 行数/字节/msg_id | 
    | verify | 对比备份差异 | `verify.verify` | diff + added/removed | 
    | restore | 回滚备份 | `verify.restore` | restored_from | 
    | backups | 列出备份 | `verify.list_backups` | backups[] | 
    | verify-syntax | 语法检查 | `verify.verify_syntax` | syntax_valid | 
    | outline | 提取 Python 文件符号结构 | `outline.outline` | symbols[] / tree |
    | apply | 符号定位编辑 | `apply.apply` | ops_resolved / ops_applied |

    ### outline FILE [--format tree]

    提取 Python 文件的符号结构（函数、类、方法）。

    - `--format tree`：树形输出（默认 JSON）

    **JSON 返回**：

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "symbols": [
        {"kind": "function", "name": "foo", "qualname": "foo", "symbol": "foo", "span": {"start_line": 1, "end_line": 3}},
        {"kind": "class", "name": "Bar", "qualname": "Bar", "symbol": "Bar", "span": {"start_line": 5, "end_line": 12}},
        {"kind": "method", "name": "baz", "qualname": "Bar.baz", "symbol": "Bar.baz", "span": {"start_line": 8, "end_line": 10}}
      ]
    }
    ```

    **tree 返回**：

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "tree": "foo (function) L1-3\nBar (class) L5-12\n  baz (method) L8-10\n"
    }
    ```

    ### apply [--stdin] [SPEC] --dry-run|--apply

    基于符号名的 Python 文件编辑。

    - `--dry-run`：预览（解析符号位置，不写文件）
    - `--apply`：执行编辑
    - `--stdin`：从 stdin 读取 JSON 规范

    **JSON 规范**：

    ```json
    {
      "file": "/path/to/file.py",
      "mode": "dry-run",
      "ops": [
        {"action": "replace-symbol", "symbol": "Bar.baz", "content": "    def baz(self):\n        return 42\n"},
        {"action": "delete-symbol", "symbol": "foo"},
        {"action": "insert-before-symbol", "symbol": "Bar", "content": "# Bar class\n"},
        {"action": "insert-after-symbol", "symbol": "Bar", "content": "\nclass Qux:\n    pass\n"}
      ]
    }
    ```

    **dry-run 返回**：

    ```json
    {
      "status": "ok",
      "mode": "dry-run",
      "file": "/abs/path/file.py",
      "ops_resolved": [
        {"action": "replace-symbol", "symbol": "Bar.baz", "span": {"start_line": 8, "end_line": 10}}
      ]
    }
    ```

    **apply 返回**：

    ```json
    {
      "status": "ok",
      "mode": "apply",
      "file": "/abs/path/file.py",
      "ops_applied": 2,
      "total_lines": 45,
      "syntax_valid": true
    }
    ```

    **错误返回**：

    ```json
    // 符号歧义
    {"status": "error", "message": "apply: ambiguous symbol 'run'", "candidates": ["run", "Task.run", "Worker.run"]}
    // 符号不存在
    {"status": "error", "message": "apply: symbol 'xyz' not found", "available": ["run", "Task", "Task.run"]}
    // 非 Python 文件
    {"status": "error", "message": "apply: only .py files supported"}
    ```

    ## CLI 基础约定

    - 所有命令输出 **JSON**（stdout），错误信息输出到 stderr 并以非 0 退出码结束。
    - 行号 **1-based** 且 **包含首尾**。
    - `fast-*` 前缀与原命令等价，用于规避 shell 内置冲突。
    - `CONTENT` 参数中的 `
`/`	` 会被展开为真实换行/Tab。

    ### 通用错误格式

    ```json
    {
      "status": "error",
      "message": "Reason for failure"
    }
    ```

    ### 命令缺参报错

    ```json
    {
      "status": "error",
      "message": "Missing arguments for show. Usage: show FILE START END"
    }
    ```

    ## 命令明细

    ### show FILE START END

    预览行号范围内容（自动 clamp 到合法范围）。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "start": 10,
      "end": 20,
      "total": 120,
      "content": "10	line...
11	line..."
    }
    ```

    ### replace FILE START END CONTENT

    替换行范围，必要时自动补充尾随换行，返回新增/删除行数。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "removed": 3,
      "added": 4,
      "total": 122,
      "warnings": [
        "DUPLICATE_LINE: ...",
        "BRACKET_BALANCE: ..."
      ]
    }
    ```

    ### insert FILE LINE CONTENT

    在指定行后插入，`LINE=0` 表示在文件开头插入。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "after": 5,
      "added": 2,
      "total": 124
    }
    ```

    ### delete FILE START END

    删除行范围。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "removed": 5,
      "total": 110
    }
    ```

    ### batch [--stdin] [SPEC]

    批量编辑（自动从底部向上排序，避免行号漂移）。

    **JSON 规范**：

    ```json
    {
      "file": "/path/to/file.py",
      "edits": [
        {"action": "replace-lines", "start": 10, "end": 12, "content": "new
"},
        {"action": "insert-after", "line": 25, "content": "# comment
"},
        {"action": "delete-lines", "start": 40, "end": 42}
      ]
    }
    ```

    **返回**：

    ```json
    {
      "status": "ok",
      "files": 1,
      "results": [
        {"file": "/abs/path/file.py", "edits": 3, "total": 140}
      ],
      "warnings": ["[file.py:10-12] DUPLICATE_LINE: ..."]
    }
    ```

    ### paste FILE [--stdin] [--extract] [--base64]

    - `--stdin`: 从 stdin 读取
    - `--extract`: 提取 ```...``` 代码块
    - `--base64`: 解码 base64 内容

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "lines": 10,
      "bytes": 256,
      "timing": {"start": "...", "end": "...", "elapsed_sec": 0.0005}
    }
    ```

    ### write [--stdin] [SPEC]

    多文件写入（支持 `extract` 与 `encoding`）。

    ```json
    {
      "files": [
        {"file": "/tmp/a.py", "content": "def a(): pass
"},
        {"file": "/tmp/b.py", "content": "ZGVmIGIoKTogcGFzcwo=", "encoding": "base64"}
      ]
    }
    ```

    ```json
    {
      "status": "ok",
      "files": 2,
      "results": [
        {"file": "/abs/path/a.py", "lines": 1, "bytes": 14, "elapsed_sec": 0.0003}
      ],
      "timing": {"start": "...", "end": "...", "elapsed_sec": 0.0008}
    }
    ```

    ### generate [--stdin] [SCRIPT] [-o FILE] [--timeout N] [--interpreter CMD] [--no-validate]

    执行代码生成文件内容。

    - `-o FILE`：单文件模式（stdout → 文件）
    - 无 `-o`：多文件模式（stdout 必须是 JSON spec）
    - `--no-validate`：跳过 .json 格式校验

    **单文件返回**：

    ```json
    {
      "status": "ok",
      "mode": "single",
      "files": 1,
      "results": [{"file": "/abs/path/file.json", "lines": 200, "bytes": 4096}],
      "stderr": null,
      "timing": {"start": "...", "end": "...", "elapsed_sec": 0.03}
    }
    ```

    **多文件返回**：

    ```json
    {
      "status": "ok",
      "mode": "multi",
      "files": 2,
      "results": [
        {"file": "/abs/path/a.json", "lines": 44, "bytes": 532},
        {"file": "/abs/path/b.md", "lines": 20, "bytes": 312}
      ]
    }
    ```

    **错误返回**：

    ```json
    {
      "status": "error",
      "message": "Script execution failed",
      "exit_code": 1,
      "stderr": "..."
    }
    ```

    ### check FILE [--checker NAME]

    Python 类型检查（basedpyright → pyright → mypy）。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "checker": "basedpyright",
      "errors": 0,
      "warnings": 0,
      "diagnostics": []
    }
    ```

    ### save-pasted FILE [--min-lines N] [--msg-id ID] [--extract] [--nth N]

    从 OpenCode 本地存储提取最近的大粘贴。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "lines": 240,
      "bytes": 12000,
      "msg_id": "msg_xxx",
      "part_id": "part_xxx"
    }
    ```

    ### verify FILE [--context N]

    对比当前文件与最新备份，返回结构化 diff。

    ```json
    {
      "status": "ok",
      "result": "changed",
      "old_lines": 100,
      "new_lines": 102,
      "added": 5,
      "removed": 3,
      "changes": [{"old_start": 10, "new_start": 10, "lines": ["-old", "+new"]}]
    }
    ```

    ### restore FILE

    回滚到最近备份，同时创建 forward backup。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "restored_from": "/abs/path/backup",
      "lines": 100
    }
    ```

    ### backups FILE

    列出所有备份。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.py",
      "backups": [
        {"name": "20260226_120000", "path": "/abs/path/backup", "size": 1024, "time": "..."}
      ]
    }
    ```

    ### verify-syntax FILE

    语言感知语法检查（Go/Py/Rust/C/C++/Java/TS/JS）。

    ```json
    {
      "status": "ok",
      "file": "/abs/path/file.go",
      "checker": "go vet",
      "syntax_valid": true,
      "output": ""
    }
    ```

    ## 警告与校验

    - `replace` / `batch` 会返回 `warnings`（重复行、括号平衡变化）。
    - JSON 规范字段为 `action` 而非 `type`。
    - 传 stdin JSON 时用 heredoc 或 `python -c 'json.dump(...)'`，避免 `
` 被 shell 展开。

