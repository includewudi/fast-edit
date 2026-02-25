# Fast-Edit 多语言测试报告 — Golang

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | Go 1.x |
| 测试文件 | `/tmp/fe-lang-test/go/server.go` |
| 文件类型 | HTTP REST API server |
| 原始行数 | 90 行 |
| 编辑后行数 | 98 行 |
| 测试项数 | 12 |
| 通过 | 11 ✅ |
| 已知问题 | 1 ⚠️ (CLI replace 展开 `\n`，非 bug) |
| 测试日期 | 2026-02-25 |

## 特殊字符清单

Go 代码包含以下需要特殊处理的字符：

| 字符 | 示例 | 说明 |
|------|------|------|
| `\n` | `log.Printf("hello\n")` | Go 字符串转义，CLI replace 会展开为真换行 |
| `\t` | `log.Printf("\t%s")` | 同上，展开为真 Tab |
| `` ` `` | `` `json:"id"` `` | struct tag 反引号 |
| `%s`, `%v`, `%d` | `fmt.Sprintf("%s", v)` | format verb，shell 无影响但需保留 |
| `*` | `func (r *APIResponse)` | 指针，shell glob 风险 |
| `&` | `resp := &APIResponse{...}` | 取地址符 |

## 测试用例

### 1. show — 预览 struct 定义（含反引号 tag）
```bash
fe show server.go 12 27
```
- **结果**: ✅ 正确显示 User struct 和 APIResponse struct
- **验证**: 反引号 tag `` `json:"id"` ``, `` `json:"data,omitempty"` `` 完整显示
- **验证**: 指针接收器 `func (r *APIResponse)` 正确

### 2. show — 预览 import 块
```bash
fe show server.go 3 10
```
- **结果**: ✅ 正确显示 import 块（8 个包）

### 3. show — 预览 loggingMiddleware（含 `\n` 字面量）
```bash
fe show server.go 73 82
```
- **结果**: ✅ `log.Printf("[%s] %s %s\n", ...)` 中 `\n` 正确显示为字面量 `\n`

### 4. CLI replace — 简单替换（无特殊字符）
```bash
fe replace server.go 70 70 '	fmt.Fprintf(w, `{"status":"ok","version":"2.0.0"}`)\n'
```
- **结果**: ✅ 版本号从 1.0.0 改为 2.0.0
- **说明**: 无 `\n` 字面量冲突，CLI replace 安全

### 5. CLI replace — 含 `\n` 的代码（⚠️ 已知问题）
```bash
fe replace server.go 75 75 '		log.Printf("[%s] %s %s\n", r.Method, r.URL.Path, r.RemoteAddr)\n'
```
- **结果**: ⚠️ `\n` 被展开为真换行，Go 代码损坏（1 行变 2 行）
- **说明**: 这是 CLI replace 的已知限制，Go 字符串中的 `\n` 会被 `parse_content()` 展开

### 6. restore — 回滚 `\n` 展开的损坏
```bash
fe restore server.go
```
- **结果**: ✅ 成功回滚到编辑前状态，行数恢复到 90 行

### 7. batch --stdin — 含 `\n` 的安全编辑
```bash
python3 -c "
import json, sys
spec = {
    'file': 'server.go',
    'edits': [{
        'action': 'replace-lines',
        'start': 75,
        'end': 75,
        'content': '\t\tlog.Printf(\"[%s] %s %s\\\\n\", r.Method, r.URL.Path, r.RemoteAddr)\n'
    }]
}
json.dump(spec, sys.stdout)
" | fe fast-batch --stdin
```
- **结果**: ✅ `\n` 保持为字面量 `\n`，Go 代码正确
- **关键**: JSON 中 `\\n` → 文件中 `\n`（字面量），不会被展开

### 8. batch --stdin — 多编辑操作（insert + replace + delete）
```bash
python3 -c "
import json, sys
spec = {
    'file': 'server.go',
    'edits': [
        {
            'action': 'insert-after',
            'line': 28,
            'content': '\nfunc writeError(...) {\n\t...\n\tlog.Printf(\"ERROR [%d] %s\\\\n\", code, msg)\n}\n'
        },
        {
            'action': 'replace-lines',
            'start': 16,
            'end': 16,
            'content': '\tRole  string \x60json:\"role\"\x60\n\tPhone string \x60json:\"phone\"\x60\n'
        },
        {
            'action': 'delete-lines',
            'start': 8,
            'end': 8
        }
    ]
}
json.dump(spec, sys.stdout)
" | fe fast-batch --stdin
```
- **结果**: ✅ 三个编辑全部正确应用（90→98 行）
  - insert: writeError 函数正确插入，`\n` 保持字面量
  - replace: Phone 字段添加，反引号 tag `` `json:"phone"` `` 完整
  - delete: `"strings"` import 行成功删除

### 9. verify — 对比编辑前后差异
```bash
fe verify server.go
```
- **结果**: ✅ 返回 3 个 change hunk
  - hunk 1: `"strings"` import 删除
  - hunk 2: Phone 字段添加（反引号 tag 完整）
  - hunk 3: writeError 函数插入（8 行新增，`\n` 字面量保留）
- `added: 9`, `removed: 1`

### 10. verify-syntax — go vet 检查
```bash
fe verify-syntax server.go
```
- **结果**: ✅ `"checker": "go vet"`, `"syntax_valid": true`
- **说明**: 删除了 `"strings"` import 且代码中未使用 strings 包，go vet 通过

### 11. backups — 列出备份链
```bash
fe backups server.go
```
- **结果**: ✅ 正确列出多个备份，包含 `_pre_restore` 前向备份
- **验证**: 备份链完整，每次编辑和 restore 都有记录

### 12. restore + verify-syntax — 回滚并检查
```bash
fe restore server.go
fe verify-syntax server.go
```
- **结果**: ✅ 回滚成功（98→90 行）
- **结果**: ⚠️ go vet 报告 `"strings" imported and not used` — 这是测试文件的预期行为（原始文件 strings 未使用），证明 verify-syntax 正确工作

## 发现的问题

### 🔴 CLI replace/insert 会展开 `\n`
- **严重程度**: HIGH
- **影响**: Go 代码中的字符串字面量 `\n`、`\t` 会被展开为真正的换行/Tab
- **解决方案**: 使用 `fast-batch --stdin` + `python -c "json.dump(...)"` 管道
- **已记录**: skill.md 中有详细说明

### 🟡 echo 管道的 JSON 转义风险
- **严重程度**: MEDIUM
- **影响**: `echo '{"content": "...\n..."}'` 中 `\n` 会被 echo 展开
- **解决方案**: 始终用 `python3 -c "json.dump(...)"` 生成 JSON

## Go 特殊字符处理总结

| 字符 | CLI replace | batch --stdin | 状态 |
|------|-------------|---------------|------|
| `\n` 字面量 | ❌ 被展开 | ✅ 安全 | 必须用 batch |
| `\t` 字面量 | ❌ 被展开 | ✅ 安全 | 必须用 batch |
| `` ` `` 反引号 | ✅ 安全 | ✅ 安全 | 无影响 |
| `%s`, `%v`, `%d` | ✅ 安全 | ✅ 安全 | 无影响 |
| `*` 指针 | ✅ 安全 | ✅ 安全 | shell 引号内安全 |
| `&` 取地址 | ✅ 安全 | ✅ 安全 | shell 引号内安全 |

## 结论

| 方法 | Go 安全性 | 推荐度 |
|------|-----------|--------|
| `fast-batch --stdin` + python json.dump | ✅ 完全安全 | ⭐⭐⭐ 强烈推荐 |
| CLI `replace` (无特殊字符) | ✅ 安全 | ⭐⭐ 简单场景可用 |
| CLI `replace` (含 `\n`/`\t`) | ❌ 损坏代码 | ❌ 禁止使用 |
| `echo` 管道 JSON | ⚠️ 有风险 | ⭐ 不推荐 |

**Go 编辑的黄金规则**: 永远使用 `fast-batch --stdin` + `python3 -c "json.dump()"` 管道。
