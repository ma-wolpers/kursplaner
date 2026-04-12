from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link


@dataclass(frozen=True)
class ExpectedHorizonLine:
    """Eine einzelne Zeile im Kompetenzhorizont-Export."""

    datum: str
    ich_kann: str
    is_main_goal: bool


@dataclass(frozen=True)
class ExpectedHorizonDocument:
    """Vollständige Renderdaten für den Kompetenzhorizont."""

    title: str
    subtitle: str
    export_date_text: str
    rows: tuple[ExpectedHorizonLine, ...]


@dataclass(frozen=True)
class ExportExpectedHorizonResult:
    """Rückgabe des Use Cases mit Zielpfad, Titel und Anzahl exportierter Zeilen."""

    output_path: Path
    title: str
    row_count: int


class ExpectedHorizonRendererPort(Protocol):
    """Port zum Rendern des Kompetenzhorizonts in ein Zielformat."""

    def render(self, document: ExpectedHorizonDocument, output_path: Path) -> None:
        """Schreibt das Dokument an den angegebenen Zielpfad."""


class ExportExpectedHorizonUseCase:
    """Exportiert die aktuelle Sequenz als Kompetenzhorizont (nur Unterrichtseinheiten)."""

    _SELECTION_ALLOWED_TYPES = {"Unterricht", "LZK"}
    _EXPORT_ALLOWED_TYPES = {"Unterricht"}
    _COMPETENCY_PREFIX_RE = re.compile(r"^[A-Za-zÄÖÜäöü]{1,8}\s+\d+(?:\.\d+)*(?:\s*[-:–)]\s*|\s+)?")

    def __init__(self, renderer: ExpectedHorizonRendererPort):
        self._renderer = renderer

    @staticmethod
    def _parse_day_date(raw_value: object) -> date | None:
        text = str(raw_value or "").strip()
        if not text:
            return None
        for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None

    @classmethod
    def _format_day_date(cls, raw_value: object) -> str:
        parsed = cls._parse_day_date(raw_value)
        if parsed is None:
            return str(raw_value or "").strip()
        return parsed.strftime("%d.%m.%y")

    @staticmethod
    def _extract_term_token(table: PlanTableData) -> str:
        candidates = [table.markdown_path.parent.name, table.markdown_path.stem]
        for candidate in candidates:
            parts = str(candidate).strip().split()
            if not parts:
                continue
            token = parts[-1].strip()
            if len(token) == 4 and token[2] == "-" and token[:2].isdigit() and token[3] in {"1", "2"}:
                return token
        raise RuntimeError("Halbjahr konnte aus dem Kursnamen nicht bestimmt werden (erwartet z. B. '25-2').")

    @staticmethod
    def _schoolyear_from_term(term_token: str) -> str:
        year_short = int(term_token[:2])
        start_year = 2000 + year_short
        end_year_short = (year_short + 1) % 100
        return f"{start_year}/{end_year_short:02d}"

    @classmethod
    def _row_type(cls, day: dict[str, object]) -> str:
        yaml_data = day.get("yaml")
        if isinstance(yaml_data, dict):
            lesson_type = str(yaml_data.get("Stundentyp", "")).strip()
            if lesson_type:
                return lesson_type
        return str(day.get("Stundentyp", "")).strip()

    @staticmethod
    def _row_oberthema(day: dict[str, object]) -> str:
        yaml_data = day.get("yaml")
        if not isinstance(yaml_data, dict):
            return ""
        return str(yaml_data.get("Oberthema", "")).strip()

    @staticmethod
    def _parse_text_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        if not text:
            return []
        normalized = text.replace("\r\n", "\n").replace("|", "\n")
        parts = [part.strip() for part in normalized.split("\n")]
        return [part for part in parts if part]

    @classmethod
    def _strip_competency_prefix(cls, text: str) -> str:
        return cls._COMPETENCY_PREFIX_RE.sub("", str(text or "").strip()).strip()

    @classmethod
    def _goals_for_day(cls, yaml_data: dict[str, object]) -> list[str]:
        goals: list[str] = []
        lesson_goal = cls._strip_competency_prefix(str(yaml_data.get("Stundenziel", "")).strip())
        if lesson_goal:
            goals.append(lesson_goal)
        goals.extend(
            cls._strip_competency_prefix(item) for item in cls._parse_text_list(yaml_data.get("Teilziele", []))
        )
        goals = [goal for goal in goals if goal]
        if not goals:
            goals.append("")
        return [f"... {goal}" if goal else "..." for goal in goals]

    @classmethod
    def _export_rows_for_oberthema(
        cls,
        *,
        day_columns: list[dict[str, object]],
        target_oberthema: str,
    ) -> list[ExpectedHorizonLine]:
        rows: list[ExpectedHorizonLine] = []
        for day in day_columns:
            if cls._row_type(day) not in cls._EXPORT_ALLOWED_TYPES:
                continue

            yaml_data = day.get("yaml")
            if not isinstance(yaml_data, dict):
                continue

            if str(yaml_data.get("Oberthema", "")).strip() != target_oberthema:
                continue

            formatted_date = cls._format_day_date(day.get("datum", ""))
            goals = cls._goals_for_day(yaml_data)
            for index, goal in enumerate(goals):
                rows.append(
                    ExpectedHorizonLine(
                        datum=formatted_date if index == 0 else "",
                        ich_kann=goal,
                        is_main_goal=(index == 0),
                    )
                )

        return rows

    def execute(
        self,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
        selected_day_index: int,
        output_path: Path,
        export_date: date,
    ) -> ExportExpectedHorizonResult:
        if selected_day_index < 0 or selected_day_index >= len(day_columns):
            raise RuntimeError("Es ist keine gültige Einheit ausgewählt.")

        selected_day = day_columns[selected_day_index]
        selected_type = self._row_type(selected_day)
        if selected_type not in self._SELECTION_ALLOWED_TYPES:
            raise RuntimeError("Der Export ist nur für Unterrichts- oder LZK-Einheiten verfügbar.")

        target_oberthema = self._row_oberthema(selected_day)
        if not target_oberthema:
            raise RuntimeError("Die ausgewählte Einheit hat kein Oberthema.")

        rows = self._export_rows_for_oberthema(day_columns=day_columns, target_oberthema=target_oberthema)
        if not rows:
            raise RuntimeError("Keine Unterrichtseinheiten für das ausgewählte Oberthema gefunden.")

        term_token = self._extract_term_token(table)
        halfyear = term_token[-1]
        schoolyear = self._schoolyear_from_term(term_token)

        subject = str(table.metadata.get("Kursfach", "")).strip() or "Fach"
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", ""))).strip() or "Lerngruppe"
        title = f"Kompetenzhorizont: {target_oberthema}"
        subtitle = f"{subject} {group} {schoolyear} Hj. {halfyear}"

        document = ExpectedHorizonDocument(
            title=title,
            subtitle=subtitle,
            export_date_text=export_date.strftime("%d.%m.%Y"),
            rows=tuple(rows),
        )

        self._renderer.render(document, output_path)
        return ExportExpectedHorizonResult(output_path=output_path, title=title, row_count=len(rows))
