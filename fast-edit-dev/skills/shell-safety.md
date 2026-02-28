---
name: shell-safety
description: 多语言 Shell 转义安全矩阵与最佳实践
---

# Shell 安全指南

> **入口摘要**
>
> 本文档解决 AI 在使用 CLI 工具编辑代码时的 Shell 转义问题。
>
> **核心决策树**：
> 1. 代码是否包含 `\n` `\t` `$` `` ` `` `<>` `|` `"""`？→ 必须用 `batch --stdin`
> 2. PHP 的 `$变量` 和 `\命名空间`？→ 必须用 `batch --stdin`
> 3. 其他情况？→ CLI `replace` 可用
>
> **安全管道模式**（必须用 heredoc，禁止 `python -c`）：
> ```bash
> python3 - <<'PY' | fe fast-batch --stdin
> import json, sys
> spec = {...}
> json.dump(spec, sys.stdout)
> PY
> ```
>
> 编辑前务必 `fe show FILE START END` 确认行号。

## 多语言编辑最佳实践

> **核心原则**: 所有包含 shell 敏感字符的代码，一律使用 `fast-batch --stdin` + `python3 - <<'PY'` heredoc 管道。
>
> 编辑前**必须** `show` 确认目标行号。Java/JSX 等代码行号容易偏差。

### 特殊字符安全矩阵

| 字符 | 影响语言 | CLI replace | batch --stdin | 处理方式 |
|------|----------|-------------|---------------|----------|
| `\n` `\t` 字面量 | Go, Java, TS, JSX | ❌ 展开为真换行/Tab | ✅ JSON `\\n` 安全 | 必须 batch |
| `$variable` | PHP, Bash | ❌ shell 展开 | ✅ python `\$` 安全 | 必须 batch |
| 反引号 `` ` `` | Go (struct tag), TS/JSX/Vue (模板字面量) | ❌ shell 执行 | ✅ python `\`` 安全 | 必须 batch |
| 模板字面量 `` `${var}` `` | TS, JSX, Vue | ❌ `$` + `` ` `` 双重危险 | ✅ 安全 | 必须 batch |
| `<tag>` / `>` | JSX, Vue, Java 泛型 | ⚠️ shell 重定向 | ✅ 安全 | 推荐 batch |
| `\` 命名空间 | PHP | ⚠️ 需双转义 | ✅ python `\\\\` | 推荐 batch |
| `{{ mustache }}` | Vue | ✅ 安全 | ✅ 安全 | 无影响 |
| `@decorator` | Java, TS, Python | ✅ 安全 | ✅ 安全 | 无影响 |
| f-string `{var}` | Python | ✅ 安全 | ✅ 安全 | 无影响 |
| `**kwargs` | Python | ✅ 安全 | ✅ 安全 | 无影响 |
| `?.` 可选链 | TS, JSX, Vue | ✅ 安全 | ✅ 安全 | 无影响 |
| `=>` 箭头 | JS/TS/JSX, PHP | ✅ 安全 | ✅ 安全 | 无影响 |
| Emoji / Unicode | 所有语言 | ✅ UTF-8 保持 | ✅ UTF-8 保持 | 无影响 |

### verify-syntax 支持矩阵

| 语言 | 检查器 | 可用性 | 注意事项 |
|------|--------|--------|----------|
| Go | `go vet` | ✅ 可用 | 可能报依赖错误（如删了 import 但代码仍引用），属于预期行为 |
| Python | `py_compile` | ✅ 可用 | 仅语法检查，不检查类型 |
| Rust | `rustc` | ✅ 可用 | — |
| C/C++ | `gcc`/`g++` | ✅ 可用 | — |
| TypeScript | `tsc` | ⚠️ 有限 | 需要 tsconfig.json + node_modules，单文件检查会报缺少模块 |
| JavaScript (.js) | `node --check` | ✅ 可用 | 仅 .js/.mjs，不支持 .jsx |
| JavaScript (.jsx) | — | ❌ 不可用 | `node --check` 不认识 .jsx 扩展名 |
| Java | `javac` | ⚠️ 有限 | 需要 JDK + classpath（Spring 等依赖） |
| PHP | — | ❌ 不可用 | 建议添加 `php -l`（PHP 内置语法检查） |
| Vue (.vue) | — | ❌ 不可用 | 建议用 `lsp_diagnostics`（Volar LSP）或 `vue-tsc` |

> **verify-syntax 定位**: 编辑后的**参考信号**，不是阻断信号。
> AI 应判断报告的错误是编辑引入的还是环境/依赖导致的预期错误。
> 对于 TS/Java/PHP/Vue 等需要完整项目环境的语言，优先使用 `lsp_diagnostics`。

### Go

**危险字符**: `\n`, `\t`, 反引号 `` ` `` (struct tag)

```bash
# ✅ 安全：heredoc 形式，反引号不会被 shell 执行
python3 - <<'PY' | fe fast-batch --stdin
import json, sys
spec = {
    'file': '/path/to/file.go',
    'edits': [{
        'action': 'replace-lines',
        'start': 10,
        'end': 12,
        'content': 'func main() {\n\tfmt.Printf("hello %s\\n", name)\n}\n'
    }]
}
json.dump(spec, sys.stdout)
PY

# ❌ 禁止：python -c "...`...`..." — shell 会先执行反引号
# python3 -c "json.dump({'content': '`date`'}, sys.stdout)" | fe fast-batch --stdin
# → shell 执行 `date`，注入当前日期到 JSON，导致内容错误或语法错误

# ❌ 同样禁止：Go struct tag 中的反引号也会被执行
# python3 -c "json.dump({'content': 'type S struct { F string `json:\"f\"`}'}, sys.stdout)"
# → `json:"f"` 被 shell 当作命令执行
```

| 场景 | 推荐 |
|------|------|
| 含 `\n`, `\t`, 反引号 | `batch --stdin` + json.dump |
| 简单替换（无特殊字符） | CLI `replace` 可用 |
| 多处编辑 | `batch --stdin`（始终推荐） |

### Python

**安全性最好的语言之一。** f-string `{var}`、`@decorator`、`**kwargs`、类型注解 `[]` 在 CLI 和 batch 中均安全。

| 场景 | 推荐 |
|------|------|
| 含 `\n` 字面量或三引号 `"""` | `batch --stdin` |
| 其他场景 | CLI `replace` 可用 |

### PHP

**核心挑战**: `$variable` 前缀 — shell 会展开为环境变量。

```bash
# ✅ heredoc 形式，\$ 转义 $，\\\\  四重转义命名空间 \
python3 - <<'PY' | fe fast-batch --stdin
import json, sys
spec = {
    'file': 'Controller.php',
    'edits': [{
        'action': 'replace-lines',
        'start': 10, 'end': 10,
        'content': '        $user = User::find($id);\n'
    }]
}
json.dump(spec, sys.stdout)
PY
```

| 场景 | 推荐 |
|------|------|
| 含 `$` 变量（几乎所有 PHP 代码） | `batch --stdin`（必须） |
| 含 `\` 命名空间 | python 中用 `\\\\` 四重转义 |
| 闭包 `function () use ($var)` | `batch --stdin`（必须） |

### Java

**与 Go 相同的 `\n` 展开问题**，额外注意泛型 `<>` 在 shell 中的重定向风险。

| 场景 | 推荐 |
|------|------|
| 含 `\n` 字面量 | `batch --stdin` |
| 含泛型 `ResponseEntity<Map<String, Object>>` | `batch --stdin`（shell `>` 重定向风险） |
| 注解密度高、行号容易偏差 | **编辑前必须 `show` 确认行号** |
| verify-syntax | 需 JDK 环境，实际项目用 `lsp_diagnostics` |

### TypeScript

**模板字面量 `` `${var}` `` 是最大风险** — shell 同时展开 `$` 和执行反引号。

| 场景 | 推荐 |
|------|------|
| 含模板字面量 `` `${var}` `` | `batch --stdin`（必须） |
| 含泛型 `<T>` | `batch --stdin`（shell `>` 风险） |
| 含联合类型 `A \| B` | `batch --stdin`（shell pipe 风险） |
| `@Decorator`、`?.`、`...spread` | CLI 可用 |
| verify-syntax | tsc 需完整项目环境，推荐 `lsp_diagnostics` |

### JavaScript (React JSX)

**同 TypeScript 的模板字面量问题**，额外注意 JSX 标签 `<>` 的 shell 重定向。

| 场景 | 推荐 |
|------|------|
| 含模板字面量 / JSX 标签 | `batch --stdin`（必须） |
| JSX 缩进层次深 | **编辑前 `show` 确认行号** |
| verify-syntax | `node --check` 不支持 .jsx，用 `lsp_diagnostics` |
| Emoji / Unicode / HTML 实体 | CLI 和 batch 均安全 |

### Vue (.vue SFC)

**特殊字符密度最高**：横跨 template / script / style 三个区域。

| 场景 | 推荐 |
|------|------|
| script 区含模板字面量 / 泛型 | `batch --stdin`（必须） |
| template 区 `<slot>` / `<Component>` | `batch --stdin`（shell `>` 风险） |
| `{{ mustache }}`、`:bind`、`@event` | CLI 和 batch 均安全 |
| 跨区域多编辑 | `batch --stdin`（一次完成 template + script + style） |
| verify-syntax | 不支持 .vue，用 `lsp_diagnostics` |

### 黄金规则

```
任何语言，只要代码包含以下任一字符 → 必须 batch --stdin:
  \n  \t  $  `  <>  |  \(PHP命名空间)  """(三引号)

安全管道模式（必须用 heredoc，禁止 python -c）:
  python3 - <<'PY' | fe fast-batch --stdin
  import json, sys
  spec = {...}
  json.dump(spec, sys.stdout)
  PY

  # ❌ 禁止：python3 -c "...`...`..." — 反引号会被 shell 执行

编辑前:
  fe show FILE START END  # 确认行号再编辑

编辑后:
  fe verify FILE           # 检查 diff
  lsp_diagnostics(file)      # 类型检查（首选）
  fe verify-syntax FILE     # 语法检查（备选，参考信号）
```
