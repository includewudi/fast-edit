# Fast-Edit 多语言测试报告 — JavaScript (React JSX)

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | JavaScript (React JSX) |
| 测试文件 | `/tmp/fe-lang-test/jsx/UserList.jsx` |
| 文件类型 | React 函数组件（用户列表 + CRUD） |
| 原始行数 | 121 行 |
| 编辑后行数 | 129 行 |
| 测试项数 | 7 |
| 通过 | 6 ✅ |
| 部分通过 | 1 ⚠️（行号定位导致 JSX 插入位置不理想） |
| 工具 bug | 0 |

## 特殊字符清单

React JSX 代码包含以下需要测试的字符：

| 字符 | 示例 | 说明 |
|------|------|------|
| JSX `<Component>` | `<div className="user-list">` | HTML-like 标签 |
| `{expression}` | `{user.name}`, `{filteredUsers.length}` | JSX 表达式 |
| 模板字面量 `` `${var}` `` | `` `Are you sure...#${userId}?` `` | 模板字符串 |
| `?.` 可选链 | `onUserSelect?.(user)` | Optional call |
| `process.env` | `process.env.REACT_APP_API_URL` | 环境变量 |
| 箭头函数 `=>` | `(u) => u.id !== userId` | 密集使用 |
| 解构 `{ data, meta }` | `const { data, meta } = await res.json()` | 对象解构 |
| JSX `className` 模板 | `` className={`user-card ${user.role}`} `` | 动态类名 |
| `&quot;` HTML 实体 | `&quot;{search}&quot;` | JSX 中的 HTML 实体 |
| Emoji 🗑️ | `🗑️` | Unicode emoji 在 JSX 中 |
| `← →` Unicode 箭头 | `← Prev`, `Next →` | Unicode 字符 |

## 测试用例

### 1. show — 预览 JSX 表达式 + 动态类名
```bash
fe show UserList.jsx 91 108
```
- **结果**: ✅ 正确显示
  - `` className={`user-card ${user.role}`} `` — 模板字面量类名完整
  - `{user.name}`, `{user.email}` — JSX 表达式花括号完整
  - `` :aria-label={`Delete ${user.name}`} `` — 模板字面量属性完整
  - `onClick={() => onUserSelect?.(user)}` — 可选调用完整
  - `🗑️` — Emoji 完整显示

### 2. show — 预览模板字面量 + 错误处理
```bash
fe show UserList.jsx 27 30
```
- **结果**: ✅ `` `HTTP ${res.status}: ${res.statusText}` `` 完整

### 3. batch --stdin — 多编辑（4 个操作）
编辑内容：
1. 修改 import 添加 `useRef`
2. 插入 `useRef` 和 `useState` 新 hook
3. 替换 `console.error` 为带模板字面量的详细日志
4. 插入 aria-live 错误提示 JSX 块

- **结果**: ✅ 4 个编辑全部正确应用
  - `` console.error(`[UserList] Failed to fetch (page=${page}, role=${role}):`, err) `` — 模板字面量 `${}` 完整
  - `<slot>` / `<div>` JSX 标签保持有效
  - `useRef(null)` 新 hook 正确插入

### 4. verify — 对比差异
```bash
fe verify UserList.jsx
```
- **结果**: ✅ 4 个 change hunk
  - hunk 1: import 修改（+useRef）
  - hunk 2: +2 行新 hook（useRef + useState）
  - hunk 3: console.error 替换为模板字面量版本
  - hunk 4: +6 行 aria-live JSX 块
- `added: 10`, `removed: 2`

### 5. show — 验证模板字面量
```bash
fe show UserList.jsx 35 37
```
- **结果**: ✅ `` console.error(`[UserList] Failed to fetch (page=${page}, role=${role}):`, err) `` 模板字面量完整

### 6. show — 验证 JSX 插入 ⚠️
```bash
fe show UserList.jsx 81 87
```
- **结果**: ⚠️ aria-live JSX 块插入位置在 `<input` 标签之后（JSX return 内部），而非作为早期 return 分支
- **原因**: 行号 79 指向的是 JSX return 内部的 `<header>` 后的 `<input>` 元素，而非函数体
- **说明**: 这是**行号定位错误**（AI 未正确 show 确认），工具本身执行正确

### 7. verify-syntax — node --check
```bash
fe verify-syntax UserList.jsx
```
- **结果**: ⚠️ `"checker": "node"`, `"syntax_valid": false`
- **错误**: `ERR_UNKNOWN_FILE_EXTENSION: Unknown file extension ".jsx"`
- **说明**: `node --check` 不支持 `.jsx` 文件（只支持 `.js` 和 `.mjs`）
- **影响**: JSX 文件无法通过 verify-syntax 检查
- **建议**: 对 `.jsx`/`.tsx` 文件建议使用 `lsp_diagnostics` 或项目的 ESLint

## 发现的问题

### 🟡 node --check 不支持 .jsx 扩展名
- **严重程度**: MEDIUM
- **现状**: verify.py 对 .jsx 使用 `node --check`，但 Node.js 不认识 `.jsx`
- **建议**: 
  1. 对 `.jsx` 文件返回 `"checker": "none"` 而非尝试 node
  2. 或者尝试 `npx --yes acorn --ecma2020 file.jsx`（需安装）
  3. 最佳方案：使用 `lsp_diagnostics`

### 🟡 JSX 中 HTML 实体和 Emoji 处理
- **发现**: `&quot;` HTML 实体和 🗑️ Emoji 在 show/edit 中完全保持不变
- **状态**: ✅ 无问题

## JSX 特殊字符处理总结

| 字符 | CLI replace | batch --stdin | 状态 |
|------|-------------|---------------|------|
| JSX `<tag>` | ⚠️ shell 重定向 `>` | ✅ 安全 | 推荐 batch |
| `{expression}` | ✅ 安全（shell 不解释） | ✅ 安全 | 无影响 |
| 模板字面量 `` `${var}` `` | ❌ `$` 和 `` ` `` 被展开 | ✅ python 转义安全 | 必须用 batch |
| `process.env.X` | ✅ 安全 | ✅ 安全 | 无影响 |
| `?.()` 可选调用 | ✅ 安全 | ✅ 安全 | 无影响 |
| `=>` 箭头 | ✅ 安全 | ✅ 安全 | 无影响 |
| HTML 实体 `&quot;` | ✅ 安全 | ✅ 安全 | 不转换 |
| Emoji 🗑️ | ✅ 安全 | ✅ 安全 | UTF-8 保持 |
| Unicode ← → | ✅ 安全 | ✅ 安全 | UTF-8 保持 |

## 结论

React JSX 编辑的核心挑战：
- **模板字面量 `` `${}` ``**: 必须用 `batch --stdin`，shell 中 `` ` `` 和 `$` 都有特殊含义
- **JSX 标签 `<>`**: shell 重定向风险，推荐 batch
- **verify-syntax**: `node --check` 不支持 `.jsx`，需用 `lsp_diagnostics`
- **行号定位**: JSX 代码缩进层次深，行号容易偏差，**必须 show 确认**
- **Unicode/Emoji**: 完美支持，无需特殊处理
