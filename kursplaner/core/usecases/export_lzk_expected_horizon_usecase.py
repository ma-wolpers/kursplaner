from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.core.ports.repositories import LessonRepository
from kursplaner.core.usecases.export_expected_horizon_usecase import (
    ExportExpectedHorizonResult,
    ExportExpectedHorizonUseCase,
)


@dataclass(frozen=True)
class LzkExpectedHorizonTargets:
    """Resolved file targets and selected lesson path for one LZK export run."""

    lesson_path: Path
    markdown_path: Path
    pdf_path: Path


@dataclass(frozen=True)
class ExportLzkExpectedHorizonResult:
    """Result payload for dedicated LZK expected-horizon export."""

    markdown_path: Path
    pdf_path: Path
    title: str
    row_count: int


class ExportLzkExpectedHorizonUseCase:
    """Exports KH as Markdown+PDF for selected LZK and stores the lesson link."""

    _ALLOWED_SLUG_CHARS_RE = re.compile(r"[^0-9A-Za-zÄÖÜäöüß_-]+")

    def __init__(
        self,
        *,
        lesson_repo: LessonRepository,
        export_markdown_usecase: ExportExpectedHorizonUseCase,
        export_pdf_usecase: ExportExpectedHorizonUseCase,
    ) -> None:
        self._lesson_repo = lesson_repo
        self._export_markdown_usecase = export_markdown_usecase
        self._export_pdf_usecase = export_pdf_usecase

    @classmethod
    def _slugify_oberthema(cls, obert: str) -> str:
        normalized = re.sub(r"\s+", "_", str(obert or "").strip())
        normalized = cls._ALLOWED_SLUG_CHARS_RE.sub("", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_-")
        return normalized or "ohne_titel"

    @staticmethod
    def _row_index(day: dict[str, object]) -> int:
        raw = day.get("row_index", -1)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.strip().isdigit():
            return int(raw.strip())
        return -1

    @staticmethod
    def _require_selected_lzk(day: dict[str, object]) -> None:
        if not bool(day.get("is_lzk", False)):
            raise RuntimeError("Die ausgewählte Spalte ist keine LZK.")

    @staticmethod
    def _require_lesson_path(day: dict[str, object]) -> Path:
        link = day.get("link")
        if not isinstance(link, Path) or not link.exists() or not link.is_file():
            raise RuntimeError("Für die ausgewählte LZK ist keine verlinkte Einheitsdatei vorhanden.")
        return link.resolve()

    @staticmethod
    def _oberthema_from_lzk_yaml(yaml_data: dict[str, object]) -> str:
        obert = str(yaml_data.get("Oberthema", "")).strip()
        if not obert:
            raise RuntimeError("Die ausgewählte LZK hat kein Oberthema.")
        return obert

    def resolve_targets(
        self,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
        selected_day_index: int,
    ) -> LzkExpectedHorizonTargets:
        if selected_day_index < 0 or selected_day_index >= len(day_columns):
            raise RuntimeError("Es ist keine gültige Spalte ausgewählt.")

        selected_day = day_columns[selected_day_index]
        self._require_selected_lzk(selected_day)
        lesson_path = self._require_lesson_path(selected_day)

        lesson = self._lesson_repo.load_lesson_yaml(lesson_path)
        yaml_data = lesson.data if isinstance(lesson.data, dict) else {}
        obert = self._oberthema_from_lzk_yaml(yaml_data)

        base_stem = f"KH-{self._slugify_oberthema(obert)}"
        course_dir = table.markdown_path.parent.resolve()
        return LzkExpectedHorizonTargets(
            lesson_path=lesson_path,
            markdown_path=course_dir / f"{base_stem}.md",
            pdf_path=course_dir / f"{base_stem}.pdf",
        )

    @staticmethod
    def _created_at_iso(now_dt: datetime | None) -> str:
        current = now_dt or datetime.now().astimezone()
        return current.replace(microsecond=0).isoformat(timespec="seconds")

    def execute(
        self,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
        selected_day_index: int,
        export_date: date,
        created_at: datetime | None = None,
    ) -> ExportLzkExpectedHorizonResult:
        targets = self.resolve_targets(
            table=table,
            day_columns=day_columns,
            selected_day_index=selected_day_index,
        )

        markdown_result: ExportExpectedHorizonResult = self._export_markdown_usecase.execute(
            table=table,
            day_columns=day_columns,
            selected_day_index=selected_day_index,
            output_path=targets.markdown_path,
            export_date=export_date,
        )
        pdf_result: ExportExpectedHorizonResult = self._export_pdf_usecase.execute(
            table=table,
            day_columns=day_columns,
            selected_day_index=selected_day_index,
            output_path=targets.pdf_path,
            export_date=export_date,
        )

        lesson = self._lesson_repo.load_lesson_yaml(targets.lesson_path)
        yaml_data = dict(lesson.data) if isinstance(lesson.data, dict) else {}
        yaml_data["Kompetenzhorizont"] = build_wiki_link(targets.markdown_path.stem)
        yaml_data["created_at"] = self._created_at_iso(created_at)
        self._lesson_repo.save_lesson_yaml(LessonYamlData(lesson_path=targets.lesson_path, data=yaml_data))

        return ExportLzkExpectedHorizonResult(
            markdown_path=markdown_result.output_path,
            pdf_path=pdf_result.output_path,
            title=markdown_result.title,
            row_count=max(markdown_result.row_count, pdf_result.row_count),
        )
