"""Migriert das YAML-Feld ``Oberthema`` der Stunden-Dateien eines Kurses auf die kanonische Liste.

Läuft beim Kursladen (im selben Hook wie das KH-Link-Cleanup). Jede verlinkte
Stunden-Datei landet in genau einer Gruppe:

* **bereits kanonisch** → nichts wird geschrieben,
* **unterstützt, aber nicht kanonisch** (Legacy-Skalar, Klartext-Einträge,
  Duplikate, leere Einträge) → der Wert wird als kanonische Liste geschrieben,
* **Problem** → die Datei bleibt unverändert und wird gemeldet:
  nicht unterstützter Typ (z. B. verschachtelter Block) oder eine Nicht-LZK
  mit mehreren Themen (Invariante verletzt, keine stille Kürzung).

Der Vergleich läuft gegen den *rohen* Plattenwert
(`LessonRepository.load_raw_lesson_frontmatter`), da `load_lesson_yaml`
bereits beim Laden kanonisiert.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.lesson_yaml_policy import allowed_keys_for_type, infer_stundentyp
from kursplaner.core.domain.oberthema_values import (
    OBERTHEMA_KEY,
    UnsupportedOberthemaValue,
    canonical_oberthema_value,
)
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


@dataclass(frozen=True)
class OberthemaProblem:
    """Eine Stunden-Datei, deren ``Oberthema`` nicht automatisch migriert werden darf.

    Args:
        lesson_path: Betroffene Datei.
        reason: Verständliche Begründung für den Ladehinweis.
    """

    lesson_path: Path
    reason: str


@dataclass(frozen=True)
class MigrateOberthemaListResult:
    """Ergebnis eines Migrationslaufs.

    Args:
        migrated_files: Dateien, deren Oberthema in die kanonische Liste überführt wurde.
        problems: Unverändert gelassene Dateien mit Begründung (Ladehinweis).
    """

    migrated_files: tuple[Path, ...]
    problems: tuple[OberthemaProblem, ...]


class MigrateOberthemaListUseCase:
    """Überführt ``Oberthema`` aller verlinkten Stunden-Dateien eines Kurses in die Listenform."""

    _REASON_UNSUPPORTED = "Oberthema hat ein nicht unterstütztes Format"
    _REASON_MULTI_TOPIC = "mehrere Oberthemen, obwohl nur eine LZK mehrere tragen darf"

    def __init__(self, *, lesson_repo: LessonRepository) -> None:
        """Initialisiert den Use Case mit dem Lesson-Repository-Port."""
        self._lesson_repo = lesson_repo

    @staticmethod
    def _linked_paths(day_columns: list[DayColumn]) -> list[Path]:
        """Liefert die existierenden, verlinkten Stunden-Dateien ohne Duplikate in Planreihenfolge."""
        seen: set[Path] = set()
        paths: list[Path] = []
        for day in day_columns:
            link = day.link
            if not isinstance(link, Path) or not link.is_file():
                continue
            resolved = link.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(resolved)
        return paths

    def execute(self, *, table: PlanTableData, day_columns: list[DayColumn]) -> MigrateOberthemaListResult:
        """Migriert alle verlinkten Stunden-Dateien des Kurses.

        Args:
            table: Geladene Planungstabelle (liefert die Lerngruppe für die Wiki-Link-Form).
            day_columns: Vollständige, unprojizierte Tagesliste.

        Returns:
            Migrierte Dateien und gemeldete Problemdateien.
        """
        group_name = str(table.metadata.get("Lerngruppe", ""))
        migrated: list[Path] = []
        problems: list[OberthemaProblem] = []

        for path in self._linked_paths(day_columns):
            raw_data = self._lesson_repo.load_raw_lesson_frontmatter(path)
            if OBERTHEMA_KEY not in raw_data:
                continue
            stundentyp = infer_stundentyp(raw_data)
            if OBERTHEMA_KEY not in allowed_keys_for_type(stundentyp):
                continue

            raw_value = raw_data[OBERTHEMA_KEY]
            try:
                canonical = canonical_oberthema_value(raw_value, group_name)
            except UnsupportedOberthemaValue:
                problems.append(OberthemaProblem(path, self._REASON_UNSUPPORTED))
                continue
            if len(canonical) > 1 and stundentyp != "LZK":
                problems.append(OberthemaProblem(path, self._REASON_MULTI_TOPIC))
                continue
            if canonical == raw_value:
                continue

            lesson = self._lesson_repo.load_lesson_yaml(path)
            lesson.data[OBERTHEMA_KEY] = canonical
            self._lesson_repo.save_lesson_yaml(lesson)
            migrated.append(path)

        return MigrateOberthemaListResult(migrated_files=tuple(migrated), problems=tuple(problems))
