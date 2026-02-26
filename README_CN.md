# Fast Edit

[English](README.md) | **中文**

一个快速的、基于行号的文件编辑工具，旨在绕过 LSP 延迟、权限提示和历史数据库开销。专为 AI 辅助编辑工作流设计。

## 动机

用过 Cursor、Claude Code、OpenCode 这类 AI 编程工具的朋友，一定经历过这种场景：

> AI 说"我来修改一下这个文件"，然后你就开始等……
>
> 3 秒……5 秒……10 秒……
>
> 终于改完了，结果发现还要改另外两处。
>
> 又是 10 秒……又是 10 秒……

一个简单的三处修改，居然要等 30 秒？问题出在原生 Edit 工具的工作方式：

1. **字符串匹配开销** — AI 需要输出「旧内容」和「新内容」两份完整的代码。一个 500 行的文件改 3 处，可能要输出上千个 token。
2. **LSP 同步等待** — 每次编辑后，编辑器要等 LSP（语言服务器）同步完成并检查类型错误，通常需要 1-5 秒。
3. **多次往返调用** — 改 3 处就要调用 3 次 Edit，每次都有网络延迟 + LSP 等待。

**Fast Edit 采用完全不同的思路**：用行号定位代替字符串匹配，用批量操作代替重复调用，直接文件 I/O 完全绕过 LSP。效果？**编辑速度提升 100 倍** — 500 行文件改 3 处，从 ~15 秒降到不到 0.1 秒。

## 功能特性

- **行号编辑**：显示、替换、插入和删除指定行范围
- **批量操作**：通过单个 JSON 请求对文件应用多次编辑
- **剪贴板/stdin 支持**：从剪贴板或 stdin 粘贴内容，支持 Markdown 代码块提取和 Base64 解码
- **多文件写入**：通过单个 JSON 规范创建多个文件
- **类型检查**：自动检测并运行可用的 Python 类型检查器（basedpyright、pyright、mypy）
- **零外部依赖**：纯 Python 实现，仅使用标准库
- **代码生成写文件**：执行代码生成文件内容，批量创建大文件时可实现 5x+ token 压缩

## 安装

```bash
# 克隆仓库
git clone https://github.com/includewudi/fast-edit.git
cd fast-edit

# 无需安装 - 直接运行脚本
python3 fast_edit.py
```

如需类型检查支持，可选安装以下之一：
```bash
pip install basedpyright  # 推荐（最快）
# 或
pip install pyright
# 或
pip install mypy
```

## 快速开始

```bash
# 定义函数方便使用
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }

# 显示第 1-10 行
fe show myfile.py 1 10

# 替换第 5-7 行
fe replace myfile.py 5 7 "new content\n"

# 在第 3 行后插入
fe insert myfile.py 3 "inserted line\n"

# 删除第 8-10 行
fe delete myfile.py 8 10

# 批量编辑
fe batch edit_spec.json

# 从 stdin 粘贴
echo "print('hello')" | fe paste output.py --stdin

# 写入多个文件
fe write files_spec.json

# 类型检查
fe check myfile.py

# 代码生成写文件
echo 'import json; print(json.dumps({"key": "value"}))' | fe generate --stdin -o output.json

# 生成多个文件
python3 gen_script.py | fe generate --stdin
```

## 命令详解

### `show FILE START END`

显示带行号的文件内容。

```bash
fe show script.py 10 20
```

### `replace FILE START END CONTENT`

替换指定行范围的内容。

```bash
fe replace script.py 5 7 "def new_function():\n    pass\n"
```

- 行号从 1 开始，首尾均包含
- 使用 `\n` 表示换行
- 内容会自动展开转义字符（如 `\n` 变为换行，`\t` 变为制表符）

### `insert FILE LINE CONTENT`

在指定行之后插入内容。

```bash
fe insert script.py 10 "import logging\n"
```

- 使用 `LINE=0` 在文件开头插入

### `delete FILE START END`

删除指定行范围。

```bash
fe delete script.py 15 20
```

### `batch [--stdin] [SPEC]`

单次操作中应用多个编辑。

```bash
# 从 JSON 文件
fe batch edits.json

# 从 stdin
echo '{"file":"a.py","edits":[...]}' | fe batch --stdin
```

**批量编辑 JSON 格式：**

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

多文件格式：

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

从剪贴板或 stdin 保存内容到文件。

```bash
# 从剪贴板（macOS 需要 pbpaste，Linux 需要 xclip）
fe paste output.py

# 从 stdin
echo "print('hello')" | fe paste output.py --stdin

# 提取 Markdown 代码块
fe paste output.py --stdin --extract << 'EOF'
这是一些代码：
```python
def hello():
    print("world")
```
EOF

# 解码 Base64 内容（适用于特殊字符）
echo "cHJpbnQoJ2hlbGxvJyk=" | fe paste output.py --stdin --base64
```

- `--extract`：自动从 ````python`...```` 代码块中提取内容
- `--base64`：写入前解码 Base64 编码的内容

### `write [--stdin] [SPEC]`

通过 JSON 规范创建多个文件。

```bash
# 从 JSON 文件
fe write files.json

# 从 stdin
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

**写入 JSON 格式：**

- `file`：要创建的文件路径
- `content`：要写入的内容
- `extract`（可选）：若为 `true`，从 Markdown 代码块中提取内容
- `encoding`（可选）：若为 `"base64"`，写入前解码内容

### `check FILE [--checker NAME]`

对 Python 文件运行类型检查器。

```bash
# 自动检测可用的检查器
fe check myfile.py

# 使用指定检查器
fe check myfile.py --checker mypy
```

自动检测顺序：`basedpyright` → `pyright` → `mypy`


### `generate [--stdin] [-o FILE] [SCRIPT] [--timeout N] [--interpreter CMD] [--no-validate]`

执行代码并将 stdout 输出写入文件。解决 AI 批量生成大文件时的输出 token 瓶颈问题。

```bash
# 单文件模式：代码 stdout → 一个文件
echo 'import json; print(json.dumps({"data": [1,2,3]}))' | fe generate --stdin -o output.json

# 多文件模式：代码 stdout 必须是 JSON 文件规范
python3 gen_files.py | fe generate --stdin

# 脚本文件模式
fe generate script.py -o output.json

# 带选项
fe generate --stdin -o out.json --timeout 60 --interpreter python3.12 --no-validate
```

**两种模式：**

1. **单文件** (`-o FILE`)：脚本 stdout 直接写入目标文件
2. **多文件** (不带 `-o`)：脚本 stdout 必须是 JSON：`{"files": [{"file": "路径", "content": "..."}]}`

**选项：**

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--stdin` | 从 stdin 读取代码 | - |
| `-o FILE` | 单文件模式输出目标 | 多文件模式 |
| `--timeout N` | 执行超时（秒） | 30 |
| `--interpreter CMD` | 执行代码的解释器 | `python3` |
| `--no-validate` | 跳过 .json 文件的格式验证 | 验证 |

**为什么使用 generate？** 当 AI 需要创建大文件（200+ 行）时，LLM 输出 token 上限成为瓶颈。所有文件写入工具都要求 LLM 输出完整内容。`generate` 让 LLM 输出紧凑的代码（~70 行），由代码在本地执行后生成内容（~375+ 行）—— 实现 5x+ 压缩比。

## 使用场景

| 场景 | 命令 |
|------|------|
| 大文件（100+ 行）中的小改动 | `replace` / `batch` |
| 同一文件多次编辑 | `batch` |
| 用户粘贴代码到输入框，保存单文件 | `paste --stdin` |
| 用户粘贴含特殊字符的代码 | `paste --stdin --base64` |
| 用户粘贴多个代码块，保存多文件 | `write --stdin` |
| 从剪贴板保存 | `paste` |
| 编辑后类型检查 | `check` |
| AI 从零生成大文件/批量文件 (200+ 行) | `generate --stdin -o FILE` 或 `generate --stdin` |

## 典型工作流

### 用户将代码粘贴到输入框

```
用户：把这个保存到 /tmp/app.py
```python
def main():
    print("hello")
```

AI 执行：
echo '<user content>' | fe paste /tmp/app.py --stdin --extract
```

### 用户粘贴含特殊字符的代码（推荐方式）

当代码包含引号、`$variables`、反斜杠等时，使用 Base64 避免 shell 转义问题：

```bash
# 用户粘贴：print('hello $USER')
# AI 先进行 Base64 编码，再传给 fast-edit
echo -n "print('hello \$USER')" | base64 | xargs -I{} sh -c 'echo {} | fe paste /tmp/app.py --stdin --base64'
```

### 用户粘贴多个代码块

```
用户：保存这两个文件
file1.py:
```python
def a(): pass
```
file2.py:
```python
def b(): pass
```

AI 构造并执行：
fe write --stdin << 'EOF'
{"files": [
  {"file": "file1.py", "content": "def a(): pass\n"},
  {"file": "file2.py", "content": "def b(): pass\n"}
]}
EOF
```


### AI 使用代码生成大文件

当 AI 需要创建 200+ 行的文件时，使用 `generate` 实现 5x+ token 压缩：

```bash
# AI 写 ~30 行 Python，生成 200+ 行输出
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

## 性能对比

| 场景 | Edit 工具 | fast-edit |
|------|-----------|-----------|
| 500 行文件，3 次编辑 | ~15 秒（3 次调用） | **<0.1 秒**（批量） |
| AI Token 输出 | 旧+新字符串 | **仅行号+内容** |
| LSP 等待 | 每次 0-5 秒 | **0** |

## 文件结构

```
fast-edit/
├── fast_edit.py   # CLI 入口（121 行）
├── core.py        # 文件 I/O 操作
├── edit.py        # 编辑操作（show、replace、insert、delete、batch）
├── paste.py       # 粘贴/写入操作
├── pasted.py      # OpenCode 存储提取
├── generate.py    # 代码生成写文件
├── check.py       # 类型检查
├── verify.py      # 验证/备份/回滚/语法检查
├── skill.md       # 详细使用文档
├── TEST_PLAN.md   # 测试计划与结果
├── requirements.txt  # 可选依赖
├── .gitignore
├── README.md
└── README_CN.md
```

## 测试

运行测试计划：

```bash
# 查看测试计划
cat TEST_PLAN.md

# 手动运行测试
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }
TEST_DIR="/tmp/fast-edit-test"
mkdir -p $TEST_DIR

# ... 按照 TEST_PLAN.md 操作 ...
```

## 验证

**推荐**：编辑后使用 `lsp_diagnostics` 检查类型错误（需要 LSP 可用）。

**备选**：如果 LSP 不可用，使用 fast-edit 内置的 check 命令：

```bash
fe check /path/to/edited_file.py
```

| 方法 | 优点 | 缺点 |
|------|------|------|
| `lsp_diagnostics` | 快速（LSP 热启动），支持所有语言 | 需要 LSP 服务器运行 |
| `fe check` | 独立运行，无依赖 | 仅支持 Python，冷启动较慢 |

## 许可证

MIT

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 作者

[wudi](https://github.com/includewudi)
