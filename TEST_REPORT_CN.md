# Fast Edit — 测试报告

> **版本**: v2（含 `generate` 命令）  
> **日期**: 2026-02-26  
> **环境**: macOS (darwin), Python 3.x  
> **结果**: **37/37 全部通过** ✅

## 总览

| 阶段 | 覆盖范围 | 测试数 | 通过 | 失败 |
|------|----------|--------|------|------|
| 1 — 核心编辑 | show, replace, insert, delete, batch | 12 | 12 | 0 |
| 2 — 粘贴写入 | stdin 粘贴、代码提取、base64、多文件写入 | 5 | 5 | 0 |
| 3 — 代码生成 | 单文件/多文件、超时、校验、大文件 | 9 | 9 | 0 |
| 4 — 验证回滚 | diff 对比、回滚、备份列表、语法检查 | 5 | 5 | 0 |
| 5 — 边界情况 | 未知命令、缺参数、CRLF、unicode、前缀等价 | 6 | 6 | 0 |
| **合计** | | **37** | **37** | **0** |

## 发现并修复的 Bug

### 测试 33：缺少必需参数（已修复）

**问题**: `python3 fast_edit.py show`（不带文件路径）返回 `"Unknown command: show"` 而不是有用的错误提示。

**原因**: CLI 分发器中每个命令分支都用 `and len(rest) >= N` 做参数数量守卫。当已知命令参数不足时，所有分支都不匹配，最终落到 `else` 分支，报告"未知命令"。

**修复**: 将兜底 `else` 改为两步检查：
1. 在已知命令表中查找命令名（去掉 `fast-` 前缀）
2. 找到 → 返回 `"Missing arguments for {cmd}. Usage: {cmd} {用法}"`
3. 未找到 → 返回 `"Unknown command: {cmd}"`

**验证**: `show`、`fast-show`、`replace`、`fast-verify` 不带参数时均返回正确的用法提示。未知命令仍报告"Unknown command"。

---

## 阶段 1：核心编辑（12 项测试）

| # | 测试项 | 预期结果 | 状态 | 备注 |
|---|--------|----------|------|------|
| 1 | help 命令 | 列出所有命令，包含 `generate` | ✅ 通过 | |
| 2 | show 基础 | 显示第 3-7 行及行号 | ✅ 通过 | |
| 3 | show 越界 | 自动钳位到 1-10，不报错 | ✅ 通过 | |
| 4 | replace 基础 | 第 2-3 行被替换，total=4 | ✅ 通过 | |
| 5 | 备份创建 | replace 后 `.fast-edit-backup` 存在 | ✅ 通过 | |
| 6 | DUPLICATE_LINE 警告 | `warnings` 包含 DUPLICATE_LINE | ✅ 通过 | |
| 7 | BRACKET_BALANCE 警告 | `warnings` 包含 BRACKET_BALANCE | ✅ 通过 | |
| 8 | insert 行首 | LINE=0 时 "prepended" 出现在第一行 | ✅ 通过 | |
| 9 | insert 中间 | "middle" 插入到第 2 行之后 | ✅ 通过 | |
| 10 | delete 范围 | 5 行删 2-4 后只剩第 1、5 行 | ✅ 通过 | |
| 11 | batch 单文件 | 编辑正确应用 | ✅ 通过 | * |
| 12 | batch 多文件 | 两个文件均被编辑 | ✅ 通过 | * |

\* 测试 11-12：batch JSON 需使用 `"action": "replace-lines"`（不是 `"type": "replace"`）。

## 阶段 2：粘贴写入（5 项测试）

| # | 测试项 | 预期结果 | 状态 | 备注 |
|---|--------|----------|------|------|
| 13 | paste stdin 基础 | 文件包含 "hello from stdin" | ✅ 通过 | |
| 14 | paste 代码提取 | 文件仅包含代码块内容 | ✅ 通过 | |
| 15 | paste base64 | 文件包含 "Hello World"（已解码） | ✅ 通过 | |
| 16 | fast-write 多文件 | 两个文件均创建成功 | ✅ 通过 | * |
| 17 | fast-write 提取 | 代码块内容被正确提取 | ✅ 通过 | * |

\* 测试 16-17：`fast-write --stdin` 需要正确转义的 JSON（`\\n` 而非 shell 解释的 `\n`）。

## 阶段 3：代码生成（9 项测试）

| # | 测试项 | 预期结果 | 状态 | 备注 |
|---|--------|----------|------|------|
| 18 | 单文件生成 | 输出有效 JSON 文件，带缩进 | ✅ 通过 | |
| 19 | 多文件生成 | 两个文件均正确创建 | ✅ 通过 | |
| 20 | 脚本文件模式 | 文件包含脚本输出 | ✅ 通过 | |
| 21 | 无效 JSON 报错 | 错误: "Generated content is not valid JSON" | ✅ 通过 | |
| 22 | --no-validate 跳过校验 | 无效内容也能写入 | ✅ 通过 | |
| 23 | stderr 捕获 | `exit_code: 1`，stderr 被捕获 | ✅ 通过 | |
| 24 | 超时执行 | 2 秒后超时（非 10 秒） | ✅ 通过 | 实测 2.003s |
| 25 | 大文件生成 | 802 行输出，JSON 有效 | ✅ 通过 | 73 倍压缩 |
| 26 | 部分失败 | 有效文件创建，无效文件被拒绝 | ✅ 通过 | |

## 阶段 4：验证回滚（5 项测试）

| # | 测试项 | 预期结果 | 状态 | 备注 |
|---|--------|----------|------|------|
| 27 | verify 显示 diff | 展示增删行数和具体差异 | ✅ 通过 | |
| 28 | restore 回滚 | 文件恢复到编辑前内容 | ✅ 通过 | |
| 29 | backups 列表 | 列出备份记录和时间戳 | ✅ 通过 | |
| 30 | verify-syntax Python | 正确代码 → `syntax_valid: true`；错误代码 → SyntaxError | ✅ 通过 | |
| 31 | 无备份时 verify | 错误: "No backup found" | ✅ 通过 | |

## 阶段 5：边界情况（6 项测试）

| # | 测试项 | 预期结果 | 状态 | 备注 |
|---|--------|----------|------|------|
| 32 | 未知命令 | 错误: "Unknown command: nonexistent-command" | ✅ 通过 | |
| 33 | 缺少必需参数 | 错误: "Missing arguments for show. Usage: ..." | ✅ 通过 | 已修复 |
| 34 | 文件不存在 | 错误包含 "No such file or directory" | ✅ 通过 | |
| 35 | CRLF 保留 | 未修改行保留 `\r\n` 换行符 | ✅ 通过 | xxd 验证 |
| 36 | unicode/emoji | 中文、日文、emoji 均正确处理 | ✅ 通过 | |
| 37 | fast-* 前缀等价 | `fast-show` 与 `show` 输出一致 | ✅ 通过 | |

---

## 测试中的发现

### Batch JSON 格式
正确的 batch JSON 格式使用 `"action": "replace-lines"`（不是 `"type": "replace"`）。支持的 action：
- `replace-lines` — 替换行范围
- `insert-after` — 在指定行后插入
- `delete-lines` — 删除行范围

### fast-write --stdin 的 shell 转义
通过 `echo` 管道传 JSON 时，JSON 字符串中的 `\n` 会被 shell 解释为真换行，导致 JSON 无效。解决方案：
- 用 `printf '%s'` 代替 `echo`
- 用 heredoc `<< 'EOF'`（单引号标记防止变量展开）
- 用 `python3 -c "json.dump(...)"` 构造复杂 JSON

### Generate 压缩比
测试 25 实现了 **73 倍压缩**：11 行 Python 提示生成了 802 行有效 JSON 输出。验证了 `generate` 命令的设计目标——绕过 AI 输出 token 上限来批量创建文件。

### CRLF 处理
fast-edit 在 replace 操作中保留未修改行的 CRLF（`\r\n`）换行符。被替换的行使用新内容指定的换行符。
