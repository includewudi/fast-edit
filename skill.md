---
name: fast-edit
description: 大文件编辑、批量修改、剪贴板/stdin粘贴、多文件写入、编辑验证/回滚。用于替代慢速的 Edit/Write 工具。
---

# Fast Edit

行号定位的文件编辑工具。绕过 LSP 等待、权限弹窗、历史数据库。**自动备份 + 验证/回滚**，编辑出错可一键恢复。

## 命令速查

```bash
# 直接调用（推荐，兼容所有 shell）
FE=python3 /path/to/fast-edit/fast_edit.py

# 所有命令支持 fast-* 前缀避免 shell 内置命令冲突
# 如: fast-write, fast-paste, fast-batch, fast-verify

# ── 编辑命令 ──
$FE show FILE START END                # 预览行
$FE replace FILE START END "content\n" # 替换行
$FE insert FILE LINE "content\n"       # 插入（LINE=0 表示开头）
$FE delete FILE START END              # 删除行

# ── 批量编辑 (JSON) ──
$FE fast-batch spec.json
echo '{"file":"a.py","edits":[...]}' | $FE fast-batch --stdin

# ── 粘贴保存 ──
$FE fast-paste FILE                    # 从剪贴板
$FE fast-paste FILE --stdin            # 从 stdin
$FE fast-paste FILE --stdin --extract  # 提取 ```...``` 代码块
$FE fast-paste FILE --stdin --base64   # stdin 内容是 base64 编码

# ── 批量写文件 ──
$FE fast-write spec.json
echo '{"files":[...]}' | $FE fast-write --stdin

# ── 验证/回滚 ──
$FE verify FILE                        # 对比当前文件与备份的差异
$FE verify FILE --context 3            # 显示更多上下文行
$FE restore FILE                       # 回滚到最近备份
$FE backups FILE                       # 列出所有备份
$FE verify-syntax FILE                 # 语言感知语法检查

# ── 其他 ──
$FE check FILE                         # Python 类型检查
$FE check FILE --checker mypy
$FE save-pasted FILE                   # 自动找最近的大粘贴 (>=20行)
$FE save-pasted FILE --min-lines 50    # 自定义行数阈值
$FE save-pasted FILE --msg-id msg_xxx  # 指定消息 ID
$FE save-pasted FILE --extract         # 提取 ```...``` 代码块
$FE save-pasted FILE --nth 2           # 第2个最近的大粘贴
$FE help
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
| 编辑后检查是否改对了 | `verify` |
| 编辑改坏了，一键回滚 | `restore` |
| 编辑后语法检查（多语言） | `verify-syntax` |
| 编辑后类型检查 | `lsp_diagnostics` (推荐) 或 `check` |
| 用户粘贴了超大文件 (600+行) | `save-pasted` |
| AI 从零创建大文件 (200+行) | 分段 heredoc → `cat` 合并 → `paste --stdin` |

## 编辑后验证（推荐工作流）

每次编辑操作（replace/insert/delete/batch）会**自动创建备份**。编辑后可以验证和回滚：

```bash
# 1. 编辑文件
$FE replace /path/to/file.go 10 15 "new code\n"

# 2. 验证：对比编辑前后的差异
$FE verify /path/to/file.go
# 返回 JSON：status, result("changed"/"identical"), added/removed 行数, 具体 diff

# 3. 如果改坏了 → 回滚
$FE restore /path/to/file.go
# 回滚前会保存当前状态（forward backup），所以不会丢失

# 4. 语法检查（支持 Go/Python/Rust/C/C++/Java/TypeScript/JavaScript）
$FE verify-syntax /path/to/file.go
# 返回 JSON：syntax_valid (true/false), checker ("go vet"/"py_compile"/...), output

# 5. 查看所有备份历史
$FE backups /path/to/file.go
```

**验证命令返回格式：**

```json
// verify 返回
{
  "status": "ok",
  "result": "changed",
  "old_lines": 100,
  "new_lines": 102,
  "added": 5,
  "removed": 3,
  "changes": [{"old_start": 10, "new_start": 10, "lines": ["-old", "+new"]}]
}

// verify-syntax 返回
{
  "status": "ok",
  "checker": "go vet",
  "syntax_valid": true,
  "output": ""
}

// restore 返回
{
  "status": "ok",
  "restored_from": "/path/to/backup",
  "lines": 100
}
```

## 多语言编辑最佳实践

> **核心原则**: 所有包含 shell 敏感字符的代码，一律使用 `fast-batch --stdin` + `python3 -c "json.dump()"` 管道。
>
> 编辑前**必须** `show` 确认目标行号。Java/JSX 等代码行号容易偏差。

### 特殊字符安全矩阵

| 字符 | 影响语言 | CLI replace | batch --stdin | 处理方式 |
|------|----------|-------------|---------------|----------|
| `\n` `\t` 字面量 | Go, Java, TS, JSX | ❌ 展开为真换行/Tab | ✅ JSON `\\n` 安全 | 必须 batch |
| `$variable` | PHP, Bash | ❌ shell 展开 | ✅ python `\$` 安全 | 必须 batch |
| 反引号 `` ` `` | Go (struct tag), TS/JSX/Vue (模板字面量) | ❌ shell 执行 | ✅ python `\`` 安全 | 必须 batch |
| 模板字面量 `` `${var}` `` | TS, JSX, Vue | ❌ `$` + `` ` `` 双重危险 | ✅ 安全 | 必须 batch |
| `<tag>` / `>` | JSX, Vue, Java 泛型 | ⚠️ shell 重定向 | ✅ 安全 | 推荐 batch |
| `\` 命名空间 | PHP | ⚠️ 需双转义 | ✅ python `\\\\` | 推荐 batch |
| `{{ mustache }}` | Vue | ✅ 安全 | ✅ 安全 | 无影响 |
| `@decorator` | Java, TS, Python | ✅ 安全 | ✅ 安全 | 无影响 |
| f-string `{var}` | Python | ✅ 安全 | ✅ 安全 | 无影响 |
| `**kwargs` | Python | ✅ 安全 | ✅ 安全 | 无影响 |
| `?.` 可选链 | TS, JSX, Vue | ✅ 安全 | ✅ 安全 | 无影响 |
| `=>` 箭头 | JS/TS/JSX, PHP | ✅ 安全 | ✅ 安全 | 无影响 |
| Emoji / Unicode | 所有语言 | ✅ UTF-8 保持 | ✅ UTF-8 保持 | 无影响 |

### verify-syntax 支持矩阵

| 语言 | 检查器 | 可用性 | 注意事项 |
|------|--------|--------|----------|
| Go | `go vet` | ✅ 可用 | 可能报依赖错误（如删了 import 但代码仍引用），属于预期行为 |
| Python | `py_compile` | ✅ 可用 | 仅语法检查，不检查类型 |
| Rust | `rustc` | ✅ 可用 | — |
| C/C++ | `gcc`/`g++` | ✅ 可用 | — |
| TypeScript | `tsc` | ⚠️ 有限 | 需要 tsconfig.json + node_modules，单文件检查会报缺少模块 |
| JavaScript (.js) | `node --check` | ✅ 可用 | 仅 .js/.mjs，不支持 .jsx |
| JavaScript (.jsx) | — | ❌ 不可用 | `node --check` 不认识 .jsx 扩展名 |
| Java | `javac` | ⚠️ 有限 | 需要 JDK + classpath（Spring 等依赖） |
| PHP | — | ❌ 不可用 | 建议添加 `php -l`（PHP 内置语法检查） |
| Vue (.vue) | — | ❌ 不可用 | 建议用 `lsp_diagnostics`（Volar LSP）或 `vue-tsc` |

> **verify-syntax 定位**: 编辑后的**参考信号**，不是阻断信号。
> AI 应判断报告的错误是编辑引入的还是环境/依赖导致的预期错误。
> 对于 TS/Java/PHP/Vue 等需要完整项目环境的语言，优先使用 `lsp_diagnostics`。

### Go

**危险字符**: `\n`, `\t`, 反引号 `` ` `` (struct tag)

```bash
# ✅ 安全：JSON 中 \\n 保持为字面量 \n
python3 -c "
import json, sys
spec = {
    'file': '/path/to/file.go',
    'edits': [{
        'action': 'replace-lines',
        'start': 10,
        'end': 12,
        'content': 'func main() {\n\tfmt.Printf(\"hello %s\\n\", name)\n}\n'
    }]
}
json.dump(spec, sys.stdout)
" | $FE fast-batch --stdin
$FE replace file.go 10 12 'fmt.Printf("hello %s\n", name)\n'
```

| 场景 | 推荐 |
|------|------|
| 含 `\n`, `\t`, 反引号 | `batch --stdin` + json.dump |
| 简单替换（无特殊字符） | CLI `replace` 可用 |
| 多处编辑 | `batch --stdin`（始终推荐） |

### Python

**安全性最好的语言之一。** f-string `{var}`、`@decorator`、`**kwargs`、类型注解 `[]` 在 CLI 和 batch 中均安全。

| 场景 | 推荐 |
|------|------|
| 含 `\n` 字面量或三引号 `"""` | `batch --stdin` |
| 其他场景 | CLI `replace` 可用 |

### PHP

**核心挑战**: `$variable` 前缀 — shell 会展开为环境变量。

```bash
# ✅ python json.dump 中用 \$ 转义 $，\\\\  四重转义命名空间 \
python3 -c "
import json, sys
spec = {
    'file': 'Controller.php',
    'edits': [{
        'action': 'replace-lines',
        'start': 10, 'end': 10,
        'content': '        \$user = User::find(\$id);\n'
    }]
}
json.dump(spec, sys.stdout)
" | $FE fast-batch --stdin
```

| 场景 | 推荐 |
|------|------|
| 含 `$` 变量（几乎所有 PHP 代码） | `batch --stdin`（必须） |
| 含 `\` 命名空间 | python 中用 `\\\\` 四重转义 |
| 闭包 `function () use ($var)` | `batch --stdin`（必须） |

### Java

**与 Go 相同的 `\n` 展开问题**，额外注意泛型 `<>` 在 shell 中的重定向风险。

| 场景 | 推荐 |
|------|------|
| 含 `\n` 字面量 | `batch --stdin` |
| 含泛型 `ResponseEntity<Map<String, Object>>` | `batch --stdin`（shell `>` 重定向风险） |
| 注解密度高、行号容易偏差 | **编辑前必须 `show` 确认行号** |
| verify-syntax | 需 JDK 环境，实际项目用 `lsp_diagnostics` |

### TypeScript

**模板字面量 `` `${var}` `` 是最大风险** — shell 同时展开 `$` 和执行反引号。

| 场景 | 推荐 |
|------|------|
| 含模板字面量 `` `${var}` `` | `batch --stdin`（必须） |
| 含泛型 `<T>` | `batch --stdin`（shell `>` 风险） |
| 含联合类型 `A \| B` | `batch --stdin`（shell pipe 风险） |
| `@Decorator`、`?.`、`...spread` | CLI 可用 |
| verify-syntax | tsc 需完整项目环境，推荐 `lsp_diagnostics` |

### JavaScript (React JSX)

**同 TypeScript 的模板字面量问题**，额外注意 JSX 标签 `<>` 的 shell 重定向。

| 场景 | 推荐 |
|------|------|
| 含模板字面量 / JSX 标签 | `batch --stdin`（必须） |
| JSX 缩进层次深 | **编辑前 `show` 确认行号** |
| verify-syntax | `node --check` 不支持 .jsx，用 `lsp_diagnostics` |
| Emoji / Unicode / HTML 实体 | CLI 和 batch 均安全 |

### Vue (.vue SFC)

**特殊字符密度最高**：横跨 template / script / style 三个区域。

| 场景 | 推荐 |
|------|------|
| script 区含模板字面量 / 泛型 | `batch --stdin`（必须） |
| template 区 `<slot>` / `<Component>` | `batch --stdin`（shell `>` 风险） |
| `{{ mustache }}`、`:bind`、`@event` | CLI 和 batch 均安全 |
| 跨区域多编辑 | `batch --stdin`（一次完成 template + script + style） |
| verify-syntax | 不支持 .vue，用 `lsp_diagnostics` |

### 黄金规则

```
任何语言，只要代码包含以下任一字符 → 必须 batch --stdin:
  \n  \t  $  `  <>  |  \(PHP命名空间)  """(三引号)

安全管道模式:
  python3 -c "import json,sys; json.dump(spec,sys.stdout)" | $FE fast-batch --stdin

编辑前:
  $FE show FILE START END  # 确认行号再编辑

编辑后:
  $FE verify FILE           # 检查 diff
  lsp_diagnostics(file)      # 类型检查（首选）
  $FE verify-syntax FILE     # 语法检查（备选，参考信号）
```

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

## 返回格式

### paste 命令返回

```json
{
  "status": "ok",
  "file": "/absolute/path/to/file.py",
  "lines": 10,
  "bytes": 256,
  "timing": {
    "start": "2026-02-22T15:01:04.304603",
    "end": "2026-02-22T15:01:04.305128",
    "elapsed_sec": 0.0005
  }
}
```

### write 命令返回
```json
{
  "status": "ok",
  "files": 2,
  "results": [
    {"file": "/absolute/path/to/a.py", "lines": 10, "bytes": 256, "elapsed_sec": 0.0004},
    {"file": "/absolute/path/to/b.py", "lines": 5, "bytes": 128, "elapsed_sec": 0.0003}
  ],
  "timing": {
    "start": "2026-02-22T15:02:21.808521",
    "end": "2026-02-22T15:02:21.809282",
    "elapsed_sec": 0.0008
  }
}
```

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

当 AI 需要**从零生成**一个大文件（无源文件可 `cp`），且内容超过 ~200 行，
单次 Write/echo/heredoc 会因 token 输出上限被截断或超时。
用分段 heredoc + `cat` 合并 + `paste --stdin` 逐步累积：

```bash
FE=(python3 /path/to/fast-edit/fast_edit.py)
# 第 1 段 (~120 行)
cat > /tmp/part1.md << 'PART1'
...first ~120 lines...
PART1

# 第 2 段 (~120 行)
cat > /tmp/part2.md << 'PART2'
...next ~120 lines...
PART2

# 合并 → 写入目标
cat /tmp/part1.md /tmp/part2.md > /tmp/combined.md
$FE paste /path/to/target.md --stdin < /tmp/combined.md

# 清理
rm -f /tmp/part*.md /tmp/combined*.md
```

| 要点 | 说明 |
|------|------|
| 每段建议 120-160 行 | 太长 heredoc 可能超时；太短则轮次多 |
| 用 `'MARKER'` 引号 | 防止 heredoc 内 `$变量` 被展开 |
| **不要用** `insert --stdin` | 多行 stdin 时只写入 1 行 (已知限制) |
| 用 `paste --stdin` | 覆写整个文件，所以每次要 `cat` 累积所有段 |

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
├── fast_edit.py   # CLI 入口
├── core.py        # 文件 I/O
├── edit.py        # 编辑操作（自动备份）
├── paste.py       # 粘贴/写入
├── pasted.py      # OpenCode 存储提取
├── check.py       # Python 类型检查
├── verify.py      # 验证/备份/回滚/语法检查
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

**备选**：如果 LSP 不可用：

| 方式 | 优点 | 缺点 |
|------|------|------|
| `lsp_diagnostics` | 快（LSP 热启动）、支持所有语言 | 需要 LSP 服务运行 |
| `$FE verify-syntax` | 多语言语法检查（Go/Py/Rust/C/TS/Java） | 仅检查语法，不检查类型 |
| `$FE verify` | 查看编辑前后差异，确认改对了 | 需要先有备份 |
| `$FE check` | Python 类型检查 | 仅支持 Python |
