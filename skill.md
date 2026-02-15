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

# 从 OpenCode 存储中提取用户粘贴的大文件 (绕过 AI token 输出瓶颈)
$FE save-pasted FILE                      # 自动找最近的大粘贴 (>=20行)
$FE save-pasted FILE --min-lines 50       # 自定义行数阈值
$FE save-pasted FILE --msg-id msg_xxx     # 指定消息 ID
$FE save-pasted FILE --extract            # 提取 ```...``` 代码块
$FE save-pasted FILE --nth 2              # 第2个最近的大粘贴
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
| 用户粘贴了超大文件 (600+行)，AI 无法 echo 输出 | `save-pasted` |
| AI 从零创建大文件 (200+行)，无源文件可复制 | 分段 heredoc → `cat` 合并 → `paste --stdin` |

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

### 用户粘贴超大文件 (AI 输出会超时)

当用户粘贴 600+ 行代码，AI 无法通过 echo/Write 输出全部内容时：

```bash
# 直接从 OpenCode 的本地存储提取，零 token 输出
$FE save-pasted /tmp/big_file.php

# 然后正常编辑
$FE show /tmp/big_file.php 1 20
$FE replace /tmp/big_file.php 10 12 "new content\n"
```

原理：用户粘贴的内容已存储在 `~/.local/share/opencode/storage/part/`，
`save-pasted` 直接读取文件系统，不需要 AI 重新输出。

### 从零创建大文件 (200+ 行)

> **⚠️ 判断是否需要分段的决策流程：**
>
> 这个技巧解决的**不是文件写入速度**问题（`paste --stdin` 本身写任意大小都很快），
> 而是 **AI 单次 Bash 调用的 token 输出上限**——heredoc/echo 内容过长会被截断或超时。
>
> ```
> AI 需要创建文件
>   │
>   ├─ 内容已存在于文件/用户粘贴？
>   │    → 直接 paste --stdin / save-pasted，不需要分段
>   │
>   ├─ AI 从零生成，≤150 行？
>   │    → 直接单次 heredoc 或 Write 工具，不需要分段
>   │
>   ├─ AI 从零生成，150-200 行？
>   │    → 可以尝试单次，如果被截断再分段
>   │
>   └─ AI 从零生成，>200 行？
>        → 直接用分段技巧，不要尝试单次（大概率会超时）
> ```
>
> **不需要分段的场景（直接用对应命令即可）：**
> | 场景 | 直接用 |
> |------|--------|
> | 用户粘贴了代码，保存到文件 | `paste --stdin` |
> | 用户粘贴了超大文件 (600+行) | `save-pasted` |
> | 已有文件 A，复制/修改后写入文件 B | `cat A \| paste B --stdin` 或 `batch` |
> | AI 生成 ≤150 行的小文件 | 单次 heredoc / Write 工具 |

当 AI 需要**从零生成**一个大文件（无源文件可 `cp`），且内容超过 ~200 行，
单次 Write/echo/heredoc 会因 token 输出上限被截断或超时。
用分段 heredoc + `cat` 合并 + `paste --stdin` 逐步累积：

```bash
FE="/Users/wudi/miniforge3/bin/python3 /Users/wudi/data/code/ai_tools/git_skills/wudi/fast-edit/fast_edit.py"

# 第 1 段 (~80 行)
cat > /tmp/part1.md << 'PART1'
# Title
...first ~80 lines...
PART1

# 第 2 段 (~80 行)
cat > /tmp/part2.md << 'PART2'
...next ~80 lines...
PART2

# 合并 → 写入目标
cat /tmp/part1.md /tmp/part2.md > /tmp/combined.md
$FE paste /path/to/target.md --stdin < /tmp/combined.md

# 第 3 段 (~80 行)
cat > /tmp/part3.md << 'PART3'
...next ~80 lines...
PART3

# 追加合并 → 覆写目标
cat /tmp/combined.md /tmp/part3.md > /tmp/combined2.md
$FE paste /path/to/target.md --stdin < /tmp/combined2.md

# 继续直到完成...

# 清理
rm -f /tmp/part*.md /tmp/combined*.md
```

**关键注意事项：**

| 要点 | 说明 |
|------|------|
| 每段建议 120-160 行 | 太长 heredoc 可能超时；太短则轮次多（2000 行 ≈ 13-17 段） |
| 用 `'MARKER'` 引号 | 防止 heredoc 内 `$变量` 被展开 |
| **不要用** `insert --stdin` | 多行 stdin 时只写入 1 行 (已知限制) |
| 用 `paste --stdin` | 覆写整个文件，所以每次要 `cat` 累积所有段 |
| 用完整 python3 路径 | heredoc 内 `$FE` 变量可能不展开 |
| 分段比单次慢 ~4x | 但单次 200+ 行会被截断，慢总比坏好 |

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
├── fast_edit.py   # CLI 入口 (139 行)
├── core.py        # 文件 I/O (82 行)
├── edit.py        # 编辑操作 (181 行)
├── paste.py       # 粘贴/写入 (107 行)
├── pasted.py      # OpenCode 存储提取 (194 行)
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
