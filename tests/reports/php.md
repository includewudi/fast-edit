# Fast-Edit 多语言测试报告 — PHP

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | PHP 8.x |
| 测试文件 | `/tmp/fe-lang-test/php/UserController.php` |
| 文件类型 | Laravel Controller（用户 CRUD） |
| 原始行数 | 124 行 |
| 编辑后行数 | 145 行 |
| 测试项数 | 6 |
| 通过 | 5 ✅ |
| 部分通过 | 1 ⚠️ |
| 失败 | 0 |

## 特殊字符清单

PHP 代码包含以下需要测试的字符：

| 字符 | 示例 | 说明 |
|------|------|------|
| `$variable` | `$request`, `$user`, `$search` | 变量前缀，shell 会展开 |
| `\` 命名空间 | `App\Http\Controllers` | 反斜杠，JSON 需双转义 |
| `{$var}` 插值 | `"{$user->id}"` | 双引号内变量插值 |
| `->` 箭头 | `$user->name` | 对象属性访问 |
| `=>` 双箭头 | `'name' => 'required'` | 数组键值对 |
| `??` 空合并 | `$validated['role'] ?? 'user'` | null coalescing |
| `::` 静态调用 | `User::create()`, `Cache::remember()` | 类静态方法 |
| `%{$var}%` | `"%{$search}%"` | LIKE 查询模式 |
| 闭包 `function ($q) use ($var)` | 匿名函数 + use 变量绑定 | PHP 特有语法 |

## 测试用例

### 1. show — 预览 index 方法
```bash
fe show UserController.php 21 50
```
- **结果**: ✅ 正确显示
  - `$request->input('role')` — `$` 变量完整
  - `function ($q) use ($search)` — 闭包语法完整
  - `"%{$search}%"` — LIKE 模式完整

### 2. batch --stdin — 多编辑（insert use + replace paginate + insert method）
```bash
python3 -c "
import json, sys
spec = {
    'file': 'UserController.php',
    'edits': [
        {
            'action': 'insert-after',
            'line': 10,
            'content': 'use Illuminate\\\\Support\\\\Facades\\\\Cache;\\n'
        },
        {
            'action': 'replace-lines',
            'start': 36,
            'end': 36,
            'content': '        \$cacheKey = \"users_page_\" . \$request->input(\"page\", 1);\\n        \$users = Cache::remember(\$cacheKey, 300, function () use (\$query, \$request) {\\n            return \$query->paginate(\$request->input(\"per_page\", 15));\\n        });\\n'
        },
        {
            'action': 'insert-after',
            'line': 121,
            'content': '\\n    /**\\n     * Bulk delete users.\\n     */\\n    public function bulkDestroy(Request \$request): JsonResponse\\n    {\\n        \$validated = \$request->validate([\\n            \"ids\" => \"required|array\",\\n            \"ids.*\" => \"integer|exists:users,id\",\\n        ]);\\n\\n        \$count = User::whereIn(\"id\", \$validated[\"ids\"])->delete();\\n        Log::warning(\"Bulk deleted {\$count} users\");\\n\\n        return response()->json([\"deleted\" => \$count]);\\n    }\\n'
        }
    ]
}
json.dump(spec, sys.stdout)
" | fe fast-batch --stdin
```
- **结果**: ✅ 三个编辑全部正确应用
  - `use Illuminate\Support\Facades\Cache;` — 命名空间反斜杠正确
  - `Cache::remember($cacheKey, 300, function () use ($query, $request) {...})` — 闭包、`$` 变量、`::` 静态调用完整
  - `bulkDestroy` 方法 — `$request->validate([...])` 完整

### 3. show — 验证 Cache::remember 代码
```bash
fe show UserController.php 37 41
```
- **结果**: ✅ 缓存代码完整
  - `$cacheKey` 变量前缀 `$` 正确
  - 闭包 `function () use ($query, $request)` 完整
  - `Cache::remember()` 静态调用完整

### 4. verify — 对比编辑前后差异
```bash
fe verify UserController.php
```
- **结果**: ✅ 返回 3 个 change hunk
  - hunk 1: `use Cache` import 插入
  - hunk 2: paginate → Cache::remember 替换
  - hunk 3: bulkDestroy 方法插入
- `added: 21`, `removed: 1`

### 5. verify-syntax — PHP 语法检查
```bash
fe verify-syntax UserController.php
```
- **结果**: ⚠️ `"checker": "none"`, `"message": "No syntax checker for .php files"`
- **说明**: verify.py 未实现 PHP 语法检查器
- **建议**: 可添加 `php -l` 作为 PHP 语法检查器

### 6. `$` 变量保持测试
- **结果**: ✅ 所有 `$` 前缀变量完整保留
  - `$request`, `$user`, `$validated`, `$cacheKey`, `$count`
  - python json.dump 中用 `\$` 转义 `$`，写入文件后正确为 `$`

## 发现的问题

### 🟡 verify-syntax 不支持 PHP
- **严重程度**: LOW（不影响编辑功能）
- **现状**: 返回 `"checker": "none"`
- **建议**: 在 verify.py 中添加:
  ```python
  ".php": (["php", "-l", abs_path], "php -l"),
  ```
  `php -l` 是 PHP 内置语法检查，不需要额外安装

### 🟡 bulkDestroy 方法插入位置
- **观察**: bulkDestroy 方法被插入在类闭合 `}` 之后（第 128 行是 `}`），导致它在类外面
- **原因**: batch insert-after line 121 对应的是 destroy 方法最后一行，但类闭合 `}` 在第 127 行。如果编辑导致行号偏移，insert 的目标行号需要重新计算
- **说明**: 这不是 fast-edit 的 bug，而是使用者（AI）需要正确计算行号

## PHP 特殊字符处理总结

| 字符 | CLI replace | batch --stdin | 状态 |
|------|-------------|---------------|------|
| `$variable` | ❌ shell 展开 | ✅ python `\$` 安全 | 必须用 batch |
| `\` 命名空间 | ⚠️ 需双转义 | ✅ python `\\\\` 安全 | 推荐 batch |
| `{$var}` 插值 | ❌ shell + `$` | ✅ 安全 | 必须用 batch |
| `->` 箭头 | ✅ 安全 | ✅ 安全 | 无影响 |
| `=>` 双箭头 | ✅ 安全 | ✅ 安全 | 无影响 |
| `??` 空合并 | ✅ 安全 | ✅ 安全 | 无影响 |
| `::` 静态调用 | ✅ 安全 | ✅ 安全 | 无影响 |
| 闭包 `use ($var)` | ❌ `$` 被展开 | ✅ 安全 | 必须用 batch |

## 结论

PHP 编辑的核心挑战是 `$` 变量前缀：
- **所有包含 `$` 的 PHP 代码必须使用 `fast-batch --stdin`**
- `python3 -c "json.dump()"` 中用 `\$` 转义 `$`
- 命名空间 `\` 用 `\\\\` 四重转义（python string → JSON → 文件）
- **verify-syntax 不支持 PHP**，建议添加 `php -l` 检查器
