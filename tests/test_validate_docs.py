"""Tests for doc cross-reference validation."""

from scripts.validate_docs import BrokenRef, scan_file


def test_scan_file_valid_references(tmp_path):
    """Test that valid references pass."""
    # Create referenced file
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("pass")

    # Create doc with valid reference
    doc = tmp_path / "README.md"
    doc.write_text("See `src/foo.py` for details.\n")

    broken = scan_file(doc)

    assert len(broken) == 0


def test_scan_file_broken_reference(tmp_path):
    """Test that broken references are detected."""
    doc = tmp_path / "README.md"
    doc.write_text("See `src/nonexistent.py` for details.\n")

    broken = scan_file(doc)

    assert len(broken) == 1
    assert "nonexistent" in broken[0].target


def test_scan_file_skips_urls(tmp_path):
    """Test that URLs are not treated as file references."""
    doc = tmp_path / "README.md"
    doc.write_text("[link](https://example.com)\n")

    broken = scan_file(doc)

    assert len(broken) == 0


def test_scan_file_skips_template_placeholders(tmp_path):
    """Test that template placeholders like {name} are skipped."""
    doc = tmp_path / "SKILL.md"
    doc.write_text("Files go in `src/alpacalyzer/agents/{name}_agent.py`\n")

    broken = scan_file(doc)

    assert len(broken) == 0


def test_scan_file_skips_glob_patterns(tmp_path):
    """Test that glob patterns like *.py are skipped."""
    doc = tmp_path / "SKILL.md"
    doc.write_text("See `src/alpacalyzer/agents/*.py` for examples.\n")

    broken = scan_file(doc)

    assert len(broken) == 0


def test_broken_ref_str():
    """Test BrokenRef string representation."""
    ref = BrokenRef(source="AGENTS.md", line=42, target="docs/missing.md")

    result = str(ref)

    assert "AGENTS.md:42" in result
    assert "docs/missing.md" in result
