"""The 300-line exception section in ARCHITEKTUR_KERN.md (§28) stays well-formed and current.

Every listed exception needs a justification, must point to an existing file and must
really exceed the limit -- a stale entry would silently exempt a file that has since
been split (or renamed) and should be checked normally again.
"""

from __future__ import annotations

from pathlib import Path

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()

from bw_gui.testing.line_limits import LINE_LIMIT, count_executable_lines, parse_exceptions  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _exceptions():
    text = (REPO_ROOT / "docs" / "ARCHITEKTUR_KERN.md").read_text(encoding="utf-8")
    return parse_exceptions(text)


def test_every_exception_has_a_justification():
    """No table row without reason."""
    _, problems = _exceptions()
    assert problems == []


def test_every_exception_exists_and_exceeds_the_limit():
    """Stale entries (file gone or already below the limit) must be removed."""
    exceptions, _ = _exceptions()
    assert exceptions, "exception section missing or empty"
    for rel_path in exceptions:
        path = REPO_ROOT / rel_path
        assert path.is_file(), f"{rel_path}: listed as exception but missing"
        count = count_executable_lines(path.read_text(encoding="utf-8-sig"))
        assert count > LINE_LIMIT, f"{rel_path}: only {count} executable lines, remove the exception"
