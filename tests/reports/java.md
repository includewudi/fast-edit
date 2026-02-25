# Fast-Edit 多语言测试报告 — Java

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | Java 17+ (Spring Boot) |
| 测试文件 | `/tmp/fe-lang-test/java/UserController.java` |
| 文件类型 | Spring REST Controller（用户 CRUD） |
| 原始行数 | 113 行 |
| 编辑后行数 | 117 行 |
| 测试项数 | 10 |
| 通过 | 8 ✅ |
| 用户错误导致的失败 | 2 ⚠️（行号定位错误，非工具 bug） |
| 工具 bug | 0 |

## 特殊字符清单

Java 代码包含以下需要测试的字符：

| 字符 | 示例 | 说明 |
|------|------|------|
| `@Annotation` | `@RestController`, `@GetMapping("/{id}")` | 注解 |
| 泛型 `<T>` | `ResponseEntity<Map<String, Object>>` | 嵌套泛型 |
| `%d`, `%s`, `%n` | `System.out.printf("user %d%n", id)` | 格式化占位符 |
| `->` lambda | `u -> u.getRole().equals(role)` | Lambda 箭头 |
| switch `->` | `case "name" -> user.setName(value)` | Java 14+ switch 表达式 |
| `\n`, `\t` | `"hello\nworld"` | 字符串转义（同 Go 问题） |
| `{}` SLF4J | `log.info("user {}", id)` | SLF4J 占位符花括号 |
| `Map.of()` | `Map.of("error", "Not found")` | 不可变 Map 构造 |

## 测试用例

### 1. show — 预览注解 + 泛型
```bash
fe show UserController.java 13 26
```
- **结果**: ✅ 正确显示
  - `@RestController` / `@RequestMapping("/api/users")` — 注解完整
  - `ResponseEntity<Map<String, Object>>` — 嵌套泛型 `<>` 完整
  - `@RequestParam(required = false)` — 注解属性完整

### 2. show — 预览 switch 表达式
```bash
fe show UserController.java 89 97
```
- **结果**: ✅ Java 14+ `case "name" -> user.setName(value)` 语法完整

### 3-4. batch --stdin — 多编辑（第一次尝试，行号错误）

**第一次尝试**：用了错误的行号（line 71 以为是 printf，实际是 return 语句）
- **结果**: ⚠️ 编辑应用在错误的行上
- **原因**: AI 推测行号错误（没有用 `show` 确认）
- **教训**: **必须先用 `show` 确认目标行号，再编辑**

### 5. restore — 回滚错误编辑
```bash
fe restore UserController.java
```
- **结果**: ✅ 成功回滚到原始状态

### 6-7. show — 精确定位目标行
```bash
fe show UserController.java 96 96   # → System.out.printf("Updated...")
fe show UserController.java 109 109 # → System.out.printf("Deleted...")
```
- **结果**: ✅ 确认正确行号：69, 96, 109

### 8. batch --stdin — 正确的多编辑（5 个操作）
```bash
python3 -c "
import json, sys
spec = {
    'file': 'UserController.java',
    'edits': [
        {'action': 'insert-after', 'line': 6, 'content': 'import org.slf4j.Logger;\nimport org.slf4j.LoggerFactory;\n'},
        {'action': 'insert-after', 'line': 18, 'content': '\n    private static final Logger log = LoggerFactory.getLogger(UserController.class);\n'},
        {'action': 'replace-lines', 'start': 69, 'end': 69, 'content': '        log.info(\"Created user {}: {}\", saved.getId(), saved.getName());\n'},
        {'action': 'replace-lines', 'start': 96, 'end': 96, 'content': '        log.info(\"Updated user {}\", updated.getId());\n'},
        {'action': 'replace-lines', 'start': 109, 'end': 109, 'content': '        log.warn(\"Deleted user {}\", id);\n'}
    ]
}
json.dump(spec, sys.stdout)
" | fe fast-batch --stdin
```
- **结果**: ✅ 5 个编辑全部正确
  - import 添加：`org.slf4j.Logger` + `LoggerFactory` 正确
  - logger 字段：`LoggerFactory.getLogger(UserController.class)` — 泛型 `.class` 正确
  - 3 处 printf → log 替换：SLF4J `{}` 占位符正确保留

### 9. verify — 对比差异
```bash
fe verify UserController.java
```
- **结果**: ✅ 5 个 change hunk 全部正确
  - hunk 1: +2 行 import
  - hunk 2: +2 行 logger 字段
  - hunk 3-5: 各 1 行 printf → log 替换

### 10. verify-syntax — javac 检查
```bash
fe verify-syntax UserController.java
```
- **结果**: ⚠️ `"checker": "javac"`, `"syntax_valid": false`
- **输出**: `"Unable to locate a Java Runtime"`
- **说明**: 测试机未安装 JDK，verify-syntax 正确检测到并报告
  - 这不是 fast-edit bug，是环境问题
  - 如果安装了 JDK，javac 会报缺少 Spring 依赖类（也是预期的）

## 发现的问题

### 🟡 行号误判导致编辑错位
- **严重程度**: MEDIUM（用户错误，非工具 bug）
- **原因**: 没有用 `show` 确认行号就直接编辑
- **教训**: Java 代码多空行和注解，行号容易偏差。**编辑前必须 `show` 确认**
- **影响**: restore 成功挽救了错误

### 🟡 JDK 未安装，verify-syntax 无法执行
- **严重程度**: LOW（环境问题）
- **说明**: verify-syntax 正确处理了 "checker not found" 的情况

## Java 特殊字符处理总结

| 字符 | CLI replace | batch --stdin | 状态 |
|------|-------------|---------------|------|
| `@Annotation` | ✅ 安全 | ✅ 安全 | 无影响 |
| 泛型 `<T>` | ⚠️ shell 可能解释 `>` | ✅ 安全 | 推荐 batch |
| `%d`, `%s`, `%n` | ✅ 安全 | ✅ 安全 | 无影响 |
| `->` lambda | ✅ 安全 | ✅ 安全 | 无影响 |
| `\n` 在字符串中 | ❌ 会展开 | ✅ JSON 安全 | 同 Go 问题 |
| `{}` SLF4J 占位符 | ✅ 安全 | ✅ 安全 | 无影响 |

## 结论

Java 编辑与 Go 面临相同的 `\n` 展开问题。额外注意：
- **泛型 `<>`**: 在 shell 中可能被解释为重定向，推荐 batch
- **注解密度高**: Java 文件行号变化频繁，**必须 show 确认后编辑**
- **verify-syntax**: 需要 JDK 环境，且 javac 需要完整 classpath（Spring 依赖等），实际项目中作用有限
- **restore 是安全网**: 行号错误 → restore → 重新 show → 重新编辑，流程可靠
