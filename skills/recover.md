---
name: recover
description: 从 OpenCode Session 恢复文件内容（OpenCode 专属）
---

# Recover — 从 OpenCode Session 恢复文件内容

从 OpenCode 的 session 存储中提取之前写入的文件内容，避免重新生成大文件。适用于 AI 写了大文件但有小错误需要修改的场景。

> **场景**: AI 写了一个大文件（300+ 行）但有小错误，重新生成太慢。
> `recover` 从 OpenCode 的 session 存储中提取上次写入的内容，你只需修改出错的小部分。

## 使用方式

```bash
# 1. 列出最近对某文件的所有写操作
fe recover myfile.py --list

# 2. 恢复最近一次写入（默认 stdout）
fe recover myfile.py

# 3. 恢复第 N 次写入
fe recover myfile.py --nth 3

# 4. 从指定 session 恢复
fe recover myfile.py --session ses_xxx --list

# 5. 输出到文件
fe recover myfile.py --nth 2 -o /tmp/recovered.py
```

## 返回格式

**--list 模式**（列出匹配的写操作）：

```json
{
  "status": "ok",
  "matches": 5,
  "entries": [
    {
      "nth": 1,
      "session": "ses_xxx",
      "tool": "edit",
      "target": "/path/to/file.py",
      "content_len": 4200,
      "preview": "def main():\n    ...",
      "time": "2026-02-27 10:30:00"
    }
  ]
}
```

**恢复模式**（返回实际内容）：

- `tool=bash/cat` → 直接返回文件全部内容（`mode: "full-content"`）
- `tool=edit` → 返回 edit spec，包含 edits 数组（`mode: "edit-replay"`）
- `tool=bash/fast-edit` → 返回 bash 命令内容（供参考）

## 典型工作流

```
AI 写了大文件 → 发现有错
  │
  ├─ fe recover file.py --list      # 找到最近写操作
  ├─ fe recover file.py -o /tmp/r.py # 恢复内容到临时文件
  ├─ fe show /tmp/r.py 50 60         # 查看出错区域
  └─ fe replace /tmp/r.py 55 57 "..." # 只修改出错部分
```

## 检测的写操作类型

| 类型 | 说明 | 恢复方式 |
|------|------|----------|
| `bash/cat` | `cat > FILE << 'EOF'` heredoc | 完整文件内容 |
| `bash/fast-edit` | `fe paste/write/replace` 命令 | bash 命令参考 |
| `edit` | Edit 工具调用 | edit spec (edits 数组) |
| `write` | Write 工具调用 | 文件内容（如果有） |

## 存储结构

```
~/.local/share/opencode/storage/
├── message/{ses_xxx}/msg_xxx.json   # 消息元数据
└── part/{msg_xxx}/prt_xxx.json      # 实际内容（工具调用）
```

> 默认扫描最近 5 个 session。用 `--session` 指定特定 session 以加速。
