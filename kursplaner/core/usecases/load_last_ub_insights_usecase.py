from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_KIND_PAEDAGOGIK,
    UB_RESOURCES_FIELD,
    UB_STEPS_FIELD,
    UB_YAML_KEY_BEREICH,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
    ub_development_lists,
)
from kursplaner.core.ports.repositories import UbRepository


@dataclass(frozen=True)
class UbInsightSection:
    """Repräsentiert einen Bereich mit den zuletzt gefundenen UB-Impulsen."""

    domain_name: str
    steps: list[str]
    resources: list[str]

    def labeled_lists(self) -> list[tuple[str, list[str]]]:
        """Überschrift + Einträge je Liste, z. B. ``("Pädagogik - Baustellen", [...])`` – einzige Labelstelle.

        Returns:
            Zwei Paare: Baustellen, dann Ressourcen; Labels aus den ``UB_*``-Konstanten.
        """
        return [
            (f"{self.domain_name} - {UB_STEPS_FIELD}", list(self.steps)),
            (f"{self.domain_name} - {UB_RESOURCES_FIELD}", list(self.resources)),
        ]


@dataclass(frozen=True)
class LastUbInsightsResult:
    """Bündelt letzte Entwicklungsimpulse aus UB-Dateien."""

    subject: UbInsightSection
    paedagogik: UbInsightSection
    domain_sections: tuple[UbInsightSection, ...] = ()


class LoadLastUbInsightsUseCase:
    """Lädt die letzten UB-Entwicklungslisten (``Baustellen``/``Ressourcen``) je Bereich."""

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

    def _past_ub_lists(self, workspace_root: Path) -> Iterator[tuple[list[str], list[str], list[str]]]:
        """``(Bereiche, Baustellen, Ressourcen)`` vergangener UBs, neueste zuerst.

        Zukünftige UBs (Stichtag + Cutoff-Uhrzeit) und nicht lesbare Dateien werden
        übersprungen; UBs ohne Bereich auch.
        """
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
                yaml_data, _body = self.ub_repo.load_ub_markdown(ub_path)
                steps, resources = ub_development_lists(yaml_data, source_label=str(ub_path))
            except Exception:
                continue
            bereiche = self._list(yaml_data.get(UB_YAML_KEY_BEREICH, []))
            if bereiche:
                yield bereiche, steps, resources

    def _latest_sections(self, workspace_root: Path) -> tuple[UbInsightSection, ...]:
        """Je Bereich die Listen seiner letzten vergangenen UB; Pädagogik zuletzt."""
        sections_by_domain: dict[str, UbInsightSection] = {}
        for bereiche, steps, resources in self._past_ub_lists(workspace_root):
            for domain_name in bereiche:
                sections_by_domain.setdefault(
                    domain_name, UbInsightSection(domain_name=domain_name, steps=steps, resources=resources)
                )
        ordered = [name for name in sections_by_domain if name != UB_KIND_PAEDAGOGIK]
        if UB_KIND_PAEDAGOGIK in sections_by_domain:
            ordered.append(UB_KIND_PAEDAGOGIK)
        return tuple(sections_by_domain[name] for name in ordered)

    def execute(self, *, workspace_root: Path, subject_name: str) -> LastUbInsightsResult:
        """Liefert letzte Impulse des Fachs, der Pädagogik und aller Bereiche.

        Args:
            workspace_root: Workspace-Stamm (für den UB-Ordner).
            subject_name: Fach des aktuellen Kurses.

        Returns:
            `LastUbInsightsResult`; Bereiche ohne vergangene UB haben leere Listen.
        """
        sections = self._latest_sections(workspace_root)
        by_domain = {section.domain_name: section for section in sections}

        def section_for(domain_name: str) -> UbInsightSection:
            return by_domain.get(domain_name, UbInsightSection(domain_name=domain_name, steps=[], resources=[]))

        return LastUbInsightsResult(
            subject=section_for(subject_name),
            paedagogik=section_for(UB_KIND_PAEDAGOGIK),
            domain_sections=sections,
        )
