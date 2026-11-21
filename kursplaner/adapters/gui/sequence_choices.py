"""Sequenzen des geöffneten Kurses als Auswahl – eine Quelle für Dialog und Leiter-Auswahlliste.

Je Sequenz gibt es genau eine `TopicSequencePlanView` (alle Läufe, geteilte LZKs);
hier wird sie mit Name, Anzahl der Einheiten und Zeitspanne beschrieben und über
Sequenzdatei bzw. markierte Zeilen gefunden.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn, days_by_row
from kursplaner.core.domain.topic_sequence_runs import find_sequence_for_row_index
from kursplaner.core.usecases.day_label_format import short_day_label
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView


@dataclass(frozen=True)
class SequenceChoice:
    """Eine wählbare Sequenz.

    Attributes:
        path: Sequenzdatei (Identität).
        title: Oberthema.
        detail: „N Einheiten · Datum – Datum“.
    """

    path: Path
    title: str
    detail: str

    @property
    def label(self) -> str:
        """Einzeilige Anzeige (Auswahlliste der Leiter)."""
        return f"{self.title} ({self.detail})"


def view_for_path(plans: Iterable[TopicSequencePlanView], path: Path) -> TopicSequencePlanView | None:
    """Die (eine) Sequenz-Ansicht zur Sequenzdatei *path*."""
    return next((view for view in plans if view.sequence_path == path), None)


def view_for_rows(plans: Sequence[TopicSequencePlanView], rows: Iterable[int]) -> TopicSequencePlanView | None:
    """Sequenz der ersten Zeile aus *rows*, die zu einer gehört (Regel `find_sequence_for_row_index`)."""
    by_sequence = {view.sequence: view for view in plans}
    for row in sorted(rows):
        sequence = find_sequence_for_row_index(list(by_sequence), row)
        if sequence is not None:
            return by_sequence[sequence]
    return None


def sequence_choices(plans: Iterable[TopicSequencePlanView], day_columns: Sequence[DayColumn]) -> list[SequenceChoice]:
    """Alle Sequenzen des Kurses als Auswahl (leer ohne Sequenz)."""
    by_row = days_by_row(day_columns)
    choices: list[SequenceChoice] = []
    for view in plans:
        members = view.sequence.member_row_indices  # alle Läufe und geteilten LZKs
        dates = [short_day_label(by_row[row].datum) for row in (members[0], members[-1]) if row in by_row]
        span = f" · {dates[0]} – {dates[-1]}" if dates else ""
        choices.append(SequenceChoice(view.sequence_path, view.oberthema, f"{len(members)} Einheiten{span}"))
    return choices
