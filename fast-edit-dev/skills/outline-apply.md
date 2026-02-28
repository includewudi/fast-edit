---
name: outline-apply
description: Python AST 符号级查看与编辑（outline + apply）
---

# Outline + Apply — Python 符号级编辑

> 基于 Python AST 的符号定位编辑。先用 `outline` 查看文件结构，再用 `apply` 按符号名执行替换/删除/插入。
>
> **仅支持 Python (.py)**，仅使用 stdlib `ast`，无第三方依赖。

## 命令速查

```bash
# 查看文件符号结构
fe outline FILE.py                         # JSON 格式
fe outline FILE.py --format tree           # 树形格式

# 符号级编辑
fe apply spec.json --dry-run               # 预览（不写文件）
fe apply spec.json --apply                 # 执行编辑
echo '{...}' | fe apply --stdin --dry-run   # stdin 预览
echo '{...}' | fe apply --stdin --apply     # stdin 执行
```

## outline 输出格式

### JSON 格式（默认）

```json
{
  "status": "ok",
  "file": "/abs/path/file.py",
  "symbols": [
    {
      "kind": "function",
      "name": "helper",
      "qualname": "helper",
      "symbol": "helper",
      "span": {"start_line": 1, "end_line": 3}
    },
    {
      "kind": "class",
      "name": "Animal",
      "qualname": "Animal",
      "symbol": "Animal",
      "span": {"start_line": 5, "end_line": 12}
    },
    {
      "kind": "method",
      "name": "speak",
      "qualname": "Animal.speak",
      "symbol": "Animal.speak",
      "span": {"start_line": 8, "end_line": 10}
    }
  ]
}
```

**kind 类型**: `function` | `async_function` | `class` | `method` | `async_method`

**symbol 字段**: 顶层符号 = 裸名（`helper`），嵌套符号 = 限定名（`Animal.speak`）。

### tree 格式

```json
{
  "status": "ok",
  "file": "/abs/path/file.py",
  "tree": "helper (function) L1-3\nAnimal (class) L5-12\n  speak (method) L8-10\n"
}
```

## apply 规范格式（输入）

```json
{
  "file": "/path/to/file.py",
  "mode": "dry-run",
  "ops": [
    {"action": "replace-symbol", "symbol": "Animal.speak", "content": "    def speak(self):\n        return 'woof'\n"},
    {"action": "delete-symbol", "symbol": "helper"},
    {"action": "insert-before-symbol", "symbol": "Animal", "content": "# Animal class\n"},
    {"action": "insert-after-symbol", "symbol": "Animal", "content": "\nclass Plant:\n    pass\n"}
  ]
}
```

### 4 种操作

| action | 作用 | 必要字段 |
|--------|------|----------|
| `replace-symbol` | 替换符号的完整定义 | `symbol`, `content` |
| `delete-symbol` | 删除符号的完整定义 | `symbol` |
| `insert-before-symbol` | 在符号前插入内容 | `symbol`, `content` |
| `insert-after-symbol` | 在符号后插入内容 | `symbol`, `content` |

### 符号寻址规则

- **裸名**（`speak`）：如果全文件唯一，自动匹配
- **限定名**（`Animal.speak`）：精确匹配，不会歧义
- **歧义时报错**：裸名匹配到多个符号时返回 `candidates` 列表

```json
{"status": "error", "message": "apply: ambiguous symbol 'run'", "candidates": ["run", "Task.run", "Worker.run"]}
```

## apply 输出格式

### dry-run 模式

```json
{
  "status": "ok",
  "mode": "dry-run",
  "file": "/abs/path/file.py",
  "ops_resolved": [
    {"action": "replace-symbol", "symbol": "Animal.speak", "span": {"start_line": 8, "end_line": 10}}
  ]
}
```

### apply 模式

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

`syntax_valid`: 编辑后自动 `py_compile` 检查，`true` = 语法正确。

## 错误响应

| 场景 | message | 附加字段 |
|------|---------|----------|
| 符号歧义 | `apply: ambiguous symbol 'X'` | `candidates`: 所有匹配的限定名 |
| 符号不存在 | `apply: symbol 'X' not found` | `available`: 文件中所有符号列表 |
| 非 .py 文件 | `apply: only .py files supported` | — |
| Python 语法错误 | `outline: syntax error in FILE` | `detail`: 错误信息 |

## 典型工作流

```bash
# 1. 查看文件结构
fe outline src/models.py --format tree
# → User (class) L1-20
#     __init__ (method) L2-5
#     save (method) L7-15
#     validate (method) L16-20

# 2. 构造编辑规范（替换 validate 方法）
echo '{
  "file": "src/models.py",
  "mode": "dry-run",
  "ops": [{"action": "replace-symbol", "symbol": "User.validate", "content": "    def validate(self):\n        if not self.name:\n            raise ValueError(\"name required\")\n"}]
}' | fe apply --stdin --dry-run

# 3. 确认 span 正确后执行
echo '{...}' | fe apply --stdin --apply

# 4. 验证
fe verify src/models.py
fe verify-syntax src/models.py
```

## 适用场景

| 场景 | 推荐方式 |
|------|----------|
| 替换整个函数/方法体 | `apply` (replace-symbol) |
| 删除某个类或函数 | `apply` (delete-symbol) |
| 在函数前后插入装饰器/注释 | `apply` (insert-before/after-symbol) |
| 需要先了解文件结构再编辑 | `outline` → `apply` |
| 行号级精确编辑 | 仍然用 `replace` / `batch`（更灵活） |
| 非 Python 文件 | 不支持，用行号级命令 |

## 约束

- **仅 Python (.py)**：基于 stdlib `ast`，不支持其他语言
- **仅顶层 + 一级嵌套**：支持 `def foo` 和 `class Foo.method`，不支持嵌套函数
- **不支持跨文件重构**：每次 apply 只操作一个文件
- **不修改 import / 全局变量**：outline 只提取 `def`/`class` 定义