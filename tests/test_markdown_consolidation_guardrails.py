"""Architektur-Smell-Test: `_HEADING_RE` bleibt Implementierungsdetail von `markdown_sections.py`.

Siehe Implementierungsplan zur kursplanerweiten Markdown-Konsolidierung, Punkt 5/9: andere
Module duerfen ausschliesslich die vier oeffentlichen Funktionen aus `markdown_sections.py`
nutzen, nie eine eigene Heading-Regex definieren oder `_HEADING_RE` direkt importieren --
sonst bleibt die konkrete Erkennung nicht austauschbar und eine neue Duplizierung entsteht.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_PATTERN = re.compile(r"_HEADING_RE\s*=\s*re\.compile|\b_HEADING_RE\b")


def test_no_module_outside_markdown_sections_defines_or_imports_heading_re():
    offending_files = []
    for directory_name in ("core/domain", "core/usecases", "adapters/gui", "infrastructure/repositories"):
        directory = _REPO_ROOT / "kursplaner" / directory_name
        if not directory.is_dir():
            continue
        for path in directory.glob("*.py"):
            if path.name == "markdown_sections.py":
                continue
            if _FORBIDDEN_PATTERN.search(path.read_text(encoding="utf-8")):
                offending_files.append(str(path.relative_to(_REPO_ROOT)))

    assert offending_files == []
