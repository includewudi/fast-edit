---
name: fast-edit
description: 大文件编辑、批量修改、剪贴板/stdin粘贴、多文件写入、类型检查。用于替代慢速的 Edit/Write 工具。
---

# Fast Edit

行号定位的文件编辑工具。绕过 LSP 等待、权限弹窗、历史数据库。

## 命令速查

```bash
FE="python3 /path/to/fast-edit/fast_edit.py"

# 预览
$FE show FILE START END

# 编辑 (行号 1-based, inclusive)
$FE replace FILE START END "content\n"
$FE insert FILE LINE "content\n"        # LINE=0 表示开头
$FE delete FILE START END

# 批量编辑 (JSON)
$FE batch spec.json
echo '{"file":"a.py","edits":[...]}' | $FE batch --stdin

# 粘贴保存
$FE paste FILE                    # 从剪贴板
$FE paste FILE --stdin            # 从 stdin
$FE paste FILE --stdin --extract  # 提取 ```...``` 代码块
$FE paste FILE --stdin --base64   # stdin 内容是 base64 编码

# 批量写文件 (多文件创建)
$FE write spec.json
echo '{"files":[...]}' | $FE write --stdin

# 类型检查
$FE check FILE
$FE check FILE --checker mypy
```

## 使用场景

| 场景 | 命令 |
|------|------|
| 大文件 (100+ 行) 小改动 | `replace` / `batch` |
| 同文件多处编辑 | `batch` |
| 用户粘贴代码到输入框，保存单文件 | `paste --stdin` |
| 用户粘贴含特殊字符的代码 | `paste --stdin --base64` |
| 用户粘贴多份代码，保存多文件 | `write --stdin` |
| 从剪贴板保存 | `paste` |
| 编辑后类型检查 | `lsp_diagnostics` (推荐) 或 `check` |

## Batch JSON 格式

```json
{
  "file": "/path/to/file.py",
  "edits": [
    {"action": "replace-lines", "start": 10, "end": 12, "content": "new\n"},
    {"action": "insert-after", "line": 25, "content": "# comment\n"},
    {"action": "delete-lines", "start": 40, "end": 42}
  ]
}
```

多文件: `{"files": [{"file": "a.py", "edits": [...]}, ...]}`

## Write JSON 格式

```json
{
  "files": [
    {"file": "/tmp/a.py", "content": "def a():\n    pass\n"},
    {"file": "/tmp/b.py", "content": "```python\ndef b(): pass\n```", "extract": true},
    {"file": "/tmp/c.py", "content": "ZGVmIGMoKTogcGFzcwo=", "encoding": "base64"}
  ]
}
```

- `extract: true` 自动提取 \`\`\`...\`\`\` 代码块内容
- `encoding: "base64"` 内容是 base64 编码，自动解码后写入

## 典型工作流

### 用户粘贴代码到输入框

```
用户: 保存这个到 /tmp/app.py
```python
def main():
    print("hello")
```

AI 执行:
echo '<用户粘贴的内容>' | $FE paste /tmp/app.py --stdin --extract
```

### 用户粘贴含特殊字符的代码 (推荐)

当代码包含引号、`$变量`、反斜杠等特殊字符时，用 base64 避免 shell 转义问题：

```bash
# 用户粘贴: print('hello $USER')
# AI 先 base64 编码，再传给 fast-edit
echo -n "print('hello \$USER')" | base64 | xargs -I{} sh -c 'echo {} | $FE paste /tmp/app.py --stdin --base64'

# 或者更简单：
printf '%s' "print('hello \$USER')" | base64 > /tmp/b64.txt
cat /tmp/b64.txt | $FE paste /tmp/app.py --stdin --base64
```

### 用户粘贴多份代码

```
用户: 保存这两个文件
file1.py:
```python
def a(): pass
```
file2.py:
```python
def b(): pass
```

AI 构造 JSON 执行:
$FE write --stdin << 'EOF'
{"files": [
  {"file": "file1.py", "content": "def a(): pass\n"},
  {"file": "file2.py", "content": "def b(): pass\n"}
]}
EOF
```

## 文件结构

```
fast-edit/
├── fast_edit.py   # CLI 入口 (118 行)
├── core.py        # 文件 I/O (82 行)
├── edit.py        # 编辑操作 (181 行)
├── paste.py       # 粘贴/写入 (107 行)
├── check.py       # 类型检查 (145 行)
└── skill.md       # 本文档
```

## 性能对比

| 场景 | Edit 工具 | fast-edit |
|------|-----------|-----------|
| 500行文件 3处编辑 | ~15s (3次调用) | **<0.1s** (batch) |
| AI Token 输出 | old+new 字符串 | **仅行号+内容** |
| LSP 等待 | 每次 0-5s | **0** |

## 编辑后验证

**推荐**：编辑完成后调用 `lsp_diagnostics` 检查类型错误：

```
lsp_diagnostics(filePath="/path/to/edited_file.py")
```

**备选**：如果 LSP 不可用，用 fast-edit 内置的 check 命令：

```bash
$FE check /path/to/edited_file.py
```

| 方式 | 优点 | 缺点 |
|------|------|------|
| `lsp_diagnostics` | 快（LSP 热启动）、支持所有语言 | 需要 LSP 服务运行 |
| `$FE check` | 独立运行、无依赖 | 仅支持 Python、冷启动稍慢 |
