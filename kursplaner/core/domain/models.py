from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class StartRequest:
    """Validierte Eingabedaten für die fachliche Plan-Erzeugung.

    Dieses Objekt wird vom Application-Layer an den Domain-Planer übergeben und
    enthält alle für die Terminberechnung erforderlichen Parameter.
    """

    course_subject: str
    subject_short: str
    group_name: str
    grade_level: int
    term: str
    day_hours: dict[int, int]
    base_dir: Path
    calendar_dir: Path
    kc_profile_label: str | None = None
    process_competencies: tuple[str, ...] = ()
    content_competency: str | None = None
    takeover_start: date | None = None
    stop_at_next_break: bool = False
    vacation_break_horizon: int = 1

    @property
    def folder_name(self) -> str:
        """Leitet den Unterrichtsordner-Namen deterministisch aus Fach, Gruppe und Halbjahr ab."""
        return f"{self.subject_short} {self.group_name} {self.term}"


@dataclass(frozen=True)
class PlanResult:
    """Fachliches Ergebnis einer Terminberechnung ohne Dateisystembezug."""

    rows_count: int
    range_start: date
    range_end: date
    warnings: list[str]


@dataclass(frozen=True)
class StartResult:
    """Ergebniscontainer für den Start-/Anlageprozess einer Unterrichtseinheit.

    Kombiniert erzeugte Pfade mit dem berechneten Planungsumfang.
    """

    lesson_dir: Path
    lesson_markdown: Path
    planned_rows: int
    range_start: date
    range_end: date
    warnings: list[str]


@dataclass(frozen=True)
class LessonOverviewItem:
    """Read-Modell für einen Eintrag in der Unterrichts-Übersicht.

    `load_error` ist optional und markiert Einträge, die beim aggregierten
    Übersichtslauf nicht vollständig ausgewertet werden konnten.
    """

    folder_name: str
    folder_path: Path
    markdown_path: Path | None
    next_topic: str = "—"
    remaining_hours: int = 0
    next_lzk: str = "—"
    load_error: str | None = None


@dataclass(frozen=True)
class ListLessonsResult:
    """Rückgabeobjekt der Unterrichts-Übersicht mit optionalen Warnhinweisen."""

    lessons: list[LessonOverviewItem]
    warnings: list[str]
