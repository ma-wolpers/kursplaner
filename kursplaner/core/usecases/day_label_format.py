"""Kurzes Tageslabel ``Mi 18.02.`` – einzige Stelle dieser Darstellungsregel.

Genutzt vom Grid-Spaltenkopf und von den Sprossen der Sequenzleiter, damit beide
denselben Termin identisch beschriften. Darstellungsregel, keine Fachregel,
deshalb in der Anwendungsschicht (vgl. §36).
"""

from __future__ import annotations

from datetime import datetime

from kursplaner.core.domain.course_rhythm import weekday_token

_ACCEPTED_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y")


def short_day_label(raw_date: str) -> str:
    """Formatiert einen Datumswert als ``Mi 18.02.``; nicht parsebare Werte bleiben unverändert.

    Args:
        raw_date: Roher Datumswert, z. B. der ``Datum``-Zellwert ``"18-02-26"``.

    Returns:
        Das Kurzlabel, den unveränderten (getrimmten) Text oder ``""`` für leere Eingaben.

    Example::

        short_day_label("18-02-26")  # -> "Mi 18.02."
    """
    text = str(raw_date).strip()
    if not text:
        return ""
    for fmt in _ACCEPTED_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return f"{weekday_token(parsed.weekday())} {parsed.day:02d}.{parsed.month:02d}."
    return text
