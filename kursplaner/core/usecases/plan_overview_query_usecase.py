from __future__ import annotations

from datetime import date, datetime

from kursplaner.core.domain.content_markers import is_ausfall_marker, normalize_marker_text
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonIndexRepository, LessonRepository


class PlanOverviewQueryUseCase:
    """Liefert zentrale Kennzahlen für die Unterrichts-Übersicht.

    Dieser Read-Use-Case berechnet aus einer Planung das nächste Thema,
    die verbleibenden Stunden und das Datum der nächsten LZK.
    """

    def __init__(self, lesson_repo: LessonRepository, lesson_index_repo: LessonIndexRepository | None = None):
        """Initialisiert den Überblicks-Use-Case mit optionalem Metadaten-Index.

        Bei vorhandenem `lesson_index_repo` werden Themen-Metadaten indexbasiert geladen.
        Ohne Index erfolgt ein Fallback auf `lesson_repo` mit voller YAML-Ladung.
        """
        self.lesson_repo = lesson_repo
        self.lesson_index_repo = lesson_index_repo

    @staticmethod
    def _keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv, ob eines der Schlüsselwörter enthalten ist."""
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

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

    def summarize_plan(
        self,
        table: PlanTableData,
        reference_day: date | None = None,
    ) -> tuple[str, int, str]:
        """Berechnet `(naechstes_thema, reststunden, naechste_lzk)` für eine Planung.

        Berücksichtigt nur Zeilen ab `reference_day`, ignoriert Ausfallmarker bei der
        Reststunden-Summe und nutzt sofern verfügbar den Lesson-Index.
        """
        reference = reference_day or date.today()

        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum")
        idx_stunden = header_map.get("stunden")
        idx_inhalt = header_map.get("inhalt")

        if idx_datum is None or idx_stunden is None or idx_inhalt is None:
            return "—", 0, "—"

        next_theme = "—"
        next_lzk = "—"
        remaining_hours = 0
        candidate_rows: list[int] = []
        row_dates: dict[int, str] = {}
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
                    "MetaLike", (), {"data": {"Stundenthema": meta.get("Stundenthema", "")}}
                )()
        else:
            lessons_by_row = self.lesson_repo.load_lessons_for_rows(table, candidate_rows)

        for row_index in candidate_rows:
            content = row_contents.get(row_index, "")
            marker_text = row_markers.get(row_index, "")
            row_date_text = row_dates.get(row_index, "")
            lesson = lessons_by_row.get(row_index)

            if lesson is not None:
                lesson_topic = str(lesson.data.get("Stundenthema", "")).strip()
                if next_theme == "—" and lesson_topic:
                    next_theme = lesson_topic
                if next_lzk == "—" and lesson_topic and "lzk" in lesson_topic.lower():
                    next_lzk = row_date_text
            else:
                if next_lzk == "—" and marker_text and "lzk" in marker_text.lower():
                    next_lzk = row_date_text

        return next_theme, remaining_hours, next_lzk
