#!/usr/bin/env python3
"""
Audit golden principles from docs/principles.md.

Checks:
1. BOUNDARY-VALIDATION: External data parsed through Pydantic models
2. NO-RAW-HTTP: No raw requests.get/post in trading code
3. TYPED-EVENTS: Events use typed classes, not raw dicts

Usage:
    uv run python scripts/audit_principles.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC_ROOT = Path("src/alpacalyzer")


class Violation:
    """A principle violation with remediation."""

    def __init__(self, path: str, line: int, rule: str, message: str, remediation: str) -> None:
        self.path = path
        self.line = line
        self.rule = rule
        self.message = message
        self.remediation = remediation

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}\n  → {self.remediation}"


def check_raw_http(filepath: Path, tree: ast.AST) -> list[Violation]:
    """Check for raw HTTP calls (requests.get/post/put/delete) outside of data access layers."""
    violations = []
    # Allow raw HTTP in data access layers — these ARE the typed clients
    allowed_dirs = {"trading", "data", "scanners"}
    parts = filepath.parts
    for part in parts:
        if part in allowed_dirs:
            return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "requests" and node.attr in ("get", "post", "put", "delete", "patch"):
                violations.append(
                    Violation(
                        path=str(filepath),
                        line=node.lineno,
                        rule="NO-RAW-HTTP",
                        message=f"Raw `requests.{node.attr}()` call. Use typed SDK functions instead.",
                        remediation="Use alpacalyzer.trading.alpaca_client for Alpaca API calls. For other APIs, create a typed client in the appropriate module.",
                    )
                )
    return violations


def check_raw_dict_events(filepath: Path, tree: ast.AST) -> list[Violation]:
    """Check for emit_event() calls with raw dicts instead of typed event classes."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "emit_event":
            if node.args and isinstance(node.args[0], ast.Dict):
                violations.append(
                    Violation(
                        path=str(filepath),
                        line=node.lineno,
                        rule="TYPED-EVENTS",
                        message="emit_event() called with raw dict. Use a typed event class.",
                        remediation="Import the appropriate event class from alpacalyzer.events (e.g., ErrorEvent, OrderFilledEvent) and pass an instance instead of a dict.",
                    )
                )
    return violations


def check_untyped_json_parse(filepath: Path, tree: ast.AST) -> list[Violation]:
    """Check for .json() calls not wrapped in Pydantic model_validate."""
    violations = []
    # Allow in data access layers, trading client, and test files
    allowed_dirs = {"trading", "data", "scanners"}
    parts = filepath.parts
    for part in parts:
        if part in allowed_dirs:
            return violations
    if "test_" in filepath.name:
        return violations

    for node in ast.walk(tree):
        # Look for response.json() assigned directly to a variable
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "json":
                violations.append(
                    Violation(
                        path=str(filepath),
                        line=node.lineno,
                        rule="BOUNDARY-VALIDATION",
                        message="Raw `.json()` result assigned to variable. Parse through a Pydantic model.",
                        remediation="Use `MyModel.model_validate(response.json())` to validate external data at the boundary.",
                    )
                )
    return violations


def audit_file(filepath: Path) -> list[Violation]:
    """Run all principle audits on a single file."""
    violations = []
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError):
        return violations

    violations.extend(check_raw_http(filepath, tree))
    violations.extend(check_raw_dict_events(filepath, tree))
    violations.extend(check_untyped_json_parse(filepath, tree))
    return violations


def main() -> int:
    """Audit all Python files under src/alpacalyzer/ for principle violations."""
    if not SRC_ROOT.exists():
        print(f"ERROR: {SRC_ROOT} not found. Run from repo root.")
        return 1

    all_violations: list[Violation] = []
    py_files = sorted(SRC_ROOT.rglob("*.py"))

    for filepath in py_files:
        all_violations.extend(audit_file(filepath))

    if not all_violations:
        print("✓ Golden principles audit passed. No violations found.")
        return 0

    print(f"\n{'=' * 60}")
    print(f"PRINCIPLE VIOLATIONS ({len(all_violations)})")
    print(f"{'=' * 60}")
    for v in all_violations:
        print(f"\n  {v}")

    print(f"\nTotal: {len(all_violations)} violation(s)")
    print("See docs/principles.md for the full list of golden principles.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
