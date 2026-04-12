from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_LANGENTWURF,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.ports.repositories import UbRepository


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
    """Berechnet UB-Fortschritt gemäß vereinbarter UBplus/BUB-Regeln."""

    DOMAIN_ORDER: tuple[str, ...] = ("Pädagogik", "Mathematik", "Informatik", "Darstellendes Spiel")
    CATEGORY_ORDER: tuple[str, ...] = ("half", "full", "ubplus", "bub")
    SUBJECTS: tuple[str, ...] = ("Mathematik", "Informatik", "Darstellendes Spiel")
    UBPLUS_BUB_SUBJECTS: tuple[str, ...] = ("Mathematik", "Informatik")
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
        title: str,
        current: int,
        target: int,
        tooltip: str,
    ) -> AchievementProgress:
        bounded = max(0, min(int(current), int(target)))
        short_domain = self.DOMAIN_SHORT_LABELS.get(domain, "?")
        category_label = self.CATEGORY_LABELS.get(category, "?")
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
                }
            )

        items: list[AchievementProgress] = []

        paed_total = sum(1 for row in rows if "Pädagogik" in row["bereiche"])
        items.append(
            self._achievement(
                key="paed_half",
                domain="Pädagogik",
                category="half",
                title="Pädagogik",
                current=paed_total,
                target=4,
                tooltip="4 von 8 pädagogischen Besuchen.",
            )
        )
        items.append(
            self._achievement(
                key="paed_full",
                domain="Pädagogik",
                category="full",
                title="Pädagogik",
                current=paed_total,
                target=8,
                tooltip="8 von 8 pädagogischen Besuchen.",
            )
        )

        paed_bub_total = sum(
            1
            for row in rows
            if bool(row["langentwurf"])
            and "Pädagogik" in row["bereiche"]
            and any(subject in row["bereiche"] for subject in self.UBPLUS_BUB_SUBJECTS)
        )
        items.append(
            self._achievement(
                key="paed_bub",
                domain="Pädagogik",
                category="bub",
                title="Pädagogik",
                current=paed_bub_total,
                target=2,
                tooltip="2 BUBs mit pädagogischer Beteiligung (Mathematik und Informatik).",
            )
        )

        for subject in self.SUBJECTS:
            subject_rows = [row for row in rows if subject in row["bereiche"]]
            subject_total = len(subject_rows)
            lang_rows = [row for row in subject_rows if bool(row["langentwurf"])]
            bub_rows = [row for row in lang_rows if "Pädagogik" in row["bereiche"]]

            ubplus_current = 1 if len(lang_rows) >= 1 else 0
            bub_current = 1 if len(bub_rows) >= 1 else 0

            items.append(
                self._achievement(
                    key=f"{subject}_half",
                    domain=subject,
                    category="half",
                    title=subject,
                    current=subject_total,
                    target=4,
                    tooltip=f"4 von 8 Besuchen im Fach {subject}.",
                )
            )
            items.append(
                self._achievement(
                    key=f"{subject}_full",
                    domain=subject,
                    category="full",
                    title=subject,
                    current=subject_total,
                    target=8,
                    tooltip=f"8 von 8 Besuchen im Fach {subject}.",
                )
            )

            if subject in self.UBPLUS_BUB_SUBJECTS:
                items.append(
                    self._achievement(
                        key=f"{subject}_ubplus",
                        domain=subject,
                        category="ubplus",
                        title=subject,
                        current=ubplus_current,
                        target=1,
                        tooltip="Erster Langentwurf-UB im Fach.",
                    )
                )
                items.append(
                    self._achievement(
                        key=f"{subject}_bub",
                        domain=subject,
                        category="bub",
                        title=subject,
                        current=bub_current,
                        target=1,
                        tooltip="Langentwurf-UB mit Pädagogik im Fach.",
                    )
                )

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
