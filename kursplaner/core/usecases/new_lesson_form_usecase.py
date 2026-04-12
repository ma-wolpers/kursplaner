from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.kompetenzkatalog import KompetenzkatalogManifestEntry
from kursplaner.core.domain.models import StartRequest
from kursplaner.core.domain.planner import find_next_halfyear_boundary_start
from kursplaner.core.domain.validators import (
    normalize_base_dir,
    normalize_calendar_dir,
    normalize_day_hours,
    normalize_grade_level,
    normalize_group,
    normalize_subject,
    parse_period_input,
)
from kursplaner.core.ports.repositories import CalendarRepository, KompetenzkatalogRepository


@dataclass(frozen=True)
class NewLessonFormData:
    """Rohdaten aus dem Neu-Unterricht-Formular."""

    subject_raw: str
    group_raw: str
    grade_raw: str
    period_raw: str
    base_dir_raw: str
    calendar_dir_raw: str
    day_hours_raw: dict[int, str]
    vacation_break_horizon_raw: str = "1"
    kc_profile_id_raw: str = ""
    process_competencies_raw: tuple[str, ...] = ()
    content_competency_raw: str = ""


@dataclass(frozen=True)
class InformatikKompetenzOptionen:
    """Beschreibt die im Formular verfuegbaren Informatik-Kompetenzoptionen."""

    profile_ids: tuple[str, ...]
    profile_labels: dict[str, str]
    process_competencies_by_profile: dict[str, tuple[str, ...]]
    content_competencies_by_profile: dict[str, tuple[str, ...]]
    process_display_lines_by_profile: dict[str, tuple[str, ...]]
    content_display_lines_by_profile: dict[str, tuple[str, ...]]
    warnings: tuple[str, ...] = ()

    @property
    def has_options(self) -> bool:
        """Signalisiert, ob fuer die gewaehlte Stufe mindestens ein Katalog vorliegt."""
        return bool(self.profile_ids)


class NewLessonFormUseCase:
    """Validiert Formulardaten und baut StartRequest/Preview ohne GUI-Abhängigkeit."""

    def __init__(self, calendar_repo: CalendarRepository, kompetenz_repo: KompetenzkatalogRepository):
        """Bindet Kalender-Repository zur Halbjahresableitung aus Startdatum."""
        self.calendar_repo = calendar_repo
        self.kompetenz_repo = kompetenz_repo
        self._catalog_path_overrides: dict[str, Path] = {}
        self._manifest_path_override: Path | None = None

    MissingCatalogResolver = Callable[[str, Path], Path | None]

    @staticmethod
    def is_informatik_subject(subject_raw: str) -> bool:
        """Prueft strikt, ob das Kursfach dem Standardwert Informatik entspricht."""
        try:
            return normalize_course_subject(subject_raw) == "Informatik"
        except Exception:
            return False

    @staticmethod
    def parse_vacation_horizon(raw_value: str) -> int:
        """Parst den Ferienhorizont strikt als positive Ganzzahl."""
        text = str(raw_value).strip()
        if not text:
            return 1
        if not text.isdigit():
            raise ValueError("Ferienhorizont muss eine positive Ganzzahl sein.")
        value = int(text)
        if value < 1:
            raise ValueError("Ferienhorizont muss mindestens 1 sein.")
        return value

    def _ferien_starts(self, start_date: date, calendar_dir: Path) -> list[date]:
        years = {start_date.year - 1, start_date.year, start_date.year + 1, start_date.year + 2}
        _, blocks, _ = self.calendar_repo.load_calendar_data(calendar_dir, years)
        ferien_blocks = [item for item in blocks if "ferien" in item[0].lower()]
        boundary = find_next_halfyear_boundary_start(start_date, ferien_blocks)
        return sorted(start for _, start, _ in ferien_blocks if start_date <= start <= boundary)

    def vacation_horizon_limits(self, form: NewLessonFormData) -> tuple[int, int]:
        """Liefert minimale und maximal verfügbare Horizonte für Datumsmodus."""
        _, start_date, is_date_mode = parse_period_input(form.period_raw)
        if not is_date_mode or start_date is None:
            return (1, 1)

        calendar_dir = normalize_calendar_dir(form.calendar_dir_raw)
        starts = self._ferien_starts(start_date, calendar_dir)
        if not starts:
            raise RuntimeError("Ab Startdatum wurden bis zur naechsten Halbjahresgrenze keine Ferienstarts gefunden.")
        return (1, len(starts))

    def preview_vacation_end_date(self, form: NewLessonFormData) -> date | None:
        """Berechnet das Enddatum (Ferienbeginn) für den gewählten numerischen Horizont."""
        _, start_date, is_date_mode = parse_period_input(form.period_raw)
        if not is_date_mode or start_date is None:
            return None

        horizon = self.parse_vacation_horizon(form.vacation_break_horizon_raw)
        calendar_dir = normalize_calendar_dir(form.calendar_dir_raw)
        starts = self._ferien_starts(start_date, calendar_dir)
        if horizon > len(starts):
            raise ValueError("Ferienhorizont liegt ausserhalb der naechsten Halbjahresgrenze.")
        return starts[horizon - 1]

    def preview_folder_name(self, form: NewLessonFormData) -> str | None:
        """Erzeugt eine Ordnervorschau oder ``None`` bei unvollständigen Eingaben."""
        course_subject = normalize_course_subject(form.subject_raw)
        subject_short = normalize_subject(course_subject)
        group_name = normalize_group(form.group_raw)
        calendar_dir = normalize_calendar_dir(form.calendar_dir_raw)
        term, start_date, is_date_mode = parse_period_input(form.period_raw)

        if is_date_mode and start_date is not None:
            term = self.calendar_repo.infer_term_from_date(start_date, calendar_dir)

        if not term:
            return None
        return f"{subject_short} {group_name} {term}"

    def build_start_request(self, form: NewLessonFormData) -> StartRequest:
        """Baut den vollständig validierten StartRequest aus Rohdaten."""
        course_subject = normalize_course_subject(form.subject_raw)
        subject_short = normalize_subject(course_subject)
        group_name = normalize_group(form.group_raw)
        grade_level = normalize_grade_level(form.grade_raw)
        day_hours = normalize_day_hours(form.day_hours_raw)
        base_dir = normalize_base_dir(form.base_dir_raw)
        calendar_dir = normalize_calendar_dir(form.calendar_dir_raw)

        term, start_date, is_date_mode = parse_period_input(form.period_raw)

        if is_date_mode:
            if start_date is None:
                raise ValueError("Startdatum fehlt.")
            term_for_title = self.calendar_repo.infer_term_from_date(start_date, calendar_dir)
            stop_at_next_break = True
            takeover_start = start_date
            horizon = self.parse_vacation_horizon(form.vacation_break_horizon_raw)
            _, max_horizon = self.vacation_horizon_limits(form)
            if horizon > max_horizon:
                raise ValueError("Ferienhorizont ueberschreitet die naechste Halbjahresgrenze.")
        else:
            if term is None:
                raise ValueError("Halbjahr fehlt.")
            term_for_title = term
            stop_at_next_break = False
            takeover_start = None
            horizon = 1

        kc_profile_label: str | None = None
        process_competencies: tuple[str, ...] = ()
        content_competency: str | None = None

        if self.is_informatik_subject(course_subject):
            profile_id = form.kc_profile_id_raw.strip()
            if profile_id:
                options = self.get_informatik_competency_options(grade_level)
                kc_profile_label = options.profile_labels.get(profile_id)

            process_competencies = tuple(
                competency.strip() for competency in form.process_competencies_raw if competency and competency.strip()
            )
            content_raw = form.content_competency_raw.strip()
            content_competency = content_raw or None

        return StartRequest(
            course_subject=course_subject,
            subject_short=subject_short,
            group_name=group_name,
            grade_level=grade_level,
            term=term_for_title,
            day_hours=day_hours,
            base_dir=base_dir,
            calendar_dir=calendar_dir,
            kc_profile_label=kc_profile_label,
            process_competencies=process_competencies,
            content_competency=content_competency,
            takeover_start=takeover_start,
            stop_at_next_break=stop_at_next_break,
            vacation_break_horizon=horizon,
        )

    def get_informatik_competency_options(
        self,
        grade_level: int,
        resolve_missing_catalog: MissingCatalogResolver | None = None,
    ) -> InformatikKompetenzOptionen:
        """Liefert Kataloge und Kompetenzen fuer Informatik in einer Jahrgangsstufe."""
        manifest_path = self._manifest_path_override or self.kompetenz_repo.default_manifest_path()
        try:
            entries = self.kompetenz_repo.load_manifest_entries_from(manifest_path)
        except (FileNotFoundError, RuntimeError, ValueError):
            if resolve_missing_catalog is not None:
                replacement = resolve_missing_catalog("Kompetenz-Manifest", manifest_path)
                if replacement is not None:
                    self._manifest_path_override = replacement
                    try:
                        entries = self.kompetenz_repo.load_manifest_entries_from(replacement)
                    except (FileNotFoundError, RuntimeError, ValueError):
                        entries = ()
                else:
                    entries = ()
            else:
                entries = ()
        warnings: list[str] = []
        profile_ids: list[str] = []
        profile_labels: dict[str, str] = {}
        process_map: dict[str, tuple[str, ...]] = {}
        content_map: dict[str, tuple[str, ...]] = {}
        process_display_map: dict[str, tuple[str, ...]] = {}
        content_display_map: dict[str, tuple[str, ...]] = {}

        for entry in entries:
            if entry.subject_code != "INF":
                continue
            if not (entry.grade_min <= grade_level <= entry.grade_max):
                continue

            catalog = self._load_catalog_entry(entry, resolve_missing_catalog)
            if catalog is None:
                warnings.append(f"KC-Datei fehlt/ungueltig: {entry.file_path}")
                continue

            profile_ids.append(catalog.profile_id)
            profile_labels[catalog.profile_id] = catalog.profile_label
            process_map[catalog.profile_id] = catalog.process_competencies
            content_map[catalog.profile_id] = catalog.content_competencies
            process_display: list[str] = []
            for section in catalog.process_sections:
                process_display.append(f"# {section.title}")
                process_display.extend(section.competencies)
            process_display_map[catalog.profile_id] = tuple(process_display)

            content_display: list[str] = []
            for section in catalog.content_sections:
                content_display.append(f"# {section.title}")
                content_display.extend(section.competencies)
            content_display_map[catalog.profile_id] = tuple(content_display)

        return InformatikKompetenzOptionen(
            profile_ids=tuple(profile_ids),
            profile_labels=profile_labels,
            process_competencies_by_profile=process_map,
            content_competencies_by_profile=content_map,
            process_display_lines_by_profile=process_display_map,
            content_display_lines_by_profile=content_display_map,
            warnings=tuple(warnings),
        )

    def profile_label_for_id(self, profile_id: str) -> str | None:
        """Liefert Label eines KC-Profils anhand der stabilen Profil-ID."""
        for entry in self.kompetenz_repo.list_manifest_entries():
            if entry.profile_id == profile_id:
                return entry.profile_label
        return None

    def _load_catalog_entry(
        self,
        entry: KompetenzkatalogManifestEntry,
        resolve_missing_catalog: MissingCatalogResolver | None,
    ):
        path = self._catalog_path_overrides.get(entry.profile_id, entry.file_path)
        try:
            catalog = self.kompetenz_repo.load_catalog_file(path, entry.profile_id)
        except (FileNotFoundError, RuntimeError, ValueError):
            if resolve_missing_catalog is None:
                return None
            replacement = resolve_missing_catalog(entry.profile_label, path)
            if replacement is None:
                return None
            self._catalog_path_overrides[entry.profile_id] = replacement
            try:
                catalog = self.kompetenz_repo.load_catalog_file(replacement, entry.profile_id)
            except (FileNotFoundError, RuntimeError, ValueError):
                return None
        if catalog.subject_code != "INF":
            return None
        return catalog
