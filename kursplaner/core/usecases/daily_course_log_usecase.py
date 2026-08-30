from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from kursplaner.core.config.path_store import serialize_workspace_relative_path
from kursplaner.core.config.settings import SCRIPT_DIR
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import PlanTableData, parse_plan_row_date, read_yaml_oberthema
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository


@dataclass(frozen=True)
class DailyCourseLogResult:
    """Ergebnis eines Daily-Course-Log-Exports."""

    export_day: date
    log_path: Path
    created: bool
    course_count: int
    unit_count: int


class DailyCourseLogUseCase:
    """Erzeugt pro Kalendertag einen JSON-Snapshot aller aktuellen Kurse."""

    _LOG_FILENAME_PREFIX = "daily_courses_"
    _FIELDS: tuple[str, ...] = (
        "datum",
        "stunden",
        "inhalt",
        "Stundenthema",
        "Oberthema",
        "Stundenziel",
        "Kompetenzen",
        "Material",
        "Kompetenzhorizont",
        "Inhaltsübersicht",
        "Vertretungsmaterial",
        "Beobachtungsschwerpunkte",
        "Ressourcen",
        "Baustellen",
    )

    def __init__(self, plan_repo: PlanRepository, lesson_repo: LessonRepository):
        """Initialisiert den Use Case mit Port-basierten Repositories."""
        self.plan_repo = plan_repo
        self.lesson_repo = lesson_repo

    @staticmethod
    def _log_dir() -> Path:
        """Liefert den fixen Ablageordner der Daily-Log-Dateien."""
        return SCRIPT_DIR / "config" / "logs"

    @classmethod
    def _log_path_for_day(cls, day: date) -> Path:
        """Liefert den Log-Dateipfad für ein Tagesdatum."""
        return cls._log_dir() / f"{cls._LOG_FILENAME_PREFIX}{day.isoformat()}.json"

    @staticmethod
    def _normalize_value(value: object) -> str | list[str]:
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    result.append(text)
            return result
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _status_for_unit(day: DayColumn) -> str:
        """Klassifiziert den Status einer Einheit anhand der `DayColumn`-Ableitungen.

        Ferien tragen weiterhin den Status ``"ausfall"`` (kein eigener
        Statuswert, um das bestehende JSON-Format kompatibel zu halten);
        ihre Ferien-Eigenschaft steht separat im Feld ``is_ferien`` (siehe
        :meth:`_units_for_table`).
        """
        if day.is_cancel():
            return "ausfall"
        if day.is_hospitation():
            return "hospitation"
        if day.is_lzk():
            return "lzk"
        return day.stundentyp.lower()

    @classmethod
    def _cells_for_unit(cls, day: DayColumn) -> dict[str, str | list[str]]:
        yaml_data = day.yaml
        cells: dict[str, str | list[str]] = {
            "datum": day.datum.strip(),
            "stunden": str(day.stunden()),
            "inhalt": day.inhalt.strip(),
        }
        for field in cls._FIELDS:
            if field in {"datum", "stunden", "inhalt", "thema/ausfall"}:
                continue
            if field == "Oberthema":
                # Darf bewusst als Wiki-Link gespeichert sein (Obsidian-
                # Verlinkung); der Tageslog-Export soll den entschlüsselten
                # Anzeigetext tragen, siehe `plan_table.read_yaml_oberthema`.
                cells[field] = read_yaml_oberthema(yaml_data, day.group_name)
                continue
            cells[field] = cls._normalize_value(
                yaml_data.get(
                    field,
                    []
                    if field
                    in {"Kompetenzen", "Teilziele", "Material", "Vertretungsmaterial", "Ressourcen", "Baustellen"}
                    else "",
                )
            )
        return cells

    def _units_for_table(self, table: PlanTableData, export_day: date) -> list[dict[str, object]]:
        day_columns: list[DayColumn] = []
        try:
            from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase

            day_columns = LoadPlanDetailUseCase(self.plan_repo, self.lesson_repo).build_day_columns(table)
        except Exception:
            return []

        units: list[dict[str, object]] = []
        for day in day_columns:
            unit_day = parse_plan_row_date(day.datum)
            if unit_day is None or unit_day < export_day:
                continue

            hours = day.stunden()
            cells = self._cells_for_unit(day)
            hour_entries = [
                {
                    "hour_index": index,
                    "cells": dict(cells),
                }
                for index in range(1, hours + 1)
            ]

            link_path = day.link
            units.append(
                {
                    "row_index": day.row_index,
                    "status": self._status_for_unit(day),
                    "is_ferien": day.is_ferien(),
                    "cells": cells,
                    "link_path": (serialize_workspace_relative_path(link_path) if isinstance(link_path, Path) else ""),
                    "hour_entries": hour_entries,
                }
            )

        return units

    @staticmethod
    def _safe_relative(path: Path, base_dir: Path) -> str:
        try:
            return str(path.resolve().relative_to(base_dir.resolve()))
        except Exception:
            return str(path)

    def _build_payload(self, unterricht_dir: Path, export_day: date) -> tuple[dict[str, object], int, int]:
        courses: list[dict[str, object]] = []
        course_count = 0
        unit_count = 0

        tables = self.plan_repo.load_plan_tables(unterricht_dir)
        for table in tables:
            units = self._units_for_table(table, export_day)
            if not units:
                continue
            course_count += 1
            unit_count += len(units)
            courses.append(
                {
                    "plan_path": self._safe_relative(table.markdown_path, unterricht_dir),
                    "metadata": {key: str(value) for key, value in table.metadata.items() if isinstance(key, str)},
                    "units": units,
                }
            )

        payload: dict[str, object] = {
            "export_date": export_day.isoformat(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_unterricht_dir": serialize_workspace_relative_path(unterricht_dir),
            "courses": courses,
        }
        return payload, course_count, unit_count

    def export_for_day(self, unterricht_dir: Path, export_day: date | None = None) -> DailyCourseLogResult:
        """Schreibt das Tageslog für den gegebenen Unterrichtsordner."""
        day = export_day or date.today()
        log_path = self._log_path_for_day(day)
        if log_path.exists():
            return DailyCourseLogResult(
                export_day=day,
                log_path=log_path,
                created=False,
                course_count=0,
                unit_count=0,
            )

        payload, course_count, unit_count = self._build_payload(unterricht_dir=unterricht_dir, export_day=day)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(log_path, payload)

        return DailyCourseLogResult(
            export_day=day,
            log_path=log_path,
            created=True,
            course_count=course_count,
            unit_count=unit_count,
        )
