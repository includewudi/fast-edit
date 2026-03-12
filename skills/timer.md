---
name: timer
description: Debug 端到端计时模式（可选功能）
---

# Debug 计时模式

> 仅当用户在 `[FAST-EDIT]` 规则中配置了 `debug-timer: true` 时才需要阅读本文档。

端到端计时功能用于测量从 skill 加载到任务完成的总耗时，**包含 AI 思考时间**。

## 使用流程

```
加载 skill 后
  │
  ├─ 1. 立即执行 fe timer start
  │     → 返回 timer_id（如 t_a1b2c3d4）
  │
  ├─ 2. 正常执行编辑/生成任务
  │
  └─ 3. 执行 fast-generate 时带上 --timer <timer_id>
        → timing 输出中会多出 total_elapsed_sec 字段
```

## 命令参考

```bash
# 启动计时器，返回 timer_id
fe timer start
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "started_at": "2025-01-01T12:00:00.000000"}

# 停止计时器，返回总耗时
fe timer stop <timer_id>
# → {"status": "ok", "timer_id": "t_a1b2c3d4", "elapsed_sec": 42.5}

# generate 带计时
fe fast-generate --stdin -o out.php --timer t_a1b2c3d4 << 'PYEOF'
...
PYEOF
# → timing 中会多出 total_elapsed_sec 字段
```

## 计时数据

| 项目 | 说明 |
|------|------|
| 存储位置 | `/tmp/fe-timers/<timer_id>.json` |
| 生命周期 | `timer start` 创建，`timer stop` 后自动删除 |
| 输出字段 | `total_elapsed_sec`（端到端总耗时），附加在 `generate` 的 timing 输出中 |

## 启用方式

在 `[FAST-EDIT]` 规则块中添加 `debug-timer: true`：

```
[FAST-EDIT]
When you need to edit, create, write, or save files:
1. Load the fast-edit skill first: skill("fast-edit")
...
debug-timer: true
```

### 关闭方式

删除 `debug-timer: true` 这一行，或改为 `debug-timer: false`。AI 加载 skill 时会跳过所有 timer 相关操作。

## 源码

- `timer.py` — `start()`, `stop()`, `elapsed()` 函数
- `fast_edit.py` — `timer start` / `timer stop` 子命令入口
- `generate.py` — `--timer` 参数，`_timing()` 中附加 `total_elapsed_sec`
