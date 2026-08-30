from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Callable, Sequence

from kursplaner.core.domain.achievement_requirements import (
    AchievementTargets,
    DomainAchievementRequirements,
    compute_grade_group_progress,
)
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_EINHEIT,
    UB_YAML_KEY_LANGENTWURF,
    parse_jahrgangsstufe,
    parse_ub_date_from_stem,
    ub_date_counts_as_past,
)
from kursplaner.core.domain.wiki_links import extract_wiki_link_target, strip_wiki_link
from kursplaner.core.ports.repositories import AchievementRequirementsRepository, PlanRepository, UbRepository


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
        plan_repo: PlanRepository,
        past_cutoff_time_provider: Callable[[], time] | None = None,
    ):
        self.ub_repo = ub_repo
        self._achievement_requirements_repo = achievement_requirements_repo
        self._plan_repo = plan_repo
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

    def _build_course_stufe_map(self, unterricht_base_dir: Path) -> dict[str, int | None]:
        """Leitet je Einheit (`lesson_stem`) die Jahrgangsstufe ihres Kurses ab.

        Single Source of Truth fuer die UB-Jahrgangs-Achievements: die Stufe
        kommt ausschliesslich aus der `Stufe`-Metadatenangabe des Kurses, zu
        dem eine Einheit gehoert -- nie aus einem UB-eigenen Feld (das gibt es
        bewusst nicht mehr, siehe `unterrichtsbesuch_policy.py`). Der Aufbau
        spiegelt `QueryUbPlanUseCase._build_course_map` (gleiche "Inhalt"-
        Spalten-Verlinkung), ergaenzt um eine Eindeutigkeits-Pruefung: da eine
        Einheit strukturell genau einem Kurs angehoert, waere ein doppelt
        vergebener `lesson_stem` ein Datenfehler -- das darf nicht
        stillschweigend eine falsche Stufe liefern, sondern muss laut auffallen.

        Raises:
            RuntimeError: wenn derselbe `lesson_stem` in mehr als einem Kurs
                verlinkt ist.
        """
        if not unterricht_base_dir.exists() or not unterricht_base_dir.is_dir():
            return {}

        stufe_by_lesson_stem: dict[str, int | None] = {}
        course_by_lesson_stem: dict[str, str] = {}
        for table in self._plan_repo.load_plan_tables(unterricht_base_dir):
            course_name = table.markdown_path.parent.name
            header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
            inhalt_idx = header_map.get("inhalt")
            if inhalt_idx is None:
                continue
            stufe = parse_jahrgangsstufe(table.metadata.get("Stufe"))
            for row in table.rows:
                if inhalt_idx >= len(row):
                    continue
                stem = extract_wiki_link_target(row[inhalt_idx])
                if not stem:
                    continue
                existing_course = course_by_lesson_stem.get(stem)
                if existing_course is not None and existing_course != course_name:
                    raise RuntimeError(
                        f"Uneindeutige Kurszuordnung: Einheit '{stem}' ist sowohl '{existing_course}' "
                        f"als auch '{course_name}' zugeordnet. Bitte die Kursdateien bereinigen."
                    )
                course_by_lesson_stem[stem] = course_name
                stufe_by_lesson_stem[stem] = stufe
        return stufe_by_lesson_stem

    def execute(self, *, workspace_root: Path, unterricht_base_dir: Path) -> UbAchievementsResult:
        """Berechnet Teil- und Vollziele für alle Fächer und Pädagogik."""
        course_stufe_map = self._build_course_stufe_map(unterricht_base_dir)

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
            lesson_stem = strip_wiki_link(str(yaml_data.get(UB_YAML_KEY_EINHEIT, "")).strip())
            rows.append(
                {
                    "bereiche": self._list(yaml_data.get(UB_YAML_KEY_BEREICH, [])),
                    "langentwurf": self._bool(yaml_data.get(UB_YAML_KEY_LANGENTWURF, False)),
                    "jahrgangsstufe": course_stufe_map.get(lesson_stem),
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


@dataclass(frozen=True)
class AchievementDomainGroup:
    """Eine Fach-Gruppe von Achievements, bereits nach Erfüllungsgrad sortiert."""

    domain: str
    items: tuple[AchievementProgress, ...]


def group_achievements_by_domain(
    items: Sequence[AchievementProgress],
    *,
    domain_order: tuple[str, ...] = QueryUbAchievementsUseCase.DOMAIN_ORDER,
) -> tuple[AchievementDomainGroup, ...]:
    """Gruppiert Achievements nach Fach für die Anzeige (GUI + PDF-Export).

    Einzige Definition von "gruppiert nach Fach, Fachreihenfolge gemäß
    `domain_order`, innerhalb der Gruppe nach Erfüllungsgrad absteigend
    sortiert" -- sowohl die GUI (`show_ub_achievements_view`) als auch der
    PDF-Export (`ExportAchievementsReportUseCase`) rufen ausschließlich diese
    Funktion auf, statt Gruppierung/Sortierung jeweils eigenständig
    nachzubauen. Fächer ganz ohne Items werden übersprungen (keine leere
    Gruppe). Ändert nichts an der Reihenfolge von `items` selbst bzw. an der
    Sortierung in `QueryUbAchievementsUseCase.execute()` -- das ist eine rein
    abgeleitete Präsentationsstruktur.
    """
    groups: list[AchievementDomainGroup] = []
    for domain in domain_order:
        domain_items = [item for item in items if item.domain == domain]
        if not domain_items:
            continue
        domain_items.sort(key=lambda item: item.current / max(1, item.target), reverse=True)
        groups.append(AchievementDomainGroup(domain=domain, items=tuple(domain_items)))
    return tuple(groups)
