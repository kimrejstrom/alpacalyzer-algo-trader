"""Tests for architecture boundary linter."""

import ast
from pathlib import Path

from scripts.lint_architecture import (
    check_entry_has_stop_loss,
    check_file_size,
    check_import_boundaries,
    get_package_name,
)

SRC_ROOT = Path("src/alpacalyzer")


def test_get_package_name_subpackage():
    """Test extracting package name from subpackage file."""
    path = SRC_ROOT / "strategies" / "momentum.py"
    assert get_package_name(path) == "strategies"


def test_get_package_name_root_module():
    """Test extracting package name from root-level module."""
    path = SRC_ROOT / "orchestrator.py"
    assert get_package_name(path) == "orchestrator"


def test_get_package_name_outside_src():
    """Test returns None for files outside src/alpacalyzer."""
    path = Path("tests/test_foo.py")
    assert get_package_name(path) is None


def test_import_boundary_violation():
    """Test that forbidden imports are detected."""
    code = "from alpacalyzer.agents.foo import bar"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "strategies" / "test.py"

    violations = check_import_boundaries(filepath, tree)

    assert len(violations) == 1
    assert violations[0].rule == "ARCH-IMPORT"
    assert "agents" in violations[0].message


def test_import_boundary_allowed():
    """Test that allowed imports pass."""
    code = "from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "strategies" / "test.py"

    violations = check_import_boundaries(filepath, tree)

    assert len(violations) == 0


def test_import_boundary_non_tracked_package():
    """Test that packages not in FORBIDDEN_IMPORTS are ignored."""
    code = "from alpacalyzer.agents.foo import bar"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "utils" / "test.py"

    violations = check_import_boundaries(filepath, tree)

    assert len(violations) == 0


def test_entry_decision_with_stop_loss():
    """Test that EntryDecision with stop_loss passes."""
    code = "EntryDecision(should_enter=True, stop_loss=145.0, reason='test')"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "strategies" / "test.py"

    violations = check_entry_has_stop_loss(filepath, tree)

    assert len(violations) == 0


def test_entry_decision_without_stop_loss():
    """Test that EntryDecision without stop_loss is flagged."""
    code = "EntryDecision(should_enter=True, reason='test')"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "strategies" / "test.py"

    violations = check_entry_has_stop_loss(filepath, tree)

    assert len(violations) == 1
    assert violations[0].rule == "SAFETY-STOP-LOSS"


def test_entry_decision_should_enter_false():
    """Test that EntryDecision(should_enter=False) is not flagged."""
    code = "EntryDecision(should_enter=False, reason='no entry')"
    tree = ast.parse(code)
    filepath = SRC_ROOT / "strategies" / "test.py"

    violations = check_entry_has_stop_loss(filepath, tree)

    assert len(violations) == 0


def test_file_size_under_limit(tmp_path):
    """Test that small files pass size check."""
    f = tmp_path / "small.py"
    f.write_text("x = 1\n" * 100)

    violations = check_file_size(f)

    assert len(violations) == 0


def test_file_size_over_limit(tmp_path):
    """Test that large files are flagged."""
    f = tmp_path / "large.py"
    f.write_text("x = 1\n" * 1000)

    violations = check_file_size(f)

    assert len(violations) == 1
    assert violations[0].rule == "SIZE-LIMIT"
    assert "1000" in violations[0].message
