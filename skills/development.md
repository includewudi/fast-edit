---
name: development
description: 开发流程、测试与发布检查
---

# Development

> fast-edit 的开发、测试与验证指南。

## 代码结构

```text
fast-edit/
├── fast_edit.py   # CLI 入口与命令分发
├── core.py        # 原子 I/O、换行处理
├── edit.py        # show/replace/insert/delete/batch
├── paste.py       # paste/write
├── pasted.py      # save-pasted（OpenCode 存储）
├── generate.py    # fast-generate
├── verify.py      # backup/verify/restore/verify-syntax
├── check.py       # Python 类型检查
├── README.md / README_CN.md
├── TEST_PLAN.md / TEST_REPORT.md
└── skill.md
```

## 环境准备

```bash
git clone https://github.com/includewudi/fast-edit.git
cd fast-edit
python3 fast_edit.py help
```

如需类型检查：

```bash
pip install basedpyright
# 或 pyright / mypy
```

## 本地开发约定

- **不需要安装**：直接运行 `python3 fast_edit.py`。
- CLI 推荐封装函数：

```bash
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }
```

## 测试

### 测试计划

测试步骤定义在 `TEST_PLAN.md`，覆盖：

- show/replace/insert/delete
- batch 批量编辑
- paste/write (stdin, extract, base64)
- check 类型检查
- base64 encode/decode

### 执行方式（手工）

```bash
fe() { python3 "/path/to/fast-edit/fast_edit.py" "$@"; }
TEST_DIR="/tmp/fast-edit-test"
mkdir -p $TEST_DIR

# 按 TEST_PLAN.md 逐步执行
```

### 测试报告

`TEST_REPORT.md` 记录 37 项测试全部通过：

- Core & Edit (12)
- Paste & Write (5)
- Generate (9)
- Verify & Restore (5)
- Edge Cases (6)

## 调试建议

- 使用 `--context` 扩大 verify diff：`fe verify FILE --context 3`
- `fast-*` 前缀与原命令行为一致，避免 shell 冲突
- 对于大文件生成，优先 `fast-generate`

## 变更检查清单

- `fast_edit.py` 是否新增命令/参数
- 返回 JSON 是否保持兼容
- `verify.py` 备份路径是否稳定
- `generate.py` 是否保持 JSON 校验行为

## 发布前验证

1. 跑 `TEST_PLAN.md` 全部步骤
2. 确认 `TEST_REPORT.md` 更新日期
3. README 与 `skill.md` 中的命令列表保持一致
4. 确认 `fast_edit.py help` 输出无误

