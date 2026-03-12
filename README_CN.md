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
- **端到端计时**：内置计时器跟踪从 skill 加载到任务完成的总耗时，包含 AI 思考时间

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

## 在 OpenCode 中使用（替代内置 Edit/Write）

Fast Edit 可以作为 [OpenCode](https://github.com/anthropics/opencode) 的 skill 安装，**完全替代内置的 Edit 和 Write 工具**。提供两种集成方式：

| 方式 | 原理 | 配置量 | 透明度 |
|------|------|--------|--------|
| **A: 规则驱动** | AI 读取规则 → 加载 skill → 通过 Bash 调用 `fe` 命令 | 添加规则块 | AI 显式调用 fast-edit |
| **B: 自定义工具覆盖** | 自定义工具覆盖内置 Edit/Write → fast-edit 在底层运行 | 复制 2 个文件 | 完全透明 — AI 照常使用 Edit/Write |

### 方式 A：规则驱动（显式）

#### 第 1 步：安装 skill

```bash
# 克隆到 skills 目录
git clone https://github.com/includewudi/fast-edit.git ~/.config/opencode/skills/fast-edit
```

#### 第 2 步：添加到 OpenCode 规则

将以下内容添加到项目的 `.opencode/rules` 或全局规则文件（`~/.config/opencode/rules`）中：

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

**可选：启用 Debug 计时模式**

在规则块中添加 `debug-timer: true` 即可启用端到端计时。启用后，AI 会在加载 skill 时自动执行 `fe timer start`，并在 generate 命令中附带 `--timer`，输出中报告总耗时（包含 AI 思考时间）。

```
debug-timer: true
```

#### AI 助手的变化

| 操作 | 之前（内置工具） | 之后（fast-edit） |
|------|-----------------|-------------------|
| 编辑文件 | `Edit` 工具 → 字符串匹配 → LSP 等待 | `fe replace` / `fe batch` → 即时完成 |
| 创建文件 | `Write` 工具 → 输出全部内容 | `fe paste --stdin` 或 `fe fast-generate` |
| 多处编辑 | 3× Edit 调用（~15 秒） | 1× `fe batch`（<0.1 秒） |
| 大文件（200+ 行） | Write 输出全部内容（token 上限） | `fe fast-generate`（~70 行代码 → 300+ 行输出） |
| 保存用户粘贴 | Write 工具 + 转义头疼 | `fe save-pasted`（零 token） |

AI 助手每次会话加载一次 skill，之后所有文件操作自动通过 fast-edit 执行。

### 方式 B：自定义工具覆盖（无感接入）

方式 B 在工具层面替换 OpenCode 的内置 Edit 和 Write 工具。AI 无需感知 fast-edit 的存在 — 照常调用 Edit/Write，fast-edit 在底层透明运行。

#### 工作原理：基于 Description 的路由

OpenCode 将每个工具的 `description` 字符串暴露给 AI，作为工具 schema 的一部分。AI 通过阅读 description 来决定**何时**以及**如何**使用该工具。自定义工具（`~/.config/opencode/tools/` 中的 TypeScript 文件）会完全覆盖同名的内置工具 — 包括其 description。

我们的自定义工具在 description 中添加了路由提示：

**内置 Edit description**（简化）：
> Performs exact string replacements in files. The oldString must match exactly...

**自定义 Edit description**（带 fast-edit 路由）：
> Performs exact string replacements in files. ...
> **STOP: If you need to replace a large block (>80 lines)** with repetitive/structured content, do NOT output the full newString here — you will waste tokens. Instead: `skill('fast-edit')`, then use `fe fast-batch --stdin` or `fe fast-generate` via Bash.

**内置 Write description**（简化）：
> Writes a file to the local filesystem. Overwrites existing files...

**自定义 Write description**（带 fast-edit 路由）：
> Writes a file to the local filesystem. ...
> **STOP: For NEW files >150 lines** with repetitive/structured content, do NOT use this tool — you will waste tokens. Instead: `skill('fast-edit')`, then `fe fast-generate --stdin -o FILE` with ≤80 lines of Python generator code.

#### 路由流程

```
AI 任务：编辑或写入文件
  │
  ├─ 小编辑（<80 行）
  │    → AI 正常调用 Edit 工具
  │    → edit.ts 拦截：oldString → findLineRange → fe fast-batch --stdin
  │    → 结果返回给 AI（透明）
  │
  ├─ 小写入（<150 行）
  │    → AI 正常调用 Write 工具
  │    → write.ts 拦截：content → fe fast-paste --stdin
  │    → 结果返回给 AI（透明）
  │
  ├─ 大编辑（>80 行，有规律）
  │    → AI 阅读 Edit description → 看到 STOP 提示
  │    → AI 加载 skill('fast-edit') → 通过 Bash 使用 fe fast-generate
  │
  └─ 大写入（>150 行，有规律）
       → AI 阅读 Write description → 看到 STOP 提示
       → AI 加载 skill('fast-edit') → 通过 Bash 使用 fe fast-generate
```

#### 第 1 步：安装 skill

```bash
git clone https://github.com/includewudi/fast-edit.git ~/.config/opencode/skills/fast-edit
```

#### 第 2 步：复制自定义工具

```bash
cp ~/.config/opencode/skills/fast-edit/opencode-tools/*.ts ~/.config/opencode/tools/
```

这会安装两个文件：
- `edit.ts` — 覆盖内置 Edit。将字符串匹配编辑转换为 `fe fast-batch` 行号操作。
- `write.ts` — 覆盖内置 Write。将文件写入委托给 `fe fast-paste --stdin`。

#### 第 3 步（可选）：添加大文件支持规则

方式 B 自动处理中小编辑。对于大文件生成（>150 行），description 提示会告诉 AI 加载 skill。可选添加精简规则块加强引导：

```
[FAST-EDIT]
For user-pasted content, prefer save-pasted (zero token, zero escaping).
```

无需 `skill("fast-edit")` 触发规则 — 自定义工具自动处理路由。

#### AI 的实际体验

| 操作 | AI 做什么 | 实际发生什么 |
|------|----------|-------------|
| 编辑文件 | 正常调用 Edit 工具 | `edit.ts` → `fe fast-batch`（即时完成，自动备份） |
| 写入文件 | 正常调用 Write 工具 | `write.ts` → `fe fast-paste`（自动备份） |
| 写入 >150 行 | 看到 description 中的 STOP 提示 | AI 加载 skill，使用 `fe fast-generate` |
| 编辑 >80 行 | 看到 description 中的 STOP 提示 | AI 加载 skill，使用 `fe fast-batch`/`fe fast-generate` |

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

### `timer start` / `timer stop TIMER_ID`

跟踪端到端总耗时，包含 AI 思考时间。

```bash
# 启动计时器（返回 timer_id）
fe timer start
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "started_at": "2025-01-01T12:00:00.000000"}

# 停止计时并获取总耗时
fe timer stop t_a1b2c3d4
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "elapsed_sec": 42.5}
```

配合 `generate --timer` 使用时，timing 输出会同时包含脚本执行时间（`elapsed_sec`）和从 timer start 开始的总时间（`total_elapsed_sec`）。这能捕获完整周期：skill 加载 → AI 推理 → 代码执行 → 文件写入。

计时数据存储在 `/tmp/fe-timers/`，stop 后自动清理。


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
| `--timer ID` | 附加计时器（来自 `fe timer start`）用于端到端计时 | - |

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
| 度量端到端任务耗时（含 AI 思考） | `timer start` → 工作 → `generate --timer ID` |

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
├── timer.py       # 端到端计时（timer start/stop）
├── opencode-tools/  # OpenCode 自定义工具覆盖层（edit.ts, write.ts）
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
