import type { Plugin } from "@opencode-ai/plugin";
import { readFileSync } from "fs";

interface GrindConfig {
  maxIterations: number;
  stallTimeoutMs: number;
}

function readConfig(): GrindConfig {
  const defaults: GrindConfig = { maxIterations: 5, stallTimeoutMs: 300_000 };
  try {
    const raw = readFileSync(".agents/config.yaml", "utf-8");
    const num = (key: string, fb: number): number => {
      const m = raw.match(new RegExp(`^\\s+${key}:\\s*(\\d+)`, "m"));
      return m ? parseInt(m[1], 10) : fb;
    };
    return {
      maxIterations: num("max_iterations", 5),
      stallTimeoutMs: num("stall_timeout_seconds", 300) * 1000,
    };
  } catch {
    return defaults;
  }
}

function extractFollowup(output: string): string | null {
  try {
    return JSON.parse(output).followup_prompt || null;
  } catch {
    return output.trim() || null;
  }
}

const sessionIters = new Map<string, number>();
const stallTimers = new Map<string, ReturnType<typeof setTimeout>>();

export const GrindLoopPlugin: Plugin = async ({ client, $ }) => {
  const config = readConfig();

  const clearStall = (sid: string) => {
    const t = stallTimers.get(sid);
    if (t) {
      clearTimeout(t);
      stallTimers.delete(sid);
    }
  };

  const startStall = (sid: string) => {
    clearStall(sid);
    if (config.stallTimeoutMs <= 0) return;
    const secs = config.stallTimeoutMs / 1000;
    const t = setTimeout(async () => {
      stallTimers.delete(sid);
      await client.app.log({
        body: {
          service: "grind-loop",
          level: "warn",
          message: `Stall timeout (${secs}s) for session ${sid}. Re-prompting.`,
        },
      });
      try {
        await client.session.prompt({
          path: { id: sid },
          body: {
            parts: [
              {
                type: "text",
                text:
                  `You appear to be stuck — the session has been inactive for ${secs} seconds. ` +
                  "Check your current approach and try a different angle. " +
                  "If you're waiting on an external service, note the issue and move on. " +
                  "Update the scratchpad (.agents/scratchpad.md) with your current status.",
              },
            ],
          },
        });
      } catch (err) {
        await client.app.log({
          body: {
            service: "grind-loop",
            level: "error",
            message: `Failed to send stall re-prompt: ${err}`,
          },
        });
      }
    }, config.stallTimeoutMs);
    stallTimers.set(sid, t);
  };

  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return;
      const sessionID = (event as any).properties?.sessionID as
        | string
        | undefined;
      if (!sessionID) return;

      clearStall(sessionID);
      const iteration = (sessionIters.get(sessionID) ?? 0) + 1;
      sessionIters.set(sessionID, iteration);

      if (iteration > config.maxIterations) {
        await client.app.log({
          body: {
            service: "grind-loop",
            level: "warn",
            message: `Max iterations (${config.maxIterations}) reached for ${sessionID}. Stopping.`,
          },
        });
        return;
      }

      await client.app.log({
        body: {
          service: "grind-loop",
          level: "info",
          message: `Checking completion (iteration ${iteration}/${config.maxIterations})...`,
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
          sessionIters.delete(sessionID);
          clearStall(sessionID);
          return;
        }

        const followup = extractFollowup(result.stdout.toString().trim());
        if (!followup) {
          await client.app.log({
            body: {
              service: "grind-loop",
              level: "warn",
              message: "check-completion non-zero but no follow-up. Stopping.",
            },
          });
          return;
        }

        await client.app.log({
          body: {
            service: "grind-loop",
            level: "info",
            message: `Incomplete. Re-prompting (iter ${iteration}): ${followup.slice(0, 100)}...`,
          },
        });

        await client.session.prompt({
          path: { id: sessionID },
          body: { parts: [{ type: "text", text: followup }] },
        });

        startStall(sessionID);
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
