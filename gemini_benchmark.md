# Gemini CLI 文件处理性能测评：原生 vs Fast-Edit

本文档记录了在 Gemini CLI 环境下，处理大规模文件（1500行+）时，原生工具与 `fast-edit` 扩展工具的对比表现。

## 测评维度

| 维度 | 原生 `write_file` / `replace` | `fast-edit` 扩展工具 | 测评结果 |
| :--- | :--- | :--- | :--- |
| **Token 效率** | 需输出完整内容，随行数线性增长 | 仅输出变更内容或使用本地缓存 | **Fast-Edit 优** |
| **稳定性** | 大规模输出易截断或产生逻辑漂移 | 原子化行操作，流式输入 | **Fast-Edit 优** |
| **执行速度** | 受模型生成速度限制（慢） | 本地 IO 处理（极快） | **Fast-Edit 优** |
| **复杂字符处理**| 容易受 Shell 转义和引号嵌套干扰 | 支持 Base64 和 Stdin 输入 | **Fast-Edit 优** |

## 1500行大文件实测数据

### 原生方式 (理论推算)
- **数据量**：约 100KB 文本。
- **Token 消耗**：约 25,000 - 30,000 Output Tokens。
- **风险**：极大概率触发 `Output token limit reached`，导致文件写入不完整。
- **耗时**：预计 40s - 90s。

### Fast-Edit 方式 (实测)
- **写入指令**：`cat source | python3 fast_edit.py paste target --stdin`
- **修改指令**：`echo '{...}' | python3 fast_edit.py batch --stdin`
- **Token 消耗**：指令本身仅需约 50-100 Tokens。
- **耗时**：小于 0.1s。
- **结果**：1500行数据完整写入，行数验证无误。

## 结论与建议

对于 **100行以上** 的文件操作，或者**多点同步修改**的任务，应优先激活并使用 `fast-edit` Skill。它不仅能显著降低 API 使用成本，更能确保在复杂重构任务中的代码完整性。

---
*测评日期：2026年2月15日*
*测评环境：Gemini CLI on darwin*
