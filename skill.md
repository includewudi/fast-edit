---
name: fast-edit
description: 大文件编辑、批量修改、剪贴板/stdin粘贴、多文件写入、编辑验证/回滚。用于替代慢速的 Edit/Write 工具。
---

# Fast Edit

行号定位的文件编辑工具。绕过 LSP 等待、权限弹窗、历史数据库。**自动备份 + 验证/回滚**，编辑出错可一键恢复。

## 命令速查

```bash
# ⚠️ 优先用函数封装（FE=... 变量在 zsh 下 $FE 只展开第一个词，会导致 command not found）
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }

# 所有命令支持 fast-* 前缀避免 shell 内置命令冲突
# 如: fast-write, fast-paste, fast-batch, fast-verify

# ── 编辑命令 ──
fe show FILE START END                # 预览行
fe replace FILE START END "content\n" # 替换行
fe insert FILE LINE "content\n"       # 插入（LINE=0 表示开头）
fe delete FILE START END              # 删除行

# ── 批量编辑 (JSON) ──
fe fast-batch spec.json
echo '{"file":"a.py","edits":[...]}' | fe fast-batch --stdin

# ── 粘贴保存 ──
fe fast-paste FILE                    # 从剪贴板
fe fast-paste FILE --stdin            # 从 stdin
fe fast-paste FILE --stdin --extract  # 提取 ```...``` 代码块
fe fast-paste FILE --stdin --base64   # stdin 内容是 base64 编码

# ── 批量写文件 ──
fe fast-write spec.json
echo '{"files":[...]}' | fe fast-write --stdin
# ⚠️ --stdin 管道传 JSON 时，echo 中的 \n 会被 shell 解释为真换行，导致 JSON 无效
# 推荐用 printf '%s' 或 heredoc << 'EOF' 或 python3 -c "json.dump(...)" 构造 JSON
# ── 代码生成写文件（推荐用于批量生成 200+ 行） ──
echo 'python_code' | fe fast-generate --stdin -o output.json   # 单文件
echo 'python_code' | fe fast-generate --stdin                   # 多文件(stdout=JSON)
fe fast-generate script.py -o output.json                       # 脚本文件模式
fe fast-generate script.py -o out.json --timeout 60             # 自定义超时
fe fast-generate --stdin -o out.json --no-validate              # 跳过 JSON 验证

# ── 验证/回滚 ──
fe verify FILE                        # 对比当前文件与备份的差异
fe verify FILE --context 3            # 显示更多上下文行
fe restore FILE                       # 回滚到最近备份
fe backups FILE                       # 列出所有备份
fe verify-syntax FILE                 # 语言感知语法检查

# ── 其他 ──
fe check FILE                         # Python 类型检查
fe check FILE --checker mypy
fe save-pasted FILE                   # 自动找最近的大粘贴 (>=20行)
fe save-pasted FILE --min-lines 50    # 自定义行数阈值
fe save-pasted FILE --msg-id msg_xxx  # 指定消息 ID
fe save-pasted FILE --extract         # 提取 ```...``` 代码块
fe save-pasted FILE --nth 2           # 第2个最近的大粘贴
fe help
```
## ⚠️ replace 前必须确认行号（强制规则）

> **绝对不要凭记忆 replace。** 行号会因为之前的编辑而偏移，AI 数行号容易 off-by-one。

**必须遵守的流程：**

```
replace/delete 操作
  │
  ├─ 第1步: fe show FILE START END
  │    确认首行和末行内容是否匹配你要替换的目标
  │    ⚠️ 重点检查 END 行 — off-by-one 最常发生在末行
  │
  ├─ 第2步: 确认行号正确后，再执行 replace
  │    fe replace FILE START END "content\
"
  │
  └─ 第3步: 检查返回的 warnings 字段
       如果有 warnings，立即检查并修复
```

**常见 off-by-one 错误模式：**

| 错误 | 后果 | 预防 |
|------|------|------|
| END 少了1行 | 目标的最后一行残留，与新内容重复 | show 确认 END 行内容 |
| END 多了1行 | 多删了下一行代码 | show 确认 END+1 行不是你要保留的 |
| START 偏移 | 替换了错误的起始位置 | show 确认 START 行内容 |

**反面案例（导致编译错误）：**
```bash
# ❌ 错误：凭记忆 replace，END 少1行
fe replace file.dart 74 78 "new widget code\
"
# 结果：第79行残留了旧代码，与新代码重复 → 编译错误

# ✅ 正确：先 show 确认
fe show file.dart 74 80    # 看清楚79行是什么
fe replace file.dart 74 79 "new widget code\
"  # 确认后再替换
```

## 使用场景
> **⚡ 粘贴保存优先级**: 用户粘贴代码需要保存时，**始终优先尝试 `save-pasted`**。
> 它直接从 OpenCode 本地存储提取，零 token 输出、零 shell 转义问题。
> 仅当 `save-pasted` 不可用（如内容非用户粘贴、或存储中找不到）时，才降级到 `paste --stdin`。

```
用户粘贴了代码，要求保存到文件
  │
  ├─ 首选: save-pasted FILE
  │    零 token、零转义、自动从本地存储提取
  │    150+ 行时强烈推荐（echo/heredoc 可能截断）
  │
  ├─ 降级: paste FILE --stdin (< 150 行、save-pasted 失败时)
  │    echo '内容' | fe paste FILE --stdin
  │
  └─ 特殊字符多: paste FILE --stdin --base64
       含 $、反引号、引号嵌套时用 base64 编码
```
| 场景 | 命令 |
|------|------|
| 大文件 (100+ 行) 小改动 | `replace` / `batch` |
| 同文件多处编辑 | `batch` |
| **用户粘贴代码，保存文件（首选）** | **`save-pasted`** |
| 用户粘贴代码，save-pasted 不可用时 | `paste --stdin` |
| 用户粘贴含特殊字符的代码 | `paste --stdin --base64` |
| 用户粘贴多份代码，保存多文件 | `write --stdin` |
| 从剪贴板保存 | `paste` |
| 编辑后检查是否改对了 | `verify` |
| 编辑改坏了，一键回滚 | `restore` |
| 编辑后语法检查（多语言） | `verify-syntax` |
| 编辑后类型检查 | `lsp_diagnostics` (推荐) 或 `check` |
| AI 从零生成大文件/批量文件 (200+行) | **`fast-generate --stdin`** (代码生成，5x+ token 压缩) |
| AI 从零生成大文件 (备选, 无 Python) | 分段 heredoc → `cat` 合并 → `paste --stdin` |

## 编辑后验证（推荐工作流）

每次编辑操作（replace/insert/delete/batch）会**自动创建备份**。编辑后可以验证和回滚：

```bash
# 1. 编辑文件
fe replace /path/to/file.go 10 15 "new code\n"

# 2. 验证：对比编辑前后的差异
fe verify /path/to/file.go
# 返回 JSON：status, result("changed"/"identical"), added/removed 行数, 具体 diff

# 3. 如果改坏了 → 回滚
fe restore /path/to/file.go
# 回滚前会保存当前状态（forward backup），所以不会丢失

# 4. 语法检查（支持 Go/Python/Rust/C/C++/Java/TypeScript/JavaScript）
fe verify-syntax /path/to/file.go
# 返回 JSON：syntax_valid (true/false), checker ("go vet"/"py_compile"/...), output

# 5. 查看所有备份历史
fe backups /path/to/file.go
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

## replace/batch 自动 warnings

`replace` 和 `batch`（replace-lines）操作会自动检测常见 AI 编辑错误，在返回 JSON 中附加 `warnings` 字段。

**检测的错误类型：**

| Warning | 含义 | 常见原因 |
|---------|------|----------|
| `DUPLICATE_LINE` | 替换内容的最后一行与紧邻的下一行完全相同 | END 行号少了1（off-by-one），旧代码残留 |
| `BRACKET_BALANCE` | 替换前后 `(){}[]` 括号平衡发生变化 | 替换内容缺少闭合括号，或多包含了开括号 |

**返回示例：**

```json
// replace 有 warning 时
{
  "status": "ok",
  "file": "/path/to/file.dart",
  "removed": 5,
  "added": 8,
  "total": 198,
  "warnings": [
    "DUPLICATE_LINE: line 83 is identical to the last replaced line (possible off-by-one in END). Content: '  subtitle: Text(device.lastSeen),'",
    "BRACKET_BALANCE: ()...() changed by -1 (1 more closes). Replacement may have mismatched brackets."
  ]
}
```

**收到 warnings 后必须：**
1. `DUPLICATE_LINE` → 检查是否 END 需要 +1，用 `show` 确认后重新 `replace`
2. `BRACKET_BALANCE` → 检查替换内容的括号是否完整闭合
3. 如果是误报（故意的不平衡替换）→ 忽略即可

> **注意**: 没有 warnings 时，返回 JSON 中不包含 `warnings` 字段（不会返回空数组）。

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
" | fe fast-batch --stdin
fe replace file.go 10 12 'fmt.Printf("hello %s\n", name)\n'
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
" | fe fast-batch --stdin
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
  python3 -c "import json,sys; json.dump(spec,sys.stdout)" | fe fast-batch --stdin

编辑前:
  fe show FILE START END  # 确认行号再编辑

编辑后:
  fe verify FILE           # 检查 diff
  lsp_diagnostics(file)      # 类型检查（首选）
  fe verify-syntax FILE     # 语法检查（备选，参考信号）
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

> ⚠️ **字段名是 `"action"` 不是 `"type"`！** 常见错误：写成 `"type": "replace"` 会被静默忽略。
> 正确写法：`"action": "replace-lines"` / `"action": "insert-after"` / `"action": "delete-lines"`。

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

## Generate 返回格式

### generate 单文件返回

```json
{
  "status": "ok",
  "mode": "single",
  "files": 1,
  "results": [{"file": "/absolute/path/to/file.json", "lines": 200, "bytes": 4096}],
  "stderr": null,
  "timing": {
    "start": "2026-02-25T15:01:04.304603",
    "end": "2026-02-25T15:01:04.335128",
    "elapsed_sec": 0.03
  }
}
```

### generate 多文件返回

```json
{
  "status": "ok",
  "mode": "multi",
  "files": 3,
  "results": [
    {"file": "/path/a.json", "lines": 44, "bytes": 532},
    {"file": "/path/b.md", "lines": 20, "bytes": 312},
    {"file": "/path/c.json", "lines": 88, "bytes": 1024}
  ],
  "stderr": null,
  "timing": {
    "start": "2026-02-25T15:02:21.808521",
    "end": "2026-02-25T15:02:21.839282",
    "elapsed_sec": 0.03
  }
}
```

### generate 错误返回

```json
{
  "status": "error",
  "message": "Script execution failed",
  "exit_code": 1,
  "stderr": "NameError: name 'foo' is not defined",
  "stdout": "",
  "timing": {"start": "...", "end": "...", "elapsed_sec": 0.01}
}
```

## 典型工作流

### 用户粘贴代码到输入框
> **首选 `save-pasted`**，失败时才用 `paste --stdin`。

```
用户: 保存这个到 /tmp/app.py
```python
def main():
    print("hello")
```

AI 执行:
# 首选: 直接从本地存储提取（零 token）
fe save-pasted /tmp/app.py --extract

# 降级: save-pasted 失败时
echo '<用户粘贴的内容>' | fe paste /tmp/app.py --stdin --extract
```

### 用户粘贴含特殊字符的代码 (推荐)

当代码包含引号、`$变量`、反斜杠等特殊字符时，用 base64 避免 shell 转义问题：

```bash
printf '%s' "print('hello \$USER')" | base64 > /tmp/b64.txt
cat /tmp/b64.txt | fe paste /tmp/app.py --stdin --base64
```

### 用户粘贴代码保存文件（首选 save-pasted）

> **始终优先使用 `save-pasted`**，不论代码长短。
> 150+ 行时强烈推荐 — echo/heredoc 可能截断。
```bash
# 直接从 OpenCode 的本地存储提取，零 token 输出
fe save-pasted /tmp/app.py

# 提取 ```...``` 代码块
fe save-pasted /tmp/app.py --extract
# 然后正常编辑
fe show /tmp/app.py 1 20
fe replace /tmp/app.py 10 12 "new content\n"
```
原理：用户粘贴的内容已存储在 `~/.local/share/opencode/storage/part/`，
`save-pasted` 直接读取文件系统，不需要 AI 重新输出。
**save-pasted 失败时**（找不到匹配的粘贴内容）才降级到 `paste --stdin`。

### 从零创建大文件 (200+ 行)

> **⚠️ 首选 `fast-generate`，备选分段 heredoc。**
>
> 所有文件写入工具（Write、paste、heredoc）都要求 AI 输出完整文件内容作为 token。
> 当文件 200+ 行时，AI 的输出 token 上限成为瓶颈。
> **`fast-generate` 的核心优势**：AI 只需输出紧凑的 Python 代码（~70 行），
> 由代码在本地执行后生成 375+ 行的文件内容 —— **5x+ token 压缩比**。
>
> ```
> AI 需要创建大文件
>   │
>   ├─ 内容有规律、可用代码生成？(如配置、数据、批量结构)
>   │    → fast-generate --stdin（首选，5x+ 压缩）
>   │
>   ├─ 内容无规律、必须逐字输出？(如自由文本、文章)
>   │    ├─ ≤150 行 → 直接 Write 工具或 heredoc
>   │    ├─ 150-200 行 → 尝试单次，截断则分段
>   │    └─ >200 行 → 分段 heredoc + cat 合并
>   │
>   └─ 内容已存在于文件/用户粘贴？
>        → paste --stdin / save-pasted（不需要生成）
> ```

#### 方式 1: fast-generate（推荐）

AI 输出 Python 代码，代码在本地执行，stdout 写入文件。

**单文件模式**（stdout → 一个文件）：

```bash
fe() { python3 "/Users/wudi/data/code/ai_tools/git_skills/wudi/fast-edit/fast_edit.py" "$@"; }

# AI 只需写 ~30 行 Python，生成 200+ 行 JSON
python3 << 'PYEOF' | fe fast-generate --stdin -o /path/to/output.json
import json

data = {
    "episodes": [
        {
            "id": i,
            "title": f"Episode {i}",
            "scenes": [{"shot": j, "duration": 2.5} for j in range(1, 7)]
        }
        for i in range(1, 16)
    ]
}
print(json.dumps(data, indent=2, ensure_ascii=False))
PYEOF
```

**多文件模式**（stdout = JSON 文件规范）：

```bash
# AI 写 ~70 行 Python，一次生成多个文件
python3 << 'PYEOF' | fe fast-generate --stdin
import json

files = []
for i in range(1, 16):
    files.append({
        "file": f"/path/to/ep{i:02d}/dialogue.md",
        "content": f"# Episode {i}

## Scene 1

Dialogue here...
"
    })
    files.append({
        "file": f"/path/to/ep{i:02d}/config.json",
        "content": json.dumps({"episode": i, "duration": 30}, indent=2)
    })

print(json.dumps({"files": files}))
PYEOF
```

**返回格式**：

```json
{
  "status": "ok",
  "mode": "single",
  "files": 1,
  "results": [{"file": "/abs/path", "lines": 44, "bytes": 532}],
  "stderr": null,
  "timing": {"start": "...", "end": "...", "elapsed_sec": 0.03}
}
```

**选项**：

| 选项 | 说明 |
|------|------|
| `--stdin` | 从 stdin 读取代码（与 heredoc/pipe 配合） |
| `-o FILE` | 单文件模式：stdout 直接写入该文件 |
| `--timeout N` | 执行超时，默认 30 秒 |
| `--interpreter CMD` | 解释器，默认 python3 |
| `--no-validate` | 跳过 .json 文件的 JSON 格式验证 |

| 要点 | 说明 |
|------|------|
| 压缩比 | ~70 行 Python → 375+ 行输出（5x+） |
| 适用场景 | 配置文件、数据文件、有规律的批量内容 |
| JSON 验证 | .json 文件自动验证格式，`--no-validate` 跳过 |
| 原子写入 | 使用 tempfile+rename，写入失败不会留下半成品 |

⚠️ **fast-generate 常见致命错误（必读）**

> 以下错误会导致**输出文件 0 字节**，且无任何报错提示。

| 禁忌 | 原因 | 后果 |
|------|------|------|
| 代码中包含 `if __name__ == "__main__": main()` | Python 执行到 `main()` 会运行整个脚本逻辑（API 调用、文件操作等），而不是计算 `content` | 脚本副作用被执行，`print(content)` 永远不会被调用 |
| 代码中包含 `sys.exit()` | `sys.exit()` 直接终止进程 | `print()` 之前进程已退出，stdout 为空 → 0 字节文件 |
| 把完整可执行脚本包在 `content = r'''...'''; print(content)` 里 | 三引号内的 `import`/`def`/`class` 虽然不会执行，但如果脚本内部调用了 `main()` 或有顶层 `sys.exit()`，Python 会在解析到 `print` 之前终止 | 文件为空或只有部分输出 |

**正确写法**：fast-generate 的代码应该**只做一件事** — 计算并 `print()` 文件内容。

```python
# ✅ 正确：纯粹的内容生成
content = '''#!/usr/bin/env python3
import sys
import json

def main():
    data = json.load(sys.stdin)
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
'''
print(content)

# ❌ 错误：把真正的脚本逻辑放进来
import sys
import requests  # 会真的执行！

def main():
    resp = requests.get('https://api.example.com')  # 真的发请求！
    # ... 做了一堆事 ...
    sys.exit(0)  # 进程终止，print 永远不会执行

content = f'result: {resp.text}'
print(content)  # ← 永远执行不到这里
```

**核心原则**：generate 代码 ≠ 目标脚本本身。generate 代码是**生成器**，目标脚本是**被生成的文本**。两者不能混为一体。

#### 方式 2: 分段 heredoc（备选）

当内容无规律、无法用代码生成时，用分段 heredoc + `cat` 合并：

```bash
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
fe paste /path/to/target.md --stdin < /tmp/combined.md

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
fe write --stdin << 'EOF'
{"files": [
  {"file": "file1.py", "content": "def a(): pass\n"},
  {"file": "file2.py", "content": "def b(): pass\n"}
]}
EOF
```

## 文件结构

fast-edit/
├── fast_edit.py   # CLI 入口
├── core.py        # 文件 I/O
├── edit.py        # 编辑操作（自动备份）
├── paste.py       # 粘贴/写入
├── pasted.py      # OpenCode 存储提取
├── generate.py    # 代码生成写文件（fast-generate）
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
| `fe verify-syntax` | 多语言语法检查（Go/Py/Rust/C/TS/Java） | 仅检查语法，不检查类型 |
| `fe verify` | 查看编辑前后差异，确认改对了 | 需要先有备份 |
| `fe check` | Python 类型检查 | 仅支持 Python |
