---
name: workflows
description: 典型工作流：粘贴保存、大文件生成、编辑验证
---

# 典型工作流

入口摘要：本文档涵盖 fast-edit 的核心使用流程，包括：
- **粘贴保存**：`save-pasted`（首选，零 token）→ `paste --stdin`（降级）→ `paste --stdin --base64`（特殊字符）
- **大文件生成**：`fast-generate`（适用于有规律内容，generate 代码 ≤80 行）→ 分段 heredoc（备选），详见 `large-file.md`
- **编辑验证**：`verify` 对比差异 → `verify-syntax` 语法检查 → `restore` 回滚

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

## 用户粘贴代码到输入框

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

## 用户粘贴含特殊字符的代码 (推荐)

当代码包含引号、`$变量`、反斜杠等特殊字符时，用 base64 避免 shell 转义问题：

```bash
printf '%s' "print('hello \$USER')" | base64 > /tmp/b64.txt
cat /tmp/b64.txt | fe paste /tmp/app.py --stdin --base64
```

## 用户粘贴代码保存文件（首选 save-pasted）

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

## 从零创建大文件 (200+ 行)

> **⚠️ 首选 `fast-generate`，备选分段 heredoc。**
>
> 所有文件写入工具（Write、paste、heredoc）都要求 AI 输出完整文件内容作为 token。
> 当文件 200+ 行时，AI 的输出 token 上限成为瓶颈。
> **`fast-generate` 的核心优势**：AI 只需输出紧凑的 Python 代码（≤80 行），
> 由代码在本地执行后生成大量文件内容。仅适用于有规律的批量内容。

### 决策树

```
AI 需要创建大文件
  │
  ├─ 内容有规律、可用代码生成？(如配置、数据、批量结构)
  │    → fast-generate --stdin（generate 代码必须 ≤80 行）
  │
  ├─ 内容无规律、必须逐字输出？(如自由文本、文章)
  │    ├─ ≤150 行 → 直接 Write 工具或 heredoc
  │    ├─ 150-200 行 → 尝试单次，截断则分段
  │    └─ >200 行 → 分段 heredoc + cat 合并
  │
  └─ 内容已存在于文件/用户粘贴？
       → paste --stdin / save-pasted（不需要生成）
```

### 详细用法

详见 `skills/large-file.md`，包含：
- `fast-generate` 单文件/多文件模式
- 常见致命错误（`main()` 调用、`sys.exit()` 等）
- 分段 heredoc 备选方案

## 用户粘贴多份代码

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
