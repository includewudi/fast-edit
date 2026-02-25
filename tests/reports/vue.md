# Fast-Edit 多语言测试报告 — Vue (.vue SFC)

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | Vue 3 (SFC + `<script setup lang="ts">`) |
| 测试文件 | `/tmp/fe-lang-test/vue/UserList.vue` |
| 文件类型 | Vue 单文件组件（用户列表 + CRUD） |
| 原始行数 | 171 行 |
| 编辑后行数 | 175 行 |
| 测试项数 | 9 |
| 通过 | 9 ✅ |
| 失败 | 0 |

## 特殊字符清单

Vue SFC 横跨 3 种语言区域（template / script / style），特殊字符最为密集：

| 字符 | 区域 | 示例 | 说明 |
|------|------|------|------|
| `{{ mustache }}` | template | `{{ title }}`, `{{ filteredUsers.length }}` | 双花括号模板语法 |
| `v-model` | template | `v-model="searchQuery"` | 双向绑定指令 |
| `:bind` 缩写 | template | `:class="{ loading: isLoading }"` | v-bind 缩写 |
| `@event` 缩写 | template | `@click="fetchUsers"`, `@click.stop` | v-on 缩写 |
| `<slot>` | template | `<slot name="..." :users="..." />` | 具名插槽 + prop |
| `<transition-group>` | template | `<transition-group name="list">` | 内置组件 |
| 模板字面量 `` `${var}` `` | script | `` `${API_BASE}/users?${params}` `` | fetch URL 构造 |
| `import.meta.env` | script | `import.meta.env.VITE_API_URL` | Vite 环境变量 |
| `ref<T>()` | script | `ref<User[]>([])`, `ref<string \| null>(null)` | 泛型 ref |
| `defineProps<{}>()` | script | `defineProps<{ role?: string }>()` | 类型化 props |
| `defineEmits<{}>()` | script | `defineEmits<{ (e: 'select', user: User): void }>()` | 类型化 events |
| `withDefaults()` | script | `withDefaults(defineProps<{...}>(), {...})` | 默认值包装 |
| `computed()` | script | `computed(() => ...)` | 计算属性 |
| `err: unknown` | script | `catch (err: unknown)` | TypeScript 类型注解 |
| CSS 变量 `--var` | style | `--card-gap: 0.75rem` | 自定义属性 |
| `scoped` | style | `<style scoped>` | 作用域样式 |
| `transition` | style | `.list-enter-active`, `.list-leave-to` | Vue 过渡类名 |

## 测试用例

### 1. show — 预览 template 区域（mustache + v-directives）
```bash
fe show UserList.vue 1 12
```
- **结果**: ✅ 正确显示
  - `{{ title }} ({{ filteredUsers.length }})` — 双花括号完整
  - `:class="{ loading: isLoading }"` — 对象绑定完整
  - `v-model="searchQuery"` — 指令完整
  - `@input="debouncedSearch"` — 事件缩写完整

### 2. show — 预览 script 区域（模板字面量 + 泛型）
```bash
fe show UserList.vue 95 103
```
- **结果**: ✅ 正确显示
  - `` `${API_BASE}/users?${params}` `` — 模板字面量完整
  - `` `HTTP ${res.status}` `` — 错误模板完整
  - `PaginatedResponse<User>` — 泛型类型完整
  - `err: unknown` — TypeScript 类型注解完整

### 3. show — 预览 style 区域（CSS 属性）
```bash
fe show UserList.vue 137 145
```
- **结果**: ✅ CSS 属性完整显示

### 4. batch --stdin — 跨区域多编辑（4 个操作）
```bash
python3 -c "json.dump(spec, sys.stdout)" | fe fast-batch --stdin
```
编辑内容（覆盖 3 个 SFC 区域）：
1. **template**: 插入 `<slot name="header-actions" :users="filteredUsers" />`
2. **script**: 插入 `const hasUsers = computed(() => ...)`
3. **script**: 替换 `console.error` 为带模板字面量的详细版本
4. **style**: 插入 CSS 变量 `--card-gap: 0.75rem`

- **结果**: ✅ 4 个编辑全部正确应用
  - `<slot>` 标签: `:users` 绑定缩写完整
  - `computed()` 新属性: 箭头函数 + `.value` 访问完整
  - `` console.error(`[UserList] fetch failed (page=${page.value}, role=${props.role}):`, err) `` — 模板字面量 `${x.value}` 完整
  - CSS 变量 `--card-gap` 正确插入

### 5. verify — 对比差异
```bash
fe verify UserList.vue
```
- **结果**: ✅ 4 个 change hunk
  - hunk 1: template 区域 — slot 插入
  - hunk 2: script 区域 — computed 插入
  - hunk 3: script 区域 — console.error 替换
  - hunk 4: style 区域 — CSS 变量插入
- `added: 5`, `removed: 1`
- **关键**: 跨 template/script/style 三区域编辑一次完成

### 6. show — 验证 slot 插入
```bash
fe show UserList.vue 11 13
```
- **结果**: ✅ `<slot name="header-actions" :users="filteredUsers" />` 完整

### 7. show — 验证模板字面量
```bash
fe show UserList.vue 105 107
```
- **结果**: ✅ `` `[UserList] fetch failed (page=${page.value}, role=${props.role}):` `` 完整

### 8. show — 验证 CSS 变量
```bash
fe show UserList.vue 141 143
```
- **结果**: ✅ `--card-gap: 0.75rem` 正确位于 `.user-list` 块内

### 9. verify-syntax
```bash
fe verify-syntax UserList.vue
```
- **结果**: ✅ `"checker": "none"`, `"message": "No syntax checker for .vue files"`
- **说明**: `.vue` 文件无内置语法检查器，这是预期行为
- **建议**: Vue 文件应使用 `vue-tsc --noEmit` 或 `lsp_diagnostics`

## 发现的问题

### ✅ 无编辑问题

所有 Vue SFC 特殊语法在 `batch --stdin` 下完全安全。

### 🟡 verify-syntax 不支持 .vue 文件
- **严重程度**: LOW
- **现状**: 返回 `"checker": "none"`
- **建议**: 
  1. 可添加 `vue-tsc --noEmit` 检查（需安装 vue-tsc）
  2. 或建议用户使用 `lsp_diagnostics`（Volar LSP）
  3. 保持现状也可接受（.vue 需要完整项目环境才能检查）

### 🟢 跨区域编辑能力验证
- **发现**: fast-edit 对 SFC 文件的行号编辑无区域概念，但这反而是优势
  - template 行号、script 行号、style 行号统一编址
  - 一次 batch 可同时修改三个区域
  - 不存在"跨区域编辑不支持"的问题

## Vue SFC 特殊字符处理总结

| 字符 | 区域 | CLI replace | batch --stdin | 状态 |
|------|------|-------------|---------------|------|
| `{{ mustache }}` | template | ✅ 安全 | ✅ 安全 | 无影响 |
| `:bind`, `@event` | template | ✅ 安全 | ✅ 安全 | 无影响 |
| `<slot :prop>` | template | ⚠️ shell `>` | ✅ 安全 | 推荐 batch |
| 模板字面量 `` `${var}` `` | script | ❌ shell 展开 | ✅ 安全 | 必须用 batch |
| `ref<T>()` 泛型 | script | ⚠️ shell `>` | ✅ 安全 | 推荐 batch |
| `import.meta.env` | script | ✅ 安全 | ✅ 安全 | 无影响 |
| `err: unknown` | script | ✅ 安全 | ✅ 安全 | 无影响 |
| CSS `--var` | style | ✅ 安全 | ✅ 安全 | 无影响 |
| `scoped` | style | ✅ 安全 | ✅ 安全 | 无影响 |

## 结论

Vue SFC 是 fast-edit 测试中**特殊字符密度最高**的语言：
- **三区域统一编辑**: 一次 batch 跨 template/script/style，行号统一编址
- **模板字面量 `` `${}` ``**: 必须用 `batch --stdin`（同 TS/JSX）
- **Vue 指令/插槽**: `:bind`, `@event`, `<slot>` 全部安全
- **mustache `{{ }}`**: 双花括号在 JSON 中不是特殊字符，完全安全
- **verify-syntax**: 不支持 .vue，需用 `lsp_diagnostics` 或 `vue-tsc`
- **总体评价**: ⭐⭐⭐ 表现优秀，推荐 batch --stdin 编辑所有 Vue 代码
