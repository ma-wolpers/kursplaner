from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link


@dataclass(frozen=True)
class TopicUnitExportRow:
    """Eine exportierte Tabellenzeile fuer den Oberthema-PDF-Report."""

    datum: str
    stunden: str
    thema: str
    stundenziel: str
    prozesskompetenzen: str


@dataclass(frozen=True)
class TopicUnitsPdfDocument:
    """Vollstaendige Renderdaten fuer den Oberthema-PDF-Export."""

    title: str
    subtitle: str
    export_date_text: str
    rows: tuple[TopicUnitExportRow, ...]


@dataclass(frozen=True)
class ExportTopicUnitsPdfResult:
    """Rueckgabe des Use Cases mit Zielpfad, Titel und Anzahl exportierter Zeilen."""

    output_path: Path
    title: str
    row_count: int


class TopicUnitsPdfRendererPort(Protocol):
    """Port zum Rendern eines fachlich vorbereiteten Oberthema-Exports als PDF."""

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        """Schreibt das PDF-Dokument an den angegebenen Zielpfad."""


class ExportTopicUnitsPdfUseCase:
    """Exportiert passende Unterrichts- und LZK-Einheiten eines Oberthemas in ein PDF."""

    _ALLOWED_TYPES = {"Unterricht", "LZK"}

    def __init__(self, renderer: TopicUnitsPdfRendererPort):
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
        return parsed.strftime("%d.%m.%Y")

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
    def _process_competencies_text(cls, value: object) -> str:
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return "; ".join(cleaned)
        return str(value or "").strip()

    @classmethod
    def _row_type(cls, day: dict[str, object]) -> str:
        yaml_data = day.get("yaml")
        if isinstance(yaml_data, dict):
            lesson_type = str(yaml_data.get("Stundentyp", "")).strip()
            if lesson_type:
                return lesson_type
        return str(day.get("Stundentyp", "")).strip()

    @classmethod
    def _row_oberthema(cls, day: dict[str, object]) -> str:
        yaml_data = day.get("yaml")
        if not isinstance(yaml_data, dict):
            return ""
        return str(yaml_data.get("Oberthema", "")).strip()

    @classmethod
    def _export_rows_for_oberthema(
        cls,
        *,
        day_columns: list[dict[str, object]],
        target_oberthema: str,
    ) -> list[TopicUnitExportRow]:
        rows: list[TopicUnitExportRow] = []
        for day in day_columns:
            lesson_type = cls._row_type(day)
            if lesson_type not in cls._ALLOWED_TYPES:
                continue

            yaml_data = day.get("yaml")
            if not isinstance(yaml_data, dict):
                continue

            obert = str(yaml_data.get("Oberthema", "")).strip()
            if obert != target_oberthema:
                continue

            rows.append(
                TopicUnitExportRow(
                    datum=cls._format_day_date(day.get("datum", "")),
                    stunden=str(day.get("stunden", "")).strip(),
                    thema=str(yaml_data.get("Stundenthema", "")).strip(),
                    stundenziel=str(yaml_data.get("Stundenziel", "")).strip(),
                    prozesskompetenzen=cls._process_competencies_text(yaml_data.get("Kompetenzen", [])),
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
    ) -> ExportTopicUnitsPdfResult:
        if selected_day_index < 0 or selected_day_index >= len(day_columns):
            raise RuntimeError("Es ist keine gueltige Einheit ausgewaehlt.")

        selected_day = day_columns[selected_day_index]
        selected_type = self._row_type(selected_day)
        if selected_type not in self._ALLOWED_TYPES:
            raise RuntimeError("Der Export ist nur fuer Unterrichts- oder LZK-Einheiten verfuegbar.")

        target_oberthema = self._row_oberthema(selected_day)
        if not target_oberthema:
            raise RuntimeError("Die ausgewaehlte Einheit hat kein Oberthema.")

        rows = self._export_rows_for_oberthema(day_columns=day_columns, target_oberthema=target_oberthema)
        if not rows:
            raise RuntimeError("Keine Einheiten fuer das ausgewaehlte Oberthema gefunden.")

        term_token = self._extract_term_token(table)
        halfyear = term_token[-1]
        schoolyear = self._schoolyear_from_term(term_token)

        subject = str(table.metadata.get("Kursfach", "")).strip() or "Fach"
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", ""))).strip() or "Lerngruppe"
        title = f"{subject} {group} {schoolyear} Hj. {halfyear}"
        subtitle = f'"{target_oberthema}"'

        document = TopicUnitsPdfDocument(
            title=title,
            subtitle=subtitle,
            export_date_text=export_date.strftime("%d.%m.%Y"),
            rows=tuple(rows),
        )

        self._renderer.render(document, output_path)
        return ExportTopicUnitsPdfResult(output_path=output_path, title=title, row_count=len(rows))
