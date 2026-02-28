---
name: formats
description: JSON 返回格式参考（paste/write/generate）
---

# JSON 返回格式参考

Fast-edit 所有命令返回 JSON 格式，便于 AI 解析和程序化处理。

入口摘要：
- `paste` 返回单文件信息：status/file/lines/bytes/timing
- `write` 返回多文件结果数组：files/results/timing
- `generate` 返回单文件或多文件模式：mode/single|multi/results/stderr

## Write JSON 格式（输入规范）

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
