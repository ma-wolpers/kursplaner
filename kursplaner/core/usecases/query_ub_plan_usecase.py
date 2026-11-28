from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_EINHEIT,
    UB_YAML_KEY_LANGENTWURF,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository, UbRepository
from kursplaner.core.usecases.ub_course_lookup import courses_by_lesson_stem


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

    def __init__(
        self,
        ub_repo: UbRepository,
        plan_repo: PlanRepository,
        past_cutoff_time_provider: Callable[[], time] | None = None,
    ):
        self.ub_repo = ub_repo
        self.plan_repo = plan_repo
        self._past_cutoff_time_provider = past_cutoff_time_provider

    def _past_cutoff_time(self) -> time:
        if self._past_cutoff_time_provider is None:
            return time(hour=15, minute=0)
        try:
            configured = self._past_cutoff_time_provider()
        except Exception:
            return time(hour=15, minute=0)
        if not isinstance(configured, time):
            return time(hour=15, minute=0)
        return configured

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

    def execute(self, *, workspace_root: Path, unterricht_base_dir: Path) -> UbPlanResult:
        """Kommende und absolvierte UBs; der Kurs kommt aus `ub_course_lookup.courses_by_lesson_stem`.

        Args:
            workspace_root: Workspace-Stamm (für den UB-Ordner).
            unterricht_base_dir: Unterrichtsordner mit allen Kursen – nicht ein einzelner Kursordner.

        Returns:
            `UbPlanResult` mit kommenden (aufsteigend) und absolvierten (absteigend) Zeilen.
        """
        courses = courses_by_lesson_stem(self.plan_repo, unterricht_base_dir)

        now = datetime.now()
        cutoff = self._past_cutoff_time()
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
            course_name = courses[lesson_stem].course_name if lesson_stem in courses else "—"

            row = UbPlanRow(
                datum=self._format_display_date(ub_date),
                faecher=", ".join(domains) if domains else "—",
                plus="+" if langentwurf else "",
                kurs=course_name,
            )

            if ub_date_counts_as_past(ub_date, now=now, cutoff_hour=cutoff.hour, cutoff_minute=cutoff.minute):
                past.append((ub_date, row))
            else:
                upcoming.append((ub_date, row))

        upcoming.sort(key=lambda item: item[0])
        past.sort(key=lambda item: item[0], reverse=True)

        return UbPlanResult(
            upcoming_rows=tuple(row for _day, row in upcoming),
            past_rows=tuple(row for _day, row in past),
        )
