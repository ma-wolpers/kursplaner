"""Bringt das YAML-Feld ``Oberthema`` der Stunden-Dateien eines Kurses in die typabhängige kanonische Form.

Läuft beim Kursladen (im selben Hook wie das KH-Link-Cleanup):

* **LZK** → kanonische Liste aus Wiki-Links (ein Legacy-Skalar wird zur Liste),
* **Unterricht/Hospitation** → Einzelwert wie gespeichert. Eine Liste mit genau
  einem Eintrag wird zum Einzelwert zurückgeführt (Korrektur einer früheren,
  zu weit gefassten Listen-Migration); ein Einzelwert bleibt unangetastet.

Jede verlinkte Datei landet in genau einer Gruppe: bereits kanonisch (nichts
wird geschrieben), unterstützt aber nicht kanonisch (wird geschrieben) oder
**Problem** — nicht unterstützter Typ bzw. mehrere Themen bei einer Nicht-LZK;
die Datei bleibt dann unverändert und wird als Ladehinweis gemeldet.

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
    distinct_raw_entries,
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
        migrated_files: Dateien, deren Oberthema in die kanonische Form überführt wurde.
        problems: Unverändert gelassene Dateien mit Begründung (Ladehinweis).
    """

    migrated_files: tuple[Path, ...]
    problems: tuple[OberthemaProblem, ...]


class MigrateOberthemaListUseCase:
    """Überführt ``Oberthema`` aller verlinkten Stunden-Dateien eines Kurses in die typabhängige Form."""

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

    @staticmethod
    def _target_value(raw_value: object, stundentyp: str, group_name: str) -> list[str] | str | None:
        """Kanonischer Zielwert je Stundentyp; ``None`` bei mehreren Themen einer Nicht-LZK.

        Raises:
            UnsupportedOberthemaValue: Bei nicht unterstütztem Typ.
        """
        if stundentyp == "LZK":
            return canonical_oberthema_value(raw_value, group_name)
        entries = distinct_raw_entries(raw_value)
        if len(entries) > 1:
            return None
        return entries[0] if entries else ""

    @staticmethod
    def _is_unchanged(raw_value: object, target: list[str] | str) -> bool:
        """Vergleicht Platten- und Zielwert; ein leerer Einzelwert liest der Parser als ``[]``."""
        if target == "" and raw_value in ("", []):
            return True
        return raw_value == target

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
                target = self._target_value(raw_value, stundentyp, group_name)
            except UnsupportedOberthemaValue:
                problems.append(OberthemaProblem(path, self._REASON_UNSUPPORTED))
                continue
            if target is None:
                problems.append(OberthemaProblem(path, self._REASON_MULTI_TOPIC))
                continue
            if self._is_unchanged(raw_value, target):
                continue

            lesson = self._lesson_repo.load_lesson_yaml(path)
            lesson.data[OBERTHEMA_KEY] = target
            self._lesson_repo.save_lesson_yaml(lesson)
            migrated.append(path)

        return MigrateOberthemaListResult(migrated_files=tuple(migrated), problems=tuple(problems))
