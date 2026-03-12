/**
 * Custom Write tool — overrides the built-in Write tool.
 *
 * Delegates to fast-edit's `fast-paste --stdin` for:
 * - Automatic backup before overwrite
 * - Shell-safe content handling (no escaping issues)
 * - Consistent with fast-edit ecosystem
 *
 * The LLM sees the same "write" tool interface — zero cognitive overhead.
 */
import { tool } from "@opencode-ai/plugin"
import path from "path"

const FAST_EDIT = path.join(
  process.env.HOME || "~",
  ".config/opencode/skills/fast-edit/fast_edit.py",
)

export default tool({
  description:
    "Writes a file to the local filesystem. Creates parent directories if needed. " +
    "Overwrites existing files. Use the read tool first on existing files before writing. " +
    "STOP: For NEW files >150 lines with repetitive/structured content (configs, migrations, data, boilerplate), " +
    "do NOT use this tool — you will waste tokens outputting the full content. " +
    "Instead: skill('fast-edit'), then `fe fast-generate --stdin -o FILE << 'PYEOF'` with ≤80 lines of Python generator code.",
  args: {
    filePath: tool.schema
      .string()
      .describe("Absolute path to the file to write"),
    content: tool.schema.string().describe("The content to write to the file"),
  },
  async execute(args, context) {
    const { filePath, content } = args
    const resolvedPath = path.isAbsolute(filePath)
      ? filePath
      : path.join(context.directory, filePath)

    // Ensure parent directory exists
    const dir = path.dirname(resolvedPath)
    await Bun.$`mkdir -p ${dir}`.quiet()

    // Pipe content via stdin to fast-edit paste (shell-safe, auto-backup)
    const proc = Bun.spawn(
      ["python3", FAST_EDIT, "fast-paste", resolvedPath, "--stdin"],
      {
        stdin: new Blob([content]),
        stdout: "pipe",
        stderr: "pipe",
      },
    )

    const exitCode = await proc.exited
    const stdout = await new Response(proc.stdout).text()
    const stderr = await new Response(proc.stderr).text()

    if (exitCode !== 0) {
      // Fallback: direct write if fast-edit fails
      try {
        await Bun.write(resolvedPath, content)
        return `Wrote ${content.split("\n").length} lines to ${resolvedPath} (direct write, fast-edit unavailable: ${stderr.trim()})`
      } catch (e: any) {
        throw new Error(
          `Failed to write ${resolvedPath}: fast-edit error: ${stderr.trim()}, direct write error: ${e.message}`,
        )
      }
    }

    // Parse fast-edit JSON output for nice feedback
    const lineCount = content.split("\n").length
    try {
      const result = JSON.parse(stdout)
      const lines = result.lines || lineCount
      const backup = result.backup ? ` (backup: ${result.backup})` : ""
      let msg = `Wrote ${lines} lines to ${resolvedPath}${backup}`

      // Large file hint: remind AI to use fast-generate next time
      if (lineCount > 150) {
        msg +=
          `\n\n⚠️ LARGE FILE (${lineCount} lines). You just spent tokens outputting the entire file content. ` +
          `Next time, use \`fe fast-generate --stdin -o ${resolvedPath} << 'PYEOF'\` with compact Python ` +
          `generator code (≤80 lines) to produce the same output — saves 5-10x tokens. ` +
          `Load the skill first: skill("fast-edit"). See skills/large-file.md for examples.`
      }

      return msg
    } catch {
      let msg = stdout.trim() || `Wrote to ${resolvedPath}`
      if (lineCount > 150) {
        msg +=
          `\n\n⚠️ LARGE FILE (${lineCount} lines). Next time use \`fe fast-generate\` to save tokens. ` +
          `Load skill("fast-edit") first.`
      }
      return msg
    }
  },
})
