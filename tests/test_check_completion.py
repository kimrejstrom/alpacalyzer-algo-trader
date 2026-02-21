"""Tests for check-completion.sh hook."""

import stat
from pathlib import Path

HOOK_PATH = Path(".agents/hooks/check-completion.sh")
PLAN_HOOK_PATH = Path(".agents/hooks/check-plan-exists.sh")


def test_check_completion_hook_exists():
    """Test that the check-completion hook script exists and is executable."""
    assert HOOK_PATH.exists()
    mode = HOOK_PATH.stat().st_mode
    assert mode & stat.S_IXUSR, "Hook should be executable by owner"


def test_check_completion_hook_has_shebang():
    """Test that the hook has a proper bash shebang."""
    content = HOOK_PATH.read_text()
    assert content.startswith("#!/usr/bin/env bash")


def test_check_completion_hook_checks_tests():
    """Test that the hook checks for test failures."""
    content = HOOK_PATH.read_text()
    assert "pytest" in content
    assert "FAILED" in content


def test_check_completion_hook_checks_review():
    """Test that the hook checks for code review findings."""
    content = HOOK_PATH.read_text()
    assert "CODE_REVIEW" in content
    assert "Critical" in content or "critical" in content


def test_check_completion_hook_has_iteration_cap():
    """Test that the hook caps iterations to prevent infinite loops."""
    content = HOOK_PATH.read_text()
    assert "MAX_ITERATIONS" in content
    assert "GRIND_ITERATION" in content


def test_check_completion_hook_checks_blind_review():
    """Test that the hook checks for blind review (issue #145)."""
    content = HOOK_PATH.read_text()
    assert "blind" in content.lower() or "separate agent" in content.lower()


def test_check_plan_exists_hook_exists():
    """Test that the plan-first hook exists and is executable."""
    assert PLAN_HOOK_PATH.exists()
    mode = PLAN_HOOK_PATH.stat().st_mode
    assert mode & stat.S_IXUSR, "Hook should be executable by owner"


def test_check_plan_exists_allows_docs():
    """Test that the plan hook allows writes to docs/plans/."""
    content = PLAN_HOOK_PATH.read_text()
    assert "docs/plans" in content


def test_check_plan_exists_allows_agent_config():
    """Test that the plan hook allows writes to .agents/ config."""
    content = PLAN_HOOK_PATH.read_text()
    assert ".agents" in content


OPENCODE_HOOK_PATH = Path(".agents/hooks/opencode-grind-loop.sh")
GRIND_LOOP_PLUGIN_PATH = Path(".opencode/plugins/grind-loop.ts")
PLAN_FIRST_PLUGIN_PATH = Path(".opencode/plugins/plan-first.ts")


def test_opencode_grind_loop_exists():
    """Test that the OpenCode grind loop script exists and is executable."""
    assert OPENCODE_HOOK_PATH.exists()
    mode = OPENCODE_HOOK_PATH.stat().st_mode
    assert mode & stat.S_IXUSR, "Hook should be executable by owner"


def test_opencode_grind_loop_has_shebang():
    """Test that the grind loop has a proper bash shebang."""
    content = OPENCODE_HOOK_PATH.read_text()
    assert content.startswith("#!/usr/bin/env bash")


def test_opencode_grind_loop_has_iteration_cap():
    """Test that the grind loop caps iterations."""
    content = OPENCODE_HOOK_PATH.read_text()
    assert "MAX_GRIND_ITERATIONS" in content or "MAX_ITERATIONS" in content


def test_opencode_grind_loop_calls_check_completion():
    """Test that the grind loop delegates to shared check-completion.sh."""
    content = OPENCODE_HOOK_PATH.read_text()
    assert "check-completion.sh" in content


def test_opencode_grind_loop_has_plan_check():
    """Test that the grind loop enforces plan-first workflow."""
    content = OPENCODE_HOOK_PATH.read_text()
    assert "plan" in content.lower()
    assert "docs/plans" in content


def test_opencode_grind_loop_can_be_sourced():
    """Test that the script supports being sourced (grind_loop function)."""
    content = OPENCODE_HOOK_PATH.read_text()
    assert "grind_loop" in content
    assert "BASH_SOURCE" in content


# --- OpenCode Plugin Tests ---


def test_grind_loop_plugin_exists():
    """Test that the OpenCode grind loop plugin exists."""
    assert GRIND_LOOP_PLUGIN_PATH.exists()


def test_grind_loop_plugin_uses_session_idle():
    """Test that the grind loop plugin listens to session.idle events."""
    content = GRIND_LOOP_PLUGIN_PATH.read_text()
    assert "session.idle" in content


def test_grind_loop_plugin_calls_check_completion():
    """Test that the plugin delegates to shared check-completion.sh."""
    content = GRIND_LOOP_PLUGIN_PATH.read_text()
    assert "check-completion.sh" in content


def test_grind_loop_plugin_has_iteration_cap():
    """Test that the plugin caps iterations to prevent infinite loops."""
    content = GRIND_LOOP_PLUGIN_PATH.read_text()
    assert "MAX_ITERATIONS" in content


def test_grind_loop_plugin_re_prompts():
    """Test that the plugin re-prompts the agent via session.prompt."""
    content = GRIND_LOOP_PLUGIN_PATH.read_text()
    assert "session.prompt" in content


def test_grind_loop_plugin_exports_plugin():
    """Test that the plugin exports a Plugin type."""
    content = GRIND_LOOP_PLUGIN_PATH.read_text()
    assert "Plugin" in content
    assert "export" in content


def test_plan_first_plugin_exists():
    """Test that the OpenCode plan-first plugin exists."""
    assert PLAN_FIRST_PLUGIN_PATH.exists()


def test_plan_first_plugin_uses_tool_execute_before():
    """Test that the plan-first plugin intercepts tool.execute.before."""
    content = PLAN_FIRST_PLUGIN_PATH.read_text()
    assert "tool.execute.before" in content


def test_plan_first_plugin_delegates_to_shared_script():
    """Test that the plugin delegates to the shared check-plan-exists.sh."""
    content = PLAN_FIRST_PLUGIN_PATH.read_text()
    assert "check-plan-exists.sh" in content


def test_plan_first_plugin_blocks_with_error():
    """Test that the plugin throws an error when the script denies."""
    content = PLAN_FIRST_PLUGIN_PATH.read_text()
    assert "throw" in content
