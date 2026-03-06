---
name: large-file
description: 大文件生成指南：fast-generate 与分段 heredoc
---

# 大文件生成指南

当 AI 需要创建 >120 行的新文件时，直接输出完整内容会消耗大量 token，且可能截断。本指南提供两种方案：**fast-generate（仅限重复模板≥5次的结构化内容）** 和 **分段 heredoc（DEFAULT 方式）**。

> **⚠️ AI 能力上限硬性警告**
> **你的单次 token 输出上限约 120 行。这是硬性物理限制，任何工具都无法绕过。**
> fast-generate 的代码本身也是你的 token 输出。generate 代码 MUST ≤80 行。
> 只有内容有重复模板（同一模板≥5次 + 变量可枚举）时 generate 才有效，它不是万能压缩器。
> **markdown / 文档 / 含代码块 = 默认非结构化 → MUST 用分段写入。**

**核心思路**：AI 输出紧凑的生成器代码（而非完整文件内容），由代码在本地执行后生成大文件。仅适用于有重复模板的结构化内容。

**决策树**：
```
AI 需要创建大文件
  │
  │  ⚠️ DEFAULT：任何犹豫 → 直接走分段写入
  │
  ├─ Q1: 预估行数
  │    ├─ ≤120 行 → 单段 cat > file << 'EOF'，结束
  │    └─ >120 行 / 不确定 → MUST 分段（继续 Q2）
  │
  ├─ Q2（可选优化，5秒内决定，MUST NOT 超时）:
  │    "结构化" 判定：同一模板重复≥5次 + 变量可枚举 + ≤80行Python可表达？
  │    ⚠️ markdown / 文档 / 含代码块 = 默认非结构化
  │    YES → fast-generate --stdin（见下方 §方式1）
  │    NO / 不确定 → 分段写入（MUST NOT 回头重新评估）
  │
  ├─ 分段写入（DEFAULT）:
  │    每段 ≤120 行
  │    第1段: cat > file << 'EOF'（覆写）
  │    后续段: cat >> file << 'EOF'（追加）
  │    ⚠️ MUST 用引号 heredoc << 'EOF'（防 $ ` 展开）
  │    ⚠️ 每段末尾 MUST 有换行；EOF 标记 MUST 顶格不缩进
  │    写完: wc -l FILE 校验行数
  │    中途失败: rm file → 从头重写，MUST NOT 续写半成品
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

### 推荐：三引号模板风格（而非 lines.append）

生成代码时，**优先用三引号字符串 + f-string 拼接**，而非逐行 `lines.append()`。代码更短、更易读：

```python
# ❌ 冗长：逐行 append
lines = []
lines.append("<?php")
lines.append("")
lines.append("class UserRepo")
lines.append("{")
for name in ["find", "save", "delete"]:
    lines.append(f"    public function {name}(): void")
    lines.append("    {")
    lines.append("        // ...")
    lines.append("    }")
lines.append("}")
print("\n".join(lines))

# ✅ 简洁：三引号模板
parts = []
parts.append('''<?php

class UserRepo
{''')

for name in ["find", "save", "delete"]:
    parts.append(f'''
    public function {name}(): void
    {{
        // ...
    }}''')

parts.append("\n}")
print("".join(parts))
```

**模式总结**：大块静态内容用 `'''...'''`，动态部分用循环 + `f'''...'''`，最后 `"".join(parts)` 或直接 `print()`。

⚠️ **f-string 花括号转义（必读）**

> 生成 **Go / JS / PHP / Java / CSS** 等含花括号 `{}` 的代码时，f-string 会把 `{` `}` 当成占位符。
> **必须双写 `{{` `}}` 来输出字面花括号。**

```python
# ❌ Python 报错：SyntaxError 或 KeyError
code = f"""
function demo() {
    return {result};
}
"""

# ✅ 正确：非变量的花括号双写
code = f"""
function demo() {{
    return {result};
}}
"""

# ✅ 也可以：静态部分不用 f-string，避免转义
header = '''function demo() {
    return '''
code = header + result + "\n}"
```

| 场景 | 推荐写法 |
|------|----------|
| 纯静态内容（无变量插值） | `'''...'''` — 花括号无需转义 |
| 有变量插值 | `f'''...'''` — 非变量花括号写 `{{` `}}` |
| 花括号密度极高（如 JSON 模板） | 用 `json.dumps()` 生成，不手拼 |
| 混合场景 | 静态用 `'''`，动态用 `f'''`，最后 join |

---

## 方式 2: 分段写入（DEFAULT — 大文件默认方式）

当内容无规律、无法用代码生成时（即绝大多数大文件场景），用分段 heredoc 直接追加写入：

```bash
# 第 1 段（≤120 行）— 覆写创建
cat > /path/to/target.md << 'EOF'
...first ≤120 lines...
EOF

# 第 2 段（≤120 行）— 追加
cat >> /path/to/target.md << 'EOF'
...next ≤120 lines...
EOF

# 第 3 段（≤120 行）— 追加
cat >> /path/to/target.md << 'EOF'
...next ≤120 lines...
EOF

# 写完校验
wc -l /path/to/target.md
```

| 要点 | 说明 |
|------|------|
| 每段 MUST ≤120 行 | 超过 120 行 AI 可能截断 |
| 第1段用 `cat >` 覆写 | 后续段 MUST 用 `cat >>` 追加 |
| MUST 用 `<< 'EOF'` 引号 heredoc | 防止 `$变量` 和 `` `反引号` `` 被展开 |
| 每段末尾 MUST 有换行 | 否则下段内容会接在上段最后一行后面 |
| EOF 标记 MUST 顶格 | 不能有空格或 Tab 缩进，否则 heredoc 不终止 |
| 写完 MUST `wc -l` 校验 | 确认实际行数与预期一致 |
| 中途失败 → `rm file` 重写 | MUST NOT 尝试续写半成品文件 |
