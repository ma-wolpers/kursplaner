from __future__ import annotations

import re

from kursplaner.core.domain.day_column import DayColumn


def day_column_matches_query(day: DayColumn, pattern: re.Pattern[str]) -> bool:
    """Prüft, ob eine Einheit (Tages-Spalte) den Suchausdruck der Strg+F-Suche enthält.

    Durchsucht `inhalt`, `thema_ausfall` (rohe Felder) sowie `header_content()`/
    `oberthema()` (fachlich abgeleitet, aber nachweislich rein/IO-frei --
    siehe `day_column.py`). `group_name` bleibt bewusst ausgeschlossen: es ist
    innerhalb eines Kurses konstant und daher für eine Einheitensuche nicht
    unterscheidend. Groß-/Kleinschreibung folgt der Standard-`re`-Semantik
    des übergebenen, bereits kompilierten Musters -- keine Sonderbehandlung.
    """
    return bool(
        pattern.search(day.inhalt)
        or pattern.search(day.thema_ausfall)
        or pattern.search(day.header_content())
        or pattern.search(day.oberthema())
    )
