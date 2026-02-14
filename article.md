# Fast-Edit：让 AI 编辑代码快 100 倍的秘密武器

## 痛点：AI 写代码为什么这么慢？

用过 Cursor、Claude Code、OpenCode 这类 AI 编程工具的朋友，一定经历过这种场景：

> AI 说"我来修改一下这个文件"，然后你就开始等……
>
> 3 秒……5 秒……10 秒……
>
> 终于改完了，结果发现还要改另外两处。
>
> 又是 10 秒……又是 10 秒……

一个简单的三处修改，居然要等 30 秒？

## 原生 Edit 工具为什么慢？

让我们看看 AI 编辑器的原生 Edit 工具是怎么工作的：

```
Edit(
  filePath: "/path/to/file.py",
  oldString: "def hello():\n    print('hello')",
  newString: "def hello():\n    print('hello world')"
)
```

**问题 1：字符串匹配**

AI 需要输出「旧内容」和「新内容」两份完整的代码。一个 500 行的文件改 3 处，AI 可能要输出上千个 token。

**问题 2：LSP 同步**

每次编辑后，编辑器要等 LSP（语言服务器）同步完成，检查类型错误。这个过程通常需要 1-5 秒。

**问题 3：多次调用**

改 3 处就要调用 3 次 Edit，每次都有网络延迟 + LSP 等待。

## Fast-Edit：行号定位 + 批量编辑

我写了一个叫 `fast-edit` 的工具，用完全不同的方式解决这个问题：

```bash
# 显示第 10-15 行
$FE show file.py 10 15

# 替换第 10-12 行
$FE replace file.py 10 12 "new content"

# 批量编辑：一次改多处
$FE batch --stdin << 'EOF'
{
  "file": "file.py",
  "edits": [
    {"action": "replace-lines", "start": 10, "end": 12, "content": "..."},
    {"action": "replace-lines", "start": 50, "end": 52, "content": "..."},
    {"action": "insert-after", "line": 100, "content": "..."}
  ]
}
EOF
```

**核心思路**：
1. 用行号定位，不用字符串匹配
2. 批量编辑，一次搞定多处修改
3. 绕过 LSP，直接操作文件

## 性能对比

| 场景 | 原生 Edit | Fast-Edit |
|------|-----------|-----------|
| 500 行文件改 3 处 | ~15 秒（3 次调用） | **< 0.1 秒**（batch） |
| AI Token 输出 | 旧+新字符串 | **仅行号+内容** |
| LSP 等待 | 每次 0-5 秒 | **0** |

没错，**快了 100 倍以上**。

## 还能做什么？

除了编辑，fast-edit 还解决了几个常见痛点：

### 1. 用户粘贴代码

用户在对话框粘贴一段代码，让 AI 保存到文件：

```bash
echo '用户粘贴的内容' | $FE paste /tmp/app.py --stdin --extract
```

`--extract` 会自动提取 ``` 代码块里的内容。

### 2. 特殊字符处理

代码里有 `$变量`、引号、反斜杠？用 base64 编码绕过 shell 转义：

```bash
echo 'base64编码的内容' | $FE paste /tmp/app.py --stdin --base64
```

### 3. 批量创建文件

一次创建多个文件：

```bash
$FE write --stdin << 'EOF'
{
  "files": [
    {"file": "a.py", "content": "def a(): pass"},
    {"file": "b.py", "content": "def b(): pass"}
  ]
}
EOF
```

### 4. 类型检查

编辑完成后验证代码：

```bash
$FE check file.py
```

## 技术实现

整个工具只有 600 多行 Python 代码，分成 5 个模块：

```
fast-edit/
├── fast_edit.py   # CLI 入口
├── core.py        # 文件 I/O
├── edit.py        # 编辑操作
├── paste.py       # 粘贴/写入
└── check.py       # 类型检查
```

核心逻辑非常简单：

```python
def replace_lines(filepath, start, end, content):
    lines = read_file(filepath).splitlines(keepends=True)
    new_lines = lines[:start-1] + [content] + lines[end:]
    write_file(filepath, ''.join(new_lines))
```

就是读文件、改数组、写回去。没有任何黑魔法。

## 如何使用？

Fast-Edit 是一个 OpenCode Skill，安装后 AI 会自动学会使用：

```bash
# 克隆到 skills 目录
git clone https://github.com/xxx/fast-edit ~/.config/opencode/skills/fast-edit

# 或者创建符号链接
ln -s /path/to/fast-edit ~/.config/opencode/skills/fast-edit
```

然后在 `oh-my-opencode.json` 里启用：

```json
{
  "skills": {
    "enable": ["fast-edit"]
  }
}
```

AI 就会在合适的时机自动使用 fast-edit 来编辑文件。

## 总结

| 问题 | 原生方案 | Fast-Edit 方案 |
|------|----------|----------------|
| 大文件小改动 | 输出大量 token | 只输出行号+内容 |
| 多处修改 | 多次调用 | 一次 batch 搞定 |
| LSP 延迟 | 每次等待 | 完全绕过 |
| 特殊字符 | shell 转义地狱 | base64 编码 |

**一句话总结**：用行号代替字符串匹配，用批量代替多次调用，让 AI 编辑代码快 100 倍。

---

*Fast-Edit 已开源，欢迎 Star 和 PR。*
