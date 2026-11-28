"""Body einer UB-Datei: einzige Stelle für seine Struktur (lesen, Vorlage).

Aufbau::

    # Reflexion

    <Freitext>

Die Entwicklungslisten (``Baustellen``/``Ressourcen``) stehen im Frontmatter
(`unterrichtsbesuch_policy.ub_development_lists`), nicht im Body. Schreibende Use
Cases reichen den bestehenden Body wörtlich durch – Text, den die Nutzerin
zusätzlich in die UB-Datei geschrieben hat, geht so nie verloren.
"""

from __future__ import annotations

from kursplaner.core.domain.markdown_sections import extract_section
from kursplaner.core.domain.unterrichtsbesuch_policy import UB_REFLECTION_HEADING


def parse_reflection(body: str) -> str:
    """Liest den Reflexionstext zwischen ``# Reflexion`` und der naechsten ``##``-Section."""
    return extract_section(body, UB_REFLECTION_HEADING, target_level=1, stop_at_level=2) or ""


def new_ub_body(reflection: str = "") -> str:
    """Body einer neuen UB-Datei (Vorlage mit Reflexion).

    Args:
        reflection: Optionaler Anfangstext der Reflexion.

    Returns:
        Body mit ``# Reflexion``-Überschrift und abschließendem Zeilenumbruch.
    """
    return f"# {UB_REFLECTION_HEADING}\n\n{str(reflection or '').strip()}".strip() + "\n"
