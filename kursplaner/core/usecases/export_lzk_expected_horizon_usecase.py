"""Exportiert den Kompetenzhorizont (KH) einer LZK als Markdown + PDF und pflegt die LZK.

Fachliche Identität eines KH ist **LZK + bereinigte Themenwahl** (gespeicherte
Liste ohne nicht mehr verfügbare Themen). Der Dateipfad ist frei wählbar und
keine Identität; die in ``Kompetenzhorizont`` verlinkte Datei ist der
*kanonische aktuelle Speicherort* der KH-Instanz der LZK.

Drei Fälle beim erneuten Export:

* gleiche LZK + gleiche Themenwahl + gleicher Pfad → bestehender KH wird
  aktualisiert (Merge-Quelle: diese Datei, Bewertungen bleiben),
* gleiche LZK + gleiche Themenwahl + neuer Pfad → dieselbe Identität am neuen
  kanonischen Speicherort: Link wird aktualisiert, Merge-Quelle ist die neue
  Zieldatei falls vorhanden, sonst die bisher verlinkte; die alte Datei bleibt,
* gleiche LZK + andere Themenwahl → neue Identität: ``Oberthema`` und Link
  zeigen auf den neuen KH, der alte bleibt als Datei liegen; Merge nur aus
  einer bewusst gewählten, bereits existierenden Zieldatei.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from kursplaner.core.config.path_store import infer_obsidian_vault_root
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.expected_horizon_files import (
    build_horizon_link,
    default_lzk_horizon_filename,
    resolve_horizon_link,
)
from kursplaner.core.domain.expected_horizon_pdf_layout import ExpectedHorizonPdfLayout
from kursplaner.core.domain.oberthema_values import OBERTHEMA_KEY, encode_oberthemen
from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData, parse_plan_row_date
from kursplaner.core.ports.repositories import LessonRepository
from kursplaner.core.usecases.expected_horizon_topic_query_usecase import (
    ExpectedHorizonTopicOptions,
    ExpectedHorizonTopicQueryUseCase,
)
from kursplaner.core.usecases.export_expected_horizon_usecase import ExportExpectedHorizonUseCase

KH_LINK_KEY = "Kompetenzhorizont"


@dataclass(frozen=True)
class LzkHorizonProposal:
    """Vorschlag für einen LZK-KH-Export: Themenoptionen, Identität und Speicherort.

    Args:
        options: Kandidaten, Vorbelegung und Warnungen (siehe `ExpectedHorizonTopicQueryUseCase`).
        lesson_path: Aufgelöster Pfad der LZK-Datei.
        lzk_date: Datum der LZK (Stichtag).
        course_dir: Aufgelöster Kursordner (Startordner des Speichern-Dialogs).
        vault_root: Obsidian-Vault-Wurzel oder ``None``.
        current_path: Kanonischer Speicherort des bisherigen KH, falls der Link
            auf eine existierende Datei zeigt, sonst ``None``.
    """

    options: ExpectedHorizonTopicOptions
    lesson_path: Path
    lzk_date: date
    course_dir: Path
    vault_root: Path | None
    current_path: Path | None

    @property
    def stored_selection(self) -> tuple[str, ...]:
        """Die bereinigte gespeicherte Themenwahl (ohne nicht verfügbare Themen, chronologisch)."""
        return self.options.ordered_selection(self.options.stored)

    def is_same_identity(self, selection: Sequence[str]) -> bool:
        """``True``, wenn die Auswahl dem bisherigen KH der LZK entspricht und dieser existiert."""
        stored = self.stored_selection
        return bool(stored) and self.current_path is not None and self.options.ordered_selection(selection) == stored

    def default_markdown_path(self, selection: Sequence[str], *, now: datetime) -> Path:
        """Default für den Speichern-Dialog: bisherige Datei bei gleicher Identität, sonst neuer Name."""
        if self.is_same_identity(selection) and self.current_path is not None:
            return self.current_path
        topics = self.options.ordered_selection(selection)
        return self.course_dir / default_lzk_horizon_filename(topics, lzk_date=self.lzk_date, created_at=now)


@dataclass(frozen=True)
class ExportLzkExpectedHorizonResult:
    """Ergebnis eines LZK-KH-Exports.

    Args:
        markdown_path: Geschriebene Markdown-Datei (neuer kanonischer Speicherort).
        pdf_path: Geschriebene PDF-Datei (gleicher Stem).
        title: Titel des KH.
        row_count: Anzahl Zielzeilen.
        oberthemen: Gespeicherte Themenwahl (chronologisch, erstes = Haupt-Oberthema).
        removed_unavailable: Aus der LZK entfernte, nicht mehr verfügbare Themen.
        link_written: ``False``, wenn die Datei außerhalb des Vaults liegt (kein Link).
        same_identity: ``True``, wenn es derselbe KH wie bisher ist.
    """

    markdown_path: Path
    pdf_path: Path
    title: str
    row_count: int
    oberthemen: tuple[str, ...]
    removed_unavailable: tuple[str, ...]
    link_written: bool
    same_identity: bool


class ExportLzkExpectedHorizonUseCase:
    """Exportiert den KH einer LZK (Markdown + PDF) und speichert Themenwahl und Link in der LZK."""

    def __init__(
        self,
        *,
        lesson_repo: LessonRepository,
        export_markdown_usecase: ExportExpectedHorizonUseCase,
        export_pdf_usecase: ExportExpectedHorizonUseCase,
        topic_query: ExpectedHorizonTopicQueryUseCase | None = None,
    ) -> None:
        """Initialisiert den Use Case.

        Args:
            lesson_repo: Port für Laden/Speichern der LZK-Datei.
            export_markdown_usecase: Markdown-Export mit Leser für die Merge-Quelle.
            export_pdf_usecase: PDF-Export.
            topic_query: Kandidatenabfrage (Default: neue Instanz).
        """
        self._lesson_repo = lesson_repo
        self._export_markdown_usecase = export_markdown_usecase
        self._export_pdf_usecase = export_pdf_usecase
        self._topic_query = topic_query or ExpectedHorizonTopicQueryUseCase()

    @staticmethod
    def _require_lzk(raw_day_columns: list[DayColumn], anchor_row_index: int) -> DayColumn:
        day = next((d for d in raw_day_columns if isinstance(d, DayColumn) and d.row_index == anchor_row_index), None)
        if day is None or not day.is_lzk():
            raise RuntimeError("Die ausgewählte Spalte ist keine LZK.")
        link = day.link
        if not isinstance(link, Path) or not link.is_file():
            raise RuntimeError("Für die ausgewählte LZK ist keine verlinkte Einheitsdatei vorhanden.")
        return day

    def build_proposal(
        self, *, table: PlanTableData, raw_day_columns: list[DayColumn], anchor_row_index: int
    ) -> LzkHorizonProposal:
        """Ermittelt Themenoptionen, bisherigen KH und Speicherort-Basis für die gewählte LZK.

        Raises:
            RuntimeError: Keine LZK, fehlende Datei/Datum, ungültiges LZK-Oberthema
                oder keine Kandidaten.
        """
        day = self._require_lzk(raw_day_columns, anchor_row_index)
        options = self._topic_query.query(raw_day_columns=raw_day_columns, anchor_row_index=anchor_row_index)
        lzk_date = parse_plan_row_date(day.datum)
        assert lzk_date is not None  # die Abfrage lehnt Anker ohne Datum ab

        course_dir = table.markdown_path.parent.resolve()
        vault_root = infer_obsidian_vault_root(course_dir)
        linked = resolve_horizon_link(day.yaml.get(KH_LINK_KEY, ""), course_dir=course_dir, vault_root=vault_root)
        current_path = linked.resolve() if linked is not None and linked.is_file() else None
        assert isinstance(day.link, Path)
        return LzkHorizonProposal(
            options=options,
            lesson_path=day.link.resolve(),
            lzk_date=lzk_date,
            course_dir=course_dir,
            vault_root=vault_root,
            current_path=current_path,
        )

    @staticmethod
    def _created_at_iso(now_dt: datetime | None) -> str:
        current = now_dt or datetime.now().astimezone()
        return current.replace(microsecond=0).isoformat(timespec="seconds")

    @staticmethod
    def _merge_source(proposal: LzkHorizonProposal, markdown_path: Path, same_identity: bool) -> Path | None:
        """Merge-Quelle nach den drei Identitätsfällen (siehe Modul-Docstring)."""
        if markdown_path.is_file():
            return markdown_path
        if same_identity and proposal.current_path is not None:
            return proposal.current_path
        return None

    def execute(
        self,
        *,
        table: PlanTableData,
        raw_day_columns: list[DayColumn],
        proposal: LzkHorizonProposal,
        selection: Sequence[str],
        markdown_path: Path,
        export_date: date,
        created_at: datetime | None = None,
        pdf_layout: ExpectedHorizonPdfLayout | None = None,
    ) -> ExportLzkExpectedHorizonResult:
        """Schreibt Markdown + PDF und aktualisiert ``Oberthema``/``Kompetenzhorizont`` der LZK.

        Args:
            table: Geladene Planungstabelle.
            raw_day_columns: Vollständige, unprojizierte Tagesliste.
            proposal: Ergebnis von `build_proposal`.
            selection: Gewählte Themen (werden bereinigt und chronologisch sortiert).
            markdown_path: Im Speichern-Dialog gewählter Markdown-Pfad.
            export_date: Exportdatum.
            created_at: Zeitstempel für ``created_at`` (Default: jetzt).
            pdf_layout: Darstellungsoptionen nur für das PDF (Aufgaben-Spalte,
                Schriftgröße); ``None`` = Standardlayout.

        Raises:
            RuntimeError: Bei leerer Auswahl oder wenn keine Stunden einfließen.
        """
        topics = proposal.options.ordered_selection(selection)
        if not topics:
            raise RuntimeError("Es ist kein Oberthema ausgewählt.")
        markdown_path = markdown_path.resolve()
        same_identity = proposal.is_same_identity(topics)
        cutoff = proposal.options.cutoff

        markdown_result = self._export_markdown_usecase.execute(
            table=table,
            raw_day_columns=raw_day_columns,
            oberthemen=topics,
            cutoff=cutoff,
            output_path=markdown_path,
            export_date=export_date,
            merge_source=self._merge_source(proposal, markdown_path, same_identity),
        )
        pdf_path = markdown_path.with_suffix(".pdf")
        self._export_pdf_usecase.execute(
            table=table,
            raw_day_columns=raw_day_columns,
            oberthemen=topics,
            cutoff=cutoff,
            output_path=pdf_path,
            export_date=export_date,
            layout=pdf_layout,
        )

        link = build_horizon_link(markdown_path, course_dir=proposal.course_dir, vault_root=proposal.vault_root)
        group_name = str(table.metadata.get("Lerngruppe", ""))
        lesson = self._lesson_repo.load_lesson_yaml(proposal.lesson_path)
        yaml_data = dict(lesson.data) if isinstance(lesson.data, dict) else {}
        yaml_data[OBERTHEMA_KEY] = encode_oberthemen(markdown_result.oberthemen or topics, group_name)
        yaml_data[KH_LINK_KEY] = link or ""
        yaml_data["created_at"] = self._created_at_iso(created_at)
        self._lesson_repo.save_lesson_yaml(LessonYamlData(lesson_path=proposal.lesson_path, data=yaml_data))

        return ExportLzkExpectedHorizonResult(
            markdown_path=markdown_result.output_path,
            pdf_path=pdf_path,
            title=markdown_result.title,
            row_count=markdown_result.row_count,
            oberthemen=markdown_result.oberthemen or topics,
            removed_unavailable=proposal.options.unavailable_stored,
            link_written=link is not None,
            same_identity=same_identity,
        )
