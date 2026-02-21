import type { Plugin } from "@opencode-ai/plugin";

/**
 * Grind Loop Plugin for OpenCode
 *
 * Equivalent to Claude Code's Stop hook running check-completion.sh.
 * On session.idle, checks if work is actually complete:
 * - Tests pass
 * - No unresolved Critical/High code review findings
 * - Blind review requested if PR exists without review
 * - Iteration cap (max 5) prevents infinite loops
 *
 * If incomplete, sends a follow-up prompt to continue working.
 */

const MAX_ITERATIONS = 5;
const sessionIterations = new Map<string, number>();

export const GrindLoopPlugin: Plugin = async ({ client, $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return;

      const sessionID = (event as any).properties?.sessionID as
        | string
        | undefined;
      if (!sessionID) return;

      const iteration = (sessionIterations.get(sessionID) ?? 0) + 1;
      sessionIterations.set(sessionID, iteration);

      if (iteration > MAX_ITERATIONS) {
        await client.app.log({
          body: {
            service: "grind-loop",
            level: "warn",
            message: `Max iterations (${MAX_ITERATIONS}) reached for session ${sessionID}. Stopping.`,
          },
        });
        return;
      }

      await client.app.log({
        body: {
          service: "grind-loop",
          level: "info",
          message: `Checking completion (iteration ${iteration}/${MAX_ITERATIONS})...`,
        },
      });

      try {
        const result =
          await $`GRIND_ITERATION=${iteration} bash .agents/hooks/check-completion.sh 2>/dev/null`.nothrow();

        if (result.exitCode === 0) {
          await client.app.log({
            body: {
              service: "grind-loop",
              level: "info",
              message: `All checks passed after ${iteration} iteration(s).`,
            },
          });
          // Reset counter on success
          sessionIterations.delete(sessionID);
          return;
        }

        // check-completion.sh outputs a follow-up prompt on stdout when incomplete
        const followup = result.stdout.toString().trim();
        if (!followup) {
          await client.app.log({
            body: {
              service: "grind-loop",
              level: "warn",
              message: `check-completion returned non-zero but no follow-up. Stopping.`,
            },
          });
          return;
        }

        await client.app.log({
          body: {
            service: "grind-loop",
            level: "info",
            message: `Incomplete. Re-prompting (iteration ${iteration}): ${followup.slice(0, 100)}...`,
          },
        });

        // Send follow-up prompt to the same session
        await client.session.prompt({
          path: { id: sessionID },
          body: {
            parts: [{ type: "text", text: followup }],
          },
        });
      } catch (err) {
        await client.app.log({
          body: {
            service: "grind-loop",
            level: "error",
            message: `Grind loop error: ${err}`,
          },
        });
      }
    },
  };
};

export default GrindLoopPlugin;
