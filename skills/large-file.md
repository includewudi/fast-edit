---
name: large-file
description: 大文件生成指南：fast-generate 与分段 heredoc
---

# 大文件生成指南

当 AI 需要创建 >200 行的新文件时，直接输出完整内容会消耗大量 token，且可能截断。本指南提供两种方案：**fast-generate（适用于有规律内容）** 和 **分段 heredoc（备选）**。

> **⚠️ AI 能力上限硬性警告**
> **你的 token 输出上限约 100-150 行。fast-generate 不会改变这个事实。**
> fast-generate 的代码本身也是你的 token 输出。generate 代码必须 ≤80 行，否则你写不完。
> 只有内容有循环/规律时 generate 才有效，它不是万能压缩器。

**核心思路**：AI 输出紧凑的生成器代码（而非完整文件内容），由代码在本地执行后生成大文件。仅适用于有规律的批量内容（配置、数据、重复结构）。

**决策树**：
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

---

## 方式 1: fast-generate（推荐）

AI 输出 Python 代码，代码在本地执行，stdout 写入文件。

**单文件模式**（stdout → 一个文件）：

```bash
fe() { python3 "/Users/wudi/data/code/ai_tools/git_skills/wudi/fast-edit/fast_edit.py" "$@"; }

# AI 只需写 ≤80 行 Python，生成 200+ 行 JSON
fe fast-generate --stdin -o /path/to/output.json << 'PYEOF'
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
# AI 写 ≤80 行 Python，一次生成多个文件
fe fast-generate --stdin << 'PYEOF'
import json

files = []
for i in range(1, 16):
    files.append({
        "file": f"/path/to/ep{i:02d}/dialogue.md",
        "content": f"# Episode {i}\n\n## Scene 1\n\nDialogue here...\n"
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

| 压缩效果 | 取决于内容规律性。有循环 → 效果好；无规律 → 不适用 |
| 适用场景 | 配置文件、数据文件、有规律的批量内容 |
| generate 代码上限 | **≤80 行**（超过 = AI 写不完，必须拆分任务） |
| JSON 验证 | .json 文件自动验证格式，`--no-validate` 跳过 |
| 原子写入 | 使用 tempfile+rename，写入失败不会留下半成品 |

⚠️ **fast-generate 常见致命错误（必读）**

> 以下错误会导致**输出文件 0 字节**，且无任何报错提示。

| 禁忌 | 原因 | 后果 |
|------|------|------|
| 代码中包含 `if __name__ == "__main__": main()` | Python 执行到 `main()` 会运行整个脚本逻辑 | 脚本副作用被执行，`print(content)` 永远不会被调用 |
| 代码中包含 `sys.exit()` | `sys.exit()` 直接终止进程 | `print()` 之前进程已退出，stdout 为空 → 0 字节文件 |
| 把完整可执行脚本包在 `content = r'''...'''; print(content)` 里 | 三引号内的脚本如果有顶层 `sys.exit()`，Python 会在解析到 `print` 之前终止 | 文件为空或只有部分输出 |

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
    sys.exit(0)  # 进程终止
content = f'result: {resp.text}'
print(content)  # ← 永远执行不到这里
```

**核心原则**：generate 代码 ≠ 目标脚本本身。generate 代码是**生成器**，目标脚本是**被生成的文本**。两者不能混为一体。
> 注意：目标文件内容包含 `main()`/`sys.exit()` 是完全正常的，只要它们在字符串内部（如 `content = '''...'''`），不会被执行。

⚠️ **stdin 换行陷阱（必读）**

> 使用 `--stdin` + heredoc 时，Python 代码中的换行符必须是**真实换行**。
> 如果通过 `echo` 管道传入，`\n` 会被保持为字面量两个字符，导致 Python 语法错误或输出 0 字节。
>
> ```bash
> # ❌ 危险：echo 中的 \n 可能不被展开，导致 Python 收到单行代码
> echo 'import json\nprint(json.dumps({"a":1}))' | fe fast-generate --stdin -o out.json
>
> # ✅ 正确：始终用 heredoc
> fe fast-generate --stdin -o out.json << 'PYEOF'
> import json
> print(json.dumps({"a": 1}))
> PYEOF
> ```

---

## 方式 2: 分段 heredoc（备选）

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
