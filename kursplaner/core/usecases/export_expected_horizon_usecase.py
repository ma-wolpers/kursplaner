from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol, Sequence

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.expected_horizon import ExpectedHorizonLine, ExpectedHorizonSection, GoalKind
from kursplaner.core.domain.expected_horizon_cutoff import HorizonCutoff
from kursplaner.core.domain.expected_horizon_files import default_adhoc_horizon_filename
from kursplaner.core.domain.expected_horizon_reconciliation import ReconciledHorizon, reconcile
from kursplaner.core.domain.oberthema_values import normalize_oberthemen
from kursplaner.core.domain.plan_table import PlanTableData, parse_plan_row_date
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.expected_horizon import ExistingExpectedHorizonReaderPort

__all__ = [
    "ExpectedHorizonDocument",
    "ExpectedHorizonLine",
    "ExpectedHorizonRendererPort",
    "ExpectedHorizonSection",
    "ExportExpectedHorizonResult",
    "ExportExpectedHorizonUseCase",
    "GoalKind",
]


@dataclass(frozen=True)
class ExpectedHorizonDocument:
    """Render-DTO des Kompetenzhorizonts (Titel, Untertitel, Exportdatum, Sections).

    Bewusst im Use-Case-Modul und mit bereits formatierten Texten
    (``export_date_text``, ``datum`` als ``TT.MM.JJ``) — konsistent mit den
    Schwester-DTOs `TopicUnitsDocument` und `AchievementsReportDocument`. Die
    fachliche Zielstruktur (Sections/Zeilen) liegt in
    `core.domain.expected_horizon`.
    """

    title: str
    subtitle: str
    export_date_text: str
    sections: tuple[ExpectedHorizonSection, ...]

    @property
    def rows(self) -> tuple[ExpectedHorizonLine, ...]:
        """Alle Zielzeilen über alle Sections hinweg in Ausgabereihenfolge."""
        return tuple(line for section in self.sections for line in section.rows)


@dataclass(frozen=True)
class ExportExpectedHorizonResult:
    """Rückgabe des Use Cases mit Zielpfad, Titel, Anzahl Zeilen und exportierten Themen."""

    output_path: Path
    title: str
    row_count: int
    oberthemen: tuple[str, ...] = ()


class ExpectedHorizonRendererPort(Protocol):
    """Port zum Rendern des Kompetenzhorizonts in ein Zielformat."""

    def render(
        self,
        document: ExpectedHorizonDocument,
        output_path: Path,
        *,
        reconciled: ReconciledHorizon | None = None,
    ) -> None:
        """Schreibt das Dokument an den angegebenen Zielpfad.

        Args:
            document: Render-DTO mit Sections.
            output_path: Zielpfad.
            reconciled: Mit einer bestehenden Datei abgeglichene Sections
                (übernommene Bewertungen); Formate ohne Bewertungsspalten (PDF)
                ignorieren sie.
        """


class ExportExpectedHorizonUseCase:
    """Exportiert den Kompetenzhorizont gewählter Oberthemen bis zum Stichtag (nur Unterrichtseinheiten)."""

    _EXPORT_ALLOWED_TYPES = {"Unterricht"}
    _COMPETENCY_PREFIX_RE = re.compile(r"^[A-Za-zÄÖÜäöü]{1,8}\s+\d+(?:\.\d+)*(?:\s*[-:–)]\s*|\s+)?")

    def __init__(
        self,
        renderer: ExpectedHorizonRendererPort,
        existing_reader: ExistingExpectedHorizonReaderPort | None = None,
    ):
        """Initialisiert den Export mit Renderer und optionalem Leser für die Merge-Quelle.

        Args:
            renderer: Zielformat-Renderer.
            existing_reader: Nur für Formate mit Bewertungsspalten (Markdown):
                liest eine bestehende KH-Datei, deren AFB/Aufg/Pkte übernommen werden.
        """
        self._renderer = renderer
        self._existing_reader = existing_reader

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
    def _goals_for_day(cls, yaml_data: dict[str, object]) -> list[tuple[str, GoalKind]]:
        goals: list[tuple[str, GoalKind]] = []
        lesson_goal = cls._strip_competency_prefix(str(yaml_data.get("Stundenziel", "")).strip())
        if lesson_goal:
            goals.append((lesson_goal, GoalKind.STUNDENZIEL))
        goals.extend(
            (cls._strip_competency_prefix(item), GoalKind.TEILZIEL)
            for item in cls._parse_text_list(yaml_data.get("Teilziele", []))
        )
        goals.extend(
            (cls._strip_competency_prefix(item), GoalKind.SONDERZIEL)
            for item in cls._parse_text_list(yaml_data.get("Sonderziele", []))
        )
        goals = [(text, kind) for text, kind in goals if text]
        if not goals:
            goals.append(("", GoalKind.STUNDENZIEL))
        return [(f"... {text}" if text else "...", kind) for text, kind in goals]

    @classmethod
    def _lines_for_day(cls, day: DayColumn) -> list[ExpectedHorizonLine]:
        """Zielzeilen einer Unterrichtsstunde (Datum nur in der ersten Zeile)."""
        formatted_date = cls._format_day_date(day.datum)
        return [
            ExpectedHorizonLine(datum=formatted_date if index == 0 else "", ich_kann=goal, kind=kind)
            for index, (goal, kind) in enumerate(cls._goals_for_day(day.yaml))
        ]

    @classmethod
    def _admitted_units(cls, raw_day_columns: list[DayColumn], cutoff: HorizonCutoff) -> list[DayColumn]:
        """Unterrichtsstunden, die der Stichtag zulässt (datumslose nie, ungültiges Oberthema nie)."""
        return [
            day
            for day in raw_day_columns
            if isinstance(day, DayColumn)
            and day.stundentyp in cls._EXPORT_ALLOWED_TYPES
            and cutoff.admits(parse_plan_row_date(day.datum))
            and not day.oberthema_state().is_invalid
        ]

    @classmethod
    def build_sections(
        cls,
        *,
        raw_day_columns: list[DayColumn],
        oberthemen: Sequence[str],
        cutoff: HorizonCutoff,
    ) -> tuple[ExpectedHorizonSection, ...]:
        """Baut je gewähltem Oberthema eine Section mit den zugelassenen Stunden.

        Die Auswahl wird duplikatfrei gemacht und **chronologisch nach erstem
        Auftreten** im zugelassenen Zeitraum sortiert (Planreihenfolge =
        chronologisch), unabhängig von der übergebenen Reihenfolge. Themen ohne
        zugelassene Stunde entfallen.

        Args:
            raw_day_columns: Vollständige, unprojizierte Tagesliste.
            oberthemen: Gewählte (entschlüsselte) Themen.
            cutoff: Stichtag des KH.
        """
        wanted = set(normalize_oberthemen(oberthemen, ""))
        lines_by_topic: dict[str, list[ExpectedHorizonLine]] = {}
        for day in cls._admitted_units(raw_day_columns, cutoff):
            for topic in day.oberthemen():
                if topic in wanted:
                    lines_by_topic.setdefault(topic, []).extend(cls._lines_for_day(day))
        return tuple(ExpectedHorizonSection(topic, tuple(lines)) for topic, lines in lines_by_topic.items())

    @staticmethod
    def default_adhoc_output_path(
        table: PlanTableData,
        *,
        topics: Sequence[str],
        cutoff: HorizonCutoff,
        now: datetime,
        extension: str,
    ) -> Path:
        """Default-Zielpfad eines Ad-hoc-KH ("Exportieren als…") im Kursordner.

        Nur ein Vorschlag für den Speichern-Dialog (siehe
        `expected_horizon_files.default_adhoc_horizon_filename`).
        """
        name = default_adhoc_horizon_filename(topics, cutoff_date=cutoff.day, created_at=now, extension=extension)
        return table.markdown_path.parent.resolve() / name

    def execute(
        self,
        *,
        table: PlanTableData,
        raw_day_columns: list[DayColumn],
        oberthemen: Sequence[str],
        cutoff: HorizonCutoff,
        output_path: Path,
        export_date: date,
        merge_source: Path | None = None,
    ) -> ExportExpectedHorizonResult:
        """Exportiert den Kompetenzhorizont der gewählten Oberthemen bis zum Stichtag.

        Args:
            table: Geladene Planungstabelle (Fach, Lerngruppe, Halbjahr).
            raw_day_columns: Vollständige, unprojizierte Tagesliste — ausgeblendete
                Spalten fehlen dadurch nicht im KH.
            oberthemen: Gewählte Themen (werden bereinigt und chronologisch sortiert).
            cutoff: Stichtag (`HorizonCutoff`).
            output_path: Zielpfad.
            export_date: Exportdatum.
            merge_source: Bestehende KH-Datei, deren Bewertungen übernommen werden
                (nur mit injiziertem Leser wirksam); ``None`` = kein Merge.

        Raises:
            RuntimeError: Bei leerer Auswahl oder wenn keine Stunden einfließen.
        """
        if not normalize_oberthemen(oberthemen, ""):
            raise RuntimeError("Es ist kein Oberthema ausgewählt.")
        sections = self.build_sections(raw_day_columns=raw_day_columns, oberthemen=oberthemen, cutoff=cutoff)
        if not sections:
            raise RuntimeError("Für die ausgewählten Oberthemen gibt es vor dem Stichtag keine Unterrichtsstunden.")

        term_token = self._extract_term_token(table)
        halfyear = term_token[-1]
        schoolyear = self._schoolyear_from_term(term_token)

        subject = str(table.metadata.get("Kursfach", "")).strip() or "Fach"
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", ""))).strip() or "Lerngruppe"
        topics = [section.oberthema for section in sections]
        title = f"Kompetenzhorizont: {', '.join(topics)}"
        subtitle = f"{subject} {group} {schoolyear} Hj. {halfyear}"

        document = ExpectedHorizonDocument(
            title=title,
            subtitle=subtitle,
            export_date_text=export_date.strftime("%d.%m.%Y"),
            sections=sections,
        )

        self._renderer.render(document, output_path, reconciled=self._reconcile(document, merge_source))
        return ExportExpectedHorizonResult(
            output_path=output_path,
            title=title,
            row_count=len(document.rows),
            oberthemen=tuple(topics),
        )

    def _reconcile(self, document: ExpectedHorizonDocument, merge_source: Path | None) -> ReconciledHorizon | None:
        """Gleicht das Dokument mit der Merge-Quelle ab (nur mit injiziertem Leser, sonst ``None``)."""
        if self._existing_reader is None:
            return None
        existing = self._existing_reader.read_existing_rows(merge_source) if merge_source is not None else []
        return reconcile(document.sections, existing)
