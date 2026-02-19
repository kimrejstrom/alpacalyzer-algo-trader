#!/bin/bash
# Setup script to create symlinks from tool-specific directories to .agents/ source of truth
# Run this script from the repository root

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

echo "Setting up agent symlinks..."

# Link .claude/skills/* to .agents/skills/
if [ -d ".agents/skills" ]; then
    echo "Linking .claude/skills/ to .agents/skills/..."
    for skill in .agents/skills/*/; do
        skill_name=$(basename "$skill")
        if [ -d ".claude/skills/$skill_name" ]; then
            rm -rf ".claude/skills/$skill_name"
        fi
        ln -s "../../.agents/skills/$skill_name" ".claude/skills/$skill_name"
        echo "  Linked $skill_name"
    done
fi

# Link .opencode/agent/* to .agents/agents/
if [ -d ".agents/agents" ]; then
    echo "Linking .opencode/agent/ to .agents/agents/..."
    for agent in .agents/agents/*.md; do
        [ -e "$agent" ] || continue
        agent_name=$(basename "$agent")
        if [ -f ".opencode/agent/$agent_name" ]; then
            rm -f ".opencode/agent/$agent_name"
        fi
        ln -s "../../.agents/agents/$agent_name" ".opencode/agent/$agent_name"
        echo "  Linked $agent_name"
    done
fi

echo "Agent symlinks setup complete!"
echo ""
echo "Directory structure:"
echo "  .agents/          - Source of truth"
echo "    skills/         - Shared skills"
echo "    agents/         - Agent definitions"
echo "    commands/       - Reusable commands (to be populated)"
echo "    hooks/          - Shared hook scripts (to be populated)"
echo "  .claude/skills/  - Symlinks to .agents/skills/"
echo "  .opencode/agent/ - Symlinks to .agents/agents/"
