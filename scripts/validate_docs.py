#!/usr/bin/env python3
"""
Validate documentation cross-references.

Checks that all file paths referenced in AGENTS.md, skill files,
and architecture docs actually exist on disk.

Usage:
    uv run python scripts/validate_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Files and directories to scan for cross-references
DOCS_TO_SCAN = [
    "AGENTS.md",
    "docs/INDEX.md",
    "docs/architecture/overview.md",
]

# Glob patterns for additional files to scan
SCAN_GLOBS = [
    ".agents/skills/*/SKILL.md",
    ".agents/commands/*.md",
    ".agents/agents/*/prompt.md",
    "docs/dev/*.md",
    "docs/architecture/decisions/*.md",
]

# Patterns that match file path references in markdown
# Matches: [text](path), `path/to/file.py`, src/alpacalyzer/module/file.py
PATH_PATTERNS = [
    # Markdown links: [text](relative/path.md)
    re.compile(r"\[.*?\]\((?!https?://|#|mailto:)([^)]+)\)"),
    # Backtick paths that look like file references
    re.compile(r"`((?:src|tests|scripts|docs|\.agents|\.claude|\.opencode|\.github|\.config)/[^`]+)`"),
]

# Paths to ignore (known external or generated)
IGNORE_PATTERNS = {
    "migration_roadmap.md",  # May not exist yet
    "SUPERPOWERS_INTEGRATION.md",  # May not exist yet
}


class BrokenRef:
    """A broken cross-reference."""

    def __init__(self, source: str, line: int, target: str) -> None:
        self.source = source
        self.line = line
        self.target = target

    def __str__(self) -> str:
        return f"{self.source}:{self.line}: broken reference → `{self.target}`"


def scan_file(filepath: Path) -> list[BrokenRef]:
    """Scan a markdown file for broken cross-references."""
    broken = []
    try:
        lines = filepath.read_text().splitlines()
    except OSError:
        return broken

    for line_num, line in enumerate(lines, start=1):
        # Skip code blocks
        if line.strip().startswith("```"):
            continue

        for pattern in PATH_PATTERNS:
            for match in pattern.finditer(line):
                target = match.group(1).strip()

                # Strip markdown anchors (e.g., file.md#section)
                target = target.split("#")[0]
                if not target:
                    continue

                # Skip ignored patterns
                if target in IGNORE_PATTERNS:
                    continue

                # Skip URLs and template placeholders
                if target.startswith(("http://", "https://", "<", "{", "$")):
                    continue

                # Skip paths with template placeholders (e.g., {name}, <agent>)
                if re.search(r"[{<].*[}>]", target):
                    continue

                # Skip glob patterns (e.g., *.py, tests/test_*)
                if "*" in target:
                    continue

                # Resolve relative to the file's directory
                resolved = filepath.parent / target
                if not resolved.exists():
                    # Also try from repo root
                    if not Path(target).exists():
                        broken.append(
                            BrokenRef(
                                source=str(filepath),
                                line=line_num,
                                target=target,
                            )
                        )

    return broken


def main() -> int:
    """Validate all doc cross-references."""
    all_broken: list[BrokenRef] = []

    # Scan explicit files
    for doc_path in DOCS_TO_SCAN:
        p = Path(doc_path)
        if p.exists():
            all_broken.extend(scan_file(p))

    # Scan glob patterns
    for glob_pattern in SCAN_GLOBS:
        for p in sorted(Path(".").glob(glob_pattern)):
            all_broken.extend(scan_file(p))

    if not all_broken:
        print("✓ Doc cross-reference validation passed. All references resolve.")
        return 0

    print(f"\n{'=' * 60}")
    print(f"BROKEN REFERENCES ({len(all_broken)})")
    print(f"{'=' * 60}")
    for ref in all_broken:
        print(f"\n  {ref}")

    print(f"\nTotal: {len(all_broken)} broken reference(s)")
    print("Fix these by updating the path or creating the missing file.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
