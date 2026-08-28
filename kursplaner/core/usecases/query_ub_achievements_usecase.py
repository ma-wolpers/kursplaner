from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.achievement_requirements import (
    AchievementTargets,
    DomainAchievementRequirements,
    compute_grade_group_progress,
)
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_JAHRGANGSSTUFE,
    UB_YAML_KEY_LANGENTWURF,
    parse_jahrgangsstufe,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.ports.repositories import AchievementRequirementsRepository, UbRepository


@dataclass(frozen=True)
class AchievementProgress:
    """Fortschrittsdarstellung eines einzelnen UB-Ziels."""

    key: str
    domain: str
    category: str
    symbol: str
    title: str
    current: int
    target: int
    tooltip: str
    is_fulfilled: bool


@dataclass(frozen=True)
class UbAchievementsResult:
    """Gesamtergebnis der UB-Fortschrittsabfrage."""

    items: list[AchievementProgress]


class QueryUbAchievementsUseCase:
    """Berechnet UB-Fortschritt gemäß den in `AchievementRequirementsRepository` konfigurierten Vorgaben."""

    DOMAIN_ORDER: tuple[str, ...] = ("Pädagogik", "Mathematik", "Informatik", "Darstellendes Spiel")
    CATEGORY_ORDER: tuple[str, ...] = ("half", "full", "ubplus", "bub")
    SUBJECTS: tuple[str, ...] = ("Mathematik", "Informatik", "Darstellendes Spiel")
    DOMAIN_SYMBOLS: dict[str, str] = {
        "Pädagogik": "◍",
        "Mathematik": "∑",
        "Informatik": "⌘",
        "Darstellendes Spiel": "◇",
    }
    DOMAIN_SHORT_LABELS: dict[str, str] = {
        "Pädagogik": "Päd",
        "Mathematik": "Mat",
        "Informatik": "Inf",
        "Darstellendes Spiel": "DSp",
    }
    CATEGORY_LABELS: dict[str, str] = {
        "half": "Halbzeit",
        "full": "UBs",
        "ubplus": "UBplus",
        "bub": "BUB",
    }

    def __init__(
        self,
        ub_repo: UbRepository,
        achievement_requirements_repo: AchievementRequirementsRepository,
        past_cutoff_time_provider: Callable[[], time] | None = None,
    ):
        self.ub_repo = ub_repo
        self._achievement_requirements_repo = achievement_requirements_repo
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

    @staticmethod
    def _bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"true", "1", "ja", "yes"}

    def _achievement(
        self,
        *,
        key: str,
        domain: str,
        category: str,
        current: int,
        target: int,
        tooltip: str,
        label_override: str | None = None,
    ) -> AchievementProgress:
        """Baut ein einzelnes Achievement-Item.

        `label_override` deckt dynamische, pro Vorgabe unterschiedliche Labels
        ab (z. B. Jahrgangsstufen-Gruppen), die nicht in die statische,
        domainuebergreifende `CATEGORY_LABELS`-Zuordnung passen.
        """
        bounded = max(0, min(int(current), int(target)))
        short_domain = self.DOMAIN_SHORT_LABELS.get(domain, "?")
        category_label = label_override if label_override is not None else self.CATEGORY_LABELS.get(category, "?")
        return AchievementProgress(
            key=key,
            domain=domain,
            category=category,
            symbol=self.DOMAIN_SYMBOLS.get(domain, "○"),
            title=f"{short_domain} {category_label}",
            current=bounded,
            target=int(target),
            tooltip=str(tooltip),
            is_fulfilled=bounded >= int(target),
        )

    def _append_grade_group_items(
        self,
        items: list[AchievementProgress],
        *,
        domain: str,
        domain_rows: list[dict[str, object]],
        requirements: DomainAchievementRequirements,
    ) -> None:
        """Haengt je konfigurierter Jahrgangsstufen-Vorgabe ein Achievement-Item an.

        Ein Fach ohne Vorgaben (leere `grade_groups`) bekommt keine
        zusaetzlichen Items -- kein vorgetaeuschter Fortschritt.
        """
        if not requirements.grade_groups:
            return

        jahrgangsstufen = [row["jahrgangsstufe"] for row in domain_rows if isinstance(row["jahrgangsstufe"], int)]
        for index, progress in enumerate(
            compute_grade_group_progress(jahrgangsstufen=jahrgangsstufen, requirements=requirements.grade_groups)
        ):
            items.append(
                self._achievement(
                    key=f"{domain}_grade_{index}",
                    domain=domain,
                    category=f"grade_{index}",
                    current=progress.current,
                    target=progress.target,
                    tooltip=f"Mind. {progress.target} UB(s) in Jahrgangsstufe {progress.label}.",
                    label_override=progress.label,
                )
            )

    def _append_paedagogik_items(
        self,
        items: list[AchievementProgress],
        *,
        rows: list[dict[str, object]],
        requirements_by_domain: dict[str, DomainAchievementRequirements],
    ) -> list[dict[str, object]]:
        """Berechnet Paedagogik-Items und liefert die zugehoerigen UB-Zeilen fuer die Grade-Group-Auswertung."""
        targets: AchievementTargets = requirements_by_domain["Pädagogik"].targets
        paed_rows = [row for row in rows if "Pädagogik" in row["bereiche"]]
        paed_total = len(paed_rows)

        items.append(
            self._achievement(
                key="paed_half",
                domain="Pädagogik",
                category="half",
                current=paed_total,
                target=targets.half,
                tooltip=f"{targets.half} von {targets.full} pädagogischen Besuchen.",
            )
        )
        items.append(
            self._achievement(
                key="paed_full",
                domain="Pädagogik",
                category="full",
                current=paed_total,
                target=targets.full,
                tooltip=f"{targets.full} von {targets.full} pädagogischen Besuchen.",
            )
        )

        if targets.bub is not None:
            # Fachlich gemeinte Bedingung: welche Faecher tracken ueberhaupt BUB (nicht: UBplus)?
            bub_cross_subjects = [s for s in self.SUBJECTS if requirements_by_domain[s].targets.bub is not None]
            paed_bub_total = sum(
                1
                for row in rows
                if bool(row["langentwurf"])
                and "Pädagogik" in row["bereiche"]
                and any(subject in row["bereiche"] for subject in bub_cross_subjects)
            )
            items.append(
                self._achievement(
                    key="paed_bub",
                    domain="Pädagogik",
                    category="bub",
                    current=paed_bub_total,
                    target=targets.bub,
                    tooltip=f"{targets.bub} BUBs mit pädagogischer Beteiligung ({', '.join(bub_cross_subjects)}).",
                )
            )

        return paed_rows

    def _append_subject_items(
        self,
        items: list[AchievementProgress],
        *,
        subject: str,
        rows: list[dict[str, object]],
        targets: AchievementTargets,
    ) -> list[dict[str, object]]:
        subject_rows = [row for row in rows if subject in row["bereiche"]]
        subject_total = len(subject_rows)
        lang_rows = [row for row in subject_rows if bool(row["langentwurf"])]
        bub_rows = [row for row in lang_rows if "Pädagogik" in row["bereiche"]]

        items.append(
            self._achievement(
                key=f"{subject}_half",
                domain=subject,
                category="half",
                current=subject_total,
                target=targets.half,
                tooltip=f"{targets.half} von {targets.full} Besuchen im Fach {subject}.",
            )
        )
        items.append(
            self._achievement(
                key=f"{subject}_full",
                domain=subject,
                category="full",
                current=subject_total,
                target=targets.full,
                tooltip=f"{targets.full} von {targets.full} Besuchen im Fach {subject}.",
            )
        )

        if targets.ubplus is not None:
            ubplus_current = 1 if len(lang_rows) >= 1 else 0
            items.append(
                self._achievement(
                    key=f"{subject}_ubplus",
                    domain=subject,
                    category="ubplus",
                    current=ubplus_current,
                    target=targets.ubplus,
                    tooltip="Erster Langentwurf-UB im Fach.",
                )
            )
        if targets.bub is not None:
            bub_current = 1 if len(bub_rows) >= 1 else 0
            items.append(
                self._achievement(
                    key=f"{subject}_bub",
                    domain=subject,
                    category="bub",
                    current=bub_current,
                    target=targets.bub,
                    tooltip="Langentwurf-UB mit Pädagogik im Fach.",
                )
            )

        return subject_rows

    def execute(self, *, workspace_root: Path) -> UbAchievementsResult:
        """Berechnet Teil- und Vollziele für alle Fächer und Pädagogik."""
        rows: list[dict[str, object]] = []
        now = self._now()
        cutoff = self._past_cutoff_time()
        for ub_path in self.ub_repo.list_ub_markdown_files(workspace_root):
            ub_date = parse_ub_date_from_stem(ub_path.stem)
            if ub_date is None or not ub_date_counts_as_past(
                ub_date,
                now=now,
                cutoff_hour=cutoff.hour,
                cutoff_minute=cutoff.minute,
            ):
                continue
            try:
                yaml_data, _ = self.ub_repo.load_ub_markdown(ub_path)
            except Exception:
                continue
            rows.append(
                {
                    "bereiche": self._list(yaml_data.get(UB_YAML_KEY_BEREICH, [])),
                    "langentwurf": self._bool(yaml_data.get(UB_YAML_KEY_LANGENTWURF, False)),
                    "jahrgangsstufe": parse_jahrgangsstufe(yaml_data.get(UB_YAML_KEY_JAHRGANGSSTUFE)),
                }
            )

        requirements_by_domain = self._achievement_requirements_repo.load_requirements()
        items: list[AchievementProgress] = []

        paed_rows = self._append_paedagogik_items(items, rows=rows, requirements_by_domain=requirements_by_domain)
        self._append_grade_group_items(
            items, domain="Pädagogik", domain_rows=paed_rows, requirements=requirements_by_domain["Pädagogik"]
        )

        for subject in self.SUBJECTS:
            requirements = requirements_by_domain[subject]
            subject_rows = self._append_subject_items(items, subject=subject, rows=rows, targets=requirements.targets)
            self._append_grade_group_items(items, domain=subject, domain_rows=subject_rows, requirements=requirements)

        category_rank = {name: index for index, name in enumerate(self.CATEGORY_ORDER)}
        domain_rank = {name: index for index, name in enumerate(self.DOMAIN_ORDER)}
        items.sort(
            key=lambda item: (
                0 if item.is_fulfilled else 1,
                category_rank.get(item.category, 99),
                domain_rank.get(item.domain, 99),
            )
        )

        return UbAchievementsResult(items=items)
