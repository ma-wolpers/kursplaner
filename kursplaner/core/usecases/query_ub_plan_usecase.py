from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_EINHEIT,
    UB_YAML_KEY_LANGENTWURF,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository, UbRepository


@dataclass(frozen=True)
class UbPlanRow:
    """Darstellung einer UB-Zeile im UB-Plan-Tab."""

    datum: str
    faecher: str
    plus: str
    kurs: str


@dataclass(frozen=True)
class UbPlanResult:
    """Getrennte Listen fuer kommende und absolvierte UBs."""

    upcoming_rows: tuple[UbPlanRow, ...]
    past_rows: tuple[UbPlanRow, ...]


class QueryUbPlanUseCase:
    """Liefert UB-Plan-Daten fuer die GUI als kommende und absolvierte Listen."""

    def __init__(self, ub_repo: UbRepository, plan_repo: PlanRepository):
        self.ub_repo = ub_repo
        self.plan_repo = plan_repo

    @staticmethod
    def _to_domain_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        return [text] if text else []

    @staticmethod
    def _to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"true", "1", "ja", "yes"}

    @staticmethod
    def _format_display_date(day: date) -> str:
        return f"{day.day:02d}.{day.month:02d}.{str(day.year)[-2:]}"

    @staticmethod
    def _extract_primary_link_target(text: str) -> str:
        match = re.search(r"\[\[([^\]]+)\]\]", str(text))
        if not match:
            return ""
        raw = match.group(1).strip()
        if "|" in raw:
            raw = raw.split("|", 1)[0].strip()
        if raw.lower().endswith(".md"):
            raw = raw[:-3].strip()
        if "/" in raw or "\\" in raw:
            raw = raw.replace("\\", "/").split("/")[-1].strip()
        return raw

    def _build_course_map(self, unterricht_base_dir: Path) -> dict[str, str]:
        if not unterricht_base_dir.exists() or not unterricht_base_dir.is_dir():
            return {}

        course_by_lesson_stem: dict[str, str] = {}
        for table in self.plan_repo.load_plan_tables(unterricht_base_dir):
            course_name = table.markdown_path.parent.name
            header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
            inhalt_idx = header_map.get("inhalt")
            if inhalt_idx is None:
                continue
            for row in table.rows:
                if inhalt_idx >= len(row):
                    continue
                stem = self._extract_primary_link_target(row[inhalt_idx])
                if not stem:
                    continue
                course_by_lesson_stem.setdefault(stem, course_name)
        return course_by_lesson_stem

    def execute(self, *, workspace_root: Path, unterricht_base_dir: Path) -> UbPlanResult:
        course_map = self._build_course_map(unterricht_base_dir)

        now = datetime.now()
        upcoming: list[tuple[date, UbPlanRow]] = []
        past: list[tuple[date, UbPlanRow]] = []

        for ub_path in self.ub_repo.list_ub_markdown_files(workspace_root):
            ub_date = parse_ub_date_from_stem(ub_path.stem)
            if ub_date is None:
                continue
            try:
                yaml_data, _ = self.ub_repo.load_ub_markdown(ub_path)
            except Exception:
                continue

            domains = self._to_domain_list(yaml_data.get(UB_YAML_KEY_BEREICH, []))
            langentwurf = self._to_bool(yaml_data.get(UB_YAML_KEY_LANGENTWURF, False))
            lesson_stem = strip_wiki_link(str(yaml_data.get(UB_YAML_KEY_EINHEIT, "")).strip())
            course_name = course_map.get(lesson_stem, "—")

            row = UbPlanRow(
                datum=self._format_display_date(ub_date),
                faecher=", ".join(domains) if domains else "—",
                plus="+" if langentwurf else "",
                kurs=course_name,
            )

            if ub_date_counts_as_past(ub_date, now=now):
                past.append((ub_date, row))
            else:
                upcoming.append((ub_date, row))

        upcoming.sort(key=lambda item: item[0])
        past.sort(key=lambda item: item[0], reverse=True)

        return UbPlanResult(
            upcoming_rows=tuple(row for _day, row in upcoming),
            past_rows=tuple(row for _day, row in past),
        )
