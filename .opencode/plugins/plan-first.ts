import type { Plugin } from "@opencode-ai/plugin";

/**
 * Plan-First Plugin for OpenCode
 *
 * Equivalent to Claude Code's PreToolUse hook on Write|Edit.
 * Delegates to the shared .agents/hooks/check-plan-exists.sh script,
 * which checks that a plan file exists before allowing code writes.
 */

export const PlanFirstPlugin: Plugin = async ({ $ }) => {
  return {
    "tool.execute.before": async (input, output) => {
      // Only intercept write/edit tools
      if (input.tool !== "write" && input.tool !== "edit") return;

      // Get the file path from args
      const filePath =
        (output.args as any).filePath ||
        (output.args as any).path ||
        (output.args as any).file ||
        "";

      // Delegate to the shared shell script (same one Claude's PreToolUse hook uses)
      const result =
        await $`bash .agents/hooks/check-plan-exists.sh ${filePath}`.nothrow();

      if (result.exitCode !== 0) {
        const message = result.stdout.toString().trim();
        throw new Error(
          message || "PLAN-FIRST: No plan file found in docs/plans/.",
        );
      }
    },
  };
};

export default PlanFirstPlugin;
