# Fast-Edit 重大更新：AI 终于能处理超大文件了

上个月发布 fast-edit 后，收到不少反馈。其中一个问题被提到最多：

> "编辑快了，但创建大文件还是会超时啊。"

说得对。fast-edit v1 解决了编辑速度问题——用行号替代字符串匹配，batch 一次改多处，把 15 秒缩到 0.1 秒。但有一个场景它没覆盖到：

**用户粘贴了一个 1500 行的文件，AI 需要把它存下来。**

原生方案是让 AI 把内容 echo 出来再写入。1500 行？光输出就要 30000 个 token，90 秒，大概率触发 `Output token limit reached`，文件直接写坏。

这次更新，解决的就是这个问题。

## 新功能：save-pasted

一条命令，零 token 输出：

```bash
$FE save-pasted /tmp/big_file.php
```

就这么简单。

**原理**：用户粘贴的内容，其实已经存在编辑器的本地存储里了（`~/.local/share/opencode/storage/part/`）。AI 何必再输出一遍？直接从文件系统读就行了。

### 它能做什么

```bash
# 自动找最近的大粘贴（默认 ≥20 行）
$FE save-pasted /tmp/output.py

# 自定义行数阈值
$FE save-pasted /tmp/output.py --min-lines 50

# 指定消息 ID
$FE save-pasted /tmp/output.py --msg-id msg_xxx

# 提取代码块
$FE save-pasted /tmp/output.py --extract

# 第 2 个最近的大粘贴
$FE save-pasted /tmp/output.py --nth 2
```

### 实测对比

在 Gemini CLI 上处理 1500 行、约 100KB 的文件：

| 维度 | 原生方式 | save-pasted |
|------|----------|-------------|
| Token 消耗 | ~30000 | **~50** |
| 耗时 | 40-90 秒 | **< 0.1 秒** |
| 成功率 | 极大概率截断 | **100%** |
| 数据完整性 | 经常写坏 | **行数验证无误** |

不是快了 100 倍——是从"基本不可用"变成了"瞬间完成"。

## 智能内容提取

用户粘贴的内容往往不是纯代码。可能是这样的：

```
帮我看看这个文件有什么问题：

[Pasted ~800 lines]
<?php
namespace App\Controller;
...800 行 PHP 代码...
```

或者：

```
这是我的配置：
{
    "database": { ... },
    "redis": { ... },
    ...500 行 JSON...
}
帮我优化一下
```

save-pasted 不会傻乎乎地把整段话存下来。它有三层提取逻辑：

1. **标记检测**：识别 `[Pasted ~N lines]` 标记，提取标记后的纯内容
2. **代码块提取**：识别 ``` 围栏代码块，提取最大的那个
3. **结构边界检测**：识别 JSON/XML/数组 的括号配对，自动剥离前后的说明文字

第三层是这次更新的亮点。它能处理这些场景：

| 用户输入 | 提取结果 |
|----------|----------|
| "看看这个 JSON" + `{...500行...}` + "帮我优化" | 只保留 JSON |
| `<configuration>...300行...</configuration>` + "有问题吗" | 只保留 XML |
| "保存这个" + `[{...}, {...}, ...]` + "到文件" | 只保留数组 |

括号配对追踪考虑了字符串内的转义（`\"` 不会打断计数），JSON 嵌套深度也能正确处理。当结构化内容占全文 ≥80% 时才提取，避免误判。

## 大文件创建决策流

另一个常见问题：AI 需要从零生成一个 200+ 行的文件怎么办？

这不是 fast-edit 的写入速度问题——`paste --stdin` 写任意大小都是瞬间。问题出在 AI 的 token 输出上限：heredoc 内容太长会被截断。

这次在文档里加了完整的决策流：

```
AI 需要创建文件
  │
  ├─ 内容已存在（用户粘贴/已有文件）？
  │    → paste --stdin / save-pasted
  │
  ├─ AI 从零生成，≤150 行？
  │    → 直接单次写入
  │
  ├─ AI 从零生成，150-200 行？
  │    → 尝试单次，失败再分段
  │
  └─ AI 从零生成，>200 行？
       → 分段 heredoc + cat 合并
```

配套的分段技巧已经写进了 skill.md，AI 读完就会用。

## 代码变化

新增 `pasted.py` 模块（308 行），整个项目从 600 行增长到约 1000 行：

```
fast-edit/
├── fast_edit.py   # CLI 入口
├── core.py        # 文件 I/O
├── edit.py        # 编辑操作
├── paste.py       # 粘贴/写入
├── pasted.py      # 本地存储提取（新增）
└── check.py       # 类型检查
```

`pasted.py` 的核心逻辑：

```python
# 扫描 OpenCode 存储，找到最近的大粘贴
user_msg_ids = _find_user_msg_ids(limit=50)
for uid in user_msg_ids:
    parts = _get_parts_for_msg(uid)
    for part in parts:
        content = _extract_pasted_content(part["text"])
        if len(content.splitlines()) >= min_lines:
            return content  # 找到了，直接返回
```

三层提取函数 `_extract_pasted_content` 的逻辑：

```python
def _extract_pasted_content(text):
    # 第 1 层：[Pasted ~N lines] 标记
    marker = re.search(r'\[Pasted\s+~?\d+\s+lines?\]', text)
    if marker:
        return text[marker.end():].strip()
    
    # 第 2 层：``` 代码块
    blocks = re.findall(r"```[\w]*\n?([\s\S]*?)```", text)
    if blocks:
        return max(blocks, key=len)
    
    # 第 3 层：JSON/XML 结构边界
    structural = _extract_structural_content(text)
    if structural:
        return structural
    
    return text  # 兜底：原样返回
```

没有外部依赖，纯标准库实现。

## 升级方式

已经安装了 fast-edit 的，直接 pull：

```bash
cd ~/.config/opencode/skills/fast-edit
git pull
```

新安装：

```bash
git clone https://github.com/includewudi/fast-edit ~/.config/opencode/skills/fast-edit
```

## 下一步

这次更新让 fast-edit 覆盖了"大文件"这个最后的痛点。目前的能力矩阵：

| 场景 | 状态 |
|------|------|
| 大文件小改动 | ✅ batch（v1） |
| 多处同时修改 | ✅ batch（v1） |
| 特殊字符处理 | ✅ base64（v1） |
| 用户粘贴大文件 | ✅ save-pasted（新） |
| 智能内容提取 | ✅ 结构边界检测（新） |
| 从零创建大文件 | ✅ 分段 heredoc 流程（新） |

如果你在用 AI 编程工具，遇到过"文件太大处理不了"的问题，试试这个更新。

---

*代码已开源：https://github.com/includewudi/fast-edit ，已安装的请更新到最新。*

*作者：极寒AI*
