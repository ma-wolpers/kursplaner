"""Body einer UB-Datei: einzige Stelle für seine Struktur (lesen, Vorlage, Listen ersetzen).

Aufbau::

    # Reflexion

    <Freitext>

    ## Professionalisierungsschritte

    - …

    ## Nutzbare Ressourcen

    - …

Abschnittsnamen kommen aus `unterrichtsbesuch_policy` (``UB_*``), Abschnittsgrenzen
aus `markdown_sections`, die ``- item``-Zeilen aus `markdown_lists`. Schreibende
Use Cases ändern nur die Abschnitte, die sie betreffen (`with_development_lists`)
und reichen den übrigen Body wörtlich durch – Text, den die Nutzerin zusätzlich
in die UB-Datei geschrieben hat, geht so nie verloren.
"""

from __future__ import annotations

from collections.abc import Sequence

from kursplaner.core.domain.markdown_lists import markdown_bullet_lines, render_markdown_bullet_section
from kursplaner.core.domain.markdown_sections import extract_bullet_items, extract_section, replace_section
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_REFLECTION_HEADING,
    UB_RESOURCES_FIELD,
    UB_STEPS_FIELD,
)


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


def parse_development_lists(body: str) -> tuple[list[str], list[str]]:
    """``(Professionalisierungsschritte, Nutzbare Ressourcen)`` eines UB-Bodys."""
    return parse_list_section(body, UB_STEPS_FIELD), parse_list_section(body, UB_RESOURCES_FIELD)


def parse_reflection(body: str) -> str:
    """Liest den Reflexionstext zwischen ``# Reflexion`` und der naechsten ``##``-Section."""
    return extract_section(body, UB_REFLECTION_HEADING, target_level=1, stop_at_level=2) or ""


def _list_lines(entries: Sequence[str]) -> list[str]:
    """Bereinigte Einträge; leere Liste → ein Platzhalter-Bullet (``- ``), die Überschrift bleibt."""
    cleaned = [item.strip() for item in entries if item and item.strip()]
    return cleaned or [""]


def new_ub_body(reflection: str = "", steps: Sequence[str] = (), resources: Sequence[str] = ()) -> str:
    """Body einer neuen UB-Datei (Vorlage mit Reflexion und beiden Listen)."""
    parts = [
        f"# {UB_REFLECTION_HEADING}",
        "",
        str(reflection or "").strip(),
        "",
        render_markdown_bullet_section(UB_STEPS_FIELD, _list_lines(steps)),
        "",
        render_markdown_bullet_section(UB_RESOURCES_FIELD, _list_lines(resources)),
    ]
    return "\n".join(parts).strip() + "\n"


def with_development_lists(body: str, steps: Sequence[str], resources: Sequence[str]) -> str:
    """*body* mit ersetzten Listen-Abschnitten; alles andere bleibt wörtlich (fehlende werden angehängt)."""
    for title, entries in ((UB_STEPS_FIELD, steps), (UB_RESOURCES_FIELD, resources)):
        body = replace_section(body, title, markdown_bullet_lines(_list_lines(entries)), level=2)
    return body.rstrip("\n") + "\n"


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
