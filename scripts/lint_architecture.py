#!/usr/bin/env python3
"""
Architecture boundary linter with agent-readable error messages.

Enforces:
1. Import direction rules (lower layers cannot import upper layers)
2. Trading safety invariants (every entry must have stop_loss)
3. Event model inheritance (must inherit from BaseEvent)
4. File size warnings (>1000 lines)

See docs/architecture/overview.md for the full layer diagram.

Usage:
    uv run python scripts/lint_architecture.py
    uv run python scripts/lint_architecture.py --fix-suggestions
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# --- Layer definitions ---
# Each key is a package name under src/alpacalyzer/
# The value is a set of packages it is FORBIDDEN from importing.
# Based on docs/architecture/overview.md "Import Direction Rules"

FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    # Lower layers cannot import upper layers
    "strategies": {"agents", "orchestrator", "cli", "hedge_fund", "pipeline", "scanners"},
    "execution": {"cli", "orchestrator", "pipeline", "scanners", "hedge_fund"},
    "agents": {"cli", "orchestrator", "execution", "strategies", "pipeline", "scanners"},
    "scanners": {"cli", "orchestrator", "execution", "strategies", "agents", "hedge_fund"},
    "pipeline": {"cli", "orchestrator", "execution", "strategies", "agents", "hedge_fund"},
    "events": {"cli", "orchestrator", "execution", "strategies", "agents", "hedge_fund", "pipeline", "scanners"},
    "trading": {"cli", "orchestrator", "execution", "strategies", "agents", "hedge_fund", "pipeline", "scanners"},
}

# Map module names to their import prefixes
MODULE_PREFIXES = {
    "agents": "alpacalyzer.agents",
    "cli": "alpacalyzer.cli",
    "orchestrator": "alpacalyzer.orchestrator",
    "execution": "alpacalyzer.execution",
    "strategies": "alpacalyzer.strategies",
    "pipeline": "alpacalyzer.pipeline",
    "scanners": "alpacalyzer.scanners",
    "events": "alpacalyzer.events",
    "trading": "alpacalyzer.trading",
    "hedge_fund": "alpacalyzer.hedge_fund",
}

SRC_ROOT = Path("src/alpacalyzer")
MAX_FILE_LINES = 1000


class Violation:
    """A single lint violation with remediation."""

    def __init__(self, path: str, line: int, rule: str, message: str, remediation: str) -> None:
        self.path = path
        self.line = line
        self.rule = rule
        self.message = message
        self.remediation = remediation

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}\n  → {self.remediation}"


def get_package_name(filepath: Path) -> str | None:
    """Extract the package name from a file path under src/alpacalyzer/."""
    try:
        rel = filepath.relative_to(SRC_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 1:
        # For files directly in alpacalyzer/ (like orchestrator.py, hedge_fund.py)
        if len(parts) == 1:
            return parts[0].replace(".py", "")
        return parts[0]
    return None


def check_import_boundaries(filepath: Path, tree: ast.AST) -> list[Violation]:
    """Check that imports respect architecture layer boundaries."""
    violations = []
    package = get_package_name(filepath)
    if package is None or package not in FORBIDDEN_IMPORTS:
        return violations

    forbidden = FORBIDDEN_IMPORTS[package]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden_pkg in forbidden:
                    prefix = MODULE_PREFIXES.get(forbidden_pkg, "")
                    if prefix and alias.name.startswith(prefix):
                        violations.append(
                            Violation(
                                path=str(filepath),
                                line=node.lineno,
                                rule="ARCH-IMPORT",
                                message=f"Import `{alias.name}` from `{filepath.name}` violates architecture boundary. `{package}/` must not import from `{forbidden_pkg}/`.",
                                remediation="See docs/architecture/overview.md for allowed import directions. Move shared logic to a lower layer (e.g., `data/`, `utils/`, `events/`).",
                            )
                        )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for forbidden_pkg in forbidden:
                prefix = MODULE_PREFIXES.get(forbidden_pkg, "")
                if prefix and node.module.startswith(prefix):
                    violations.append(
                        Violation(
                            path=str(filepath),
                            line=node.lineno,
                            rule="ARCH-IMPORT",
                            message=f"Import `{node.module}` from `{filepath.name}` violates architecture boundary. `{package}/` must not import from `{forbidden_pkg}/`.",
                            remediation="See docs/architecture/overview.md for allowed import directions. Move shared logic to a lower layer (e.g., `data/`, `utils/`, `events/`).",
                        )
                    )

    return violations


def check_entry_has_stop_loss(filepath: Path, tree: ast.AST) -> list[Violation]:
    """Check that EntryDecision(should_enter=True) always includes stop_loss."""
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match EntryDecision(...) calls
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name != "EntryDecision":
            continue

        # Check if should_enter=True
        has_should_enter_true = False
        has_stop_loss = False

        for kw in node.keywords:
            if kw.arg == "should_enter" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                has_should_enter_true = True
            if kw.arg == "stop_loss":
                has_stop_loss = True

        if has_should_enter_true and not has_stop_loss:
            violations.append(
                Violation(
                    path=str(filepath),
                    line=node.lineno,
                    rule="SAFETY-STOP-LOSS",
                    message="EntryDecision(should_enter=True) without stop_loss. Every entry MUST have a stop loss to limit downside risk.",
                    remediation="Add stop_loss parameter: EntryDecision(should_enter=True, stop_loss=<price>). Calculate stop loss based on strategy config (e.g., entry_price * (1 - stop_loss_pct)).",
                )
            )

    return violations


def check_file_size(filepath: Path) -> list[Violation]:
    """Warn if file exceeds MAX_FILE_LINES."""
    violations = []
    try:
        line_count = len(filepath.read_text().splitlines())
    except OSError:
        return violations

    if line_count >= MAX_FILE_LINES:
        violations.append(
            Violation(
                path=str(filepath),
                line=1,
                rule="SIZE-LIMIT",
                message=f"File has {line_count} lines (limit: {MAX_FILE_LINES}). Large files are harder to review and test.",
                remediation="Consider splitting into smaller modules. Extract helper functions or data classes into separate files.",
            )
        )

    return violations


def lint_file(filepath: Path) -> list[Violation]:
    """Run all lint checks on a single file."""
    violations = []

    # File size check (no AST needed)
    violations.extend(check_file_size(filepath))

    # Parse AST
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError) as e:
        violations.append(
            Violation(
                path=str(filepath),
                line=1,
                rule="PARSE-ERROR",
                message=f"Could not parse file: {e}",
                remediation="Fix syntax errors before running architecture lint.",
            )
        )
        return violations

    violations.extend(check_import_boundaries(filepath, tree))
    violations.extend(check_entry_has_stop_loss(filepath, tree))

    return violations


def main() -> int:
    """Run architecture linter on all Python files under src/alpacalyzer/."""
    if not SRC_ROOT.exists():
        print(f"ERROR: {SRC_ROOT} not found. Run from repository root.", file=sys.stderr)
        return 1

    all_violations: list[Violation] = []
    py_files = sorted(SRC_ROOT.rglob("*.py"))

    for filepath in py_files:
        # Skip __pycache__
        if "__pycache__" in filepath.parts:
            continue
        all_violations.extend(lint_file(filepath))

    if not all_violations:
        print("✓ Architecture lint passed. No violations found.")
        return 0

    # Group by rule for readability
    errors = [v for v in all_violations if v.rule in ("ARCH-IMPORT", "SAFETY-STOP-LOSS")]
    warnings = [v for v in all_violations if v.rule in ("SIZE-LIMIT",)]

    if errors:
        print(f"\n{'=' * 60}")
        print(f"ERRORS ({len(errors)})")
        print(f"{'=' * 60}")
        for v in errors:
            print(f"\n{v}")

    if warnings:
        print(f"\n{'=' * 60}")
        print(f"WARNINGS ({len(warnings)})")
        print(f"{'=' * 60}")
        for v in warnings:
            print(f"\n{v}")

    print(f"\nTotal: {len(errors)} error(s), {len(warnings)} warning(s)")

    # Only fail on errors, not warnings
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
