"""Spalten-IDs der Kursübersicht (``lesson_tree``).

Einzige Quelle für Reihenfolge und Namen der Übersichtsspalten. Aufbau,
Befüllen und Aktualisieren der Zeilen beziehen sich darauf, damit eine neue
Spalte nicht stillschweigend Werte in Nachbarspalten verschiebt.
"""

from __future__ import annotations

OVERVIEW_COLUMNS: tuple[str, ...] = (
    "name",
    "stufe",
    "next_topic",
    "next_unit",
    "remaining_hours",
    "next_lzk",
    "next_ub",
)


def overview_row_values(row: dict[str, str]) -> tuple[str, ...]:
    """Ordnet benannte Zellwerte in Spaltenreihenfolge an.

    Unbekannte oder fehlende Schlüssel sind ein Programmierfehler und
    schlagen sofort fehl, statt eine verschobene Zeile zu erzeugen.
    """
    unknown = set(row) - set(OVERVIEW_COLUMNS)
    missing = set(OVERVIEW_COLUMNS) - set(row)
    if unknown or missing:
        raise ValueError(
            f"Übersichtszeile passt nicht zu den Spalten: fehlend={sorted(missing)}, unbekannt={sorted(unknown)}"
        )
    return tuple(row[column_id] for column_id in OVERVIEW_COLUMNS)
