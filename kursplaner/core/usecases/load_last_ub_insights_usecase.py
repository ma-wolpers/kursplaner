from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.ports.repositories import UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section


@dataclass(frozen=True)
class LastUbInsightsResult:
    """Bündelt letzte Entwicklungsimpulse aus UB-Dateien."""

    subject_steps: list[str]
    subject_resources: list[str]
    paedagogik_steps: list[str]
    paedagogik_resources: list[str]
    domain_sections: tuple["UbInsightSection", ...] = ()


@dataclass(frozen=True)
class UbInsightSection:
    """Repräsentiert einen Bereich mit den zuletzt gefundenen UB-Impulsen."""

    domain_name: str
    steps: list[str]
    resources: list[str]


class LoadLastUbInsightsUseCase:
    """Lädt letzte UB-Schwerpunkte für Fach und Pädagogik."""

    def __init__(
        self,
        ub_repo: UbRepository,
        past_cutoff_time_provider: Callable[[], time] | None = None,
    ):
        self.ub_repo = ub_repo
        self._past_cutoff_time_provider = past_cutoff_time_provider

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

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
    def _list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        return [text] if text else []

    def _latest_for_domain(self, workspace_root: Path, domain_name: str) -> tuple[list[str], list[str]]:
        now = self._now()
        cutoff = self._past_cutoff_time()
        for ub_path in reversed(self.ub_repo.list_ub_markdown_files(workspace_root)):
            ub_date = parse_ub_date_from_stem(ub_path.stem)
            if ub_date is not None and not ub_date_counts_as_past(
                ub_date,
                now=now,
                cutoff_hour=cutoff.hour,
                cutoff_minute=cutoff.minute,
            ):
                continue
            try:
                yaml_data, body = self.ub_repo.load_ub_markdown(ub_path)
            except Exception:
                continue
            bereiche = self._list(yaml_data.get(UB_YAML_KEY_BEREICH, []))
            if domain_name not in bereiche:
                continue
            return (
                parse_list_section(body, "Professionalisierungsschritte"),
                parse_list_section(body, "Nutzbare Ressourcen"),
            )
        return ([], [])

    def _latest_sections(self, workspace_root: Path) -> tuple[UbInsightSection, ...]:
        sections_by_domain: dict[str, UbInsightSection] = {}
        ordered_domains: list[str] = []
        now = self._now()
        cutoff = self._past_cutoff_time()

        for ub_path in reversed(self.ub_repo.list_ub_markdown_files(workspace_root)):
            ub_date = parse_ub_date_from_stem(ub_path.stem)
            if ub_date is not None and not ub_date_counts_as_past(
                ub_date,
                now=now,
                cutoff_hour=cutoff.hour,
                cutoff_minute=cutoff.minute,
            ):
                continue
            try:
                yaml_data, body = self.ub_repo.load_ub_markdown(ub_path)
            except Exception:
                continue

            bereiche = self._list(yaml_data.get(UB_YAML_KEY_BEREICH, []))
            if not bereiche:
                continue

            steps = parse_list_section(body, "Professionalisierungsschritte")
            resources = parse_list_section(body, "Nutzbare Ressourcen")

            for domain_name in bereiche:
                if domain_name in sections_by_domain:
                    continue
                sections_by_domain[domain_name] = UbInsightSection(
                    domain_name=domain_name,
                    steps=steps,
                    resources=resources,
                )
                ordered_domains.append(domain_name)

        if "Pädagogik" in sections_by_domain:
            ordered_domains = [name for name in ordered_domains if name != "Pädagogik"]
            ordered_domains.append("Pädagogik")

        return tuple(sections_by_domain[name] for name in ordered_domains)

    def execute(self, *, workspace_root: Path, subject_name: str) -> LastUbInsightsResult:
        """Liefert letzte Impulse des Fachs plus letzte pädagogische Impulse."""
        subject_steps, subject_resources = self._latest_for_domain(workspace_root, subject_name)
        paed_steps, paed_resources = self._latest_for_domain(workspace_root, "Pädagogik")
        sections = self._latest_sections(workspace_root)
        return LastUbInsightsResult(
            subject_steps=subject_steps,
            subject_resources=subject_resources,
            paedagogik_steps=paed_steps,
            paedagogik_resources=paed_resources,
            domain_sections=sections,
        )
