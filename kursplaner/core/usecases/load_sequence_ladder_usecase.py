"""Use Case: Sequenzleiter einer Sequenz samt Sprossen-Terminen laden.

Die Leiter ist eine Sicht auf die Einheiten (`sequence_ladder_homes`): Sprossen
mit Termin zeigen Ziele, Kompetenzen und Ideen ihrer Einheit, Sprossen jenseits
der Termine die Ablage der Sequenzdatei. Die Termine kommen aus der Sequenz:
pro Lauf alle Planzeilen vom ersten bis zum letzten Mitglied (Unterricht, LZK,
Hospitation und dazwischenliegende Ausfälle), vereinigt über alle Läufe, die
dieselbe Datei teilen. Zeilen fremder Themen zwischen zwei Läufen werden nie
Sprossen. Jenseits der Termine tragen Sprossen ``??``. Siehe §37.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.sequence_ladder import BlockRef, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_homes import RungKind, rung_kind
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.day_label_format import short_day_label
from kursplaner.core.usecases.sequence_ladder_source import SequenceLadderSource

UNKNOWN_DATE_LABEL = "??"
"""Beschriftung von Sprossen ohne zugeordneten Termin."""

__all__ = [
    "UNKNOWN_DATE_LABEL",
    "LoadSequenceLadderUseCase",
    "RungInfo",
    "RungKind",
    "SequenceLadderView",
    "rung_infos",
    "sequence_term_days",
]


@dataclass(frozen=True)
class RungInfo:
    """Termin einer Sprosse: Kurzdatum (oder ``??``) und Terminart."""

    date_label: str
    kind: RungKind


@dataclass(frozen=True)
class SequenceLadderView:
    """Alles, was der Leiter-Editor anzeigt.

    Attributes:
        sequence_path: Sequenzdatei (Identität der Sequenz).
        oberthema: Name der Sequenz.
        ladder: Zusammengesetzte Leiter; ``None`` bei Lesefehler (dann schreibgeschützt).
        rungs: Termin je angezeigter Sprosse (unten → oben), inkl. einer Reserve-Sprosse.
        error: Nutzerlesbarer Fehler (Formatfehler, Datei fehlt) oder ``None``.
        notes: Hinweise zu einzelnen Sprossen (gesperrt, nicht lesbar, gekürzt).
        duplicates: Gruppen von Bausteinen, die schon vor der Eindeutigkeitsregel doppelt standen.
    """

    sequence_path: Path
    oberthema: str
    ladder: SequenceLadder | None
    rungs: tuple[RungInfo, ...]
    error: str | None = None
    notes: tuple[str, ...] = ()
    duplicates: tuple[tuple[BlockRef, ...], ...] = ()


def sequence_term_days(day_columns: Sequence[DayColumn], runs: Sequence[TopicSequenceRun]) -> list[DayColumn]:
    """Termine der Sequenz chronologisch: Mitglieder und Ausfälle innerhalb jedes Laufs.

    Args:
        day_columns: Alle Tagesspalten des Plans (unprojiziert, `raw_day_columns`).
        runs: Alle Läufe, die dieselbe Sequenzdatei teilen.
    """
    by_row = {day.row_index: day for day in day_columns}
    rows: set[int] = set()
    for run in runs:
        if not run.member_row_indices:
            continue
        members = set(run.member_row_indices)
        first, last = min(members), max(members)
        rows.update(
            index
            for index in range(first, last + 1)
            if index in by_row and (index in members or by_row[index].is_cancel())
        )
    return [by_row[index] for index in sorted(rows)]


def rung_infos(days: Sequence[DayColumn], rung_count: int) -> tuple[RungInfo, ...]:
    """Termin je Sprosse (Index 0 = unten); ohne Termin ``??``/`OFFEN`."""
    return tuple(
        RungInfo(short_day_label(days[i].datum), rung_kind(days[i]))
        if i < len(days)
        else RungInfo(UNKNOWN_DATE_LABEL, RungKind.OFFEN)
        for i in range(rung_count)
    )


class LoadSequenceLadderUseCase:
    """Liest die Leiter aus Einheiten und Ablage und berechnet die Sprossen-Termine."""

    def __init__(self, source: SequenceLadderSource) -> None:
        """Initialisiert den Use Case mit der gemeinsamen Lesequelle."""
        self._source = source

    def execute(
        self,
        *,
        sequence_path: Path,
        oberthema: str,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
    ) -> SequenceLadderView:
        """Lädt die Leiter; ein Lesefehler liefert eine schreibgeschützte Ansicht mit Fehlertext.

        Args:
            sequence_path: Sequenzdatei.
            oberthema: Anzeigename der Sequenz.
            runs: Alle Läufe mit diesem Pfad (leer, wenn die Sequenz im Kurs nicht mehr vorkommt).
            day_columns: Alle Tagesspalten des geöffneten Plans.
        """
        days = sequence_term_days(day_columns, runs)
        try:
            snapshot = self._source.read(sequence_path, days)
        except LadderFormatError as exc:
            error = f"{exc} – die Leiter ist schreibgeschützt, bis die Datei korrigiert ist."
            return SequenceLadderView(sequence_path, oberthema, None, rung_infos(days, len(days) + 1), error)
        except OSError as exc:
            error = f"Sequenzdatei nicht lesbar: {exc}"
            return SequenceLadderView(sequence_path, oberthema, None, rung_infos(days, len(days) + 1), error)
        ladder = snapshot.ladder
        count = max(len(days), len(ladder.rungs)) + 1
        return SequenceLadderView(
            sequence_path,
            oberthema,
            ladder,
            rung_infos(days, count),
            notes=snapshot.notes,
            duplicates=ladder.duplicate_groups(),
        )
