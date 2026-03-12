    ---
    name: configuration
    description: 配置项、路径约定与平台差异
    ---

    # Configuration

    > fast-edit 的路径、存储与运行环境配置说明。

    ## 路径与目录约定

    | 组件 | 默认路径 | 说明 |
    |---|---|---|
    | 备份目录 | `~/.fast-edit-backups/` | `verify`/`restore` 使用的备份根目录 | 
    | OpenCode Part 存储 | `~/.local/share/opencode/storage/part` | `save-pasted` 从此读取大粘贴 | 
    | OpenCode Message 存储 | `~/.local/share/opencode/storage/message` | `save-pasted` 查找用户消息 | 

    ### 备份目录结构

    ```text
    ~/.fast-edit-backups/
    └── <md5(abs_path)>/
        ├── 20260226_120000_123456
        ├── 20260226_120000_123456.meta
        └── 20260226_120000_123456_pre_restore
    ```

    - `meta` 文件保存原始绝对路径。
    - `pre_restore` 是回滚前的 forward backup。

    ## 自动备份开关

    - 编辑操作（replace/insert/delete/batch）会调用 `edit._maybe_backup`。
    - `edit._auto_backup = True`（默认开启）。
    - 如需关闭，必须在运行时修改变量（目前未提供 CLI 开关）。

    ## JSON 协议配置

    ### batch JSON

    ```json
    {
      "file": "/path/to/file.py",
      "edits": [
        {"action": "replace-lines", "start": 10, "end": 12, "content": "new
"},
        {"action": "insert-after", "line": 25, "content": "# comment
"},
        {"action": "delete-lines", "start": 40, "end": 42}
      ]
    }
    ```

    **注意**：字段名必须是 `action`，不是 `type`。

    ### write JSON

    ```json
    {
      "files": [
        {"file": "/tmp/a.py", "content": "def a(): pass
"},
        {"file": "/tmp/b.py", "content": "ZGVmIGIoKTogcGFzcwo=", "encoding": "base64"},
        {"file": "/tmp/c.py", "content": "```python
def c(): pass
```", "extract": true}
      ]
    }
    ```

    - `encoding: "base64"`：写入前解码
    - `extract: true`：提取 ```...``` 代码块

    ### generate JSON

    - **单文件模式**：stdout 直接写入 `-o FILE`
    - **多文件模式**：stdout 为 `{"files": [{"file": "...", "content": "..."}]}`

    `.json` 文件默认进行 JSON 验证，可通过 `--no-validate` 关闭。

    ## 平台差异

    | 平台 | 剪贴板命令 | 说明 |
    |---|---|---|
    | macOS | `pbpaste` | 默认支持 | 
    | Linux | `xclip -selection clipboard -o` | 需要安装 xclip | 
    | Windows | 无内置 | 建议使用 `--stdin` | 

    ## 行号与换行

    - 行号 **1-based** 且包含首尾。
    - `replace`/`insert` 会根据文件现有行尾选择 `
` 或 `
`。
    - `normalize_content` 会统一新内容的行尾风格。

    ## 超时配置

    `generate` 默认超时 30 秒，可用 `--timeout` 调整：

    ```bash
    fe generate --stdin -o out.json --timeout 60
    ```

    ## 依赖检查器配置

    `check` 会按顺序自动检测：

    1. basedpyright
    2. pyright
    3. mypy

    可通过 `--checker` 强制指定。

    ## 运行环境建议

    - Python 3.8+（标准库即可运行）
    - 若需要语法检查：安装对应语言的编译器/运行时
    - 若使用 `save-pasted`：确保 OpenCode 本地存储存在

    ## Debug 计时模式

    端到端计时功能默认**关闭**。启用后 AI 会在加载 skill 时自动执行 `fe timer start`，并在后续 `generate` 操作中附带 `--timer` 参数，输出中会包含从 skill 加载到任务完成的总耗时。

    ### 启用方式

    在 `[FAST-EDIT]` 规则块中添加 `debug-timer: true`：

    ```
    [FAST-EDIT]
    When you need to edit, create, write, or save files:
    1. Load the fast-edit skill first: skill("fast-edit")
    2. Use fast-edit commands (show/replace/insert/delete/batch/paste/write/generate) instead of the built-in Edit/Write tools.
    3. For batch edits or multi-file writes, prefer fast-batch and fast-write.
    4. For user-pasted content, prefer save-pasted (zero token, zero escaping).
    Fast-edit is 100x faster than built-in tools. NEVER use Edit/Write when fast-edit can do the job.
    Trigger: any intent to create, modify, save, or write a file.
    debug-timer: true
    ```

    ### 关闭方式

    删除 `debug-timer: true` 这一行，或改为 `debug-timer: false`。AI 加载 skill 时会跳过所有 timer 相关操作。

    ### 计时数据

    | 项目 | 说明 |
    |------|------|
    | 存储位置 | `/tmp/fe-timers/<timer_id>.json` |
    | 生命周期 | `timer start` 创建，`timer stop` 后自动删除 |
    | 输出字段 | `total_elapsed_sec`（端到端总耗时），附加在 `generate` 的 timing 输出中 |

