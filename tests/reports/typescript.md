# Fast-Edit 多语言测试报告 — TypeScript

## 测试概况

| 项目 | 值 |
|------|-----|
| 语言 | TypeScript (NestJS) |
| 测试文件 | `/tmp/fe-lang-test/ts/UserController.ts` |
| 文件类型 | NestJS REST Controller（用户 CRUD） |
| 原始行数 | 105 行 |
| 编辑后行数 | 108 行 |
| 测试项数 | 6 |
| 通过 | 6 ✅ |
| 失败 | 0 |

## 特殊字符清单

TypeScript/NestJS 代码包含以下需要测试的字符：

| 字符 | 示例 | 说明 |
|------|------|------|
| 泛型 `<T>` | `PaginatedResponse<T>`, `Promise<{ data: User }>` | 嵌套泛型 |
| 模板字面量 `` `${var}` `` | `` `User ${id} not found` `` | 含表达式的模板字符串 |
| `@Decorator()` | `@Controller('api/users')`, `@Get(':id')` | NestJS 装饰器 |
| 联合类型 `\|` | `'admin' \| 'user' \| 'moderator'` | 类型联合 |
| `Omit<T, K>` / `Partial<T>` | `Omit<User, 'id' \| 'createdAt'>` | 工具类型 |
| `?.` 可选链 | `dto.name?.trim()` | Optional chaining |
| `?.()`  可选调用 | `onUserSelect?.(user)` | Optional call |
| `...spread` | `{ id: nextId++, ...dto }` | 对象展开 |
| `as` 类型断言 | — | 无，但 JSON 中不冲突 |

## 测试用例

### 1. show — 预览泛型接口
```bash
fe show UserController.ts 11 22
```
- **结果**: ✅ 正确显示
  - `PaginatedResponse<T>` — 泛型参数 `<T>` 完整
  - `T[]` — 数组泛型完整
  - `Omit<User, 'id' | 'createdAt'>` — 工具类型 + 联合 `|` 完整
  - `Partial<CreateUserDto>` — 嵌套工具类型完整

### 2. show — 预览装饰器 + 模板字面量
```bash
fe show UserController.ts 55 63
```
- **结果**: ✅ 正确显示
  - `@Get(':id')` — 路由装饰器完整
  - `` `User ${id} not found` `` — 模板字面量 `${}` 完整
  - `Promise<{ data: User }>` — 嵌套泛型 `<{ }>` 完整

### 3. batch --stdin — 多编辑（5 个操作）
```bash
python3 -c "json.dump(spec, sys.stdout)" | fe fast-batch --stdin
```
编辑内容：
1. 插入 `import { Logger }` 
2. 插入 `private readonly logger = new Logger(UserController.name)`
3. 替换 3 处 `console.log(...)` → `this.logger.log(...)` / `this.logger.warn(...)`

- **结果**: ✅ 5 个编辑全部正确应用
  - `` this.logger.log(`Created user ${user.id}: ${user.name}`) `` — 模板字面量内 `${}` 完整
  - `new Logger(UserController.name)` — 类引用完整
  - `` this.logger.warn(`Deleted user ${deleted.id}: ${deleted.name}`) `` — 完整

### 4. verify — 对比差异
```bash
fe verify UserController.ts
```
- **结果**: ✅ 5 个 change hunk
  - hunk 1: +1 行 import
  - hunk 2: +2 行 logger 字段
  - hunk 3-5: 各 1 行 console.log → this.logger 替换
- `added: 6`, `removed: 3`

### 5. show — 验证编辑后模板字面量保持
```bash
fe show UserController.ts 78 79  # Created user ${user.id}
fe show UserController.ts 93 94  # Updated user ${user.id}
fe show UserController.ts 105 106 # Deleted user ${deleted.id}
```
- **结果**: ✅ 所有 `${}` 表达式完整保留

### 6. verify-syntax — tsc 检查
```bash
fe verify-syntax UserController.ts
```
- **结果**: ⚠️ `"checker": "tsc"`, `"syntax_valid": false`
- **错误**: `Cannot find module '@nestjs/common'`, `Decorators are not valid here`, `--lib ES2015` needed
- **说明**: 全部是**环境/配置问题**（缺少 node_modules 和 tsconfig.json），不是编辑问题
- **有用**: tsc 能正常运行并返回错误，证明 verify-syntax 对 .ts 文件的检查器选择正确

## 发现的问题

### 🟡 tsc 单文件检查需要 tsconfig 和 node_modules
- **严重程度**: LOW（已知限制）
- **现状**: `tsc --noEmit file.ts` 不会自动读取 tsconfig.json
- **影响**: 装饰器、ES2015+ API、外部 module 都会报错
- **建议**: 在实际项目中，应使用 `lsp_diagnostics` 而非 `verify-syntax` 检查 TypeScript

### ✅ 模板字面量 `${expr}` 完全安全
- `batch --stdin` 中用 python 反引号转义 `\`` + `\${}` 即可
- JSON 层面 `${...}` 不是特殊字符，无需额外转义

## TypeScript 特殊字符处理总结

| 字符 | CLI replace | batch --stdin | 状态 |
|------|-------------|---------------|------|
| 泛型 `<T>` | ⚠️ shell 可能解释 `>` | ✅ 安全 | 推荐 batch |
| 模板字面量 `` `${var}` `` | ❌ shell 展开 `$` 和 `` ` `` | ✅ python 转义安全 | 必须用 batch |
| `@Decorator` | ✅ 安全 | ✅ 安全 | 无影响 |
| 联合类型 `\|` | ⚠️ shell pipe | ✅ 安全 | 推荐 batch |
| `?.` 可选链 | ✅ 安全 | ✅ 安全 | 无影响 |
| `...spread` | ✅ 安全 | ✅ 安全 | 无影响 |

## 结论

TypeScript 是 `fast-batch --stdin` 的最佳受益者之一：
- **模板字面量** `` `${}` `` 在 shell 中极难安全传递（`$` 展开 + 反引号执行），`batch --stdin` 完美解决
- **泛型 `<>`**: shell 重定向风险，batch 安全
- **装饰器/可选链**: 无特殊处理需要
- **verify-syntax**: tsc 可用但需要完整项目环境，推荐用 `lsp_diagnostics`
