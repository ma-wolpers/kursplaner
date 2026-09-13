from __future__ import annotations

from kursplaner.core.domain.markdown_sections import extract_bullet_items, extract_section


def parse_list_section(body: str, title: str) -> list[str]:
    """Liest Bullet-Einträge unter einer Markdown-Section ``## <title>``.

    Nutzt `markdown_sections.py` fuer die Ueberschriften-/Abschnittserkennung
    (`## `-Ueberschrift exakt Ebene 2 gesucht, endet an der naechsten Ueberschrift
    exakt Ebene 2 -- Unterueberschriften tieferer Ebene bleiben Teil des Abschnitts)
    und `extract_bullet_items()` fuer das Bullet-Filtern selbst.
    """
    section = extract_section(body, title, target_level=2, stop_at_level=2)
    if section is None:
        return []
    return extract_bullet_items(section)


def parse_reflection(body: str) -> str:
    """Liest den Reflexionstext zwischen ``# Reflexion`` und der naechsten ``##``-Section."""
    return extract_section(body, "Reflexion", target_level=1, stop_at_level=2) or ""


def text_to_list_entries(text: str) -> list[str]:
    """Konvertiert mehrzeiligen UI-Text in Bullet-Einträge (eine Zeile = ein Eintrag)."""
    result: list[str] = []
    for line in str(text or "").splitlines():
        item = line.strip()
        if not item:
            continue
        if item.startswith("-"):
            item = item[1:].strip()
        if item:
            result.append(item)
    return result
