/**
 * Custom Edit tool — overrides the built-in Edit tool.
 *
 * Translates string-match edits into fast-edit line-number operations:
 *   oldString → find line range → fast-edit replace-lines
 *
 * Benefits over built-in:
 * - Automatic backup before every edit
 * - Warning detection (duplicate lines, bracket balance)
 * - No LSP wait overhead
 * - Shell-safe via stdin pipe (no escaping issues)
 *
 * The LLM sees the same "edit" tool interface — zero cognitive overhead.
 */
import { tool } from "@opencode-ai/plugin"
import path from "path"
import { readFileSync } from "fs"

const FAST_EDIT = path.join(
  process.env.HOME || "~",
  ".config/opencode/skills/fast-edit/fast_edit.py",
)

/**
 * Find the line range in fileContent that matches oldString exactly.
 * Returns { start, end } (1-based, inclusive) or throws if not found / ambiguous.
 */
function findLineRange(
  fileContent: string,
  oldString: string,
): { start: number; end: number } {
  const idx = fileContent.indexOf(oldString)
  if (idx === -1) {
    throw new Error("oldString not found in file content")
  }

  // Check for multiple matches
  const secondIdx = fileContent.indexOf(oldString, idx + 1)
  if (secondIdx !== -1) {
    throw new Error(
      "oldString found multiple times — provide more context to make it unique, or use replaceAll",
    )
  }

  // Convert byte offset to line numbers (1-based)
  const beforeMatch = fileContent.slice(0, idx)
  const startLine = beforeMatch.split("\n").length
  const matchLines = oldString.split("\n")
  const endLine = startLine + matchLines.length - 1

  return { start: startLine, end: endLine }
}

export default tool({
  description:
    "Performs exact string replacements in files. The oldString must match exactly " +
    "in the file. Use replaceAll to replace every occurrence. " +
    "Read the file first before editing. " +
    "STOP: If you need to replace a large block (>80 lines) with repetitive/structured content, " +
    "do NOT output the full newString here — you will waste tokens. " +
    "Instead: skill('fast-edit'), then use `fe fast-batch --stdin` or `fe fast-generate` via Bash.",
  args: {
    filePath: tool.schema
      .string()
      .describe("Absolute path to the file to modify"),
    oldString: tool.schema.string().describe("The exact text to find and replace"),
    newString: tool.schema
      .string()
      .describe("The replacement text (must differ from oldString)"),
    replaceAll: tool.schema
      .boolean()
      .optional()
      .describe("Replace all occurrences (default: false)"),
  },
  async execute(args, context) {
    const { filePath, oldString, newString, replaceAll } = args
    const resolvedPath = path.isAbsolute(filePath)
      ? filePath
      : path.join(context.directory, filePath)

    if (oldString === newString) {
      throw new Error("oldString and newString are identical — no change needed")
    }

    // Read file content
    let fileContent: string
    try {
      fileContent = readFileSync(resolvedPath, "utf-8")
    } catch (e: any) {
      throw new Error(`Cannot read file ${resolvedPath}: ${e.message}`)
    }

    // --- replaceAll mode: global string replace, write back via fast-paste ---
    if (replaceAll) {
      if (!fileContent.includes(oldString)) {
        throw new Error("oldString not found in file content")
      }
      const updated = fileContent.split(oldString).join(newString)
      const count = fileContent.split(oldString).length - 1

      const proc = Bun.spawn(
        ["python3", FAST_EDIT, "fast-paste", resolvedPath, "--stdin"],
        { stdin: new Blob([updated]), stdout: "pipe", stderr: "pipe" },
      )

      const exitCode = await proc.exited
      const stderr = await new Response(proc.stderr).text()
      if (exitCode !== 0) {
        // Fallback: direct write
        await Bun.write(resolvedPath, updated)
        return `Replaced ${count} occurrences in ${resolvedPath} (direct write)`
      }
      return `Replaced ${count} occurrences of oldString in ${resolvedPath}`
    }

    // --- Single-match mode: find line range, use fast-edit batch ---
    const { start, end } = findLineRange(fileContent, oldString)

    // Build batch JSON for fast-edit
    const batchSpec = {
      file: resolvedPath,
      edits: [
        {
          action: "replace-lines",
          start,
          end,
          content: newString.endsWith("\n") ? newString : newString + "\n",
        },
      ],
    }

    const proc = Bun.spawn(
      ["python3", FAST_EDIT, "fast-batch", "--stdin"],
      { stdin: new Blob([JSON.stringify(batchSpec)]), stdout: "pipe", stderr: "pipe" },
    )

    const exitCode = await proc.exited
    const stdout = await new Response(proc.stdout).text()
    const stderr = await new Response(proc.stderr).text()

    if (exitCode !== 0) {
      // Fallback: direct string replace + write
      const updated = fileContent.replace(oldString, newString)
      await Bun.write(resolvedPath, updated)
      return `Edited ${resolvedPath} lines ${start}-${end} (direct write, fast-edit error: ${stderr.trim()})`
    }

    // Parse fast-edit output for warnings
    try {
      const result = JSON.parse(stdout)
      const warnings = result.warnings || result.results?.[0]?.warnings || []
      const warningMsg =
        warnings.length > 0
          ? `\n⚠️ Warnings: ${warnings.join("; ")}`
          : ""
      const backup = result.backup || result.results?.[0]?.backup || ""
      const backupMsg = backup ? ` (backup: ${path.basename(backup)})` : ""
      return `Edited ${resolvedPath} lines ${start}-${end}${backupMsg}${warningMsg}`
    } catch {
      return stdout.trim() || `Edited ${resolvedPath} lines ${start}-${end}`
    }
  },
})
