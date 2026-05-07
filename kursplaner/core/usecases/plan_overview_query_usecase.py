from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.content_markers import is_ausfall_marker, normalize_marker_text
from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_LANGENTWURF,
    parse_ub_date_from_stem,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import LessonIndexRepository, LessonRepository, UbRepository


class PlanOverviewQueryUseCase:
    """Liefert zentrale Kennzahlen für die Unterrichts-Übersicht.

    Dieser Read-Use-Case berechnet aus einer Planung das nächste Thema,
    die verbleibenden Stunden und das Datum der nächsten LZK.
    """

    UB_INITIAL_ORDER: tuple[str, ...] = (
        "Mathematik",
        "Informatik",
        "Darstellendes Spiel",
        "Pädagogik",
    )
    UB_INITIALS: dict[str, str] = {
        "Pädagogik": "P",
        "Mathematik": "M",
        "Informatik": "I",
        "Darstellendes Spiel": "DS",
    }

    def __init__(
        self,
        lesson_repo: LessonRepository,
        lesson_index_repo: LessonIndexRepository | None = None,
        ub_repo: UbRepository | None = None,
    ):
        """Initialisiert den Überblicks-Use-Case mit optionalem Metadaten-Index.

        Bei vorhandenem `lesson_index_repo` werden Themen-Metadaten indexbasiert geladen.
        Ohne Index erfolgt ein Fallback auf `lesson_repo` mit voller YAML-Ladung.
        """
        self.lesson_repo = lesson_repo
        self.lesson_index_repo = lesson_index_repo
        self.ub_repo = ub_repo

    @staticmethod
    def _parse_date(value: str) -> date | None:
        """Parst Plan-Datumswerte tolerant in bekannte Formate."""
        text = value.strip()
        if not text:
            return None
        for pattern in ("%d-%m-%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"true", "1", "ja", "yes"}

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        return infer_workspace_root_from_path(table.markdown_path)

    @classmethod
    def _format_ub_initials(cls, domains: list[str]) -> str:
        unique_domains = []
        for item in domains:
            text = str(item or "").strip()
            if text and text not in unique_domains:
                unique_domains.append(text)

        initials_by_domain = {
            domain: cls.UB_INITIALS.get(domain, domain[:1].upper()) for domain in unique_domains if domain
        }
        ordered = [
            initials_by_domain[domain]
            for domain in cls.UB_INITIAL_ORDER
            if domain in initials_by_domain and initials_by_domain[domain]
        ]
        remaining = [
            initials
            for domain, initials in initials_by_domain.items()
            if domain not in cls.UB_INITIAL_ORDER and initials
        ]
        return "".join(ordered + remaining)

    @classmethod
    def _format_next_ub_display(cls, *, ub_date: date, domains: list[str], langentwurf: bool) -> str:
        initials = cls._format_ub_initials(domains)
        marker = "+" if bool(langentwurf) else ""
        if initials:
            return f"{ub_date.day}.{ub_date.month}. {initials}{marker}"
        return f"{ub_date.day}.{ub_date.month}."

    def summarize_plan(
        self,
        table: PlanTableData,
        reference_day: date | None = None,
    ) -> tuple[str, int, str, str]:
        """Berechnet `(naechstes_thema, reststunden, naechste_lzk, naechster_ub)` fuer eine Planung.

        Berücksichtigt nur Zeilen ab `reference_day`, ignoriert Ausfallmarker bei der
        Reststunden-Summe und nutzt sofern verfügbar den Lesson-Index.
        """
        reference = reference_day or date.today()

        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum")
        idx_stunden = header_map.get("stunden")
        idx_inhalt = header_map.get("inhalt")

        if idx_datum is None or idx_stunden is None or idx_inhalt is None:
            return "—", 0, "—", ""

        next_theme = "—"
        next_lzk = "—"
        next_ub = ""
        earliest_ub_date: date | None = None
        remaining_hours = 0
        candidate_rows: list[int] = []
        row_dates: dict[int, str] = {}
        row_date_values: dict[int, date] = {}
        row_contents: dict[int, str] = {}
        row_markers: dict[int, str] = {}

        for row_index, row in enumerate(table.rows):
            if idx_datum >= len(row) or idx_stunden >= len(row) or idx_inhalt >= len(row):
                continue

            row_date = self._parse_date(row[idx_datum])
            if row_date is None or row_date < reference:
                continue

            content = row[idx_inhalt].strip()
            marker_text = normalize_marker_text(content)
            row_contents[row_index] = content
            row_markers[row_index] = marker_text
            row_dates[row_index] = row[idx_datum]
            row_date_values[row_index] = row_date
            candidate_rows.append(row_index)
            is_cancel = is_ausfall_marker(marker_text)

            if not is_cancel:
                hours_raw = row[idx_stunden].strip()
                if hours_raw.isdigit():
                    remaining_hours += int(hours_raw)

        # Prefer index-based metadata load if available to avoid full YAML loads per row.
        if self.lesson_index_repo is not None:
            lessons_meta = self.lesson_index_repo.load_lessons_metadata_for_rows(table, candidate_rows)
            # adapt index metadata shape to match previous `LessonYamlData`-based access
            lessons_by_row = {}
            for row_idx, meta in lessons_meta.items():
                lessons_by_row[row_idx] = type(
                    "MetaLike",
                    (),
                    {
                        "data": {
                            "Stundenthema": meta.get("Stundenthema", ""),
                            "Stundentyp": meta.get("Stundentyp", ""),
                        }
                    },
                )()
        else:
            lessons_by_row = self.lesson_repo.load_lessons_for_rows(table, candidate_rows)

        lessons_for_ub = self.lesson_repo.load_lessons_for_rows(table, candidate_rows)
        workspace_root = self._workspace_root_from_table(table)
        ub_root = self.ub_repo.ensure_ub_root(workspace_root) if self.ub_repo is not None else None

        for row_index in candidate_rows:
            content = row_contents.get(row_index, "")
            marker_text = row_markers.get(row_index, "")
            row_date_text = row_dates.get(row_index, "")
            lesson = lessons_by_row.get(row_index)
            lesson_for_ub = lessons_for_ub.get(row_index)

            if lesson is not None:
                lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
                lesson_topic = str(lesson_data.get("Stundenthema", "")).strip()
                if next_theme == "—" and lesson_topic:
                    next_theme = lesson_topic
                if next_lzk == "—" and infer_stundentyp(lesson_data) == "LZK":
                    next_lzk = row_date_text

            lesson_data = lesson_for_ub.data if lesson_for_ub is not None else {}
            if not isinstance(lesson_data, dict):
                continue

            ub_link = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
            if not ub_link:
                continue

            ub_path: Path | None = None
            if ub_root is not None:
                candidate = ub_root / f"{ub_link}.md"
                if candidate.exists() and candidate.is_file():
                    ub_path = candidate

            ub_date = parse_ub_date_from_stem(ub_path.stem if ub_path is not None else ub_link)
            if ub_date is None:
                ub_date = row_date_values.get(row_index)
            if ub_date is None or ub_date < reference:
                continue

            ub_domains: list[str] = []
            ub_langentwurf = False
            if ub_path is not None and self.ub_repo is not None:
                try:
                    ub_yaml, _ = self.ub_repo.load_ub_markdown(ub_path)
                except Exception:
                    ub_yaml = {}
                domains_value = ub_yaml.get(UB_YAML_KEY_BEREICH, [])
                if isinstance(domains_value, list):
                    ub_domains = [str(item).strip() for item in domains_value if str(item).strip()]
                elif str(domains_value).strip():
                    ub_domains = [str(domains_value).strip()]
                ub_langentwurf = self._to_bool(ub_yaml.get(UB_YAML_KEY_LANGENTWURF, False))

            if earliest_ub_date is None or ub_date < earliest_ub_date:
                earliest_ub_date = ub_date
                next_ub = self._format_next_ub_display(
                    ub_date=ub_date,
                    domains=ub_domains,
                    langentwurf=ub_langentwurf,
                )

        return next_theme, remaining_hours, next_lzk, next_ub
