"""Minimales Ledger-Schema fuer schulweite Ausfaelle.

Ein Eintrag (`SchoolWideCancellationEntry`) beschreibt einen deklarativen
Ausfall (Grund, Zeitraum, betroffene Jahrgangsstufen) plus, je betroffenem
Kurs, ein `CourseApplicationLedger` mit den tatsaechlich verschobenen
Einheiten (`UnitMove`). Identitaet einer verschobenen Einheit ist Datum +
Position innerhalb des Datums + Markdown-Referenz (siehe `RowLocation`/
`UnitReference`) - bewusst KEIN Content-Snapshot und KEINE positionale
"letzte N Zeilen"-Zaehlung. Der Inhalt der referenzierten Datei ist nicht
Teil der Identitaet: aendert er sich, bleibt die Zuordnung gueltig (siehe
`core.domain.row_identity` fuer die Aufloesung gegen die aktuelle Tabelle).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Sequence


@dataclass(frozen=True)
class UnitReference:
    """Wiedererkennungsmerkmal einer verschobenen Einheit (nicht ihr Inhalt)."""

    kind: Literal["link", "raw_text"]
    value: str


@dataclass(frozen=True)
class RowLocation:
    """Position einer Planzeile: Datum plus Position unter gleich-datierten Zeilen.

    `position_in_date` ist nur bedeutsam, wenn `date` gesetzt ist (mehrere
    Zeilen mit exakt demselben Datum sind ein seltener, aber moeglicher Fall
    bei manueller Bearbeitung). `date=None` steht fuer eine datumslose Zeile.
    """

    date: str | None
    position_in_date: int = 0


@dataclass(frozen=True)
class UnitMove:
    """Eine stornierte, ggf. verschobene Einheit innerhalb eines Kurses.

    `reference`/`target` sind `None`, wenn die stornierte Zeile keinen Inhalt
    trug - dann gibt es nichts zu verschieben, Revert muss nur die
    Ausfall-Markierung an `source` wieder entfernen.
    """

    source: RowLocation
    reference: UnitReference | None
    target: RowLocation | None


@dataclass(frozen=True)
class CourseApplicationLedger:
    """Alle von einem Entry in einem Kurs vorgenommenen Verschiebungen."""

    moves: tuple[UnitMove, ...] = ()

    def cancelled_dates(self) -> frozenset[str]:
        """Liefert alle Daten, die dieser Ledger als Ausfall beansprucht."""
        return frozenset(move.source.date for move in self.moves if move.source.date is not None)


@dataclass(frozen=True)
class SchoolWideCancellationEntry:
    """Ein schulweiter Ausfall-Eintrag: Grund, Zeitraum, Stufen, pro-Kurs-Ledger."""

    entry_id: str
    reason: str
    date_from: date
    date_to: date
    grade_levels: frozenset[int]
    created_at: str
    course_ledgers: dict[str, CourseApplicationLedger] = field(default_factory=dict)


def format_ledger_date(value: date) -> str:
    """Formatiert ein Datum im kanonischen Plan-Zeilenformat (`DD-MM-YY`)."""
    return value.strftime("%d-%m-%y")


def find_claiming_entry(
    entries: Sequence[SchoolWideCancellationEntry],
    *,
    course_key: str,
    target_date: date,
    exclude_entry_id: str | None = None,
) -> SchoolWideCancellationEntry | None:
    """Liefert den aktiven Entry, der `(course_key, target_date)` bereits beansprucht.

    Exklusivitaets-Invariante: ein `(Kurs, Datum)` darf zu jedem Zeitpunkt von
    hoechstens einem aktiven Entry als Ausfall beansprucht sein. Wird von
    Preview (fruehestmoegliche Sichtbarkeit) und Apply genutzt, um Kollisionen
    zwischen unabhaengigen Entries zu erkennen, statt eine kuenstliche
    Reihenfolgepflicht zwischen ihnen einzufuehren.
    """
    target_text = format_ledger_date(target_date)
    for entry in entries:
        if entry.entry_id == exclude_entry_id:
            continue
        ledger = entry.course_ledgers.get(course_key)
        if ledger is None:
            continue
        if target_text in ledger.cancelled_dates():
            return entry
    return None


def course_key_for_path(markdown_path: Path) -> str:
    """Kanonischer String-Schluessel eines Kurses fuer `course_ledgers` (Dict-Key, JSON-tauglich)."""
    return str(markdown_path)
