"""Sequenzen des geöffneten Kurses als Auswahl – eine Quelle für Dialog und Leiter-Auswahlliste.

Gruppiert die Sequenz-Läufe nach Sequenzdatei (mehrere Läufe können eine Datei teilen)
und beschreibt jede Sequenz mit Name, Anzahl der Einheiten und Zeitspanne.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn, days_by_row
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


def views_by_path(plans: Iterable[TopicSequencePlanView]) -> dict[Path, list[TopicSequencePlanView]]:
    """Sequenz-Ansichten je Sequenzdatei, in Plan-Reihenfolge."""
    grouped: dict[Path, list[TopicSequencePlanView]] = {}
    for view in plans:
        grouped.setdefault(view.sequence_path, []).append(view)
    return grouped


def sequence_choices(plans: Iterable[TopicSequencePlanView], day_columns: Sequence[DayColumn]) -> list[SequenceChoice]:
    """Alle Sequenzen des Kurses als Auswahl (leer ohne Sequenz)."""
    by_row = days_by_row(day_columns)
    choices: list[SequenceChoice] = []
    for path, views in views_by_path(plans).items():
        members = sorted(row for view in views for row in view.run.member_row_indices)
        dates = [short_day_label(by_row[row].datum) for row in (members[0], members[-1]) if row in by_row]
        span = f" · {dates[0]} – {dates[-1]}" if dates else ""
        choices.append(SequenceChoice(path, views[0].run.oberthema, f"{len(members)} Einheiten{span}"))
    return choices
