from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


@dataclass(frozen=True)
class CleanupLzkExpectedHorizonLinksResult:
    """Reports cleanup actions for missing KH files and invalid timestamps."""

    cleared_links: int
    repaired_timestamps: int


class CleanupLzkExpectedHorizonLinksUseCase:
    """Removes stale LZK KH links and repairs malformed creation timestamps."""

    _WIKI_LINK_RE = re.compile(r"^\[\[([^\]]+)\]\]$")

    def __init__(self, *, lesson_repo: LessonRepository) -> None:
        self._lesson_repo = lesson_repo

    @classmethod
    def _extract_link_stem(cls, raw_value: object) -> str:
        text = str(raw_value or "").strip()
        if not text:
            return ""

        match = cls._WIKI_LINK_RE.match(text)
        target = match.group(1).strip() if match else text
        if "|" in target:
            target = target.split("|", 1)[0].strip()
        if target.lower().endswith(".md"):
            target = target[:-3].strip()
        target = target.replace("\\", "/")
        if "/" in target:
            target = target.split("/")[-1].strip()
        return target

    @staticmethod
    def _parse_created_at(value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _iso_from_mtime(path: Path) -> str:
        dt = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        return dt.replace(microsecond=0).isoformat(timespec="seconds")

    def execute(
        self,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
    ) -> CleanupLzkExpectedHorizonLinksResult:
        course_dir = table.markdown_path.parent.resolve()
        cleared_links = 0
        repaired_timestamps = 0

        for day in day_columns:
            if not bool(day.get("is_lzk", False)):
                continue

            lesson_path = day.get("link")
            if not isinstance(lesson_path, Path) or not lesson_path.exists() or not lesson_path.is_file():
                continue

            lesson = self._lesson_repo.load_lesson_yaml(lesson_path)
            yaml_data = dict(lesson.data) if isinstance(lesson.data, dict) else {}
            changed = False

            stem = self._extract_link_stem(yaml_data.get("Kompetenzhorizont", ""))
            markdown_path = (course_dir / f"{stem}.md").resolve() if stem else None
            has_valid_markdown = isinstance(markdown_path, Path) and markdown_path.exists() and markdown_path.is_file()

            if stem and not has_valid_markdown:
                yaml_data["Kompetenzhorizont"] = ""
                yaml_data["created_at"] = ""
                cleared_links += 1
                changed = True
            elif has_valid_markdown:
                created_at = yaml_data.get("created_at", "")
                if self._parse_created_at(created_at) is None:
                    yaml_data["created_at"] = self._iso_from_mtime(markdown_path)
                    repaired_timestamps += 1
                    changed = True

            if changed:
                self._lesson_repo.save_lesson_yaml(LessonYamlData(lesson_path=lesson_path, data=yaml_data))

        return CleanupLzkExpectedHorizonLinksResult(
            cleared_links=cleared_links,
            repaired_timestamps=repaired_timestamps,
        )
