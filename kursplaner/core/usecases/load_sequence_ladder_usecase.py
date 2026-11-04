"""Use Case: Sequenzleiter einer Sequenzdatei samt Sprossen-Terminen laden.

Sprossen sind Positionen; ihre Beschriftung kommt aus den Terminen der Sequenz:
pro Lauf alle Planzeilen vom ersten bis zum letzten Mitglied (Unterricht, LZK,
Hospitation und dazwischenliegende Ausfälle), vereinigt über alle Läufe, die
dieselbe Datei teilen. Zeilen fremder Themen zwischen zwei Läufen werden nie
Sprossen. Jenseits der Termine tragen Sprossen ``??``. Siehe §37.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.sequence_ladder import SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.ports.repositories import SequencePlanRepository
from kursplaner.core.usecases.day_label_format import short_day_label

UNKNOWN_DATE_LABEL = "??"
"""Beschriftung von Sprossen ohne zugeordneten Termin."""


class RungKind(str, Enum):
    """Art des Termins einer Sprosse (steuert die Markierung in der Leiter)."""

    UNTERRICHT = "unterricht"
    LZK = "lzk"
    HOSPITATION = "hospitation"
    AUSFALL = "ausfall"
    OFFEN = "offen"


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
        ladder: Gelesene Leiter; ``None`` bei Lesefehler (dann schreibgeschützt).
        rungs: Termin je angezeigter Sprosse (unten → oben), inkl. einer Reserve-Sprosse.
        error: Nutzerlesbarer Fehler (Formatfehler, Datei fehlt) oder ``None``.
    """

    sequence_path: Path
    oberthema: str
    ladder: SequenceLadder | None
    rungs: tuple[RungInfo, ...]
    error: str | None = None


def _kind(day: DayColumn) -> RungKind:
    if day.is_cancel():
        return RungKind.AUSFALL
    if day.is_lzk():
        return RungKind.LZK
    if day.is_hospitation():
        return RungKind.HOSPITATION
    return RungKind.UNTERRICHT


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
        RungInfo(short_day_label(days[i].datum), _kind(days[i]))
        if i < len(days)
        else RungInfo(UNKNOWN_DATE_LABEL, RungKind.OFFEN)
        for i in range(rung_count)
    )


class LoadSequenceLadderUseCase:
    """Liest die Leiter und berechnet die Sprossen-Termine."""

    def __init__(self, sequence_plan_repo: SequencePlanRepository) -> None:
        """Initialisiert den Use Case mit dem Sequenzdatei-Repository."""
        self._repo = sequence_plan_repo

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
        ladder: SequenceLadder | None
        error: str | None = None
        try:
            ladder = self._repo.read_sequence_ladder(sequence_path)
        except LadderFormatError as exc:
            ladder, error = None, f"{exc} – die Leiter ist schreibgeschützt, bis die Datei korrigiert ist."
        except OSError as exc:
            ladder, error = None, f"Sequenzdatei nicht lesbar: {exc}"
        days = sequence_term_days(day_columns, runs)
        count = max(len(days), len(ladder.rungs) if ladder is not None else 0) + 1
        return SequenceLadderView(sequence_path, oberthema, ladder, rung_infos(days, count), error)
