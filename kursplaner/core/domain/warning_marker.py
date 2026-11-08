"""Warnzeichen „⚠“ – einzige Quelle für Warnmarkierungen in Texten.

Markiert Einträge, die nicht vollständig geladen oder ungültig sind (Kursliste,
Oberthema, Spaltenkopf mit unaufgelöstem Link) und jede Zeile des Warnbanners.
"""

from __future__ import annotations

WARNING_GLYPH = "⚠"


def warning_text(text: str) -> str:
    """Text mit vorangestelltem Warnzeichen (``"⚠ text"``)."""
    return f"{WARNING_GLYPH} {text}"
