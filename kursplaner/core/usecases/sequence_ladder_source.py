"""Lesequelle der Sequenzleiter: Einheiten und Ablage frisch lesen, Leiter zusammensetzen (§37).

Einzige Lesestelle für Laden und Bearbeiten, damit beide dieselbe Leiter aus
denselben Speicherorten sehen (`sequence_ladder_homes`). Einheiten werden bei
jedem Aufruf über das Lesson-Repository gelesen (dessen Cache prüft die
Datei-Signatur), nie aus den Tagesspalten des Hauptfensters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.sequence_ladder import SequenceLadder
from kursplaner.core.domain.sequence_ladder_homes import (
    IDEEN_HEADING,
    LadderHomes,
    UnitContent,
    compose_ladder,
    ladder_homes,
    unit_content_from_yaml,
)
from kursplaner.core.ports.repositories import LessonRepository, SequencePlanRepository


@dataclass(frozen=True)
class LadderSnapshot:
    """Alles, was beim Lesen einer Leiter entsteht.

    Attributes:
        homes: Speicherort je Sprosse.
        units: Gelesener Inhalt je lesbarer Unterrichts-Einheit.
        ablage: Ablage der Sequenzdatei.
        ladder: Zusammengesetzte Leiter (mit gesperrten Sprossen).
        notes: Hinweise (gesperrte, nicht lesbare oder gekürzte Sprossen).
    """

    homes: LadderHomes
    units: Mapping[Path, UnitContent]
    ablage: SequenceLadder
    ladder: SequenceLadder
    notes: tuple[str, ...]


class SequenceLadderSource:
    """Liest Einheiten und Ablage einer Sequenz und setzt die Leiter zusammen."""

    def __init__(self, sequence_plan_repo: SequencePlanRepository, lesson_repo: LessonRepository) -> None:
        """Initialisiert die Quelle mit Sequenzdatei- und Einheiten-Repository."""
        self._sequences = sequence_plan_repo
        self._lessons = lesson_repo

    def read_unit(self, lesson_path: Path) -> UnitContent:
        """Leiter-relevanter Inhalt einer Einheit (Frontmatter und ``## Ideen``).

        Raises:
            OSError, RuntimeError, TypeError, ValueError: Die Einheit ist nicht lesbar.
        """
        data = self._lessons.load_lesson_yaml(lesson_path).data
        return unit_content_from_yaml(data, self._lessons.read_lesson_section(lesson_path, IDEEN_HEADING))

    def read(self, sequence_path: Path, term_days: Sequence[DayColumn]) -> LadderSnapshot:
        """Liest alles frisch und setzt die Leiter zusammen.

        Nicht lesbare Einheiten fehlen in ``units``; ihre Sprosse ist gesperrt.

        Raises:
            LadderFormatError: Die Ablage der Sequenzdatei ist nicht im Format.
            OSError: Die Sequenzdatei ist nicht lesbar.
        """
        homes = ladder_homes(term_days)
        units: dict[Path, UnitContent] = {}
        for path in homes.unit_paths:
            try:
                units[path] = self.read_unit(path)
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
        ablage = self._sequences.read_ladder_ablage(sequence_path)
        composed = compose_ladder(homes, units, ablage)
        return LadderSnapshot(homes, units, ablage, composed.ladder, composed.notes)
